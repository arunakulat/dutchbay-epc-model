#!/usr/bin/env python
"""Tax sensitivity tests — migrated to the contract API analytics.sensitivity.tax.

The legacy analytics.tax_sensitivity_v14 functions (analyze_delay_period_sensitivity,
analyze_tax_rate_sensitivity, generate_tax_tornado_chart, ...) were removed; the shim
now raises NotImplementedError with migration guidance. This suite exercises the
replacement — analytics.sensitivity.tax.run_tax_one_way — on the canonical basecase and
asserts real tax economics: impact, direction, after-tax project IRR response, the
tax-holiday lever, suite structure, and a baseline regression pin.

Framework Compliance:
- TEST-01: regression pins for tax-model behavior
- CESSPIT: no hardcoded model params (drives the canonical scenario config)
- TYPE-01: type hints on helpers

Run:
    pytest tests/analytics/test_tax_sensitivity.py -v
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.sensitivity.tax import TaxSensitivityConfig, run_tax_one_way

BASECASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")


@pytest.fixture
def base_config() -> dict[str, Any]:
    if not BASECASE.is_file():
        pytest.skip(f"canonical scenario missing: {BASECASE}")
    from omegaconf import OmegaConf

    return OmegaConf.to_container(OmegaConf.load(BASECASE), resolve=True)


def _one_way(
    cfg: Mapping[str, Any],
    variable: str,
    base_value: float,
    *,
    metric: str = "equity_irr",
    low_pct: float = -50.0,
    high_pct: float = 50.0,
):
    return run_tax_one_way(
        base_config=cfg,
        parameter=ParameterRangeConfig(
            variable_name=variable,
            base_value=base_value,
            low_pct=low_pct,
            high_pct=high_pct,
            points=3,
            label=variable.split(".")[-1],
        ),
        cfg=TaxSensitivityConfig(metric_key=metric),
    )


def _equity_irr(cfg: Mapping[str, Any], overrides: Mapping[str, Any]) -> float:
    out = evaluate_with_overrides(
        config_path=None, raw_config=copy.deepcopy(cfg), overrides=overrides
    )
    kpis = out.get("kpis", out) if hasattr(out, "get") else out
    return float(kpis["equity_irr"])


def test_corporate_tax_rate_has_material_impact(base_config):
    """A ±50% sweep of the corporate tax rate must register a real impact."""
    tornado = _one_way(base_config, "tax.corporate_tax_rate", 0.30).tornado_results[0]
    assert tornado.impact_abs > 0.0


def test_higher_corporate_tax_lowers_equity_irr(base_config):
    """Lower tax (low case) should yield a higher equity IRR than the high case."""
    shock = (
        _one_way(base_config, "tax.corporate_tax_rate", 0.30)
        .tornado_results[0]
        .shock_results[0]
    )
    assert shock.low_case > shock.high_case


def test_corporate_tax_rate_also_moves_project_irr(base_config):
    """project_irr is after-tax in this model, so it must respond too."""
    tornado = _one_way(
        base_config, "tax.corporate_tax_rate", 0.30, metric="project_irr"
    ).tornado_results[0]
    assert tornado.impact_abs > 0.0


def test_tax_holiday_improves_equity_irr(base_config):
    """More tax-holiday years must improve (not reduce) equity IRR."""
    assert _equity_irr(base_config, {"tax.tax_holiday_years": 10}) > _equity_irr(
        base_config, {"tax.tax_holiday_years": 0}
    )


def test_suite_structure_and_base_kpis(base_config):
    suite = _one_way(base_config, "tax.corporate_tax_rate", 0.30)
    assert suite.metric == "equity_irr"
    assert suite.tornado_results
    assert {"equity_irr", "project_irr"} <= set(suite.base_kpis)


def test_basecase_returns_regression_pins(base_config):
    """Pin baseline returns so a tax-model regression is caught."""
    base = _one_way(base_config, "tax.corporate_tax_rate", 0.30).base_kpis
    # equity_irr re-baselined by the 2026-06 debt-service-orphan fix (audit finding 2.1):
    # the bridge period's scheduled service is now charged to equity, lowering the
    # basecase equity IRR from ~0.095 to ~0.071. (An earlier alignment fix had already
    # removed a phantom covenant lockup that had inflated this to ~0.30.) The Wave-1
    # equity-waterfall fix then releases the DSRA to the sponsor at maturity, lifting it
    # ~0.071 -> ~0.083.
    assert 0.06 < base["equity_irr"] < 0.08
    # project_irr re-baselined by the construction-lag fix (audit finding 2.0): ~7.9%.
    assert 0.07 < base["project_irr"] < 0.09
