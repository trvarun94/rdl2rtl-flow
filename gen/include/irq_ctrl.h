#ifndef IRQ_CTRL_H
#define IRQ_CTRL_H

/*
 * GENERATED FILE — do not edit by hand.
 * Source: spec/irq_ctrl.yaml
 * Generator: tools/reggen/reggen_engine.py
 *
 * Block  : irq_ctrl
 * Base   : 0x40001000
 * Regs   : 5
 */

#include <stdint.h>

/* Base address */
#define IRQ_CTRL_BASE  0x40001000U

/* Register offsets */
#define IRQ_CTRL_CTRL_OFFSET        0x00U
#define IRQ_CTRL_STATUS_OFFSET      0x04U
#define IRQ_CTRL_IRQ_STS_OFFSET     0x08U
#define IRQ_CTRL_TRIG_OFFSET        0x0CU
#define IRQ_CTRL_FIFO_STS_OFFSET    0x10U

/* CTRL — Control register — enables and configures the interrupt controller */
#define IRQ_CTRL_CTRL_ENABLE_POS        0U
#define IRQ_CTRL_CTRL_ENABLE_MSK        (0x1U << 0U)
#define IRQ_CTRL_CTRL_ENABLE_WIDTH      1U
#define IRQ_CTRL_CTRL_MODE_POS          1U
#define IRQ_CTRL_CTRL_MODE_MSK          (0x3U << 1U)
#define IRQ_CTRL_CTRL_MODE_WIDTH        2U
#define IRQ_CTRL_CTRL_PRIORITY_POS      3U
#define IRQ_CTRL_CTRL_PRIORITY_MSK      (0x7U << 3U)
#define IRQ_CTRL_CTRL_PRIORITY_WIDTH    3U

/* STATUS — Status register — reflects current hardware state (read-only to software) */
#define IRQ_CTRL_STATUS_BUSY_POS      0U
#define IRQ_CTRL_STATUS_BUSY_MSK      (0x1U << 0U)
#define IRQ_CTRL_STATUS_BUSY_WIDTH    1U
#define IRQ_CTRL_STATUS_IRQ_POS       1U
#define IRQ_CTRL_STATUS_IRQ_MSK       (0x1U << 1U)
#define IRQ_CTRL_STATUS_IRQ_WIDTH     1U
#define IRQ_CTRL_STATUS_ERR_POS       2U
#define IRQ_CTRL_STATUS_ERR_MSK       (0x1U << 2U)
#define IRQ_CTRL_STATUS_ERR_WIDTH     1U

/* IRQ_STS — Interrupt status register — HW sets bits when IRQs fire; SW writes 1 to clear (acknowledge) */
#define IRQ_CTRL_IRQ_STS_IRQ0_PEND_POS      0U
#define IRQ_CTRL_IRQ_STS_IRQ0_PEND_MSK      (0x1U << 0U)
#define IRQ_CTRL_IRQ_STS_IRQ0_PEND_WIDTH    1U
#define IRQ_CTRL_IRQ_STS_IRQ1_PEND_POS      1U
#define IRQ_CTRL_IRQ_STS_IRQ1_PEND_MSK      (0x1U << 1U)
#define IRQ_CTRL_IRQ_STS_IRQ1_PEND_WIDTH    1U
#define IRQ_CTRL_IRQ_STS_IRQ2_PEND_POS      2U
#define IRQ_CTRL_IRQ_STS_IRQ2_PEND_MSK      (0x1U << 2U)
#define IRQ_CTRL_IRQ_STS_IRQ2_PEND_WIDTH    1U

/* TRIG — Software trigger register — write to fire a soft interrupt; readback is always 0 */
#define IRQ_CTRL_TRIG_SOFT_IRQ_POS      0U
#define IRQ_CTRL_TRIG_SOFT_IRQ_MSK      (0x1U << 0U)
#define IRQ_CTRL_TRIG_SOFT_IRQ_WIDTH    1U
#define IRQ_CTRL_TRIG_SOFT_NMI_POS      1U
#define IRQ_CTRL_TRIG_SOFT_NMI_MSK      (0x1U << 1U)
#define IRQ_CTRL_TRIG_SOFT_NMI_WIDTH    1U

/* FIFO_STS — FIFO status register — reports pending event count; reading clears the count (read-to-clear) */
#define IRQ_CTRL_FIFO_STS_EVT_COUNT_POS      0U
#define IRQ_CTRL_FIFO_STS_EVT_COUNT_MSK      (0xFU << 0U)
#define IRQ_CTRL_FIFO_STS_EVT_COUNT_WIDTH    4U

/*
 * Typed struct — use IRQ_CTRL->REGNAME for register access.
 * Members are plain uint32_t (not packed bitfields) for portability.
 */
typedef volatile struct {
    uint32_t CTRL; /* 0x00 — Control register — enables and configures the interrupt controller */
    uint32_t STATUS; /* 0x04 — Status register — reflects current hardware state (read-only to software) */
    uint32_t IRQ_STS; /* 0x08 — Interrupt status register — HW sets bits when IRQs fire; SW writes 1 to clear (acknowledge) */
    uint32_t TRIG; /* 0x0C — Software trigger register — write to fire a soft interrupt; readback is always 0 */
    uint32_t FIFO_STS; /* 0x10 — FIFO status register — reports pending event count; reading clears the count (read-to-clear) */
} irq_ctrl_t;

/* Pointer macro — IRQ_CTRL->CTRL dereferences the base address as the struct */
#define IRQ_CTRL  ((irq_ctrl_t *)IRQ_CTRL_BASE)

#endif /* IRQ_CTRL_H */
