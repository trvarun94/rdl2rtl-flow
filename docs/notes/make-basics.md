# Make basics (just what you need for this project)

## What is Make?
A 1970s build tool that's still the universal front door in EDA, OS kernels,
and many open-source projects. It reads a `Makefile`, figures out what's out
of date, and runs the shell commands to bring things up to date.

In EDA specifically: every flow you've ever heard of (synthesis, simulation,
P&R) is usually wrapped in `make`. New engineers run `make help` on day one
and discover the whole flow.

## The three building blocks
```make
VAR := value                    # 1. Variable

target: dep1 dep2               # 2. Rule:  target depends on dep1, dep2
	command1                    # 3. Recipe (TAB-indented, not spaces!)
	command2

.PHONY: target                  # 4. Phony: this target is an action,
                                #    not a file Make should look for
```

## Three things that bite new users
1. **Tabs, not spaces.** The recipe MUST start with a real tab character.
   Spaces give a cryptic "missing separator" error.
2. **One shell per line.** Each recipe line runs in its own subshell. To chain
   commands, use `&&` or wrap them on one logical line with backslashes.
3. **`@` silences command echo.** Default behavior is to print the command
   before running. `@echo "hi"` prints just `hi`, not `echo "hi"` then `hi`.

## What we use in this project
```make
TCLSH := tclsh                  # Variable holding the TCL interpreter
SPEC  := spec/irq_ctrl.yaml     # Variable for the spec path

.PHONY: rtl                     # rtl is an action, not a file
rtl:
	$(TCLSH) flow/run/gen.tcl --output rtl
```

That's the whole pattern. Each target (`rtl`, `header`, `docs`, `clean`,
`help`) is a phony action that runs one shell command.

## Why `help` is the default
Convention: declare `help` first. Then bare `make` shows the menu instead of
doing something unexpected. We use this in our Makefile.

## Interview-ready one-liner
> "Make is the front door I expose to designers. They never need to know that
> underneath I shell out to tclsh and a Python engine — they type `make rtl`
> and it works. That's methodology: hide the complexity behind a clean API."
