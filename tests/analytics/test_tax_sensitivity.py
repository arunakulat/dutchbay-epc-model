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


def _kpi(cfg: Mapping[str, Any], overrides: Mapping[str, Any], key: str) -> Any:
    out = evaluate_with_overrides(
        config_path=None, raw_config=copy.deepcopy(cfg), overrides=overrides
    )
    kpis = out.get("kpis", out) if hasattr(out, "get") else out
    return kpis.get(key)


def _equity_irr(cfg: Mapping[str, Any], overrides: Mapping[str, Any]) -> float:
    return float(_kpi(cfg, overrides, "equity_irr"))


def test_corporate_tax_rate_has_material_impact(base_config):
    """A +-50% sweep of the corporate tax rate must register a real impact, on the
    position its cash actually reaches.

    #1736: on this basecase that position is the lenders', not equity's. Interest and
    depreciation shelter every operating year's income except years 12 and 13 (measured
    on the equity-facing rows), and both fall under the lock-up, so their after-tax cash
    is trapped and then paid to the post-maturity balloon, which is never cleared. A
    higher rate therefore leaves a larger balloon unpaid and does not touch equity's
    cash flows. The equity-IRR half of this used to pass only because the sweep was
    sized on CFADS that left the trapped cash to equity.
    """
    tornado = _one_way(
        base_config, "tax.corporate_tax_rate", 0.30, metric="balloon_residual"
    ).tornado_results[0]
    assert tornado.impact_abs > 1e5  # USD; about 0.79M across the sweep


def test_corporate_tax_rate_direction_on_levered_equity_is_shield_dominated(
    base_config,
):
    """More corporate tax costs the levered position, in the conventional direction.

    #1397 restored the conventional sign by sizing on the tax the SPV pays. #1736 then
    pays the post-maturity balloon from the cash the SPV holds, so on this basecase the
    tax that is paid (years 12 and 13, both locked up) comes out of the balloon, not
    out of equity: a higher rate leaves MORE balloon unpaid and equity's flows are
    unchanged (asserted bit-for-bit below, so a change that lets taxed cash reach equity
    again is caught).

    With the interest shield removed there is tax in the years equity is paid, and the
    conventional direction must then show on equity itself.
    """
    shock = (
        _one_way(base_config, "tax.corporate_tax_rate", 0.30, metric="balloon_residual")
        .tornado_results[0]
        .shock_results[0]
    )
    # higher tax (high_case) -> a LARGER unpaid balloon
    assert shock.high_case > shock.low_case
    assert _equity_irr(base_config, {"tax.corporate_tax_rate": 0.45}) == pytest.approx(
        _equity_irr(base_config, {"tax.corporate_tax_rate": 0.15}), abs=1e-9
    )

    unsheltered = {"tax.interest_deductibility": False}
    low = _kpi(
        base_config, {**unsheltered, "tax.corporate_tax_rate": 0.15}, "equity_npv"
    )
    high = _kpi(
        base_config, {**unsheltered, "tax.corporate_tax_rate": 0.45}, "equity_npv"
    )
    assert high < low


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
    and the holiday then moves equity's position materially, in the conventional
    direction. #1736: the control reads equity NPV, not equity IRR. Without the holiday
    the unsheltered case never pays equity back, so its IRR is undefined (and reported
    as such, #1525); the NPV moves by about USD 6.6M.

    #1505: the tolerance is 1e-9, not 1e-12. Deducting the balloon interest the sweep
    pays makes the sizing loop run 17 passes here instead of 4, and it stops once no
    row's CFADS moves by more than one cent, so two runs that should land on the same
    fixed point are only guaranteed to agree to that tolerance, not to the bit
    (measured 2.1e-12 apart in equity IRR). 1e-9 is still a thousand times tighter than any
    effect the second half of this test measures.
    """
    assert _equity_irr(base_config, {"tax.tax_holiday_years": 10}) == pytest.approx(
        _equity_irr(base_config, {"tax.tax_holiday_years": 0}), abs=1e-9
    )

    sheltered = _kpi(
        base_config,
        {"tax.tax_holiday_years": 10, "tax.interest_deductibility": False},
        "equity_npv",
    )
    taxed = _kpi(
        base_config,
        {"tax.tax_holiday_years": 0, "tax.interest_deductibility": False},
        "equity_npv",
    )
    assert sheltered > taxed + 1e6, (
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
    # P2-F3-01 (#1398) moved the band down: the basecase's sub-1.0x years now cost equity
    # their shortfall instead of being clamped to zero (-2.90% -> -3.14% at 27e0cb10).
    # #1736 moved it again (-3.14% -> -7.52%): the post-maturity sweep now pays the
    # balloon from the reserve and the trapped cash before anything reaches equity.
    assert -0.09 < base["equity_irr"] < -0.06
    assert 0.03 < base["project_irr"] < 0.05
