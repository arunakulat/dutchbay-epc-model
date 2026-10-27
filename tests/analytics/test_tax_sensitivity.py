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


def test_corporate_tax_rate_direction_on_levered_equity_is_shield_dominated(
    base_config,
):
    """At the realistic 5.9% FX-drift baseline the LEVERED equity IRR RISES with the
    corporate tax rate: more tax costs equity.

    This asserted the OPPOSITE until #1397, and the reversal it recorded turns out to
    have been an artifact of the sizing basis rather than of the shields. The debt
    schedule was sized on CFADS carrying tax computed with no interest deducted, so a
    higher rate shrank the sized debt service and flattered equity enough to outweigh
    the extra tax on its profit share. With the shield priced correctly on both the
    sizing and the equity path, the conventional direction returns: equity IRR is
    -0.02865 at 15% against -0.02938 at 45%. The UNLEVERED project IRR falls with tax
    too (see test_corporate_tax_rate_also_moves_project_irr), so the two surfaces now
    agree on the sign instead of disagreeing.
    """
    shock = (
        _one_way(base_config, "tax.corporate_tax_rate", 0.30)
        .tornado_results[0]
        .shock_results[0]
    )
    # higher tax (high_case) -> LOWER levered equity IRR
    assert shock.high_case < shock.low_case


def test_corporate_tax_rate_also_moves_project_irr(base_config):
    """project_irr is after-tax in this model, so it must respond too."""
    tornado = _one_way(
        base_config, "tax.corporate_tax_rate", 0.30, metric="project_irr"
    ).tornado_results[0]
    assert tornado.impact_abs > 0.0


def test_tax_holiday_is_inert_where_interest_already_shelters_the_income(base_config):
    """On this basecase a tax holiday changes nothing, and that is the correct answer.

    This used to assert that more holiday years REDUCED equity IRR, through wasted
    early-year depreciation. #1397 showed that conclusion was an artifact: the holiday
    was reaching the KPIs through a debt schedule sized on CFADS that carried tax
    computed with no interest deducted. Size on the tax the SPV actually pays and the
    first eleven operating years of this scenario carry ZERO tax whether or not a
    holiday is declared -- interest plus depreciation already shelter all of it --
    measured directly on the sizing rows. A holiday over years 1-10 therefore shelters
    nothing that was not already sheltered, and the equity IRR is bit-identical.

    A test that asserts "no change" is worthless without a control, so the second half
    turns the shield off. With interest non-deductible there IS tax in the early years,
    and the holiday then moves equity IRR by 350bps, in the conventional direction.
    """
    assert _equity_irr(base_config, {"tax.tax_holiday_years": 10}) == pytest.approx(
        _equity_irr(base_config, {"tax.tax_holiday_years": 0}), abs=1e-12
    )

    sheltered = _equity_irr(
        base_config,
        {"tax.tax_holiday_years": 10, "tax.interest_deductibility": False},
    )
    taxed = _equity_irr(
        base_config,
        {"tax.tax_holiday_years": 0, "tax.interest_deductibility": False},
    )
    assert sheltered > taxed + 0.01, (
        "the holiday is inert even where there is tax to shelter, so the first "
        "assertion above is passing vacuously"
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
