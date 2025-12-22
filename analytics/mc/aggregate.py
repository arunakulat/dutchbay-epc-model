from __future__ import annotations

"""
analytics.mc.aggregate

Aggregate per-trial outputs into MonteCarloResult.
Keep this vectorized, deterministic, and contract-stable.

No dependencies on engine internals.
"""

from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

# Import contract (if available); fallback to dict if not yet defined
try:
    from analytics.contracts_v14 import MonteCarloResult
except ImportError:
    # Fallback: MonteCarloResult will be a dict
    MonteCarloResult = dict  # type: ignore[misc, assignment]


def _compute_percentiles(
    arr: np.ndarray,
    percentiles: Sequence[int]
) -> Dict[int, float]:
    """
    Compute percentiles for array.
    
    Args:
        arr: 1D array of values
        percentiles: List of percentile values (e.g., [5, 10, 50, 90, 95])
    
    Returns:
        Dictionary mapping percentile → value
    """
    if arr.size == 0:
        return {int(p): np.nan for p in percentiles}
    
    return {int(p): float(np.percentile(arr, p)) for p in percentiles}


def aggregate_trials(
    *,
    trial_metrics: List[Mapping[str, Any]],
    base_config: Mapping[str, Any],
    param_names: Sequence[str],
    samples: np.ndarray,
    meta: Mapping[str, Any],
    percentiles: Sequence[int] = (5, 10, 50, 90, 95),
) -> MonteCarloResult:
    """
    Aggregate trial results into summary statistics.
    
    Computes mean, std, and percentiles for each metric across trials.
    
    Args:
        trial_metrics: List of metric dictionaries (one per trial)
        base_config: Base scenario configuration
        param_names: Names of stochastic parameters
        samples: Sample matrix [n_trials, n_params]
        meta: Metadata dictionary (seed, sampler, etc.)
        percentiles: Percentiles to compute (default: P5, P10, P50, P90, P95)
    
    Returns:
        MonteCarloResult with summary statistics
    
    Example:
        >>> trial_metrics = [
        ...     {"project_irr": 0.18, "project_npv": 57e6, "dscr_min": 1.32},
        ...     {"project_irr": 0.16, "project_npv": 52e6, "dscr_min": 1.28},
        ...     # ... more trials
        ... ]
        >>> result = aggregate_trials(
        ...     trial_metrics=trial_metrics,
        ...     base_config=cfg,
        ...     param_names=["revenue", "cost", "fx_rate"],
        ...     samples=samples_array,
        ...     meta={"seed": 42, "n_trials": 1000}
        ... )
        >>> result["summary"]["project_irr"]["mean"]
        0.17
    """
    # Canonical metric keys (adapt to your v14 pipeline outputs)
    # These should match the keys returned by evaluate_with_overrides()
    metric_keys = [
        "project_irr",
        "project_npv",
        "equity_irr",
        "equity_npv",
        "dscr_min",
        "llcr",
        "plcr",
        "max_debt_usd",
    ]
    
    # Extract metric arrays
    arrays: Dict[str, np.ndarray] = {}
    for key in metric_keys:
        vals: List[float] = []
        for tm in trial_metrics:
            v = tm.get(key, None)
            if v is not None:
                vals.append(float(v))
        
        if vals:
            arrays[key] = np.array(vals, dtype=float)
    
    # Compute summary statistics
    summary: Dict[str, Any] = {}
    for key, arr in arrays.items():
        if arr.size == 0:
            continue
        
        summary[key] = {
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            "median": float(np.median(arr)),
            "percentiles": _compute_percentiles(arr, percentiles),
            "min": float(arr.min()),
            "max": float(arr.max()),
            "count": int(arr.size),
        }
    
    # Add parameter statistics (useful for debugging correlations)
    param_stats: Dict[str, Any] = {}
    for i, name in enumerate(param_names):
        if i < samples.shape[1]:
            param_col = samples[:, i]
            param_stats[name] = {
                "mean": float(param_col.mean()),
                "std": float(param_col.std(ddof=1)) if param_col.size > 1 else 0.0,
                "min": float(param_col.min()),
                "max": float(param_col.max()),
            }
    
    # Assemble result
    # If MonteCarloResult is a Pydantic model, construct properly
    # Otherwise, return dict
    result_dict = {
        "summary": summary,
        "metadata": dict(meta),
        "param_stats": param_stats,
        "n_trials": len(trial_metrics),
    }
    
    if isinstance(MonteCarloResult, type) and hasattr(MonteCarloResult, "__dataclass_fields__"):
        # MonteCarloResult is a dataclass/Pydantic model
        return MonteCarloResult(**result_dict)  # type: ignore[call-arg]
    else:
        # Fallback: return dict
        return result_dict  # type: ignore[return-value]


def compute_covenant_breach_probability(
    metric_values: Sequence[float],
    covenant_threshold: float,
    breach_type: str = "below"
) -> float:
    """
    Compute probability of covenant breach.
    
    Useful for lender risk analysis:
    - P(DSCR < 1.2)
    - P(LLCR < 1.1)
    - P(Debt/Equity > 3.0)
    
    Args:
        metric_values: List of metric values from trials
        covenant_threshold: Covenant limit
        breach_type: "below" for min covenants (DSCR, LLCR),
                     "above" for max covenants (Debt/Equity)
    
    Returns:
        Breach probability [0, 1]
    
    Example:
        >>> dscr_values = [1.32, 1.28, 1.15, 1.40, 1.22, ...]
        >>> prob_breach = compute_covenant_breach_probability(
        ...     dscr_values,
        ...     covenant_threshold=1.2,
        ...     breach_type="below"
        ... )
        >>> print(f"P(DSCR < 1.2) = {prob_breach*100:.1f}%")
        P(DSCR < 1.2) = 12.3%
    """
    metric_array = np.array(metric_values, dtype=float)
    
    if metric_array.size == 0:
        return np.nan
    
    if breach_type == "below":
        breaches = np.sum(metric_array < covenant_threshold)
    elif breach_type == "above":
        breaches = np.sum(metric_array > covenant_threshold)
    else:
        raise ValueError(
            f"Invalid breach_type: {breach_type}. "
            f"Must be 'below' or 'above'."
        )
    
    probability = float(breaches) / float(metric_array.size)
    
    return probability


def compute_lender_risk_metrics(
    trial_metrics: List[Mapping[str, Any]],
    covenants: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """
    Compute lender-focused risk metrics from MC trials.
    
    Provides:
    - Covenant breach probabilities
    - Downside risk measures (P10, worst-case)
    - Probability of negative equity IRR/NPV
    
    Args:
        trial_metrics: List of trial results
        covenants: Optional covenant thresholds
            e.g., {"dscr_min": 1.2, "llcr": 1.1}
    
    Returns:
        Dictionary with lender risk metrics
    
    Example:
        >>> lender_metrics = compute_lender_risk_metrics(
        ...     trial_metrics=results,
        ...     covenants={"dscr_min": 1.2, "llcr": 1.1}
        ... )
        >>> lender_metrics["covenant_breach_prob"]["dscr_min"]
        0.123  # 12.3% chance of DSCR < 1.2
    """
    if covenants is None:
        covenants = {
            "dscr_min": 1.2,   # Typical lender minimum
            "llcr": 1.1,       # Typical lender minimum
        }
    
    lender_metrics: Dict[str, Any] = {
        "covenant_breach_prob": {},
        "downside_risk": {},
        "probability_negative": {},
    }
    
    # Covenant breach probabilities
    for metric, threshold in covenants.items():
        values = [t.get(metric) for t in trial_metrics if t.get(metric) is not None]
        if values:
            prob = compute_covenant_breach_probability(
                values,
                threshold,
                breach_type="below"
            )
            lender_metrics["covenant_breach_prob"][metric] = prob
    
    # Downside risk (P10 values)
    for metric in ["project_irr", "equity_irr", "dscr_min", "llcr"]:
        values = [t.get(metric) for t in trial_metrics if t.get(metric) is not None]
        if values:
            arr = np.array(values)
            lender_metrics["downside_risk"][f"{metric}_p10"] = float(
                np.percentile(arr, 10)
            )
    
    # Probability of negative returns
    for metric in ["project_npv", "equity_npv", "equity_irr"]:
        values = [t.get(metric) for t in trial_metrics if t.get(metric) is not None]
        if values:
            arr = np.array(values)
            prob_negative = float(np.sum(arr < 0)) / float(arr.size)
            lender_metrics["probability_negative"][metric] = prob_negative
    
    return lender_metrics


__all__ = [
    "aggregate_trials",
    "compute_covenant_breach_probability",
    "compute_lender_risk_metrics",
]
