"""
analytics.sensitivity.dscr

DSCR-focused sensitivity helpers.

Scope:
- Pure transforms + wrappers around engine-level sensitivity runs
- No plotting
- No direct pipeline imports (only evaluation gateway via engine)

This module is intentionally minimal: pure DSCR-sensitivity transforms/wrappers over
engine-level sensitivity runs.
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
class DscrSensitivityConfig:
    dscr_metric_key: str = "dscr_min"
    dscr_floor: float = 1.30


# Module-level singletons: shared read-only defaults built once at import time
# (both configs are frozen) — behaviour-identical to the old argument-default
# `= X()` calls but B008-compliant (#753).
_DEFAULT_DSCR_SENSITIVITY_CONFIG = DscrSensitivityConfig()
_DEFAULT_SENSITIVITY_RUN_CONFIG = SensitivityRunConfig()


def run_dscr_one_way(
    *,
    base_config: Mapping[str, Any],
    parameter: ParameterRangeConfig,
    cfg: DscrSensitivityConfig = _DEFAULT_DSCR_SENSITIVITY_CONFIG,
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
) -> SensitivitySuite:
    """
    Convenience wrapper: one-way sensitivity for DSCR(min).

    Notes:
    - Covenant evaluation (breach probabilities) belongs in tail_risk enrichment
      and/or downstream reporting. This wrapper is deterministic only.
    """
    return build_one_way_sensitivity_suite(
        base_config=base_config,
        parameter=parameter,
        metric_key=cfg.dscr_metric_key,
        run_cfg=run_cfg,
    )
