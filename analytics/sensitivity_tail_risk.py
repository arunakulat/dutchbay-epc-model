from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from analytics.contracts_v14 import (
    MonteCarloResult,
    SensitivitySuite,
    TailRiskMetrics,
    TailRiskSnapshot,
)

FloatArray = NDArray[np.float64]


# ──────────────────────────────────────────────────────────────────────────────
# Legacy internal stats container (kept for backwards-compat tests)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TailRiskStats:
    """
    Internal tail-risk summary for a single metric.

    Kept for backwards compatibility with existing tests/imports.
    New callers should use TailRiskMetrics via `compute_tail_risk_metrics`.
    """

    confidence: float
    var: float
    cvar: float
    p10: float
    p90: float


# ──────────────────────────────────────────────────────────────────────────────
# Core helpers – metric extraction + tail-risk math (engine-agnostic)
# ──────────────────────────────────────────────────────────────────────────────


def _extract_metric_values(mc_result: MonteCarloResult, metric: str) -> FloatArray:
    """
    Extract a 1D float array of samples for `metric` from a MonteCarloResult.

    Contract / CESSPIT notes
    ------------------------
    - Contract-explicit: we only look at MonteCarloResult surfaces
      (metric_samples or raw_results).
    - Engine-agnostic: we do NOT depend on the Monte Carlo engine internals.
    - Traceable: error messages include the metric name to aid debugging.
    """
    # Prefer metric_samples if the engine populated it (most direct surface).
    metric_samples: Mapping[str, Sequence[float]] | None = getattr(
        mc_result, "metric_samples", None
    )
    if metric_samples is not None and metric in metric_samples:
        return np.asarray(metric_samples[metric], dtype=float)

    # Fallback to raw_results – expected to be a list of mappings.
    raw_results: Sequence[Mapping[str, float]] | None = getattr(
        mc_result, "raw_results", None
    )
    if raw_results is None:
        msg = f"MonteCarloResult has no samples for metric '{metric}'."
        raise ValueError(msg)

    values_list = [row[metric] for row in raw_results if metric in row]
    if not values_list:
        msg = f"No samples found for metric '{metric}'."
        raise ValueError(msg)

    return np.asarray(values_list, dtype=float)


def _validate_confidence(confidence: float) -> None:
    """
    Validate confidence level for tail-risk calculations.
    """
    if not 0.0 < confidence < 1.0:
        msg = f"confidence must be in (0, 1), got {confidence!r}"
        raise ValueError(msg)


def _compute_tail_risk_stats(values: FloatArray, confidence: float) -> TailRiskStats:
    """
    Compute VaR, CVaR, and P10/P90 for a 1D array of metric samples.

    VaR/CVaR are left-tail (downside) measures at the given confidence.

    This function returns the legacy TailRiskStats type for compatibility.
    New callers should use `compute_tail_risk_metrics`, which wraps this and
    returns the canonical TailRiskMetrics contract from contracts_v14.
    """
    _validate_confidence(confidence)

    if values.size == 0:
        raise ValueError("Cannot compute tail risk statistics on an empty sample.")

    # Left-tail VaR: q where only (1 - confidence) of outcomes are worse.
    var_pct = 100.0 * (1.0 - confidence)
    var = float(np.percentile(values, var_pct))
    p10 = float(np.percentile(values, 10.0))
    p90 = float(np.percentile(values, 90.0))

    mask = values <= var
    if np.any(mask):
        cvar = float(values[mask].mean())
    else:
        # Degenerate case: if nothing is <= VaR due to numeric quirks, fall back.
        cvar = var

    return TailRiskStats(
        confidence=confidence,
        var=var,
        cvar=cvar,
        p10=p10,
        p90=p90,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public CESSPIT / CASPER-aligned contract entrypoint
# ──────────────────────────────────────────────────────────────────────────────


def compute_tail_risk_metrics(
    *,
    mc_result: MonteCarloResult,
    metric: str,
    confidence: float = 0.9,
) -> TailRiskMetrics:
    """
    Compute canonical TailRiskMetrics for a given Monte Carlo metric.

    Parameters
    ----------
    mc_result:
        MonteCarloResult with raw metric draws (metric_samples or raw_results).
    metric:
        Name of the metric to analyze (e.g. "project_irr", "dscr_min").
        Must match the keys used in MonteCarloResult.raw_results.
    confidence:
        Confidence level for VaR/CVaR in (0, 1).
        Example: 0.9 → 10% left tail.

    Returns
    -------
    TailRiskMetrics
        Contract from `analytics.contracts_v14`, ready for CASPER / exporters.

    CESSPIT / GWTF notes
    --------------------
    - Contract-explicit: we expose TailRiskMetrics as the only output type.
    - Engine-agnostic: only depends on MonteCarloResult surfaces, not engine.
    - Scenario-stable: deterministic given (values, confidence).
    - Traceable: metric name and confidence are carried by the caller.
    """
    values = _extract_metric_values(mc_result, metric)
    stats = _compute_tail_risk_stats(values, confidence=confidence)

    # Median / p50 for the distribution – central tendency.
    p50 = float(np.percentile(values, 50.0))

    # Breach probability relative to VaR (mass in the left tail).
    breach_mask = values <= stats.var
    breach_prob = float(np.mean(breach_mask.astype(float)))

    return TailRiskMetrics(
        var=stats.var,
        cvar=stats.cvar,
        p10=stats.p10,
        p50=p50,
        p90=stats.p90,
        breach_prob=breach_prob,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tornado integration – tail risk overlay for sensitivity tables
# ──────────────────────────────────────────────────────────────────────────────


def _resolve_low_metric_column(tornado_df: pd.DataFrame) -> str:
    """
    Determine which column in the tornado DataFrame represents the "low" metric.

    Supports a few canonical spellings and falls back to a heuristic that
    looks for a column name containing both 'low' and 'metric' (case-insensitive).
    """
    preferred_names = [
        "Low Metric",
        "low_metric",
        "low_metric_value",
        "LowMetric",
    ]
    for name in preferred_names:
        if name in tornado_df.columns:
            return name

    # Heuristic fallback: first column matching both "low" and "metric".
    lowered = {col.lower(): col for col in tornado_df.columns}
    for key, original in lowered.items():
        if "low" in key and "metric" in key:
            return original

    msg = (
        "Could not resolve 'low metric' column in tornado DataFrame. "
        f"Available columns: {list(tornado_df.columns)!r}"
    )
    raise ValueError(msg)


def tornado_suite_to_dataframe(tornado_suite: SensitivitySuite) -> pd.DataFrame:
    """
    Thin wrapper around the export helper to keep the contract local.

    This indirection allows tests to monkeypatch
    `analytics.sensitivity_tail_risk.tornado_suite_to_dataframe`
    without touching the export module.

    GWTF alignment: analytics layer talks to exporters via stable contracts,
    not via ad-hoc DataFrame construction spread across the codebase.
    """
    import analytics.sensitivity_export as sxp

    return sxp.tornado_suite_to_dataframe(tornado_suite)


def enrich_tornado_with_tail_risk(
    tornado_suite: SensitivitySuite,
    mc_result: MonteCarloResult,
    metric: str = "project_irr",
    confidence: float = 0.9,
) -> pd.DataFrame:
    """
    Enrich a tornado table with VaR, CVaR, P10/P90, and breach probabilities.

    Parameters
    ----------
    tornado_suite:
        SensitivitySuite containing the underlying tornado data.
    mc_result:
        MonteCarloResult with sampled outcomes for `metric`.
    metric:
        Name of the metric to analyze (e.g. "project_irr", "dscr_min").
    confidence:
        Confidence level for VaR/CVaR (0.9 → 10% left-tail).

    Returns
    -------
    DataFrame
        Tornado table with additional columns:
        - 'VaR'
        - 'CVaR'
        - 'P10'
        - 'P90'
        - 'BreachProbability'  (probability that the sample < low metric)

    CESSPIT / CASPER alignment
    --------------------------
    - Contract-explicit: tornado input is SensitivitySuite, MC input is
      MonteCarloResult, tail-risk contract is TailRiskMetrics.
    - Engine-agnostic: no imports from finance/ engines; analytics-only.
    - Scenario-stable: deterministic given (tornado_suite, mc_result, metric).
    - Traceable: metrics and probabilities can be tied back to raw draws.
    """
    _validate_confidence(confidence)

    # Global tail-risk metrics for the chosen metric (for dashboards).
    # This is not written into the DataFrame but can be surfaced by callers
    # via `compute_tail_risk_metrics` if needed for CASPER payloads.
    values = _extract_metric_values(mc_result, metric)
    stats = _compute_tail_risk_stats(values, confidence=confidence)

    df = tornado_suite_to_dataframe(tornado_suite).copy()
    low_col = _resolve_low_metric_column(df)

    # Row-wise breach probability: P(sample < low_threshold) per driver.
    thresholds = df[low_col].to_numpy(dtype=float)
    breach_probs = np.array(
        [float(np.mean(values < threshold)) for threshold in thresholds],
        dtype=float,
    )

    # Add tail-risk columns (constant across rows for this metric).
    df["VaR"] = stats.var
    df["CVaR"] = stats.cvar
    df["P10"] = stats.p10
    df["P90"] = stats.p90
    df["BreachProbability"] = breach_probs

    return df


def build_tail_risk_snapshot(
    *,
    metric: str,
    values: FloatArray,
    confidence: float,
) -> TailRiskSnapshot:
    """
    Build a TailRiskSnapshot from raw Monte Carlo samples.

    This is the canonical way to derive CASPER-visible tail-risk metrics
    from a single metric distribution.

    Parameters
    ----------
    metric:
        Name of the metric (e.g. "project_irr", "dscr_min").
    values:
        1D array of Monte Carlo samples for the metric.
    confidence:
        Confidence level in (0, 1) for VaR / CVaR (0.9 → 10% left-tail).

    Returns
    -------
    TailRiskSnapshot
        Contract-explicit, JSON-friendly summary for CASPER / dashboards.
    """
    stats = _compute_tail_risk_stats(values=values, confidence=confidence)

    # Median (P50) is not included in TailRiskStats for now, so we compute it
    # explicitly here to keep the contract honest and transparent.
    p50 = float(np.percentile(values, 50.0))

    # Breach probability: P(sample < VaR), using the same VaR threshold that
    # feeds the CVaR calculation. This is lender-readable and stable.
    breach_prob = float(np.mean(values < stats.var))

    return TailRiskSnapshot(
        metric=metric,
        confidence=confidence,
        var=stats.var,
        cvar=stats.cvar,
        p10=stats.p10,
        p50=p50,
        p90=stats.p90,
        breach_probability=breach_prob,
    )


def build_tail_risk_snapshots_for_metrics(
    *,
    mc_result: MonteCarloResult,
    metrics: Sequence[str],
    confidence: float,
) -> dict[str, TailRiskSnapshot]:
    """
    Convenience helper: build TailRiskSnapshot objects for multiple metrics.

    This keeps the evaluation / CASPER layer thin:
    - Pulls sample vectors via _extract_metric_values.
    - Delegates summary logic to build_tail_risk_snapshot.

    Parameters
    ----------
    mc_result:
        MonteCarloResult with raw metric samples.
    metrics:
        Sequence of metric names to summarise (e.g. ["project_irr", "dscr_min"]).
    confidence:
        Confidence level in (0, 1) for VaR / CVaR.

    Returns
    -------
    dict[str, TailRiskSnapshot]
        Mapping from metric name -> TailRiskSnapshot.
    """
    snapshots: dict[str, TailRiskSnapshot] = {}

    for metric in metrics:
        values = _extract_metric_values(mc_result, metric)
        snapshots[metric] = build_tail_risk_snapshot(
            metric=metric,
            values=values,
            confidence=confidence,
        )

    return snapshots
