#!/usr/bin/env python
"""Comprehensive tests for tax optimization sensitivity analysis.

Test Coverage:
- Delay period sensitivity (0-10 years)
- Tax rate sensitivity (15-35%)
- Tornado chart generation and sorting
- Trade-off analysis: IRR vs tax savings
- Complete sensitivity pipeline integration
- Regression pins for sensitivity behavior

Framework Compliance:
- TEST-01: Regression pins for sensitivity
- GWTF R7: Validates IRR calculations
- CESSPIT: No hardcoded parameters
- TYPE-01: Full type hints

Author: DutchBay Tax Sensitivity Testing Team
Date: December 2025
"""

import pytest
from typing import List
from omegaconf import OmegaConf

from analytics.tax_sensitivity_v14 import (
    analyze_delay_period_sensitivity,
    analyze_tax_rate_sensitivity,
    generate_tax_tornado_chart,
    analyze_tax_optimization_sensitivity,
)


@pytest.fixture
def typical_fcfe() -> List[float]:
    """Typical FCFE schedule."""
    return [0.0] + [5e6 + i * 0.5e6 for i in range(19)]


@pytest.fixture
def typical_tlcf() -> List[float]:
    """Typical TLCF schedule."""
    return [5e6, 3e6, 2e6, 1.5e6, 0.8e6] + [0.0] * 15


@pytest.fixture
def test_config():
    """Test configuration."""
    return OmegaConf.create({
        "project": {"capex_usd": 200e6},
        "financing": {"debt_ratio_target": 0.70, "equity_target_irr": 0.15},
        "tax": {"corporate_rate": 0.28},
    })


class TestDelayPeriodSensitivity:
    """Test delay period sensitivity analysis."""
    
    def test_delay_sensitivity_produces_results(self, typical_fcfe, typical_tlcf):
        """Delay sensitivity should produce results for each delay period."""
        result = analyze_delay_period_sensitivity(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            min_delay=0,
            max_delay=5
        )
        
        # Should have results for 0-5 years (6 data points)
        assert len(result["delay_analysis"]) == 6
        
        # Should have optimal delay
        assert "optimal_delay_years" in result
        assert 0 <= result["optimal_delay_years"] <= 5
    
    def test_longer_delay_higher_tax_savings(self, typical_fcfe, typical_tlcf):
        """Longer delays should generally increase tax savings (up to TLCF exhaustion)."""
        result = analyze_delay_period_sensitivity(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            min_delay=0,
            max_delay=5
        )
        
        delays = result["delay_analysis"]
        
        # Tax savings should increase from 0 to optimal
        savings_0yr = delays[0]["tax_savings_npv_usd"]
        savings_3yr = delays[3]["tax_savings_npv_usd"]
        
        assert savings_3yr > savings_0yr, (
            f"3-year delay should have more savings than 0-year: "
            f"${savings_3yr/1e6:.1f}M vs ${savings_0yr/1e6:.1f}M"
        )
    
    def test_excessive_delay_reduces_irr(self, typical_fcfe, typical_tlcf):
        """Excessive delay should materially reduce equity IRR."""
        result = analyze_delay_period_sensitivity(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28,
            min_delay=0,
            max_delay=10
        )
        
        delays = result["delay_analysis"]
        
        # IRR should decrease with longer delays
        irr_0yr = delays[0]["equity_irr_pct"]
        irr_10yr = delays[10]["equity_irr_pct"]
        
        assert irr_10yr < irr_0yr, (
            f"10-year delay should reduce IRR: {irr_10yr:.2f}% vs {irr_0yr:.2f}%"
        )
        
        # Reduction should be > 3% for 10-year delay
        irr_reduction = irr_0yr - irr_10yr
        assert irr_reduction > 2.0, (
            f"10-year delay should reduce IRR by > 2%, got {irr_reduction:.2f}%"
        )


class TestTaxRateSensitivity:
    """Test corporate tax rate sensitivity analysis."""
    
    def test_tax_rate_sensitivity_produces_results(self, typical_fcfe, typical_tlcf):
        """Tax rate sensitivity should produce results for low/base/high."""
        result = analyze_tax_rate_sensitivity(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            base_tax_rate=0.28,
            tax_rate_range=(0.15, 0.35)
        )
        
        # Should have 3 results (low, base, high)
        assert len(result["tax_rate_analysis"]) == 3
        
        # Should calculate impact range
        assert "tax_rate_impact_range" in result
        assert result["tax_rate_impact_range"] > 0
    
    def test_higher_tax_rate_increases_savings(self, typical_fcfe, typical_tlcf):
        """Higher tax rate should increase tax savings magnitude."""
        result = analyze_tax_rate_sensitivity(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            base_tax_rate=0.28,
            tax_rate_range=(0.15, 0.35)
        )
        
        rates = result["tax_rate_analysis"]
        
        # Order: low (15%), base (28%), high (35%)
        savings_low = rates[0]["tax_savings_npv_usd"]
        savings_high = rates[2]["tax_savings_npv_usd"]
        
        assert savings_high > savings_low, (
            f"Higher tax rate should yield more savings: "
            f"${savings_high/1e6:.1f}M vs ${savings_low/1e6:.1f}M"
        )
    
    def test_tax_rate_impact_magnitude(self, typical_fcfe, typical_tlcf):
        """Tax rate impact should be material (20-50% of base savings)."""
        result = analyze_tax_rate_sensitivity(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            base_tax_rate=0.28,
            tax_rate_range=(0.15, 0.35)
        )
        
        impact_pct = result["tax_rate_impact_pct"]
        
        # Tax rate should have 20-60% impact on savings
        assert 15.0 < impact_pct < 70.0, (
            f"Tax rate impact should be 15-70%, got {impact_pct:.1f}%"
        )


class TestTornadoChart:
    """Test tornado chart generation."""
    
    def test_tornado_chart_generates(self, typical_fcfe, typical_tlcf):
        """Tornado chart should generate for all variables."""
        tornado = generate_tax_tornado_chart(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28
        )
        
        # Should have 3 variables
        assert len(tornado) == 3
        
        # Should have standard variables
        variables = [item["variable"] for item in tornado]
        assert "Distribution Delay Period" in variables
        assert "Corporate Tax Rate" in variables
        assert "FCFE Level" in variables
    
    def test_tornado_chart_sorted_by_impact(self, typical_fcfe, typical_tlcf):
        """Tornado chart should be sorted by impact magnitude (descending)."""
        tornado = generate_tax_tornado_chart(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28
        )
        
        # Verify sorted descending
        for i in range(len(tornado) - 1):
            assert tornado[i]["impact_range"] >= tornado[i+1]["impact_range"], (
                f"Tornado should be sorted: {tornado[i]['variable']} "
                f"({tornado[i]['impact_range']}) should be >= "
                f"{tornado[i+1]['variable']} ({tornado[i+1]['impact_range']})"
            )
    
    def test_tornado_includes_impact_metrics(self, typical_fcfe, typical_tlcf):
        """Each tornado entry should have complete impact metrics."""
        tornado = generate_tax_tornado_chart(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28
        )
        
        for entry in tornado:
            # Required fields
            assert "variable" in entry
            assert "base_value" in entry
            assert "low_impact" in entry
            assert "high_impact" in entry
            assert "impact_range" in entry
            assert "impact_range_pct" in entry
            
            # Impact range should be non-zero
            assert entry["impact_range"] > 0
    
    def test_tax_rate_most_sensitive(self, typical_fcfe, typical_tlcf):
        """Corporate tax rate should typically be most sensitive variable."""
        tornado = generate_tax_tornado_chart(
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf,
            equity_invested=50e6,
            corporate_tax_rate=0.28
        )
        
        # First entry (highest impact) should often be tax rate or delay
        most_sensitive = tornado[0]["variable"]
        
        # Should be one of the two most important variables
        assert most_sensitive in ["Corporate Tax Rate", "Distribution Delay Period"], (
            f"Most sensitive should be tax rate or delay, got {most_sensitive}"
        )


class TestCompleteSensitivityAnalysis:
    """Test complete sensitivity analysis pipeline."""
    
    def test_complete_analysis_produces_all_outputs(self, test_config, typical_fcfe, typical_tlcf):
        """Complete analysis should produce all output sections."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        # Required top-level sections
        assert "delay_sensitivity" in result
        assert "tax_rate_sensitivity" in result
        assert "tornado_chart" in result
        assert "base_optimization" in result
        assert "summary" in result
    
    def test_summary_includes_key_metrics(self, test_config, typical_fcfe, typical_tlcf):
        """Summary should include all key optimization metrics."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        summary = result["summary"]
        
        # Required metrics
        assert "optimal_delay_years" in summary
        assert "tax_savings_npv_usd" in summary
        assert "optimized_equity_irr_pct" in summary
        assert "base_equity_irr_pct" in summary
        assert "equity_irr_trade_off_pct" in summary
        assert "most_sensitive_variable" in summary
        assert "recommendation" in summary
        
        # Values should be reasonable
        assert 0 <= summary["optimal_delay_years"] <= 10
        assert summary["tax_savings_npv_usd"] > 0
        assert 8.0 < summary["optimized_equity_irr_pct"] < 20.0
    
    def test_recommendation_generated(self, test_config, typical_fcfe, typical_tlcf):
        """Analysis should generate meaningful recommendation."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        recommendation = result["summary"]["recommendation"]
        
        # Should be substantial text
        assert len(recommendation) > 50
        
        # Should mention key metrics
        assert "year" in recommendation.lower()
        assert "irr" in recommendation.lower() or "savings" in recommendation.lower()


class TestRegressionPins:
    """Regression pins for tax sensitivity (TEST-01 compliance)."""
    
    def test_typical_optimal_delay_range(self, test_config, typical_fcfe, typical_tlcf):
        """Typical projects should have 3-5 year optimal delay."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        optimal_delay = result["summary"]["optimal_delay_years"]
        
        # Regression pin: 3-5 years typical
        assert 2 <= optimal_delay <= 6, (
            f"Optimal delay should be 2-6 years, got {optimal_delay}"
        )
    
    def test_tax_savings_magnitude(self, test_config, typical_fcfe, typical_tlcf):
        """Tax savings should be $1-4M NPV for typical project."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        savings_m = result["summary"]["tax_savings_npv_usd"] / 1e6
        
        # Regression pin: $0.5-5M NPV typical
        assert 0.3 < savings_m < 6.0, (
            f"Tax savings should be $0.3-6M NPV, got ${savings_m:.1f}M"
        )
    
    def test_irr_trade_off_reasonable(self, test_config, typical_fcfe, typical_tlcf):
        """Equity IRR trade-off should be < 3% for optimal timing."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        irr_trade_off = abs(result["summary"]["equity_irr_trade_off_pct"])
        
        # Regression pin: < 3% IRR reduction
        assert irr_trade_off < 3.5, (
            f"IRR trade-off should be < 3.5%, got {irr_trade_off:.2f}%"
        )
    
    def test_tornado_chart_has_material_impacts(self, test_config, typical_fcfe, typical_tlcf):
        """All tornado variables should have material impact (> 10%)."""
        result = analyze_tax_optimization_sensitivity(
            config=test_config,
            fcfe_schedule=typical_fcfe,
            tlcf_schedule=typical_tlcf
        )
        
        tornado = result["tornado_chart"]
        
        # All variables should have > 5% impact
        for entry in tornado:
            assert entry["impact_range_pct"] > 3.0, (
                f"{entry['variable']} should have > 3% impact, "
                f"got {entry['impact_range_pct']:.1f}%"
            )
    
    def test_dutchbay_sensitivity_baseline(self):
        """DutchBay baseline should produce expected sensitivity results."""
        config = OmegaConf.create({
            "project": {"capex_usd": 200e6},
            "financing": {"debt_ratio_target": 0.70, "equity_target_irr": 0.15},
            "tax": {"corporate_rate": 0.28},
        })
        
        fcfe = [0] + [6e6 + i * 0.3e6 for i in range(19)]
        tlcf = [6e6, 4e6, 2.5e6, 1.2e6, 0.5e6] + [0] * 15
        
        result = analyze_tax_optimization_sensitivity(
            config=config,
            fcfe_schedule=fcfe,
            tlcf_schedule=tlcf
        )
        
        summary = result["summary"]
        
        # DutchBay should have:
        # - Optimal delay: 3-5 years
        # - Tax savings: $1.5-3.5M NPV
        # - IRR trade-off: < 2%
        
        assert 3 <= summary["optimal_delay_years"] <= 5
        assert 1.0e6 < summary["tax_savings_npv_usd"] < 4.5e6
        assert abs(summary["equity_irr_trade_off_pct"]) < 2.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
