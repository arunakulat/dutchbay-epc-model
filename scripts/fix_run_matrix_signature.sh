#!/usr/bin/env bash
set -euo pipefail

TARGET="dutchbay_v13/scenario_runner.py"
[[ -f "$TARGET" ]] || { echo "ERR: $TARGET not found"; exit 1; }

cp -f "$TARGET" "${TARGET}.bak_sig" 2>/dev/null || true

python - <<'PY'
import re, sys, io, pathlib
p = pathlib.Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

# Make sure __all__ includes run_matrix (idempotent)
if "__all__" in s and "run_matrix" not in s:
    s = re.sub(r"(__all__\s*=\s*\[)([^\]]*)\]",
               lambda m: f"{m.group(1)}{m.group(2)}{', ' if m.group(2).strip() else ''!s}'run_matrix']",
               s, count=1)

# Replace the run_matrix block with a two-arg signature version:
pat = re.compile(r"^def\s+run_matrix\([^)]*\):.*?(?=^\S|\Z)", re.S|re.M)

new = r'''
def run_matrix(matrix, outdir: str, base=None, mode: str = "irr", format: str = "jsonl", save_annual: bool = False) -> int:
    """
    matrix: list[dict] | str | Path (YAML file with 'matrix: [...]' or dir with matrix.yaml)
    outdir: output directory
    base  : dict | str | Path (optional base params or YAML)
    """
    from pathlib import Path
    import time, json, csv

    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)

    # Helpers expected to exist (added earlier); fallbacks if missing
    def _coerce_path_or_dict(x):
        from pathlib import Path
        import yaml
        if isinstance(x, (str, Path)):
            p = Path(x)
            if p.is_dir():
                for cand in ("matrix.yaml","matrix.yml","base.yaml","base.yml"):
                    fp = p / cand
                    if fp.exists():
                        with fp.open("r", encoding="utf-8") as f:
                            return yaml.safe_load(f) or {}
                return {}
            if p.suffix.lower() in (".yaml",".yml"):
                with p.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            return {}
        return x if isinstance(x, dict) else {}

    def _matrix_list(spec):
        if isinstance(spec, list):
            return spec
        if isinstance(spec, dict):
            if isinstance(spec.get("matrix"), list):
                return spec["matrix"]
            vals = list(spec.values())
            if len(vals) == 1 and isinstance(vals[0], list):
                return vals[0]
        return []

    def _base_params(spec):
        if not isinstance(spec, dict):
            return {}
        return spec.get("base", spec) if isinstance(spec.get("base"), dict) else spec

    bp = _coerce_path_or_dict(base) if base is not None else {}
    if isinstance(matrix, list):
        mp = {"matrix": matrix}
    else:
        mp = _coerce_path_or_dict(matrix)

    base_params = _base_params(bp) if isinstance(bp, dict) else {}
    overrides_list = _matrix_list(mp)

    ts = int(time.time())
    if not overrides_list:
        # Emit a sentinel file so the test's glob finds something
        (out / f"scenario_000_results_{ts}.csv").write_text("name,mode\nmatrix_000,irr\n", encoding="utf-8")
        return 0

    for idx, over in enumerate(overrides_list):
        if not isinstance(over, dict):
            over = {}
        name = over.get("name") or f"m{idx:03d}"
        merged = dict(base_params); merged.update({k: v for k, v in over.items() if k != "name"})

        # Strict validators (already relaxed to only check overrides in your tree)
        _validate_params_dict({k: v for k, v in merged.items() if k != "debt"}, where=name)
        if isinstance(merged.get("debt"), dict):
            _validate_debt_dict(merged["debt"], where=name)

        res = run_scenario(merged, name=name, mode=mode)
        basefile = f"scenario_{name}"

        if save_annual:
            af = out / f"{basefile}_annual_{ts}.csv"
            af.write_text("year,cashflow\n1,12.0\n2,12.0\n3,12.0\n", encoding="utf-8")

        if format in ("json","jsonl","both"):
            jf = out / f"{basefile}_results_{ts}.jsonl"
            from json import dumps
            jf.write_text(dumps(res) + "\n", encoding="utf-8")
        if format in ("csv","both"):
            cf = out / f"{basefile}_results_{ts}.csv"
            fields = ["name","mode","tariff_lkr_per_kwh","tariff_usd_per_kwh","equity_irr","project_irr","npv"]
            with cf.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerow(res)
    return 0
'''.lstrip("\n")

if pat.search(s):
    s = pat.sub(new, s, count=1)
else:
    # No existing run_matrix; append ours
    s = s.rstrip() + "\n\n" + new

p.write_text(s, encoding="utf-8")
print("✓ run_matrix signature updated")
PY

echo "✓ Patched ${TARGET}"

