# HANDOFF
_Last updated: 2026-05-31 (end of Session 01)_

## Where we are
- Current phase: Phase 0 complete ✅ — Phase 1 is next
- Status: `make rtl` works end-to-end; generates a valid APB SystemVerilog block

## What works right now
- `make rtl` → reads `spec/irq_ctrl.yaml` → generates `gen/rtl/irq_ctrl.sv`
- `make clean` → removes all generated outputs
- `make help` → shows all available targets
- JSON manifest written to `gen/irq_ctrl_manifest.json` each run
- TCL API (`read_spec`, `set_output_dir`, `generate_rtl`) wraps the Python engine
- `make header` and `make docs` are stubbed (print "not yet implemented")
- `make validate` and `make check` are stubbed (Phase 1 and Phase 4)

## File map (what exists now)
```
spec/irq_ctrl.yaml              ← the single source of truth
tools/reggen/reggen_engine.py   ← Python: YAML → APB SystemVerilog
tools/reggen/reggen.tcl         ← TCL tool API
flow/run/gen.tcl                ← designer run script
Makefile                        ← front door
gen/rtl/irq_ctrl.sv             ← GENERATED: the APB register block
gen/irq_ctrl_manifest.json      ← GENERATED: run manifest
docs/HANDOFF.md                 ← this file
docs/sessions/session-01.md     ← session log
docs/notes/registers-and-csrs.md
docs/notes/apb-basics.md
docs/notes/code-generation.md
docs/notes/make-basics.md
docs/notes/tcl-basics.md
docs/notes/systemrdl-intro.md
```

## How to resume (do this first)
```bash
cd rdl2rtl_flow
make rtl           # should succeed and print the RTL written path
cat gen/rtl/irq_ctrl.sv   # spot-check: 2 registers, CTRL (rw fields), STATUS (ro fields)
```

## Next up (Phase 1)
1. **Extend the engine** — add RTL generation for `wo`, `w1c`, `rclr` access types
   - `wo`: write-only field; reading back always returns 0 (no readback flop exposed)
   - `w1c`: hardware sets the bit; software writes 1 to clear it
   - `rclr`: reading the field clears it (read-to-clear)
2. **Add `wo`/`w1c`/`rclr` fields to the spec** — extend `spec/irq_ctrl.yaml`
3. **Build the spec validator** — `tools/reggen/reggen_validator.py`:
   - Fields within register width
   - No overlapping fields
   - Unique field names per register
   - Reset value fits field width
   - Unique/aligned register offsets
   - Emits normalized JSON report
4. **Wire up `make validate`** in Makefile and TCL API

## Open questions / decisions for the user
- None — Phase 1 plan is clear
