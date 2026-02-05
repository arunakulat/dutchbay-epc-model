from __future__ import annotations

from typing import Any

"""
analytics.sensitivity

Sensitivity analysis package for v14+ scenarios.

CRITICAL: This __init__.py uses lazy loading via __getattr__ to avoid
circular imports with analytics.evaluation_v14.

Public API:
- run_sensitivity_analysis(...)
- build_one_way_sensitivity_suite(...)
- suite_to_tables(...)
- suite_to_records(...)
- TailRiskConfig
- SensitivityRunConfig
"""

__all__ = [
    "SensitivityRunConfig",
    "run_sensitivity_analysis",
    "build_one_way_sensitivity_suite",
    "TailRiskConfig",
    "enrich_suite_with_tail_risk",
    "suite_to_tables",
    "suite_to_records",
]


def __getattr__(name: str) -> Any:
    """
    Lazy module loading to prevent circular imports.

    This pattern ensures that importing 'analytics.sensitivity' does NOT
    trigger import of analytics.evaluation_v14 at import time.
    """
    # Engine exports
    if name in (
        "SensitivityRunConfig",
        "run_sensitivity_analysis",
        "build_one_way_sensitivity_suite",
    ):
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

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
