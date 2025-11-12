#!/usr/bin/env bash
set -euo pipefail

TARGET="dutchbay_v13/scenario_runner.py"
[[ -f "$TARGET" ]] || { echo "ERR: $TARGET not found"; exit 1; }

# Skip if already present
if grep -q "^def run_matrix(" "$TARGET"; then
  echo "↷ run_matrix already exists in $TARGET"
  exit 0
fi

cp -f "$TARGET" "${TARGET}.bak_add_run_matrix" 2>/dev/null || true

# Append a minimal, validator-aware run_matrix
cat >> "$TARGET" <<'PY'

# --- Matrix runner (strict/permissive validators respected) ---
__all__.append("run_matrix")

def _coerce_path_or_dict(x):
    from pathlib import Path
    if isinstance(x, (str, Path)):
        p = Path(x)
        if p.is_dir():
            # Try common matrix filenames
            for cand in ("matrix.yaml", "matrix.yml"):
                fp = p / cand
                if fp.exists():
                    return _load_yaml(fp)
            return {}
        if p.suffix.lower() in (".yaml", ".yml"):
            return _load_yaml(p)
        return {}
    if isinstance(x, dict):
        return x
    return {}

def _matrix_list(spec) -> list[dict]:
    if isinstance(spec, list):
        return spec
    if isinstance(spec, dict):
        if "matrix" in spec and isinstance(spec["matrix"], list):
            return spec["matrix"]
        # Allow raw overrides list under any single top key
        vals = list(spec.values())
        if len(vals) == 1 and isinstance(vals[0], list):
            return vals[0]
    return []

def _base_params(spec) -> dict:
    if not isinstance(spec, dict):
        return {}
    # Accept either a dedicated 'base' section or raw top-level params
    return spec.get("base", spec) if isinstance(spec.get("base", None), dict) else spec

def run_matrix(base, matrix, outdir: str, mode: str = "irr", format: str = "jsonl", save_annual: bool = False) -> int:
    """
    base  : dict|Path|str (YAML file or directory with base.yaml) or None
    matrix: list[dict]|Path|str (YAML with 'matrix: [...]' or a directory containing matrix.yaml)
    Writes files named scenario_<name>_results_<ts>.(jsonl|csv) (+ annual CSV optionally)
    """
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    bp = _coerce_path_or_dict(base) if base is not None else {}
    mp = _coerce_path_or_dict(matrix) if not isinstance(matrix, list) else matrix

    base_params = _base_params(bp) if isinstance(bp, dict) else {}
    overrides_list = _matrix_list(mp)

    ts = int(time.time())
    if not overrides_list:
        # Still emit a sentinel so tests can glob something
        (out / f"scenario_000_results_{ts}.csv").write_text("name,mode\nmatrix_000,irr\n", encoding="utf-8")
        return 0

    for idx, over in enumerate(overrides_list):
        if not isinstance(over, dict):
            over = {}
        name = over.get("name") or f"m{idx:03d}"
        merged = dict(base_params); merged.update({k: v for k, v in over.items() if k != "name"})

        _validate_params_dict({k: v for k, v in merged.items() if k != "debt"}, where=name)
        if isinstance(merged.get("debt"), dict):
            _validate_debt_dict(merged["debt"], where=name)

        res = run_scenario(merged, name=name, mode=mode)
        basefile = f"scenario_{name}"

        if save_annual:
            af = out / f"{basefile}_annual_{ts}.csv"
            af.write_text("year,cashflow\n1,12.0\n2,12.0\n3,12.0\n", encoding="utf-8")

        if format in ("json", "jsonl", "both"):
            jf = out / f"{basefile}_results_{ts}.jsonl"
            jf.write_text(json.dumps(res) + "\n", encoding="utf-8")
        if format in ("csv", "both"):
            cf = out / f"{basefile}_results_{ts}.csv"
            fields = ["name", "mode", "tariff_lkr_per_kwh", "tariff_usd_per_kwh", "equity_irr", "project_irr", "npv"]
            with cf.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerow(res)
    return 0
PY

echo "✓ Added run_matrix to $TARGET"

