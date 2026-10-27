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


def test_corporate_tax_rate_direction_on_levered_equity_follows_the_carried_shortfall(
    base_config,
):
    """With the debt-service shortfall carried, the levered equity IRR no longer RISES with
    the corporate tax rate at the basecase.

    This test used to assert the opposite ("interest-shield dominated": equity IRR -2.19% at
    15% vs -1.90% at 45%). P2-F3-01 (#1398) showed that rise was manufactured by the equity
    waterfall's clamp. The basecase has sub-1.0x years late in the tenor, and a higher tax
    rate re-sizes the debt so those years' shortfall grows (USD 2.10M across years 13-14 at
    15%, USD 3.14M across years 12-14 at 45%). The clamp dropped that shortfall, so the
    extra burden of a high-tax debt profile never reached equity. Carried through the DSRA,
    it does: equity IRR is -2.780% at 15% and -2.787% at 45%, a fall of under one basis
    point, so the shield and the shortfall now roughly offset.

    Both halves are pinned: the high-tax case carries the larger shortfall, and its equity
    IRR is no higher than the low-tax case's.
    """
    shock = (
        _one_way(base_config, "tax.corporate_tax_rate", 0.30)
        .tornado_results[0]
        .shock_results[0]
    )
    assert shock.high_case <= shock.low_case

    def _shortfall(rate: float) -> float:
        out = evaluate_with_overrides(
            config_path=None,
            raw_config=copy.deepcopy(base_config),
            overrides={"tax.corporate_tax_rate": rate},
            return_full_result=True,
        )
        summary = out["equity_distribution"]["equity_summary"]
        return float(summary["total_debt_service_shortfall_usd"])

    assert _shortfall(0.45) > _shortfall(0.15)


def test_corporate_tax_rate_also_moves_project_irr(base_config):
    """project_irr is after-tax in this model, so it must respond too."""
    tornado = _one_way(
        base_config, "tax.corporate_tax_rate", 0.30, metric="project_irr"
    ).tornado_results[0]
    assert tornado.impact_abs > 0.0


def test_tax_holiday_reduces_equity_irr_wasted_depreciation(base_config):
    """At the realistic 5.9% FX-drift baseline MORE tax-holiday years REDUCE equity IRR.

    Direction REVERSED by the 5.9% FX-drift re-baseline. A tax holiday wastes the
    early-year depreciation (and interest) tax shields — they fall in years with no tax
    to offset and cannot be carried far enough forward, while the steeper LKR depreciation
    has already thinned the later (taxed) years' USD income. Net: equity IRR ~0.0581 at
    0 holiday years vs ~0.0496 at 10. (At the old 3% drift more holiday improved equity
    IRR — 0.1014 vs 0.0925 — the conventional direction.)
    """
    assert _equity_irr(base_config, {"tax.tax_holiday_years": 10}) < _equity_irr(
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
    # F5-01 binds the parametric operating FX path to COD (two years after close),
    # while keeping the authored close spot for tax basis. The steeper operating
    # conversion makes this fixed-70%-geared basecase loss-making for equity.
    assert -0.03 < base["equity_irr"] < -0.01
    assert 0.03 < base["project_irr"] < 0.05
