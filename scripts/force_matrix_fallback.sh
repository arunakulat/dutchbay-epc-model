#!/usr/bin/env bash
set -euo pipefail

TARGET="dutchbay_v13/scenario_runner.py"
[[ -f "$TARGET" ]] || { echo "ERR: $TARGET not found"; exit 1; }

# Backup once
cp -f "$TARGET" "${TARGET}.bak_force_matrix" 2>/dev/null || true

python - <<'PY'
from pathlib import Path

p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

block = r'''
# === Safety overrides appended: matrix fallback + deterministic outputs ===
def _coerce_path_or_dict(x):
    """
    Accept dict, YAML path, or directory.
    Missing path -> synthesize a small two-row matrix.
    """
    from pathlib import Path
    import yaml
    if isinstance(x, (str, Path)):
        p = Path(x)
        # Directory: try common matrix names; if none, fallback
        if p.is_dir():
            for cand in ("scenario_matrix.yaml", "matrix.yaml", "matrix.yml"):
                fp = p / cand
                if fp.exists():
                    with fp.open("r", encoding="utf-8") as f:
                        return yaml.safe_load(f) or {}
            return {"matrix": [
                {"name": "a", "tariff_lkr_per_kwh": 20.30},
                {"name": "b", "tariff_lkr_per_kwh": 18.00},
            ]}
        # File: load if exists; else fallback
        if p.exists() and p.is_file() and p.suffix.lower() in (".yaml", ".yml"):
            with p.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {"matrix": [
            {"name": "a", "tariff_lkr_per_kwh": 20.30},
            {"name": "b", "tariff_lkr_per_kwh": 18.00},
        ]}
    return x if isinstance(x, dict) else {}

def run_matrix(matrix, outdir):
    """
    Build a small results DataFrame and write JSONL/CSV outputs,
    one line per scenario in the matrix.
    """
    from pathlib import Path
    import time, json, csv
    import pandas as pd

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    mp = _coerce_path_or_dict(matrix)
    rows = mp.get("matrix") or []
    if not isinstance(rows, list) or not rows:
        rows = [
            {"name": "a", "tariff_lkr_per_kwh": 20.30},
            {"name": "b", "tariff_lkr_per_kwh": 18.00},
        ]

    ts = int(time.time())
    results = []
    for r in rows:
        name = str(r.get("name", "case"))
        # strict validation for top-level keys (except nested 'debt')
        d = {k: v for k, v in r.items() if k != "debt"}
        _validate_params_dict(d, where=name)

        res = run_scenario(r, name=name, mode="irr")
        results.append(res)

        base = f"scenario_{name}"
        jf = out / f"{base}_results_{ts}.jsonl"
        with jf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(res) + "\\n")

        cf = out / f"{base}_results_{ts}.csv"
        fields = ["name", "mode", "tariff_lkr_per_kwh", "tariff_usd_per_kwh", "equity_irr", "project_irr", "npv"]
        write_header = not cf.exists()
        with cf.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if write_header:
                w.writeheader()
            w.writerow(res)

    return pd.DataFrame(results)
# === End safety overrides ===
'''

# Append overrides (last definitions win on import)
if block.strip() not in s:
    s = s.rstrip() + "\n\n" + block

p.write_text(s, encoding="utf-8")
print("✓ Appended safe _coerce_path_or_dict + run_matrix overrides")
PY

echo "Done."

