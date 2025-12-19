"""Comprehensive test suite for FX structured blocks.

Tests cover:
- FXStructuredBlock validation and edge cases
- FXRiskProfile lender-grade metrics
- FXVolumetry debt exposure tracking
- FX loader functions
- FX curve generation

All tests follow Go with the Flow v3.0 standards.

Refs: Issue #31, v14R6, GWTF v3.0 (tests gate changes)
"""

from __future__ import annotations

import pytest

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
    FXVolumetry,
)


class TestFXStructuredBlockValidation:
    """Tests for FXStructuredBlock validation logic."""

    def test_valid_structured_block(self) -> None:
        """Valid FX structured block should construct."""
        block = FXStructuredBlock(
            strategy="blended",
            base_currency="USD",
            reporting_currency="USD",
        )

        assert block.strategy == "blended"
        assert block.base_currency == "USD"
        assert block.reporting_currency == "USD"
        assert block.fx_match_ratio == 0.0
        assert block.hedging_coverage_pct == 0.0

    def test_invalid_fx_match_ratio_rejected(self) -> None:
        """fx_match_ratio must be in [0, 100]."""
        with pytest.raises(ValueError, match="fx_match_ratio"):
            FXStructuredBlock(
                strategy="blended",
                fx_match_ratio=150.0,
            )

    def test_invalid_hedging_coverage_rejected(self) -> None:
        """hedging_coverage_pct must be in [0, 100]."""
        with pytest.raises(ValueError, match="hedging_coverage_pct"):
            FXStructuredBlock(
                strategy="blended",
                hedging_coverage_pct=-10.0,
            )

    def test_invalid_base_currency_rejected(self) -> None:
        """base_currency must be in valid set."""
        with pytest.raises(ValueError, match="base_currency"):
            FXStructuredBlock(
                strategy="blended",
                base_currency="XYZ",
            )

    def test_structured_block_with_volumetry(self) -> None:
        """FX block with volumetry snapshots."""
        vol1 = FXVolumetry(
            period=0,
            total_debt_lkr=1_000_000,
            total_debt_usd=5_000,
        )
        vol2 = FXVolumetry(
            period=1,
            total_debt_lkr=950_000,
            total_debt_usd=4_800,
        )

        block = FXStructuredBlock(
            strategy="natural_hedge",
            volumetry=[vol1, vol2],
        )

        assert block.total_periods() == 2
        assert block.volumetry[0].period == 0
        assert block.volumetry[1].period == 1


class TestFXVolumetry:
    """Tests for FXVolumetry contract."""

    def test_valid_volumetry(self) -> None:
        """Valid volumetry snapshot should construct."""
        vol = FXVolumetry(
            period=0,
            total_debt_lkr=1_000_000,
            total_debt_usd=5_000,
            total_debt_cny=0,
            revenue_lkr=200_000,
            revenue_usd=0,
        )

        assert vol.period == 0
        assert vol.total_debt_lkr == 1_000_000
        assert vol.total_debt_usd == 5_000
        assert vol.revenue_lkr == 200_000

    def test_total_usd_exposure_equivalent(self) -> None:
        """USD equivalent calculation."""
        vol = FXVolumetry(
            period=0,
            total_debt_lkr=300_000,  # ~1000 USD at 300 LKR/USD
            total_debt_usd=5_000,
            interest_lkr=30_000,  # ~100 USD
        )

        # Expected: 5000 USD + (300000 + 30000)/300 = 5000 + 1100 = 6100
        assert abs(vol.total_usd_exposure_equivalent - 6100) < 10


class TestFXRiskProfiles:
    """Tests for lender-grade risk profile outputs."""

    def test_valid_risk_profile(self) -> None:
        """Valid risk profile should construct."""
        risk = FXRiskProfile(
            var_95_usd_million=15.0,
            cvar_95_usd_million=22.5,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
            debt_cny_pct=0.0,
        )

        assert risk.var_95_usd_million == 15.0
        assert risk.cvar_95_usd_million == 22.5
        assert risk.debt_lkr_pct == 60.0

    def test_debt_percentages_must_sum_to_100(self) -> None:
        """Debt percentages must sum to ~100%."""
        with pytest.raises(ValueError, match="must sum to"):
            FXRiskProfile(
                var_95_usd_million=15.0,
                cvar_95_usd_million=22.5,
                debt_lkr_pct=50.0,
                debt_usd_pct=30.0,
                debt_cny_pct=0.0,  # Sum = 80%, invalid
            )

    def test_var_must_be_less_than_cvar(self) -> None:
        """VaR must be <= CVaR."""
        with pytest.raises(ValueError, match="VaR"):
            FXRiskProfile(
                var_95_usd_million=25.0,
                cvar_95_usd_million=22.5,  # CVaR < VaR, invalid
                debt_lkr_pct=60.0,
                debt_usd_pct=40.0,
            )

    def test_hhi_must_be_in_valid_range(self) -> None:
        """HHI must be in [0, 1]."""
        with pytest.raises(ValueError, match="debt_concentration_hhi"):
            FXRiskProfile(
                var_95_usd_million=15.0,
                cvar_95_usd_million=22.5,
                debt_lkr_pct=60.0,
                debt_usd_pct=40.0,
                debt_concentration_hhi=1.5,  # Invalid
            )

    def test_is_high_risk_flag(self) -> None:
        """is_high_risk flag works correctly."""
        low_risk = FXRiskProfile(
            var_95_usd_million=3.0,
            cvar_95_usd_million=4.0,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
        )

        high_risk = FXRiskProfile(
            var_95_usd_million=10.0,
            cvar_95_usd_million=15.0,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
        )

        assert low_risk.is_high_risk() is False
        assert high_risk.is_high_risk() is True


class TestFXCurveOutput:
    """Tests for FX curve generation and validation."""

    def test_valid_fx_curve(self) -> None:
        """Valid FX curve should construct."""
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 305.0, 310.0],
            source="base_case",
        )

        assert len(curve.years) == 3
        assert curve.lkr_usd[0] == 300.0
        assert curve.source == "base_case"

    def test_years_and_rates_length_mismatch_rejected(self) -> None:
        """years and lkr_usd must have same length."""
        with pytest.raises(ValueError, match="same length"):
            FXCurveOutput(
                years=[0, 1, 2],
                lkr_usd=[300.0, 305.0],  # Mismatch
            )

    def test_negative_rates_rejected(self) -> None:
        """All rates must be > 0."""
        with pytest.raises(ValueError, match="must be > 0"):
            FXCurveOutput(
                years=[0, 1],
                lkr_usd=[300.0, -10.0],  # Invalid
            )

    def test_get_rate_success(self) -> None:
        """get_rate retrieves correct rate."""
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 305.0, 310.0],
        )

        assert curve.get_rate(0, "lkr_usd") == 300.0
        assert curve.get_rate(1, "lkr_usd") == 305.0

    def test_get_rate_invalid_year_raises(self) -> None:
        """get_rate raises IndexError for invalid year."""
        curve = FXCurveOutput(
            years=[0, 1],
            lkr_usd=[300.0, 305.0],
        )

        with pytest.raises(IndexError):
            curve.get_rate(5, "lkr_usd")

    def test_get_rate_unavailable_pair_raises(self) -> None:
        """get_rate raises ValueError for unavailable pair."""
        curve = FXCurveOutput(
            years=[0, 1],
            lkr_usd=[300.0, 305.0],
            lkr_cny=None,
        )

        with pytest.raises(ValueError, match="not available"):
            curve.get_rate(0, "lkr_cny")

    def test_multi_currency_curve(self) -> None:
        """FX curve with multiple currency pairs."""
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 305.0, 310.0],
            lkr_cny=[42.0, 43.0, 44.0],
        )

        assert curve.get_rate(1, "lkr_usd") == 305.0
        assert curve.get_rate(1, "lkr_cny") == 43.0


class TestFXStructuredBlockConversions:
    """Tests for FX block serialization methods."""

    def test_to_dict_basic(self) -> None:
        """to_dict converts block to dict correctly."""
        block = FXStructuredBlock(
            strategy="fixed_ccy",
            base_currency="USD",
        )

        result = block.to_dict()

        assert result["strategy"] == "fixed_ccy"
        assert result["base_currency"] == "USD"
        assert "volumetry" in result

    def test_to_dict_with_volumetry(self) -> None:
        """to_dict serializes volumetry correctly."""
        vol = FXVolumetry(
            period=0,
            total_debt_lkr=1_000_000,
            total_debt_usd=5_000,
        )

        block = FXStructuredBlock(
            strategy="natural_hedge",
            volumetry=[vol],
        )

        result = block.to_dict()

        assert len(result["volumetry"]) == 1
        assert result["volumetry"][0]["period"] == 0
        assert result["volumetry"][0]["total_debt_lkr"] == 1_000_000


# EOF
