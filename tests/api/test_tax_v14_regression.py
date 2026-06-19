"""Regression tests for the canonical v14 corporate-tax engine.

Verifies tax behaviour against the CURRENT-regime configs
(``dutchbay_lendercase_2025Q4.yaml`` + the SDP-pathway override) using the
**canonical** ``finance.cashflow_v14_tax`` engine — the engine the lender pipeline
actually runs.

This suite previously exercised the now-retired ``finance.tax_profile_v14_hydra``
single-life engine; it was migrated onto ``cashflow_v14_tax`` as part of the CCCDIR
tax-engine de-duplication (one centralized ``TaxConfig`` / ``DepreciationSchedule``
/ ``calculate_tax`` contract). Unlike the old engine, the canonical engine honours
the Sri Lanka Fourth-Schedule plant/civil split (5 yr / 20 yr), so the split is now
asserted here against the real lender config.

Framework Compliance:
- TEST-01: regression pins on the current SL regime (post-2025).
- CESSPIT / ARCH-01: every value sourced from the scenario YAML (no hardcoding).
- CCCDIR: single canonical tax contract (``finance.cashflow_v14_tax``).
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from omegaconf import OmegaConf

from finance.cashflow_v14_tax import (
    DepreciationSchedule,
    TaxConfig,
    TaxProfile,
    build_tax_holiday_map,
    build_tax_profile,
    calculate_tax,
)

LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"
SDP_OVERRIDE = "scenarios/overrides/sdp_pathway.yaml"


def _to_dict(cfg: Any) -> Dict[str, Any]:
    """Resolve an OmegaConf config to a plain dict for the Mapping-based engine."""
    return OmegaConf.to_container(cfg, resolve=True)  # type: ignore[return-value]


@pytest.fixture
def lender_cfg() -> Dict[str, Any]:
    """The canonical lender case (current regime: no statutory holiday)."""
    return _to_dict(OmegaConf.load(LENDER_CASE))


@pytest.fixture
def holiday_cfg() -> Dict[str, Any]:
    """Lender case overridden with an explicit 12-year holiday.

    The live regime grants no statutory holiday, so holiday-WINDOW logic is
    exercised against an explicit-holiday config (e.g. a discretionary grant),
    independent of the scenario's actual (zero) holiday.
    """
    merged = OmegaConf.merge(
        OmegaConf.load(LENDER_CASE),
        {"tax": {"tax_holiday_years": 12, "tax_holiday_start_year": 1}},
    )
    return _to_dict(merged)


@pytest.fixture
def sdp_cfg() -> Dict[str, Any]:
    """Lender case + the SDP-pathway override (≤10-yr holiday + enhanced)."""
    merged = OmegaConf.merge(
        OmegaConf.load(LENDER_CASE), OmegaConf.load(SDP_OVERRIDE)
    )
    return _to_dict(merged)


def _capex_lkr(cfg: Dict[str, Any]) -> float:
    return float(cfg["capex"]["usd_total"]) * float(cfg["fx"]["start_lkr_per_usd"])


def _split_schedule(cfg: Dict[str, Any], tc: TaxConfig) -> DepreciationSchedule:
    """The lender case's split (plant/civil) straight-line schedule."""
    assert tc.plant_capex_share is not None  # lender case is split-mode
    assert tc.plant_depreciation_years is not None
    assert tc.civil_depreciation_years is not None
    return DepreciationSchedule.build_split_straight_line(
        total_capex=_capex_lkr(cfg),
        plant_capex_share=tc.plant_capex_share,
        plant_useful_life=tc.plant_depreciation_years,
        civil_useful_life=tc.civil_depreciation_years,
        project_life=int(cfg["returns"]["project_life_years"]),
    )


class TestLenderCaseRegimePins:
    """The real lender config parses to the current SL regime (post-2025)."""

    def test_current_regime_scalar_pins(self, lender_cfg: Dict[str, Any]) -> None:
        tc = TaxConfig.from_yaml(lender_cfg)
        assert tc.corporate_tax_rate == 0.30
        assert tc.tax_holiday_years == 0  # no renewable holiday for new IPPs
        assert tc.tax_holiday_start_year == 1
        assert tc.tax_holiday_route == "none"
        assert tc.depreciation_method == "straight_line"
        assert tc.loss_carryforward_years == 6  # TLCF 6 yr
        assert tc.wht_on_interest_enabled is True
        assert tc.wht_on_interest_to_nonresidents == 0.10

    def test_plant_civil_split_pins(self, lender_cfg: Dict[str, Any]) -> None:
        """The canonical engine honours the SL Fourth-Schedule split — coverage the
        de-dup *gains* (the retired hydra engine read a single ``depreciation_years``).
        """
        tc = TaxConfig.from_yaml(lender_cfg)
        assert tc.plant_capex_share == 0.80
        assert tc.plant_depreciation_years == 5  # Class 2 plant & machinery
        assert tc.civil_depreciation_years == 20  # Class 4 buildings/civils


class TestSplitDepreciationSchedule:
    """The lender case's actual split straight-line schedule."""

    def test_split_schedule_writes_off_full_base(
        self, lender_cfg: Dict[str, Any]
    ) -> None:
        tc = TaxConfig.from_yaml(lender_cfg)
        sched = _split_schedule(lender_cfg, tc)
        assert sum(sched.annual_amounts) == pytest.approx(_capex_lkr(lender_cfg))
        assert sched.book_value[-1] == pytest.approx(0.0)

    def test_plant_writes_off_first_then_civil_only(
        self, lender_cfg: Dict[str, Any]
    ) -> None:
        tc = TaxConfig.from_yaml(lender_cfg)
        sched = _split_schedule(lender_cfg, tc)
        capex = _capex_lkr(lender_cfg)
        plant = 0.80 * capex / 5.0
        civil = 0.20 * capex / 20.0
        assert sched.annual_amounts[0] == pytest.approx(plant + civil)  # year 1
        assert sched.annual_amounts[5] == pytest.approx(civil)  # year 6: civil only


class TestHolidayWindow:
    """Holiday-window mapping via the canonical ``build_tax_holiday_map``."""

    def test_holiday_map_inclusive_window(self, holiday_cfg: Dict[str, Any]) -> None:
        tc = TaxConfig.from_yaml(holiday_cfg)
        holidays = build_tax_holiday_map(tc, project_life_years=20)
        assert all(holidays[y] for y in range(1, 13))  # years 1-12 in holiday
        assert holidays[13] is False
        assert holidays[20] is False

    def test_live_lender_case_has_no_holiday(
        self, lender_cfg: Dict[str, Any]
    ) -> None:
        tc = TaxConfig.from_yaml(lender_cfg)
        holidays = build_tax_holiday_map(tc, project_life_years=20)
        assert not any(holidays[y] for y in range(1, 21))


class TestPerYearTax:
    """Per-year CIT: holiday → zero CIT (WHT still applies); interest shield."""

    @staticmethod
    def _profile(cfg: Dict[str, Any]) -> tuple[DepreciationSchedule, TaxProfile]:
        tc = TaxConfig.from_yaml(cfg)
        sched = _split_schedule(cfg, tc)
        tp = build_tax_profile(
            config=tc,
            depreciation_schedule=sched,
            project_life_years=int(cfg["returns"]["project_life_years"]),
        )
        return sched, tp

    def test_holiday_year_zero_cit_but_wht_applies(
        self, holiday_cfg: Dict[str, Any]
    ) -> None:
        sched, tp = self._profile(holiday_cfg)
        result = calculate_tax(
            year=1,  # 1-based; within the 12-yr holiday
            ebit=10_000_000_000.0,
            interest_expense=1_000_000_000.0,
            depreciation=sched.annual_amounts[0],
            tax_profile=tp,
        )
        assert result.tax_holiday_applied is True
        assert result.tax_liability == pytest.approx(0.0)
        # interest WHT (10%) still flows during a CIT holiday
        assert result.wht_on_interest == pytest.approx(1_000_000_000.0 * 0.10)

    def test_post_holiday_interest_shield(self, holiday_cfg: Dict[str, Any]) -> None:
        sched, tp = self._profile(holiday_cfg)
        ebit = 10_000_000_000.0
        interest = 1_000_000_000.0
        dep_y13 = sched.annual_amounts[12]
        result = calculate_tax(
            year=13,  # first taxed year after the 12-yr holiday
            ebit=ebit,
            interest_expense=interest,
            depreciation=dep_y13,
            tax_profile=tp,
        )
        assert result.tax_holiday_applied is False
        # interest is deductible (shield) under the lender config
        expected_with_shield = (ebit - interest - dep_y13) * 0.30
        assert result.tax_liability == pytest.approx(expected_with_shield)
        # the shield strictly lowers CIT vs. the no-shield counterfactual
        assert result.tax_liability < (ebit - dep_y13) * 0.30


class TestSDPPathwayOverride:
    """SDP-pathway override → ≤10-yr holiday + enhanced allowance (dual pathway)."""

    def test_sdp_override_grants_10yr_holiday_and_enhanced(
        self, sdp_cfg: Dict[str, Any]
    ) -> None:
        tc = TaxConfig.from_yaml(sdp_cfg)
        assert tc.tax_holiday_route == "sdp"
        assert tc.tax_holiday_years == 10  # SDP Act 26/2025 caps the holiday at 10 yr
        assert tc.enhanced_allowance_applies is True
        holidays = build_tax_holiday_map(tc, project_life_years=20)
        assert all(holidays[y] for y in range(1, 11))  # years 1-10 in holiday
        assert holidays[11] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
