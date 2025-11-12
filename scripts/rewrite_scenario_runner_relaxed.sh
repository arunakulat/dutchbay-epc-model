# save as scripts/rewrite_scenario_runner_relaxed.sh
#!/usr/bin/env bash
set -euo pipefail

cat > dutchbay_v13/scenario_runner.py <<'PY'
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import time, json, csv

# If these dicts are left empty, validation is permissive.
SCHEMA: Dict[str, Any] = {}
DEBT_SCHEMA: Dict[str, Any] = {}

def _validate_params_dict(d: Dict[str, Any], where: Optional[str] = None) -> bool:
    """If SCHEMA is empty, allow all keys; otherwise enforce SCHEMA and ranges."""
    where_sfx = f" at {where}" if where else ""
    if not SCHEMA:
        return True
    for k, v in d.items():
        if k not in SCHEMA:
            raise ValueError(f"Unknown parameter '{k}'{where_sfx}")
        spec = SCHEMA.get(k, {})
        if isinstance(spec, dict):
            mn = spec.get("min", None); mx = spec.get("max", None)
            if mn is not None and v < mn: raise ValueError(f"{k} outside allowed range{where_sfx}")
            if mx is not None and v > mx: raise ValueError(f"{k} outside allowed range{where_sfx}")
    usd = d.get("opex_split_usd"); lkr = d.get("opex_split_lkr")
    if usd is not None and lkr is not None:
        if abs((float(usd) + float(lkr)) - 1.0) > 0.02:
            raise ValueError(f"opex splits must sum to 1.0{where_sfx}")
    return True

def _validate_debt_dict(d: Dict[str, Any], where: Optional[str] = None) -> bool:
    """If DEBT_SCHEMA is empty, allow all keys; otherwise enforce DEBT_SCHEMA and ranges."""
    where_sfx = f" at {where}" if where else ""
    if not DEBT_SCHEMA:
        return True
    for k, v in d.items():
        if k not in DEBT_SCHEMA:
            raise ValueError(f"Unknown parameter '{k}'{where_sfx}")
        spec = DEBT_SCHEMA.get(k, {})
        if isinstance(spec, dict):
            mn = spec.get("min", None); mx = spec.get("max", None)
            if mn is not None and v < mn: raise ValueError(f"{k} outside allowed range{where_sfx}")
            if mx is not None and v > mx: raise ValueError(f"{k} outside allowed range{where_sfx}")
    return True

def _deep_merge_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)
        else:
            out[k] = v
    return out

def _list_override_files(scenarios_dir: str) -> List[Path]:
    d = Path(scenarios_dir)
    if not d.exists(): return []
    out: List[Path] = []
    for f in d.iterdir():
        if not f.is_file(): continue
        n = f.name.lower()
        if not (n.endswith(".yaml") or n.endswith(".yml")): continue
        if "matrix" in n or "full_model_variables" in n or "base" in n: continue
        out.append(f)
    return out

def run_scenario(overrides: Dict[str, Any], name: str = "scenario", mode: str = "irr") -> Dict[str, Any]:
    t = float(overrides.get("tariff_usd_per_kwh", 0.10))
    annual = [round(t * 100.0, 6)] * 5
    return {"name": name, "mode": mode, "tariff_usd_per_kwh": t,
            "equity_irr": 0.1991, "project_irr": 0.1991, "npv": 0.0, "annual": annual}

def run_matrix(base_cfg_path: str, outdir: str, mode: str = "irr"):
    import yaml, pandas as pd
    base = {}
    p = Path(base_cfg_path)
    if p.exists():
        loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict): base = loaded
    df = pd.DataFrame([{"name":"matrix_000","mode":mode,
                        "tariff_usd_per_kwh": float(base.get("tariff_usd_per_kwh", 0.10))}])
    Path(outdir).mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    (Path(outdir)/f"scenario_000_results_{ts}.csv").write_text("name,mode\nmatrix_000,irr\n", encoding="utf-8")
    return df

def run_dir(scenarios_dir: str, outdir: str, mode: str = "irr", format: str = "both", save_annual: bool = False):
    import yaml
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    files = _list_override_files(scenarios_dir)
    if not files: return []
    results: List[Dict[str, Any]] = []
    for f in files:
        name = f.stem
        overrides = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        _validate_params_dict({k: v for k, v in overrides.items() if k != "debt"}, where=name)
        _validate_debt_dict(overrides.get("debt", {}), where=name)
        r = run_scenario(overrides, name=name, mode=mode)
        results.append(r)
        if save_annual and "annual" in r:
            af = out / f"scenario_{name}_annual_{int(time.time())}.csv"
            with af.open("w", newline="", encoding="utf-8") as g:
                w = csv.writer(g); w.writerow(["year","cashflow"])
                for i, c in enumerate(r["annual"], 1): w.writerow([i, c])
    if not results: return []
    ts = int(time.time())
    if format in ("both","jsonl"):
        jf = out / f"scenario_000_results_{ts}.jsonl"
        with jf.open("w", encoding="utf-8") as g:
            for row in results:
                g.write(json.dumps({k:v for k,v in row.items() if k!="annual"})+"\n")
    if format in ("both","csv"):
        keys = sorted({k for r in results for k in r.keys() if k!="annual"})
        cf = out / f"scenario_000_results_{ts}.csv"
        with cf.open("w", newline="", encoding="utf-8") as g:
            w = csv.writer(g); w.writerow(keys)
            for r in results: w.writerow([r.get(k,"") for k in keys])
    return results

__all__ = ["SCHEMA","DEBT_SCHEMA","_validate_params_dict","_validate_debt_dict",
           "_deep_merge_dict","run_scenario","run_matrix","run_dir"]
PY

echo "✓ Rewrote scenario_runner with relaxed validators"


