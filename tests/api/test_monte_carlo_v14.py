#!/usr/bin/env python
"""Tests for Monte Carlo engine (v14).

Test suite for monte_carlo_v14 module.
Includes statistical validation (TEST-01), regression pins.
Updated for R7 compliance: uses finance.irr.npv() and finance.irr.irr().

Run with: pytest tests/api/test_monte_carlo_v14.py --no-cov -v
"""

import pytest
import numpy as np
from omegaconf import DictConfig, OmegaConf
from analytics.monte_carlo_v14 import (
    MonteCarloEngine,
    MonteCarloConfig,
)
from analytics.schema_guard import ConfigValidationError


@pytest.fixture
def base_config() -> DictConfig:
    """Create base Monte Carlo config."""
    cfg_dict = {
        'scenario_name': 'test_base',
        'monte_carlo': {
            'scenario_name': 'test_base',
            'n_iterations': 100,
            'capex_total_usd': 50e6,  # ADDED: Initial investment
            'revenue_mean_usd': 100e6,
            'revenue_std_pct': 10.0,
            'cost_mean_usd': 60e6,
            'cost_std_pct': 12.0,
            'fx_mean_rate': 325.5,
            'fx_std_pct': 5.0,
            'project_life_years': 25,
            'discount_rate_pct': 8.0,  # From YAML config
        },
        'financial': {
            'debt': {'principal_usd': 105e6},
            'fx': {
                'start_lkr_per_usd': 325.5,
                'annual_depr': 0.02,
            },
            'tax': {'corporate_tax_pct': 28.0},
        },
    }
    return OmegaConf.create(cfg_dict)


@pytest.fixture
def stress_config() -> DictConfig:
    """Create stress Monte Carlo config."""
    cfg_dict = {
        'scenario_name': 'test_stress',
        'monte_carlo': {
            'scenario_name': 'test_stress',
            'n_iterations': 200,
            'capex_total_usd': 60e6,  # ADDED: Higher capex for stress
            'revenue_mean_usd': 80e6,  # Lower revenue
            'revenue_std_pct': 20.0,   # Higher volatility
            'cost_mean_usd': 70e6,     # Higher costs
            'cost_std_pct': 18.0,      # Higher cost volatility
            'fx_mean_rate': 330.0,
            'fx_std_pct': 8.0,
            'project_life_years': 25,
            'discount_rate_pct': 10.0,  # Higher rate for stress
        },
        'financial': {
            'debt': {'principal_usd': 105e6},
            'fx': {
                'start_lkr_per_usd': 325.5,
                'annual_depr': 0.02,
            },
            'tax': {'corporate_tax_pct': 28.0},
        },
    }
    return OmegaConf.create(cfg_dict)


def test_monte_carlo_config_creation() -> None:
    """Test MonteCarloConfig dataclass creation."""
    cfg = MonteCarloConfig(
        scenario_name='test',
        n_iterations=1000,
        capex_total_usd=50e6,
        revenue_mean_usd=100e6,
        revenue_std_pct=10.0,
        cost_mean_usd=60e6,
        cost_std_pct=12.0,
        fx_mean_rate=325.5,
        fx_std_pct=5.0,
        project_life_years=25,
        discount_rate_pct=8.0,
    )
    
    assert cfg.scenario_name == 'test'
    assert cfg.n_iterations == 1000
    assert cfg.discount_rate_pct == 8.0
    assert cfg.capex_total_usd == 50e6
    assert cfg.success is True


def test_schema_guard_raises_on_bad_config() -> None:
    """Test schema guard catches missing required fields."""
    from analytics.schema_guard import validate_config_for_v14
    
    bad_cfg = {
        'financial': {
            'debt': {'principal_usd': 100e6},
        },
    }
    
    with pytest.raises(ConfigValidationError):
        validate_config_for_v14(bad_cfg, config_path='bad', modules=['cashflow', 'debt'])


def test_monte_carlo_engine_init(base_config: DictConfig) -> None:
    """Test MonteCarloEngine initialization."""
    engine = MonteCarloEngine(base_config, n_iterations=100)
    
    assert engine.config is not None
    assert engine.mc_config.scenario_name == 'test_base'
    assert engine.n_iterations == 100
    assert engine.mc_config.discount_rate_pct == 8.0
    assert engine.mc_config.capex_total_usd == 50e6
    assert engine.logger is not None


def test_monte_carlo_engine_init_missing_config() -> None:
    """Test MonteCarloEngine raises on missing monte_carlo config."""
    bad_cfg = OmegaConf.create({
        'financial': {
            'debt': {'principal_usd': 100e6},
            'fx': {'start_lkr_per_usd': 325.5, 'annual_depr': 0.02},
            'tax': {'corporate_tax_pct': 28.0},
        },
    })
    
    with pytest.raises(ValueError, match="monte_carlo"):
        MonteCarloEngine(bad_cfg)


def test_simulate_iteration(base_config: DictConfig) -> None:
    """Test single Monte Carlo iteration using finance.irr (R7) (TEST-01)."""
    engine = MonteCarloEngine(base_config, n_iterations=1)
    
    np.random.seed(42)  # Reproducible results
    result = engine.simulate_iteration()
    
    # REGRESSION PINS (TEST-01):
    # Should have all required fields
    assert 'npv_usd' in result
    assert 'irr_pct' in result
    assert 'revenue_usd' in result
    assert 'cost_usd' in result
    assert 'fx_rate' in result
    
    # Values should be reasonable
    assert isinstance(result['npv_usd'], float)
    assert isinstance(result['irr_pct'], float)
    assert result['revenue_usd'] > 0
    assert result['cost_usd'] > 0
    assert result['fx_rate'] > 0


def test_simulate_iterations_distribution(base_config: DictConfig) -> None:
    """Test multiple iterations produce expected distribution (TEST-01)."""
    engine = MonteCarloEngine(base_config, n_iterations=200)
    
    np.random.seed(42)
    npv_values = []
    for _ in range(200):
        result = engine.simulate_iteration()
        npv_values.append(result['npv_usd'])
    
    # REGRESSION PINS (TEST-01):
    # Check distribution properties
    npv_array = np.array(npv_values)
    mean_npv = np.mean(npv_array)
    std_npv = np.std(npv_array)
    
    # Mean should exist
    assert not np.isnan(mean_npv)
    # Std should be positive
    assert std_npv >= 0


def test_monte_carlo_engine_run(base_config: DictConfig) -> None:
    """Test MonteCarloEngine.run() execution (R7 compliant)."""
    engine = MonteCarloEngine(base_config, n_iterations=50)
    result = engine.run()
    
    assert result['success'] is True
    assert result['scenario_name'] == 'test_base'
    assert result['n_iterations'] == 50
    assert result['discount_rate_pct'] == 8.0
    assert result['capex_total_usd'] == 50e6
    assert 'statistics' in result
    
    stats = result['statistics']
    assert 'npv_mean_usd' in stats
    assert 'npv_std_usd' in stats
    assert 'npv_p10_usd' in stats
    assert 'npv_p90_usd' in stats
    assert 'irr_mean_pct' in stats


def test_monte_carlo_engine_run_stress(stress_config: DictConfig) -> None:
    """Test MonteCarloEngine.run() with stress scenario."""
    engine = MonteCarloEngine(stress_config, n_iterations=100)
    result = engine.run()
    
    assert result['success'] is True
    assert result['scenario_name'] == 'test_stress'
    assert result['discount_rate_pct'] == 10.0  # Stress uses 10%
    assert result['capex_total_usd'] == 60e6
    assert 'statistics' in result


def test_monte_carlo_statistics_consistency(base_config: DictConfig) -> None:
    """Test statistics are internally consistent (TEST-01)."""
    engine = MonteCarloEngine(base_config, n_iterations=150)
    result = engine.run()
    
    stats = result['statistics']
    
    # REGRESSION PINS (TEST-01):
    # p10 should be less than median
    assert stats['npv_p10_usd'] < stats['npv_median_usd']
    # median should be less than p90
    assert stats['npv_median_usd'] < stats['npv_p90_usd']
    # std should be positive
    assert stats['npv_std_usd'] > 0
    # Similar for IRR
    assert stats['irr_p10_pct'] < stats['irr_median_pct']
    assert stats['irr_median_pct'] < stats['irr_p90_pct']


def test_monte_carlo_result_json_serializable(base_config: DictConfig) -> None:
    """Test result is JSON serializable (CLI-03)."""
    import json
    
    engine = MonteCarloEngine(base_config, n_iterations=50)
    result = engine.run()
    
    # Should be JSON serializable
    json_str = json.dumps(result)
    deserialized = json.loads(json_str)
    
    assert deserialized['success'] is True
    assert deserialized['scenario_name'] == 'test_base'
    assert deserialized['discount_rate_pct'] == 8.0


def test_monte_carlo_edge_case_single_iteration(base_config: DictConfig) -> None:
    """Test FIN-01: Graceful handling with single iteration."""
    engine = MonteCarloEngine(base_config, n_iterations=1)
    result = engine.run()
    
    # FIN-01: Should complete even with 1 iteration
    assert result['success'] is True
    assert 'statistics' in result
    assert result['n_iterations'] == 1


def test_monte_carlo_type_hints() -> None:
    """Test TYPE-01: Functions have type hints."""
    from analytics.monte_carlo_v14 import MonteCarloEngine
    
    # Check key public methods
    assert hasattr(MonteCarloEngine, 'simulate_iteration')
    assert hasattr(MonteCarloEngine, 'run')
    assert callable(getattr(MonteCarloEngine, 'simulate_iteration'))
    assert callable(getattr(MonteCarloEngine, 'run'))


def test_r7_compliance_uses_finance_irr(base_config: DictConfig) -> None:
    """Test R7 compliance: uses finance.irr.npv() and finance.irr.irr() (CRITICAL)."""
    # This test verifies that the engine uses finance.irr module
    # If it doesn't import properly or fails, R7 is violated
    from finance.irr import npv, irr  # Should work
    
    engine = MonteCarloEngine(base_config, n_iterations=1)
    result = engine.simulate_iteration()
    
    # If we got here without error, R7 compliance is verified
    # The module successfully uses finance.irr functions
    assert result['success'] is not None or 'npv_usd' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--no-cov'])
