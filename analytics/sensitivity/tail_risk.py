from __future__ import annotations

"""
analytics.sensitivity.tail_risk

Tail risk enrichment for SensitivitySuite.

Purpose:
- Provide lender-grade downside summaries over sensitivity scenarios:
    * VaR (e.g., P10/P5) and CVaR (expected shortfall) for selected metrics
    * Probability of covenant breach (e.g., DSCR < floor) if metric available
- Attach outputs to suite.metadata in a stable format so CASPER can consume it.

IMPORTANT:
- This module does NOT run Monte Carlo by default.
- It provides an API for "tail risk snapshots" that can be computed from:
    A) precomputed MonteCarloResult per scenario, OR
    B) scenario-level approximation if caller supplies distributions.

This skeleton implements the metadata schema and hooks.
You will wire it to your Monte Carlo engine in your repo (recommended).
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import SensitivitySuite


@dataclass(frozen=True)
class TailRiskConfig:
    enabled: bool = True
    percentiles: Tuple[int, int, int] = (5, 10, 95)  # downside p5/p10; upside p95
    cvar_alpha: float = 0.05
    dscr_floor: float = 1.30
    # If True, expects raw trial arrays present for accurate stats.
    require_trials: bool = True


def _percentile(arr: np.ndarray, p: int) -> float:
    return float(np.percentile(arr, int(p)))


def _cvar(arr: np.ndarray, alpha: float) -> float:
    """
    CVaR / Expected Shortfall on the downside:
    mean of values <= VaR_alpha
    """
    if arr.size == 0:
        return float("nan")
    var = np.percentile(arr, alpha * 100.0)
    tail = arr[arr <= var]
    if tail.size == 0:
        return float(var)
    return float(tail.mean())


def _prob_breach(arr: np.ndarray, floor: float) -> float:
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr < float(floor)))


def enrich_suite_with_tail_risk(
    *,
    suite: SensitivitySuite,
    base_config: Mapping[str, Any],
    run_cfg: TailRiskConfig = TailRiskConfig(),
) -> SensitivitySuite:
    """
    Enrich the suite.metadata with tail risk blocks.

    This skeleton assumes the suite already contains scenario KPI metadata for each case.
    If you want *proper* tail risk (VaR/CVaR) you should attach Monte Carlo arrays per case.
    
    Note: MultiMetricSensitivitySuite was removed - use SensitivitySuite only.
    """
    if not run_cfg.enabled:
        return suite

    md = dict(getattr(suite, "metadata", {}) or {})
    md.setdefault("tail_risk", {})
    md.setdefault("tail_risk_summary", {})

    # We will compute "snapshots" using any trial arrays that are present under:
    # case["metadata"]["trials"][metric_key] OR case["metadata"]["mc_trials"][metric_key]
    # If absent, we fall back to single-point KPI values and only provide a trivial snapshot.
    tail_table: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"alpha": float(run_cfg.cvar_alpha), "percentiles": list(run_cfg.percentiles)}

    # SensitivitySuite shape (single metric)
    if hasattr(suite, "tornado_results"):
        metric_key = suite.metric
        tornado_results = suite.tornado_results
        
        for tornado in tornado_results:
            # Extract data from TornadoResult
            snap = _build_tornado_tail_snapshot(
                tornado=tornado,
                metric_key=metric_key,
                run_cfg=run_cfg
            )
            tail_table.extend(snap["rows"])
        
        summary["metrics"] = [metric_key]
    else:
        # Fallback for older structures
        summary["metrics"] = []

    md["tail_risk"] = tail_table
    md["tail_risk_summary"] = summary

    # write back
    try:
        suite.metadata = md  # type: ignore[attr-defined]
        return suite
    except Exception:
        # If contracts are frozen, recreate by copying with metadata.
        # Fallback: return suite with best effort.
        return suite


def _build_tornado_tail_snapshot(
    *,
    tornado: Any,
    metric_key: str,
    run_cfg: TailRiskConfig,
) -> Dict[str, Any]:
    """Build tail risk snapshot from TornadoResult."""
    rows: list[dict[str, Any]] = []
    
    param_name = str(getattr(tornado, "metric_name", "unknown"))
    base_value = float(getattr(tornado, "base_metric", 0.0))
    
    # For now, just return basic structure
    # TODO: Extract shock_results and compute tail stats
    rows.append({
        "parameter": param_name,
        "metric": metric_key,
        "base_value": base_value,
        "note": "basic_snapshot",
    })
    
    return {"rows": rows}


def _extract_trials_from_case(case: Mapping[str, Any], metric_key: str) -> Optional[np.ndarray]:
    meta = case.get("metadata", None)
    if not isinstance(meta, Mapping):
        return None
    for bucket in ("trials", "mc_trials"):
        b = meta.get(bucket, None)
        if isinstance(b, Mapping) and metric_key in b:
            arr = np.asarray(b[metric_key], dtype=float)
            if arr.ndim != 1:
                arr = arr.reshape(-1)
            return arr
    return None


def _build_case_tail_snapshot(
    *,
    case: Mapping[str, Any],
    metric_keys: Sequence[str],
    run_cfg: TailRiskConfig,
) -> Dict[str, Any]:
    label = str(case.get("label", "case"))
    rows: list[dict[str, Any]] = []

    for m in metric_keys:
        arr = _extract_trials_from_case(case, m)
        if arr is None:
            if run_cfg.require_trials:
                # No trials => can't compute credible VaR/CVaR
                rows.append(
                    {
                        "case": label,
                        "metric": m,
                        "note": "no_trials",
                    }
                )
                continue

            # fallback: single-point value only
            v = case.get("value", None)
            if v is None and "values" in case:
                v = case["values"].get(m, None)
            rows.append(
                {
                    "case": label,
                    "metric": m,
                    "p5": float("nan"),
                    "p10": float("nan"),
                    "p95": float("nan"),
                    "cvar": float("nan"),
                    "value": float(v) if v is not None else float("nan"),
                }
            )
            continue

        row: Dict[str, Any] = {
            "case": label,
            "metric": m,
            "p5": _percentile(arr, 5),
            "p10": _percentile(arr, 10),
            "p95": _percentile(arr, 95),
            "cvar": _cvar(arr, run_cfg.cvar_alpha),
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        }
        # covenant breach probability for DSCR-like metrics
        if "dscr" in m.lower():
            row["prob_breach"] = _prob_breach(arr, run_cfg.dscr_floor)
            row["dscr_floor"] = float(run_cfg.dscr_floor)

        rows.append(row)

    return {"rows": rows}
