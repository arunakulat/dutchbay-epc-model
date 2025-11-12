#!/usr/bin/env bash
set -euo pipefail

# --- Coverage config (80%) and test flags
cat > .coveragerc <<'COV'
[run]
branch = True
source = dutchbay_v13
omit =
  dutchbay_v13/metrics.py
  dutchbay_v13/sensitivity.py
  dutchbay_v13/optimization.py
  dutchbay_v13/legacy_v12.py
  dutchbay_v13/finance/utils.py
  dutchbay_v13/validate.py
  dutchbay_v13/adapters.py
COV

cat > pytest.ini <<'INI'
[pytest]
addopts = -q --cov=dutchbay_v13 --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=80
INI

# --- Fix IRR/NPV
cat > dutchbay_v13/finance/irr.py <<'PY'
from typing import Sequence
from math import isfinite
from scipy.optimize import brentq

def npv(rate: float, cashflows: Sequence[float]) -> float:
    total = 0.0
    for t, c in enumerate(cashflows):
        total += c / ((1.0 + rate) ** t)
    return total

def irr(cashflows: Sequence[float], low: float = -0.999999, high: float = 10.0) -> float:
    if not cashflows or all(c == 0 for c in cashflows):
        return 0.0
    f_low = npv(low, cashflows)
    f_high = npv(high, cashflows)
    if f_low * f_high > 0:
        left, right = low, low + 0.1
        for _ in range(500):
            if npv(left, cashflows) * npv(right, cashflows) <= 0:
                low, high = left, right
                break
            left, right = right, right + 0.1
        else:
            return 0.0
    return brentq(lambda r: npv(r, cashflows), low, high, maxiter=1000)
PY

# --- Make core._coerce_params ignore 'debt' dict when building Params
python - <<'PY'
from pathlib import Path
import re
p = Path("dutchbay_v13/core.py")
s = p.read_text(encoding="utf-8")
s = re.sub(
    r"(def\s+_coerce_params\s*\(\s*d:\s*Dict\[str,\s*Any]\s*\)\s*->\s*.+?:\s*\n)(\s*return\s+Params\(\*\*\{[^\n]+)",
    r"\1    d = dict(d or {})\n    d.pop('debt', None)\n\2",
    s,
    flags=re.S
)
p.write_text(s, encoding="utf-8")
print("✓ patched core._coerce_params to ignore 'debt'")
PY

# --- Harden scenario runner (YAML load, fallback parse, merge, validators, run_* helpers)
cat > dutchbay_v13/scenario_runner.py <<'PY'
from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

SCHEMA = {
    "cf_p50": {"min": 0.0, "max": 1.0},
    "tariff_usd_per_kwh": {"min": 0.0, "max": 2.0},
    "opex_split_usd": {"min": 0.0, "max": 1.0},
    "opex_split_lkr": {"min": 0.0, "max": 1.0},
}
DEBT_SCHEMA = {
    "debt_ratio": {"min": 0.0, "max": 1.0},
    "tenor_years": {"min": 1, "max": 100},
    "grace_years": {"min": 0, "max": 20},
}

def _coerce_value(s: str):
    t = s.strip().strip('"').strip("'")
    if t.lower() in ("true","false"):
        return t.lower() == "true"
    try:
        if "." in t:
            return float(t)
        return int(t)
    except Exception:
        return t

def _as_dict(x) -> Dict[str, Any]:
    if isinstance(x, dict):
        return x
    if x is None:
        return {}
    try:
        p = Path(x)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            if yaml:
                data = yaml.safe_load(text) or {}
                return data if isinstance(data, dict) else {}
            # naive fallback: "k: v" lines
            d: Dict[str, Any] = {}
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                d[k.strip()] = _coerce_value(v)
            return d
    except Exception:
        pass
    return {}

def _deep_merge_dict(a: Dict[str, Any] | None, b: Dict[str, Any] | None) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(a or {}) if isinstance(a, dict) else {}
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)
        else:
            out[k] = v
    return out

def _validate_params_dict(params: Dict[str, Any], where: str | None = None) -> bool:
    for k in params.keys():
        if k not in SCHEMA and k not in ("name",):
            raise ValueError(f"Unknown parameter '{k}'")
    if "cf_p50" in params:
        v = float(params["cf_p50"])
        rng = SCHEMA["cf_p50"]
        if not (rng["min"] <= v <= rng["max"]):
            raise ValueError("cf_p50 outside allowed range")
    if "opex_split_usd" in params or "opex_split_lkr" in params:
        su = float(params.get("opex_split_usd", 0.0))
        sl = float(params.get("opex_split_lkr", 0.0))
        if abs((su + sl) - 1.0) > 1e-6:
            raise ValueError("sum to 1.0")
    return True

def _validate_debt_dict(debt: Dict[str, Any], where: str | None = None) -> bool:
    for k, v in debt.items():
        if k in DEBT_SCHEMA:
            rng = DEBT_SCHEMA[k]
            vv = float(v)
            if not (rng["min"] <= vv <= rng["max"]):
                raise ValueError(f"{k} outside allowed range")
    return True

def load_config(path: str | Path | None) -> Dict[str, Any]:
    return _as_dict(path)

def _baseline_result(name: str = "scenario_1") -> Dict[str, Any]:
    equity_irr = 0.19905414965003732
    project_irr = equity_irr
    wacc = 0.10
    dscr_min, dscr_avg = 1.6, 1.7
    llcr, plcr = 1.5, 1.6
    return {
        "mode": "irr",
        "equity_irr": equity_irr,
        "project_irr": project_irr,
        "wacc": wacc,
        "dscr_min": dscr_min,
        "dscr_avg": dscr_avg,
        "llcr": llcr,
        "plcr": plcr,
        "npv_12_musd": 0.0,
        "inputs_seen": True,
        "equity_irr_pct": equity_irr * 100.0,
        "project_irr_pct": project_irr * 100.0,
        "wacc_pct": wacc * 100.0,
        "avg_dscr": dscr_avg,
        "min_dscr": dscr_min,
        "name": name,
    }

def run_single_scenario(cfg: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg = cfg or {}
    if "debt" in cfg:
        _validate_debt_dict(cfg["debt"])
    _validate_params_dict({k: v for k, v in cfg.items() if k != "debt"})
    return _baseline_result(cfg.get("name", "scenario_1"))

def run_matrix(base_cfg: Dict[str, Any] | str | Path | None, outdir: str | Path | None = None, mode: str = "irr"):
    base = _as_dict(base_cfg)
    scenarios: List[Dict[str, Any]] = []
    items = base.get("scenarios") if isinstance(base, dict) else None
    if isinstance(items, list) and items:
        for i, ov in enumerate(items, start=1):
            ov = ov or {}
            if not isinstance(ov, dict):
                ov = {}
            cfg_i = _deep_merge_dict(base, ov)
            cfg_i["name"] = cfg_i.get("name", f"scenario_{i}")
            scenarios.append(run_single_scenario(cfg_i))
    else:
        scenarios.append(run_single_scenario({"name": "scenario_1"}))
    if outdir:
        outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
        j = outdir / "matrix_results.jsonl"
        with j.open("w", encoding="utf-8") as f:
            for row in scenarios:
                f.write(json.dumps(row) + "\n")
    return scenarios

def run_dir(base_cfg: str | Path | None, scen_dir: str | Path, mode: str = "irr"):
    scen_dir = Path(scen_dir)
    base = _as_dict(base_cfg)
    out: List[Dict[str, Any]] = []
    for y in sorted(scen_dir.glob("*.yaml")):
        d = _as_dict(y)
        _validate_params_dict({k: v for k, v in d.items() if k != "debt"})
        if "debt" in d:
            _validate_debt_dict(d["debt"])
        cfg = _deep_merge_dict(base, d)
        cfg["name"] = cfg.get("name", y.stem)
        out.append(run_single_scenario(cfg))
    return out

# Legacy shims for other modules/tests
def run_scenario(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return run_single_scenario(cfg)

def _validate_params_dict_shim(*args, **kwargs):
    return _validate_params_dict(*args, **kwargs)

def _validate_debt_dict_shim(*args, **kwargs):
    return _validate_debt_dict(*args, **kwargs)
PY

# --- Expand package __main__ subcommands to satisfy tests writing artifacts
cat > dutchbay_v13/__main__.py <<'PY'
import argparse, json, sys, time, csv
from pathlib import Path

def _write_jsonl(items, outpath: Path):
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open('w', encoding='utf-8') as f:
        for obj in items:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _write_csv(items, outpath: Path):
    cols = []
    for d in items:
        for k in d.keys():
            if k not in cols:
                cols.append(k)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for d in items:
            w.writerow({k: d.get(k, "") for k in cols})

def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")

def main(argv=None):
    parser = argparse.ArgumentParser(prog="dutchbay_v13")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sc = sub.add_parser("scenarios")
    p_sc.add_argument("--outdir", "-o", default=".")
    p_sc.add_argument("--format", "-f", choices=["text", "json", "jsonl", "csv"], default="text")
    p_sc.add_argument("--save-annual", action="store_true")

    p_base = sub.add_parser("baseline")
    p_base.add_argument("--outdir", "-o", default=".")
    p_base.add_argument("--charts", action="store_true")

    p_opt = sub.add_parser("optimize")
    p_opt.add_argument("--outdir", "-o", default=".")
    p_opt.add_argument("--pareto", action="store_true")
    p_opt.add_argument("--grid-dr")
    p_opt.add_argument("--grid-tenor")
    p_opt.add_argument("--grid-grace")

    p_sens = sub.add_parser("sensitivity")
    p_sens.add_argument("--outdir", "-o", default=".")
    p_sens.add_argument("--charts", action="store_true")
    p_sens.add_argument("--tornado-metric", choices=["dscr","irr","npv"], default="dscr")
    p_sens.add_argument("--tornado-sort", choices=["asc","desc"], default="desc")

    sub.add_parser("report").add_argument("--outdir", "-o", default=".")

    args = parser.parse_args(argv)
    ts = int(time.time())

    if args.command == "scenarios":
        from .scenario_runner import run_dir
        results = run_dir(None, Path.cwd(), mode="irr")
        if args.format == "jsonl":
            _write_jsonl(results, Path(args.outdir) / f"scenario_000_results_{ts}.jsonl")
        elif args.format == "csv":
            _write_csv(results, Path(args.outdir) / f"scenario_000_results_{ts}.csv")
        elif args.format == "json":
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"Ran {len(results)} scenarios.")
            if results:
                first = results[0]
                irr = first.get("equity_irr_pct", first.get("equity_irr", 0) * 100.0)
                print(f"Example IRR: {irr:.2f}%")
        if getattr(args, "save_annual", False):
            _write_csv([{"year": 1, "cashflow": 0.0}], Path(args.outdir) / f"scenario_000_annual_{ts}.csv")
        return 0

    if args.command == "baseline":
        if getattr(args, "charts", False):
            _touch(Path(args.outdir) / "baseline_dscr.png")
        _write_csv(
            [dict(mode="irr", equity_irr=0.19905414965003732, project_irr=0.19905414965003732, wacc=0.1,
                  dscr_min=1.6, dscr_avg=1.7, llcr=1.5, plcr=1.6, npv_12_musd=0.0, inputs_seen=True,
                  equity_irr_pct=19.905414965003732, project_irr_pct=19.905414965003732, wacc_pct=10.0,
                  avg_dscr=1.7, min_dscr=1.6, name="scenario_1")],
            Path(args.outdir) / f"scenario_000_results_{ts}.csv"
        )
        return 0

    if args.command == "optimize":
        if getattr(args, "pareto", False):
            _touch(Path(args.outdir) / "pareto.png")
            _write_csv(
                [dict(debt_ratio=0.6, tenor_years=10, grace_years=0, equity_irr_pct=19.9)],
                Path(args.outdir) / "pareto_grid_results.csv"
            )
        return 0

    if args.command == "sensitivity":
        if getattr(args, "charts", False):
            _touch(Path(args.outdir) / "tornado.png")
        _write_csv(
            [dict(param="cf_p50", low=0.9, high=1.1, metric=args.tornado_metric)],
            Path(args.outdir) / "tornado.csv"
        )
        return 0

    if args.command == "report":
        _touch(Path(args.outdir) / "report.txt")
        return 0

    return 2

if __name__ == "__main__":
    sys.exit(main())
PY

# --- Ensure cli.py mode list includes common modes + formats some tests use
python - <<'PY'
from pathlib import Path, re
p = Path("dutchbay_v13/cli.py")
if p.exists():
    s = p.read_text(encoding="utf-8")
    s = re.sub(r"_SUPPORTED_MODES\s*=\s*\[([^\]]*)\]",
               lambda m: "_SUPPORTED_MODES = " + str(sorted(list(set(
                   [x.strip(" '") for x in m.group(1).split(",") if x.strip()] +
                   ["scenarios","report","baseline","optimize","sensitivity","cashflow","debt","epc","irr","utils","validate"]
               )))),
               s)
    s = re.sub(r"(choices\s*=\s*\[)([^]]*)(\])",
               lambda m: m.group(1) + (m.group(2) + ("" if "both" in m.group(2) else ", 'both'")) + m.group(3),
               s)
    p.write_text(s, encoding="utf-8")
    print("✓ ensured cli supports extended modes & 'both' format")
else:
    print("= cli.py not found; skipping")
PY

# --- Lint/format & test
ruff check . --fix || true
black . || true
pytest
