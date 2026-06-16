#!/usr/bin/env python
"""Comprehensive tests for tax-aware equity distribution optimization.

Test Coverage:
- TLCF schedule tracking and exhaustion
- Immediate distribution baseline calculations
- Deferred distribution optimization logic
- Tax savings calculation accuracy
- Equity IRR vs tax efficiency trade-offs
- Edge cases and boundary conditions
- Regression pins for optimization behavior

Framework Compliance:
- TEST-01: Regression pins for tax optimization
- CASPER: Conservative tax scenarios
- GWTF R7: Validates IRR calculation usage
- TYPE-01: Full type hints

Author: DutchBay Tax Testing Team
Date: December 2025
"""

import pytest
import numpy as np
from typing import List

from finance.tax_optimization_v14 import (
    track_tlcf_schedule,
    calculate_immediate_distributions,
    calculate_deferred_distributions,
    calculate_tax_savings,
    optimize_distribution_timing,
    TLCFSchedule,
)


@pytest.fixture
def typical_fcfe_schedule() -> List[float]:
    """Typical FCFE schedule for 20-year project."""
    # Year 0: no distributions
    # Years 1-20: growing FCFE $5M to $14M
    return [0.0] + [5e6 + i * 0.5e6 for i in range(19)]


@pytest.fixture
def typical_tlcf_schedule() -> List[float]:
    """Typical TLCF schedule with early depreciation."""
    # Years 1-3: High TLCF from accelerated depreciation
    # Years 4-5: Declining TLCF
    # Years 6+: TLCF exhausted
    return [5e6, 3e6, 2e6, 1.5e6, 0.8e6] + [0.0] * 15


@pytest.fixture
def typical_taxable_income() -> List[float]:
    """Typical taxable income schedule with early losses."""
    # Years 1-3: Tax losses (negative income)
    # Years 4+: Taxable profits
    return [-5e6, -3e6, 2e6, 5e6, 8e6] + [10e6] * 15


class TestTLCFTracking:
    """Test Tax Loss Carryforward tracking logic."""
    
    def test_tlcf_accumulates_during_losses(self, typical_taxable_income):
        """TLCF should accumulate during loss years."""
        tlcf = track_tlcf_schedule(typical_taxable_income, 0.28)
        
        # Year 1: -$5M loss → $5M TLCF
        assert abs(tlcf.annual_tlcf[0] - 5e6) < 1000
        
        # Year 2: -$3M loss → $8M TLCF (5M + 3M)
        assert abs(tlcf.annual_tlcf[1] - 8e6) < 1000
    
    def test_tlcf_utilized_during_profits(self, typical_taxable_income):
        """TLCF should be utilized during profit years."""
        tlcf = track_tlcf_schedule(typical_taxable_income, 0.28)
        
        # Year 3: +$2M profit, $8M TLCF → Utilize $2M → $6M remaining
        assert abs(tlcf.annual_tlcf[2] - 6e6) < 1000
        assert abs(tlcf.tlcf_utilization[2] - 2e6) < 1000
    
    def test_tlcf_exhaustion_year_detected(self, typical_taxable_income):
        """TLCF exhaustion year should be detected correctly."""
        tlcf = track_tlcf_schedule(typical_taxable_income, 0.28)
        
        # TLCF should exhaust within 5 years
        assert tlcf.tlcf_exhaustion_year <= 5
        assert tlcf.annual_tlcf[tlcf.tlcf_exhaustion_year] < 1e6
    
    def test_zero_tlcf_case(self):
        """Zero TLCF case should be handled correctly."""
        # All positive income (no losses)
        income = [5e6] * 10
        tlcf = track_tlcf_schedule(income, 0.28)
        
        # Should have zero TLCF throughout
        assert all(t < 1e3 for t in tlcf.annual_tlcf)
        assert tlcf.tlcf_exhaustion_year == 0


class TestImmediateDistributions:
    """Test immediate distribution baseline calculations."""
    
    def test_immediate_distributions_equal_fcfe(self, typical_fcfe_schedule):
        """Immediate distributions should equal FCFE."""
        result = calculate_immediate_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6
        )
        
        # All distributions should match FCFE
        for i, fcfe in enumerate(typical_fcfe_schedule):
            assert abs(result.annual_distributions[i] - fcfe) < 100
    
    def test_cumulative_distributions_calculated(self, typical_fcfe_schedule):
        """Cumulative distributions should be calculated correctly."""
        result = calculate_immediate_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6
        )
        
        # Verify cumulative sum
        expected_cumulative = 0.0
        for i, dist in enumerate(result.annual_distributions):
            expected_cumulative += dist
            assert abs(result.cumulative_distributions[i] - expected_cumulative) < 100
    
    def test_equity_irr_calculated(self, typical_fcfe_schedule):
        """Equity IRR should be calculated for immediate distributions."""
        result = calculate_immediate_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6
        )
        
        # IRR should be reasonable (10-20% range)
        assert 10.0 < result.equity_irr < 20.0, (
            f"Equity IRR should be 10-20%, got {result.equity_irr:.2f}%"
        )
    
    def test_total_distributed_equals_sum(self, typical_fcfe_schedule):
        """Total distributed should equal sum of annual distributions."""
        result = calculate_immediate_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6
        )
        
        expected_total = sum(typical_fcfe_schedule)
        assert abs(result.total_distributed - expected_total) < 1000


class TestDeferredDistributions:
    """Test tax-optimized deferred distribution logic."""
    
    def test_distributions_deferred_during_tlcf_period(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Distributions should be deferred while TLCF > threshold."""
        tlcf = TLCFSchedule(
            annual_tlcf=typical_tlcf_schedule,
            tlcf_utilization=[0.0] * len(typical_tlcf_schedule),
            tlcf_wasted=0.0,
            tlcf_exhaustion_year=5
        )
        
        result = calculate_deferred_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6,
            tlcf_schedule=tlcf,
            max_delay_years=5,
            tlcf_threshold=1e6
        )
        
        # Years 1-4 should have zero distributions (TLCF > $1M)
        for i in range(4):
            assert result.annual_distributions[i] == 0.0, (
                f"Year {i+1} should defer, got ${result.annual_distributions[i]/1e6:.1f}M"
            )
    
    def test_accumulated_distributions_released(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Accumulated distributions should be released after TLCF exhaustion."""
        tlcf = TLCFSchedule(
            annual_tlcf=typical_tlcf_schedule,
            tlcf_utilization=[0.0] * len(typical_tlcf_schedule),
            tlcf_wasted=0.0,
            tlcf_exhaustion_year=5
        )
        
        result = calculate_deferred_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6,
            tlcf_schedule=tlcf,
            max_delay_years=5,
            tlcf_threshold=1e6
        )
        
        # Year 5 (index 4) releases the accumulated deferrals + that year's FCFE.
        # Deferred years 2-4 FCFE ($5M + $5.5M + $6M = $16.5M) + year-5 FCFE ($6.5M)
        # = $23M (year-1 FCFE is 0, so nothing accrues in year 1).
        assert result.annual_distributions[4] == pytest.approx(23e6), (
            f"Year 5 should release accumulated + current, got ${result.annual_distributions[4]/1e6:.1f}M"
        )
    
    def test_max_delay_respected(self, typical_fcfe_schedule):
        """Distributions should not be deferred beyond max_delay_years."""
        # High TLCF for 10 years
        tlcf_long = [5e6] * 20
        tlcf = TLCFSchedule(
            annual_tlcf=tlcf_long,
            tlcf_utilization=[0.0] * 20,
            tlcf_wasted=0.0,
            tlcf_exhaustion_year=20
        )
        
        result = calculate_deferred_distributions(
            fcfe_schedule=typical_fcfe_schedule,
            equity_invested=50e6,
            tlcf_schedule=tlcf,
            max_delay_years=3,  # Max 3 years
            tlcf_threshold=1e6
        )
        
        # Year 4 (index 3) should have distributions despite high TLCF
        assert result.annual_distributions[3] > 0, (
            "Distributions should start after max_delay_years"
        )
    
    def test_total_distributed_unchanged(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Total distributed should equal FCFE regardless of timing."""
        tlcf = TLCFSchedule(
            annual_tlcf=typical_tlcf_schedule,
            tlcf_utilization=[0.0] * len(typical_tlcf_schedule),
            tlcf_wasted=0.0,
            tlcf_exhaustion_year=5
        )
        
        immediate = calculate_immediate_distributions(typical_fcfe_schedule, 50e6)
        deferred = calculate_deferred_distributions(
            typical_fcfe_schedule, 50e6, tlcf, max_delay_years=5, tlcf_threshold=1e6
        )
        
        # Total distributed should be the same (just timing differs)
        assert abs(immediate.total_distributed - deferred.total_distributed) < 1000


class TestTaxSavingsCalculation:
    """Test tax savings calculation logic."""
    
    def test_tax_savings_positive_with_deferral(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Deferring distributions during TLCF should create tax savings."""
        tlcf = TLCFSchedule(
            annual_tlcf=typical_tlcf_schedule,
            tlcf_utilization=[0.0] * len(typical_tlcf_schedule),
            tlcf_wasted=0.0,
            tlcf_exhaustion_year=5
        )
        
        immediate = calculate_immediate_distributions(typical_fcfe_schedule, 50e6)
        deferred = calculate_deferred_distributions(
            typical_fcfe_schedule, 50e6, tlcf, max_delay_years=5, tlcf_threshold=1e6
        )
        
        savings, savings_npv = calculate_tax_savings(
            immediate, deferred, tlcf, 0.28, discount_rate=0.12
        )
        
        # Distribution timing is value-neutral on a NOMINAL basis (the same total is
        # distributed), so the undiscounted total is ~0 by construction. The real
        # benefit is the NPV of deferring the dividend WHT to later years.
        assert savings == pytest.approx(0.0, abs=1.0), "Nominal distribution-tax total is conserved by timing"
        assert savings_npv > 0, "Deferring the distribution WHT yields a positive NPV benefit"
    
    def test_higher_tax_rate_increases_savings(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Higher tax rate should increase tax savings magnitude."""
        tlcf = TLCFSchedule(
            annual_tlcf=typical_tlcf_schedule,
            tlcf_utilization=[0.0] * len(typical_tlcf_schedule),
            tlcf_wasted=0.0,
            tlcf_exhaustion_year=5
        )
        
        immediate = calculate_immediate_distributions(typical_fcfe_schedule, 50e6)
        deferred = calculate_deferred_distributions(
            typical_fcfe_schedule, 50e6, tlcf, max_delay_years=5, tlcf_threshold=1e6
        )
        
        # Compare the NPV benefit (the meaningful, non-zero quantity) across rates;
        # the undiscounted total is ~0 by construction (timing-conserved).
        _, savings_npv_low = calculate_tax_savings(immediate, deferred, tlcf, 0.20)
        _, savings_npv_high = calculate_tax_savings(immediate, deferred, tlcf, 0.35)

        # Higher WHT rate should yield a larger NPV benefit.
        assert savings_npv_high > savings_npv_low, (
            f"Higher WHT rate should yield more NPV benefit: "
            f"low=${savings_npv_low/1e6:.2f}M, high=${savings_npv_high/1e6:.2f}M"
        )


class TestOptimizationIntegration:
    """Test complete optimization integration."""
    
    def test_optimization_produces_valid_result(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Complete optimization should produce valid result."""
        result = optimize_distribution_timing(
            fcfe_schedule=typical_fcfe_schedule,
            tlcf_schedule_data=typical_tlcf_schedule,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            target_equity_irr=0.15,
            max_delay_years=5
        )
        
        # Should have both base and optimized cases
        assert result.base_case is not None
        assert result.optimized_case is not None
        
        # Tax savings should be positive
        assert result.tax_savings_npv_usd > 0
        
        # Optimal delay should be reasonable (0-5 years)
        assert 0 <= result.optimal_delay_years <= 5
        
        # Recommendation should be non-empty
        assert len(result.recommendation) > 50
    
    def test_optimized_irr_lower_than_base(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Optimized IRR should be lower than base (trade-off)."""
        result = optimize_distribution_timing(
            fcfe_schedule=typical_fcfe_schedule,
            tlcf_schedule_data=typical_tlcf_schedule,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            target_equity_irr=0.15,
            max_delay_years=5
        )
        
        # Deferring distributions should reduce IRR slightly
        # (time value of money effect)
        assert result.optimized_case.equity_irr <= result.base_case.equity_irr, (
            f"Optimized IRR {result.optimized_case.equity_irr:.2f}% should be "
            f"<= base IRR {result.base_case.equity_irr:.2f}%"
        )
    
    def test_irr_reduction_reasonable(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """IRR reduction should be reasonable (< 3% for optimal timing)."""
        result = optimize_distribution_timing(
            fcfe_schedule=typical_fcfe_schedule,
            tlcf_schedule_data=typical_tlcf_schedule,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            target_equity_irr=0.15,
            max_delay_years=5
        )
        
        irr_reduction = result.base_case.equity_irr - result.optimized_case.equity_irr
        
        # Reduction should be < 3% for well-optimized timing
        assert irr_reduction < 3.0, (
            f"IRR reduction should be < 3%, got {irr_reduction:.2f}%"
        )


class TestRegressionPins:
    """Regression pins for tax optimization (TEST-01 compliance)."""
    
    def test_typical_project_optimal_delay(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Typical project should have 3-5 year optimal delay."""
        result = optimize_distribution_timing(
            fcfe_schedule=typical_fcfe_schedule,
            tlcf_schedule_data=typical_tlcf_schedule,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            target_equity_irr=0.15,
            max_delay_years=10
        )
        
        # Regression pin: Typical optimal delay is 3-5 years
        assert 3 <= result.optimal_delay_years <= 5, (
            f"Typical optimal delay should be 3-5 years, got {result.optimal_delay_years}"
        )
    
    def test_tax_savings_magnitude_reasonable(self, typical_fcfe_schedule, typical_tlcf_schedule):
        """Tax-deferral NPV benefit is a modest, positive fraction of $1M (dividend-WHT
        time value at the SL 15% rate) — not the multi-$M of the old simplified pin."""
        result = optimize_distribution_timing(
            fcfe_schedule=typical_fcfe_schedule,
            tlcf_schedule_data=typical_tlcf_schedule,
            equity_invested=50e6,  # 25% equity of $200M
            corporate_tax_rate=0.28,
            target_equity_irr=0.15,
            max_delay_years=5,
        )

        savings_m = result.tax_savings_npv_usd / 1e6

        # Regression pin: ~$0.4M NPV (dividend-WHT timing benefit at the SL 15% rate).
        assert 0.2 < savings_m < 1.0, (
            f"Tax-deferral NPV benefit should be ~$0.2-1.0M, got ${savings_m:.2f}M"
        )
    
    def test_dutchbay_baseline_optimization(self):
        """DutchBay baseline should optimize as expected."""
        # DutchBay 150MW: $200M CAPEX, 70% debt, 30% equity = $60M
        fcfe = [0] + [6e6 + i * 0.3e6 for i in range(19)]  # $6-11.7M FCFE
        tlcf = [6e6, 4e6, 2.5e6, 1.2e6, 0.5e6] + [0] * 15
        
        result = optimize_distribution_timing(
            fcfe_schedule=fcfe,
            tlcf_schedule_data=tlcf,
            equity_invested=60e6,
            corporate_tax_rate=0.28,
            target_equity_irr=0.15,
            max_delay_years=5
        )
        
        # DutchBay should have:
        # - Optimal delay: 4-5 years (TLCF exhausts ~year 5)
        # - Tax-deferral NPV benefit: ~$0.46M (dividend-WHT time value at SL 15%)
        # - Equity IRR reduction: < 2%

        assert 3 <= result.optimal_delay_years <= 5
        assert 0.25e6 < result.tax_savings_npv_usd < 0.75e6
        
        irr_reduction = result.base_case.equity_irr - result.optimized_case.equity_irr
        assert irr_reduction < 2.5, (
            f"DutchBay IRR reduction should be < 2.5%, got {irr_reduction:.2f}%"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
