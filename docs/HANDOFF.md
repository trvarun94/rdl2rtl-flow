# HANDOFF
_Last updated: 2026-05-31 (end of Session 03)_

## Where we are
- Current phase: **Phase 2 complete ✅** — Phase 3 is next
- Status: `make all` runs cleanly (validate → rtl → header → docs-stub → check-stub)

## What works right now
- `make validate` → lints `spec/irq_ctrl.yaml` with 6+1 checks; emits `gen/validation_report.json`
- `make rtl` → generates `gen/rtl/irq_ctrl.sv` with full support for **rw, ro, wo, w1c, rclr**
- `make header` → generates `gen/include/irq_ctrl.h` (base addr, offsets, POS/MSK/WIDTH macros, struct, pointer)
- `make all` → validate first (gates everything), then rtl, header, docs-stub, check-stub
- `make clean` → removes all generated outputs incl. `validation_report.json` and `gen/include/`
- `make help` → shows all targets
- TCL API: `read_spec`, `set_output_dir`, `validate_spec`, `generate_rtl`, `generate_header`
- `make all` aborts immediately if the spec is invalid — confirmed by injecting a bit overlap

## File map (what exists now)
```
spec/irq_ctrl.yaml                          ← single source of truth (5 regs, 12 fields)
tools/reggen/reggen_engine.py               ← Python engine (RTL + C header generation)
tools/reggen/reggen_validator.py            ← Phase 1: spec linter, 6+1 checks
tools/reggen/reggen.tcl                     ← TCL API (read_spec, validate_spec, generate_*)
flow/run/gen.tcl                            ← run script (dispatches all output types)
Makefile                                    ← front door
gen/rtl/irq_ctrl.sv                         ← GENERATED: APB register block (5 regs)
gen/include/irq_ctrl.h                      ← GENERATED: C firmware header (NEW Phase 2)
gen/irq_ctrl_manifest.json                  ← GENERATED: run manifest
gen/validation_report.json                  ← GENERATED: validator output (PASS/FAIL + errors)
docs/HANDOFF.md                             ← this file
docs/sessions/session-01.md                 ← Phase 0 log
docs/sessions/session-02.md                 ← Phase 1 log
docs/sessions/session-03.md                 ← Phase 2 log (NEW)
docs/notes/registers-and-csrs.md
docs/notes/apb-basics.md
docs/notes/code-generation.md
docs/notes/make-basics.md
docs/notes/tcl-basics.md
docs/notes/systemrdl-intro.md
docs/notes/access-types.md
docs/notes/spec-validation.md
docs/notes/c-header-layout.md              ← NEW: C header anatomy, volatile, why no bitfields
```

## How to resume (do this first)
```bash
cd rdl2rtl_flow
make all                     # full flow: validate → rtl → header → stubs → done
cat gen/include/irq_ctrl.h   # spot-check: 5 registers, all field macros present
cat gen/rtl/irq_ctrl.sv      # spot-check: 5 registers, all 5 access types represented
```

## Next up (Phase 3: register-map documentation)
Generate `gen/docs/irq_ctrl.md` (or `.html`) with a human-readable register map table:

| Register | Offset | Field     | Bits | Access | Reset | Description |
|----------|--------|-----------|------|--------|-------|-------------|
| CTRL     | 0x00   | ENABLE    | 0    | rw     | 0     | Global interrupt enable |
| CTRL     | 0x00   | MODE      | 2:1  | rw     | 0     | Operating mode |
| ...      | ...    | ...       | ...  | ...    | ...   | ...         |

Steps:
1. Implement `generate_docs()` in `reggen_engine.py` (currently a stub with a print).
2. Output: Markdown table per register block. One row per field.
3. `make docs` is already plumbed in Makefile and TCL — just needs the Python work.
4. Add `docs/notes/register-map-docs.md`.

## Open questions / decisions for the user
- Phase 3 output format: **Markdown** (simplest, renders on GitHub) or **HTML** (richer, standalone)?
  Default plan: Markdown, since the repo is on GitHub and it renders free.
