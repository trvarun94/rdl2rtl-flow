#!/usr/bin/env python3
"""
reggen_engine.py — Register generation engine (Phase 0: RTL, Phase 2: C header)

LEARNING NOTE: This is a simplified mock of what commercial register generators do.
Real tools that solve the same problem:
  - PeakRDL     (open source, SystemRDL input)
  - Semifore    (commercial, industry standard)
  - Agnisys     (commercial, IDesignSpec)
  - Synopsys Register Compiler (part of Design Compiler)

Those tools take SystemRDL (.rdl) as input. We use YAML here so the parsing is
transparent — you can see exactly what data drives the generation.

Usage:
    python3 reggen_engine.py --spec <spec.yaml> --outdir <output_dir> --output rtl|header|docs|all
"""

import argparse
import json
import os
import shutil
import subprocess
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

STORABLE = ("rw", "wo", "w1c", "rclr")  # access types that need a storage flop


def offset_int_of(reg):
    """Get the register offset as a Python int (specs may use hex string or int)."""
    o = reg["offset"]
    return int(o, 16) if isinstance(o, str) else o


def generate_rtl(spec):
    """
    Generate a SystemVerilog APB register block from the parsed spec dict.
    Returns the RTL as a string.

    HARDWARE CONCEPT — APB transaction:
      APB has a simple 2-phase handshake:
        Phase 1 (SETUP):  manager drives PADDR, PWRITE, PWDATA, asserts PSEL
        Phase 2 (ACCESS): manager asserts PENABLE; subordinate responds
      We always drive PREADY=1 (zero-wait-state response).

    ACCESS TYPES SUPPORTED:
      rw   — SW read/write; storage flop; HW reads value.
      ro   — SW read-only; HW input port drives PRDATA directly (no flop).
      wo   — SW write-only; storage flop; readback is hardwired 0;
             flop value is exposed on an output port so HW can see it.
      w1c  — HW sets via _set strobe; SW writes 1 to bits to clear them.
             Used for interrupt-pending registers (ARM GIC, RISC-V PLIC).
      rclr — HW loads via _en/value ports; SW reads return current value
             AND clear the flop to 0 next cycle.

    PRIORITY WITHIN one clock (last non-blocking write wins):
      (1) APB write  →  (2) APB read-clear (rclr)  →  (3) HW set (w1c)  →  (4) HW load (rclr)
      HW ports come last so a HW event in the same cycle as a SW
      ack/read is NEVER lost (no missed interrupts).
    """
    block     = spec["block"]
    base_addr = spec["base_addr"]
    registers = spec["registers"]

    # Flat list of (reg, field) tuples grouped by access type — used many times below.
    by_access = {a: [] for a in ("rw", "ro", "wo", "w1c", "rclr")}
    for reg in registers:
        for field in reg["fields"]:
            by_access[field["access"]].append((reg, field))

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
        f"//",
        f"// Access types in this block: rw, ro, wo, w1c, rclr",
        f"// ============================================================",
        f"",
        f"`timescale 1ns/1ps",
        f"",
    ]

    # ------------------------------------------------------------------
    # Module declaration + port list
    # ------------------------------------------------------------------
    # LEARNING NOTE: 'logic' is the SystemVerilog type for all signals.
    # Cleaner than old Verilog's wire/reg distinction.
    #
    # We build port DECLARATIONS and COMMENTS separately so we can put
    # commas only between declarations — the last port must NOT have a
    # trailing comma (that's a SV syntax error).

    # Each entry is (declaration, comment).  Comment may be "".
    port_entries = [
        ("    // APB subordinate interface",                  ""),  # heading row, no comma
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

    # HW ports per access type — see ACCESS TYPES doc above.
    if any(by_access[a] for a in ("ro", "wo", "w1c", "rclr")):
        port_entries.append(("    // Hardware-interface ports (per access type)", ""))

    def width_pad(width):
        return f"[{width-1}:0] " if width > 1 else "       "

    # ro: input port (HW drives value into the register block)
    for reg, field in by_access["ro"]:
        msb, lsb = parse_bits(field["bits"])
        w = width_pad(field_width(msb, lsb))
        name = f"hw_{reg['name']}_{field['name']}"
        port_entries.append(
            (f"    input  logic {w}{name}",
             f"ro:  HW drives {reg['name']}.{field['name']} (SW reads it)")
        )
    # wo: output port (expose the SW-written flop value to HW)
    for reg, field in by_access["wo"]:
        msb, lsb = parse_bits(field["bits"])
        w = width_pad(field_width(msb, lsb))
        name = f"hw_{reg['name']}_{field['name']}"
        port_entries.append(
            (f"    output logic {w}{name}",
             f"wo:  HW observes SW-written {reg['name']}.{field['name']} (SW readback is 0)")
        )
    # w1c: HW _set strobe (sets the sticky bit; SW writes 1 to clear)
    for reg, field in by_access["w1c"]:
        set_name = f"hw_{reg['name']}_{field['name']}_set"
        port_entries.append(
            (f"    input  logic        {set_name}",
             f"w1c: HW pulse to SET {reg['name']}.{field['name']} (SW writes 1 to clear)")
        )
    # rclr: HW _en strobe + HW value (load into flop; SW read clears it)
    for reg, field in by_access["rclr"]:
        msb, lsb = parse_bits(field["bits"])
        w = width_pad(field_width(msb, lsb))
        val_name = f"hw_{reg['name']}_{field['name']}"
        en_name  = f"hw_{reg['name']}_{field['name']}_en"
        port_entries.append(
            (f"    input  logic {w}{val_name}",
             f"rclr:HW load value for {reg['name']}.{field['name']}")
        )
        port_entries.append(
            (f"    input  logic        {en_name}",
             f"rclr:HW load enable strobe (clears on SW read)")
        )

    # Render module header + ports. Heading rows have no comma; last real port has no comma.
    lines.append(f"module {block} (")
    last_port_idx = max(
        i for i, (d, _) in enumerate(port_entries)
        if d.lstrip().startswith(("input", "output", "inout"))
    )
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
    # Storage flip-flops (rw, wo, w1c, rclr)
    # ------------------------------------------------------------------
    lines += [
        f"    // --------------------------------------------------------",
        f"    // Storage flip-flops — one per rw/wo/w1c/rclr field",
        f"    //   rw   : holds SW-written value (HW reads it)",
        f"    //   wo   : holds SW-written value (exposed as output port; readback=0)",
        f"    //   w1c  : sticky bit set by HW, cleared by SW write-1",
        f"    //   rclr : holds HW-loaded value; auto-clears on SW read",
        f"    // ro fields have NO flop — they are wires from the HW input port.",
        f"    // --------------------------------------------------------",
    ]
    for reg in registers:
        for field in reg["fields"]:
            if field["access"] in STORABLE:
                msb, lsb = parse_bits(field["bits"])
                width = field_width(msb, lsb)
                sig = f"r_{reg['name']}_{field['name']}"
                w = width_pad(width)
                lines.append(
                    f"    logic {w}{sig};"
                    f"  // {reg['name']}.{field['name']} ({width}-bit {field['access']})"
                )
    lines.append("")

    # ------------------------------------------------------------------
    # wo: assign output port = storage flop value
    # ------------------------------------------------------------------
    if by_access["wo"]:
        lines += [
            f"    // wo fields: expose the SW-written value to HW via output port.",
            f"    // HW can detect a pulse on this signal to trigger an action.",
        ]
        for reg, field in by_access["wo"]:
            sig  = f"r_{reg['name']}_{field['name']}"
            port = f"hw_{reg['name']}_{field['name']}"
            lines.append(f"    assign {port} = {sig};")
        lines.append("")

    # ------------------------------------------------------------------
    # Sequential logic — all flop updates in priority order
    # ------------------------------------------------------------------
    lines += [
        f"    // --------------------------------------------------------",
        f"    // Sequential logic — all flop updates",
        f"    //",
        f"    // PRIORITY within one clock (last NBA assignment wins in always_ff):",
        f"    //   (1) APB write    — rw/wo store PWDATA; w1c write-1-clears",
        f"    //   (2) APB read     — rclr clears the flop                ",
        f"    //   (3) HW _set      — w1c HW-set strobe (overrides SW ack)",
        f"    //   (4) HW _en       — rclr HW load     (overrides read-clear)",
        f"    // HW comes last → HW events never lost when racing with SW.",
        f"    // --------------------------------------------------------",
        f"    always_ff @(posedge PCLK or negedge PRESETn) begin",
        f"        if (!PRESETn) begin",
        f"            // Reset: drive every storable flop to its spec'd reset value",
    ]
    for reg in registers:
        for field in reg["fields"]:
            if field["access"] in STORABLE:
                msb, lsb = parse_bits(field["bits"])
                width = field_width(msb, lsb)
                rval = field.get("reset", 0)
                sig  = f"r_{reg['name']}_{field['name']}"
                lines.append(f"            {sig} <= {width}'d{rval};")
    lines.append(f"        end else begin")

    # ---- (1) APB write phase: rw, wo, w1c ----
    apb_writable = [
        (reg, [f for f in reg["fields"] if f["access"] in ("rw", "wo", "w1c")])
        for reg in registers
    ]
    apb_writable = [(r, fs) for (r, fs) in apb_writable if fs]
    if apb_writable:
        lines += [
            f"            // (1) APB write phase ----------------------------------",
            f"            if (PSEL && PENABLE && PWRITE) begin",
            f"                case (PADDR[7:0])",
        ]
        for reg, fields in apb_writable:
            lines.append(f"                    8'h{offset_int_of(reg):02X}: begin  // {reg['name']}")
            for field in fields:
                msb, lsb = parse_bits(field["bits"])
                sig = f"r_{reg['name']}_{field['name']}"
                slice_expr = f"PWDATA[{msb}:{lsb}]" if msb != lsb else f"PWDATA[{lsb}]"
                if field["access"] in ("rw", "wo"):
                    lines.append(
                        f"                        {sig} <= {slice_expr};"
                        f"  // {field['access']}: store PWDATA bits [{msb}:{lsb}]"
                    )
                else:  # w1c
                    # Write-1-to-clear: only clear bits where SW writes 1.
                    # For a 1-bit field this is a simple `if (PWDATA[lsb]) sig <= 0`.
                    # For multi-bit w1c fields, mask each bit individually.
                    bit_expr = f"PWDATA[{lsb}]" if msb == lsb else f"|{slice_expr}"
                    if msb == lsb:
                        lines.append(
                            f"                        if ({bit_expr}) {sig} <= 1'b0;"
                            f"  // w1c: SW writes 1 → clear"
                        )
                    else:
                        # multi-bit w1c: bitwise clear (sig &= ~PWDATA[msb:lsb])
                        w_bits = field_width(msb, lsb)
                        lines.append(
                            f"                        {sig} <= {sig} & ~{slice_expr};"
                            f"  // w1c: clear bits where SW wrote 1 ({w_bits}-bit)"
                        )
            lines.append(f"                    end")
        lines += [
            f"                    default: ;  // unknown offset — write ignored",
            f"                endcase",
            f"            end",
        ]

    # ---- (2) APB read phase: rclr clear ----
    rclr_by_reg = [
        (reg, [f for f in reg["fields"] if f["access"] == "rclr"])
        for reg in registers
    ]
    rclr_by_reg = [(r, fs) for (r, fs) in rclr_by_reg if fs]
    if rclr_by_reg:
        lines += [
            f"            // (2) APB read phase — rclr clears on read ------------",
            f"            // The clear is registered: it takes effect on the clock",
            f"            // edge AFTER the read, so the read still returns the old",
            f"            // value (via the combinational read mux below).",
            f"            if (PSEL && PENABLE && !PWRITE) begin",
            f"                case (PADDR[7:0])",
        ]
        for reg, fields in rclr_by_reg:
            lines.append(f"                    8'h{offset_int_of(reg):02X}: begin  // {reg['name']}")
            for field in fields:
                msb, lsb = parse_bits(field["bits"])
                width = field_width(msb, lsb)
                sig = f"r_{reg['name']}_{field['name']}"
                lines.append(
                    f"                        {sig} <= {width}'d0;"
                    f"  // rclr: clear on read"
                )
            lines.append(f"                    end")
        lines += [
            f"                    default: ;",
            f"                endcase",
            f"            end",
        ]

    # ---- (3) HW _set strobes (w1c) — override SW ack ----
    if by_access["w1c"]:
        lines.append(f"            // (3) HW _set strobes — w1c HW-set wins over SW ack")
        for reg, field in by_access["w1c"]:
            sig = f"r_{reg['name']}_{field['name']}"
            set_port = f"hw_{reg['name']}_{field['name']}_set"
            lines.append(
                f"            if ({set_port}) {sig} <= 1'b1;"
                f"  // HW sets {reg['name']}.{field['name']}"
            )

    # ---- (4) HW load strobes (rclr) — override read-clear ----
    if by_access["rclr"]:
        lines.append(f"            // (4) HW _en strobes — rclr HW load wins over read-clear")
        for reg, field in by_access["rclr"]:
            sig = f"r_{reg['name']}_{field['name']}"
            en_port  = f"hw_{reg['name']}_{field['name']}_en"
            val_port = f"hw_{reg['name']}_{field['name']}"
            lines.append(
                f"            if ({en_port}) {sig} <= {val_port};"
                f"  // HW loads {reg['name']}.{field['name']}"
            )

    lines += [
        f"        end",
        f"    end",
        f"",
    ]

    # ------------------------------------------------------------------
    # Read mux (combinational)
    # ------------------------------------------------------------------
    lines += [
        f"    // --------------------------------------------------------",
        f"    // Read mux — drive PRDATA based on PADDR (combinational).",
        f"    // Per-access readback rules:",
        f"    //   rw   → flop value",
        f"    //   ro   → live HW input port",
        f"    //   wo   → omitted from OR-tree (readback is 0)",
        f"    //   w1c  → flop value (sticky bit)",
        f"    //   rclr → flop value (clear happens next cycle in always_ff)",
        f"    // --------------------------------------------------------",
        f"    always_comb begin",
        f"        PRDATA = 32'h0;  // default: unimplemented addresses read as 0",
        f"        if (PSEL && !PWRITE) begin",
        f"            case (PADDR[7:0])",
    ]
    for reg in registers:
        lines.append(f"                8'h{offset_int_of(reg):02X}: begin  // {reg['name']}")
        terms = []
        for field in reg["fields"]:
            access = field["access"]
            if access == "wo":
                continue  # write-only: readback is 0, contribute nothing to PRDATA
            msb, lsb = parse_bits(field["bits"])
            if access == "ro":
                sig = f"hw_{reg['name']}_{field['name']}"     # live HW input
            else:
                sig = f"r_{reg['name']}_{field['name']}"      # storage flop
            terms.append(f"(32'({sig}) << {lsb})" if lsb > 0 else f"32'({sig})")
        if terms:
            lines.append(f"                    PRDATA = {' | '.join(terms)};")
        else:
            lines.append(f"                    PRDATA = 32'h0;  // all fields are wo")
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
# Register-map documentation generation (Markdown)
# ---------------------------------------------------------------------------

def generate_docs(spec):
    """
    Generate a Markdown register-map document from the parsed spec dict.
    Returns the document as a string.

    DOCUMENTATION CONCEPT — Why generate the register map?
    In real chip development, the register map is the contract between hardware
    and software. It lives in the Programmer's Reference Manual (PRM) and is the
    document firmware engineers, verification engineers, and customers all read.

    Generating it from the same YAML spec that drives RTL and firmware headers
    guarantees the three artifacts never diverge — a bit position change in the
    spec propagates everywhere at once. Writing it by hand and keeping it in sync
    is a known source of bugs in real projects.

    Real tools (Arm regtool, IP-XACT exporters, Synopsys Register Compiler) emit
    HTML, PDF, and even UVM register models from the same source. We emit Markdown
    because it renders for free on GitHub and stays readable as plain text.

    Output structure:
      - File header: block name, base address, register/field counts
      - Register summary table: one row per register (offset + description)
      - Per-register section (##): one field table listing bits, access, reset, desc
    """
    block     = spec["block"]
    base_addr = spec["base_addr"]
    registers = spec["registers"]

    base_str  = hex(base_addr) if isinstance(base_addr, int) else base_addr
    field_count = sum(len(r["fields"]) for r in registers)
    sorted_regs = sorted(registers, key=offset_int_of)

    lines = []

    # ------------------------------------------------------------------
    # File header
    # ------------------------------------------------------------------
    lines += [
        f"# {block} Register Map",
        f"",
        f"_Generated from `spec/{block}.yaml` — do not edit by hand._",
        f"",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| Base address | `{base_str}` |",
        f"| Register width | 32 bits |",
        f"| Registers | {len(registers)} |",
        f"| Fields | {field_count} |",
        f"",
        f"---",
        f"",
    ]

    # ------------------------------------------------------------------
    # Register summary table
    # ------------------------------------------------------------------
    lines += [
        f"## Register Summary",
        f"",
        f"| Register | Offset | Description |",
        f"|----------|--------|-------------|",
    ]
    for reg in sorted_regs:
        off  = offset_int_of(reg)
        desc = reg.get("desc", "")
        lines.append(f"| `{reg['name']}` | `0x{off:02X}` | {desc} |")

    lines += ["", "---", ""]

    # ------------------------------------------------------------------
    # Per-register sections
    # ------------------------------------------------------------------
    for reg in sorted_regs:
        off  = offset_int_of(reg)
        desc = reg.get("desc", "")

        lines += [
            f"## {reg['name']} — Offset `0x{off:02X}`",
            f"",
        ]
        if desc:
            lines += [desc, ""]

        lines += [
            f"| Field | Bits | Access | Reset | Description |",
            f"|-------|------|--------|-------|-------------|",
        ]
        for field in reg["fields"]:
            msb, lsb = parse_bits(field["bits"])
            bits_str = f"{msb}:{lsb}" if msb != lsb else str(lsb)
            reset    = field.get("reset", 0)
            w        = field_width(msb, lsb)
            reset_str = f"`0x{reset:0{(w + 3) // 4}X}`"
            fdesc    = field.get("desc", "")
            lines.append(
                f"| `{field['name']}` | {bits_str} | `{field['access']}` | {reset_str} | {fdesc} |"
            )

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# C firmware header generation
# ---------------------------------------------------------------------------

def generate_header(spec):
    """
    Generate a C firmware header from the parsed spec dict.
    Returns the header source as a string.

    FIRMWARE CONCEPT — Why a C header?
    The RTL (Phase 0) is the hardware implementation. The C header is the
    firmware contract: it lets a C programmer write to a register without
    knowing or hard-coding any hex addresses or bit positions.

    Instead of:
        *((volatile uint32_t *)0x40001000) = 0x00000005;  // magic numbers, fragile

    Firmware engineers write:
        IRQ_CTRL->CTRL = (1U << IRQ_CTRL_CTRL_ENABLE_POS)
                       | (2U << IRQ_CTRL_CTRL_MODE_POS);

    The header has four parts (each explained below):
      1. Include guard + #include <stdint.h>
      2. Base address macro
      3. Register offset macros
      4. Per-field POS / MSK / WIDTH macros
      5. volatile struct typedef + pointer macro

    WHY NOT C PACKED BITFIELDS?
    You might expect:
        struct { uint32_t ENABLE:1; uint32_t MODE:2; } CTRL;
    The C standard leaves bitfield layout (bit order, padding) implementation-
    defined. ARM-GCC, MSVC, and IAR pack them differently. Production embedded
    code uses macro masks — portable across every compiler, CPU, and endianness.
    See docs/notes/c-header-layout.md for the full story.
    """
    block     = spec["block"]
    prefix    = block.upper()          # "irq_ctrl" → "IRQ_CTRL"
    base_addr = spec["base_addr"]
    registers = spec["registers"]

    # Sort registers by byte offset so the struct members are in address order.
    sorted_regs = sorted(registers, key=offset_int_of)

    base_str = hex(base_addr) if isinstance(base_addr, int) else base_addr
    guard    = f"{prefix}_H"
    lines    = []

    # ------------------------------------------------------------------
    # Include guard + file header
    # ------------------------------------------------------------------
    lines += [
        f"#ifndef {guard}",
        f"#define {guard}",
        f"",
        f"/*",
        f" * GENERATED FILE — do not edit by hand.",
        f" * Source: spec/{block}.yaml",
        f" * Generator: tools/reggen/reggen_engine.py",
        f" *",
        f" * Block  : {block}",
        f" * Base   : {base_str}",
        f" * Regs   : {len(registers)}",
        f" */",
        f"",
        f"#include <stdint.h>",  # uint32_t lives here
        f"",
    ]

    # ------------------------------------------------------------------
    # Part 1 — Base address
    # ------------------------------------------------------------------
    # FIRMWARE NOTE: The 'U' suffix makes this an unsigned integer literal.
    # Without it, large addresses (> 0x7FFFFFFF) would be negative signed ints
    # on 32-bit platforms. Always use 'U' for hardware addresses and masks.
    lines += [
        f"/* Base address */",
        f"#define {prefix}_BASE  {base_str}U",
        f"",
    ]

    # ------------------------------------------------------------------
    # Part 2 — Register offset macros
    # ------------------------------------------------------------------
    # FIRMWARE NOTE: Firmware accesses a register as (BASE + OFFSET).
    # Having a named macro for each offset means a spec change (e.g. moving
    # a register) only requires regenerating this file — no manual grep-and-fix.
    lines.append("/* Register offsets */")
    off_macros = [
        (f"#define {prefix}_{reg['name']}_OFFSET", f"0x{offset_int_of(reg):02X}U")
        for reg in sorted_regs
    ]
    col = max(len(m) for m, _ in off_macros) + 2
    for macro, val in off_macros:
        lines.append(f"{macro:<{col}}  {val}")
    lines.append("")

    # ------------------------------------------------------------------
    # Part 3 — Per-field POS / MSK / WIDTH macros
    # ------------------------------------------------------------------
    # FIRMWARE NOTE — three macros per field:
    #   _POS   : bit position of the LSB of the field (for shifting)
    #   _MSK   : bitmask isolating the field (for reading: reg & MSK)
    #   _WIDTH : number of bits (useful for range checks and documentation)
    #
    # Example usage in firmware:
    #   Write MODE=2:  IRQ_CTRL->CTRL |= (2U << IRQ_CTRL_CTRL_MODE_POS);
    #   Read  MODE:    mode = (IRQ_CTRL->CTRL & IRQ_CTRL_CTRL_MODE_MSK)
    #                         >> IRQ_CTRL_CTRL_MODE_POS;
    for reg in sorted_regs:
        desc = reg.get("desc", "")
        lines.append(f"/* {reg['name']}" + (f" — {desc}" if desc else "") + " */")

        entries = []
        for field in reg["fields"]:
            msb, lsb = parse_bits(field["bits"])
            w        = field_width(msb, lsb)
            mask_val = (1 << w) - 1
            pos_m  = f"#define {prefix}_{reg['name']}_{field['name']}_POS"
            msk_m  = f"#define {prefix}_{reg['name']}_{field['name']}_MSK"
            wid_m  = f"#define {prefix}_{reg['name']}_{field['name']}_WIDTH"
            entries.append((pos_m, f"{lsb}U",
                            msk_m, f"(0x{mask_val:X}U << {lsb}U)",
                            wid_m, f"{w}U"))

        # Align all three macro names in this register to the same column.
        col = max(max(len(e[0]), len(e[2]), len(e[4])) for e in entries) + 2
        for pos_m, pos_v, msk_m, msk_v, wid_m, wid_v in entries:
            lines.append(f"{pos_m:<{col}}  {pos_v}")
            lines.append(f"{msk_m:<{col}}  {msk_v}")
            lines.append(f"{wid_m:<{col}}  {wid_v}")
        lines.append("")

    # ------------------------------------------------------------------
    # Part 4 — volatile struct typedef + pointer macro
    # ------------------------------------------------------------------
    # FIRMWARE NOTE — 'volatile struct':
    #   'volatile' tells the compiler that memory at these addresses can change
    #   outside its view (hardware writes registers between two SW reads).
    #   Without it, the compiler might cache a register read in a CPU register
    #   and skip re-reading memory — a classic firmware bug.
    #
    #   The struct gives typed field access:
    #     IRQ_CTRL->CTRL = 1U;       ← write to offset 0x00
    #     uint32_t s = IRQ_CTRL->STATUS;  ← read from offset 0x04
    #
    #   Padding (reserved[N]) is inserted for any gap between registers
    #   so the struct layout exactly mirrors the hardware memory map.
    lines += [
        "/*",
        " * Typed struct — use IRQ_CTRL->REGNAME for register access.",
        " * Members are plain uint32_t (not packed bitfields) for portability.",
        " */",
        f"typedef volatile struct {{",
    ]

    expected_off = 0
    pad_idx      = 0
    for reg in sorted_regs:
        off = offset_int_of(reg)
        if off > expected_off:
            gap_words = (off - expected_off) // 4
            lines.append(
                f"    uint32_t _reserved{pad_idx}[{gap_words}]; /* 0x{expected_off:02X}–0x{off - 4:02X}: gap */"
            )
            pad_idx += 1
        desc    = reg.get("desc", "")
        comment = f"/* 0x{off:02X}" + (f" — {desc}" if desc else "") + " */"
        lines.append(f"    uint32_t {reg['name']}; {comment}")
        expected_off = off + 4

    lines += [
        f"}} {block}_t;",
        f"",
        f"/* Pointer macro — IRQ_CTRL->CTRL dereferences the base address as the struct */",
        f"#define {prefix}  (({block}_t *){prefix}_BASE)",
        f"",
        f"#endif /* {guard} */",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Functional simulation (iverilog compile + vvp run)
# ---------------------------------------------------------------------------

def run_sim(spec, outdir, project_root):
    """
    Compile the testbench with iverilog and run it with vvp.
    Writes gen/sim_report.json with PASS or FAIL in both outcomes.
    Exits non-zero on failure so Make aborts.

    FLOW CONCEPT — why sim after lint, not instead of it?
    Lint (static analysis) catches structural RTL bugs without any stimulus.
    Simulation (dynamic analysis) drives the RTL with actual APB transactions
    and verifies it BEHAVES correctly. In a real flow you run both: lint gates
    synthesis, simulation gates tape-out sign-off.

    The two-step iverilog→vvp flow mirrors commercial tools:
      iverilog compile  =  vlogan/xmvlog  (VCS/Xcelium compile step)
      vvp run           =  vcs -R / xmsim (the actual simulation run)
    $fatal in the testbench exits vvp non-zero; TCL's exec catches that and
    propagates it as an error — Make aborts automatically.
    """
    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            print(f"[reggen] ERROR: '{tool}' not found on PATH.", file=sys.stderr)
            print(f"[reggen] Install: brew install icarus-verilog  (macOS)", file=sys.stderr)
            print(f"[reggen]          apt install iverilog          (Debian/Ubuntu)", file=sys.stderr)
            sys.exit(1)

    block   = spec["block"]
    sv_path = os.path.join(outdir, "rtl", f"{block}.sv")
    tb_path = os.path.join(project_root, "tb", f"{block}_tb.sv")
    sim_dir = os.path.join(outdir, "sim")
    sim_bin = os.path.join(sim_dir, f"{block}_sim")

    for path, label in [(sv_path, "RTL"), (tb_path, "Testbench")]:
        if not os.path.exists(path):
            print(f"[reggen] ERROR: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    os.makedirs(sim_dir, exist_ok=True)

    # Compile: iverilog turns .sv sources into a VVP bytecode executable.
    compile_result = subprocess.run(
        ["iverilog", "-g2012", "-o", sim_bin, tb_path, sv_path],
        capture_output=True, text=True,
    )
    if compile_result.returncode != 0:
        print("[reggen] Sim compile FAILED", file=sys.stderr)
        if compile_result.stderr:
            print(compile_result.stderr, file=sys.stderr)
        _write_sim_report(outdir, block, "FAIL", compile_result, None)
        sys.exit(1)

    # Run: vvp executes the bytecode; $fatal inside the TB exits non-zero.
    run_result = subprocess.run(["vvp", sim_bin], capture_output=True, text=True)

    passed = run_result.returncode == 0
    report_path = _write_sim_report(
        outdir, block, "PASS" if passed else "FAIL", compile_result, run_result
    )

    if passed:
        print(run_result.stdout.strip())
        print(f"[reggen] Sim PASSED  → {report_path}")
    else:
        print(f"[reggen] Sim FAILED  → {report_path}", file=sys.stderr)
        if run_result.stdout:
            print(run_result.stdout, file=sys.stderr)
        sys.exit(1)


def _write_sim_report(outdir, block, status, compile_result, run_result):
    """Write gen/sim_report.json and return its path."""
    stdout = run_result.stdout.strip() if run_result else ""
    # Count assertion checks: testbench prints "  PASS: ..." per passing check.
    checks_passed = sum(1 for line in stdout.splitlines() if "PASS:" in line)

    report = {
        "tool": "iverilog/vvp",
        "status": status,
        "checks_passed": checks_passed,
        "compile_exit_code": compile_result.returncode,
        "run_exit_code": run_result.returncode if run_result else None,
        "stdout": stdout,
        "stderr": (compile_result.stderr.strip()
                   + ("\n" + run_result.stderr.strip()
                      if run_result and run_result.stderr else "")),
    }
    report_path = os.path.join(outdir, "sim_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    return report_path


# ---------------------------------------------------------------------------
# RTL lint (Verilator --lint-only)
# ---------------------------------------------------------------------------

def run_lint(spec, outdir):
    """
    Run Verilator in lint-only mode on the generated RTL file.
    Writes gen/lint_report.json. Exits non-zero (hard fail) if:
      - verilator is not on PATH
      - verilator reports any warnings or errors

    FLOW CONCEPT — why lint after generation, not during?
    The generator (us) is responsible for emitting correct RTL.
    Lint is the independent checker that catches anything we got wrong:
    width mismatches, undriven nets, implicit wire declarations, etc.
    It is the first gate before synthesis sees the file.

    Verilator --lint-only does static analysis only — no simulation,
    no C++ compilation. Runs in under a second.
    """
    if shutil.which("verilator") is None:
        print("[reggen] ERROR: 'verilator' not found on PATH.", file=sys.stderr)
        print("[reggen] Install it with:  brew install verilator  (macOS)", file=sys.stderr)
        print("[reggen]                   apt install verilator    (Debian/Ubuntu)", file=sys.stderr)
        sys.exit(1)

    sv_path = os.path.join(outdir, "rtl", f"{spec['block']}.sv")
    if not os.path.exists(sv_path):
        print(f"[reggen] ERROR: RTL file not found: {sv_path}", file=sys.stderr)
        print("[reggen] Run 'make rtl' before 'make lint'.", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        # --Wall enables all warnings; -Wno-UNUSEDSIGNAL suppresses the
        # "upper bits of PADDR/PWDATA unused" warning — those signals are
        # mandated 32-bit by the APB protocol even when the register map
        # uses fewer bits. This is a standard lint waiver for APB blocks.
        ["verilator", "--lint-only", "--Wall", "-Wno-UNUSEDSIGNAL", "-sv", sv_path],
        capture_output=True,
        text=True,
    )

    passed = result.returncode == 0
    report = {
        "tool": "verilator",
        "version_flag": "--lint-only",
        "rtl_file": sv_path,
        "exit_code": result.returncode,
        "status": "PASS" if passed else "FAIL",
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }

    report_path = os.path.join(outdir, "lint_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    if passed:
        print(f"[reggen] Lint PASSED  → {report_path}")
    else:
        print(f"[reggen] Lint FAILED  → {report_path}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Generation manifest (JSON) — scanned from disk, not accumulated by generators
# ---------------------------------------------------------------------------

def scan_manifest(spec, outdir):
    """
    Build the run manifest by scanning <outdir> for generated artifacts.
    This is an end-of-run audit snapshot — the LAST step in `make all`,
    after every generator and lint have produced their files.

    FLOW CONCEPT — why scan disk instead of accumulating?
    In real EDA flows (Synopsys DC, Cadence Innovus) summary reports are
    produced by dedicated commands (`report_design`, `report_qor`) that run
    AFTER generation/synthesis and inspect the design database. Generators
    don't summarize themselves — that responsibility lives in one place,
    making the report authoritative and easy to reason about.

    Only files that actually exist on disk are recorded. The lint block is
    included only if gen/lint_report.json is present (graceful degradation).
    Output paths are stored relative to outdir so the committed manifest
    is portable across machines.
    """
    block = spec["block"]
    base  = spec["base_addr"]

    # Probe known artifact locations
    candidates = {
        "rtl":    os.path.join("rtl",     f"{block}.sv"),
        "header": os.path.join("include", f"{block}.h"),
        "docs":   os.path.join("docs",    f"{block}.md"),
    }
    outputs = {
        kind: rel_path
        for kind, rel_path in candidates.items()
        if os.path.exists(os.path.join(outdir, rel_path))
    }

    manifest = {
        "tool": "reggen",
        "block": block,
        "spec_base_addr": hex(base) if isinstance(base, int) else base,
        "register_count": len(spec["registers"]),
        "field_count": sum(len(r["fields"]) for r in spec["registers"]),
        "outputs": outputs,
    }

    # Include lint status if a lint report exists
    lint_path = os.path.join(outdir, "lint_report.json")
    if os.path.exists(lint_path):
        with open(lint_path) as f:
            lint_report = json.load(f)
        manifest["lint"] = {
            "status": lint_report.get("status"),
            "tool":   lint_report.get("tool"),
        }

    # Include sim status if a sim report exists
    sim_path = os.path.join(outdir, "sim_report.json")
    if os.path.exists(sim_path):
        with open(sim_path) as f:
            sim_report = json.load(f)
        manifest["sim"] = {
            "status":        sim_report.get("status"),
            "tool":          sim_report.get("tool"),
            "checks_passed": sim_report.get("checks_passed"),
        }

    manifest_path = os.path.join(outdir, f"{block}_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[reggen] Manifest written → {manifest_path}")
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
                        choices=["rtl", "header", "docs", "lint", "sim", "manifest", "all"],
                        help="What to generate")
    args = parser.parse_args()

    spec = load_spec(args.spec)

    if args.output in ("rtl", "all"):
        rtl_dir = os.path.join(args.outdir, "rtl")
        os.makedirs(rtl_dir, exist_ok=True)
        rtl_path = os.path.join(rtl_dir, f"{spec['block']}.sv")
        with open(rtl_path, "w") as f:
            f.write(generate_rtl(spec))
        print(f"[reggen] RTL written  → {rtl_path}")

    if args.output in ("header", "all"):
        inc_dir = os.path.join(args.outdir, "include")
        os.makedirs(inc_dir, exist_ok=True)
        header_path = os.path.join(inc_dir, f"{spec['block']}.h")
        with open(header_path, "w") as f:
            f.write(generate_header(spec))
        print(f"[reggen] Header written → {header_path}")

    if args.output in ("docs", "all"):
        docs_dir = os.path.join(args.outdir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        docs_path = os.path.join(docs_dir, f"{spec['block']}.md")
        with open(docs_path, "w") as f:
            f.write(generate_docs(spec))
        print(f"[reggen] Docs written  → {docs_path}")

    if args.output == "lint":
        run_lint(spec, args.outdir)

    if args.output == "sim":
        # Derive the project root from the spec path (spec is at <root>/spec/<block>.yaml).
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(args.spec)))
        run_sim(spec, args.outdir, project_root)

    if args.output == "manifest":
        scan_manifest(spec, args.outdir)


if __name__ == "__main__":
    main()
