# HANDOFF
_Last updated: 2026-05-31 (end of Session 04)_

## Where we are
- Current phase: **Phase 3 complete ✅** — Phase 4 is next
- Status: `make all` runs cleanly (validate → rtl → header → docs → check-stub)

## What works right now
- `make validate` → lints `spec/irq_ctrl.yaml` with 6+1 checks; emits `gen/validation_report.json`
- `make rtl` → generates `gen/rtl/irq_ctrl.sv` with full support for **rw, ro, wo, w1c, rclr**
- `make header` → generates `gen/include/irq_ctrl.h` (base addr, offsets, POS/MSK/WIDTH macros, struct, pointer)
- `make docs` → generates `gen/docs/irq_ctrl.md` (register map: summary table + per-register field tables)
- `make all` → validate first (gates everything), then rtl, header, docs, check-stub
- `make clean` → removes all generated outputs incl. `validation_report.json`, `gen/include/`, `gen/docs/`
- `make help` → shows all targets
- TCL API: `read_spec`, `set_output_dir`, `validate_spec`, `generate_rtl`, `generate_header`, `generate_docs`

## File map (what exists now)
```
spec/irq_ctrl.yaml                          ← single source of truth (5 regs, 12 fields)
tools/reggen/reggen_engine.py               ← Python engine (RTL + C header + Markdown docs)
tools/reggen/reggen_validator.py            ← Phase 1: spec linter, 6+1 checks
tools/reggen/reggen.tcl                     ← TCL API (read_spec, validate_spec, generate_*)
flow/run/gen.tcl                            ← run script (dispatches all output types)
Makefile                                    ← front door
gen/rtl/irq_ctrl.sv                         ← GENERATED: APB register block (5 regs)
gen/include/irq_ctrl.h                      ← GENERATED: C firmware header
gen/docs/irq_ctrl.md                        ← GENERATED: Markdown register map (NEW Phase 3)
gen/irq_ctrl_manifest.json                  ← GENERATED: run manifest
gen/validation_report.json                  ← GENERATED: validator output (PASS/FAIL + errors)
docs/HANDOFF.md                             ← this file
docs/sessions/session-01.md                 ← Phase 0 log
docs/sessions/session-02.md                 ← Phase 1 log
docs/sessions/session-03.md                 ← Phase 2 log
docs/sessions/session-04.md                 ← Phase 3 log (NEW)
docs/notes/registers-and-csrs.md
docs/notes/apb-basics.md
docs/notes/code-generation.md
docs/notes/make-basics.md
docs/notes/tcl-basics.md
docs/notes/systemrdl-intro.md
docs/notes/access-types.md
docs/notes/spec-validation.md
docs/notes/c-header-layout.md
docs/notes/register-map-docs.md             ← NEW: what a register map is, why generated
```

## How to resume (do this first)
```bash
cd rdl2rtl_flow
make all                       # full flow: validate → rtl → header → docs → done
cat gen/docs/irq_ctrl.md       # spot-check: 5 registers, all fields, summary table present
cat gen/include/irq_ctrl.h     # spot-check: 5 registers, all field macros present
cat gen/rtl/irq_ctrl.sv        # spot-check: 5 registers, all 5 access types represented
```

## Next up (Phase 4: consistency gating)

`make check` should diff the committed generated files (`gen/`) against a fresh re-generation
and fail if they differ — catching the case where someone edits a spec but forgets to run
`make all` before committing.

Steps:
1. `make check` re-runs the generator into a temp dir, then diffs against `gen/`.
2. If any file differs, print the diff and exit non-zero.
3. This becomes the CI gate: `make check` in CI catches spec/output drift.
4. Add `docs/notes/consistency-gating.md`.

Options for implementation:
- Shell/Make approach: generate into `gen_check/`, run `diff -rq gen/ gen_check/`, clean up.
- Python approach: add a `--output check` mode to the engine that generates in-memory and
  compares against existing files.
- The Make/shell approach is simplest and most transparent for learning.

## Open questions / decisions for the user
- Phase 4 implementation approach: **Make/shell diff** (simplest, visible) or Python in-memory compare?
  Default plan: Make/shell, since it requires no new Python and makes the comparison transparent.
