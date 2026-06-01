# Session 02 — Phase 1: Access Types + Spec Validator
_Date: 2026-05-31_

## Goal for this session
Build Phase 1 on top of the Phase 0 skeleton:
- Add three new register access types to the engine: `wo`, `w1c`, `rclr`
- Extend the YAML spec with concrete examples of each (IRQ_STS, TRIG, FIFO_STS)
- Build a standalone spec validator (`reggen_validator.py`) with 6 lint checks
- Wire `make validate` through the Make → TCL → Python layering
- Gate `make all` on validation passing

## What we did
1. Verified Phase 0 still runs (`make rtl` clean).
2. **Step 1 — extended `spec/irq_ctrl.yaml`** with three new registers exercising the new access types:
   - `IRQ_STS` @ 0x08 — three `w1c` interrupt-pending bits
   - `TRIG` @ 0x0C — two `wo` software-trigger bits
   - `FIFO_STS` @ 0x10 — one 4-bit `rclr` event count
   - Block now has 5 registers, 12 fields.
3. **Step 2 — restructured `generate_rtl()` in `reggen_engine.py`**:
   - Added per-access HW port generation:
     - `wo` → output port (HW observes the SW-written value)
     - `w1c` → input `_set` strobe (HW sets the sticky bit)
     - `rclr` → input value + `_en` strobe (HW load)
   - Added storage flops for `wo`/`w1c`/`rclr` (in addition to existing `rw`).
   - Restructured the `always_ff` into 4 priority-ordered phases:
     1. APB write (`rw` store, `wo` store, `w1c` write-1-clear)
     2. APB read (`rclr` clear-on-read)
     3. HW `_set` strobes (`w1c`)
     4. HW `_en` strobes (`rclr`)
   - The last NBA wins in `always_ff`, so HW phases come last → HW events never lost.
   - Updated the read mux: `wo` contributes 0 (omitted from OR-tree); `w1c`/`rclr` read like `rw`.
4. **Step 3 — wrote `tools/reggen/reggen_validator.py`** with 6 (+1) checks:
   - bit range fits within `reg_width`
   - no overlapping fields within a register
   - unique field names within a register
   - reset value fits in field width
   - unique register offsets across the block
   - register offsets aligned to bus byte-width
   - (bonus) access type ∈ {rw, ro, wo, w1c, rclr}
   - Emits `gen/validation_report.json` with PASS/FAIL summary.
   - Exits 1 on any error so Make can gate.
5. **Step 4 — wired `make validate`**:
   - New `validate_spec` proc in `tools/reggen/reggen.tcl` (shells out to validator, raises TCL error on non-zero exit).
   - `flow/run/gen.tcl` learned `--output validate` and now runs `validate_spec` first in the `all` path.
   - `Makefile` replaced the stub; updated `all:` order to `validate rtl header docs check` so a broken spec stops the build before generation.
   - `make clean` also removes `validation_report.json`.
6. **Verified end-to-end**:
   - `make validate` on clean spec → PASS, exit 0
   - Hand-crafted broken spec exercised all 7 error categories → FAIL, exit 1
   - Temporarily broke `TRIG.SOFT_NMI` to overlap `SOFT_IRQ` → `make all` aborted at validate, never reached `rtl` target ✅
   - Restored spec; `make all` runs all stages clean.

## Commands run
```bash
make clean
make validate        # new
make rtl
make all             # full flow, validate-gated
```

## Decisions made (and why)
- **HW priority over SW in `always_ff`**: chose to order HW strobes LAST so a HW IRQ arriving the same cycle SW writes-1-to-clear isn't lost. Documented inline.
- **`rclr` uses two ports (`_en` + value)** rather than one combined port — explicit
  enable strobe is clearer for learners and matches how real RDL tools generate
  this. Allows HW to load 0 explicitly if needed.
- **`wo` exposes the flop as an output port**: even though SW readback is 0,
  HW must be able to observe what was written. Without this the field would be
  unobservable — meaningless.
- **Make orchestrates validation gating** (vs. only doing it in `gen.tcl`'s `all` path):
  keeps each `make XXX` target single-purpose and lets Make's natural failure
  semantics do the work. Both gates are now in place (Make-level and TCL-level),
  belt-and-suspenders.
- **Validator is its own Python script** (not folded into `reggen_engine.py`):
  single responsibility, easier to test, fast to run.

## Problems hit & how we solved them
- **Make `all` ordering**: initial Phase 0 stub had `all: rtl header docs validate check` which would run validation AFTER generation — useless as a gate. Reordered to `validate rtl header docs check`. Documented why inline.
- **TCL error propagation from validator**: confirmed via `catch {exec ...} err` pattern that a non-zero Python exit raises in TCL, which propagates to tclsh non-zero exit, which makes Make abort. Tested by deliberately corrupting the spec.

## What I learned (plain language)
- **w1c is how every real IRQ controller works** (ARM GIC, RISC-V PLIC, NVIC).
  HW sets a sticky pending bit; firmware reads to see which IRQs fired; writes
  1 to the bits it handled to clear them. The HW priority over SW (last NBA
  wins) is the no-missed-IRQ guarantee.
- **wo registers are command/trigger ports**, not storage. The flop is just a
  convenient way to expose the write to HW; SW reading back would be meaningless
  because the trigger is a momentary action, not state.
- **rclr models event counters and FIFO levels** — HW increments / loads, SW
  reads to drain. Reading is the acknowledgement.
- **Lint comes before generate, every time.** Real EDA flows are deep stacks
  of generators and checkers; catching a bit overlap in the spec saves you
  from chasing a "weird simulation failure" 3 hours into a regression run.
- **TCL `catch { exec … } err`** is the idiom for running an external command
  and recovering from failure — equivalent to Python's `try: subprocess.run(...)`
  but built into the language.

## Capstone reflection — how I'd explain this in an interview
> "In Phase 1 I extended the generator to support five access types — rw, ro,
> plus three new ones: wo (software-write trigger registers), w1c (sticky bits
> set by HW, cleared by SW writing 1 — this is the IRQ controller pattern),
> and rclr (read-to-clear, used for event counters). The interesting design
> choice is the `always_ff` priority order: HW strobes come after SW writes
> in the procedural code, so the last non-blocking assignment wins, which
> guarantees a HW event in the same cycle as a SW ack is never lost. Then I
> built a spec validator — six checks for bit overlaps, range, naming,
> alignment, etc. — and wired it as `make validate`. The validator is gated
> ahead of generation in `make all`, so a broken spec aborts the build before
> any RTL is emitted. The whole thing is layered Make → TCL → Python, which
> is how real EDA flows are structured: the designer types `make`, the TCL
> mirrors a tool's command API, and Python does the work."

## Next session should start with
1. `make all` — confirm the full Phase 1 flow runs clean
2. Read `docs/HANDOFF.md` for current state
3. Begin **Phase 2**: C firmware header generation (`gen/include/irq_ctrl.h`)
   - `#define IRQ_CTRL_BASE 0x40001000`
   - per-register offset macros
   - per-field bit-position and mask macros
   - a `struct` view of the register block for typed access
