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
	@echo "  make check     Consistency gate: are gen/ files up to date? (Phase 4)"
	@echo "  make all       generate + validate + check (full flow)"
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
# make check — consistency gate (implemented in Phase 4)
# ---------------------------------------------------------------------------

.PHONY: check
check:
	@echo "[make] Running consistency check..."
	@echo "[make] Consistency check not yet implemented (Phase 4)"
	@exit 0

# ---------------------------------------------------------------------------
# make all — full flow: validate first, then generate, then check
# LEARNING NOTE: A target can depend on other targets.
#   The order here is intentional: VALIDATE comes first so a broken spec
#   stops the build before we waste time generating RTL/headers/docs from
#   a flawed source. Make stops on the first non-zero exit code, so the
#   gate is automatic.
# ---------------------------------------------------------------------------

.PHONY: all
all: validate rtl header docs check
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
	@echo "[make] Clean complete."
