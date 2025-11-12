#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Low gate while iterating; includes *all* modules
cat > .coveragerc <<'COV'
[run]
branch = True
source = dutchbay_v13
[report]
fail_under = 20
COV

cat > pytest.ini <<'INI'
[pytest]
addopts = -q --cov=dutchbay_v13 --cov-config=.coveragerc --cov-report=term-missing
INI

PHASES=(
  "irr"
  "debt"
  "cashflow"
  "core"
  "scenario_runner"
  "validators"
  "cli"
  "__main__"
  "optimization"
  "sensitivity"
  "charts"
  "report"
  "api"
)

FROM="${1:-}"
start=0
if [[ -n "$FROM" ]]; then
  for i in "${!PHASES[@]}"; do
    if [[ "${PHASES[$i]}" == "$FROM" ]]; then start="$i"; break; fi
  done
fi

for ((i=start; i<${#PHASES[@]}; i++)); do
  phase="${PHASES[$i]}"
  echo
  echo "==================== Phase $((i+1))/${#PHASES[@]}: $phase ===================="
  bash scripts/test_one_module.sh "$phase" || {
    echo
    echo "✖ Stopped at phase '$phase'. Fix failures, then rerun:"
    echo "   bash scripts/test_all_stepwise.sh $phase"
    exit 1
  }
done

echo
echo "✅ All phases passed with the current gate (20%)."
echo "→ When green, raise coverage gate (e.g., 60/70/80) in .coveragerc:"
echo "[report]\nfail_under = 80"