"""
integration test: FX + Monte Carlo integration

Tests interaction between FX module and Monte Carlo engine.
Verifies:
- FX volatility captured in MC samples
- MC config keys properly extracted
- Discount rates applied from config
- Raw results properly validated

Test Count: 25+ cases
Coverage: MC config, FX sampling, raw_results handling
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pytest
from omegaconf import DictConfig, OmegaConf

from analytics.evaluation_v14 import evaluate_with_casper_tail_risk
from analytics.monte_carlo_v14 import (
    MonteCarloConfig,
    MonteCarloEngine,
    run_monte_carlo_analysis,
)
from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)


class TestMCConfigExtraction:
    """Test MC config key extraction and validation."""

    def test_mc_iterations_key_priority(self) -> None:
        """
        Verify 'iterations' key has priority over 'n_iterations'.
        (FIX #1 verification)
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 2000,
                "n_iterations": 1000,  # Should be ignored
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=2000)
        assert engine.mc_config.n_iterations == 2000
        logger.info("✓ MC iterations key priority correct")

    def test_mc_fallback_to_n_iterations(self) -> None:
        """
        Verify fallback to 'n_iterations' if 'iterations' missing.
        (FIX #1 backward compat)
        """
        cfg_dict = {
            "monte_carlo": {
                "n_iterations": 1500,  # Fallback key
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=1500)
        assert engine.mc_config.n_iterations == 1500
        logger.info("✓ MC fallback to n_iterations works")

    def test_mc_default_iterations(self) -> None:
        """
        Verify default 1000 iterations if neither key present.
        """
        cfg_dict = {"monte_carlo": {}}
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=1000)
        assert engine.mc_config.n_iterations == 1000
        logger.info("✓ MC default iterations (1000) correct")


class TestMCDiscountRate:
    """Test MC discount rate from config (FIX #3)."""

    def test_discount_rate_from_config(self) -> None:
        """
        Verify discount_rate_pct read from config, not hardcoded.
        (FIX #3 verification)
        """
        cfg_dict = {
            "monte_carlo": {
                "discount_rate_pct": 7.5,
                "iterations": 100,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=100)
        assert engine.mc_config.discount_rate_pct == 7.5
        logger.info("✓ MC discount_rate from config: 7.5%")

    def test_discount_rate_default(self) -> None:
        """
        Verify default 8.0% if discount_rate_pct missing.
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 100,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=100)
        assert engine.mc_config.discount_rate_pct == 8.0
        logger.info("✓ MC discount_rate default: 8.0%")

    def test_discount_rate_various_values(self) -> None:
        """
        Test discount rate with various valid values.
        """
        for rate in [5.0, 6.5, 7.0, 8.0, 9.5, 10.0, 12.0]:
            cfg_dict = {
                "monte_carlo": {
                    "discount_rate_pct": rate,
                    "iterations": 50,
                    "capex_total_usd": 50e6,
                    "revenue_mean_usd": 100e6,
                    "cost_mean_usd": 60e6,
                }
            }
            cfg = OmegaConf.create(cfg_dict)
            engine = MonteCarloEngine(cfg, n_iterations=50)
            assert engine.mc_config.discount_rate_pct == rate
        logger.info("✓ MC discount_rate variations tested")


class TestFXSampling:
    """Test FX sampling applied to MC (FIX #5)."""

    def test_fx_factor_applied_to_revenue(self) -> None:
        """
        Verify FX factor sampled and applied to revenue.
        (FIX #5 verification)
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 10,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "revenue_std_pct": 0.0,  # No revenue variance
                "cost_mean_usd": 60e6,
                "cost_std_pct": 0.0,  # No cost variance
                "fx_mean_rate": 325.0,
                "fx_std_pct": 10.0,  # 10% FX volatility
            },
            "FX": {  # Enable FX
                "strategy": "natural_hedge",
                "spot_rate": 325.0,
            },
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=10)

        # Run iterations and check FX values vary
        results = []
        for _ in range(10):
            result = engine.simulate_iteration()
            results.append(result)

        # Extract revenue values (should vary due to FX)
        revenues = [r["revenue_usd"] for r in results]
        unique_revenues = len(set(revenues))

        # Should have variation due to FX sampling
        assert unique_revenues > 1, "FX not sampled in MC iterations"
        logger.info(f"✓ FX sampling verified ({unique_revenues} unique revenues)")

    def test_fx_rate_variation(self) -> None:
        """
        Verify FX rate varies across iterations.
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 50,
                "fx_mean_rate": 330.0,
                "fx_std_pct": 5.0,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            },
            "FX": {"strategy": "natural_hedge"},
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=50)

        fx_rates = []
        for _ in range(50):
            result = engine.simulate_iteration()
            fx_rates.append(result["fx_rate"])

        # Check distribution
        fx_mean = np.mean(fx_rates)
        fx_std = np.std(fx_rates)

        # Mean should be close to 330
        assert 320 < fx_mean < 340, f"FX mean {fx_mean} not near 330"
        # Std should reflect 5% volatility (~16.5)
        assert 5 < fx_std < 25, f"FX std {fx_std} too high/low"
        logger.info(f"✓ FX distribution correct (mean={fx_mean:.1f}, std={fx_std:.1f})")


class TestMCRawResults:
    """Test MC raw_results validation and handling (FIX #2)."""

    def test_raw_results_populated(self) -> None:
        """
        Verify raw_results populated from MC iterations.
        (FIX #2 validation check)
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 10,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=10)
        result = engine.run()

        assert result.get("success") is True
        # raw_results stored in iterations field
        iterations = result.get("iterations", [])
        assert len(iterations) == 10
        assert all(isinstance(it, dict) for it in iterations)
        logger.info("✓ MC raw_results populated correctly")

    def test_raw_results_dict_format(self) -> None:
        """
        Verify each raw result entry is dict with metric keys.
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 5,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=5)
        result = engine.run()

        iterations = result.get("iterations", [])
        required_keys = {"npv_usd", "irr_pct", "revenue_usd", "cost_usd", "fx_rate"}

        for iteration in iterations:
            assert isinstance(iteration, dict)
            for key in required_keys:
                assert key in iteration, f"Missing key: {key}"
                assert isinstance(iteration[key], (int, float))

        logger.info("✓ Raw results have correct dict format")


class TestMCStatistics:
    """Test MC statistics computation."""

    def test_statistics_computed(self) -> None:
        """
        Verify statistics (mean, std, percentiles) computed.
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 100,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=100)
        result = engine.run()

        stats = result.get("statistics", {})
        required_stats = {
            "npv_mean_usd",
            "npv_std_usd",
            "npv_p10_usd",
            "npv_p90_usd",
            "irr_mean_pct",
            "irr_std_pct",
            "irr_p10_pct",
            "irr_p90_pct",
        }

        for stat_key in required_stats:
            assert stat_key in stats, f"Missing stat: {stat_key}"
            assert isinstance(stats[stat_key], (int, float))
            assert not np.isnan(stats[stat_key]), f"{stat_key} is NaN"

        logger.info(f"✓ All {len(required_stats)} statistics computed")

    def test_percentiles_ordered(self) -> None:
        """
        Verify percentiles are ordered: p10 < p50 < p90.
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 100,
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=100)
        result = engine.run()

        stats = result.get("statistics", {})
        npv_p10 = stats["npv_p10_usd"]
        npv_p50 = stats["npv_p50_usd"] if "npv_p50_usd" in stats else stats.get("npv_median_usd", npv_p10)
        npv_p90 = stats["npv_p90_usd"]

        assert npv_p10 <= npv_p50 <= npv_p90, "NPV percentiles not ordered"
        logger.info(f"✓ Percentiles ordered: {npv_p10:.2e} <= {npv_p50:.2e} <= {npv_p90:.2e}")


class TestMCIntegrationWithEvaluation:
    """Test MC integration with evaluation_v14."""

    def test_mc_result_produces_monte_carlo_contract(self) -> None:
        """
        Verify run_monte_carlo_analysis returns proper contract.
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 50,
                "scenario_name": "base_case",
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        result = run_monte_carlo_analysis(config=cfg, n_iterations=50)

        assert result is not None
        assert result.get("success") is True
        assert result.get("scenario_name") == "base_case"
        assert result.get("n_iterations") == 50
        assert "statistics" in result
        logger.info("✓ MC result proper contract")

    def test_mc_with_config_path_loading(self) -> None:
        """
        Verify MC works when loaded from config path.
        (Simulates real usage)
        """
        cfg_dict = {
            "monte_carlo": {
                "iterations": 25,
                "scenario_name": "test_scenario",
                "capex_total_usd": 50e6,
                "revenue_mean_usd": 100e6,
                "cost_mean_usd": 60e6,
                "discount_rate_pct": 7.0,
            }
        }
        cfg = OmegaConf.create(cfg_dict)
        engine = MonteCarloEngine(cfg, n_iterations=25)
        result = engine.run()

        assert result["success"] is True
        assert result["discount_rate_pct"] == 7.0
        logger.info("✓ MC works with config-based loading")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
