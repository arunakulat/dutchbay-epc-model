"""Audit-R1: the sensitivity engine must reject unknown parameter names.

An override on a variable_name that does not resolve to an existing config path silently
produces a FLAT/zero tornado bar (the override just creates a new, unused key), which
misleads a lender's sensitivity read. The engine now fails loud in strict mode.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity.engine import (
    SensitivityRunConfig,
    build_one_way_sensitivity_suite,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _param(name: str) -> ParameterRangeConfig:
    return ParameterRangeConfig(
        variable_name=name, base_value=1.0, low_pct=-10.0, high_pct=10.0, label=name
    )


def test_valid_parameter_resolves_and_sweeps() -> None:
    cfg = load_scenario_config(LENDER)
    suite = build_one_way_sensitivity_suite(
        base_config=cfg,
        parameter=_param("project.capacity_factor"),
        metric_key="project_irr",
    )
    assert len(suite.tornado_results) == 1


def test_unknown_parameter_raises_in_strict_mode() -> None:
    cfg = load_scenario_config(LENDER)
    with pytest.raises(ValueError, match="does not resolve"):
        build_one_way_sensitivity_suite(
            base_config=cfg,
            parameter=_param("opex_annual"),  # not a real config path
            metric_key="project_irr",
        )


def test_unknown_parameter_warns_when_not_strict() -> None:
    cfg = load_scenario_config(LENDER)
    # Non-strict: must NOT raise (it warns and produces a — flat — bar instead).
    suite = build_one_way_sensitivity_suite(
        base_config=cfg,
        parameter=_param("opex_annual"),
        metric_key="project_irr",
        run_cfg=SensitivityRunConfig(strict=False),
    )
    assert len(suite.tornado_results) == 1
