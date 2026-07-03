"""
analytics.mc.exports

Lender-style exports for Monte Carlo results.

Outputs:
- risk table suitable for IC memo / lender pack
  * P50 plus the P90/P95 DOWNSIDE (exceedance) tail for key higher-is-better
    metrics (DSCR, IRR, NPV, LLCR, PLCR): P90 = 10th pct, P95 = 5th pct, i.e. the
    value exceeded 90%/95% of the time (consistent with the AEP P90 convention).
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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import numpy as np

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore[assignment]

from analytics.contracts_v14 import MonteCarloResult
from analytics.core.covenant_breach import is_floor_pinned, prob_breach


@dataclass(frozen=True)
class CovenantSpec:
    dscr_floor: float = 1.30


# Module-level singleton: the default covenant is built once at import time and
# shared read-only (CovenantSpec is frozen), which is behaviour-identical to the
# old `covenant=CovenantSpec()` argument default but B008-compliant (#753).
_DEFAULT_COVENANT_SPEC = CovenantSpec()


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
    """Noise-tolerant DSCR covenant-breach fraction.

    Delegates to :func:`analytics.core.covenant_breach.prob_breach` so a dual-DSCR
    sculpt that pins per-trial min-DSCR at exactly ``floor`` is not fabricated as an
    85-93% breach (#725); the true probability there is 0.0.
    """
    return prob_breach(dscr, floor)


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
    covenant: CovenantSpec = _DEFAULT_COVENANT_SPEC,
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

    def add_metric(label: str, key: str, *, higher_is_better: bool = True) -> None:
        try:
            arr = _get_trial_array(result, key)
        except KeyError:
            return
        # Lender/exceedance convention: the "P90"/"P95" columns report the DOWNSIDE
        # (bankable) tail -- the value exceeded 90%/95% of the time -- consistent with
        # the "Worst-year DSCR (P95 downside)" row below (5th pct) and the AEP P90 =
        # 10th-pct convention in analytics.capital_risk_layer_v14. For higher-is-better
        # metrics (DSCR, IRR, NPV, LLCR, PLCR) that adverse tail is the LOW end, so
        # P90 = 10th pct and P95 = 5th pct. Reporting the raw 90th/95th pct here would
        # emit the favourable upside and understate tail risk to a lender.
        if higher_is_better:
            p90, p95 = _p(arr, 10), _p(arr, 5)
        else:
            p90, p95 = _p(arr, 90), _p(arr, 95)
        rows.append(
            {
                "metric": label,
                "P50": _p(arr, 50),
                "P90": p90,
                "P95": p95,
                "mean": float(arr.mean()) if arr.size else float("nan"),
                "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            }
        )

    # Core metrics table. Every metric here is higher-is-better, so P90/P95 are the
    # downside (exceedance) tail -- see add_metric().
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
    df["__order"] = df["metric"].apply(
        lambda x: preferred_order.index(x) if x in preferred_order else 999
    )
    df = df.sort_values("__order").drop(columns="__order").reset_index(drop=True)
    return df


def build_casper_risk_blocks(
    result: MonteCarloResult,
    *,
    covenant: CovenantSpec = _DEFAULT_COVENANT_SPEC,
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
        # Disclose-don't-mislead: when a dual-DSCR sculpt pins per-trial min-DSCR at
        # the floor, prob_breach is a structural 0.0 with no distributional signal --
        # read the lender tail from LLCR/PLCR and the balloon, not min-DSCR (#725).
        "floor_pinned": bool(is_floor_pinned(dscr, covenant.dscr_floor)),
        "worst_year_dscr_p95_downside": worst_year_dscr_p95(dscr),
        "n_trials": int(len(dscr)),
    }

    return {
        "lender_risk_table": df,
        "covenant": covenant_block,
    }
