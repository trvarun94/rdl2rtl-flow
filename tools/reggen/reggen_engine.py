#!/usr/bin/env python3
"""
reggen_engine.py — Register generation engine (Phase 0: RTL output)

LEARNING NOTE: This is a simplified mock of what commercial register generators do.
Real tools that solve the same problem:
  - PeakRDL     (open source, SystemRDL input)
  - Semifore    (commercial, industry standard)
  - Agnisys     (commercial, IDesignSpec)
  - Synopsys Register Compiler (part of Design Compiler)

Those tools take SystemRDL (.rdl) as input. We use YAML here so the parsing is
transparent — you can see exactly what data drives the generation.

Usage:
    python3 reggen_engine.py --spec <spec.yaml> --outdir <output_dir> --output rtl
"""

import argparse
import json
import os
import sys
import yaml  # PyYAML — pip install pyyaml


# ---------------------------------------------------------------------------
# Spec loading and field parsing
# ---------------------------------------------------------------------------

def load_spec(path):
    """Load and return the YAML register spec as a Python dict."""
    with open(path) as f:
        return yaml.safe_load(f)


def parse_bits(bits_str):
    """
    Parse a bit-range string into (msb, lsb) integers.

    Examples:
      "0"   -> (0, 0)    single bit
      "2:1" -> (2, 1)    two-bit field, MSB:LSB notation
    """
    bits_str = str(bits_str).strip()
    if ":" in bits_str:
        msb_s, lsb_s = bits_str.split(":")
        return int(msb_s), int(lsb_s)
    else:
        bit = int(bits_str)
        return bit, bit


def field_width(msb, lsb):
    """Return the number of bits in a field."""
    return msb - lsb + 1


# ---------------------------------------------------------------------------
# RTL generation: APB register block
# ---------------------------------------------------------------------------

def generate_rtl(spec):
    """
    Generate a SystemVerilog APB register block from the parsed spec dict.
    Returns the RTL as a string.

    HARDWARE CONCEPT — APB transaction:
      APB has a simple 2-phase handshake:
        Phase 1 (SETUP):  manager drives PADDR, PWRITE, PWDATA, asserts PSEL
        Phase 2 (ACCESS): manager asserts PENABLE; subordinate responds
      We always drive PREADY=1 (zero-wait-state response).

    GENERATED STRUCTURE:
      1. Module header + APB port list
      2. One storage flip-flop per rw field (ro fields are HW input ports)
      3. Write logic: on rising clock, if PSEL & PENABLE & PWRITE, decode address
         and write PWDATA bits into the right field storage flops
      4. Read mux: combinatorially drive PRDATA based on PADDR
    """
    block     = spec["block"]
    base_addr = spec["base_addr"]
    registers = spec["registers"]

    lines = []

    # ------------------------------------------------------------------
    # Header comment
    # ------------------------------------------------------------------
    lines += [
        f"// ============================================================",
        f"// GENERATED FILE — do not edit by hand.",
        f"// Source: spec/{block}.yaml",
        f"// Generator: tools/reggen/reggen_engine.py",
        f"//",
        f"// Block  : {block}",
        f"// Base   : {hex(base_addr) if isinstance(base_addr, int) else base_addr}",
        f"// Regs   : {len(registers)}",
        f"//",
        f"// LEARNING NOTE: This is an APB (Advanced Peripheral Bus) register block.",
        f"// APB is the simplest AMBA bus — used for low-bandwidth control/status",
        f"// registers. The CPU writes/reads registers over APB; hardware logic",
        f"// uses the register values to control behavior.",
        f"// ============================================================",
        f"",
        f"`timescale 1ns/1ps",
        f"",
    ]

    # ------------------------------------------------------------------
    # Module declaration + APB ports
    # ------------------------------------------------------------------
    # LEARNING NOTE: 'logic' is the SystemVerilog type for all signals.
    # Cleaner than old Verilog's wire/reg distinction.
    #
    # We build port DECLARATIONS and COMMENTS separately so we can put
    # commas only between declarations — the last port must NOT have a
    # trailing comma (that's a SV syntax error).

    # Each entry is (declaration, comment).  Comment may be "".
    port_entries = [
        ("    // APB subordinate interface",                  ""),  # heading row, no comma needed
        ("    input  logic        PCLK",                       "Clock — registers update on rising edge"),
        ("    input  logic        PRESETn",                    "Active-low reset — 0 means reset asserted"),
        ("    input  logic [31:0] PADDR",                      "Byte address from the APB manager (CPU)"),
        ("    input  logic        PWRITE",                     "1 = write transaction, 0 = read transaction"),
        ("    input  logic        PSEL",                       "This block is selected"),
        ("    input  logic        PENABLE",                    "Second cycle of APB transfer (access phase)"),
        ("    input  logic [31:0] PWDATA",                     "Write data from the manager"),
        ("    output logic [31:0] PRDATA",                     "Read data back to the manager"),
        ("    output logic        PREADY",                     "We're ready (tied 1 = zero wait states)"),
    ]

    # Hardware input ports for 'ro' fields
    # LEARNING NOTE: ro fields are driven INTO the register FROM hardware logic
    # (e.g., a state machine elsewhere in the chip sets BUSY=1 when it's running).
    # Software can only read them — it cannot write them.
    for reg in registers:
        for field in reg["fields"]:
            if field["access"] == "ro":
                msb, lsb = parse_bits(field["bits"])
                width = field_width(msb, lsb)
                port_name = f"hw_{reg['name']}_{field['name']}"
                w = f"[{width-1}:0] " if width > 1 else "       "
                port_entries.append(
                    (f"    input  logic {w}{port_name}",
                     f"HW-driven: {reg['name']}.{field['name']}")
                )

    # Render: comma after every real port EXCEPT the last; heading rows get no comma.
    lines.append(f"module {block} (")

    # Find the index of the last entry that is a real port (not a heading/blank).
    last_port_idx = max(i for i, (d, _) in enumerate(port_entries) if d.lstrip().startswith(("input", "output", "inout")))

    for i, (decl, comment) in enumerate(port_entries):
        is_heading = not decl.lstrip().startswith(("input", "output", "inout"))
        if is_heading:
            lines.append(decl)
            continue
        suffix = "" if i == last_port_idx else ","
        if comment:
            lines.append(f"{decl}{suffix}  // {comment}")
        else:
            lines.append(f"{decl}{suffix}")

    lines += [
        f");",
        f"",
        f"    // PREADY = 1: always respond in the access phase, no wait states.",
        f"    assign PREADY = 1'b1;",
        f"",
    ]

    # ------------------------------------------------------------------
    # Storage flip-flops for rw fields
    # ------------------------------------------------------------------
    # LEARNING NOTE: Only rw fields need storage flip-flops.
    # ro fields are just wires connected to hardware input ports above.
    lines += [
        f"    // --------------------------------------------------------",
        f"    // Storage flip-flops — one per rw field",
        f"    // Hold the value software last wrote. Hardware reads these",
        f"    // to know what software requested.",
        f"    // --------------------------------------------------------",
    ]
    for reg in registers:
        for field in reg["fields"]:
            if field["access"] == "rw":
                msb, lsb = parse_bits(field["bits"])
                width = field_width(msb, lsb)
                sig_name = f"r_{reg['name']}_{field['name']}"
                w = f"[{width-1}:0] " if width > 1 else "       "
                lines.append(
                    f"    logic {w}{sig_name};"
                    f"  // {reg['name']}.{field['name']} ({width}-bit rw)"
                )

    lines.append("")

    # ------------------------------------------------------------------
    # Write logic (sequential — clocked)
    # ------------------------------------------------------------------
    # LEARNING NOTE: always_ff is the SystemVerilog idiom for flip-flop logic.
    # @(posedge PCLK) = "trigger on every rising clock edge."
    # PRESETn is active-low: PRESETn==0 means reset is asserted.
    lines += [
        f"    // --------------------------------------------------------",
        f"    // Write logic — triggered on APB write: PSEL & PENABLE & PWRITE",
        f"    // Decode PADDR[7:0] to find which register, then store PWDATA",
        f"    // bits into the matching field flip-flops.",
        f"    // --------------------------------------------------------",
        f"    always_ff @(posedge PCLK or negedge PRESETn) begin",
        f"        if (!PRESETn) begin",
        f"            // On reset: drive every rw field to its configured reset value",
    ]

    for reg in registers:
        for field in reg["fields"]:
            if field["access"] == "rw":
                msb, lsb = parse_bits(field["bits"])
                width = field_width(msb, lsb)
                reset_val = field.get("reset", 0)
                sig_name = f"r_{reg['name']}_{field['name']}"
                lines.append(f"            {sig_name} <= {width}'d{reset_val};")

    lines += [
        f"        end else if (PSEL && PENABLE && PWRITE) begin",
        f"            // APB write: decode address offset, update matching fields.",
        f"            // PADDR[7:0] gives the register offset within this block.",
        f"            case (PADDR[7:0])",
    ]

    for reg in registers:
        offset = reg["offset"]
        offset_int = int(offset, 16) if isinstance(offset, str) else offset
        rw_fields = [f for f in reg["fields"] if f["access"] == "rw"]
        if rw_fields:
            lines.append(f"                8'h{offset_int:02X}: begin  // {reg['name']}")
            for field in rw_fields:
                msb, lsb = parse_bits(field["bits"])
                sig_name = f"r_{reg['name']}_{field['name']}"
                slice_expr = f"PWDATA[{msb}:{lsb}]" if msb != lsb else f"PWDATA[{lsb}]"
                lines.append(
                    f"                    {sig_name} <= {slice_expr};"
                    f"  // {field['name']}, bits [{msb}:{lsb}]"
                )
            lines.append(f"                end")

    lines += [
        f"                default: ;  // write to unknown offset — silently ignored",
        f"            endcase",
        f"        end",
        f"    end",
        f"",
    ]

    # ------------------------------------------------------------------
    # Read mux (combinational)
    # ------------------------------------------------------------------
    # LEARNING NOTE: always_comb = combinational logic (no clock, no flops).
    # PRDATA updates immediately whenever PADDR or field values change.
    # We reconstruct the full 32-bit register by OR-ing each field into
    # its correct bit position within the word.
    lines += [
        f"    // --------------------------------------------------------",
        f"    // Read mux — drive PRDATA based on PADDR (combinational)",
        f"    // Reconstruct the 32-bit register word by placing each field",
        f"    // at its correct bit position and OR-ing them together.",
        f"    // --------------------------------------------------------",
        f"    always_comb begin",
        f"        PRDATA = 32'h0;  // default: unimplemented addresses read as 0",
        f"        if (PSEL && !PWRITE) begin",
        f"            case (PADDR[7:0])",
    ]

    for reg in registers:
        offset = reg["offset"]
        offset_int = int(offset, 16) if isinstance(offset, str) else offset
        lines.append(f"                8'h{offset_int:02X}: begin  // {reg['name']}")
        terms = []
        for field in reg["fields"]:
            msb, lsb = parse_bits(field["bits"])
            sig = (f"r_{reg['name']}_{field['name']}" if field["access"] == "rw"
                   else f"hw_{reg['name']}_{field['name']}")
            # Shift field value up to its bit position in the 32-bit word
            terms.append(f"(32'({sig}) << {lsb})" if lsb > 0 else f"32'({sig})")
        lines.append(f"                    PRDATA = {' | '.join(terms)};")
        lines.append(f"                end")

    lines += [
        f"                default: PRDATA = 32'h0;",
        f"            endcase",
        f"        end",
        f"    end",
        f"",
        f"endmodule  // {block}",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Generation manifest (JSON)
# ---------------------------------------------------------------------------

def write_manifest(spec, outdir, outputs_written):
    """
    Write a small JSON manifest recording what was generated and from what.
    Real tools produce run reports for auditing — this mimics that practice.
    """
    base = spec["base_addr"]
    manifest = {
        "tool": "reggen",
        "block": spec["block"],
        # Store as hex string for readability; YAML parses 0x... as an int.
        "spec_base_addr": hex(base) if isinstance(base, int) else base,
        "register_count": len(spec["registers"]),
        "field_count": sum(len(r["fields"]) for r in spec["registers"]),
        "outputs": outputs_written,
    }
    manifest_path = os.path.join(outdir, f"{spec['block']}_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="reggen_engine — register generation engine (learning mock of PeakRDL/Semifore)"
    )
    parser.add_argument("--spec",   required=True, help="Path to register spec YAML")
    parser.add_argument("--outdir", required=True, help="Output directory root")
    parser.add_argument("--output", required=True,
                        choices=["rtl", "header", "docs", "all"],
                        help="What to generate")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    outputs_written = []

    if args.output in ("rtl", "all"):
        rtl_dir = os.path.join(args.outdir, "rtl")
        os.makedirs(rtl_dir, exist_ok=True)
        rtl_path = os.path.join(rtl_dir, f"{spec['block']}.sv")
        with open(rtl_path, "w") as f:
            f.write(generate_rtl(spec))
        print(f"[reggen] RTL written  → {rtl_path}")
        outputs_written.append(rtl_path)

    if args.output in ("header", "all"):
        print("[reggen] Header generation not yet implemented (Phase 2)")

    if args.output in ("docs", "all"):
        print("[reggen] Docs generation not yet implemented (Phase 3)")

    manifest_path = write_manifest(spec, args.outdir, outputs_written)
    print(f"[reggen] Manifest    → {manifest_path}")


if __name__ == "__main__":
    main()
