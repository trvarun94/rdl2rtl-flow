# Register Map Documentation

## What is a register map?

A **register map** (also called a **register specification** or the register chapter of a
**Programmer's Reference Manual / PRM**) is a table that describes every software-accessible
register in a hardware block:

- its address offset from the block's base
- each field inside it: which bits, what the field means, how software reads/writes it
- the reset value (what the hardware drives on power-up before SW touches it)

If you've read the UART or GPIO chapter of a microcontroller datasheet, that's a register map.

## Why generate it, not write it?

In early chip development, register maps were written by hand in Word or Excel and kept
"in sync" with the RTL manually — a famously error-prone process. A field would move from
bit 3 to bit 4 in the RTL, the header wouldn't be updated, and a firmware engineer would
spend a day debugging a silent misconfiguration.

Modern IP development flows use a **single source of truth** — one machine-readable spec
(SystemRDL, IP-XACT, or a YAML like ours) — from which all three artifacts are generated:

| Artifact | Consumer | Phase |
|----------|----------|-------|
| SystemVerilog RTL | Synthesis, DV | Phase 0 |
| C firmware header | Firmware engineers | Phase 2 |
| Markdown / HTML register map | Everyone (PRM) | Phase 3 |

Because all three come from the same spec, a bit-position change propagates everywhere at
once with a single `make all`. There's no way for the doc to disagree with the RTL.

## Real-world register map generators

| Tool | Format | Output |
|------|--------|--------|
| Arm `regtool` (Ibex/OpenTitan) | HJSON | HTML, C header, UVM |
| PeakRDL | SystemRDL | HTML, C header, UVM, IP-XACT |
| Synopsys Register Compiler | SystemRDL | RTL, UVM, C header, docs |
| Semifore CDReg | SystemRDL | RTL, UVM, C header, HTML |
| IP-XACT editors | XML | Tool-dependent |

Our Markdown output is the simplest possible version of what these tools produce. It renders
for free on GitHub, stays readable as plain text, and demonstrates the core principle: the
doc is a derived artifact, not a manually maintained one.

## What our generator produces

```
gen/docs/irq_ctrl.md
```

Structure of the file:

1. **File header** — block name, base address, counts (rendered as a small metadata table)
2. **Register summary** — one row per register, offset and one-line description
3. **Per-register section** — a `##` heading per register, then a field table:

```markdown
## CTRL — Offset `0x00`
Control register — enables and configures the interrupt controller

| Field    | Bits | Access | Reset | Description            |
|----------|------|--------|-------|------------------------|
| `ENABLE` | 0    | `rw`   | `0x0` | Global interrupt enable |
| `MODE`   | 2:1  | `rw`   | `0x0` | Operating mode          |
```

## Access type legend (in the generated table)

| Access | Meaning |
|--------|---------|
| `rw`   | SW read/write |
| `ro`   | SW read-only (HW drives the value) |
| `wo`   | SW write-only (readback is always 0) |
| `w1c`  | Write-1-to-Clear: HW sets the bit, SW writes 1 to acknowledge/clear |
| `rclr` | Read-to-Clear: reading the field also clears it to 0 |

## Where this fits in the flow

```
spec/irq_ctrl.yaml
        │
        ▼
reggen_engine.py  (generate_docs)
        │
        ▼
gen/docs/irq_ctrl.md   ← human-readable Markdown, renders on GitHub
```

`make docs` is the entry point. `make all` runs it after RTL and header generation.
