#!/usr/bin/env python
"""Tests for proper corporate tax calculation with TLCF.

Test Coverage:
- Taxable income calculation (Revenue - OPEX - Depreciation - Interest)
- TLCF accumulation and utilization
- Tax liability with TLCF shield
- CAFOD (Cash Available For Distribution) calculation
- Depreciation methods (straight-line, MACRS)
- Tax savings from TLCF utilization
- DutchBay baseline validation

Framework Compliance:
- TEST-01: Regression pins for tax behavior
- GWTF: Validates proper tax mechanics
- CASPER: Conservative assumption verification

Author: DutchBay Tax Testing Team
Date: December 2025
"""

import pytest
from typing import List

from finance.tax_schedule_v14 import (
    calculate_corporate_tax_schedule,
    calculate_straight_line_depreciation,
    calculate_macrs_depreciation,
    calculate_tax_savings_from_tlcf,
    DepreciationMethod,
    TaxSchedule,
)


def _amortizing_interest(
    debt: float, rate: float, tenor_years: int, project_life: int
) -> List[float]:
    """Declining annual interest on an equal-principal amortizing debt balance.

    Mirrors finance.debt_v14's amortizing schedules (interest = outstanding * rate),
    so fixtures exercise a realistic *declining* interest profile. A flat schedule
    (the prior fixture bug) drives perpetual losses -> unbounded TLCF -> $0 tax (#59).

    Args:
        debt: Initial debt principal (USD).
        rate: Annual interest rate (decimal).
        tenor_years: Years over which principal amortizes to zero.
        project_life: Number of annual periods to emit.

    Returns:
        List of annual interest expense (USD), declining to 0 after ``tenor_years``.
    """
    schedule: List[float] = []
    balance = debt
    principal = debt / tenor_years
    for _ in range(project_life):
        schedule.append(max(0.0, balance) * rate)
        balance = max(0.0, balance - principal)
    return schedule


@pytest.fixture
def typical_project_params():
    """Typical wind project parameters."""
    return {
        "capex": 200e6,
        "project_life": 20,
        "revenue": [20e6 + i * 0.5e6 for i in range(20)],
        "opex": [7e6] * 20,
        "debt": 140e6,
        "interest_rate": 0.08,
    }


class TestDepreciationCalculation:
    """Test depreciation schedule calculations."""
    
    def test_straight_line_depreciation(self):
        """Straight-line should produce equal annual depreciation."""
        depreciation = calculate_straight_line_depreciation(
            capex=200e6,
            useful_life_years=10,
            project_life_years=20
        )
        
        # Years 1-10: Equal depreciation
        for year in range(10):
            assert depreciation.annual_depreciation[year] == 20e6, (
                f"Year {year+1} should have $20M depreciation"
            )
        
        # Years 11-20: Zero depreciation
        for year in range(10, 20):
            assert depreciation.annual_depreciation[year] == 0, (
                f"Year {year+1} should have $0 depreciation (fully depreciated)"
            )
        
        # Final book value should be zero
        assert depreciation.book_value[-1] == 0
    
    def test_macrs_depreciation_accelerated(self):
        """MACRS should frontload depreciation vs straight-line."""
        macrs = calculate_macrs_depreciation(
            capex=200e6,
            macrs_class=DepreciationMethod.MACRS_7,
            project_life_years=20
        )
        
        straight_line = calculate_straight_line_depreciation(
            capex=200e6,
            useful_life_years=7,
            project_life_years=20
        )
        
        # Year 1: MACRS should be higher (accelerated)
        assert macrs.annual_depreciation[0] > straight_line.annual_depreciation[0], (
            "MACRS Year 1 should exceed straight-line"
        )
        
        # Year 7: MACRS should be lower (tail-end)
        assert macrs.annual_depreciation[6] < straight_line.annual_depreciation[6], (
            "MACRS Year 7 should be less than straight-line"
        )
        
        # Total depreciation should equal CAPEX
        assert abs(sum(macrs.annual_depreciation) - 200e6) < 1000, (
            "Total MACRS depreciation should equal CAPEX"
        )


class TestTaxableIncomeCalculation:
    """Test proper taxable income calculation."""
    
    def test_ebitda_calculation(self, typical_project_params):
        """EBITDA = Revenue - OPEX."""
        params = typical_project_params
        
        # Simple depreciation
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Verify EBITDA = Revenue - OPEX
        for t in range(params["project_life"]):
            expected_ebitda = params["revenue"][t] - params["opex"][t]
            assert abs(tax_schedule.annual_ebitda[t] - expected_ebitda) < 1, (
                f"Year {t+1} EBITDA calculation incorrect"
            )
    
    def test_ebit_calculation(self, typical_project_params):
        """EBIT = EBITDA - Depreciation."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Verify EBIT = EBITDA - Depreciation
        for t in range(params["project_life"]):
            expected_ebit = tax_schedule.annual_ebitda[t] - depreciation.annual_depreciation[t]
            assert abs(tax_schedule.annual_ebit[t] - expected_ebit) < 1, (
                f"Year {t+1} EBIT calculation incorrect"
            )
    
    def test_ebt_calculation(self, typical_project_params):
        """EBT = EBIT - Interest."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Verify EBT = EBIT - Interest
        for t in range(params["project_life"]):
            expected_ebt = tax_schedule.annual_ebit[t] - interest[t]
            assert abs(tax_schedule.annual_ebt[t] - expected_ebt) < 1, (
                f"Year {t+1} EBT calculation incorrect"
            )


class TestTLCFMechanics:
    """Test Tax Loss Carryforward mechanics."""
    
    def test_tlcf_accumulation_during_loss_years(self, typical_project_params):
        """TLCF should accumulate during loss years (negative EBT)."""
        params = typical_project_params
        
        # Use accelerated depreciation to create early losses
        depreciation = calculate_macrs_depreciation(
            capex=params["capex"],
            macrs_class=DepreciationMethod.MACRS_7
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Early years should have TLCF accumulation
        assert tax_schedule.annual_tlcf_balance[0] > 0, (
            "Year 1 should have TLCF (loss year)"
        )
        
        # TLCF should peak in early years
        peak_tlcf = max(tax_schedule.annual_tlcf_balance)
        assert peak_tlcf > 10e6, (
            f"Peak TLCF should exceed $10M, got ${peak_tlcf/1e6:.1f}M"
        )
    
    def test_tlcf_utilization_during_profit_years(self, typical_project_params):
        """TLCF should be utilized during profit years to reduce tax."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Find first profit year after loss year
        for t in range(1, params["project_life"]):
            if (tax_schedule.annual_ebt[t] > 0 and 
                tax_schedule.annual_tlcf_balance[t-1] > 0):
                # Should utilize TLCF
                assert tax_schedule.annual_tlcf_utilized[t] > 0, (
                    f"Year {t+1} should utilize TLCF (profit year with TLCF available)"
                )
                break
    
    def test_tlcf_exhaustion_timing(self, typical_project_params):
        """TLCF exhausts in the back half of project life under amortizing debt."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Regression pin (TEST-01): with amortizing debt, accumulated TLCF is
        # not consumed until the back half of the 20-year life (~year 16).
        assert 13 <= tax_schedule.tlcf_exhaustion_year <= 19, (
            f"TLCF exhaustion year {tax_schedule.tlcf_exhaustion_year} "
            f"should be ~16 (back half) for typical project"
        )


class TestTaxLiabilityCalculation:
    """Test corporate tax liability calculation."""
    
    def test_no_tax_during_loss_years(self, typical_project_params):
        """No tax should be paid during loss years (negative EBT)."""
        params = typical_project_params
        
        # Create loss years with high depreciation
        depreciation = [40e6] * 5 + [0] * 15  # Front-loaded
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Loss years should have zero tax
        for t in range(5):
            if tax_schedule.annual_ebt[t] < 0:
                assert tax_schedule.annual_tax_liability[t] == 0, (
                    f"Year {t+1} (loss year) should have $0 tax"
                )
    
    def test_tax_with_tlcf_shield(self, typical_project_params):
        """Tax should be reduced when TLCF shields taxable income."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Find year with TLCF utilization
        for t in range(params["project_life"]):
            if tax_schedule.annual_tlcf_utilized[t] > 0:
                # Taxable income should be reduced by TLCF
                ebt = tax_schedule.annual_ebt[t]
                tlcf_used = tax_schedule.annual_tlcf_utilized[t]
                taxable = tax_schedule.annual_taxable_income[t]
                
                assert abs(taxable - (ebt - tlcf_used)) < 1, (
                    f"Year {t+1} taxable income should be EBT - TLCF"
                )
                
                # Tax should be on reduced taxable income
                expected_tax = taxable * 0.28
                assert abs(tax_schedule.annual_tax_liability[t] - expected_tax) < 1, (
                    f"Year {t+1} tax should be {expected_tax/1e6:.1f}M"
                )
                break


class TestCAFODCalculation:
    """Test Cash Available For Distribution calculation."""
    
    def test_cafod_formula(self, typical_project_params):
        """CAFOD = Revenue - OPEX - Interest - Tax + Depreciation."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # Verify CAFOD = Revenue - OPEX - Interest - Tax + Depreciation
        for t in range(params["project_life"]):
            expected_cafod = (
                params["revenue"][t] -
                params["opex"][t] -
                interest[t] -
                tax_schedule.annual_tax_liability[t] +
                depreciation.annual_depreciation[t]
            )
            
            assert abs(tax_schedule.annual_cafod[t] - expected_cafod) < 1, (
                f"Year {t+1} CAFOD calculation incorrect"
            )
    
    def test_cafod_always_positive(self, typical_project_params):
        """CAFOD should be positive throughout project life (viable project)."""
        params = typical_project_params
        
        depreciation = calculate_straight_line_depreciation(
            capex=params["capex"],
            useful_life_years=10,
            project_life_years=params["project_life"]
        )
        
        interest = _amortizing_interest(
            params["debt"], params["interest_rate"], 15, params["project_life"]
        )
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=params["revenue"],
            opex_schedule=params["opex"],
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        # All years should have positive CAFOD
        for t, cafod in enumerate(tax_schedule.annual_cafod):
            assert cafod > 0, (
                f"Year {t+1} CAFOD ${cafod/1e6:.1f}M should be positive"
            )


class TestRegressionPins:
    """Regression pins for DutchBay baseline (TEST-01 compliance)."""
    
    def test_dutchbay_baseline_tlcf(self):
        """DutchBay baseline: amortizing debt + 15-yr depreciation -> ~$59M peak TLCF."""
        capex = 200e6
        project_life = 20
        revenue = [20e6 + i * 0.5e6 for i in range(project_life)]
        opex = [7e6] * project_life
        
        depreciation = calculate_straight_line_depreciation(capex, 15, 0, project_life)
        
        debt = 140e6
        interest = _amortizing_interest(debt, 0.08, 15, project_life)
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=revenue,
            opex_schedule=opex,
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        peak_tlcf = max(tax_schedule.annual_tlcf_balance)
        
        # Regression pin (TEST-01): declining interest + 15-yr straight-line
        # depreciation yield ~$59.2M peak TLCF for the DutchBay baseline.
        assert 52e6 < peak_tlcf < 66e6, (
            f"DutchBay peak TLCF should be ~$59M, got ${peak_tlcf/1e6:.1f}M"
        )
    
    def test_dutchbay_baseline_total_tax(self):
        """DutchBay baseline: amortizing debt -> ~$18M total corporate tax over 20y."""
        capex = 200e6
        project_life = 20
        revenue = [20e6 + i * 0.5e6 for i in range(project_life)]
        opex = [7e6] * project_life
        
        depreciation = calculate_straight_line_depreciation(capex, 15, 0, project_life)
        
        debt = 140e6
        interest = _amortizing_interest(debt, 0.08, 15, project_life)
        
        tax_schedule = calculate_corporate_tax_schedule(
            revenue_schedule=revenue,
            opex_schedule=opex,
            depreciation_schedule=depreciation.annual_depreciation,
            interest_schedule=interest,
            corporate_tax_rate=0.28
        )
        
        total_tax = sum(tax_schedule.annual_tax_liability) / 1e6
        
        # Regression pin (TEST-01): declining interest retires the legacy $0-tax
        # artifact (#59); ~$18.3M total corporate tax over 20 years.
        assert 15 < total_tax < 22, (
            f"DutchBay total tax should be ~$18M (non-zero), got ${total_tax:.1f}M"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
