# Code generation (in EDA / register flows)

## What is "code generation"?
A program that reads a high-level description and **emits source code** in
another language. In our case: read a YAML register spec, emit SystemVerilog.

## Why generate instead of hand-write?
- **Single source of truth**: change the spec once, everything downstream
  updates. No drift between RTL, headers, and docs.
- **Correctness by construction**: the generator follows a fixed pattern,
  so structural bugs (off-by-one bit slices, missing address decode) are
  impossible by design.
- **Scale**: 5000 registers across 50 blocks is normal for a modern SoC.
  Hand-writing is infeasible.
- **Multi-output**: one spec → RTL + C header + docs + UVM RAL + Python
  model. All consistent.

## How does our engine work (step by step)?
1. **Parse** the YAML into a Python dict (`yaml.safe_load`).
2. **Walk** the dict — for each register and field, decide what RTL to emit.
3. **Emit** strings into a list, then `"\n".join(lines)`.
4. **Write** to file.

That's it. Phase 0 uses plain string templates. A real tool (or a future
refactor) would use **Jinja2** templates, but the principle is identical.

## Phase 0 emission patterns
- Module header + APB ports (boilerplate)
- For each `ro` field → emit an extra `input logic ...` port (HW-driven)
- For each `rw` field → emit a `logic` declaration for the storage flop
- `always_ff` block with reset + write logic — `case` on `PADDR[7:0]`
- `always_comb` block with the read mux — `case` on `PADDR[7:0]`

## Real tools that do this
| Tool | Input | Output |
|------|-------|--------|
| PeakRDL (open source) | SystemRDL `.rdl` | SV, UVM, C, HTML, JSON |
| Semifore CSRCompiler  | SystemRDL `.rdl` | SV, UVM, C, docs, IP-XACT |
| Agnisys IDesignSpec   | SystemRDL/IP-XACT | SV, UVM, C, docs |
| Synopsys Register Compiler | SystemRDL | RTL, UVM, docs |

All of them apply the same idea: **one spec, many generated outputs, gated for
consistency**. We are building a learning-grade version of the same pattern.

## Interview-ready one-liner
> "Register generation is a code-generation flow: parse a structured spec,
> walk it, emit RTL/headers/docs from templates. The methodology value comes
> from the gating around it — validation of the spec, consistency checks
> against checked-in outputs, and CI enforcement that prevents stale files."
