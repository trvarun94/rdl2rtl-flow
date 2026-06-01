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
