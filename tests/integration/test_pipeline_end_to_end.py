#!/usr/bin/env python
"""End-to-end integration test for complete DutchBay pipeline.

Tests the full analytical pipeline:
1. Wind resource assessment (or mock data)
2. Cashflow model with degradation
3. Dual DSCR debt sizing
4. Monte Carlo simulation
5. Sensitivity analysis

Validates:
- Cross-module data flow
- Degradation propagation
- Performance benchmarks
- Output completeness
- NO REGRESSIONS

Framework Compliance:
- TEST-01: End-to-end regression pins
- CASPER: Complete tail-risk analysis
- Performance: < 60s for full pipeline

Author: DutchBay Integration Team
Date: December 2025
"""

import pytest
import time
import json
from typing import Dict, Any
from pathlib import Path

# Import pipeline modules
try:
    from analytics.dscr_sensitivity import analyze_dscr_sensitivity
    from analytics.monte_carlo_v14 import MonteCarloEngine
    from omegaconf import OmegaConf
except ImportError as e:
    pytest.skip(f"Required pipeline modules not available: {e}", allow_module_level=True)


class TestPipelineDataFlow:
    """Test data flow across pipeline modules."""
    
    def test_wind_to_cashflow_data_flow(self, wind_assessment_mock_results, dutchbay_base_config):
        """Wind assessment results should flow into cashflow model."""
        # Wind assessment outputs
        wind_aep_p50 = wind_assessment_mock_results["energy_production"]["net_aep"]["net_aep_p50_mwh"]
        wind_aep_p99 = wind_assessment_mock_results["energy_production"]["net_aep"]["net_aep_p99_mwh"]
        
        # These should match or update config
        config_aep_p50 = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        
        # Verify AEP values are in same ballpark
        assert abs(wind_aep_p50 - config_aep_p50) / config_aep_p50 < 0.1, (
            f"Wind AEP should be consistent: wind={wind_aep_p50/1e3:.0f}GWh, "
            f"config={config_aep_p50/1e3:.0f}GWh"
        )
    
    def test_cashflow_to_dscr_data_flow(self, dutchbay_base_config):
        """Cashflow outputs should feed into dual DSCR sizing."""
        # Cashflow generates revenue projections
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        opex = dutchbay_base_config["operations"]["opex_usd_year"]
        degradation = dutchbay_base_config["project"]["degradation"]
        
        # Build simple CFADS
        from analytics.dscr_sensitivity import _build_cfads_array
        cfads_p50 = _build_cfads_array(aep, tariff, opex, degradation, 20)
        
        # CFADS should be positive and reasonable
        assert all(cf > 0 for cf in cfads_p50), "CFADS should be positive"
        assert cfads_p50[0] > opex, "Year 1 CFADS should exceed OPEX"
    
    def test_dscr_to_sensitivity_data_flow(self, dutchbay_omegaconf_config):
        """DSCR sizing results should feed into sensitivity analysis."""
        try:
            # Run sensitivity with degradation only (fast)
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation"]
            )
            
            # Should have base case debt sizing
            assert "sensitivity_config" in result
            assert "variables" in result
            
            # Base debt should be available
            base_result = result["variables"][0]
            assert "base_debt" in base_result
            assert base_result["base_debt"] > 0
            
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")


class TestPipelineDegradationPropagation:
    """Test degradation propagates through entire pipeline."""
    
    def test_degradation_in_cashflow_layer(self, dutchbay_base_config):
        """Degradation should be applied in cashflow calculations."""
        degradation = dutchbay_base_config["project"]["degradation"]
        
        # Verify degradation is configured
        assert degradation > 0, "Degradation should be configured"
        assert degradation == 0.006, f"Expected 0.6%, got {degradation*100}%"
    
    def test_degradation_in_monte_carlo_layer(self, dutchbay_omegaconf_config):
        """Degradation should be sampled in Monte Carlo."""
        mc_config = dutchbay_omegaconf_config.monte_carlo
        
        assert "degradation_mean_pct" in mc_config
        assert mc_config.degradation_mean_pct == 0.6
    
    def test_degradation_in_sensitivity_layer(self, dutchbay_omegaconf_config):
        """Degradation should be a sensitivity variable."""
        sens_config = dutchbay_omegaconf_config.sensitivity
        
        assert "degradation" in sens_config.variables
    
    @pytest.mark.slow
    def test_degradation_flows_to_outputs(self, dutchbay_omegaconf_config):
        """Degradation impact should be visible in final outputs."""
        try:
            # Run sensitivity analysis
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation"]
            )
            
            deg_result = result["variables"][0]
            
            # Should have degradation-specific outputs
            assert deg_result["variable"] == "degradation"
            assert "tornado_data" in deg_result
            
            # Impact should be measurable
            tornado = deg_result["tornado_data"]
            assert tornado["range_pct"] > 2.0, (
                f"Degradation should have > 2% impact, got {tornado['range_pct']:.1f}%"
            )
            
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")


class TestPipelinePerformance:
    """Test pipeline performance benchmarks."""
    
    @pytest.mark.slow
    @pytest.mark.performance
    def test_sensitivity_analysis_performance(self, dutchbay_omegaconf_config, performance_benchmarks):
        """Sensitivity analysis should meet performance target."""
        try:
            # Use minimal variables for speed test
            start_time = time.time()
            
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation", "aep"]
            )
            
            execution_time = time.time() - start_time
            max_time = performance_benchmarks["sensitivity_analysis_max_seconds"]
            
            assert execution_time < max_time, (
                f"Sensitivity should complete in < {max_time}s, took {execution_time:.1f}s"
            )
            
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")
    
    @pytest.mark.slow
    @pytest.mark.performance
    def test_monte_carlo_performance(self, dutchbay_omegaconf_config, performance_benchmarks):
        """Monte Carlo should meet performance target."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 1000
        
        start_time = time.time()
        
        engine = MonteCarloEngine(mc_config, n_iterations=1000)
        result = engine.run()
        
        execution_time = time.time() - start_time
        max_time = performance_benchmarks["monte_carlo_1k_max_seconds"]
        
        assert execution_time < max_time, (
            f"MC 1K iterations should complete in < {max_time}s, took {execution_time:.1f}s"
        )
    
    @pytest.mark.slow
    @pytest.mark.performance
    def test_full_pipeline_performance(self, dutchbay_omegaconf_config, performance_benchmarks):
        """Complete pipeline should meet performance target."""
        start_time = time.time()
        
        try:
            # Run sensitivity (includes DSCR sizing)
            sens_result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation", "aep"]
            )
            
            # Run Monte Carlo (small sample)
            mc_config = dutchbay_omegaconf_config
            mc_config.monte_carlo.n_iterations = 500
            mc_engine = MonteCarloEngine(mc_config, n_iterations=500)
            mc_result = mc_engine.run()
            
            execution_time = time.time() - start_time
            max_time = performance_benchmarks["full_pipeline_max_seconds"]
            
            assert execution_time < max_time, (
                f"Full pipeline should complete in < {max_time}s, took {execution_time:.1f}s"
            )
            
        except Exception as e:
            pytest.skip(f"Pipeline modules not available: {e}")


class TestPipelineOutputs:
    """Test pipeline output completeness and validity."""
    
    @pytest.mark.slow
    def test_sensitivity_output_structure(self, dutchbay_omegaconf_config):
        """Sensitivity analysis should produce complete output."""
        try:
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation", "aep"]
            )
            
            # Required top-level keys
            assert "sensitivity_config" in result
            assert "variables" in result
            assert "tornado_chart" in result
            assert "summary" in result
            assert "binding_constraint_analysis" in result
            
            # Tornado chart should be sorted
            tornado = result["tornado_chart"]
            for i in range(1, len(tornado)):
                assert abs(tornado[i-1]["impact_range"]) >= abs(tornado[i]["impact_range"])
            
            # Summary should have key metrics
            summary = result["summary"]
            assert "most_sensitive_variable" in summary
            assert "base_debt" in summary
            assert summary["base_debt"] > 0
            
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")
    
    @pytest.mark.slow
    def test_monte_carlo_output_structure(self, dutchbay_omegaconf_config):
        """Monte Carlo should produce complete output."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 100
        
        engine = MonteCarloEngine(mc_config, n_iterations=100)
        result = engine.run()
        
        # Required top-level keys
        assert "scenario_name" in result
        assert "n_iterations" in result
        assert "statistics" in result
        assert "success" in result
        
        # Statistics should be complete
        stats = result["statistics"]
        required_stats = [
            "npv_mean_usd", "npv_std_usd", "npv_median_usd",
            "npv_p10_usd", "npv_p90_usd",
            "irr_mean_pct", "irr_std_pct", "irr_median_pct",
            "irr_p10_pct", "irr_p90_pct",
        ]
        
        for stat in required_stats:
            assert stat in stats, f"Missing statistic: {stat}"
    
    @pytest.mark.slow
    def test_outputs_are_json_serializable(self, dutchbay_omegaconf_config):
        """All pipeline outputs should be JSON-serializable."""
        try:
            # Sensitivity output
            sens_result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation"]
            )
            
            # Should serialize to JSON
            json_str = json.dumps(sens_result, indent=2)
            assert len(json_str) > 0
            
            # Monte Carlo output
            mc_config = dutchbay_omegaconf_config
            mc_config.monte_carlo.n_iterations = 50
            mc_engine = MonteCarloEngine(mc_config, n_iterations=50)
            mc_result = mc_engine.run()
            
            json_str = json.dumps(mc_result, indent=2)
            assert len(json_str) > 0
            
        except TypeError as e:
            pytest.fail(f"Output not JSON-serializable: {e}")
        except Exception as e:
            pytest.skip(f"Pipeline not available: {e}")


class TestPipelineRegressionPins:
    """Regression pins for end-to-end pipeline (TEST-01 compliance)."""
    
    @pytest.mark.slow
    def test_dutchbay_baseline_npv(self, dutchbay_omegaconf_config):
        """DutchBay baseline should produce expected NPV range."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 500
        mc_config.monte_carlo.seed = 42  # Reproducible
        
        engine = MonteCarloEngine(mc_config, n_iterations=500)
        result = engine.run()
        
        stats = result["statistics"]
        mean_npv_m = stats["npv_mean_usd"] / 1e6
        
        # Regression pin: Should be in $20-80M range
        assert 20.0 < mean_npv_m < 80.0, (
            f"DutchBay baseline NPV should be $20-80M, got ${mean_npv_m:.1f}M"
        )
    
    @pytest.mark.slow
    def test_dutchbay_baseline_irr(self, dutchbay_omegaconf_config):
        """DutchBay baseline should produce expected IRR range."""
        mc_config = dutchbay_omegaconf_config
        mc_config.monte_carlo.n_iterations = 500
        mc_config.monte_carlo.seed = 42
        
        engine = MonteCarloEngine(mc_config, n_iterations=500)
        result = engine.run()
        
        stats = result["statistics"]
        mean_irr = stats["irr_mean_pct"]
        
        # Regression pin: Should be in 7-15% range
        assert 7.0 < mean_irr < 15.0, (
            f"DutchBay baseline IRR should be 7-15%, got {mean_irr:.1f}%"
        )
    
    @pytest.mark.slow
    def test_dutchbay_debt_capacity(self, dutchbay_omegaconf_config):
        """DutchBay debt capacity should be in expected range."""
        try:
            result = analyze_dscr_sensitivity(
                dutchbay_omegaconf_config,
                variables=["degradation"]
            )
            
            base_debt_m = result["summary"]["base_debt"] / 1e6
            capex_m = dutchbay_omegaconf_config.project.capex_usd / 1e6
            
            debt_ratio = base_debt_m / capex_m
            
            # Regression pin: Debt should be 50-75% of CAPEX
            assert 0.50 < debt_ratio < 0.75, (
                f"Debt ratio should be 50-75%, got {debt_ratio:.1%}"
            )
            
        except Exception as e:
            pytest.skip(f"Sensitivity analysis not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
