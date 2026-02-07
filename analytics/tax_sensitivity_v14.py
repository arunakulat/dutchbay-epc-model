from __future__ import annotations

"""
analytics.tax_sensitivity_v14

**DEPRECATED**: This module is a shim for backward compatibility.

New code should use:
    from analytics.sensitivity.tax import run_tax_one_way, TaxSensitivityConfig

This file will be removed in a future version.
"""

import warnings
from typing import Any

warnings.warn(
    "analytics.tax_sensitivity_v14 is deprecated. Use 'from analytics.sensitivity.tax import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Import new API
from analytics.sensitivity.tax import *  # noqa: F401,F403


# ═════════════════════════════════════════════════════════════════════════════
# BACKWARDS-COMPATIBILITY STUBS (Legacy API surface)
# ═════════════════════════════════════════════════════════════════════════════
# These functions existed in the v14 API but were removed during refactor.
# Stubs allow imports to succeed (unblocking test collection) while providing
# clear migration guidance if functions are actually called.


def analyze_delay_period_sensitivity(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Legacy function from tax_sensitivity_v14.

    Migration Guide:
        Old API (removed):
            from analytics.tax_sensitivity_v14 import analyze_delay_period_sensitivity
            result = analyze_delay_period_sensitivity(...)

        New API (use this instead):
            from analytics.sensitivity.tax import run_tax_one_way, TaxSensitivityConfig
            from analytics.contracts_v14 import ParameterRangeConfig

            param = ParameterRangeConfig(
                path=["tax", "delay_period_months"],
                values=[0, 6, 12, 18, 24]
            )

            result = run_tax_one_way(
                base_config=your_config,
                parameter=param,
                cfg=TaxSensitivityConfig(metric_key="project_irr")
            )

    Raises:
        NotImplementedError: This function was removed in favor of run_tax_one_way()
    """
    raise NotImplementedError(
        "analyze_delay_period_sensitivity() was removed. "
        "Use run_tax_one_way() with ParameterRangeConfig instead. "
        "See analytics.sensitivity.tax for migration guide."
    )


def analyze_tax_rate_sensitivity(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Legacy function from tax_sensitivity_v14.

    Migration Guide:
        Old API (removed):
            from analytics.tax_sensitivity_v14 import analyze_tax_rate_sensitivity
            result = analyze_tax_rate_sensitivity(...)

        New API (use this instead):
            from analytics.sensitivity.tax import run_tax_one_way, TaxSensitivityConfig
            from analytics.contracts_v14 import ParameterRangeConfig

            param = ParameterRangeConfig(
                path=["tax", "corporate_rate_pct"],
                values=[24, 26, 28, 30, 32]
            )

            result = run_tax_one_way(
                base_config=your_config,
                parameter=param,
                cfg=TaxSensitivityConfig(metric_key="project_irr")
            )

    Raises:
        NotImplementedError: This function was removed in favor of run_tax_one_way()
    """
    raise NotImplementedError(
        "analyze_tax_rate_sensitivity() was removed. "
        "Use run_tax_one_way() with ParameterRangeConfig instead. "
        "See analytics.sensitivity.tax for migration guide."
    )


def generate_tax_tornado_chart(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Legacy function from tax_sensitivity_v14.

    Migration Guide:
        Tornado chart generation is now handled by visualization layer.
        Use analytics.sensitivity.engine.build_tornado_chart() instead.

    Raises:
        NotImplementedError: This function was removed
    """
    raise NotImplementedError(
        "generate_tax_tornado_chart() was removed. "
        "Use analytics.sensitivity.engine.build_tornado_chart() for visualization."
    )


__all__ = [
    # New API (from analytics.sensitivity.tax)
    "run_tax_one_way",
    "TaxSensitivityConfig",
    # Legacy API stubs (for backward compat imports)
    "analyze_delay_period_sensitivity",
    "analyze_tax_rate_sensitivity",
    "generate_tax_tornado_chart",
]
