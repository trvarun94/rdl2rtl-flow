# HANDOFF
_Last updated: 2026-05-31 (end of Session 02)_

## Where we are
- Current phase: **Phase 1 complete ✅** — Phase 2 is next
- Status: `make all` runs cleanly (validate → rtl → header-stub → docs-stub → check-stub)

## What works right now
- `make validate` → lints `spec/irq_ctrl.yaml` with 6+1 checks; emits `gen/validation_report.json`
- `make rtl` → generates `gen/rtl/irq_ctrl.sv` with full support for **rw, ro, wo, w1c, rclr**
- `make all` → validate first (gates everything), then rtl, header-stub, docs-stub, check-stub
- `make clean` → removes all generated outputs incl. `validation_report.json`
- `make help` → shows all targets
- TCL API now has `validate_spec` in addition to `read_spec`, `set_output_dir`, `generate_rtl`
- `make all` aborts immediately if the spec is invalid — confirmed by injecting a bit overlap

## File map (what exists now)
```
spec/irq_ctrl.yaml                          ← single source of truth (5 regs, 12 fields)
tools/reggen/reggen_engine.py               ← Python engine (rw/ro/wo/w1c/rclr → APB SV)
tools/reggen/reggen_validator.py            ← NEW Phase 1: spec linter, 6+1 checks
tools/reggen/reggen.tcl                     ← TCL API (now includes validate_spec)
flow/run/gen.tcl                            ← run script (now handles --output validate)
Makefile                                    ← front door (validate target wired)
gen/rtl/irq_ctrl.sv                         ← GENERATED: APB register block (5 regs)
gen/irq_ctrl_manifest.json                  ← GENERATED: run manifest
gen/validation_report.json                  ← NEW: validator output (PASS/FAIL + errors)
docs/HANDOFF.md                             ← this file
docs/sessions/session-01.md                 ← Phase 0 log
docs/sessions/session-02.md                 ← NEW: Phase 1 log
docs/notes/registers-and-csrs.md
docs/notes/apb-basics.md
docs/notes/code-generation.md
docs/notes/make-basics.md
docs/notes/tcl-basics.md
docs/notes/systemrdl-intro.md
docs/notes/access-types.md                  ← NEW: rw/ro/wo/w1c/rclr semantics + RTL diagrams
docs/notes/spec-validation.md               ← NEW: why lint specs, what the validator checks
```

## How to resume (do this first)
```bash
cd rdl2rtl_flow
make validate                # should PASS
make all                     # full flow; runs validate → rtl → stubs → done
cat gen/rtl/irq_ctrl.sv      # spot-check: 5 registers, all 5 access types represented
```

Sanity-check the gate works (optional):
```bash
cp spec/irq_ctrl.yaml /tmp/spec.bak
# inject a bit overlap, then:
make all                     # should FAIL at the `validate` stage
cp /tmp/spec.bak spec/irq_ctrl.yaml
```

## Next up (Phase 2: C firmware header)
Generate `gen/include/<block>.h` with:
1. Base-address macro: `#define IRQ_CTRL_BASE 0x40001000U`
2. Per-register offset macros: `#define IRQ_CTRL_CTRL_OFFSET 0x00U`, etc.
3. Per-field bit-position + mask + width macros:
   ```c
   #define IRQ_CTRL_CTRL_ENABLE_POS   0U
   #define IRQ_CTRL_CTRL_ENABLE_MSK   (1U << 0)
   #define IRQ_CTRL_CTRL_MODE_POS     1U
   #define IRQ_CTRL_CTRL_MODE_MSK     (3U << 1)
   ```
4. A C `struct` view of the register block for typed access:
   ```c
   typedef volatile struct {
       uint32_t CTRL;     /* 0x00 */
       uint32_t STATUS;   /* 0x04 */
       uint32_t IRQ_STS;  /* 0x08 */
       uint32_t TRIG;     /* 0x0C */
       uint32_t FIFO_STS; /* 0x10 */
   } irq_ctrl_t;
   #define IRQ_CTRL ((irq_ctrl_t *) IRQ_CTRL_BASE)
   ```
5. Implement `generate_header()` in `reggen_engine.py` (currently a stub).
6. Wire it up: `make header` is already plumbed; just needs the engine to do real work.
7. Add `docs/notes/c-header-layout.md`.

## Open questions / decisions for the user
- Phase 2 will need a decision on whether to use **packed bitfields** in the C
  struct (compiler-dependent layout, controversial) or **macro masks only**
  (portable, the embedded-firmware norm). Default plan: macros only, with
  a note on why packed bitfields are typically avoided in real firmware.
