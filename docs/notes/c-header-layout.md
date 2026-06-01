# C Firmware Header Layout

**What is this?**
Every hardware register block needs a way for firmware (C code running on the CPU) to access it safely without embedding magic numbers. The C header file is that interface. It is generated from the same YAML spec that drives RTL generation — so the hardware and firmware are guaranteed to stay in sync.

**Real-world counterpart**
In ARM's CMSIS standard (used on every Cortex-M microcontroller), every peripheral ships with a generated header like this. Look at `stm32f4xx.h` or `nrf52840.h` and you'll see exactly this pattern: base address, offset macros, field masks, volatile struct, and a pointer macro. Our generated `irq_ctrl.h` follows that same convention.

---

## The four parts of the header

### 1. Include guard
```c
#ifndef IRQ_CTRL_H
#define IRQ_CTRL_H
...
#endif /* IRQ_CTRL_H */
```
Prevents double-inclusion when multiple `.c` files include the same header. Standard C practice.

`#include <stdint.h>` provides `uint32_t` — a fixed-width 32-bit unsigned integer. Using `int` or `unsigned int` is platform-dependent; `uint32_t` is always exactly 32 bits.

### 2. Base address macro
```c
#define IRQ_CTRL_BASE  0x40001000U
```
The physical address in the chip's memory map where this register block starts. The `U` suffix makes it an **unsigned** literal — without it, addresses above `0x7FFFFFFF` would be negative signed integers on 32-bit systems, causing subtle casting bugs.

### 3. Register offset and field macros
```c
#define IRQ_CTRL_CTRL_OFFSET       0x00U

#define IRQ_CTRL_CTRL_ENABLE_POS   0U
#define IRQ_CTRL_CTRL_ENABLE_MSK   (0x1U << 0U)
#define IRQ_CTRL_CTRL_ENABLE_WIDTH 1U
```
Three macros per field:
- **_POS** — bit position of the field's LSB. Used to shift a value into position before writing, or to shift it out after reading.
- **_MSK** — bitmask that covers exactly the field's bits. Used to isolate the field when reading, and to avoid clobbering adjacent fields when writing.
- **_WIDTH** — number of bits. Useful for bounds-checking values before writing, and for documentation/tooling.

Usage example:
```c
/* Write MODE=2 into CTRL without touching other fields */
IRQ_CTRL->CTRL = (IRQ_CTRL->CTRL & ~IRQ_CTRL_CTRL_MODE_MSK)
               | (2U << IRQ_CTRL_CTRL_MODE_POS);

/* Read current MODE value */
uint32_t mode = (IRQ_CTRL->CTRL & IRQ_CTRL_CTRL_MODE_MSK)
                >> IRQ_CTRL_CTRL_MODE_POS;
```

### 4. Volatile struct + pointer macro
```c
typedef volatile struct {
    uint32_t CTRL;     /* 0x00 */
    uint32_t STATUS;   /* 0x04 */
    ...
} irq_ctrl_t;

#define IRQ_CTRL  ((irq_ctrl_t *)IRQ_CTRL_BASE)
```
The struct lets firmware use named member access (`IRQ_CTRL->CTRL`) instead of raw pointer arithmetic (`*(uint32_t *)(0x40001000 + 0x00)`). Both compile to the same load/store instruction — the struct is just safer and more readable.

**`volatile` is mandatory** for hardware registers. Without it:
- The compiler may cache a register read in a CPU register and skip re-reading memory.
- Two consecutive reads of the same register may return the same cached value even if the hardware changed it between reads.
- An interrupt handler that writes a register may have its write optimized away.

`volatile` tells the compiler: *this memory location can change at any time outside your knowledge — always read it fresh and always write it immediately.*

---

## Why NOT packed C bitfields?

You might write:
```c
typedef struct {
    uint32_t ENABLE   : 1;
    uint32_t MODE     : 2;
    uint32_t PRIORITY : 3;
    uint32_t          : 26;  /* padding */
} ctrl_t;
```
This looks clean but has a critical flaw: **the C standard (C99 §6.7.2.1) explicitly leaves bitfield layout implementation-defined.** Specifically:
- Which end of the word the first bit occupies (big-endian vs little-endian bit order)
- How padding is inserted between fields
- Whether a field can straddle a word boundary

ARM-GCC, IAR Embedded Workbench, MSVC, and Keil ARMCC all pack bitfields differently. A header that works perfectly with one compiler silently generates wrong register accesses on another. Production embedded teams — including ARM's own CMSIS team — explicitly avoid packed bitfields in hardware register headers for this reason.

**Macro masks are portable.** `(0x3U << 1U)` means the same thing on every compiler, CPU, and endianness.

---

## Naming convention

All macros follow the pattern `BLOCK_REGISTER_FIELD_SUFFIX`:
- `IRQ_CTRL` — block name (from `block:` in the YAML spec)
- `CTRL` — register name
- `ENABLE` — field name
- `POS` / `MSK` / `WIDTH` — suffix

This avoids name collisions when multiple register blocks are included in the same project. Every symbol is globally unique.
