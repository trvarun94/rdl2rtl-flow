# Capstone Project Prompt — RDL→RTL Register Generation Flow (for Claude Code)

> **How to use this file:** Create a **brand-new empty folder**, save this file
> inside it as `SPEC.md`, open Claude Code in that folder, and paste the
> **Kickoff message** (very bottom) as your first message. Claude Code will read
> this spec and start Session 1. You can also paste this entire file as your
> first message.
>
> **▶ Start completely fresh.** This project begins at **Phase 0** in an **empty
> folder**. Do **not** assume, reuse, or look for any files from any earlier
> conversation — there are none. Build every file yourself, from zero, in the
> order this spec lays out.

> **Sibling project (context, not a dependency):** I have a separate capstone
> that builds the *analysis* side of front-end CAD — mock Lint/CDC/RDC tools.
> **This** project is the *construction* side: generating RTL from a register
> description. Together they cover both halves of "RTL Construction and Analysis."
> Build this one standalone; do not depend on the other repo.

---

## 0. This is my capstone project

Treat this as a **capstone project**: a substantial, portfolio-defining build I
will show in interviews and put on GitHub. That means rigor, a clear learning
trail, and a polished final writeup — not just working code.

**Learning objectives** — what I must be able to explain confidently by the end:
- What memory-mapped registers (CSRs) are and why nearly every chip has many.
- What a **register description language** (SystemRDL) is and why register
  generation flows exist (single source of truth → RTL + firmware + docs + DV).
- Register **field access types** (rw, ro, wo, w1c, rclr, hardware-writable…) and
  what each means in hardware.
- How a generator/flow is structured: spec parsing, validation, code generation,
  multi-output consistency, and gating — the methodology around the tool.
- A basic register-bus protocol (APB) and enough Make/TCL to write real EDA flows.

**Definition of success:** a clean GitHub repo where `make all` turns one register
spec into a SystemVerilog register block, a C header, and documentation; a
documented learning trail (notes + session logs); and a final **capstone report**
I could walk an interviewer through start to finish.

---

## 1. Who I am (read this — it changes how you should help me)

- I'm a software/methodology engineer. **I'm comfortable with Python and general
  coding.**
- **I am a beginner at TCL and Makefiles.** Assume I know nothing about either.
  Explain every TCL/Make concept in plain language *before* using it, and write a
  short note about it.
- I am **new to hardware register design**. Explain the hardware concepts
  (registers, fields, access types, APB) as you go — assume I'm smart but new.
- I learn **by doing**. Build small, runnable things; explain as you go.
- **Goal:** prepare for an Apple "Front-End CAD Methodology Engineer" interview by
  building a realistic register-generation flow myself.

**Tone rules for you (Claude Code):**
- **Explain before you implement — always.** Before writing or changing any code,
  explain (a) what we're about to build, (b) the real-world EDA/hardware concept
  behind it, and (c) how you plan to implement it. Then **wait for me to confirm I
  understand and say "go"** before writing code. This is a teaching loop, not a
  delivery service — never jump straight to code.
- Explain the *why* before the *how*. Tie each piece to its real-world counterpart
  (SystemRDL, PeakRDL, Semifore, Agnisys, Synopsys register tooling).
- No unexplained "magic." Comment code generously.
- Prefer clarity over cleverness.
- When you hit a real decision, pause and ask me rather than guessing.

---

## 2. What we're building

A **mock register-generation flow** ("rdl2rtl"): take a register description as
the **single source of truth** and *generate* everything downstream from it —
RTL, firmware headers, and documentation — wrapped in real methodology (run
orchestration, spec validation, multi-output consistency, and gating).

**The core idea (this is the whole point):** registers are the software-visible
control/status interface of a chip, and there are hundreds or thousands of them.
Hand-writing the RTL, *and* keeping firmware headers, docs, and verification
models in sync, is tedious and bug-prone. So you describe the registers **once**
and generate the rest. Correctness-by-construction. That generation flow is a
flagship front-end CAD methodology responsibility.

### The layers
1. **Spec layer** — a register description (the single source of truth): blocks,
   registers, fields, access types, reset values, addresses.
2. **Generator tools** — read the spec, validate it, and emit outputs (RTL, C
   header, docs). TCL tool API on top, Python engine underneath.
3. **Methodology layer (the star)** — spec validation (a "lint" for the register
   spec), a generation manifest/report, and multi-output **consistency gating**
   ("are the checked-in generated files stale vs the spec?").
4. **Orchestration / CI** — a top-level `make` front door + GitHub Actions.

### Tech stack (keep it)
- **Make** — the single front door (`make rtl`, `make header`, `make all`).
- **TCL** — the tool command API + run scripts (mimics real EDA tools; preferred
  qual for the role).
- **Python** — the spec parser, validator, and generators.

### Important scoping decisions
- **Input format:** start with a simple **YAML** register spec (easy to read and
  parse). Real tools use **SystemRDL**; note that in the docs. A *stretch* phase
  adds a light mini-RDL text parser so I get a taste of the real syntax. Do **not**
  build a full SystemRDL parser.
- **Generation:** start with plain Python string templates (a concept I already
  know); optionally refactor to **Jinja2** later (what real generators use), with
  explanation.
- **Bus protocol:** generate an **APB** register-block interface (the simplest
  standard register bus — good for learning).

---

## 3. Repo layout (build toward this)

```
rdl2rtl-flow/
  spec/           register spec(s) — the single source of truth (YAML to start)
  tools/
    reggen/       generator: reggen.tcl (TCL API) + reggen_engine.py + templates/
  flow/
    run/          designer-facing TCL run scripts
    (validator, consistency check, reporting added in later phases)
  gen/            GENERATED outputs (rtl/, include/, docs/) — checked in, but
                  regenerated and consistency-checked
  config/         project config (which spec, which outputs)   (Phase 4+)
  docs/
    SPEC.md       this file
    HANDOFF.md    living "current state / how to resume" doc
    sessions/     one log per work session
    notes/        beginner-friendly learning notes, by concept
  Makefile        top-level entry point
  .gitignore
  README.md
```

---

## 4. Documentation system (MAINTAIN THIS EVERY SESSION — non-negotiable)

As important to me as the code. I want to resume instantly weeks later or hand off
to a fresh session, and reread a learning trail before interviews.

### 4a. `docs/HANDOFF.md` — living state doc (update at the END of every session)
```markdown
# HANDOFF
_Last updated: <date> (end of Session NN)_

## Where we are
- Current phase: <e.g. Phase 1 — validation>
- Status: <one line>

## What works right now
- <e.g. `make rtl` generates gen/rtl/<block>.sv from spec/<block>.yaml>

## How to resume (do this first)
1. <exact commands to verify the flow still works>
2. <the next concrete task>

## Next up
- <next 1–3 tasks in priority order>

## Open questions / decisions for the user
- <anything you need me to decide>
```

### 4b. `docs/sessions/session-NN.md` — per-session log (new file each session)
```markdown
# Session NN — <short title>
_Date: <date>_

## Goal for this session
## What we did
## Commands run (so I can reproduce)
## Decisions made (and why)
## Problems hit & how we solved them
## What I learned (plain language)
## Capstone reflection — how I'd explain this in an interview
## Next session should start with
```

### 4c. `docs/notes/<concept>.md` — beginner-friendly learning notes
Write/extend when a concept appears. Each note answers: *What is it? Why does it
exist? What problem does it solve? What would I say in an interview?* Expected
notes over the project:
- `make-basics.md`, `tcl-basics.md`
- `registers-and-csrs.md`, `systemrdl-intro.md`, `apb-basics.md`
- `code-generation.md`, `access-types.md`, `spec-validation.md`
- `single-source-of-truth.md`, `consistency-gating.md`

---

## 5. How to work (cadence)

- **Work ONE phase per session.** Build it, make it runnable, explain it, update
  all docs, then **STOP** and tell me how to resume. Don't run ahead.
- **Explain → confirm → implement, for every step.** Break each phase into small
  steps. For each: explain the concept and your plan, wait for my go-ahead,
  implement, then show me the result and what it means. Never batch code without
  explaining first.
- At the **start** of every session: read `docs/HANDOFF.md`, verify the flow still
  runs, state the plan, wait for my go-ahead.
- At the **end** of every session: ensure `make` still works, update `HANDOFF.md`,
  write the `session-NN.md` log, add/extend `notes/`.
- **Capstone mindset:** end each phase with an interview-framed reflection in the
  session log.
- Every phase ends with a **working, runnable flow** (never leave it broken).
- Keep changes coherent so I can `git commit` cleanly per phase.

---

## 6. Shared conventions

### Register spec format (YAML, the single source of truth)
A block has a base address and registers; a register has an offset, width, and
fields; a field has a bit position, width, access type, reset, and description.
Example to build toward:
```yaml
block: irq_ctrl
base_addr: 0x40001000
reg_width: 32
registers:
  - name: CTRL
    offset: 0x00
    fields:
      - { name: ENABLE,  bits: "0",   access: rw,  reset: 0, desc: "Global enable" }
      - { name: MODE,    bits: "2:1", access: rw,  reset: 0, desc: "Operating mode" }
  - name: STATUS
    offset: 0x04
    fields:
      - { name: BUSY,    bits: "0",   access: ro,  reset: 0, desc: "HW busy flag" }
      - { name: IRQ,     bits: "1",   access: w1c, reset: 0, desc: "Interrupt, write-1-clear" }
```

### Access types to support (build up over phases)
`rw` (SW read/write), `ro` (SW read-only, HW-driven status), `wo` (SW write-only),
`w1c` (SW writes 1 to clear; HW sets), `rclr` (read clears). Explain each in
`access-types.md` with the hardware behavior.

### Generated outputs (all from the one spec)
- **RTL**: `gen/rtl/<block>.sv` — APB register block: address decode, field
  storage flops, read mux, write logic honoring each access type.
- **C header**: `gen/include/<block>.h` — base address, register offsets, field
  mask/shift macros.
- **Docs**: `gen/docs/<block>.md` — a register-map table.

### Generation manifest / validation report (JSON)
Each run writes a small JSON manifest (what was generated, register/field counts)
and the validator writes a normalized report:
```json
{ "tool": "reggen", "block": "irq_ctrl",
  "violations": [ { "id": "OVERLAP_001", "rule": "FIELD_OVERLAP",
    "severity": "error", "reg": "CTRL", "message": "..." } ],
  "summary": { "error": 0, "warning": 0 } }
```

### Tool TCL API (mimics real EDA tools)
Expose TCL commands like `read_spec`, `set_output_dir`, `validate`,
`generate_rtl`, `generate_header`, `generate_docs`. TCL is the orchestration skin;
a Python engine does the work (`exec python3 ...`).

### Engines are simplified, on purpose
Light YAML parsing + templated generation. Do **not** build a full SystemRDL
parser. Header-comment every engine saying it's a learning mock and naming the
real tools it stands in for (PeakRDL, Semifore, Agnisys).

---

## 7. The roadmap (phases)

> **Start from a completely empty folder. Assume nothing exists yet.** Build the
> repo skeleton and `docs/` system first in Session 1.

### Phase 0 — Skeleton + spec + minimal RTL generation (end-to-end)
**Concepts first:** what registers/CSRs are; single source of truth; APB basics;
code generation; Make basics; TCL basics.
**Build:**
- `spec/irq_ctrl.yaml` — one block, ~2 registers, `rw` and `ro` fields only.
- `tools/reggen/reggen_engine.py` — parse YAML, generate an APB SystemVerilog
  register block (decode + rw storage + read mux), write `gen/rtl/<block>.sv`.
- `tools/reggen/reggen.tcl` — TCL API (`read_spec`, `set_output_dir`,
  `generate_rtl`) shelling out to the engine.
- `flow/run/gen.tcl` — designer run script.
- `Makefile` — `make rtl`, `make clean`, `make help`.
- `README.md`, `.gitignore` (ignore caches; decide whether `gen/` is committed —
  recommend committing it so consistency checks have a baseline).
**Verify:** `make rtl` produces a readable `gen/rtl/irq_ctrl.sv` with the right
registers/fields.
**Notes:** `make-basics`, `tcl-basics`, `registers-and-csrs`, `systemrdl-intro`,
`apb-basics`, `code-generation`.

### Phase 1 — More access types + spec validation
**Concept:** access-type semantics (the heart of register design) and
correctness-by-construction via validation.
**Build:**
- Support `wo`, `w1c`, `rclr` in the RTL generator (explain each behavior).
- A **validator** (lint for the spec): field bits within register width, no
  overlapping fields, unique names, reset fits field width, unique/aligned
  offsets. Emits the normalized JSON report; `make validate`.
**Verify:** a deliberately broken spec (overlapping fields) fails validation with a
clear message; the good spec passes.
**Notes:** `access-types`, `spec-validation`.

### Phase 2 — C header generation (multi-output from one source)
**Concept:** keeping firmware and hardware in sync from one source.
**Build:** generate `gen/include/<block>.h` (base addr, offsets, field MASK/SHIFT
macros); `make header`.
**Verify:** macros match the spec's bit positions exactly.
**Notes:** `single-source-of-truth`.

### Phase 3 — Documentation generation
**Concept:** docs as a generated artifact — never hand-maintain a register map.
**Build:** generate `gen/docs/<block>.md` (a per-register table: offset, field,
bits, access, reset, description); `make docs`.
**Verify:** the table reflects the spec.

### Phase 4 — Consistency gating + CI (the methodology star)
**Concept:** generated files go stale; the flow must detect drift and gate on it.
**Build:**
- `make check` — regenerate to a temp dir and **diff** against checked-in `gen/`;
  fail (non-zero exit) if they differ ("outputs are stale, re-run generation").
  Also run validation. `make all` runs generate + validate + check.
- `.github/workflows/ci.yml` — runs `make all` on push.
**Verify:** editing the spec without regenerating makes `make check` fail;
regenerating makes it pass; CI green.
**Notes:** `consistency-gating`, `ci`.

### Phase 5 (stretch) — mini-RDL front-end OR UVM model
**Pick one (ask me):**
- **A:** a light parser for a simplified SystemRDL-like text syntax (taste the real
  language) that feeds the same generator.
- **B:** generate a simple UVM register model (RAL) or a Python register model for
  verification.
**Notes:** `rdl-syntax` or `uvm-ral`.

### Capstone wrap-up — final report & demo
**Build:**
- `docs/CAPSTONE_REPORT.md` — the problem, the architecture (layer diagram), what
  each output is and why generation matters, the methodology decisions
  (validation, consistency gating), what I learned, what I'd extend.
- Tighten `README.md` into a portfolio front page (what it is, how to run, a
  sample of generated output).
- Confirm `make all` demos the whole flow in one command.
**Done when:** a stranger can clone, run one command, and understand it from the
README + capstone report alone.

---

## 8. Setup (pick your OS) — do once at the start of Session 1

Need Python 3, `make`, `tclsh`, and the `pyyaml` package.

**macOS:**
```bash
python3 --version            # or: brew install python
make --version               # Xcode CLT: xcode-select --install
tclsh <<< 'puts [info patchlevel]'   # if missing: brew install tcl-tk
python3 -m pip install pyyaml
```
**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-pip make tcl
tclsh <<< 'puts [info patchlevel]'
python3 -m pip install pyyaml
```
**Windows:** use **WSL** and follow the Linux steps.

(If `pyyaml` is a hassle, the spec can be JSON instead — stdlib only. Ask me.)
Confirm all tools print versions before building anything.

---

## 9. Definition of done (every phase)
- The new `make` target runs from a clean checkout.
- Generated output is correct and matches the spec.
- Code is commented for a beginner; new TCL/Make concepts are explained.
- `docs/HANDOFF.md` updated, `session-NN.md` written, relevant `notes/*.md`
  added/extended.
- Nothing is left broken.

---

## 10. Kickoff message (paste this into Claude Code)

> This is my **capstone project**, described in `SPEC.md` (please read it fully
> first). We are starting from a **completely empty folder — assume nothing exists
> yet.** I'm comfortable with Python but new to TCL, Make, and hardware register
> design, and I learn by doing.
>
> Most important: **explain everything before you implement it.** For each step,
> first tell me what we're building, the real-world concept behind it, and your
> plan — then wait for me to say "go" before writing any code. Treat this as a
> teaching loop, and explain each TCL and Make line, and each register concept,
> the first time it appears.
>
> For this first session: (1) walk me through the OS setup checks until Python,
> make, tclsh, and pyyaml all work; (2) explain, then create the repo skeleton and
> the `docs/` system (HANDOFF.md, sessions/, notes/); (3) build **Phase 0** only,
> step by step with explanation and my go-ahead before each piece — the YAML spec,
> the reggen engine that generates an APB SystemVerilog register block, the TCL
> tool API, the run script, and the Makefile; (4) run `make rtl` to prove it
> works; (5) write the Phase 0 learning notes, the session log, and the handoff.
> Then **stop** and tell me how to resume. Pause and ask me whenever there's a real
> decision.
