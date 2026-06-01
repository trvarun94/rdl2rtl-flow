# Spec Validation — Lint Before Generate

## What and why

`reggen_validator.py` is a **lint pass on the YAML register spec**. It runs
*before* any code generation. If it finds errors, generation is blocked.

This is the same pattern as:
- **`gcc -Wall`** — catches code smells before producing a binary
- **`verilator --lint-only`** / **SpyGlass** — RTL static checking before sim
- **Synopsys DC `check_design`** — design rule check before synthesis
- **PeakRDL `peakrdl validate`** — semantic checks on a SystemRDL spec

The principle: **fail at the earliest possible stage**. A spec bug caught by
the validator costs you 0.1 seconds. The same bug caught in simulation costs
30 minutes plus your concentration. The same bug caught in silicon costs a
respin.

## The flow

```
  spec/irq_ctrl.yaml
        │
        ▼
  ┌─────────────────────┐
  │ reggen_validator.py │  ──► gen/validation_report.json
  │ 6+1 checks          │
  └──────────┬──────────┘
             │
       PASS  │  FAIL (exit 1)
             │  ──► tclsh raises ──► make aborts
             ▼
  Generators run (rtl, header, docs)
```

## What it checks

| # | Check | Why it matters |
|---|---|---|
| 1 | Field bits within `reg_width` | Generated RTL accesses non-existent PWDATA bits — synthesis error |
| 2 | No overlapping fields in a register | Two fields write the same flop — race / undefined |
| 3 | Unique field names per register | Duplicate `logic` declarations → SV compile error |
| 4 | Reset value fits in field width | `2'd5` for a 1-bit field — SV warning + wrong reset |
| 5 | Unique register offsets | Two regs at same offset → write to one reads from the other |
| 6 | Offsets are bus-byte aligned | APB is 32-bit; unaligned breaks C struct layout |
| + | Access type ∈ {rw, ro, wo, w1c, rclr} | Engine wouldn't know what to generate |

## What it does NOT check (yet)

These checks exist in real-world validators and could be added later:

- **Reserved bits** — gaps between fields are fine, but real tools warn you so
  you can decide whether to call them "reserved" explicitly.
- **CSR naming conventions** — UPPER_SNAKE, no leading digits, no SV keywords
  (`reg`, `wire`, `module`, `case`, etc. — would conflict with the generated RTL).
- **Field reset consistency with access type** — e.g., `w1c` fields should
  typically reset to 0 (HW sets them later). A `w1c` with `reset: 1` is unusual.
- **Address gaps** — register at 0x00 followed by one at 0x100 might indicate
  a typo. Some tools warn; some don't.
- **Endianness / byte-strobe consistency** — APB doesn't use byte strobes, but
  AHB/AXI variants do. Multi-bit fields crossing byte boundaries need attention.

## How it's wired

Three layers, same pattern as `make rtl`:

```
  Makefile         ──►  flow/run/gen.tcl  ──►  tools/reggen/reggen.tcl
  (target)              (run script)            (TCL API)
                                                      │
                                                      └─► exec python3 reggen_validator.py
```

- `make validate` is the user-facing entry.
- `validate_spec` is the TCL command (mirrors `check_design` in DC, etc.).
- `reggen_validator.py` is the Python implementation.

If the Python script exits non-zero, TCL's `exec` raises an error, tclsh
exits non-zero, and Make aborts. **Failure propagates automatically through
every layer** — no hand-rolled gating logic needed.

## Output format — `gen/validation_report.json`

```json
{
  "tool":          "reggen_validator",
  "spec":          "spec/irq_ctrl.yaml",
  "status":        "PASS" | "FAIL",
  "error_count":   <n>,
  "warning_count": <n>,
  "errors":        [ "string", ... ],
  "warnings":      [ "string", ... ]
}
```

This JSON is consumable by CI dashboards, Phase 4's consistency checker, and
anyone who wants to diff "did the spec change in a way that introduced new
warnings?".

## Why a JSON report when stdout/stderr already prints?

- **Auditability**: PR reviewers can attach the report to the change.
- **Diffability**: tomorrow's report vs. yesterday's tells you "you fixed
  these errors but introduced these warnings."
- **Tool chaining**: other generators or dashboards can read it without
  parsing free-form text.

This is a recurring real-world pattern: every EDA stage emits a structured
"report" file alongside its primary artifact (RTL, header, gate-level netlist),
and downstream stages consume those reports.
