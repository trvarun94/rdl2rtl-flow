# Consistency Gating

## What it is

A consistency gate is a CI check that answers: **"Do the committed generated files
still match what the generator would produce from the current spec?"**

If they match — the repo is in sync and the check passes.
If they differ — someone edited the spec (or the generator) but forgot to re-run
code generation before committing. The gate fails loudly.

## Why generated files drift

In a real chip project the spec (`irq_ctrl.yaml`, or a `.rdl` file) is the source
of truth, but the generated outputs (`irq_ctrl.sv`, `irq_ctrl.h`, `irq_ctrl.md`)
are also checked into source control so that:

1. **Reviewers can see diffs in pull requests** — "the ENABLE field moved from
   bit 0 to bit 1" is visible in the RTL diff without running the tool.
2. **Consumers don't need the tool installed** — firmware engineers can `git clone`
   and use the header immediately.
3. **History is traceable** — `git log gen/include/irq_ctrl.h` tells you exactly
   when and why the API changed.

The downside: the spec and generated files can get out of sync.

## The gate mechanism (how we implement it)

```
make check
  1. mkdir gen_check/
  2. run generator into gen_check/  (same as make all, just a different outdir)
  3. diff gen/ vs gen_check/        (exclude files with timestamps: *_manifest.json)
  4. PASS → clean up gen_check/, exit 0
     FAIL → print the diff, clean up gen_check/, exit 1
```

Exit code 1 causes CI to mark the build as failed. The engineer is told:
> check FAILED — gen/ is out of date. Re-run: make all

## Real-world counterpart

Professional teams running SystemRDL compilers (Ordt, PeakRDL, IP-XACT) do exactly
this. The CI pipeline runs the compiler and diffs the outputs against committed files.
Some teams go further: the committed files are stored in a dedicated `gen/` branch
and the check job opens an automatic PR if they drift.

## Make concepts used here

| Concept | Meaning |
|---------|---------|
| `\` at line end | Joins adjacent recipe lines into one shell subprocess — required for `if/else/fi` and `exit 1` to work across multiple physical lines |
| `@` prefix | Suppresses echoing the command; applies to the whole `\`-joined block |
| `-x pattern` | BSD `diff` flag to exclude files matching a glob pattern from comparison |
| `> /dev/null 2>&1` | Redirect both stdout and stderr to /dev/null — suppress output when we only care about the exit code |

## The `--outdir` flag in gen.tcl

The check target passes `--outdir gen_check` to the run script so the generator
writes into the temp dir instead of the live `gen/`. The `--output` flag was already
there (Phase 0); `--outdir` is new in Phase 4. Both follow the same TCL arg-parsing
pattern: `lsearch` to find the flag's index, `lindex` to get the following value.
