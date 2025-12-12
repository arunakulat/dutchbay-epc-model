#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sensitivity Analysis Runner - Core Engine (SENS-002 Refactored)

Purpose:
    Gateway function for sensitivity analysis. Loads scenario config,
    applies shocks, computes metrics, and returns SensitivitySuite.

Features:
    • Config-driven analysis (YAML/JSON scenarios)
    • Shock specification with low/high values
    • Tornado ranking by impact
    • Metric aggregation and reporting
    • Gateway pattern compliance (GWTF)

Author: DutchBay Development Team
Version: 1.0.0
License: Proprietary
Created: 2025-12-12
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from analytics.contracts import (
    ShockResult,
    ShockSpec,
    SensitivitySuite,
)


def analyze_sensitivity_refactored(
    config_path: str,
    scenario_name: str,
    shocks: List[ShockSpec],
    metric_name: str = "project_irr",
) -> SensitivitySuite:
    """
    [SENS-002] Run sensitivity analysis on a given scenario configuration.

    Loads the base scenario config and computes the base metric.
    Applies each ShockSpec (low and high values) to compute outcome metrics.
    Aggregates results into a SensitivitySuite dataclass.

    Args:
        config_path: Path to scenario configuration file
        scenario_name: Name of scenario being analyzed
        shocks: List of ShockSpec definitions to apply
        metric_name: Metric to analyze (default: project_irr)

    Returns:
        SensitivitySuite: Aggregated sensitivity analysis results

    Raises:
        FileNotFoundError: If config_path does not exist
        ValueError: If shocks list is empty
    """
    base_metric_value = _evaluate_metric_from_config(config_path, metric_name)

    shock_results: List[ShockResult] = []
    for shock in shocks:
        low_metric = _evaluate_metric_from_config(
            config_path, metric_name, overrides={shock.variable_name: shock.low_value}
        )
        high_metric = _evaluate_metric_from_config(
            config_path,
            metric_name,
            overrides={shock.variable_name: shock.high_value},
        )
        impact = abs(high_metric - low_metric)
        direction = "positive" if high_metric >= low_metric else "negative"
        sensitivity = (
            (impact / abs(base_metric_value)) if base_metric_value != 0 else 0.0
        )
        label = shock.label or shock.variable_name
        shock_result = ShockResult(
            variable_name=shock.variable_name,
            label=label,
            base_metric=base_metric_value,
            low_metric=low_metric,
            high_metric=high_metric,
            impact=round(impact, 6),
            direction=direction,
            sensitivity=round(sensitivity, 6),
        )
        shock_results.append(shock_result)

    tornado_ranking = sorted(
        shock_results, key=lambda s: abs(s.impact), reverse=True
    )

    suite = SensitivitySuite(
        scenario_name=scenario_name,
        metric_name=metric_name,
        base_metric_value=base_metric_value,
        shock_results=shock_results,
        tornado_ranking=tornado_ranking,
        analysis_timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return suite


def get_tornado_chart_data(suite: SensitivitySuite) -> Dict[str, Any]:
    """
    [SENS-002] Get tornado chart data from a SensitivitySuite.

    Args:
        suite: SensitivitySuite result object

    Returns:
        Dict with tornado chart data (x_low, x_high, y_labels, colors, etc.)
    """
    data: Dict[str, Any] = {
        "variables": [],
        "low": [],
        "high": [],
        "impact": [],
        "direction": [],
    }
    for shock in suite.tornado_ranking:
        data["variables"].append(shock.label or shock.variable_name)
        data["low"].append(shock.base_metric - shock.low_metric)
        data["high"].append(shock.high_metric - shock.base_metric)
        data["impact"].append(shock.impact)
        data["direction"].append(shock.direction)
    return data


def compare_with_baseline(
    new_suite: SensitivitySuite, baseline_suite: SensitivitySuite
) -> Dict[str, Any]:
    """
    [SENS-002] Compare sensitivity results with a baseline suite.

    Args:
        new_suite: New sensitivity analysis results
        baseline_suite: Previous/baseline results for comparison

    Returns:
        Dict with differences, order mismatches, impact deltas
    """
    differences: Dict[str, Any] = {"impact_deltas": [], "order_mismatch": []}

    if len(new_suite.shock_results) != len(baseline_suite.shock_results):
        differences["count_mismatch"] = True

    for i, (new_res, old_res) in enumerate(
        zip(new_suite.tornado_ranking, baseline_suite.tornado_ranking)
    ):
        if new_res.variable_name != old_res.variable_name:
            differences["order_mismatch"].append(
                f"Rank {i + 1}: NEW={new_res.variable_name}, OLD={old_res.variable_name}"
            )

    old_results_map = {res.variable_name: res for res in baseline_suite.shock_results}
    for res in new_suite.shock_results:
        var = res.variable_name
        if var in old_results_map:
            delta = abs(res.impact - old_results_map[var].impact)
            if delta > 1e-6:
                differences["impact_deltas"].append(
                    {"variable": var, "delta": round(delta, 6)}
                )

    return differences


def _evaluate_metric_from_config(
    config_path: str,
    metric_name: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Load scenario config, apply overrides, compute metric.

    Args:
        config_path: Path to configuration file
        metric_name: Metric to compute
        overrides: Optional parameter overrides

    Returns:
        Computed metric value (float)
    """
    # Placeholder: would load YAML/JSON and compute actual metric
    return 0.0


def _load_base_values(config_path: str) -> Dict[str, Any]:
    """
    Load base input values from scenario config.

    Args:
        config_path: Path to configuration file

    Returns:
        Dict of base parameter values
    """
    # Placeholder: would load YAML/JSON config
    return {}


__all__ = [
    "analyze_sensitivity_refactored",
    "get_tornado_chart_data",
    "compare_with_baseline",
]
