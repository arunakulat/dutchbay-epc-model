# ruff: noqa: E402
from __future__ import annotations

"""
analytics.mc.aggregate

Aggregate per-trial outputs into MonteCarloResult.
Keep this vectorized and deterministic.

Sprint 18 Enhancement:
- Stores raw trial arrays in MonteCarloResult.trials
- Enables lender-grade breach probability calculations
- Supports worst-year DSCR P95 downside statistics
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from analytics.contracts_v14 import MonteCarloResult


def _percentiles(arr: np.ndarray, ps: Sequence[int]) -> Dict[int, float]:
    """Compute percentiles for a single metric array.

    Each requested percentile is computed independently via ``np.percentile``,
    so extending ``ps`` is strictly additive: pre-existing levels keep their
    exact values.

    Args:
        arr: Metric values across all trials
        ps: Percentiles to compute (e.g., [1, 5, 10, 50, 90, 95, 99])

    Returns:
        Dictionary mapping percentile to value
    """
    return {int(p): float(np.percentile(arr, p)) for p in ps}


#: Default raw-percentile levels reported by :func:`aggregate_trials` when the
#: scenario does not pin ``monte_carlo.percentiles``. P99 is first-class (#599)
#: because senior-debt loan-size capping is conventionally set at P99.
#:
#: Lender exceedance convention (tail direction, consistent with #563 in
#: ``analytics.mc.exports``): these keys are RAW percentiles of the metric
#: distribution. For higher-is-better metrics (DSCR, IRR, NPV, LLCR, PLCR) the
#: lender's "P99" — the value exceeded 99% of the time — is the RAW 1st
#: percentile (key ``1`` below), NOT the raw 99th. The raw 99th (key ``99``) is
#: the favourable upside tail. Both tails ship by default so downside-P99
#: consumers never mistake the upside for it.
DEFAULT_PERCENTILES: tuple[int, ...] = (1, 5, 10, 50, 90, 95, 99)


def aggregate_trials(
    *,
    trial_metrics: List[Mapping[str, Any]],
    base_config: Mapping[str, Any],
    param_names: Sequence[str],
    samples: np.ndarray,
    meta: Mapping[str, Any],
    percentiles: Sequence[int] = DEFAULT_PERCENTILES,
) -> MonteCarloResult:
    """
    Aggregate per-trial metrics into MonteCarloResult.

    Sprint 18 Enhancement: Stores raw trial arrays in result.trials for
    lender-grade analytics (breach probability, worst-case downside).

    Args:
        trial_metrics: List of metric dicts, one per trial
            Example: [{"dscr_min": 1.32, "project_irr": 0.14}, ...]
        base_config: Base scenario configuration
        param_names: Parameter names that were varied
        samples: LHS sample matrix [n_trials, n_params]
        meta: Execution metadata (seed, sampler, correlation_enabled)
        percentiles: RAW percentiles to compute (default: ``DEFAULT_PERCENTILES``
            = P1, P5, P10, P50, P90, P95, P99). P99 is first-class for
            senior-debt loan-size capping (#599). Tail direction: for
            higher-is-better metrics the lender exceedance "P99" is the raw
            1st percentile (key 1); the raw 99th is the upside tail — see
            ``DEFAULT_PERCENTILES`` and the #563 convention in
            ``analytics.mc.exports``.

    Returns:
        MonteCarloResult with:
        - summary: {metric: {mean, std, percentiles}}
        - trials: {metric: [val1, val2, ...]}  # RAW ARRAYS
        - metadata: execution metadata
        - percentiles: lookup table

    Example:
        >>> trials = [
        ...     {"dscr_min": 1.32, "project_irr": 0.14},
        ...     {"dscr_min": 1.45, "project_irr": 0.13},
        ...     # ... 998 more trials
        ... ]
        >>> result = aggregate_trials(
        ...     trial_metrics=trials,
        ...     base_config=cfg,
        ...     param_names=["capex", "tariff"],
        ...     samples=lhs_samples,
        ...     meta={"seed": 42, "n_trials": 1000}
        ... )
        >>>
        >>> # Access raw trials for breach probability
        >>> from analytics.core.covenant_breach import prob_breach
        >>> dscr_trials = result.trials["dscr_min"]  # 1000 values
        >>> defined_dscr = np.asarray([v for v in dscr_trials if v is not None], dtype=float)
        >>> breach_prob = prob_breach(defined_dscr, 1.30)  # disclose its metric_coverage too

    Note:
        Canonical KPI names expected in trial_metrics:
        - dscr_min: Minimum DSCR over project life
        - project_irr: Unlevered project IRR
        - project_npv: Unlevered project NPV
        - llcr: Loan Life Coverage Ratio
        - plcr: Project Life Coverage Ratio
        - equity_irr: Levered equity IRR (if equity modeled)

        Add/remove metric keys based on your canonical KPI set.
    """
    # Canonical metric keys - adjust to match your KPI naming
    metric_keys = [
        "dscr_min",
        "project_irr",
        "project_npv",
        "llcr",
        "plcr",
        "equity_irr",
        "equity_npv",
    ]

    # O-5 (#1474): keep the original trial index in EVERY raw metric array. None is
    # an explicit unavailable observation, never zero. Statistics use each metric's
    # own defined sample; deleting an undefined equity IRR must not delete its DSCR.
    # The earlier complete-case policy solved ragged arrays (#571) by introducing
    # selection bias. Aligned nullable rows preserve both identity and coverage.
    def _num(v: Any) -> Optional[float]:
        if v is None or isinstance(v, bool):
            return None
        try:
            f = float(v)
        except (TypeError, ValueError, OverflowError):
            return None
        return f if np.isfinite(f) else None

    declared_keys = [k for k in metric_keys if any(k in tm for tm in trial_metrics)]
    normalised = [
        {key: _num(tm.get(key)) for key in declared_keys} for tm in trial_metrics
    ]
    n_trials = len(trial_metrics)
    arrays: Dict[str, np.ndarray] = {}
    trials: Dict[str, List[Optional[float]]] = {}
    coverage: Dict[str, Any] = {}
    for key in declared_keys:
        aligned = [row[key] for row in normalised]
        defined = [value for value in aligned if value is not None]
        arrays[key] = np.asarray(defined, dtype=float)
        trials[key] = aligned
        undefined = sum(1 for tm in trial_metrics if key in tm and tm[key] is None)
        missing = sum(1 for tm in trial_metrics if key not in tm)
        invalid = n_trials - len(defined) - undefined - missing
        if len(defined) == n_trials:
            status = "defined"
        elif defined:
            status = "partial"
        elif invalid:
            status = "invalid"
        else:
            status = "undefined"
        coverage[key] = {
            "total_count": n_trials,
            "defined_count": len(defined),
            "undefined_count": undefined,
            "missing_count": missing,
            "invalid_count": invalid,
            "status": status,
        }

    # Compute summary statistics
    summary: Dict[str, Any] = {}
    percentile_lookup: Dict[int, Dict[str, float]] = {p: {} for p in percentiles}

    for k, arr in arrays.items():
        if arr.size == 0:
            summary[k] = {
                "status": coverage[k]["status"],
                "mean": None,
                "std": None,
                "min": None,
                "max": None,
                "percentiles": {},
            }
            continue

        pctl_dict = _percentiles(arr, percentiles)

        summary[k] = {
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            "percentiles": pctl_dict,
            "min": float(arr.min()),
            "max": float(arr.max()),
        }

        # Build percentile lookup table
        for p, val in pctl_dict.items():
            percentile_lookup[p][k] = val

    # Build metadata
    metadata = dict(meta)
    metadata["n_metrics"] = len(arrays)
    metadata["metric_keys"] = list(arrays.keys())
    metadata["metric_coverage_schema"] = "dutchbay.mc.metric_coverage.v1"
    metadata["metric_coverage"] = coverage
    metadata["undefined_metrics"] = [
        key for key, facts in coverage.items() if facts["status"] == "undefined"
    ]
    metadata["trial_alignment"] = "input_order_null_placeholders"
    # Surface toy-fallback usage so a degenerate run (real evaluation failed on
    # every trial, fabricated KPIs substituted) is detectable rather than silent.
    # toy_fallback_count == n_trials means NO real evaluation succeeded.
    metadata["toy_fallback_count"] = sum(
        1 for tm in trial_metrics if tm.get("_toy_fallback")
    )

    # Populate the legacy flat scalar surface from the structured aggregates, so
    # consumers reading MonteCarloResult.iterations / .project_irr_p10 /
    # .success_rate() see the real run instead of the dataclass defaults (0/None).
    # Derived from summary + percentile_lookup (no recomputation). A trial is failed/
    # degraded if it produced NO canonical metric OR fell back to the toy-metric fallback
    # (fabricated KPIs from a failed full-v14 eval, tagged _toy_fallback by the engine).
    # Otherwise success_rate() would report fabricated trials as successful production
    # runs (audit R1).
    invalid_trials = [
        any(
            key in tm and tm[key] is not None and row[key] is None
            for key in declared_keys
        )
        for tm, row in zip(trial_metrics, normalised, strict=True)
    ]
    n_failed = sum(
        1
        for tm, invalid in zip(trial_metrics, invalid_trials, strict=True)
        if tm.get("_toy_fallback") or not any(k in tm for k in metric_keys) or invalid
    )
    metadata["invalid_trial_count"] = sum(invalid_trials)
    # Partial metric coverage remains visible but is not an evaluation failure.
    # Defined observations from malformed/failed rows also retain their identity;
    # the failure/invalid counters prevent treating those runs as clean evidence.
    metadata["partial_trial_count"] = sum(
        1 for row in normalised if any(value is None for value in row.values())
    )

    def _stat(metric: str, key: str) -> Optional[float]:
        s = summary.get(metric)
        value = s.get(key) if isinstance(s, dict) else None
        return float(value) if value is not None else None

    def _pct(metric: str, p: int) -> Optional[float]:
        return percentile_lookup.get(p, {}).get(metric)

    # Construct MonteCarloResult with raw trials + the flat compatibility surface.
    result = MonteCarloResult(
        summary=summary,
        metadata=metadata,
        trials=trials,  # RAW TRIAL ARRAYS for lender analytics
        percentiles=percentile_lookup,
        iterations=n_trials,
        n_iterations=n_trials,
        failed_iterations=n_failed,
        project_irr_mean=_stat("project_irr", "mean"),
        project_irr_std=_stat("project_irr", "std"),
        project_irr_p10=_pct("project_irr", 10),
        project_irr_p50=_pct("project_irr", 50),
        project_irr_p90=_pct("project_irr", 90),
        project_npv_mean=_stat("project_npv", "mean"),
        project_npv_p10=_pct("project_npv", 10),
        project_npv_p50=_pct("project_npv", 50),
        project_npv_p90=_pct("project_npv", 90),
        dscr_min_p10=_pct("dscr_min", 10),
        dscr_min_p50=_pct("dscr_min", 50),
        # Provenance: surface the sampler actually used (meta["sampler"], set by the
        # engine to the validated "lhs"|"sobol") as the first-class result field so the
        # lender-facing risk blocks can attribute bands to their generation method,
        # instead of leaving it as the None default while the identity hides in the loose
        # metadata dict (#648a, CCCDIR). Falls back to None if a direct caller omits it.
        sampling_method=meta.get("sampler"),
    )

    return result
