# Session 01 — Phase 0: Skeleton + End-to-End RTL Generation
_Date: 2026-05-31_

## Goal for this session
Build Phase 0 from scratch in an empty folder:
- Repo skeleton and docs system
- YAML register spec (single source of truth)
- Python engine: YAML → APB SystemVerilog
- TCL tool API wrapping the engine
- Designer run script
- Makefile front door
- Verify `make rtl` generates a valid `gen/rtl/irq_ctrl.sv`
- Write concept notes and this log

## What we did
1. Verified environment: Python 3.13.5, GNU Make 3.81, tclsh 8.6.14, pyyaml 6.0.2 ✅
2. Created the full directory skeleton:
   `spec/`, `tools/reggen/`, `flow/run/`, `gen/{rtl,include,docs}`, `config/`, `docs/{sessions,notes}/`
3. Created `.gitignore`, `README.md`, `docs/HANDOFF.md`
4. Wrote `spec/irq_ctrl.yaml` — 2 registers (CTRL with 3 rw fields, STATUS with 3 ro fields)
5. Wrote `tools/reggen/reggen_engine.py` — parses YAML, generates APB SystemVerilog and JSON manifest
6. Wrote `tools/reggen/reggen.tcl` — TCL tool API: `read_spec`, `set_output_dir`, `generate_rtl`
7. Wrote `flow/run/gen.tcl` — designer run script, sources the tool API, calls commands
8. Wrote `Makefile` — `make rtl`, `make clean`, `make help` (plus stubs for later phases)
9. Fixed a trailing-comma bug in the port list (SV syntax error on the last port)
10. Ran `make rtl` successfully — confirmed `gen/rtl/irq_ctrl.sv` is correct
11. Wrote concept notes: registers-and-csrs, apb-basics, code-generation, make-basics, tcl-basics, systemrdl-intro

## Commands run (so I can reproduce)
```bash
make help          # see all targets
make rtl           # generate gen/rtl/irq_ctrl.sv
make clean         # remove gen/ outputs
```

## Decisions made (and why)
- **YAML over SystemRDL as spec format**: keeps parser trivial; the data model
  maps 1:1. SystemRDL is documented in `docs/notes/systemrdl-intro.md`. Phase 5
  (stretch) can add a mini-RDL parser.
- **PeakRDL not used for the engine**: discussed and decided against. Building
  the engine from scratch gives deeper understanding of what a register generator
  actually does (flip-flop storage, read mux, access types). Reference to PeakRDL
  is in docs; stretch phase can add it as an alternative front-end.
- **`gen/` is checked in**: so Phase 4 consistency-gating can diff against a
  real baseline. `.gitignore` documents this choice.
- **APB as bus protocol**: simplest AMBA bus, best for learning. Explained in
  `docs/notes/apb-basics.md`.
- **`make help` as default target**: always safe; never accidentally runs
  generation or deletion.

## Problems hit & how we solved them
- **Trailing comma on last port**: the initial loop appended a comma to every
  `ro` field port, including the last one — which is a SV syntax error.
  Fixed by collecting all ports into a list first, then rendering commas only
  between entries (not after the last).

## What I learned (plain language)
- **CSRs** are the interface between software and hardware. Software writes to
  a known address; hardware logic reads the stored value to control behavior.
  For status registers, it's reversed: hardware writes, software reads.
- **APB** is a 2-cycle handshake bus. The `PENABLE` signal distinguishes the
  access phase from the setup phase. Our generator always drives `PREADY=1`
  (zero wait states).
- **Code generation** is just walking a data structure and emitting strings.
  The patterns (write logic, storage flops, read mux) are fixed; only the
  names, widths, and offsets come from the spec.
- **TCL's exec** is the bridge between the TCL API and the Python engine.
  If Python exits non-zero, TCL raises an error automatically — that's free
  failure gating.
- **Make's `.PHONY`** is important: without it, Make would look for files
  named `rtl`, `clean`, etc. and silently skip the recipe if a file by that
  name existed.

## Capstone reflection — how I'd explain this in an interview
> "I built a register generation flow that takes a YAML register spec as the
> single source of truth and generates an APB SystemVerilog register block.
> The key insight is that a register block has a fixed structure — APB port
> interface, one flip-flop per rw field, address-decoded write logic, and a
> combinational read mux — so you can template it: walk the spec, fill in
> names and bit ranges, emit the RTL. I wrapped the Python engine in a TCL
> tool API because that's how real EDA tools are orchestrated, and exposed a
> Make front door so a designer just types `make rtl`. The methodology value
> comes in Phase 1 (validation) and Phase 4 (consistency gating) — catching
> spec errors early and preventing stale generated files from shipping."

## Next session should start with
1. `cd rdl2rtl_flow && make rtl` — confirm it still works
2. Read `docs/HANDOFF.md` for current state
3. Begin Phase 1: add `wo`, `w1c`, `rclr` access types to the engine, then build the spec validator
