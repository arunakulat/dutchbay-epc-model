"""Coverage tests for ``finance.cashflow_v14_tax``.

This suite targets the validation / alias / error branches of the SL tax profile
module that the existing refactored suite does not reach: the corporate-tax-rate
compatibility ladder (canonical / compact-percent / deprecated ``_pct``), every
``TaxConfig._validate`` and ``TaxProfile.__post_init__`` guard, the depreciation
constructors' bounds, and ``build_tax_series`` length-mismatch + full carry-forward
loop.

Every expected value is DERIVED in-test from first principles (straight-line
arithmetic, TLCF offset semantics, holiday-window membership) — never an opaque
economic constant. No source files are modified.
"""

from __future__ import annotations

import warnings

import pytest

from finance.cashflow_v14_tax import (
    DepreciationSchedule,
    TaxConfig,
    TaxProfile,
    build_tax_holiday_map,
    build_tax_profile,
    build_tax_series,
    calculate_tax,
)
from finance.cashflow_v14_tax import (
    _get_key_with_default,
    _get_tax_rate_with_compat,
)


def _base_tax_block() -> dict:
    """Minimal, valid ``tax`` block (canonical rate, all required keys)."""
    return {
        "corporate_tax_rate": 0.30,
        "depreciation_method": "straight_line",
        "depreciation_start_year": 1,
        "depreciation_years": 5,
        "enhanced_allowance_applies": False,
        "enhanced_capital_allowance_pct": 1.0,
        "loss_carryforward_years": 25,
        "tax_holiday_start_year": 1,
        "tax_holiday_years": 2,
        "wht_on_interest_to_nonresidents": 0.10,
        "wht_on_interest_enabled": True,
        "wht_gross_up": False,
    }


def _cfg(**overrides: object) -> dict:
    block = _base_tax_block()
    block.update(overrides)
    return {"tax": block}


# ---------------------------------------------------------------------------
# Section / key helpers
# ---------------------------------------------------------------------------

def test_from_yaml_missing_tax_section_raises() -> None:
    """No ``tax`` section at all -> KeyError from _require_section (line 50)."""
    with pytest.raises(KeyError, match=r"Missing required YAML section: tax"):
        TaxConfig.from_yaml({})


def test_from_yaml_tax_section_not_mapping_raises() -> None:
    """A non-Mapping ``tax`` value also trips the section guard."""
    with pytest.raises(KeyError, match=r"Missing required YAML section: tax"):
        TaxConfig.from_yaml({"tax": ["not", "a", "mapping"]})


def test_get_key_with_default_present_and_absent() -> None:
    """_get_key_with_default returns cast value when present, default when absent."""
    section = {"alpha": "7", "Beta": "true"}
    # present (exact) -> cast applied
    assert _get_key_with_default(section, "alpha", -1, int) == 7
    # present (case-insensitive) -> cast applied
    assert _get_key_with_default(section, "beta", "x", str) == "true"
    # absent -> default returned unchanged (no cast)
    sentinel = object()
    assert _get_key_with_default(section, "missing", sentinel, int) is sentinel


# ---------------------------------------------------------------------------
# corporate-tax-rate compatibility ladder
# ---------------------------------------------------------------------------

def test_canonical_rate_out_of_range_raises() -> None:
    """Canonical rate above 1.0 is rejected (line 88)."""
    with pytest.raises(ValueError, match=r"corporate_tax_rate must be decimal"):
        _get_tax_rate_with_compat({"corporate_tax_rate": 1.5})


def test_compact_rate_percent_is_divided_by_100() -> None:
    """Compact ``corporate_rate`` given as a percent (>1) is /100 (line 97)."""
    rate = _get_tax_rate_with_compat({"corporate_rate": 30})
    assert rate == pytest.approx(0.30)


def test_compact_rate_decimal_passthrough() -> None:
    """Compact rate already in [0,1] passes through unscaled."""
    rate = _get_tax_rate_with_compat({"corporate_rate": 0.25})
    assert rate == pytest.approx(0.25)


def test_compact_rate_out_of_range_raises() -> None:
    """Compact rate that is neither valid decimal nor valid percent raises (line 99)."""
    with pytest.raises(ValueError, match=r"corporate_rate must be decimal"):
        _get_tax_rate_with_compat({"corporate_rate": 250})


def test_deprecated_pct_rate_warns_and_converts() -> None:
    """Deprecated ``corporate_tax_rate_pct`` warns then returns pct/100 (lines 106-114)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rate = _get_tax_rate_with_compat({"corporate_tax_rate_pct": 28})
    assert rate == pytest.approx(0.28)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_deprecated_pct_rate_out_of_range_raises() -> None:
    """Deprecated pct outside 0-100 raises (line 113)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ValueError, match=r"corporate_tax_rate_pct must be 0-100"):
            _get_tax_rate_with_compat({"corporate_tax_rate_pct": 150})


def test_no_rate_key_at_all_raises_keyerror() -> None:
    """None of the three aliases present -> KeyError (line 116)."""
    with pytest.raises(KeyError, match=r"corporate_tax_rate"):
        _get_tax_rate_with_compat({"depreciation_method": "straight_line"})


def test_from_yaml_uses_compact_alias_end_to_end() -> None:
    """from_yaml accepts the compact percent alias through the full builder."""
    block = _base_tax_block()
    del block["corporate_tax_rate"]
    block["corporate_rate"] = 30
    cfg = TaxConfig.from_yaml({"tax": block})
    assert cfg.corporate_tax_rate == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# TaxConfig._validate guards (each raises on exactly one bad field)
# ---------------------------------------------------------------------------

def _direct_config(**overrides: object) -> TaxConfig:
    """Build a TaxConfig directly (bypassing from_yaml's rate pre-validation).

    The dataclass constructor itself does not validate; only ``_validate`` does.
    This lets us reach the ``_validate`` corporate-rate guard, which from_yaml
    never reaches because ``_get_tax_rate_with_compat`` pre-clamps the rate.
    """
    base = dict(
        corporate_tax_rate=0.30,
        depreciation_method="straight_line",
        depreciation_start_year=1,
        depreciation_years=5,
        enhanced_allowance_applies=False,
        enhanced_capital_allowance_pct=1.0,
        loss_carryforward_years=25,
        tax_holiday_start_year=1,
        tax_holiday_years=0,
        wht_on_interest_to_nonresidents=0.0,
        wht_on_interest_enabled=False,
        wht_gross_up=False,
    )
    base.update(overrides)
    return TaxConfig(**base)


def test_validate_corporate_rate_out_of_range_raises() -> None:
    """_validate rejects a corporate_tax_rate outside [0,1] (line 209).

    Reachable only by constructing TaxConfig directly, since from_yaml's
    rate-compat helper pre-validates the same bound earlier.
    """
    cfg = _direct_config(corporate_tax_rate=1.4)
    with pytest.raises(ValueError, match=r"corporate_tax_rate must be in \[0,1\]"):
        cfg._validate()


def test_validate_negative_depreciation_years_raises() -> None:
    """depreciation_years < 0 (line 213). Rate is canonical-valid so we reach it."""
    with pytest.raises(ValueError, match=r"depreciation_years must be >= 0"):
        TaxConfig.from_yaml(_cfg(depreciation_years=-1))


def test_validate_depreciation_start_year_below_one_raises() -> None:
    """depreciation_start_year < 1 (line 215)."""
    with pytest.raises(ValueError, match=r"depreciation_start_year must be >= 1"):
        TaxConfig.from_yaml(_cfg(depreciation_start_year=0))


def test_validate_negative_holiday_years_raises() -> None:
    """tax_holiday_years < 0 (line 217)."""
    with pytest.raises(ValueError, match=r"tax holiday parameters invalid"):
        TaxConfig.from_yaml(_cfg(tax_holiday_years=-1))


def test_validate_negative_lcf_years_raises() -> None:
    """loss_carryforward_years < 0 (line 219)."""
    with pytest.raises(ValueError, match=r"loss_carryforward_years must be >= 0"):
        TaxConfig.from_yaml(_cfg(loss_carryforward_years=-1))


def test_validate_wht_out_of_range_raises() -> None:
    """wht_on_interest_to_nonresidents outside [0,1] (line 221)."""
    with pytest.raises(ValueError, match=r"wht_on_interest_to_nonresidents"):
        TaxConfig.from_yaml(_cfg(wht_on_interest_to_nonresidents=1.5))


def test_validate_unsupported_depreciation_method_raises() -> None:
    """Unknown depreciation_method (line 227)."""
    with pytest.raises(ValueError, match=r"depreciation_method unsupported"):
        TaxConfig.from_yaml(_cfg(depreciation_method="reducing_balance"))


def test_validate_bad_holiday_route_raises() -> None:
    """tax_holiday_route must be none|sdp."""
    with pytest.raises(ValueError, match=r"tax_holiday_route must be"):
        TaxConfig.from_yaml(_cfg(tax_holiday_route="ten_year"))


def test_validate_plant_share_out_of_range_raises() -> None:
    """plant_capex_share outside [0,1] (line 236)."""
    with pytest.raises(ValueError, match=r"plant_capex_share must be in"):
        TaxConfig.from_yaml(
            _cfg(
                plant_capex_share=1.4,
                plant_depreciation_years=5,
                civil_depreciation_years=20,
            )
        )


def test_validate_plant_share_requires_plant_years() -> None:
    """plant_capex_share set but plant_depreciation_years missing -> raises."""
    with pytest.raises(ValueError, match=r"plant_depreciation_years must be >= 1"):
        TaxConfig.from_yaml(
            _cfg(plant_capex_share=0.7, civil_depreciation_years=20)
        )


def test_validate_plant_share_requires_civil_years() -> None:
    """plant_capex_share + plant_years set but civil_depreciation_years missing."""
    with pytest.raises(ValueError, match=r"civil_depreciation_years must be >= 1"):
        TaxConfig.from_yaml(
            _cfg(plant_capex_share=0.7, plant_depreciation_years=5)
        )


def test_validate_full_split_config_accepted() -> None:
    """A fully specified split config validates and round-trips its fields."""
    cfg = TaxConfig.from_yaml(
        _cfg(
            plant_capex_share=0.7,
            plant_depreciation_years=5,
            civil_depreciation_years=20,
            tax_holiday_route="sdp",
        )
    )
    assert cfg.plant_capex_share == pytest.approx(0.7)
    assert cfg.plant_depreciation_years == 5
    assert cfg.civil_depreciation_years == 20
    assert cfg.tax_holiday_route == "sdp"


# ---------------------------------------------------------------------------
# TaxProfile.__post_init__ guards
# ---------------------------------------------------------------------------

def _profile(**overrides: object) -> dict:
    base = dict(
        tax_rate=0.30,
        interest_deductibility=True,
        depreciation_method="straight_line",
        depreciation_schedule=[1.0, 1.0],
        allowable_losses_carryforward=True,
        withholding_tax_rate=0.10,
        tax_holidays_by_year={1: False},
    )
    base.update(overrides)
    return base


def test_taxprofile_bad_tax_rate_raises() -> None:
    """tax_rate outside [0,1] (line 259)."""
    with pytest.raises(ValueError, match=r"tax_rate must be in"):
        TaxProfile(**_profile(tax_rate=1.2))


def test_taxprofile_bad_wht_rate_raises() -> None:
    """withholding_tax_rate outside [0,1] (line 261)."""
    with pytest.raises(ValueError, match=r"withholding_tax_rate must be in"):
        TaxProfile(**_profile(withholding_tax_rate=-0.1))


def test_taxprofile_bad_depreciation_method_raises() -> None:
    """Unknown depreciation_method (line 269)."""
    with pytest.raises(ValueError, match=r"Unknown depreciation_method"):
        TaxProfile(**_profile(depreciation_method="double_declining"))


# ---------------------------------------------------------------------------
# DepreciationSchedule constructors
# ---------------------------------------------------------------------------

def test_build_straight_line_nonpositive_life_raises() -> None:
    """useful_life <= 0 (line 288)."""
    with pytest.raises(ValueError, match=r"useful_life must be > 0"):
        DepreciationSchedule.build_straight_line(1000.0, 0, 10)


def test_build_straight_line_arithmetic_and_conservation() -> None:
    """Straight-line: each year = capex/life until life, book value floors at 0."""
    capex, life, project = 1000.0, 4, 6
    sched = DepreciationSchedule.build_straight_line(capex, life, project)
    annual = capex / life
    assert sched.annual_amounts == [annual, annual, annual, annual, 0.0, 0.0]
    # conservation: accumulated never exceeds capex; final acc == capex
    assert sched.accumulated_depreciation[-1] == pytest.approx(capex)
    assert sched.book_value[0] == pytest.approx(capex - annual)
    assert sched.book_value[-1] == pytest.approx(0.0)
    # monotone non-increasing book value
    assert all(
        b2 <= b1 + 1e-9
        for b1, b2 in zip(sched.book_value, sched.book_value[1:])
    )


def test_build_split_straight_line_bad_share_raises() -> None:
    """build_split_straight_line rejects share outside [0,1] (line 329)."""
    with pytest.raises(ValueError, match=r"plant_capex_share must be in"):
        DepreciationSchedule.build_split_straight_line(
            1000.0, 1.5, 5, 20, 25
        )


def test_build_split_straight_line_sums_components() -> None:
    """Split schedule equals plant + civil straight-lines, summed annually."""
    total, share, plant_life, civil_life, project = 1000.0, 0.6, 5, 20, 25
    plant_annual = total * share / plant_life
    civil_annual = total * (1.0 - share) / civil_life
    sched = DepreciationSchedule.build_split_straight_line(
        total, share, plant_life, civil_life, project
    )
    # Year 1: both components depreciate
    assert sched.annual_amounts[0] == pytest.approx(plant_annual + civil_annual)
    # Year 6 (after plant life): only civil remains
    assert sched.annual_amounts[5] == pytest.approx(civil_annual)
    # Conservation: total depreciation over project life == total capex
    assert sched.accumulated_depreciation[-1] == pytest.approx(total)
    assert sched.useful_life_years == max(plant_life, civil_life)


# ---------------------------------------------------------------------------
# Holiday map + profile wiring
# ---------------------------------------------------------------------------

def test_build_tax_holiday_map_window() -> None:
    """Holiday is True exactly within [start, start+years-1]."""
    cfg = TaxConfig.from_yaml(
        _cfg(tax_holiday_start_year=2, tax_holiday_years=3)
    )
    hmap = build_tax_holiday_map(cfg, project_life_years=6)
    assert hmap == {1: False, 2: True, 3: True, 4: True, 5: False, 6: False}


def test_build_tax_profile_wht_disabled_is_zero() -> None:
    """When WHT is disabled, profile withholding rate is forced to 0."""
    cfg = TaxConfig.from_yaml(_cfg(wht_on_interest_enabled=False))
    sched = DepreciationSchedule.build_straight_line(1000.0, 5, 6)
    profile = build_tax_profile(cfg, sched, project_life_years=6)
    assert profile.withholding_tax_rate == 0.0
    assert profile.tax_rate == pytest.approx(0.30)
    assert profile.allowable_losses_carryforward is True


# ---------------------------------------------------------------------------
# build_tax_series: length guard + carry-forward loop
# ---------------------------------------------------------------------------

def test_build_tax_series_length_mismatch_raises() -> None:
    """Mismatched input lengths raise (line 456)."""
    sched = DepreciationSchedule.build_straight_line(1000.0, 3, 3)
    with pytest.raises(ValueError, match=r"Mismatched lengths"):
        build_tax_series(
            years=[1, 2, 3],
            ebit_series=[10.0, 10.0],  # short by one
            interest_series=[0.0, 0.0, 0.0],
            depreciation_schedule=sched,
            tax_profile=build_tax_profile(
                TaxConfig.from_yaml(_cfg()), sched, 3
            ),
        )


def test_build_tax_series_carries_losses_forward() -> None:
    """A loss year creates carry-forward that offsets a later profit year.

    Year 1: large depreciation makes taxable income negative -> a loss, zero tax.
    Year 2/3: depreciation falls to 0, profit arrives; the year-1 loss offsets it
    before any tax is levied. We derive every expected number from the engine's
    own arithmetic (EBIT - interest - depr - LCF offset) * rate.
    """
    rate = 0.30
    # 3-year straight-line on 300 capex => 100/yr for 3 years.
    sched = DepreciationSchedule.build_straight_line(300.0, 1, 3)
    # life=1 => only year 1 depreciates the full 300.
    assert sched.annual_amounts == [300.0, 0.0, 0.0]

    profile = TaxProfile(
        tax_rate=rate,
        interest_deductibility=True,
        depreciation_method="straight_line",
        depreciation_schedule=list(sched.annual_amounts),
        allowable_losses_carryforward=True,
        withholding_tax_rate=0.0,
        tax_holidays_by_year={1: False, 2: False, 3: False},
    )

    ebit = [100.0, 100.0, 100.0]
    interest = [0.0, 0.0, 0.0]
    results = build_tax_series(
        years=[1, 2, 3],
        ebit_series=ebit,
        interest_series=interest,
        depreciation_schedule=sched,
        tax_profile=profile,
    )

    # Year 1: taxable = 100 - 0 - 300 = -200 => loss of 200, zero tax.
    assert results[0].taxable_income == pytest.approx(0.0)
    assert results[0].tax_liability == pytest.approx(0.0)
    assert results[0].carried_forward_losses == pytest.approx(200.0)

    # Year 2: taxable pre-LCF = 100; offset min(200,100)=100 => taxable 0, zero tax;
    # remaining carry-forward = 200 - 100 = 100.
    assert results[1].taxable_income == pytest.approx(0.0)
    assert results[1].tax_liability == pytest.approx(0.0)
    assert results[1].carried_forward_losses == pytest.approx(100.0)

    # Year 3: taxable pre-LCF = 100; offset min(100,100)=100 => taxable 0, zero tax;
    # carry-forward exhausted.
    assert results[2].taxable_income == pytest.approx(0.0)
    assert results[2].tax_liability == pytest.approx(0.0)
    assert results[2].carried_forward_losses == pytest.approx(0.0)


def test_calculate_tax_holiday_zeroes_liability() -> None:
    """In a holiday year, a profitable company still owes zero tax."""
    profile = TaxProfile(
        tax_rate=0.30,
        interest_deductibility=True,
        depreciation_method="straight_line",
        depreciation_schedule=[0.0],
        allowable_losses_carryforward=False,
        withholding_tax_rate=0.10,
        tax_holidays_by_year={1: True},
    )
    res = calculate_tax(
        year=1,
        ebit=100.0,
        interest_expense=10.0,
        depreciation=0.0,
        tax_profile=profile,
    )
    # taxable = 100 - 10 - 0 = 90, but holiday => zero liability.
    assert res.tax_holiday_applied is True
    assert res.taxable_income == pytest.approx(90.0)
    assert res.tax_liability == pytest.approx(0.0)
    # WHT still accrues on interest regardless of holiday.
    assert res.wht_on_interest == pytest.approx(10.0 * 0.10)
    # effective rate is zero in a holiday year.
    assert res.effective_tax_rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Wave-1: depreciation_start_year is now WIRED (was validated but ignored)
# ---------------------------------------------------------------------------


def test_depreciation_start_year_offsets_the_schedule() -> None:
    """depreciation_start_year defers the schedule: years before it are zero and the
    useful-life window shifts later (was validated but silently ignored)."""
    sched = DepreciationSchedule.build_straight_line(
        capex_lkr=1_000.0, useful_life=5, project_life=10, start_year=3
    )
    annual_depr = 1_000.0 / 5  # 200
    # years 1-2 zero, years 3..7 depreciate, years 8+ zero
    assert sched.annual_amounts[0] == 0.0
    assert sched.annual_amounts[1] == 0.0
    assert sched.annual_amounts[2] == pytest.approx(annual_depr)
    assert sched.annual_amounts[6] == pytest.approx(annual_depr)  # year 7 = start+life-1
    assert sched.annual_amounts[7] == 0.0  # year 8 past the window
    # full base still recovered, just deferred
    assert sum(sched.annual_amounts) == pytest.approx(1_000.0)


def test_depreciation_start_year_one_is_byte_identical() -> None:
    """start_year=1 (the default) reproduces the historical year<=useful_life schedule."""
    s1 = DepreciationSchedule.build_straight_line(900.0, 3, 6, start_year=1)
    assert s1.annual_amounts == pytest.approx([300.0, 300.0, 300.0, 0.0, 0.0, 0.0])


def test_depreciation_start_year_below_one_raises() -> None:
    with pytest.raises(ValueError, match="start_year"):
        DepreciationSchedule.build_straight_line(900.0, 3, 6, start_year=0)


def test_depreciation_start_year_changes_economics_end_to_end() -> None:
    """Deferring depreciation shifts the tax shield and genuinely moves CFADS / IRR — proving
    the lever is live in the pipeline, not just the builder."""
    from analytics.evaluation_v14 import evaluate_with_overrides

    lender = "scenarios/dutchbay_lendercase_2025Q4.yaml"
    base = evaluate_with_overrides(lender, overrides={})
    deferred = evaluate_with_overrides(lender, overrides={"tax.depreciation_start_year": 3})
    assert deferred["total_cfads_usd"] != base["total_cfads_usd"]
    # start_year=1 default is byte-identical to the canonical baseline (post 2% P50 haircut: AEP 473.8->464.3, CFADS 199.10M)
    assert base["total_cfads_usd"] == pytest.approx(199103726.01021385, rel=1e-9)


def test_depreciation_start_year_overrun_warns_about_forfeited_tail(
    caplog: "pytest.LogCaptureFixture",
) -> None:
    """A start_year that pushes the useful-life window past project_life forfeits the tail
    allowance; the engine must WARN (Wave-1 re-audit hardening of the newly-wired field)."""
    from pathlib import Path

    from analytics.scenario_loader import load_scenario_config
    from finance.cashflow_v14 import build_annual_rows

    lender = Path(__file__).resolve().parents[2] / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
    cfg = load_scenario_config(str(lender))
    cfg["tax"]["depreciation_start_year"] = 18  # life 20 -> window 18..(18+life-1) overruns
    with caplog.at_level("WARNING", logger="finance.cashflow_v14"):
        build_annual_rows(cfg)
    assert any("forfeiting the tail-year allowance" in r.message for r in caplog.records)


def test_depreciation_start_year_one_does_not_warn(
    caplog: "pytest.LogCaptureFixture",
) -> None:
    """The canonical start_year=1 fully amortizes within life -> no forfeit warning."""
    from pathlib import Path

    from analytics.scenario_loader import load_scenario_config
    from finance.cashflow_v14 import build_annual_rows

    lender = Path(__file__).resolve().parents[2] / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
    cfg = load_scenario_config(str(lender))
    with caplog.at_level("WARNING", logger="finance.cashflow_v14"):
        build_annual_rows(cfg)
    assert not any("forfeiting the tail-year allowance" in r.message for r in caplog.records)
