# =============================================================================
# gen.tcl — Designer run script: generate all outputs for irq_ctrl
#
# LEARNING NOTE — Two levels of TCL scripts:
#   1. tools/reggen/reggen.tcl  — the TOOL API (don't edit; ships with the tool)
#   2. flow/run/gen.tcl         — the RUN SCRIPT (project-specific; you write this)
#
#   This mirrors real EDA flows. For synthesis you might have:
#     tools/dc/dc_setup.tcl     ← tool setup (don't touch)
#     flow/syn/run_syn.tcl      ← your project's synthesis run script
#
# Usage:
#   tclsh flow/run/gen.tcl [--output rtl|header|docs|all]
#   (The Makefile calls this for you — you don't usually run it directly.)
# =============================================================================

# ---------------------------------------------------------------------------
# Locate project root — so this script works regardless of where it's run from
# ---------------------------------------------------------------------------
# LEARNING NOTE: [info script] = path to this file.
#   We go up two directories (run/ -> flow/ -> project root) to get the root.
#   [file normalize] resolves ".." and symlinks to a clean absolute path.
set script_dir  [file dirname [file normalize [info script]]]
set project_root [file normalize [file join $script_dir "../.."]]

# ---------------------------------------------------------------------------
# Parse --output argument (default: rtl)
# ---------------------------------------------------------------------------
# LEARNING NOTE: $argv is TCL's list of command-line arguments (like sys.argv[1:]).
#   We look for "--output <value>" in it. lsearch finds the index of a value
#   in a list; lindex retrieves the element at a given index.
set output_type "rtl"
set idx [lsearch $argv "--output"]
if {$idx >= 0} {
    set output_type [lindex $argv [expr {$idx + 1}]]
}

# ---------------------------------------------------------------------------
# Source the tool API — this loads all the reggen procs into our session
# ---------------------------------------------------------------------------
# LEARNING NOTE: "source" in TCL is like Python's "import" or shell's ".".
#   It reads and executes the named file in the current interpreter,
#   making all its procs available.
source [file join $project_root "tools/reggen/reggen.tcl"]

# ---------------------------------------------------------------------------
# Run the flow
# ---------------------------------------------------------------------------
puts "\[flow\] Starting reggen run (output=$output_type)"
puts "\[flow\] Project root: $project_root"

# Step 1: Tell the tool which spec to use
read_spec [file join $project_root "spec/irq_ctrl.yaml"]

# Step 2: Tell the tool where to put generated files
# LEARNING NOTE: --outdir lets the caller override the output directory.
#   "make check" uses this to generate into a temp dir (gen_check/) so it can
#   diff that against the committed gen/ without clobbering anything.
#   [file normalize] resolves relative paths against CWD (the project root
#   when called from Make), giving us a clean absolute path regardless.
set out_dir [file join $project_root "gen"]
set idx2 [lsearch $argv "--outdir"]
if {$idx2 >= 0} {
    set out_dir [file normalize [lindex $argv [expr {$idx2 + 1}]]]
}
set_output_dir $out_dir

# Step 3: Generate the requested output(s)
# LEARNING NOTE — Phase 1 added `validate` here. In a real flow you'd also
# call validate_spec at the top of the "all" path to gate generation behind
# linting; we instead let the Makefile orchestrate that ordering (see Makefile
# "all" target). Both approaches are valid.
switch $output_type {
    "validate" { validate_spec  }
    "rtl"      { generate_rtl    }
    "header"   { generate_header }
    "docs"     { generate_docs   }
    "lint"     { lint_rtl        }
    "all"      { validate_spec; generate_rtl; generate_header; generate_docs }
    default    {
        error "Unknown output type: $output_type. Use validate, rtl, header, docs, lint, or all."
    }
}

puts "\[flow\] Run complete."
