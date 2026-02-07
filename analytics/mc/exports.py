from __future__ import annotations

"""
analytics.mc.exports

Lender-style exports for Monte Carlo results.

Outputs:
- risk table suitable for IC memo / lender pack
  * P50 / P90 for key metrics
  * Prob(DSCR < covenant_floor)
  * Worst-year DSCR P95 (conservative downside statistic)
- optional CASPER-ready payload blocks (dict-of-tables)

Notes:
- This module is intentionally "thin" and pure: it does not run simulations.
- It assumes MonteCarloResult carries either:
    (A) raw trial arrays in result.trials[metric] (preferred), OR
    (B) summary percentiles + metadata that includes enough to compute breach prob.
  If only summary is present, breach probabilities cannot be computed correctly; we fail fast.

GWTF/CASPER:
- Keep this import-safe; pandas is optional (guarded import).
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

from analytics.contracts_v14 import MonteCarloResult


@dataclass(frozen=True)
class CovenantSpec:
    dscr_floor: float = 1.30


DEFAULT_PERCENTILES: Tuple[int, int, int] = (50, 90, 95)


def _get_trial_array(result: MonteCarloResult, key: str) -> np.ndarray:
    """
    Pull a raw per-trial array for metric key.
    This function defines the contract: to compute breach probabilities and robust stats,
    we need raw trial values.

    Supported locations (pick one and standardize across the codebase):
      - result.trials: Dict[str, Sequence[float]]
      - result.metadata["trials"][key]
    """
    # Option A: attribute access
    trials = getattr(result, "trials", None)
    if isinstance(trials, Mapping) and key in trials:
        arr = np.asarray(trials[key], dtype=float)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        return arr

    # Option B: metadata fallback
    md = getattr(result, "metadata", {})
    if isinstance(md, Mapping):
        t = md.get("trials", None)
        if isinstance(t, Mapping) and key in t:
            arr = np.asarray(t[key], dtype=float)
            if arr.ndim != 1:
                arr = arr.reshape(-1)
            return arr

    raise KeyError(
        f"MonteCarloResult does not expose raw trial array for '{key}'. "
        "To compute lender-grade breach probabilities, store per-trial metric arrays "
        "in result.trials (preferred) or metadata['trials']."
    )


def _p(arr: np.ndarray, pctl: int) -> float:
    return float(np.percentile(arr, int(pctl)))


def dscr_breach_probability(dscr: np.ndarray, *, floor: float) -> float:
    if dscr.size == 0:
        return float("nan")
    return float(np.mean(dscr < float(floor)))


def worst_year_dscr_p95(dscr_min_by_trial: np.ndarray) -> float:
    """
    Conservative downside statistic:
    "Worst-year DSCR P95" interpreted as the 5th percentile of dscr_min distribution.
    (Because P95 downside = only 5% of outcomes are worse.)
    """
    if dscr_min_by_trial.size == 0:
        return float("nan")
    return float(np.percentile(dscr_min_by_trial, 5))


def build_lender_risk_table(
    result: MonteCarloResult,
    *,
    covenant: CovenantSpec = CovenantSpec(),
    metric_map: Optional[Mapping[str, str]] = None,
) -> "pd.DataFrame":
    """
    Build a lender-style risk table.

    Required raw arrays:
      - dscr_min (per-trial minimum DSCR over life or sculpt horizon)
    Recommended raw arrays:
      - project_irr
      - project_npv
      - llcr
      - plcr

    metric_map lets you adapt to your canonical KPI naming:
      e.g. {"dscr_min": "dscr_min", "project_irr": "equity_irr"} etc.

    Returns pandas DataFrame (preferred for exports).
    """
    if pd is None:
        raise RuntimeError("pandas is required for build_lender_risk_table()")

    mm = dict(metric_map or {})
    # canonical internal keys
    k_dscr = mm.get("dscr_min", "dscr_min")
    k_irr = mm.get("project_irr", "project_irr")
    k_npv = mm.get("project_npv", "project_npv")
    k_llcr = mm.get("llcr", "llcr")
    k_plcr = mm.get("plcr", "plcr")

    # Raw arrays
    dscr = _get_trial_array(result, k_dscr)

    rows: list[dict[str, Any]] = []

    def add_metric(label: str, key: str) -> None:
        try:
            arr = _get_trial_array(result, key)
        except KeyError:
            return
        rows.append(
            {
                "metric": label,
                "P50": _p(arr, 50),
                "P90": _p(arr, 90),
                "P95": _p(arr, 95),
                "mean": float(arr.mean()) if arr.size else float("nan"),
                "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            }
        )

    # Core metrics table
    add_metric("DSCR (min)", k_dscr)
    add_metric("Project IRR", k_irr)
    add_metric("Project NPV", k_npv)
    add_metric("LLCR", k_llcr)
    add_metric("PLCR", k_plcr)

    # Covenant rows
    prob_breach = dscr_breach_probability(dscr, floor=covenant.dscr_floor)
    dscr_p95_downside = worst_year_dscr_p95(dscr)

    rows.append(
        {
            "metric": f"Prob(DSCR < {covenant.dscr_floor:.2f})",
            "P50": float("nan"),
            "P90": float("nan"),
            "P95": float("nan"),
            "mean": prob_breach,
            "std": float("nan"),
        }
    )
    rows.append(
        {
            "metric": "Worst-year DSCR (P95 downside)",
            "P50": float("nan"),
            "P90": float("nan"),
            "P95": float("nan"),
            "mean": dscr_p95_downside,
            "std": float("nan"),
        }
    )

    df = pd.DataFrame(rows)
    # nicer ordering for lender packs
    preferred_order = [
        "DSCR (min)",
        f"Prob(DSCR < {covenant.dscr_floor:.2f})",
        "Worst-year DSCR (P95 downside)",
        "LLCR",
        "PLCR",
        "Project IRR",
        "Project NPV",
    ]
    df["__order"] = df["metric"].apply(lambda x: preferred_order.index(x) if x in preferred_order else 999)
    df = df.sort_values("__order").drop(columns="__order").reset_index(drop=True)
    return df


def build_casper_risk_blocks(
    result: MonteCarloResult,
    *,
    covenant: CovenantSpec = CovenantSpec(),
    metric_map: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    Return a CASPER-friendly dict-of-tables.

    Structure:
      {
        "lender_risk_table": <pd.DataFrame or list[dict]>,
        "covenant": {"dscr_floor": ..., "prob_breach": ..., "worst_year_dscr_p95_downside": ...},
      }

    CASPER payload builder can accept the DataFrame directly (preferred),
    or you can convert to records for JSON payloads.
    """
    df = build_lender_risk_table(result, covenant=covenant, metric_map=metric_map)

    # Compute covenant stats from raw DSCR
    mm = dict(metric_map or {})
    k_dscr = mm.get("dscr_min", "dscr_min")
    dscr = _get_trial_array(result, k_dscr)

    covenant_block = {
        "dscr_floor": float(covenant.dscr_floor),
        "prob_breach": dscr_breach_probability(dscr, floor=covenant.dscr_floor),
        "worst_year_dscr_p95_downside": worst_year_dscr_p95(dscr),
        "n_trials": int(len(dscr)),
    }

    return {
        "lender_risk_table": df,
        "covenant": covenant_block,
    }
