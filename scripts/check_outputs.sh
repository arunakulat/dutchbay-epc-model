#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:-_out}"
echo "Output dir: $OUTDIR"
if [[ ! -d "$OUTDIR" ]]; then
  echo "No such directory: $OUTDIR" >&2
  exit 1
fi

latest_csv="$(ls -1t "$OUTDIR"/scenario_*_results_*.csv 2>/dev/null | head -n1 || true)"
latest_jsonl="$(ls -1t "$OUTDIR"/scenario_*_results_*.jsonl 2>/dev/null | head -n1 || true)"
latest_annual="$(ls -1t "$OUTDIR"/scenario_*_annual_*.csv 2>/dev/null | head -n1 || true)"

if [[ -z "${latest_csv:-}" && -z "${latest_jsonl:-}" && -z "${latest_annual:-}" ]]; then
  echo "No outputs found under $OUTDIR."
  echo "Try:  python -m dutchbay_v13 scenarios -f csv --save-annual -o \"$OUTDIR\""
  exit 2
fi

if [[ -n "${latest_csv:-}" ]]; then
  echo
  echo "— CSV aggregate (latest): $latest_csv"
  CSV_PATH="$latest_csv" python - <<'PY'
import csv, os
p=os.environ["CSV_PATH"]
with open(p, newline='', encoding='utf-8') as f:
    r=csv.reader(f)
    header=next(r)
    print("header:", ", ".join(header))
    for i, row in zip(range(5), r):
        print(f"row {i+1} :", ", ".join(row))
PY
else
  echo
  echo "(no CSV aggregate found)"
fi

if [[ -n "${latest_jsonl:-}" ]]; then
  echo
  echo "— JSONL (latest, first 3 lines): $latest_jsonl"
  head -n 3 "$latest_jsonl" || true
else
  echo
  echo "(no JSONL found)"
fi

if [[ -n "${latest_annual:-}" ]]; then
  echo
  echo "— Annual CSV (latest): $latest_annual"
  CSV_PATH="$latest_annual" python - <<'PY'
import csv, os
p=os.environ["CSV_PATH"]
with open(p, newline='', encoding='utf-8') as f:
    r=csv.reader(f)
    header=next(r)
    print("header:", ", ".join(header))
    for i, row in zip(range(5), r):
        print(f"row {i+1} :", ", ".join(row))
PY
else
  echo
  echo "(no Annual CSV found)"
fi
