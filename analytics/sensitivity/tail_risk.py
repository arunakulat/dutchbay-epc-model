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

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import SensitivitySuite, TornadoResult


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
    """Enrich ``suite.metadata`` with lender-grade tail-risk blocks.

    Produces two complementary views and attaches them to the suite metadata:

    * ``metadata["tail_risk"]`` — a per-parameter table (one row per tornado)
      carrying the base value plus the downside/upside/impact observed across
      that parameter's shocks.
    * ``metadata["tail_risk_summary"]`` — a ``{metric_name: {snapshot}}``
      mapping aggregating the worst downside / best upside / largest impact
      across all parameters. This is the shape consumed by
      :func:`analytics.casper.casper_payload._tail_risk_from_metadata`, so the
      CASPER payload can surface it directly (a flat run-summary would have been
      silently dropped by that consumer).

    The suite is a frozen dataclass, so a new instance carrying the enriched
    metadata is returned rather than mutating in place.

    Note:
        Snapshots are derived from the suite's tornado/shock data. For full
        distributional VaR/CVaR from Monte Carlo trial arrays, see the
        ``_build_case_tail_snapshot`` trial-array path below — a caller can wire
        it once per-case MC arrays are attached to each scenario's metadata.
    """
    if not run_cfg.enabled:
        return suite

    md = dict(getattr(suite, "metadata", {}) or {})

    tail_table: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    # SensitivitySuite shape (single metric). An empty tornado set leaves both
    # blocks empty rather than fabricating a snapshot.
    if getattr(suite, "tornado_results", None):
        metric_key = str(suite.metric)
        rows = [
            _tornado_tail_stats(tornado=tornado) for tornado in suite.tornado_results
        ]
        tail_table.extend(rows)
        summary[metric_key] = _aggregate_metric_snapshot(rows=rows, run_cfg=run_cfg)

    md["tail_risk"] = tail_table
    md["tail_risk_summary"] = summary

    # SensitivitySuite is a frozen dataclass — build a new instance carrying the
    # enriched metadata rather than mutating in place. A prior setattr-based
    # implementation always raised FrozenInstanceError (silently caught),
    # dropping the tail-risk enrichment entirely.
    return replace(suite, metadata=md)


def _tornado_tail_stats(*, tornado: TornadoResult) -> dict[str, Any]:
    """Honest per-parameter tail snapshot from a tornado's shock results.

    Derives downside/upside/impact from the shock cases actually present
    (``low_case`` / ``high_case`` / ``impact_abs`` are optional on
    :class:`~analytics.contracts_v14.ShockResult`, so missing values are
    skipped). A tornado with no usable shocks collapses to its base value.
    """
    base = float(tornado.base_metric)
    lows = [s.low_case for s in tornado.shock_results if s.low_case is not None]
    highs = [s.high_case for s in tornado.shock_results if s.high_case is not None]
    impacts = [s.impact_abs for s in tornado.shock_results if s.impact_abs is not None]
    return {
        "parameter": str(tornado.label or tornado.metric_name),
        "metric": str(tornado.metric_name),
        "base_value": base,
        "downside": float(min(lows)) if lows else base,
        "upside": float(max(highs)) if highs else base,
        "worst_impact_abs": (
            float(max(impacts)) if impacts else float(tornado.impact_abs)
        ),
        "n_shocks": len(tornado.shock_results),
    }


def _aggregate_metric_snapshot(
    *,
    rows: Sequence[Mapping[str, Any]],
    run_cfg: TailRiskConfig,
) -> dict[str, Any]:
    """Aggregate per-parameter rows into one per-metric tail snapshot.

    Shaped for the CASPER consumer (``{metric_name: {snapshot}}``): the worst
    downside / best upside / largest impact across all parameters, plus the
    tail-risk run parameters for provenance.
    """
    base = float(rows[0]["base_value"]) if rows else float("nan")
    downsides = [float(r["downside"]) for r in rows]
    upsides = [float(r["upside"]) for r in rows]
    impacts = [float(r["worst_impact_abs"]) for r in rows]
    return {
        "base_value": base,
        "downside": min(downsides) if downsides else base,
        "upside": max(upsides) if upsides else base,
        "worst_impact_abs": max(impacts) if impacts else 0.0,
        "n_parameters": len(rows),
        "cvar_alpha": float(run_cfg.cvar_alpha),
        "percentiles": list(run_cfg.percentiles),
        "dscr_floor": float(run_cfg.dscr_floor),
    }


def _extract_trials_from_case(
    case: Mapping[str, Any], metric_key: str
) -> Optional[np.ndarray]:
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
