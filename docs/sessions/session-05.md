# Session 05 — Phase 4: Consistency Gating

_Date: 2026-05-31_

## What we built

`make check` — a consistency gate that re-generates all outputs into a temp dir
(`gen_check/`) and diffs them against the committed `gen/` files. Fails loudly with
a visible diff if anything differs.

## Files changed

| File | Change |
|------|--------|
| `Makefile` | Added `CHECK_DIR := gen_check` variable; replaced stub `check` target with real diff logic; added `gen_check/` removal to `clean` |
| `flow/run/gen.tcl` | Added `--outdir` argument parsing so the generator can be pointed at any directory |
| `docs/notes/consistency-gating.md` | New concept note: what drift is, why gen files are checked in, the gate mechanism, real-world counterpart |

## What we proved

Verified both sides of the gate:
- `make all` on a clean repo → `check PASSED`
- Manually appended `// drift-test` to `gen/rtl/irq_ctrl.sv` → `check FAILED` with diff printed, exit non-zero
- Ran `make rtl` to restore → `make check` passed again

## Key concepts introduced this session

**Multi-line Make recipes** — `\` at line end joins lines into one shell subprocess,
which is required for `if/else/fi` and `exit 1` to work correctly.

**BSD vs GNU `diff`** — macOS ships BSD diff, which uses `-x pattern` to exclude
files; GNU diff (Linux/CI) uses `--exclude=pattern`. Using `-x` keeps the Makefile
portable.

**`--outdir` flag in gen.tcl** — uses the same `lsearch`/`lindex` arg-parsing
pattern introduced in Phase 0 for `--output`. `file normalize` turns a relative
path from the caller into an absolute one so the generator always writes to the
right place.

## Interview-framed reflection

> **Q: Why check generated files into source control at all? Couldn't you just
> always regenerate?**

Checked-in generated files let reviewers see the impact of a spec change in a PR
diff without running any tools. Firmware engineers can consume headers from a plain
`git clone`. And `git log` on `gen/include/irq_ctrl.h` gives you a precise history
of when the firmware API changed and why — that's harder to reconstruct from spec
history alone. The tradeoff is exactly what `make check` solves: enforcing that the
committed outputs never silently drift from the spec.

## State at end of session

All four phases complete. `make all` runs validate → rtl → header → docs → check,
and every step is real (no stubs). See `docs/HANDOFF.md` for the full picture.
