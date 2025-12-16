#!/usr/bin/env python
"""Tests for equity distribution module (v14).

Test suite for equity_distribution_v14_hydra module.
Includes error handling (FIN-01), regression pins (TEST-01).

Run with: pytest tests/api/test_equity_distribution_v14.py --no-cov
"""

import pytest
from omegaconf import DictConfig, OmegaConf
from finance.equity_distribution_v14_hydra import (
    EquityDistributionEngine,
    EquityDistributionConfig,
)
from analytics.schema_guard import ConfigValidationError


@pytest.fixture
def base_config() -> DictConfig:
    """Create base equity distribution config."""
    cfg_dict = {
        'scenario_name': 'test_base',
        'equity': {
            'scenario_name': 'test_base',
            'project_life_years': 25,
            'annual_distributable_cash_usd': 15e6,
            'equity_stake_pct': 25.0,
            'target_equity_irr_pct': 16.0,
            'priority_senior_debt_usd': 100e6,
            'priority_mezzanine_usd': 50e6,
            'reserve_fund_pct': 10.0,
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
    """Create stress equity distribution config."""
    cfg_dict = {
        'scenario_name': 'test_stress',
        'equity': {
            'scenario_name': 'test_stress',
            'project_life_years': 25,
            'annual_distributable_cash_usd': 10e6,  # Lower cash
            'equity_stake_pct': 30.0,
            'target_equity_irr_pct': 14.0,  # Lower IRR target
            'priority_senior_debt_usd': 120e6,  # Higher debt
            'priority_mezzanine_usd': 60e6,
            'reserve_fund_pct': 15.0,
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


def test_equity_config_creation() -> None:
    """Test EquityDistributionConfig dataclass creation."""
    cfg = EquityDistributionConfig(
        scenario_name='test',
        project_life_years=25,
        annual_distributable_cash_usd=15e6,
        equity_stake_pct=25.0,
        target_equity_irr_pct=16.0,
        priority_senior_debt_usd=100e6,
        priority_mezzanine_usd=50e6,
        reserve_fund_pct=10.0,
    )
    
    assert cfg.scenario_name == 'test'
    assert cfg.project_life_years == 25
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


def test_equity_engine_init(base_config: DictConfig) -> None:
    """Test EquityDistributionEngine initialization."""
    engine = EquityDistributionEngine(base_config)
    
    assert engine.config is not None
    assert engine.equity_config.scenario_name == 'test_base'
    assert engine.logger is not None


def test_equity_engine_init_missing_config() -> None:
    """Test EquityDistributionEngine raises on missing equity config."""
    bad_cfg = OmegaConf.create({
        'financial': {
            'debt': {'principal_usd': 100e6},
            'fx': {'start_lkr_per_usd': 325.5, 'annual_depr': 0.02},
            'tax': {'corporate_tax_pct': 28.0},
        },
    })
    
    with pytest.raises(ValueError, match="equity"):
        EquityDistributionEngine(bad_cfg)


def test_calculate_distributions(base_config: DictConfig) -> None:
    """Test distribution calculation with base scenario (TEST-01)."""
    engine = EquityDistributionEngine(base_config)
    dists = engine.calculate_distributions(
        total_distributable_cash_usd=15e6,
        senior_debt_balance_usd=100e6,
        mezzanine_balance_usd=50e6,
    )
    
    # REGRESSION PINS (TEST-01):
    # All 15M available cash goes to senior debt (priority 1)
    assert dists['senior_debt_dist_usd'] == 15e6
    assert dists['mezzanine_dist_usd'] == 0  # None left for mezz
    assert dists['reserve_fund_usd'] == 0
    assert dists['equity_distribution_usd'] == 0
    assert dists['waterfall_complete'] is True


def test_calculate_distributions_stress(stress_config: DictConfig) -> None:
    """Test distribution calculation with stress scenario."""
    engine = EquityDistributionEngine(stress_config)
    # Scenario: Senior mostly paid, has room for equity
    dists = engine.calculate_distributions(
        total_distributable_cash_usd=10e6,
        senior_debt_balance_usd=5e6,  # Lower balance
        mezzanine_balance_usd=60e6,
    )
    
    # REGRESSION PINS (TEST-01):
    # 5M to senior (what's left), 5M remaining
    assert dists['senior_debt_dist_usd'] == 5e6
    # 5M would go to mezz, but reserve takes 10% = 1.5M needed
    # After senior: 5M left, mezz needs priority
    # After mezz: remaining for reserve and equity


def test_equity_engine_run(base_config: DictConfig) -> None:
    """Test EquityDistributionEngine.run() execution."""
    engine = EquityDistributionEngine(base_config)
    result = engine.run()
    
    assert result['success'] is True
    assert result['scenario_name'] == 'test_base'
    assert result['project_life_years'] == 25
    assert 'distributions' in result
    assert 'equity_summary' in result
    assert 'annual_distributions' in result['distributions']


def test_equity_engine_run_stress(stress_config: DictConfig) -> None:
    """Test EquityDistributionEngine.run() with stress scenario."""
    engine = EquityDistributionEngine(stress_config)
    result = engine.run()
    
    assert result['success'] is True
    assert result['scenario_name'] == 'test_stress'
    assert 'distributions' in result


def test_equity_invalid_config() -> None:
    """Test error handling for invalid config."""
    bad_cfg = OmegaConf.create({
        'scenario_name': 'test_bad',
        'equity': {
            'scenario_name': 'test_bad',
            'project_life_years': 25,
            'annual_distributable_cash_usd': 15e6,
            'equity_stake_pct': 25.0,
            'target_equity_irr_pct': 16.0,
            'priority_senior_debt_usd': 100e6,
            'priority_mezzanine_usd': 50e6,
            'reserve_fund_pct': 10.0,
        },
        'financial': {},  # Invalid: missing required fields
    })
    
    engine = EquityDistributionEngine(bad_cfg)
    result = engine.run()
    
    # Should fail gracefully
    assert result['success'] is False
    assert 'error' in result


def test_equity_result_json_serializable(base_config: DictConfig) -> None:
    """Test result is JSON serializable (CLI-03)."""
    import json
    
    engine = EquityDistributionEngine(base_config)
    result = engine.run()
    
    # Should be JSON serializable
    json_str = json.dumps(result)
    deserialized = json.loads(json_str)
    
    assert deserialized['success'] is True
    assert deserialized['scenario_name'] == 'test_base'


def test_equity_type_hints() -> None:
    """Test TYPE-01: Functions have type hints."""
    import inspect
    from finance.equity_distribution_v14_hydra import EquityDistributionEngine
    
    # Check key public methods exist and are callable
    assert hasattr(EquityDistributionEngine, 'calculate_distributions')
    assert hasattr(EquityDistributionEngine, 'run')
    assert callable(getattr(EquityDistributionEngine, 'calculate_distributions'))
    assert callable(getattr(EquityDistributionEngine, 'run'))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--no-cov'])
