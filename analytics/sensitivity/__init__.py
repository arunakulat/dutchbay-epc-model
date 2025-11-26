# analytics/sensitivity/__init__.py
"""
High-level sensitivity hub package.

This package exposes the v14+ sensitivity API in a single import surface:

    from analytics.sensitivity import (
        SensitivityRequest,
        run_tornado_sensitivity,
        run_multi_metric_tornado,
        run_breakeven_parameter,
        tornado_suite_to_dataframe,
        breakeven_results_to_dataframe,
        multi_metric_suite_to_dataframe,
        plot_tornado_chart,
        plot_spider_chart,
        enrich_tornado_with_tail_risk,
        optimize_from_sensitivity_insights,
        run_two_way_sensitivity,
        plot_two_way_heatmap,
    )

It is a thin facade over the concrete modules that live in the parent
`analytics` package (sensitivity_v14, sensitivity_export, etc.).
"""

from __future__ import annotations

from ..sensitivity_export import (breakeven_results_to_dataframe,
                                  multi_metric_suite_to_dataframe,
                                  tornado_suite_to_dataframe)
from ..sensitivity_heatmap import plot_two_way_heatmap, run_two_way_sensitivity
from ..sensitivity_pareto import optimize_from_sensitivity_insights
from ..sensitivity_tail_risk import enrich_tornado_with_tail_risk
from ..sensitivity_v14 import (SensitivityRequest, run_breakeven_parameter,
                               run_multi_metric_tornado,
                               run_tornado_sensitivity)
from ..sensitivity_visualization import plot_spider_chart, plot_tornado_chart
