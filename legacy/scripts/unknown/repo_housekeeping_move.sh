#!/usr/bin/env bash
set -euo pipefail

echo "Repo root: $(pwd)"

# --- helper ---

move_if_exists() {
  local src="$1"
  local dest="$2"
  if [ -f "$src" ]; then
    local dest_dir
    dest_dir="$(dirname "$dest")"
    mkdir -p "$dest_dir"
    echo "Moving $src -> $dest"
    mv "$src" "$dest"
  else
    echo "Skipping $src (not found)"
  fi
}

# --- 1. Workflows -> archive ---

mkdir -p ci/archive

move_if_exists ".github/workflows/ci.yml" "ci/archive/ci_full_matrix.yml"
move_if_exists ".github/workflows/ci_Tox.yml" "ci/archive/ci_tox_legacy.yml"

# --- 2. Docs -> docs/ tree ---

mkdir -p docs/go-with-the-flow docs/roadmap docs/tech-debt docs/tech-debt/archive

# Go-with-the-Flow docs
move_if_exists "GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md" \
  "docs/go-with-the-flow/GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md"
move_if_exists "GO_WITH_THE_FLOW_INTEGRATION_GUIDE.md" \
  "docs/go-with-the-flow/GO_WITH_THE_FLOW_INTEGRATION_GUIDE.md"
move_if_exists "GO_WITH_THE_FLOW_AI_RESPONSE_NOTES.md" \
  "docs/go-with-the-flow/GO_WITH_THE_FLOW_AI_RESPONSE_NOTES.md"

# Roadmap / sprint notes
move_if_exists "SPRINT_4_ROADMAP.md" \
  "docs/roadmap/SPRINT_4_ROADMAP.md"
move_if_exists "PHASE_3_CLOSURE_SUMMARY.md" \
  "docs/roadmap/PHASE_3_CLOSURE_SUMMARY.md"
move_if_exists "DutchBay_EPC_Model_Priority_Stack_20251122.md" \
  "docs/roadmap/DutchBay_EPC_Model_Priority_Stack_20251122.md"
move_if_exists "DutchBay_EPC_Model_TEST_Matrix_Design_Notes.md" \
  "docs/roadmap/DutchBay_EPC_Model_TEST_Matrix_Design_Notes.md"

# Tech-debt / context docs
move_if_exists "DEBT_CASHFLOW_IDC_REGRESSION_CONTEXT.md" \
  "docs/tech-debt/DEBT_CASHFLOW_IDC_REGRESSION_CONTEXT.md"
move_if_exists "MONTE_CARLO_AND_SENSITIVITY_CONSOLIDATED_NOTES.md" \
  "docs/tech-debt/MONTE_CARLO_AND_SENSITIVITY_CONSOLIDATED_NOTES.md"
move_if_exists "TESTING_SAFETY_NETS_CONTEXT.md" \
  "docs/tech-debt/TESTING_SAFETY_NETS_CONTEXT.md"
move_if_exists "TRACKING_DEFERRED_VIOLATIONS_AND_TECH_DEBT.md" \
  "docs/tech-debt/TRACKING_DEFERRED_VIOLATIONS_AND_TECH_DEBT.md"
move_if_exists "deferred-violations-registry.md" \
  "docs/tech-debt/deferred-violations-registry.md"

# --- 3. Devtools / fixer scripts ---

mkdir -p scripts/devtools scripts/devtools/fixers

# General devtools
move_if_exists "file_editor.py" \
  "scripts/devtools/file_editor.py"
move_if_exists "gather-violations.py" \
  "scripts/devtools/gather-violations.py"
move_if_exists "gather-sensitivity-tools.py" \
  "scripts/devtools/gather-sensitivity-tools.py"
move_if_exists "apply_fixes.py" \
  "scripts/devtools/apply_fixes.py"
move_if_exists "fx_config_generator.py" \
  "scripts/devtools/fx_config_generator.py"
move_if_exists "deferred-violations-registry.py" \
  "scripts/devtools/deferred-violations-registry.py"

# One-shot fixer helpers
move_if_exists "add_tr_noqa.py" \
  "scripts/devtools/fixers/add_tr_noqa.py"
move_if_exists "fix-all-tr-usage.py" \
  "scripts/devtools/fixers/fix-all-tr-usage.py"
move_if_exists "fix-b007-usage.py" \
  "scripts/devtools/fixers/fix-b007-usage.py"
move_if_exists "fix_fx_processor_e501.py" \
  "scripts/devtools/fixers/fix_fx_processor_e501.py"
move_if_exists "fix_singleton_montecarlo_e501.py" \
  "scripts/devtools/fixers/fix_singleton_montecarlo_e501.py"
move_if_exists "fix_singleton_sensitivity_tools_e501.py" \
  "scripts/devtools/fixers/fix_singleton_sensitivity_tools_e501.py"
move_if_exists "fix_singletons_batch_e501.py" \
  "scripts/devtools/fixers/fix_singletons_batch_e501.py"
move_if_exists "fix_singletons_schema_guard_e501.py" \
  "scripts/devtools/fixers/fix_singletons_schema_guard_e501.py"
move_if_exists "fix_singletons_scenario_analytics_e501.py" \
  "scripts/devtools/fixers/fix_singletons_scenario_analytics_e501.py"
move_if_exists "fix_singletons_stochastic_e501.py" \
  "scripts/devtools/fixers/fix_singletons_stochastic_e501.py"
move_if_exists "fix_singletons_validation_e501.py" \
  "scripts/devtools/fixers/fix_singletons_validation_e501.py"
move_if_exists "revert-tr-fix.py" \
  "scripts/devtools/fixers/revert-tr-fix.py"

# --- 4. Scratch / context artefacts -> archived tech-debt ---

move_if_exists "analytics_singles_e501_context.txt" \
  "docs/tech-debt/archive/analytics_singles_e501_context.txt"
move_if_exists "finance_e501_context.txt" \
  "docs/tech-debt/archive/finance_e501_context.txt"
move_if_exists "sensitivity_tools_e501_context.txt" \
  "docs/tech-debt/archive/sensitivity_tools_e501_context.txt"
move_if_exists "pre-commit-output-2025-11-27.txt" \
  "docs/tech-debt/archive/pre-commit-output-2025-11-27.txt"

echo "Done."
