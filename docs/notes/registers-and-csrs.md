# Registers and CSRs

## What is a register?
A "register" inside a chip is a small piece of fast storage — typically 32 or 64
bits — that holds state. The kind we care about here are **Control and Status
Registers (CSRs)**: registers that **software can read and write** via the bus,
to talk to the hardware.

## Why do they exist?
Software (running on the CPU) and hardware (logic gates on the chip) are two
worlds. They need a way to communicate:
- **Software → Hardware**: "Hey UART, please send this byte at 115200 baud."
- **Hardware → Software**: "Hey CPU, the data transfer finished."

CSRs are the agreed-upon mailbox between them. Each CSR has a fixed memory
address; software reads/writes it like normal memory, but the address is wired
to a hardware block instead of DRAM.

## Anatomy of a register
A 32-bit register is divided into **fields** — meaningful groups of bits. Example:

```
Bit:  31                                              5 4 3 2 1 0
      ┌─────────────────────────────────────────────┬─┬─┬─┬─┬─┬─┐
      │ unused (reserved)                           │  PRI │MOD│E│
      └─────────────────────────────────────────────┴─┴─┴─┴─┴─┴─┘
                                                     PRIORITY MODE ENABLE
                                                     (3 bits)(2 bits)(1)
```

This is `CTRL` from our irq_ctrl block. Software can write `0x0000_0029` to
enable interrupts with mode=1, priority=5 — all in one register write.

## Access types (the heart of register design)
A field is not just bits — it also has a *behavior*: who can write it, what
happens on read, etc. The common ones:

| Type | Software can | Hardware can | Notes |
|------|--------------|--------------|-------|
| `rw`  | read/write   | read         | Plain config knob |
| `ro`  | read only    | write        | Status flag set by HW |
| `wo`  | write only   | read         | Write-triggers, e.g. "start" |
| `w1c` | write 1 to clear | set (write 1) | Common for interrupt flags |
| `rclr`| read; read clears | set | Read-to-clear, a.k.a. self-clearing |

In Phase 0 we support only `rw` and `ro`. Phase 1 adds the rest.

## How many CSRs does a real chip have?
- A simple peripheral (UART, SPI): tens of registers
- A complex IP block (USB, PCIe controller): hundreds
- A modern SoC: **thousands** in total across all blocks

That's why hand-writing the RTL, headers, and docs is unsustainable —
register generation is mandatory above a certain scale.

## Interview-ready one-liner
> "A CSR is a memory-mapped register that lets software configure a hardware
> block or read its status. Modern chips have thousands of them, which is why
> every serious flow uses a code-generation tool — RDL → RTL, headers, docs,
> UVM models — to keep them all in sync from one source of truth."
