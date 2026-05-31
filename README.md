# rdl2rtl-flow

A mock **register-generation flow**: describe your registers once in YAML, generate
SystemVerilog RTL, a C firmware header, and documentation — all from a single source
of truth. Wrapped in real methodology: spec validation, multi-output consistency
gating, and Make + TCL orchestration.

## Why this exists

In a real chip, hundreds of Control and Status Registers (CSRs) must be kept in sync
across RTL, firmware, docs, and verification. Hand-maintaining them is error-prone.
This flow mimics what commercial tools (PeakRDL, Semifore, Agnisys, Synopsys Register
Compiler) do: take one register spec and generate everything downstream.

## Quick start

```bash
make help          # show all targets
make rtl           # generate SystemVerilog from spec/irq_ctrl.yaml
make validate      # lint the register spec
make header        # generate C firmware header
make docs          # generate register-map documentation
make all           # generate + validate + consistency check
make clean         # remove generated outputs
```

Generated outputs land in `gen/` and are **checked in** so the consistency checker
can detect drift between the spec and the checked-in files.

## Repo layout

```
spec/           register spec(s) — the single source of truth (YAML)
tools/reggen/   generator: TCL API + Python engine + templates
flow/run/       designer-facing TCL run scripts
gen/            GENERATED outputs: rtl/, include/, docs/
config/         project config (which spec, which outputs)
docs/           learning notes, session logs, HANDOFF.md
Makefile        top-level entry point
```

## Tech stack

- **Make** — single front door
- **TCL** — tool command API + run scripts (mirrors real EDA tool flows)
- **Python** — spec parser, validators, generators
- **YAML** — register spec format (real tools use SystemRDL; noted in `docs/notes/systemrdl-intro.md`)

## Learning trail

See `docs/notes/` for beginner-friendly explanations of every concept used here:
registers/CSRs, APB protocol, code generation, access types, Make, TCL, and more.
