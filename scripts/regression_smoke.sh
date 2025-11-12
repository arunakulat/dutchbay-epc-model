# scripts/regression_smoke.sh
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p _regression
REPORT="_regression/report.txt"
JSON="_regression/summary.json"
: >"$REPORT"
echo '{"cases":[]}' >"$JSON"

short_sha="$(git rev-parse --short HEAD 2>/dev/null || echo "nogit")"
echo "=== DutchBay v13 Regression Smoke @ $(date -Iseconds) (rev: $short_sha) ===" | tee -a "$REPORT"

pass() { printf "PASS  %s\n" "$1" | tee -a "$REPORT"; }
fail() { printf "FAIL  %s (exit %s)\n" "$1" "$2" | tee -a "$REPORT"; }

add_json_case() {
  # args: name, status, seconds
  python - <<'PY' "$JSON" "$1" "$2" "$3"
import json,sys
p,name,stat,secs=sys.argv[1:]
d=json.load(open(p))
d["cases"].append({"name":name,"status":stat,"seconds":float(secs)})
open(p,"w").write(json.dumps(d,indent=2))
PY
}

run_case() {
  local name="$1"; shift
  local cmd=("$@")
  local start end dur rc

  printf "\n--- %s ---\n" "$name" | tee -a "$REPORT"
  printf "CMD: %q " "${cmd[@]}" | tee -a "$REPORT"; echo | tee -a "$REPORT"

  SECONDS=0
  set +e
  "${cmd[@]}"
  rc=$?
  set -e
  dur="$SECONDS"

  if [ $rc -eq 0 ]; then pass "$name"; add_json_case "$name" "PASS" "$dur"
  else fail "$name" "$rc"; add_json_case "$name" "FAIL" "$dur"; fi
}

# Clean noisy artifacts from previous runs
rm -f _out/scenario_* || true

# A. Module-focused tests we already used
run_case "finance.irr module tests"  bash scripts/test_one_module.sh irr
run_case "finance.debt module tests" bash scripts/test_one_module.sh debt

# B. CLI smoke (direct)
run_case "cli smoke (direct)" pytest -q tests/test_cli_smoke_direct.py \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

# C. Scenarios (multiple files/outputs)
run_case "scenarios (multi-file emit)" pytest -q tests/test_cli_scenarios_more.py \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

# D. Matrix + strict validator behavior
run_case "matrix + validator" pytest -q tests/test_scenarios_jsonl_and_validator.py \
  --override-ini="addopts=-q --cov=dutchbay_v13 --cov-report=term-missing --cov-fail-under=1"

echo -e "\n=== Summary ===" | tee -a "$REPORT"
python - <<'PY' "$JSON" | tee -a "$REPORT"
import json,sys
d=json.load(open(sys.argv[1]))
total=len(d["cases"])
fails=[c for c in d["cases"] if c["status"]!="PASS"]
print(f"Total: {total} | Failures: {len(fails)}")
for c in d["cases"]:
    print(f" - {c['name']}: {c['status']} ({c['seconds']:.1f}s)")
exit(1 if fails else 0)
PY

