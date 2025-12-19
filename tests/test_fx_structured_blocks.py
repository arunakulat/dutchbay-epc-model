"""Comprehensive test suite for FX structured blocks (R23).

Tests cover the R23-compliant FX contracts:
- FXStructuredBlock: Primary FX strategy and configuration
- FXVolumetry: Debt and revenue exposure by currency
- FXCurveOutput: Time-series FX rate projections
- FXRiskProfile: Lender-grade FX risk metrics (VaR, CVaR, HHI)

All tests follow Go with the Flow v3.0 standards for R23 minimalist architecture.

Note: Previous test classes for FXSensitivityConfig, FXRegimeScenario, and
FXMonteCarloConfig have been removed as these classes no longer exist after R23 refactor.

Refs: Issue #31, v14R6, Sprint 12 R23 contracts refactor
"""

from __future__ import annotations

import pytest

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
    FXVolumetry,
)


# ═════════════════════════════════════════════════════════════════════════════
# FXVolumetry Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFXVolumetry:
    """Tests for FXVolumetry exposure tracking."""

    def test_valid_volumetry(self) -> None:
        """Valid FX volumetry should construct."""
        vol = FXVolumetry(
            period=0,
            total_debt_lkr=1000.0,
            total_debt_usd=50.0,
            total_debt_cny=20.0,
            revenue_lkr=500.0,
        )

        assert vol.period == 0
        assert vol.total_debt_lkr == 1000.0
        assert vol.total_debt_usd == 50.0
        assert vol.total_debt_cny == 20.0
        assert vol.revenue_lkr == 500.0

    def test_volumetry_usd_exposure(self) -> None:
        """Test USD exposure equivalent calculation."""
        vol = FXVolumetry(
            period=1,
            total_debt_lkr=6000.0,  # ~20 USD at 300 LKR/USD
            total_debt_usd=100.0,
            interest_lkr=1500.0,  # ~5 USD
        )

        # Should be approx 100 (USD debt) + 20 (LKR debt equiv) + 5 (interest equiv) = 125
        exposure = vol.total_usd_exposure_equivalent
        assert 120.0 < exposure < 130.0  # Approximate due to spot rate assumption


# ═════════════════════════════════════════════════════════════════════════════
# FXCurveOutput Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFXCurveOutput:
    """Tests for FX curve time-series outputs."""

    def test_valid_fx_curve(self) -> None:
        """Valid FX curve should construct."""
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 310.0, 320.0],
            source="base_case",
        )

        assert curve.years == [0, 1, 2]
        assert curve.lkr_usd == [300.0, 310.0, 320.0]
        assert curve.source == "base_case"

    def test_curve_length_mismatch_rejected(self) -> None:
        """Years and rates must have same length."""
        with pytest.raises(ValueError, match="same length"):
            FXCurveOutput(
                years=[0, 1, 2],
                lkr_usd=[300.0, 310.0],  # Mismatch!
            )

    def test_negative_rate_rejected(self) -> None:
        """Rates must be positive."""
        with pytest.raises(ValueError, match="must be > 0"):
            FXCurveOutput(
                years=[0, 1],
                lkr_usd=[300.0, -10.0],  # Negative rate!
            )

    def test_zero_rate_rejected(self) -> None:
        """Zero rates not allowed."""
        with pytest.raises(ValueError, match="must be > 0"):
            FXCurveOutput(
                years=[0, 1],
                lkr_usd=[300.0, 0.0],  # Zero rate!
            )

    def test_get_rate_lkr_usd(self) -> None:
        """Retrieve rate for specific year and pair."""
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 310.0, 320.0],
        )

        assert curve.get_rate(0, "lkr_usd") == 300.0
        assert curve.get_rate(1, "lkr_usd") == 310.0
        assert curve.get_rate(2, "lkr_usd") == 320.0

    def test_get_rate_year_not_found(self) -> None:
        """Raise IndexError if year not in curve."""
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 310.0, 320.0],
        )

        with pytest.raises(IndexError, match="not in curve"):
            curve.get_rate(5, "lkr_usd")

    def test_get_rate_optional_currency(self) -> None:
        """Retrieve rate for optional currency pairs."""
        curve = FXCurveOutput(
            years=[0, 1],
            lkr_usd=[300.0, 310.0],
            lkr_cny=[45.0, 46.0],
        )

        assert curve.get_rate(0, "lkr_cny") == 45.0
        assert curve.get_rate(1, "lkr_cny") == 46.0

    def test_get_rate_unavailable_currency(self) -> None:
        """Raise ValueError if optional currency not in curve."""
        curve = FXCurveOutput(
            years=[0, 1],
            lkr_usd=[300.0, 310.0],
        )

        with pytest.raises(ValueError, match="not available"):
            curve.get_rate(0, "lkr_cny")

    def test_fx_curve_to_dict(self) -> None:
        """FXCurveOutput serializes to dict."""
        curve = FXCurveOutput(
            years=[0, 1],
            lkr_usd=[300.0, 310.0],
            source="test",
            notes="test curve",
        )

        result = curve.to_dict()

        assert result["years"] == [0, 1]
        assert result["lkr_usd"] == [300.0, 310.0]
        assert result["source"] == "test"
        assert result["notes"] == "test curve"


# ═════════════════════════════════════════════════════════════════════════════
# FXRiskProfile Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFXRiskProfile:
    """Tests for lender-grade FX risk metrics."""

    def test_valid_risk_profile(self) -> None:
        """Valid risk profile should construct."""
        risk = FXRiskProfile(
            var_95_usd_million=5.0,
            cvar_95_usd_million=7.5,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
            debt_concentration_hhi=0.52,
        )

        assert risk.var_95_usd_million == 5.0
        assert risk.cvar_95_usd_million == 7.5
        assert risk.debt_lkr_pct == 60.0
        assert risk.debt_usd_pct == 40.0

    def test_debt_percentages_must_sum_to_100(self) -> None:
        """Debt percentages must sum to ~100%."""
        with pytest.raises(ValueError, match="sum to ~100%"):
            FXRiskProfile(
                var_95_usd_million=5.0,
                cvar_95_usd_million=7.5,
                debt_lkr_pct=60.0,
                debt_usd_pct=20.0,  # Only 80% total!
            )

    def test_var_must_be_less_than_cvar(self) -> None:
        """VaR must be <= CVaR."""
        with pytest.raises(ValueError, match="VaR .* must be <= CVaR"):
            FXRiskProfile(
                var_95_usd_million=10.0,  # VaR > CVaR!
                cvar_95_usd_million=7.5,
                debt_lkr_pct=60.0,
                debt_usd_pct=40.0,
            )

    def test_hhi_out_of_range_rejected(self) -> None:
        """HHI must be in [0, 1]."""
        with pytest.raises(ValueError, match="debt_concentration_hhi"):
            FXRiskProfile(
                var_95_usd_million=5.0,
                cvar_95_usd_million=7.5,
                debt_lkr_pct=60.0,
                debt_usd_pct=40.0,
                debt_concentration_hhi=1.5,  # Out of range!
            )

    def test_is_high_risk_flag(self) -> None:
        """is_high_risk flag returns True if VaR exceeds threshold."""
        risk = FXRiskProfile(
            var_95_usd_million=8.0,  # Above default 5.0 threshold
            cvar_95_usd_million=10.0,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
        )

        assert risk.is_high_risk() is True

    def test_is_not_high_risk(self) -> None:
        """is_high_risk flag returns False if VaR below threshold."""
        risk = FXRiskProfile(
            var_95_usd_million=3.0,  # Below default 5.0 threshold
            cvar_95_usd_million=4.5,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
        )

        assert risk.is_high_risk() is False

    def test_risk_profile_to_dict(self) -> None:
        """FXRiskProfile serializes to dict."""
        risk = FXRiskProfile(
            var_95_usd_million=5.0,
            cvar_95_usd_million=7.5,
            debt_lkr_pct=60.0,
            debt_usd_pct=40.0,
            correlation_shock_scenario="LKR -15% shock",
            worst_case_year=7,
        )

        result = risk.to_dict()

        assert result["var_95_usd_million"] == 5.0
        assert result["cvar_95_usd_million"] == 7.5
        assert result["debt_lkr_pct"] == 60.0
        assert result["debt_usd_pct"] == 40.0
        assert result["correlation_shock_scenario"] == "LKR -15% shock"
        assert result["worst_case_year"] == 7
        assert "is_high_risk" in result


# ═════════════════════════════════════════════════════════════════════════════
# FXStructuredBlock Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFXStructuredBlock:
    """Tests for FXStructuredBlock primary configuration."""

    def test_valid_structured_block(self) -> None:
        """Valid FX structured block should construct."""
        block = FXStructuredBlock(
            strategy="natural_hedge",
            base_currency="USD",
            fx_match_ratio=75.0,
            hedging_coverage_pct=25.0,
        )

        assert block.strategy == "natural_hedge"
        assert block.base_currency == "USD"
        assert block.fx_match_ratio == 75.0
        assert block.hedging_coverage_pct == 25.0

    def test_fx_match_ratio_out_of_range_rejected(self) -> None:
        """fx_match_ratio must be in [0, 100]."""
        with pytest.raises(ValueError, match="fx_match_ratio"):
            FXStructuredBlock(
                fx_match_ratio=150.0,  # Out of range!
            )

    def test_hedging_coverage_out_of_range_rejected(self) -> None:
        """hedging_coverage_pct must be in [0, 100]."""
        with pytest.raises(ValueError, match="hedging_coverage_pct"):
            FXStructuredBlock(
                hedging_coverage_pct=-10.0,  # Negative!
            )

    def test_invalid_base_currency_rejected(self) -> None:
        """base_currency must be in valid set."""
        with pytest.raises(ValueError, match="base_currency"):
            FXStructuredBlock(
                base_currency="JPY",  # Not in valid set!
            )

    def test_invalid_reporting_currency_rejected(self) -> None:
        """reporting_currency must be in valid set."""
        with pytest.raises(ValueError, match="reporting_currency"):
            FXStructuredBlock(
                reporting_currency="AUD",  # Not in valid set!
            )

    def test_total_periods_empty_volumetry(self) -> None:
        """total_periods returns 0 if no volumetry."""
        block = FXStructuredBlock()

        assert block.total_periods() == 0

    def test_total_periods_with_volumetry(self) -> None:
        """total_periods returns length of volumetry list."""
        vol1 = FXVolumetry(period=0, total_debt_lkr=1000.0, total_debt_usd=50.0)
        vol2 = FXVolumetry(period=1, total_debt_lkr=900.0, total_debt_usd=45.0)

        block = FXStructuredBlock(
            volumetry=[vol1, vol2],
        )

        assert block.total_periods() == 2

    def test_total_debt_usd_equivalent(self) -> None:
        """Calculate total debt in USD equivalent."""
        vol1 = FXVolumetry(period=0, total_debt_lkr=3000.0, total_debt_usd=100.0, total_debt_cny=10.0)
        vol2 = FXVolumetry(period=1, total_debt_lkr=6000.0, total_debt_usd=200.0, total_debt_cny=15.0)

        block = FXStructuredBlock(
            volumetry=[vol1, vol2],
        )

        # Uses final period: 6000 LKR / 300 = 20 USD, + 200 USD + 15 CNY = 235 USD
        total = block.total_debt_usd_equivalent(spot_rate_lkr_usd=300.0)
        assert abs(total - 235.0) < 1.0

    def test_structured_block_to_dict(self) -> None:
        """FXStructuredBlock serializes to dict."""
        vol = FXVolumetry(period=0, total_debt_lkr=1000.0, total_debt_usd=50.0)

        block = FXStructuredBlock(
            strategy="blended",
            volumetry=[vol],
            fx_match_ratio=60.0,
            notes="test block",
        )

        result = block.to_dict()

        assert result["strategy"] == "blended"
        assert result["fx_match_ratio"] == 60.0
        assert result["notes"] == "test block"
        assert len(result["volumetry"]) == 1
        assert result["volumetry"][0]["period"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFXIntegration:
    """Integration tests combining multiple FX contracts."""

    def test_complete_fx_scenario(self) -> None:
        """Test complete FX scenario with all contracts."""
        # Create volumetry
        vol = FXVolumetry(
            period=0,
            total_debt_lkr=10000.0,
            total_debt_usd=500.0,
            revenue_lkr=2000.0,
            interest_lkr=800.0,
        )

        # Create structured block
        block = FXStructuredBlock(
            strategy="natural_hedge",
            volumetry=[vol],
            fx_match_ratio=70.0,
            debt_tranches={"LKR_Tranche": "LKR", "USD_Tranche": "USD"},
        )

        # Create FX curve
        curve = FXCurveOutput(
            years=[0, 1, 2],
            lkr_usd=[300.0, 310.0, 320.0],
            source="base_case",
        )

        # Create risk profile
        risk = FXRiskProfile(
            var_95_usd_million=5.0,
            cvar_95_usd_million=7.5,
            debt_lkr_pct=65.0,
            debt_usd_pct=35.0,
        )

        # Validate all constructed correctly
        assert block.strategy == "natural_hedge"
        assert len(curve.years) == 3
        assert risk.is_high_risk() is False

        # Validate serialization
        block_dict = block.to_dict()
        curve_dict = curve.to_dict()
        risk_dict = risk.to_dict()

        assert "volumetry" in block_dict
        assert "lkr_usd" in curve_dict
        assert "var_95_usd_million" in risk_dict


# EOF
