# irq_ctrl Register Map

_Generated from `spec/irq_ctrl.yaml` — do not edit by hand._

| Property | Value |
|----------|-------|
| Base address | `0x40001000` |
| Register width | 32 bits |
| Registers | 5 |
| Fields | 12 |

---

## Register Summary

| Register | Offset | Description |
|----------|--------|-------------|
| `CTRL` | `0x00` | Control register — enables and configures the interrupt controller |
| `STATUS` | `0x04` | Status register — reflects current hardware state (read-only to software) |
| `IRQ_STS` | `0x08` | Interrupt status register — HW sets bits when IRQs fire; SW writes 1 to clear (acknowledge) |
| `TRIG` | `0x0C` | Software trigger register — write to fire a soft interrupt; readback is always 0 |
| `FIFO_STS` | `0x10` | FIFO status register — reports pending event count; reading clears the count (read-to-clear) |

---

## CTRL — Offset `0x00`

Control register — enables and configures the interrupt controller

| Field | Bits | Access | Reset | Description |
|-------|------|--------|-------|-------------|
| `ENABLE` | 0 | `rw` | `0x0` | Global interrupt enable (1=enabled) |
| `MODE` | 2:1 | `rw` | `0x0` | Operating mode (00=level, 01=edge, 10=pulse) |
| `PRIORITY` | 5:3 | `rw` | `0x0` | Interrupt priority level (0=lowest, 7=highest) |

## STATUS — Offset `0x04`

Status register — reflects current hardware state (read-only to software)

| Field | Bits | Access | Reset | Description |
|-------|------|--------|-------|-------------|
| `BUSY` | 0 | `ro` | `0x0` | Hardware busy flag (1=busy, set by HW) |
| `IRQ` | 1 | `ro` | `0x0` | Interrupt pending flag (1=interrupt active, set by HW) |
| `ERR` | 2 | `ro` | `0x0` | Error flag (1=error detected, set by HW) |

## IRQ_STS — Offset `0x08`

Interrupt status register — HW sets bits when IRQs fire; SW writes 1 to clear (acknowledge)

| Field | Bits | Access | Reset | Description |
|-------|------|--------|-------|-------------|
| `IRQ0_PEND` | 0 | `w1c` | `0x0` | IRQ channel 0 pending (HW sets; SW writes 1 to ack) |
| `IRQ1_PEND` | 1 | `w1c` | `0x0` | IRQ channel 1 pending (HW sets; SW writes 1 to ack) |
| `IRQ2_PEND` | 2 | `w1c` | `0x0` | IRQ channel 2 pending (HW sets; SW writes 1 to ack) |

## TRIG — Offset `0x0C`

Software trigger register — write to fire a soft interrupt; readback is always 0

| Field | Bits | Access | Reset | Description |
|-------|------|--------|-------|-------------|
| `SOFT_IRQ` | 0 | `wo` | `0x0` | Write 1 to assert a software interrupt (pulse) |
| `SOFT_NMI` | 1 | `wo` | `0x0` | Write 1 to assert a software NMI (non-maskable interrupt) |

## FIFO_STS — Offset `0x10`

FIFO status register — reports pending event count; reading clears the count (read-to-clear)

| Field | Bits | Access | Reset | Description |
|-------|------|--------|-------|-------------|
| `EVT_COUNT` | 3:0 | `rclr` | `0x0` | Pending event count (0-15); clears to 0 on read |
