#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "→ Phase C: finance IRR & debt…"
bash "$ROOT/scripts/test_finance_irr_debt.sh" || true

echo "→ Phase C: scenario matrix + validator…"
pytest -q tests/test_scenarios_jsonl_and_validator.py \
  --override-ini="addopts=-q --cov=dutchbay_v13.scenario_runner --cov-report=term-missing --cov-fail-under=1" || true

echo "→ Phase C: CLI scenarios smoke…"
pytest -q tests/test_cli_scenarios_more.py \
  --override-ini="addopts=-q --cov=dutchbay_v13.cli --cov-report=term-missing --cov-fail-under=1" || true

echo "→ Phase C: heavy modules (MC/Sens/Opt/Metrics)…"
bash "$ROOT/scripts/run_heavy_with_shims.sh" || true

echo "→ Phase C: reporting import + smokes…"
bash "$ROOT/scripts/run_next_modules_suite.sh" || true

echo "→ Phase C: reporting CLI stub smoke…"
bash "$ROOT/scripts/run_reporting_cli_smoke.sh" || true

echo "→ Phase C: charts smoke…"
bash "$ROOT/scripts/add_charts_smoke_and_run.sh" || true

echo "✓ Phase C complete."

