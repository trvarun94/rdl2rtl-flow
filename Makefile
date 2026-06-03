# =============================================================================
# Makefile — rdl2rtl-flow top-level entry point
#
# LEARNING NOTE — Make fundamentals:
#   A Makefile has three building blocks:
#
#   1. VARIABLES: defined at the top, referenced with $(VAR_NAME)
#      Example:  TCLSH := tclsh
#
#   2. RULES:    target: dependencies
#                    recipe (shell command — MUST be indented with a real TAB)
#
#   3. PHONY targets: targets that don't produce a file — they're just actions.
#      Declaring them .PHONY prevents conflicts if a file with that name exists.
#
#   The default target (first one in the file) runs when you type just "make".
#   We make "help" the default so a new user always sees instructions first.
#
# LEARNING NOTE — Why Make in EDA?
#   Every EDA flow uses Make (or a similar tool: CMake, SCons, Bazel) as a
#   front door. It gives a consistent interface:
#     make rtl    make sim    make syn    make clean
#   A new engineer on the team runs "make help" and knows everything they need.
# =============================================================================

# ---------------------------------------------------------------------------
# Variables — change these to adapt the flow to a different project
# ---------------------------------------------------------------------------

TCLSH       := tclsh
SPEC        := spec/irq_ctrl.yaml
GEN_DIR     := gen
CHECK_DIR   := gen_check
RUN_SCRIPT  := flow/run/gen.tcl

# ---------------------------------------------------------------------------
# Default target: show help
# LEARNING NOTE: Declaring "help" first makes it the default (runs on bare "make").
#   This is a common Makefile idiom — never let the default target do something
#   destructive or unexpected.
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo ""
	@echo "rdl2rtl-flow — Register Generation Flow"
	@echo "========================================"
	@echo ""
	@echo "  make rtl       Generate SystemVerilog APB register block"
	@echo "  make header    Generate C firmware header  (Phase 2)"
	@echo "  make docs      Generate register-map docs  (Phase 3)"
	@echo "  make validate  Lint the register spec       (Phase 1)"
	@echo "  make lint      RTL lint gate (Verilator --lint-only)"
	@echo "  make sim       Functional simulation (iverilog + vvp testbench)"
	@echo "  make manifest  End-of-run manifest snapshot (scans gen/)"
	@echo "  make check     Consistency gate: are gen/ files up to date? (Phase 4)"
	@echo "  make all       validate + rtl + header + docs + lint + sim + manifest + check (full flow)"
	@echo "  make clean     Remove all generated outputs"
	@echo "  make help      Show this message"
	@echo ""
	@echo "Spec: $(SPEC)"
	@echo "Out:  $(GEN_DIR)/"
	@echo ""

# ---------------------------------------------------------------------------
# make rtl — generate the SystemVerilog register block
# LEARNING NOTE: The recipe calls tclsh with our run script, passing --output rtl.
#   tclsh is the TCL interpreter (like python3 for Python).
#   The run script sources reggen.tcl and calls generate_rtl.
# ---------------------------------------------------------------------------

.PHONY: rtl
rtl:
	@echo "[make] Running RTL generation..."
	$(TCLSH) $(RUN_SCRIPT) --output rtl
	@echo "[make] Done. See $(GEN_DIR)/rtl/"

# ---------------------------------------------------------------------------
# make header — generate the C firmware header (implemented in Phase 2)
# ---------------------------------------------------------------------------

.PHONY: header
header:
	@echo "[make] Running header generation..."
	$(TCLSH) $(RUN_SCRIPT) --output header
	@echo "[make] Done. See $(GEN_DIR)/include/"

# ---------------------------------------------------------------------------
# make docs — generate register-map documentation (implemented in Phase 3)
# ---------------------------------------------------------------------------

.PHONY: docs
docs:
	@echo "[make] Running docs generation..."
	$(TCLSH) $(RUN_SCRIPT) --output docs
	@echo "[make] Done. See $(GEN_DIR)/docs/"

# ---------------------------------------------------------------------------
# make validate — lint the register spec (Phase 1)
# LEARNING NOTE: Like `make rtl`, this calls tclsh with the run script. The
#   TCL `validate_spec` command shells out to reggen_validator.py. If the
#   validator finds errors, tclsh exits non-zero and Make aborts the build —
#   the `all` target uses this to gate generation on a clean spec.
# ---------------------------------------------------------------------------

.PHONY: validate
validate:
	@echo "[make] Running spec validation..."
	$(TCLSH) $(RUN_SCRIPT) --output validate
	@echo "[make] Done. See $(GEN_DIR)/validation_report.json"

# ---------------------------------------------------------------------------
# make lint — RTL lint gate
#
# LEARNING NOTE — what lint is and isn't:
#   Lint is STATIC analysis — Verilator reads the .sv file and checks for
#   structural problems (width mismatches, undriven nets, etc.) without
#   simulating a single clock cycle. No testbench needed.
#
#   In a real flow, lint runs immediately after RTL generation and gates
#   synthesis. If lint is red, synthesis doesn't see the file.
#
#   Why Verilator and not a commercial linter?
#   Spyglass (Synopsys) and Questa Lint (Siemens) are the industry tools;
#   Verilator is the best open-source equivalent and is used by real projects
#   (OpenTitan, lowRISC, etc.). Same concept, no license required.
# ---------------------------------------------------------------------------

.PHONY: lint
lint:
	@echo "[make] Running RTL lint..."
	$(TCLSH) $(RUN_SCRIPT) --output lint
	@echo "[make] Done. See $(GEN_DIR)/lint_report.json"

# ---------------------------------------------------------------------------
# make sim — compile and run the functional testbench
#
# LEARNING NOTE — two-step simulation flow (iverilog + vvp):
#   iverilog compiles one or more .sv/.v source files into an intermediate
#   bytecode executable (gen/sim/irq_ctrl_sim). This step catches syntax and
#   elaboration errors (wrong port counts, undeclared signals).
#
#   vvp is the runtime that executes that bytecode, running the simulation
#   from time 0 until $finish or $fatal. $fatal exits with non-zero status.
#
#   In a real flow this step is replaced by VCS, Xcelium, or Questa, but the
#   split between compile and run is identical — "vlogan + vcs -R" (VCS) or
#   "xmvlog + xmsim" (Xcelium) are the commercial equivalents.
#
#   We delegate to TCL→Python (like make lint) so that gen/sim_report.json
#   is written with PASS *or* FAIL before Make exits — a stale PASS from a
#   previous run will never mask a current failure.
# ---------------------------------------------------------------------------

.PHONY: sim
sim: rtl
	@echo "[make] Running functional simulation..."
	$(TCLSH) $(RUN_SCRIPT) --output sim
	@echo "[make] Done. See $(GEN_DIR)/sim_report.json"

# ---------------------------------------------------------------------------
# make manifest — end-of-run audit snapshot
#
# LEARNING NOTE — why a dedicated manifest step:
#   The manifest is a summary of what's in gen/ — which RTL, header, and docs
#   files were produced, plus the lint result. In real EDA flows this is the
#   job of dedicated report commands (`report_design`, `report_qor`) that run
#   AFTER generation and synthesis, scanning the design database for a snapshot.
#   Keeping it as its own step means one owner, one source of truth — no
#   generator has to summarize any other generator's work.
# ---------------------------------------------------------------------------

.PHONY: manifest
manifest:
	@echo "[make] Building manifest..."
	$(TCLSH) $(RUN_SCRIPT) --output manifest
	@echo "[make] Done. See $(GEN_DIR)/irq_ctrl_manifest.json"

# ---------------------------------------------------------------------------
# make check — consistency gate (Phase 4)
#
# LEARNING NOTE — Multi-line Make recipes:
#   Each TAB-indented line in a recipe normally runs in its own shell subprocess.
#   A backslash (\) at the end of a line joins it with the next so the entire
#   block runs in ONE shell — that's how if/else/fi and "exit 1" work correctly
#   here. The @ prefix suppresses echoing and applies to the whole joined block.
#
# LEARNING NOTE — Why BSD diff uses -x, not --exclude:
#   macOS ships BSD diff; GNU diff (Linux/CI) uses --exclude=pattern.
#   The -x flag is understood by both, so we use it for portability.
#
# LEARNING NOTE — What this gate catches (spec/output drift):
#   A developer edits spec/irq_ctrl.yaml but forgets "make all" before
#   committing. The committed gen/ files are now stale — the RTL, header,
#   and docs no longer match the spec. This target re-generates everything
#   into a temp dir ($(CHECK_DIR)/) and diffs. If anything differs, it prints
#   the diff and exits non-zero so CI fails loudly on the pull request.
# ---------------------------------------------------------------------------

.PHONY: check
check:
	@echo "[make] Consistency check: re-generating into $(CHECK_DIR)/..."
	@rm -rf $(CHECK_DIR) && mkdir -p $(CHECK_DIR)
	@$(TCLSH) $(RUN_SCRIPT) --output all --outdir $(CHECK_DIR) > /dev/null
	@if diff -rq \
	        -x "*_manifest.json" \
	        -x "validation_report.json" \
	        -x "lint_report.json" \
	        -x "sim_report.json" \
	        -x "sim" \
	        $(GEN_DIR) $(CHECK_DIR) > /dev/null 2>&1; then \
	    echo "[make] check PASSED — gen/ is up to date."; \
	    rm -rf $(CHECK_DIR); \
	else \
	    echo "[make] check FAILED — gen/ is out of date. Re-run: make all"; \
	    diff -r \
	        -x "*_manifest.json" \
	        -x "validation_report.json" \
	        -x "lint_report.json" \
	        -x "sim_report.json" \
	        -x "sim" \
	        $(GEN_DIR) $(CHECK_DIR); \
	    rm -rf $(CHECK_DIR); \
	    exit 1; \
	fi

# ---------------------------------------------------------------------------
# make all — full flow: validate first, then generate, then check
# LEARNING NOTE: A target can depend on other targets.
#   The order here is intentional: VALIDATE comes first so a broken spec
#   stops the build before we waste time generating RTL/headers/docs from
#   a flawed source. Make stops on the first non-zero exit code, so the
#   gate is automatic.
# ---------------------------------------------------------------------------

.PHONY: all
all: validate rtl header docs lint sim manifest check
	@echo "[make] Full flow complete."

# ---------------------------------------------------------------------------
# make clean — remove generated outputs
# LEARNING NOTE: $(GEN_DIR)/rtl etc. are the directories we delete.
#   We keep the gen/ directory itself (it's checked in) but remove its contents.
#   The '-' prefix on a recipe line tells Make to ignore errors (e.g., dir
#   doesn't exist yet on a fresh checkout).
# ---------------------------------------------------------------------------

.PHONY: clean
clean:
	@echo "[make] Removing generated outputs..."
	-rm -rf $(GEN_DIR)/rtl
	-rm -rf $(GEN_DIR)/include
	-rm -rf $(GEN_DIR)/docs
	-rm -f  $(GEN_DIR)/*_manifest.json
	-rm -f  $(GEN_DIR)/validation_report.json
	-rm -f  $(GEN_DIR)/lint_report.json
	-rm -f  $(GEN_DIR)/sim_report.json
	-rm -rf $(GEN_DIR)/sim
	-rm -rf $(CHECK_DIR)
	@echo "[make] Clean complete."
