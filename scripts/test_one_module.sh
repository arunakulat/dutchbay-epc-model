#!/usr/bin/env bash
set -euo pipefail

alias_name="${1:-}"
if [[ -z "$alias_name" ]]; then
  echo "usage: $0 <module-alias>" >&2
  echo "aliases: irr | cashflow | debt | scenario | scenarios | cli | optimize | optimization | sensitivity" >&2
  exit 2
fi

MODULE_IMPORT=""
TEST_FILES=()

case "$alias_name" in
  irr)
    MODULE_IMPORT="dutchbay_v13.finance.irr"
    TEST_FILES=(tests/test_irr.py tests/test_finance_irr_unit.py)
    ;;
  cashflow)
    MODULE_IMPORT="dutchbay_v13.finance.cashflow"
    TEST_FILES=(tests/test_cashflow.py)
    ;;
  debt)
    MODULE_IMPORT="dutchbay_v13.finance.debt"
    TEST_FILES=(tests/test_debt_yaml_exposed.py)
    ;;
  scenario|scenarios)
    MODULE_IMPORT="dutchbay_v13.scenario_runner"
    TEST_FILES=(tests/test_scenarios.py tests/test_scenarios_jsonl_and_validator.py)
    ;;
  cli)
    MODULE_IMPORT="dutchbay_v13.cli"
    TEST_FILES=(tests/test_cli.py tests/test_cli_unittest.py tests/test_cli_help.py tests/test_cli_modes_smoke.py tests/test_cli_dead_smokes.py tests/test_cli_format_flag.py)
    ;;
  optimize|optimization)
    MODULE_IMPORT="dutchbay_v13.optimization"
    TEST_FILES=(tests/test_optimize_pareto_and_tornado_export.py tests/test_utopia_and_report.py)
    ;;
  sensitivity)
    MODULE_IMPORT="dutchbay_v13.sensitivity"
    TEST_FILES=(tests/test_tornado_flags.py tests/test_optimize_pareto_and_tornado_export.py)
    ;;
  *)
    echo "unknown alias: $alias_name" >&2
    exit 2
    ;;
esac

echo "→ Module alias '${alias_name}' → ${MODULE_IMPORT}"
echo "→ Running tests:"
printf '   %s\n' "${TEST_FILES[@]}"

# keep the module-by-module loop flexible; relax coverage gate for focused runs
pytest -q --cov="${MODULE_IMPORT}" --cov-fail-under=1 "${TEST_FILES[@]}"
