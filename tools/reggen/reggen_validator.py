#!/usr/bin/env python3
"""
reggen_validator.py — Register spec linter (Phase 1)

Runs sanity checks on a YAML register spec BEFORE it is handed to the
RTL/header/docs generators. Catches mistakes that would otherwise produce
silently-broken RTL or compile errors deep in synthesis.

LEARNING NOTE: Real EDA flows have a layer just like this:
  - PeakRDL has `peakrdl validate` (semantic checks on the elaborated model)
  - Semifore CSRCompiler has a lint pass on its register database
  - Synopsys Register Compiler emits CDC/clock-domain warnings on the spec

The pattern is the same: parse the spec, walk every register/field, accumulate
errors and warnings, emit a structured report, exit non-zero if anything failed.

Usage:
    python3 reggen_validator.py --spec spec/irq_ctrl.yaml --outdir gen

Exit codes:
    0 — all checks passed (report written; generation may proceed)
    1 — one or more errors found (generation must be blocked)
"""

import argparse
import json
import os
import sys
import yaml

# Access types that the engine currently knows how to generate.
# If the spec references an unknown access type, that's a hard error —
# the engine wouldn't produce sensible RTL for it.
VALID_ACCESS_TYPES = {"rw", "ro", "wo", "w1c", "rclr"}


# ---------------------------------------------------------------------------
# Helpers — bit-range parsing (same semantics as reggen_engine.py)
# ---------------------------------------------------------------------------

def parse_bits(bits_str):
    """
    "0"   -> (0, 0)
    "2:1" -> (2, 1)   (MSB:LSB)
    Returns (msb, lsb) ints, or raises ValueError if the string is malformed.
    """
    s = str(bits_str).strip()
    if ":" in s:
        msb_s, lsb_s = s.split(":")
        return int(msb_s), int(lsb_s)
    bit = int(s)
    return bit, bit


def field_width(msb, lsb):
    return msb - lsb + 1


def bit_set(msb, lsb):
    """Return the set of bit positions a field covers."""
    return set(range(lsb, msb + 1))


# ---------------------------------------------------------------------------
# Individual checks — each one returns a list of error strings
# ---------------------------------------------------------------------------

def check_field_bits_in_range(reg, field, reg_width):
    """CHECK 1: every bit referenced by the field must be < reg_width."""
    errors = []
    try:
        msb, lsb = parse_bits(field["bits"])
    except (ValueError, KeyError) as e:
        errors.append(
            f"{reg['name']}.{field.get('name', '?')}: malformed 'bits' field "
            f"({field.get('bits', '<missing>')}) — {e}"
        )
        return errors

    if lsb < 0 or msb < 0:
        errors.append(
            f"{reg['name']}.{field['name']}: negative bit index in bits=\"{field['bits']}\""
        )
    if msb < lsb:
        errors.append(
            f"{reg['name']}.{field['name']}: MSB ({msb}) < LSB ({lsb}) in "
            f"bits=\"{field['bits']}\" (use \"MSB:LSB\" notation)"
        )
    if msb >= reg_width:
        errors.append(
            f"{reg['name']}.{field['name']}: bit {msb} is outside the {reg_width}-bit "
            f"register (max valid bit = {reg_width - 1})"
        )
    return errors


def check_no_overlap(reg):
    """CHECK 2: within a register, no two fields may share a bit position."""
    errors = []
    seen = {}  # bit-position -> field name that owns it
    for field in reg["fields"]:
        try:
            msb, lsb = parse_bits(field["bits"])
        except (ValueError, KeyError):
            continue  # already flagged by CHECK 1
        for b in bit_set(msb, lsb):
            if b in seen:
                errors.append(
                    f"{reg['name']}.{field['name']}: bit {b} overlaps with "
                    f"{reg['name']}.{seen[b]}"
                )
            else:
                seen[b] = field["name"]
    return errors


def check_unique_field_names(reg):
    """CHECK 3: field names must be unique within a register."""
    errors = []
    seen = set()
    for field in reg["fields"]:
        name = field.get("name", "<missing>")
        if name in seen:
            errors.append(f"{reg['name']}: duplicate field name '{name}'")
        seen.add(name)
    return errors


def check_reset_fits_width(reg, field):
    """CHECK 4: reset value must fit within the field's bit width."""
    errors = []
    try:
        msb, lsb = parse_bits(field["bits"])
    except (ValueError, KeyError):
        return errors  # CHECK 1 catches this
    width = field_width(msb, lsb)
    reset = field.get("reset", 0)
    max_val = (1 << width) - 1
    if reset < 0:
        errors.append(
            f"{reg['name']}.{field['name']}: reset value {reset} is negative"
        )
    elif reset > max_val:
        errors.append(
            f"{reg['name']}.{field['name']}: reset value {reset} does not fit in "
            f"{width}-bit field (max = {max_val})"
        )
    return errors


def check_unique_offsets(registers):
    """CHECK 5: no two registers may share an offset."""
    errors = []
    seen = {}  # offset_int -> reg name
    for reg in registers:
        try:
            offset = reg["offset"]
            offset_int = int(offset, 16) if isinstance(offset, str) else int(offset)
        except (ValueError, KeyError):
            errors.append(f"{reg.get('name', '?')}: malformed 'offset' field")
            continue
        if offset_int in seen:
            errors.append(
                f"{reg['name']}: offset 0x{offset_int:X} collides with register "
                f"'{seen[offset_int]}'"
            )
        else:
            seen[offset_int] = reg["name"]
    return errors


def check_offset_alignment(reg, reg_width):
    """CHECK 6: register offsets must be aligned to the bus width (in bytes)."""
    errors = []
    try:
        offset = reg["offset"]
        offset_int = int(offset, 16) if isinstance(offset, str) else int(offset)
    except (ValueError, KeyError):
        return errors  # CHECK 5 already flags this

    byte_width = reg_width // 8
    if offset_int % byte_width != 0:
        errors.append(
            f"{reg['name']}: offset 0x{offset_int:X} is not aligned to {byte_width} bytes "
            f"(APB requires {reg_width}-bit word alignment)"
        )
    return errors


def check_access_type(reg, field):
    """Bonus check: access type must be one the engine knows."""
    errors = []
    access = field.get("access")
    if access not in VALID_ACCESS_TYPES:
        errors.append(
            f"{reg['name']}.{field['name']}: unknown access type '{access}' "
            f"(valid: {sorted(VALID_ACCESS_TYPES)})"
        )
    return errors


# ---------------------------------------------------------------------------
# Orchestration — run all checks, collect errors, emit report
# ---------------------------------------------------------------------------

def validate(spec):
    """
    Run every check against the spec dict. Returns (errors, warnings) — two lists
    of human-readable strings. errors=[] means PASS.
    """
    errors = []
    warnings = []

    reg_width = spec.get("reg_width", 32)
    registers = spec.get("registers", [])

    # Register-level checks
    errors += check_unique_offsets(registers)

    for reg in registers:
        errors += check_offset_alignment(reg, reg_width)
        errors += check_unique_field_names(reg)
        errors += check_no_overlap(reg)
        for field in reg["fields"]:
            errors += check_field_bits_in_range(reg, field, reg_width)
            errors += check_reset_fits_width(reg, field)
            errors += check_access_type(reg, field)

    return errors, warnings


def write_report(spec_path, outdir, errors, warnings):
    """Emit a JSON report capturing the validator's findings."""
    os.makedirs(outdir, exist_ok=True)
    report = {
        "tool":       "reggen_validator",
        "spec":       spec_path,
        "status":     "PASS" if not errors else "FAIL",
        "error_count":   len(errors),
        "warning_count": len(warnings),
        "errors":     errors,
        "warnings":   warnings,
    }
    path = os.path.join(outdir, "validation_report.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="reggen_validator — lint a YAML register spec before generation"
    )
    parser.add_argument("--spec",   required=True, help="Path to register spec YAML")
    parser.add_argument("--outdir", required=True, help="Where to write validation_report.json")
    args = parser.parse_args()

    with open(args.spec) as f:
        spec = yaml.safe_load(f)

    errors, warnings = validate(spec)
    report_path = write_report(args.spec, args.outdir, errors, warnings)

    # Print findings to stderr so they're visible even when stdout is captured.
    for w in warnings:
        print(f"[validator] WARN : {w}", file=sys.stderr)
    for e in errors:
        print(f"[validator] ERROR: {e}", file=sys.stderr)

    if errors:
        print(f"[validator] FAIL — {len(errors)} error(s). See {report_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[validator] PASS — spec is clean. Report: {report_path}")


if __name__ == "__main__":
    main()
