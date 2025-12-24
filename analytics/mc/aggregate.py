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

from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

from analytics.contracts_v14 import MonteCarloResult


def _percentiles(arr: np.ndarray, ps: Sequence[int]) -> Dict[int, float]:
    """Compute percentiles for a single metric array.
    
    Args:
        arr: Metric values across all trials
        ps: Percentiles to compute (e.g., [5, 10, 50, 90, 95])
    
    Returns:
        Dictionary mapping percentile to value
    """
    return {int(p): float(np.percentile(arr, p)) for p in ps}


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
        percentiles: Percentiles to compute (default: P5, P10, P50, P90, P95)
    
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
        >>> dscr_trials = result.trials["dscr_min"]  # 1000 values
        >>> breach_prob = np.mean(dscr_trials < 1.30)
    
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

    # Extract raw trial arrays
    arrays: Dict[str, np.ndarray] = {}
    trials: Dict[str, List[float]] = {}
    
    for k in metric_keys:
        vals: List[float] = []
        for tm in trial_metrics:
            v = tm.get(k, None)
            if v is None:
                # Missing metric in this trial - skip or use NaN
                # For production: decide on NaN handling policy
                continue
            vals.append(float(v))
        
        if not vals:
            # No trials had this metric - skip it
            continue
            
        arr = np.array(vals, dtype=float)
        arrays[k] = arr
        trials[k] = vals  # Store raw list for MonteCarloResult.trials

    # Compute summary statistics
    summary: Dict[str, Any] = {}
    percentile_lookup: Dict[int, Dict[str, float]] = {p: {} for p in percentiles}
    
    for k, arr in arrays.items():
        if arr.size == 0:
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
    
    # Construct MonteCarloResult with raw trials
    result = MonteCarloResult(
        summary=summary,
        metadata=metadata,
        trials=trials,  # ✅ RAW TRIAL ARRAYS for lender analytics
        percentiles=percentile_lookup,
    )
    
    return result
