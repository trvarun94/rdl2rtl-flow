# SystemRDL — a quick introduction

## What is SystemRDL?
**SystemRDL** (Register Description Language) is an industry-standard,
Accellera-blessed language for describing memory-mapped registers. It's
what real register-generation tools take as input.

In this project, **we use YAML instead of SystemRDL** to keep the parser
trivial and focus on the methodology. The data model is the same; only the
syntax differs.

## What does SystemRDL look like?
A SystemRDL version of our `irq_ctrl` block would look like:

```systemrdl
addrmap irq_ctrl {
    name = "Interrupt Controller";
    desc = "Top-level interrupt enable and status";

    reg {
        name = "CTRL";
        desc = "Control register";

        field { sw = rw; hw = r; reset = 0; } ENABLE[0:0];
        field { sw = rw; hw = r; reset = 0; } MODE[2:1];
        field { sw = rw; hw = r; reset = 0; } PRIORITY[5:3];
    } CTRL @ 0x00;

    reg {
        name = "STATUS";
        desc = "Status register";

        field { sw = r; hw = rw; } BUSY[0:0];
        field { sw = r; hw = rw; } IRQ[1:1];
        field { sw = r; hw = rw; } ERR[2:2];
    } STATUS @ 0x04;
};
```

Compare to our YAML — the *concepts* line up 1:1:

| SystemRDL                         | Our YAML              |
|-----------------------------------|-----------------------|
| `addrmap` / `regfile`             | `block:`              |
| `reg { ... } NAME @ 0xNN;`        | `name:` + `offset:`   |
| `field { sw=rw; hw=r; ...} BITS;` | `access: rw`, `bits:` |
| `reset = 0;`                      | `reset: 0`            |

## SystemRDL access semantics (`sw` × `hw`)
Where YAML uses one `access` field, SystemRDL splits it into two: what
**software** can do (`sw`) and what **hardware** can do (`hw`). The
combination implies the access type:

| SW | HW | Implies                |
|----|----|------------------------|
| rw | r  | rw (config register)   |
| r  | rw | ro (status register)   |
| w  | r  | wo (write trigger)     |
| rw | rw | bidirectional shared   |

Plus modifiers: `woclr`, `woset`, `rclr`, `rset`, `singlepulse`, etc.

## Why not just use SystemRDL here?
- **Parsing burden**: a real SystemRDL parser is non-trivial (Accellera spec
  is ~400 pages). PeakRDL solves this with a real ANTLR grammar.
- **Learning ROI**: YAML lets you see every byte of the input. SystemRDL
  adds inheritance, property-set instantiation, and `regfile`/`addrmap`
  nesting that distract from the methodology focus.
- **Stretch phase**: Phase 5 (option A) is a mini-RDL parser — a simplified
  text syntax to get a taste of the real language.

## How to actually use SystemRDL in real life
1. Write `.rdl` files.
2. Run **PeakRDL** (`pip install peakrdl peakrdl-regblock peakrdl-uvm
   peakrdl-html`).
3. Get out: SystemVerilog register block, UVM RAL model, C header, HTML docs.

PeakRDL is open source and free — a great tool to install and play with after
this capstone, since you'll already understand what a register generator is
trying to do.

## Interview-ready one-liner
> "SystemRDL is the Accellera standard for register description — the input
> language for tools like PeakRDL, Semifore, Agnisys. In this capstone I used
> YAML to keep the parser out of scope, but the data model maps 1:1 — block,
> register, field, access type, reset, bit range. Same generation flow."
