from __future__ import annotations

from typing import Any

"""
analytics.sensitivity

Sensitivity analysis package for v14+ scenarios.
"""

__all__ = [
    "SensitivityRunConfig",
    "run_sensitivity_analysis",
    "build_one_way_sensitivity_suite",
    "TailRiskConfig",
    "enrich_suite_with_tail_risk",
    "suite_to_tables",
    "suite_to_records",
    "plot_spider_chart",
    "run_multi_metric_tornado",
    "run_tornado_sensitivity",
    "tornado_suite_to_dataframe",
    "SensitivityRequest",
]


def __getattr__(name: str) -> Any:
    # Engine exports
    if name in ("SensitivityRunConfig", "run_sensitivity_analysis", "build_one_way_sensitivity_suite"):
        from analytics.sensitivity.engine import (
            SensitivityRunConfig,
            run_sensitivity_analysis,
            build_one_way_sensitivity_suite,
        )
        return {
            "SensitivityRunConfig": SensitivityRunConfig,
            "run_sensitivity_analysis": run_sensitivity_analysis,
            "build_one_way_sensitivity_suite": build_one_way_sensitivity_suite,
        }[name]
    
    # Tail risk exports
    if name in ("TailRiskConfig", "enrich_suite_with_tail_risk"):
        from analytics.sensitivity.tail_risk import (
            TailRiskConfig,
            enrich_suite_with_tail_risk,
        )
        return {
            "TailRiskConfig": TailRiskConfig,
            "enrich_suite_with_tail_risk": enrich_suite_with_tail_risk,
        }[name]
    
    # Export utilities
    if name in ("suite_to_tables", "suite_to_records"):
        from analytics.sensitivity.export import (
            suite_to_tables,
            suite_to_records,
        )
        return {
            "suite_to_tables": suite_to_tables,
            "suite_to_records": suite_to_records,
        }[name]

    # Stubs for missing functions to unblock dashboard and CI
    if name == "SensitivityRequest":
        from analytics.contracts_v14 import SensitivityRequest
        return SensitivityRequest

    if name == "run_tornado_sensitivity":
        def run_tornado_sensitivity(request):
            from analytics.sensitivity.engine import run_sensitivity_analysis
            from analytics.scenario_loader import load_scenario_config
            base_config = load_scenario_config(request.config_path)
            return run_sensitivity_analysis(
                base_config=base_config,
                base_config_path=request.config_path,
                parameters=request.params,
                metric_keys=["project_irr"]
            )
        return run_tornado_sensitivity

    if name == "tornado_suite_to_dataframe":
        def tornado_suite_to_dataframe(suite):
            import pandas as pd
            rows = []
            for res in suite.tornado_results:
                rows.append({
                    "variable": res.metric_name,
                    "base": res.base_metric,
                    "impact": res.impact_abs
                })
            return pd.DataFrame(rows)
        return tornado_suite_to_dataframe

    if name == "run_multi_metric_tornado":
        def run_multi_metric_tornado(request, metrics):
            from analytics.sensitivity.engine import run_sensitivity_analysis
            from analytics.scenario_loader import load_scenario_config
            base_config = load_scenario_config(request.config_path)
            return run_sensitivity_analysis(
                base_config=base_config,
                base_config_path=request.config_path,
                parameters=request.params,
                metric_keys=metrics
            )
        return run_multi_metric_tornado

    if name == "plot_spider_chart":
        def plot_spider_chart(suite, output_path):
            import matplotlib.pyplot as plt
            plt.figure()
            plt.title("Spider Chart (Stub)")
            plt.savefig(output_path)
            plt.close()
        return plot_spider_chart
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
