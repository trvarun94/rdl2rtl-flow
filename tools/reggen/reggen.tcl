# =============================================================================
# reggen.tcl — Register Generator TCL Tool API
#
# LEARNING NOTE — Why TCL?
#   Every major EDA tool (Synopsys DC, Cadence Genus, Mentor Questa) exposes a
#   TCL command API. Designers type commands like:
#       read_verilog foo.v
#       set_dont_touch [get_cells clk_buf*]
#       compile_ultra
#   Our tool follows the same pattern. This TCL file IS the "tool interface."
#   Underneath, it shells out to Python — TCL is the API skin, Python does
#   the real work. This is a common methodology pattern.
#
# LEARNING NOTE — How to source this file:
#   In your run script (or at a tclsh prompt), you do:
#       source tools/reggen/reggen.tcl
#   After that, all the procs below become available as commands.
#
# Procs (commands) exposed:
#   read_spec   <path>        — load the register spec (YAML)
#   set_output_dir <path>     — set where generated files go
#   validate_spec             — lint the spec (Phase 1)
#   generate_rtl              — generate the SystemVerilog APB block
#   generate_header           — generate the C firmware header (Phase 2)
#   generate_docs             — generate register-map documentation (Phase 3)
# =============================================================================

# ---------------------------------------------------------------------------
# Internal state — tool "session" variables
# ---------------------------------------------------------------------------
# LEARNING NOTE — TCL global variables:
#   TCL variable scope is per-proc. Variables set at the top level are global.
#   Inside a proc, you must say "global varname" to access a global.
#   We use globals here to hold the tool's state across command calls,
#   just like a real EDA tool holds state (e.g., after read_verilog, the
#   tool remembers which files were loaded).

set _reggen_spec_path  ""    ;# path to the YAML spec, set by read_spec
set _reggen_output_dir ""    ;# output directory, set by set_output_dir

# Find the directory this script lives in — engine.py is right next to it.
# LEARNING NOTE: [info script] returns the path of the currently-sourced file.
#   [file dirname ...] is TCL's equivalent of Python's os.path.dirname().
set _reggen_tool_dir [file dirname [info script]]

# ---------------------------------------------------------------------------
# proc read_spec
# ---------------------------------------------------------------------------
proc read_spec {spec_path} {
    # LEARNING NOTE: "global" makes the global variable visible inside this proc.
    global _reggen_spec_path

    # Check the file exists before accepting it
    if {![file exists $spec_path]} {
        # LEARNING NOTE: "error" in TCL raises an exception and stops the script,
        # similar to Python's "raise". The caller sees the message.
        error "read_spec: spec file not found: $spec_path"
    }
    set _reggen_spec_path $spec_path
    # LEARNING NOTE: "puts" prints to stdout. "\[reggen\]" is a literal bracket
    # (brackets are special in TCL — they denote command substitution, like $()).
    puts "\[reggen\] Spec loaded: $spec_path"
}

# ---------------------------------------------------------------------------
# proc set_output_dir
# ---------------------------------------------------------------------------
proc set_output_dir {outdir} {
    global _reggen_output_dir

    # Create the directory if it doesn't exist yet.
    # LEARNING NOTE: "file mkdir" is TCL's equivalent of Python's os.makedirs().
    #   The -p equivalent in TCL is that file mkdir already handles nested paths.
    file mkdir $outdir
    set _reggen_output_dir $outdir
    puts "\[reggen\] Output dir: $outdir"
}

# ---------------------------------------------------------------------------
# proc _run_engine  (internal helper — prefixed with _ by convention)
# ---------------------------------------------------------------------------
proc _run_engine {output_type} {
    global _reggen_spec_path _reggen_output_dir _reggen_tool_dir

    # Guard: require read_spec and set_output_dir to have been called first
    if {$_reggen_spec_path eq ""} {
        error "_run_engine: no spec loaded — call read_spec first"
    }
    if {$_reggen_output_dir eq ""} {
        error "_run_engine: no output dir set — call set_output_dir first"
    }

    set engine [file join $_reggen_tool_dir "reggen_engine.py"]

    # LEARNING NOTE: "exec" runs an external program and captures its output.
    # It's like Python's subprocess.check_output(). If the command exits non-zero,
    # TCL raises an error automatically — built-in failure gating.
    # The output is returned as a string, which we print with "puts".
    #
    # We build the command as a list (not a raw string) — this is the correct
    # TCL way to avoid word-splitting issues with paths that have spaces.
    set cmd [list python3 $engine \
                 --spec    $_reggen_spec_path \
                 --outdir  $_reggen_output_dir \
                 --output  $output_type]

    # LEARNING NOTE: {*}$cmd is TCL's "expand" operator (like Python's *args).
    # It spreads the list elements as individual arguments to exec.
    set output [exec {*}$cmd]
    puts $output
}

# ---------------------------------------------------------------------------
# proc validate_spec — Phase 1
# ---------------------------------------------------------------------------
# LEARNING NOTE: This is the TCL "command" the designer types in a real flow.
#   It mirrors how Synopsys DC exposes `check_design` or Cadence Genus exposes
#   `check_design -all`. Under the hood we shell out to a Python script that
#   does the actual work. If the validator exits non-zero, TCL's `exec` raises
#   an error automatically — so generation stops on validator failure.
proc validate_spec {} {
    global _reggen_spec_path _reggen_output_dir _reggen_tool_dir

    if {$_reggen_spec_path eq ""} {
        error "validate_spec: no spec loaded — call read_spec first"
    }
    if {$_reggen_output_dir eq ""} {
        error "validate_spec: no output dir set — call set_output_dir first"
    }

    set validator [file join $_reggen_tool_dir "reggen_validator.py"]
    set cmd [list python3 $validator \
                 --spec   $_reggen_spec_path \
                 --outdir $_reggen_output_dir]

    puts "\[reggen\] Validating spec..."
    # LEARNING NOTE: We tee the validator's stderr through to our stderr so the
    # designer sees per-error lines, not just the final PASS/FAIL summary.
    # `exec` will raise (non-zero exit) on validator failure — which is exactly
    # what we want for gating.
    if {[catch {exec {*}$cmd >@ stdout 2>@ stderr} err_msg]} {
        # Re-raise so the calling script (and make) sees a failure
        error "validate_spec: validator reported errors (see above)"
    }
    puts "\[reggen\] Validation complete."
}

# ---------------------------------------------------------------------------
# Public generation commands
# ---------------------------------------------------------------------------

proc generate_rtl {} {
    puts "\[reggen\] Generating RTL..."
    _run_engine rtl
    puts "\[reggen\] RTL generation complete."
}

proc generate_header {} {
    puts "\[reggen\] Generating C header..."
    _run_engine header
    puts "\[reggen\] Header generation complete."
}

proc generate_docs {} {
    puts "\[reggen\] Generating docs..."
    _run_engine docs
    puts "\[reggen\] Docs generation complete."
}
