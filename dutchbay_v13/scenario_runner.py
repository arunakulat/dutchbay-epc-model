# dutchbay_v13/scenario_runner.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
import csv
import json

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from .adapters import run_irr  # core calc; debt layer is applied within adapters
from .validate import validate_params_dict, load_params_from_file  # strict/relaxed handled there


Pathish = Union[str, Path]


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _to_csv_rows(annual: List[Dict[str, Any]]) -> Tuple[List[str], List[List[Any]]]:
    """
    Produce (header, rows) for CSV from a list of annual dicts.
    Keys are unioned and ordered with a small preference for common fields.
    """
    if not annual:
        return [], []
    # Union keys
    keys = set()
    for row in annual:
        keys.update(row.keys())

    # Prefer this order if present, then append the rest sorted
    preferred = [
        "year",
        "revenue_usd",
        "cfads_usd",
        "equity_cf",
        "debt_service",
        "interest",
        "principal",
        "dscr",
    ]
    ordered = [k for k in preferred if k in keys] + [k for k in sorted(keys) if k not in set(preferred)]

    rows = []
    for row in annual:
        rows.append([row.get(k, "") for k in ordered])
    return ordered, rows


def _write_outputs(outputs_dir: Path, fmt: str, res: Dict[str, Any], save_annual: bool) -> None:
    _ensure_dir(outputs_dir)

    # Always drop a summary JSON
    summary_path = outputs_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "equity_irr": res.get("equity_irr"),
                "project_irr": res.get("project_irr"),
                "npv_12": res.get("npv_12"),
                "dscr_min": res.get("dscr_min"),
                "balloon_remaining": res.get("balloon_remaining"),
            },
            f,
            indent=2,
        )

    if save_annual:
        annual = res.get("annual") or []
        if fmt.lower() == "csv":
            header, rows = _to_csv_rows(annual)
            if header:
                with (outputs_dir / "annual.csv").open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(rows)
        else:
            # JSON fallback (extensible later)
            with (outputs_dir / "annual.json").open("w", encoding="utf-8") as f:
                json.dump(annual, f, indent=2)


def run_params(
    params: Dict[str, Any],
    outputs_dir: Optional[Pathish] = None,
    *,
    mode: str = "irr",
    fmt: str = "csv",
    save_annual: bool = False,
) -> Dict[str, Any]:
    """
    Execute a scenario from an in-memory params dict.
    - Validates via validate_params_dict (env-aware strict/relaxed).
    - Calls adapters.run_irr(params, annual).
    - Writes outputs if requested.
    """
    if mode != "irr":
        raise ValueError(f"Unsupported mode: {mode}")

    # Validate (raises on STRICT unknown keys; relaxed otherwise)
    params = validate_params_dict(params)

    # Extract inlined annual (optional)
    annual = params.get("annual")
    if annual is not None and not isinstance(annual, list):
        raise TypeError("If provided, `annual` must be a list of {year, ...} mappings")

    res = run_irr(params, annual)

    # Basic sanity: run_irr must return a mapping
    if not isinstance(res, dict):
        raise TypeError(f"run_irr must return a mapping-compatible result, got {type(res).__name__}")

    # Optional outputs
    if outputs_dir is not None:
        out_dir = Path(outputs_dir)
        _write_outputs(out_dir, fmt, res, save_annual)

    return res


def run_dir(
    config_path: Pathish,
    outputs_dir: Pathish,
    *,
    mode: str = "irr",
    fmt: str = "csv",
    save_annual: bool = False,
) -> Dict[str, Any]:
    """
    File-based entry (used by CLI). Validates, runs, and writes outputs.
    """
    params = load_params_from_file(config_path)
    return run_params(params, outputs_dir, mode=mode, fmt=fmt, save_annual=save_annual)


# Back-compat alias
run_file = run_dir

