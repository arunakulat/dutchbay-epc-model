"""Phase 6 test suite (5 cases): cashflow_v14_tax v14 integration

This suite intentionally focuses on the *public contract* of the refactored
`finance.cashflow_v14_tax` module:
- YAML-driven config parsing (no hidden defaults)
- Depreciation schedule construction
- Tax holiday mapping
- Per-year tax calculation (CIT) including depreciation & interest deductibility
- Loss carry-forward and interest WHT as cash outflows

Run with:
  pytest tests/finance/test_cashflow_v14_tax_refactored.py -v
"""

from __future__ import annotations

import pytest

from finance.cashflow_v14_tax import (
    DepreciationSchedule,
    TaxConfig,
    build_tax_holiday_map,
    build_tax_profile,
    calculate_tax,
)


def _base_yaml_cfg() -> dict:
    """Minimal scenario dict carrying only the required `tax` block."""
    return {
        "tax": {
            "corporate_tax_rate": 0.30,
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 5,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_multiple": 1.0,
            "loss_carryforward_years": 25,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 2,
            "wht_on_interest_to_nonresidents": 0.10,
            "wht_on_interest_enabled": True,
            "wht_gross_up": False,
            # optional
            "interest_deductibility": True,
        }
    }


# ---------------------------------------------------------------------------
# 1) YAML parsing contract
# ---------------------------------------------------------------------------


def test_tax_config_from_yaml_missing_required_key_raises() -> None:
    cfg = _base_yaml_cfg()
    del cfg["tax"]["corporate_tax_rate"]

    with pytest.raises(KeyError, match=r"tax\.corporate_tax_rate"):
        TaxConfig.from_yaml(cfg)


@pytest.mark.parametrize(
    "field",
    [
        "depreciation_method",
        "depreciation_start_year",
        "depreciation_years",
        "enhanced_allowance_applies",
        "enhanced_capital_allowance_multiple",
        "loss_carryforward_years",
        "tax_holiday_start_year",
        "tax_holiday_years",
        "wht_on_interest_to_nonresidents",
        "wht_on_interest_enabled",
        "wht_gross_up",
    ],
)
def test_tax_config_from_yaml_missing_each_required_key_raises(field: str) -> None:
    """CESSPIT/R22: every required tax field fails fast when absent (no hidden default)."""
    cfg = _base_yaml_cfg()
    del cfg["tax"][field]

    with pytest.raises(KeyError, match=rf"tax\.{field}"):
        TaxConfig.from_yaml(cfg)


def test_enhanced_allowance_accepts_new_key_and_deprecated_alias() -> None:
    """FIN-02 rename (audit D8): the canonical ``enhanced_capital_allowance_multiple``
    key is read, and the deprecated ``enhanced_capital_allowance_pct`` alias still
    resolves (with a DeprecationWarning) so pre-rename scenarios keep loading unchanged.
    """
    # Canonical new key (the base fixture already uses it).
    cfg_new = _base_yaml_cfg()
    cfg_new["tax"]["enhanced_capital_allowance_multiple"] = 1.5
    tc_new = TaxConfig.from_yaml(cfg_new)
    assert tc_new.enhanced_capital_allowance_multiple == 1.5

    # Deprecated alias: same value, resolves with a DeprecationWarning.
    cfg_old = _base_yaml_cfg()
    del cfg_old["tax"]["enhanced_capital_allowance_multiple"]
    cfg_old["tax"]["enhanced_capital_allowance_pct"] = 1.5
    with pytest.warns(DeprecationWarning, match="enhanced_capital_allowance_pct"):
        tc_old = TaxConfig.from_yaml(cfg_old)
    assert tc_old.enhanced_capital_allowance_multiple == 1.5

    # Neither key present -> fail loud (CESSPIT).
    cfg_missing = _base_yaml_cfg()
    del cfg_missing["tax"]["enhanced_capital_allowance_multiple"]
    with pytest.raises(KeyError, match="enhanced_capital_allowance_multiple"):
        TaxConfig.from_yaml(cfg_missing)


# ---------------------------------------------------------------------------
# 2) Depreciation schedule contract
# ---------------------------------------------------------------------------


def test_depreciation_schedule_straight_line_totals_and_tail_zeros() -> None:
    capex_lkr = 100.0
    useful_life = 4
    project_life = 6

    s = DepreciationSchedule.build_straight_line(
        capex_lkr=capex_lkr,
        useful_life=useful_life,
        project_life=project_life,
    )

    assert len(s.annual_amounts) == project_life
    assert sum(s.annual_amounts[:useful_life]) == pytest.approx(capex_lkr)
    assert all(v == 0.0 for v in s.annual_amounts[useful_life:])
    assert s.book_value[-1] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2b) Split (plant + civil) depreciation contract  [#136 post-2025 regime]
# ---------------------------------------------------------------------------


def test_build_split_straight_line_sums_plant_and_civil() -> None:
    total_capex = 1000.0
    plant_share = 0.80
    project_life = 25

    s = DepreciationSchedule.build_split_straight_line(
        total_capex=total_capex,
        plant_capex_share=plant_share,
        plant_useful_life=5,
        civil_useful_life=20,
        project_life=project_life,
    )

    assert len(s.annual_amounts) == project_life
    # Whole base written off over the longer (civil) life.
    assert sum(s.annual_amounts) == pytest.approx(total_capex)
    assert s.book_value[-1] == pytest.approx(0.0)
    # Year 1 = plant (800/5 = 160) + civil (200/20 = 10).
    assert s.annual_amounts[0] == pytest.approx(800.0 / 5 + 200.0 / 20)
    # After plant is fully written off (yr 6+), only civil (10/yr) remains.
    assert s.annual_amounts[5] == pytest.approx(200.0 / 20)
    # Equals the element-wise sum of two independent straight-line schedules.
    plant = DepreciationSchedule.build_straight_line(800.0, 5, project_life)
    civil = DepreciationSchedule.build_straight_line(200.0, 20, project_life)
    for i in range(project_life):
        assert s.annual_amounts[i] == pytest.approx(
            plant.annual_amounts[i] + civil.annual_amounts[i]
        )


def test_tax_config_split_mode_parses_and_validates() -> None:
    cfg = _base_yaml_cfg()
    cfg["tax"]["plant_capex_share"] = 0.80
    cfg["tax"]["plant_depreciation_years"] = 5
    cfg["tax"]["civil_depreciation_years"] = 20
    cfg["tax"]["tax_holiday_route"] = "sdp"

    tc = TaxConfig.from_yaml(cfg)
    assert tc.plant_capex_share == pytest.approx(0.80)
    assert tc.plant_depreciation_years == 5
    assert tc.civil_depreciation_years == 20
    assert tc.tax_holiday_route == "sdp"


def test_tax_config_legacy_single_mode_has_none_split_fields() -> None:
    # A config without the split fields stays in legacy single-class mode.
    tc = TaxConfig.from_yaml(_base_yaml_cfg())
    assert tc.plant_capex_share is None
    assert tc.tax_holiday_route == "none"


@pytest.mark.parametrize(
    "missing", ["plant_depreciation_years", "civil_depreciation_years"]
)
def test_tax_config_split_mode_requires_both_lives(missing: str) -> None:
    cfg = _base_yaml_cfg()
    cfg["tax"]["plant_capex_share"] = 0.80
    cfg["tax"]["plant_depreciation_years"] = 5
    cfg["tax"]["civil_depreciation_years"] = 20
    del cfg["tax"][missing]

    with pytest.raises(ValueError, match=missing):
        TaxConfig.from_yaml(cfg)


def test_tax_holiday_route_invalid_raises() -> None:
    cfg = _base_yaml_cfg()
    cfg["tax"]["tax_holiday_route"] = "boi"  # not none|sdp
    with pytest.raises(ValueError, match="tax_holiday_route"):
        TaxConfig.from_yaml(cfg)


# ---------------------------------------------------------------------------
# 3) Holiday mapping contract
# ---------------------------------------------------------------------------


def test_tax_holiday_map_start_end_inclusive() -> None:
    cfg = _base_yaml_cfg()
    cfg["tax"]["tax_holiday_start_year"] = 3
    cfg["tax"]["tax_holiday_years"] = 2

    tc = TaxConfig.from_yaml(cfg)
    m = build_tax_holiday_map(tc, project_life_years=6)

    assert m[1] is False
    assert m[2] is False
    assert m[3] is True
    assert m[4] is True
    assert m[5] is False


# ---------------------------------------------------------------------------
# 4) Per-year calc: holiday → zero CIT, but WHT still applies
# ---------------------------------------------------------------------------


def test_calculate_tax_holiday_zero_cit_but_wht_applies() -> None:
    cfg = _base_yaml_cfg()
    tc = TaxConfig.from_yaml(cfg)

    dep = DepreciationSchedule.build_straight_line(
        capex_lkr=1000.0,
        useful_life=tc.depreciation_years,
        project_life=5,
    )
    tp = build_tax_profile(config=tc, depreciation_schedule=dep, project_life_years=5)

    # Year 1 is in holiday (per _base_yaml_cfg)
    r = calculate_tax(
        year=1,
        ebit=1_000_000.0,
        interest_expense=100_000.0,
        depreciation=dep.annual_amounts[0],
        tax_profile=tp,
        prior_year_losses=0.0,
    )

    assert r.tax_holiday_applied is True
    assert r.tax_liability == pytest.approx(0.0)
    assert r.wht_on_interest == pytest.approx(100_000.0 * 0.10)


# ---------------------------------------------------------------------------
# 5) Loss carry-forward offsets future taxable income
# ---------------------------------------------------------------------------


def test_loss_carryforward_offsets_future_taxable_income() -> None:
    cfg = _base_yaml_cfg()
    cfg["tax"]["tax_holiday_years"] = 0  # remove holiday so CIT is visible

    tc = TaxConfig.from_yaml(cfg)
    dep = DepreciationSchedule.build_straight_line(
        capex_lkr=0.0,
        useful_life=1,
        project_life=2,
    )
    tp = build_tax_profile(config=tc, depreciation_schedule=dep, project_life_years=2)

    # Year 1: negative taxable income → losses carried
    r1 = calculate_tax(
        year=1,
        ebit=-50.0,
        interest_expense=0.0,
        depreciation=0.0,
        tax_profile=tp,
        prior_year_losses=0.0,
    )
    assert r1.taxable_income == pytest.approx(0.0)
    assert r1.tax_liability == pytest.approx(0.0)
    assert r1.carried_forward_losses == pytest.approx(50.0)

    # Year 2: profits are offset by carried losses
    r2 = calculate_tax(
        year=2,
        ebit=30.0,
        interest_expense=0.0,
        depreciation=0.0,
        tax_profile=tp,
        prior_year_losses=r1.carried_forward_losses,
    )

    assert r2.taxable_income == pytest.approx(0.0)
    assert r2.tax_liability == pytest.approx(0.0)
    assert r2.carried_forward_losses == pytest.approx(20.0)
