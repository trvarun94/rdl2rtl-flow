# Register Access Types

The "access" attribute of a field defines the *contract* between software and
hardware for that bit (or group of bits). Five access types are common; this
project supports all five.

## The five types at a glance

```
                  SOFTWARE ACTION
                  ┌───────────┬───────────────────────────────────┐
                  │  WRITE    │  READ                             │
  ────────────────┼───────────┼───────────────────────────────────┤
  rw              │ stores    │ returns stored value              │
  ro              │ ignored   │ returns live HW input port        │
  wo              │ stores    │ always returns 0 (no readback)    │
  w1c             │ writing 1 │ returns sticky flop (HW sets;     │
                  │ clears    │ SW clears by writing 1 to bit)    │
  rclr            │ ignored   │ returns value AND clears it to 0  │
  ────────────────┴───────────┴───────────────────────────────────┘
```

## Why each exists — concrete examples

### `rw` — Read/Write (the default)
Used for **control** registers (CTRL.ENABLE, MODE, PRIORITY) and **configuration**
(thresholds, prescalers, polarity bits). SW writes a value, HW reads it later
to know how to behave.

### `ro` — Read-Only
Used for **status** signals driven by hardware. SW can read but not write.
- `STATUS.BUSY` — a state machine elsewhere on the chip asserts this when it's running.
- `STATUS.ERR` — flagged by HW when it detects an error condition.
- Identifier registers (chip ID, version), reset cause, etc.

### `wo` — Write-Only
Used for **command** or **trigger** registers — fields that represent an *action*,
not a *state*. Reading them back would return meaningless or stale data.
- `TRIG.SOFT_IRQ` — write 1 to fire a software interrupt (a pulse).
- Some chips have a "BOOT" register that triggers a re-init when written.

The flop in our generated RTL exists so HW can observe what SW wrote (the
output port `hw_<R>_<F>` exposes it). SW readback is hardwired to 0.

### `w1c` — Write-1-to-Clear (sticky bit)
The classic **interrupt-pending** pattern. HW sets the bit when an event happens;
the bit *stays set* until SW acknowledges by writing 1 to it.

This is exactly how:
- ARM GIC (Generic Interrupt Controller) `GICD_ISPENDRn` / `GICD_ICPENDRn`
- RISC-V PLIC pending register
- ARM Cortex-M NVIC `NVIC_ICPRn`
…all work. Every real interrupt controller you'll ever touch uses w1c.

**Why "write 1 to clear" and not "any write clears"?** Because the register
typically holds **multiple IRQs in one word**. If "any write to the register
clears it" then SW couldn't selectively ack IRQ 2 without also clearing IRQ 5.
With w1c, SW writes `1` only in the bit positions it wants to clear.

```
  Before:  IRQ_STS = 0b00010110  (IRQs 1, 2, 4 pending)
  SW writes:        0b00000100  (acking only IRQ 2)
  After:   IRQ_STS = 0b00010010  (IRQs 1, 4 still pending — not lost)
```

### `rclr` — Read-to-Clear
Used for **event counters** or **status latches** where the act of reading
drains the value. HW loads new values; reading both **observes and clears**.

Examples:
- A UART error counter: HW increments; SW reads it (and resets) periodically.
- A "have you seen this event since you last asked?" latch.

The clear is **registered** (it takes effect on the clock after the read),
so the read still returns the pre-clear value. The combinational read mux
returns the current flop; `always_ff` sets it to 0 on the next edge.

## RTL block diagram — one flop, multiple writers

For w1c and rclr, multiple "writers" can target the same flop in one clock:

```
                       ┌─────────────────────────────┐
                       │                             │
   PCLK ──►            │                             │
                       │     Storage flop            │
   Reset ─────────────►│     r_REG_FIELD             │──► (to PRDATA mux
                       │                             │     and/or HW output)
   APB write ────────► │                             │
   (rw/wo store,       │     SystemVerilog rule:     │
    w1c write-1-clear) │     last NBA assignment     │
                       │     wins in always_ff       │
   APB read ──────────►│                             │
   (rclr clear)        │                             │
                       │                             │
   HW _set (w1c) ─────►│                             │
                       │                             │
   HW _en+val (rclr) ─►│                             │
                       └─────────────────────────────┘
                            ▲
                            │
                       Priority (lowest → highest):
                          APB write
                          APB read-clear
                          HW _set
                          HW _en+val
                       HW comes LAST → HW events never lost.
```

## Why HW priority matters — the "no missed IRQ" argument

Consider a w1c bit `IRQ0_PEND`. The cycle plays out like this:
1. SW reads `IRQ_STS`, sees `IRQ0_PEND=1`, decides to ack it.
2. SW writes `IRQ_STS = 0x01` to clear `IRQ0_PEND`.
3. **In the very same clock**, a new IRQ0 fires — HW asserts `hw_IRQ0_PEND_set`.

If SW priority wins, the HW set is dropped → **silent missed interrupt**, which
in the field looks like "the chip occasionally stops responding for no reason."
By making HW priority win, the flop ends at 1: the new IRQ is preserved, SW
will see it on its next poll, and *no event is ever lost*.

This is a real-world reason a teaching project like this is worth doing —
the same priority bug exists in junior-engineer-written RTL all the time,
and it's a classic interview question.

## Generator implementation summary

In `tools/reggen/reggen_engine.py`, each access type drives:

| access | flop? | HW ports | Read mux | Write logic |
|---|---|---|---|---|
| rw   | ✅ | (none)              | flop      | store PWDATA |
| ro   | ❌ | input value         | live HW input | (n/a)    |
| wo   | ✅ | output value        | 0         | store PWDATA |
| w1c  | ✅ | input `_set` strobe | flop      | if PWDATA[bit]→clear; HW set wins |
| rclr | ✅ | input value + `_en` | flop      | clear on read; HW load wins      |
