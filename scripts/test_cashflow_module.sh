#!/usr/bin/env bash
# scripts/test_cashflow_module.sh
# Purpose: Add a minimal, high-signal cashflow test and run it via the module harness.
# Usage:   bash scripts/test_cashflow_module.sh
# Notes:   Keeps to LKR tariff as canonical; verifies JSONL/CSV results + annual CSV header.

set -Eeuo pipefail
trap 'echo "ERR at line $LINENO" >&2' ERR

ROOT_HINT="dutchbay_v13"
HARNESS="scripts/test_one_module.sh"
TEST_FILE="tests/test_cashflow.py"

echo "→ Verifying repository root..."
[[ -d "$ROOT_HINT" && -d "scripts" ]] || { echo "Run from repo root (missing $ROOT_HINT/ or scripts/)"; exit 1; }

echo "→ Ensuring test directory exists..."
mkdir -p tests

if [[ -f "$TEST_FILE" ]]; then
  echo "↷ $TEST_FILE already exists; will overwrite to the canonical smoke test."
fi

echo "→ Writing $TEST_FILE"
cat > "$TEST_FILE" <<'PY'
from pathlib import Path
from glob import glob
from dutchbay_v13.scenario_runner import run_dir

def test_cashflow_scenario_smoke(tmp_path: Path):
    scen = tmp_path / "scen"; scen.mkdir()
    out  = tmp_path / "out";  out.mkdir()

    # Canonical LKR tariff key; no USD artifacts.
    (scen / "cf.yaml").write_text("tariff_lkr_per_kwh: 36.0\n", encoding="utf-8")

    rc = run_dir(str(scen), str(out), mode="irr", format="both", save_annual=True)
    assert rc == 0

    # Results (JSONL + CSV)
    j = glob(str(out / "scenario_cf_results_*.jsonl"))
    c = glob(str(out / "scenario_cf_results_*.csv"))
    assert len(j) == 1 and len(c) == 1

    # Annual CSV must exist and use the runner's header
    a = glob(str(out / "scenario_cf_annual_*.csv"))
    assert len(a) == 1
    head = Path(a[0]).read_text(encoding="utf-8").splitlines()[0]
    assert head.strip() == "year,cashflow"

    # JSONL content sanity
    line = Path(j[0]).read_text(encoding="utf-8").splitlines()[0]
    import json
    row = json.loads(line)
    for key in ("name", "mode", "equity_irr", "project_irr", "npv"):
        assert key in row
    assert row["name"] == "cf"
PY

echo "→ Running tests for module: cashflow"
if [[ -x "$HARNESS" ]]; then
  bash "$HARNESS" cashflow
else
  echo "↷ $HARNESS not found; falling back to direct pytest."
  python - <<'PY'
import sys, subprocess
cmd = [
  sys.executable, "-m", "pytest", "-q", "tests/test_cashflow.py",
  "--override-ini=addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"
]
raise SystemExit(subprocess.call(cmd))
PY
fi

echo "✓ cashflow smoke test completed."
echo "   (Optional) git add/commit:"
echo "     git add $TEST_FILE && git commit -m 'tests: add cashflow scenario smoke (JSONL/CSV + annual header)'"

