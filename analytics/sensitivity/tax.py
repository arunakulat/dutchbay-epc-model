"""
analytics.sensitivity.tax

Tax sensitivity utilities.

Placeholder module:
- Provides small wrappers for common tax-related sensitivity parameters
- No direct pipeline imports; use engine orchestration

Typical tax knobs (examples; adapt to your schema):
- tax.corporate_rate
- tax.holiday_years
- tax.wht_dividends
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.sensitivity.engine import (
    SensitivityRunConfig,
    build_one_way_sensitivity_suite,
)


@dataclass(frozen=True)
class TaxSensitivityConfig:
    metric_key: str = "project_irr"


# Module-level singletons: shared read-only defaults built once at import time
# (both configs are frozen) — behaviour-identical to the old argument-default
# `= X()` calls but B008-compliant (#753).
_DEFAULT_TAX_SENSITIVITY_CONFIG = TaxSensitivityConfig()
_DEFAULT_SENSITIVITY_RUN_CONFIG = SensitivityRunConfig()


def run_tax_one_way(
    *,
    base_config: Mapping[str, Any],
    parameter: ParameterRangeConfig,
    cfg: TaxSensitivityConfig = _DEFAULT_TAX_SENSITIVITY_CONFIG,
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
) -> SensitivitySuite:
    """
    Convenience wrapper: one-way sensitivity for a tax parameter on a chosen metric.
    """
    return build_one_way_sensitivity_suite(
        base_config=base_config,
        parameter=parameter,
        metric_key=cfg.metric_key,
        run_cfg=run_cfg,
    )
