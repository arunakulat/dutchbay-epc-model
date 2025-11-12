#!/usr/bin/env bash
set -euo pipefail

TARGET="dutchbay_v13/scenario_runner.py"
[[ -f "$TARGET" ]] || { echo "ERR: $TARGET not found"; exit 1; }
cp -f "$TARGET" "${TARGET}.bak_emit_matrix" 2>/dev/null || true

python - <<'PY'
from pathlib import Path
import re

p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

# Idempotent: if already emitting scenario_matrix_* just exit.
if "scenario_matrix_results_" in s:
    print("↷ Consolidated matrix outputs already present; no change.")
else:
    # Inject consolidated writer right before the run_matrix return
    pattern = r"(def\s+run_matrix\([\\s\\S]*?)return\s+pd\\.DataFrame\\(results\\)"
    repl = r"""\\1
    # Consolidated matrix JSONL/CSV (tests expect scenario_matrix_* files)
    base = "scenario_matrix"
    jf_all = out / f"{base}_results_{ts}.jsonl"
    with jf_all.open("w", encoding="utf-8") as f:
        for r in results:
            import json
            f.write(json.dumps(r) + "\\n")

    cf_all = out / f"{base}_results_{ts}.csv"
    fields = ["name","mode","tariff_lkr_per_kwh","tariff_usd_per_kwh","equity_irr","project_irr","npv"]
    import csv
    with cf_all.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow(r)

    return pd.DataFrame(results)"""
    ns, n = re.subn(pattern, repl, s, flags=re.M | re.S)
    if n == 0:
        raise SystemExit("ERR: couldn't patch run_matrix; unexpected layout.")
    p.write_text(ns, encoding="utf-8")
    print("✓ Patched run_matrix to emit scenario_matrix_* consolidated files.")
PY

echo "Done."

