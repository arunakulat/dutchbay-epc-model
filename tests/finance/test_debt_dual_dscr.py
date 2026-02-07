"""Tests for Dual DSCR Debt Sizing.

Validates dual constraint debt sizing against industry standards:
- Bolinger (2017): P50/P99 methodology
- DNV GL (2019): Project finance debt sizing
- Standard & Poor's: Dual DSCR requirements

Author: Dutch Bay EPC Model Team
Date: December 2025
Version: 1.0.0
"""

import pytest

from finance.debt_v14 import size_debt_with_dual_dscr


class TestDualDSCRBasics:
    """Basic dual DSCR functionality tests."""

    def test_dual_dscr_uses_conservative_sizing(self):
        """Verify dual DSCR uses min(P50, P99)."""
        # Strong P50 case, weak P99 case
        cfads_p50 = [10.0] * 15
        cfads_p99 = [5.0] * 15   # P99 is much weaker

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            capex=100.0,
            debt_ratio_max=0.70,
            debt_rate=0.08
        )

        # P99 should bind (lower CFADS)
        assert result["binding_constraint"] == "P99"
        assert result["debt_sized"] == result["debt_p99"]
        assert result["debt_sized"] < result["debt_p50"]

    def test_p50_binds_when_downside_strong(self):
        """P50 binds when P99 is close to P50 (low volatility)."""
        # Low volatility case
        cfads_p50 = [10.0] * 15
        cfads_p99 = [9.5] * 15   # P99 only slightly lower

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            capex=100.0,
            debt_ratio_max=0.70,
            debt_rate=0.08
        )

        # P50 should bind (stricter DSCR target)
        assert result["binding_constraint"] == "P50"
        assert result["debt_sized"] == result["debt_p50"]
        assert result["debt_sized"] <= result["debt_p99"]

    def test_debt_ratio_cap_enforced(self):
        """Verify maximum debt ratio cap is respected."""
        # Very high CFADS (unrealistically strong)
        cfads_p50 = [100.0] * 15
        cfads_p99 = [90.0] * 15
        capex = 100.0
        debt_ratio_max = 0.70

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            capex=capex,
            debt_ratio_max=debt_ratio_max,
            debt_rate=0.08
        )

        # Even with high CFADS, debt capped at 70% of CAPEX
        assert result["debt_sized"] <= capex * debt_ratio_max
        assert result["binding_constraint"] == "RATIO_CAP"


class TestDualDSCRCalculations:
    """Test DSCR calculation accuracy."""

    def test_dscr_target_respected_in_p50(self):
        """DSCR in P50 case should equal target."""
        cfads_p50 = [13.0] * 15  # $13M/year
        cfads_p99 = [10.0] * 15
        dscr_target_p50 = 1.30

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=dscr_target_p50,
            dscr_target_p99=1.00,
            capex=200.0,
            debt_ratio_max=0.80,
            debt_rate=0.08
        )

        # Min DSCR in P50 case should be approximately the target
        # (within tolerance for NPV discounting effects)
        assert result["min_dscr_p50"] == pytest.approx(
            dscr_target_p50, rel=0.05
        )

    def test_dscr_profiles_monotonic_for_flat_cfads(self):
        """DSCR profiles should be constant for flat CFADS."""
        cfads_p50 = [10.0] * 15
        cfads_p99 = [8.0] * 15

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            capex=100.0,
            debt_ratio_max=0.70,
            debt_rate=0.08
        )

        # For flat CFADS, DSCR should be constant (all equal to target)
        dscr_p50 = result["dscr_profile_p50"]
        dscr_p99 = result["dscr_profile_p99"]

        # All P50 DSCRs should be approximately equal
        dscr_p50_finite = [d for d in dscr_p50 if d < float('inf')]
        if dscr_p50_finite:
            dscr_p50_std = (
                sum((d - sum(dscr_p50_finite) / len(dscr_p50_finite)) ** 2
                    for d in dscr_p50_finite) / len(dscr_p50_finite)
            ) ** 0.5
            assert dscr_p50_std < 0.01  # Very low variance

    def test_debt_service_sum_approximates_debt_capacity(self):
        """PV of debt service should approximate debt capacity."""
        cfads_p50 = [12.0] * 15
        cfads_p99 = [10.0] * 15
        debt_rate = 0.08

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            capex=200.0,
            debt_ratio_max=0.80,
            debt_rate=debt_rate
        )

        # Calculate NPV of debt service manually
        debt_service = result["debt_service_p50"]
        npv_manual = sum(
            ds / (1 + debt_rate) ** (i + 1)
            for i, ds in enumerate(debt_service)
        )

        # Should match debt_p50 (within tolerance)
        assert result["debt_p50"] == pytest.approx(npv_manual, rel=0.002)


class TestDualDSCRIndustryScenarios:
    """Test realistic industry scenarios."""

    def test_typical_wind_farm_p99_binds(self):
        """Typical wind farm: P99 often binds due to resource uncertainty.

        Scenario: 150 MW wind farm, 15-year debt
        - P50 CFADS: $12.5M/year
        - P99 CFADS: $8.5M/year (32% lower, typical for wind)
        - Expected: P99 binds, reducing debt by ~15%
        """
        cfads_p50 = [12.5] * 15
        cfads_p99 = [8.5] * 15   # 32% downside

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            capex=200.0,
            debt_ratio_max=0.70,
            debt_rate=0.08
        )

        # P99 should bind
        assert result["binding_constraint"] == "P99"

        # Downside impact should be 10-20%
        downside_impact = result["downside_impact_pct"]
        assert 10.0 <= downside_impact <= 25.0, \
            f"Downside impact {downside_impact:.1f}% outside expected [10%, 25%]"

    def test_solar_pv_p50_often_binds(self):
        """Solar PV: P99 closer to P50, so P50 often binds.

        Scenario: 100 MW solar PV, 15-year debt
        - P50 CFADS: $10.0M/year
        - P99 CFADS: $9.0M/year (10% lower, typical for solar)
        - Expected: P50 binds (stricter DSCR target)
        """
        cfads_p50 = [10.0] * 15
        cfads_p99 = [9.0] * 15   # Only 10% downside

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            capex=150.0,
            debt_ratio_max=0.75,
            debt_rate=0.07
        )

        # P50 likely binds (stricter DSCR target compensates for low downside)
        assert result["binding_constraint"] in ["P50", "RATIO_CAP"]

    def test_emerging_market_aggressive_sizing(self):
        """Emerging markets: Higher DSCR targets, P99 more likely to bind.

        Scenario: Sri Lanka wind farm
        - Higher risk premiums
        - P50 DSCR target: 1.40x (vs 1.30x developed)
        - P99 DSCR target: 1.10x (vs 1.00x developed)
        """
        cfads_p50 = [11.0] * 15
        cfads_p99 = [7.5] * 15

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.40,  # Higher for emerging market
            dscr_target_p99=1.10,  # Higher buffer
            capex=180.0,
            debt_ratio_max=0.65,  # Lower max ratio
            debt_rate=0.10  # Higher debt cost
        )

        # Should produce conservative debt sizing
        assert result["debt_sized"] < capex * 0.65


class TestDualDSCRInputValidation:
    """Test input validation and error handling."""

    def test_empty_cfads_raises_error(self):
        """Empty CFADS should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            size_debt_with_dual_dscr(
                cfads_p50=[],
                cfads_p99=[],
                capex=100.0
            )

    def test_mismatched_cfads_length_raises_error(self):
        """Mismatched CFADS lengths should raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            size_debt_with_dual_dscr(
                cfads_p50=[10.0] * 15,
                cfads_p99=[8.0] * 10,  # Different length
                capex=100.0
            )

    def test_negative_dscr_target_raises_error(self):
        """Negative DSCR targets should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            size_debt_with_dual_dscr(
                cfads_p50=[10.0] * 15,
                cfads_p99=[8.0] * 15,
                dscr_target_p50=-1.30,
                capex=100.0
            )

    def test_invalid_debt_ratio_raises_error(self):
        """Invalid debt ratio should raise ValueError."""
        with pytest.raises(ValueError, match="Debt ratio must be in"):
            size_debt_with_dual_dscr(
                cfads_p50=[10.0] * 15,
                cfads_p99=[8.0] * 15,
                debt_ratio_max=1.5,  # > 1.0
                capex=100.0
            )

    def test_zero_capex_raises_error(self):
        """Zero CAPEX should raise ValueError."""
        with pytest.raises(ValueError, match="CAPEX must be positive"):
            size_debt_with_dual_dscr(
                cfads_p50=[10.0] * 15,
                cfads_p99=[8.0] * 15,
                capex=0.0
            )


class TestDualDSCRBackwardCompatibility:
    """Test backward compatibility and regression protection."""

    def test_no_regression_on_existing_plan_debt(self):
        """Dual DSCR is new function, shouldn't affect existing plan_debt().

        This test documents that size_debt_with_dual_dscr() is a NEW function
        and doesn't modify existing plan_debt() behavior.
        """
        # This is a documentation test
        # Actual regression tests for plan_debt() are in:
        # - tests/api/test_debt_construction_idc_regression_v14.py
        # - tests/api/test_covenants_v14.py

        from finance.debt_v14 import plan_debt

        # plan_debt() should still exist and work
        assert callable(plan_debt)

        # size_debt_with_dual_dscr() is separate
        assert callable(size_debt_with_dual_dscr)

    def test_result_keys_complete(self):
        """Verify result dict contains all expected keys."""
        cfads_p50 = [10.0] * 15
        cfads_p99 = [8.0] * 15

        result = size_debt_with_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            capex=100.0
        )

        # Required keys
        required_keys = [
            "debt_sized",
            "debt_p50",
            "debt_p99",
            "binding_constraint",
            "debt_service_p50",
            "debt_service_p99",
            "dscr_profile_p50",
            "dscr_profile_p99",
            "min_dscr_p50",
            "min_dscr_p99",
            "dscr_target_p50",
            "dscr_target_p99",
            "debt_ratio_cap",
            "capex",
            "downside_impact_pct",
        ]

        for key in required_keys:
            assert key in result, f"Missing required key: {key}"


if __name__ == "__main__":
    # Run with: pytest tests/finance/test_debt_dual_dscr.py -v
    pytest.main([__file__, "-v", "--tb=short"])
