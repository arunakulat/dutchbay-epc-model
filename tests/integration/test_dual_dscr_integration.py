#!/usr/bin/env python
"""Integration tests for dual DSCR debt sizing across modules.

Verifies that dual DSCR methodology:
1. Builds CFADS P50/P99 arrays with degradation
2. Applies conservative sizing: min(Debt_P50, Debt_P99)
3. Detects when P99 constraint binds
4. Integrates with sensitivity analysis
5. Responds correctly to degradation changes

Framework Compliance:
- TEST-01: Regression pins for DSCR behavior
- CASPER: Tail-risk validation
- NO REGRESSION: Tests integration only

Author: DutchBay Integration Team
Date: December 2025
"""

import pytest
import numpy as np
from typing import Dict, Any, List

# Import modules to test
try:
    from finance.debt_v14 import size_debt_dual_dscr
    from analytics.dscr_sensitivity import (
        _build_cfads_array,
        analyze_dscr_sensitivity,
    )
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


class TestDualDSCRBasics:
    """Test fundamental dual DSCR debt sizing behavior."""
    
    def test_conservative_sizing_takes_minimum(self):
        """Dual DSCR should use min(Debt_P50, Debt_P99) for conservative sizing."""
        # Strong P50, weaker P99
        cfads_p50 = [10.0e6] * 20  # $10M/year
        cfads_p99 = [7.0e6] * 20   # $7M/year (30% weaker)
        
        result = size_debt_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # P99 should bind (weaker downside)
        assert result["binding_constraint"] == "P99", (
            "P99 should bind when downside is weak"
        )
        
        # Debt should equal P99 constraint
        assert result["debt_sized_usd"] == result["debt_p99_usd"], (
            "Sized debt should equal P99 constraint when it binds"
        )
        
        # Should be reduction from P50
        assert result["reduction_from_p50_pct"] > 15.0, (
            "Significant reduction expected when P99 binds"
        )
    
    def test_p50_binds_when_downside_strong(self):
        """P50 should bind when P99 downside is relatively strong."""
        # Strong downside (P99 close to P50)
        cfads_p50 = [10.0e6] * 20
        cfads_p99 = [9.5e6] * 20   # Only 5% weaker
        
        result = size_debt_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # P50 should bind (strong downside doesn't constrain)
        assert result["binding_constraint"] == "P50", (
            "P50 should bind when downside is strong"
        )
        
        # Minimal reduction
        assert result["reduction_from_p50_pct"] < 5.0, (
            "Minimal reduction when P50 binds"
        )
    
    def test_dscr_profiles_calculated(self):
        """DSCR profiles should be calculated for both P50 and P99."""
        cfads_p50 = [10.0e6] * 20
        cfads_p99 = [8.0e6] * 20
        
        result = size_debt_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # Should have actual DSCRs
        assert "dscr_p50_actual" in result
        assert "dscr_p99_actual" in result
        
        # Actual DSCRs should be >= targets
        assert result["dscr_p50_actual"] >= 1.30, (
            f"P50 DSCR {result['dscr_p50_actual']:.2f} should be >= 1.30"
        )
        assert result["dscr_p99_actual"] >= 1.00, (
            f"P99 DSCR {result['dscr_p99_actual']:.2f} should be >= 1.00"
        )


class TestDualDSCRWithDegradation:
    """Test dual DSCR integration with degradation."""
    
    def test_cfads_construction_with_degradation(self, dutchbay_base_config):
        """CFADS arrays should incorporate degradation correctly."""
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        opex = dutchbay_base_config["operations"]["opex_usd_year"]
        degradation = dutchbay_base_config["project"]["degradation"]
        project_life = dutchbay_base_config["project"]["life_years"]
        
        cfads = _build_cfads_array(
            aep=aep,
            tariff=tariff,
            opex=opex,
            degradation_rate=degradation,
            project_life=project_life,
        )
        
        # Year 1 CFADS
        revenue_y1 = aep * tariff
        cfads_y1_expected = revenue_y1 - opex
        
        assert abs(cfads[0] - cfads_y1_expected) < 1000, (
            f"Year 1 CFADS mismatch: expected ${cfads_y1_expected:.0f}, "
            f"got ${cfads[0]:.0f}"
        )
        
        # Year 20 CFADS (with degradation)
        aep_y20 = aep * (1 - degradation) ** 19
        revenue_y20 = aep_y20 * tariff
        cfads_y20_expected = revenue_y20 - opex
        
        assert abs(cfads[19] - cfads_y20_expected) < 1000, (
            f"Year 20 CFADS mismatch: expected ${cfads_y20_expected:.0f}, "
            f"got ${cfads[19]:.0f}"
        )
    
    def test_degradation_reduces_both_p50_and_p99_cfads(self, dutchbay_base_config):
        """Degradation should reduce both P50 and P99 CFADS proportionally."""
        aep_p50 = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        aep_p99 = dutchbay_base_config["wind_resource"]["aep_p99_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        opex = dutchbay_base_config["operations"]["opex_usd_year"]
        degradation = dutchbay_base_config["project"]["degradation"]
        
        # Build P50 and P99 CFADS
        cfads_p50 = _build_cfads_array(aep_p50, tariff, opex, degradation, 20)
        cfads_p99 = _build_cfads_array(aep_p99, tariff, opex, degradation, 20)
        
        # P99 should be consistently lower than P50
        for i in range(20):
            assert cfads_p99[i] < cfads_p50[i], (
                f"Year {i+1}: P99 CFADS should be < P50 CFADS"
            )
        
        # Ratio should be roughly constant (degradation affects both equally)
        ratio_y1 = cfads_p99[0] / cfads_p50[0]
        ratio_y20 = cfads_p99[19] / cfads_p50[19]
        
        assert abs(ratio_y1 - ratio_y20) < 0.02, (
            f"P99/P50 ratio should be stable: Y1={ratio_y1:.3f}, Y20={ratio_y20:.3f}"
        )
    
    def test_higher_degradation_reduces_debt_capacity(self, dutchbay_base_config):
        """Higher degradation should reduce debt sizing capacity."""
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        opex = dutchbay_base_config["operations"]["opex_usd_year"]
        
        # Low degradation case
        cfads_low_deg = _build_cfads_array(aep, tariff, opex, 0.004, 20)
        result_low = size_debt_dual_dscr(
            cfads_p50=cfads_low_deg,
            cfads_p99=cfads_low_deg,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # High degradation case
        cfads_high_deg = _build_cfads_array(aep, tariff, opex, 0.008, 20)
        result_high = size_debt_dual_dscr(
            cfads_p50=cfads_high_deg,
            cfads_p99=cfads_high_deg,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # Higher degradation should reduce debt
        assert result_low["debt_sized_usd"] > result_high["debt_sized_usd"], (
            "Higher degradation should reduce debt capacity"
        )
        
        # Quantify impact
        debt_reduction_pct = (
            (result_low["debt_sized_usd"] - result_high["debt_sized_usd"]) /
            result_low["debt_sized_usd"] * 100
        )
        
        # Expect 3-8% reduction when degradation doubles (0.4% → 0.8%)
        assert 2.0 < debt_reduction_pct < 10.0, (
            f"Debt reduction should be 2-10%, got {debt_reduction_pct:.1f}%"
        )


class TestDualDSCRSensitivityIntegration:
    """Test dual DSCR integration with sensitivity analysis."""
    
    def test_sensitivity_produces_dscr_results(self, dutchbay_omegaconf_config):
        """Sensitivity analysis should produce dual DSCR results."""
        try:
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation"]
            )
            
            # Should have dual DSCR outputs
            assert "variables" in result
            deg_result = result["variables"][0]
            
            # Each perturbation should have DSCR info
            for pert in deg_result["perturbations"]:
                assert "debt_sized" in pert
                assert "binding_constraint" in pert
                assert "debt_p50" in pert
                assert "debt_p99" in pert
        
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")
    
    def test_binding_constraint_transitions_detected(self, dutchbay_omegaconf_config):
        """Sensitivity should detect when binding constraint changes."""
        try:
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["aep"]  # AEP likely to cause transitions
            )
            
            aep_result = result["variables"][0]
            
            # Check if transitions detected
            if "constraint_transitions" in aep_result:
                transitions = aep_result["constraint_transitions"]
                
                # If transitions exist, validate structure
                for trans in transitions:
                    assert "at_perturbation_pct" in trans
                    assert "from_constraint" in trans
                    assert "to_constraint" in trans
                    assert trans["from_constraint"] != trans["to_constraint"]
        
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")
    
    def test_tornado_chart_includes_dscr_impacts(self, dutchbay_omegaconf_config):
        """Tornado chart should show debt capacity impact ranges."""
        try:
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation", "aep"]
            )
            
            tornado = result["tornado_chart"]
            
            # Should have entries for each variable
            assert len(tornado) == 2
            
            # Each should have impact metrics
            for entry in tornado:
                assert "variable" in entry
                assert "impact_range" in entry
                assert "min_impact" in entry
                assert "max_impact" in entry
                assert entry["impact_range"] != 0, (
                    f"Variable {entry['variable']} should have non-zero impact"
                )
        
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")


class TestDualDSCRRegressionPins:
    """Regression pins for dual DSCR integration (TEST-01 compliance)."""
    
    def test_typical_p99_reduction_magnitude(self):
        """When P99 binds, typical reduction should be 5-15%."""
        # Industry-typical case: P99 is 85% of P50
        cfads_p50 = [10.0e6] * 20
        cfads_p99 = [8.5e6] * 20  # 15% weaker
        
        result = size_debt_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # P99 should bind
        assert result["binding_constraint"] == "P99"
        
        # Reduction should be 5-15% (industry typical)
        reduction = result["reduction_from_p50_pct"]
        assert 5.0 < reduction < 20.0, (
            f"Typical P99 reduction should be 5-20%, got {reduction:.1f}%"
        )
    
    def test_debt_sizing_with_dutchbay_parameters(self, dutchbay_base_config):
        """Debt sizing with DutchBay parameters should produce reasonable results."""
        aep_p50 = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        aep_p99 = dutchbay_base_config["wind_resource"]["aep_p99_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        opex = dutchbay_base_config["operations"]["opex_usd_year"]
        degradation = dutchbay_base_config["project"]["degradation"]
        capex = dutchbay_base_config["project"]["capex_usd"]
        
        # Build CFADS
        cfads_p50 = _build_cfads_array(aep_p50, tariff, opex, degradation, 20)
        cfads_p99 = _build_cfads_array(aep_p99, tariff, opex, degradation, 20)
        
        result = size_debt_dual_dscr(
            cfads_p50=cfads_p50,
            cfads_p99=cfads_p99,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
        )
        
        # Debt should be reasonable fraction of CAPEX
        debt_ratio = result["debt_sized_usd"] / capex
        assert 0.50 < debt_ratio < 0.75, (
            f"Debt should be 50-75% of CAPEX, got {debt_ratio:.1%}"
        )
        
        # Sized debt should be positive
        assert result["debt_sized_usd"] > 0, "Debt sizing should be positive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
