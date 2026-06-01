# Session 03 — Phase 2: C Firmware Header

**Date:** 2026-05-31
**Phase:** 2 — C firmware header generation
**Status at end:** Complete ✅

---

## What we built

Implemented `generate_header()` in `tools/reggen/reggen_engine.py`. The function reads the same spec dict already used by RTL generation and emits `gen/include/irq_ctrl.h` with:

1. **Include guard + `#include <stdint.h>`** — boilerplate that every C header needs
2. **Base address macro** — `#define IRQ_CTRL_BASE 0x40001000U` with `U` suffix
3. **Register offset macros** — one per register, aligned to a consistent column
4. **Field macros** — three per field: `_POS` (LSB position), `_MSK` (bitmask), `_WIDTH` (bit count)
5. **`volatile struct` typedef** — `irq_ctrl_t` with one `uint32_t` member per register; auto-padding for address gaps
6. **Pointer macro** — `#define IRQ_CTRL ((irq_ctrl_t *)IRQ_CTRL_BASE)`

No changes were needed to the TCL layer (both `reggen.tcl` and `gen.tcl` already dispatched `--output header` to the engine).

---

## Key concepts introduced

### `volatile` in firmware
Hardware registers are memory-mapped I/O: the CPU and hardware both read/write the same addresses. `volatile` tells the C compiler to never cache a read (always re-fetch from memory) and never elide a write (always store to memory). Without it, optimized code can silently skip reads or writes to registers — a notoriously hard class of firmware bug.

### Why not packed C bitfields?
C packed bitfields (`uint32_t ENABLE:1;`) look like a natural fit for register fields but C99 §6.7.2.1 leaves bitfield layout (bit order within a word, padding between fields) **implementation-defined**. Different compilers (ARM-GCC, IAR, MSVC, Keil ARMCC) pack them differently. Production embedded firmware universally uses macro masks (`(0x1U << 0U)`) instead — portable across every compiler, CPU, and endianness. This was a deliberate architectural choice documented in `docs/notes/c-header-layout.md`.

### Macro mask formula
For a field at bits `[msb:lsb]`:
- `_POS  = lsb`
- `_MSK  = ((1 << width) - 1) << lsb`  where `width = msb - lsb + 1`
- `_WIDTH = width`

Examples: `CTRL.PRIORITY` at bits `[5:3]` → POS=3, MSK=`(0x7U << 3U)`, WIDTH=3.

### CMSIS connection
This header follows the same convention as ARM's CMSIS standard headers (e.g., `stm32f4xx.h`, `nrf52840.h`): base address + offset macros + field masks + volatile struct + pointer macro. Every Cortex-M embedded engineer would recognize this layout instantly.

---

## Files changed

| File | Change |
|------|--------|
| `tools/reggen/reggen_engine.py` | Added `generate_header()`; updated `main()` stub → real write |
| `gen/include/irq_ctrl.h` | NEW: generated C header |
| `docs/notes/c-header-layout.md` | NEW: explains header anatomy, volatile, bitfield pitfall |
| `docs/HANDOFF.md` | Updated: Phase 2 complete, Phase 3 plan |
| `docs/sessions/session-03.md` | NEW: this file |

---

## Interview-framed reflection

**Q: Why does a single-source-of-truth register generation flow matter in a real chip project?**

A: In a large SoC, a register block might be touched by RTL engineers, firmware engineers, verification engineers, and architects — all working in parallel. If any one of them manually edits their copy of the register map (the SV file, the C header, the design spec), they introduce a risk of divergence: firmware reads field X at bit 3 while hardware actually implemented it at bit 4. By generating all three artifacts from one YAML spec, that class of bug is impossible — if the spec changes, everyone regenerates and the divergence is caught before tape-out.

**Q: What was the one design decision that required the most thought in Phase 2?**

A: Whether to use a `volatile struct` with bitfields vs macro masks. Bitfields look cleaner in code but are compiler-dependent. Macros are more verbose but portable and explicitly correct. The decision matters in interview settings because it shows you understand that embedded C has constraints that desktop software doesn't: you can't abstract away the hardware layout.

---

## Next session (Phase 3)

Implement `generate_docs()` in `reggen_engine.py` — emit `gen/docs/irq_ctrl.md`, a Markdown register map table (one row per field). All the TCL and Make plumbing is already in place. See `docs/HANDOFF.md` for the full plan.
