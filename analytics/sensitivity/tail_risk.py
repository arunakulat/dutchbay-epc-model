"""Tail risk analysis for sensitivity results.

Analyzes downside scenarios from sensitivity sweeps:
- Identify worst-case parameter combinations
- Calculate conditional value-at-risk (CVaR)
- Stress testing scenarios

Integrates with:
- analytics.sensitivity.engine (TornadoResult input)
- analytics.contracts_v14 (SensitivitySuite)

DOLPHIN #10b: Removed unused `param_name` variable

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import SensitivitySuite


@dataclass(frozen=True)
class TailRiskConfig:
    """Configuration for tail risk analysis.
    
    Attributes:
        percentile: Threshold for tail events (e.g., 0.05 for 5th percentile)
        combinations: Whether to analyze parameter combinations
    """
    percentile: float = 0.05
    combinations: bool = False


@dataclass(frozen=True)
class TailRiskSnapshot:
    """Snapshot of tail risk metrics.
    
    Attributes:
        param_name: Parameter varied
        worst_case_value: Worst metric value observed
        worst_case_shock: Shock that caused worst case
        p5_value: 5th percentile metric value
        downside_scenarios: List of (shock, metric_value) for tail events
    """
    param_name: str
    worst_case_value: float
    worst_case_shock: float
    p5_value: float
    downside_scenarios: Sequence[Tuple[float, float]]


def analyze_tail_risk(
    suite: SensitivitySuite,
    config: Optional[TailRiskConfig] = None,
) -> Dict[str, TailRiskSnapshot]:
    """Analyze tail risk from sensitivity results.
    
    Args:
        suite: Sensitivity analysis results
        config: Tail risk configuration (default: 5th percentile)
        
    Returns:
        Dict mapping parameter names to tail risk snapshots
        
    Example:
        >>> tail_risks = analyze_tail_risk(suite)
        >>> capex_risk = tail_risks["capex"]
        >>> print(f"Worst case: {capex_risk.worst_case_value:.2%}")
    """
    config = config or TailRiskConfig()
    
    results: Dict[str, TailRiskSnapshot] = {}
    tornado_results = suite.tornado_results
    
    for tornado in tornado_results:
        # Extract data from TornadoResult
        snap = _build_tornado_tail_snapshot(
            tornado=tornado,
            percentile=config.percentile,
        )
        results[tornado.param_name] = snap
    
    return results


def _build_tornado_tail_snapshot(
    tornado: Any,
    percentile: float,
) -> TailRiskSnapshot:
    """Build tail risk snapshot from tornado result.
    
    Args:
        tornado: TornadoResult object
        percentile: Tail threshold (e.g., 0.05)
        
    Returns:
        TailRiskSnapshot with worst-case and percentile metrics
    """
    # Extract shock-value pairs
    low_shock = float(tornado.low_shock)
    high_shock = float(tornado.high_shock)
    low_value = float(tornado.low_value)
    high_value = float(tornado.high_value)
    
    # Determine worst case (minimize metric)
    if low_value < high_value:
        worst_value = low_value
        worst_shock = low_shock
    else:
        worst_value = high_value
        worst_shock = high_shock
    
    # For simple 2-point tornado, use linear interpolation for percentile
    values = np.array([low_value, high_value])
    p_value = float(np.percentile(values, percentile * 100))
    
    # Downside scenarios (below baseline)
    baseline = float(tornado.baseline_value)
    downside = [
        (shock, value)
        for shock, value in [(low_shock, low_value), (high_shock, high_value)]
        if value < baseline
    ]
    
    return TailRiskSnapshot(
        param_name=tornado.param_name,
        worst_case_value=worst_value,
        worst_case_shock=worst_shock,
        p5_value=p_value,
        downside_scenarios=tuple(downside),
    )
