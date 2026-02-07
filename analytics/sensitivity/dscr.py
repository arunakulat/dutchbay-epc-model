from __future__ import annotations

"""
analytics.sensitivity.dscr

DSCR-focused sensitivity helpers.

Scope:
- Pure transforms + wrappers around engine-level sensitivity runs
- No plotting
- No direct pipeline imports (only evaluation gateway via engine)

This module is intentionally minimal as a placeholder.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.sensitivity.engine import SensitivityRunConfig, build_one_way_sensitivity_suite


@dataclass(frozen=True)
class DscrSensitivityConfig:
    dscr_metric_key: str = "dscr_min"
    dscr_floor: float = 1.30


def run_dscr_one_way(
    *,
    base_config: Mapping[str, Any],
    parameter: ParameterRangeConfig,
    cfg: DscrSensitivityConfig = DscrSensitivityConfig(),
    run_cfg: SensitivityRunConfig = SensitivityRunConfig(),
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
