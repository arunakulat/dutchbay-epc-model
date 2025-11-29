from __future__ import annotations

from analytics.sensitivity_v14 import (
    MultiMetricTornadoResult,
    SensitivityRequest,
    TornadoResult,
    enrich_tornado_with_tail_risk,
    multi_metric_suite_to_dataframe,
    optimize_from_sensitivity_insights,
    plot_spider_chart,
    plot_tornado_chart,
    plot_two_way_heatmap,
    run_breakeven_parameter,
    run_multi_metric_tornado,
    run_tornado_sensitivity,
    run_two_way_sensitivity,
    tornado_suite_to_dataframe,
)

__all__ = [
    "SensitivityRequest",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "run_tornado_sensitivity",
    "run_multi_metric_tornado",
    "run_breakeven_parameter",
    "tornado_suite_to_dataframe",
    "multi_metric_suite_to_dataframe",
    "plot_tornado_chart",
    "plot_spider_chart",
    "plot_two_way_heatmap",
    "enrich_tornado_with_tail_risk",
    "optimize_from_sensitivity_insights",
    "run_two_way_sensitivity",
]
"""
analytics.sensitivity

High-level sensitivity hub package for v14+ API.

This package exposes the v14 sensitivity API in a single import surface,
acting as a thin facade over concrete modules in the parent analytics package
(sensitivity_v14, sensitivity_export, etc.).

Typical usage::

    from analytics.sensitivity import (
        SensitivityRequest,
        run_tornado_sensitivity,
        run_multi_metric_tornado,
        tornado_suite_to_dataframe,
        plot_tornado_chart,
    )

Downstream code should import from ``analytics.sensitivity`` instead of
reaching into ``sensitivity_v14`` directly.
"""
# EOF
