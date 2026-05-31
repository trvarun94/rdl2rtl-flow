# APB (Advanced Peripheral Bus) — beginner's guide

## What is it?
**APB** = **A**dvanced **P**eripheral **B**us, part of ARM's **AMBA** bus
family. It's a simple synchronous bus designed for **low-bandwidth control and
status registers** — not for streaming data.

If a chip has an AXI or AHB backbone for high-throughput traffic, APB is
typically the "side road" that connects to the peripheral registers. A
manager (CPU or AXI-to-APB bridge) talks to APB subordinates (UART, GPIO,
timers, our `irq_ctrl`).

## Why is it the right bus for registers?
1. **Simple** — easy to implement, easy to verify
2. **Low pin count** — no burst, no out-of-order, no IDs
3. **Zero-or-low-wait-state** — register reads/writes are just one access
4. **Universally supported** — every IP block in industry has an APB version

When PeakRDL/Semifore generate a register block, APB is almost always one of
the supported bus types.

## The signals (subordinate side)
| Signal     | Dir | Purpose |
|------------|-----|---------|
| `PCLK`     | in  | Clock |
| `PRESETn`  | in  | Active-low reset |
| `PADDR`    | in  | Address being accessed |
| `PWRITE`   | in  | 1 = write, 0 = read |
| `PSEL`     | in  | This subordinate is selected |
| `PENABLE`  | in  | Second cycle of transfer (the "access" phase) |
| `PWDATA`   | in  | Write data |
| `PRDATA`   | out | Read data |
| `PREADY`   | out | We're done — 1 = no wait state |

(Newer APB versions add `PPROT`, `PSTRB`, `PSLVERR`. We ignore those for
learning.)

## The 2-cycle handshake
APB transfers always take 2 cycles:

```
Cycle 1 (SETUP)             Cycle 2 (ACCESS)
PSEL    = 1                 PSEL    = 1
PENABLE = 0                 PENABLE = 1        ← only difference
PADDR   = valid             PADDR   = same
PWRITE  = valid             PWRITE  = same
PWDATA  = valid (if write)  PWDATA  = same
                            PREADY  = 1 (we respond now)
                            PRDATA  = valid (if read)
```

The subordinate captures the write (or drives PRDATA) on the cycle where
`PSEL && PENABLE` is true. That's why our generator's write logic is:
```verilog
if (PSEL && PENABLE && PWRITE) ...
```

## How it maps into our generated RTL
- **Address decode**: `case (PADDR[7:0])` selects which register's flop bank
  to write or read mux to drive. (Upper PADDR bits select the *block* — that's
  done by an external decoder, outside our module.)
- **Write logic**: under `always_ff @(posedge PCLK)`, condition on
  `PSEL && PENABLE && PWRITE`, then `case` on the address, then assign the
  right `PWDATA` slice into the right `r_<REG>_<FIELD>` flop.
- **Read mux**: combinational `always_comb`, condition on `PSEL && !PWRITE`,
  `case` on address, drive `PRDATA` from the field signals.
- **PREADY**: tied 1 — we never need to stall.

## Interview-ready one-liner
> "APB is the simplest AMBA bus — 2-cycle handshake, no bursts, perfect for
> register access. Generated register blocks usually expose an APB port
> because it's universally supported and trivial to verify."
