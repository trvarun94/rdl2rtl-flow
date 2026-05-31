# TCL basics (just what you need for this project)

## What is TCL?
**T**ool **C**ommand **L**anguage — a small scripting language from the 1980s
that became the universal command/extension language for EDA tools. Every
major EDA tool exposes a TCL interface:
- Synopsys Design Compiler: `read_verilog`, `compile_ultra`, `report_timing`
- Cadence Genus / Innovus: similar TCL command set
- Mentor / Siemens Questa: `vsim`, `run`, `add wave`

If you want to be a methodology engineer, you write TCL. A lot.

## Why TCL (and not Python)?
Mostly historical: TCL was the obvious extension language in the early 90s
when these tools were built. Now it's locked in by inertia and by enormous
existing codebases. You don't have to love it — you have to read and write
it fluently.

## Syntax that surprises Python programmers

### Everything is a string
```tcl
set x 5            ;# x is the STRING "5" (TCL types are strings)
puts $x            ;# prints 5
```

### Brackets are command substitution (like $() in bash)
```tcl
set today [clock format [clock seconds] -format %Y-%m-%d]
#         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#         This whole thing runs and substitutes its return value.
```

### Braces are deferred evaluation (like a quoted block)
```tcl
proc add {a b} { return [expr {$a + $b}] }
#         ^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#         args   body — braces mean "don't evaluate yet"
```

### Variables in proc are local — `global` makes them visible
```tcl
set count 0
proc bump {} {
    global count        ;# without this, $count is undefined inside the proc
    set count [expr {$count + 1}]
}
```

### `exec` runs an external program
```tcl
set out [exec ls -la]    ;# captures the output as a string
```
If the program exits non-zero, TCL raises an error — that's free failure
gating in scripts.

## What we use in this project
- `proc name {args} { body }` — define commands
- `global varname` — share state across procs (our tool state)
- `set var value` / `$var` — set / read variables
- `exec python3 ... ` — shell out to the Python engine
- `puts "text"` — print
- `source path` — load another TCL file (like Python `import`)
- `file dirname` / `file join` / `file normalize` — path manipulation
- `[info script]` — path of the currently-running script
- `case $val { pattern { body } default { body } }` — pattern dispatch
- `lsearch` / `lindex` — list operations (for parsing `$argv`)
- `error "msg"` — raise an error and stop

## The two-level TCL pattern we use
1. **`tools/reggen/reggen.tcl`** — the **tool API** (commands like
   `read_spec`, `generate_rtl`). Stable; doesn't know about any project.
2. **`flow/run/gen.tcl`** — the **run script**. Sources the tool API and
   calls the commands with project-specific paths.

This is exactly how Synopsys DC is used in real flows:
- `tools/dc/dc_setup.tcl` (don't touch)
- `flow/syn/run_syn.tcl` (you write this)

## Interview-ready one-liner
> "TCL is the universal command language for EDA tools. I expose register
> generation as a TCL API — `read_spec`, `set_output_dir`, `generate_rtl` —
> backed by a Python engine. Designers write a TCL run script just like they
> would for any synthesis or simulation tool."
