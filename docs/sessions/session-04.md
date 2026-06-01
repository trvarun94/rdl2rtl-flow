# Session 04 — Phase 3: Register-Map Documentation

_Date: 2026-05-31_

## What we built

`make docs` now generates `gen/docs/irq_ctrl.md` — a complete, human-readable register map
derived from the same `spec/irq_ctrl.yaml` that drives the RTL and C header.

### Files changed
| File | Change |
|------|--------|
| `tools/reggen/reggen_engine.py` | Added `generate_docs(spec)` function; updated `main()` to write the file |
| `docs/notes/register-map-docs.md` | New concept note |
| `docs/HANDOFF.md` | Updated for Phase 3 complete |
| `docs/sessions/session-04.md` | This file |

### New generated output
`gen/docs/irq_ctrl.md` — structure:
- Metadata table (base address, register count, field count)
- Register summary table (one row per register)
- Per-register `##` section with a field table: Field | Bits | Access | Reset | Description

## What we learned

### The register map as a contract

The register map is the **contract between hardware and software**. Before it existed,
the RTL (Phase 0) and the C header (Phase 2) were consistent with the spec, but there
was nothing a human could read end-to-end to verify the block's behavior. The Markdown
doc completes the picture: anyone can open `gen/docs/irq_ctrl.md` and understand every
register and field without reading RTL or YAML.

Real chips ship PRMs (Programmer's Reference Manuals) that are hundreds of pages of
exactly this: register name, offset, field table, behavioral description. Our single-file
output is a miniature version of that.

### Nothing in the TCL layer changed

The TCL `generate_docs` proc was already wired in Phase 0 as a stub. Phase 3 only added
the Python implementation and the file-writing logic in `main()`. This mirrors how real
tools are built: the API surface (TCL commands) is defined early and kept stable; the
implementation underneath can evolve without changing how designers invoke the tool.

### `generate_docs()` structure decisions

- **Sorted by offset** (`sorted_regs = sorted(registers, key=offset_int_of)`) — same
  order as the hardware memory map, which is how every real PRM presents registers.
- **Summary table first** — lets a reader find a register by name/offset without
  scrolling through all the field detail.
- **Reset values as hex** (`0x0`, `0xF`, etc.) — matches how firmware engineers think
  about register state; decimal would be confusing for multi-bit fields.
- **Access types in backticks** — renders as code in Markdown, visually distinguishing
  `rw` from descriptive text.

## Interview reflection

**Q: Why generate docs from the spec rather than writing them by hand?**

Because generated docs can't drift. The single biggest failure mode in register
documentation is bit-position mismatches between the RTL and the PRM — a field moves
in the spec, the engineer regenerates the RTL, forgets to update the Word document, and
the firmware engineer later spends half a day debugging a field that isn't where they
expect it. When docs are generated from the same source of truth as the RTL, this class
of bug is structurally eliminated.

**Q: What would a production register-map generator add on top of this?**

HTML output (for standalone viewing without a Markdown renderer), per-field behavioral
notes, access-type diagrams (timing waveforms for w1c and rclr), cross-links between
registers that share the same HW event, and UVM register model generation. The core
table structure we generate here is identical to what real tools produce; the
enhancements are presentation and model depth, not different data.

## What's next (Phase 4)

`make check` — consistency gating: re-generate all outputs into a temp dir, diff against
the committed `gen/` tree, and fail if any file differs. This is the CI gate that
enforces "always commit generated files in sync with the spec."
