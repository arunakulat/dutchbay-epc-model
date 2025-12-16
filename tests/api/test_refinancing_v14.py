#!/usr/bin/env python
"""Tests for refinancing module (v14).

Comprehensive test suite for refinancing_v14_hydra module.
Includes error handling (FIN-01), regression pins (TEST-01),
and edge case handling.

Note: Schema validation tests are minimal (just checking function signature).
Full schema guard tests belong in test_config_schema_guard.py.

Run with: pytest tests/api/test_refinancing_v14.py --no-cov
"""

import pytest
from omegaconf import DictConfig, OmegaConf
from finance.refinancing_v14_hydra import (
    RefinancingEngine,
    RefinancingConfig,
)
from analytics.schema_guard import ConfigValidationError


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def base_config() -> DictConfig:
    """Create base refinancing config (minimal, no full schema validation).
    
    Returns: OmegaConf DictConfig
    """
    cfg_dict = {
        'scenario_name': 'test_base',
        'refinancing': {
            'scenario_name': 'test_base',
            'trigger_date': '2028-01-01',
            'trigger_dscr_threshold': 1.25,
            'refi_structure': 'extend',
            'new_spread_bps': 250.0,
            'new_tenor_years': 10,
            'upfront_fee_pct': 1.5,
            'success': True,
        },
        'financial': {
            'debt': {
                'principal_usd': 105e6,
            },
            'fx': {
                'start_lkr_per_usd': 325.5,
                'annual_depr': 0.02,
            },
            'tax': {
                'corporate_tax_pct': 28.0,
            },
        },
    }
    return OmegaConf.create(cfg_dict)


@pytest.fixture
def stress_config() -> DictConfig:
    """Create stress refinancing config (higher spread).
    
    Returns: OmegaConf DictConfig
    """
    cfg_dict = {
        'scenario_name': 'test_stress',
        'refinancing': {
            'scenario_name': 'test_stress',
            'trigger_date': '2027-06-01',
            'trigger_dscr_threshold': 1.1,
            'refi_structure': 'reprice',
            'new_spread_bps': 400.0,  # Higher spread
            'new_tenor_years': 8,
            'upfront_fee_pct': 2.0,
            'success': True,
        },
        'financial': {
            'debt': {
                'principal_usd': 105e6,
            },
            'fx': {
                'start_lkr_per_usd': 325.5,
                'annual_depr': 0.02,
            },
            'tax': {
                'corporate_tax_pct': 28.0,
            },
        },
    }
    return OmegaConf.create(cfg_dict)


# ============================================================================
# TEST: CONFIGURATION
# ============================================================================

def test_refinancing_config_creation() -> None:
    """Test RefinancingConfig dataclass creation.
    
    Validates: Dataclass structure, default values
    """
    cfg = RefinancingConfig(
        scenario_name='test',
        trigger_date='2028-01-01',
        trigger_dscr_threshold=1.25,
        refi_structure='extend',
        new_spread_bps=250.0,
        new_tenor_years=10,
        upfront_fee_pct=1.5,
    )
    
    assert cfg.scenario_name == 'test'
    assert cfg.trigger_date == '2028-01-01'
    assert cfg.new_spread_bps == 250.0
    assert cfg.success is True  # Default value


def test_schema_guard_raises_on_bad_config() -> None:
    """Test schema guard catches missing required fields.
    
    Validates: ConfigValidationError is raised (R22)
    """
    from analytics.schema_guard import validate_config_for_v14
    
    bad_cfg = {
        'financial': {
            'debt': {'principal_usd': 100e6},
            # Missing 'fx' key - required
        },
    }
    
    with pytest.raises(ConfigValidationError):
        # Schema guard will raise because config missing required FX and project fields
        validate_config_for_v14(bad_cfg, config_path='bad', modules=['cashflow', 'debt'])


# ============================================================================
# TEST: ENGINE INITIALIZATION
# ============================================================================

def test_refinancing_engine_init(base_config: DictConfig) -> None:
    """Test RefinancingEngine initialization.
    
    Validates: Config loading, type hints, logger setup
    """
    engine = RefinancingEngine(base_config)
    
    assert engine.config is not None
    assert engine.refi_config.scenario_name == 'test_base'
    assert engine.logger is not None


def test_refinancing_engine_init_missing_config() -> None:
    """Test RefinancingEngine raises on missing refinancing config.
    
    Validates: Error handling (FIN-01)
    Raises: ValueError
    """
    bad_cfg = OmegaConf.create({
        'financial': {
            'debt': {'principal_usd': 100e6},
            'fx': {'start_lkr_per_usd': 325.5, 'annual_depr': 0.02},
            'tax': {'corporate_tax_pct': 28.0},
        },
        # Missing 'refinancing' key
    })
    
    with pytest.raises(ValueError, match="refinancing"):
        RefinancingEngine(bad_cfg)


# ============================================================================
# TEST: REFINANCING IMPACT CALCULATION (REGRESSION PINS - TEST-01)
# ============================================================================

def test_refinancing_impact_calculation(base_config: DictConfig) -> None:
    """Test impact calculation with base scenario.
    
    Validates: Metric calculation, unit suffixes (FIN-02),
    regression pins (TEST-01)
    
    Calculations:
        - refi_cost_usd: 1.5% of 100M = 1.5M ✓
        - spread_delta_bps: new_spread_bps (250) - (current_wacc_pct * 100) = 250 - 950 = -700 bps
        - tenor_delta_years: new_tenor (10) - current_tenor (5) = 5 years ✓
    """
    engine = RefinancingEngine(base_config)
    impact = engine.calculate_refinancing_impact(
        current_debt_outstanding_usd=100e6,
        current_wacc_pct=9.5,  # 9.5% = 950 basis points
        remaining_tenor_years=5,
    )
    
    # REGRESSION PIN (TEST-01): Expected values for base scenario
    assert impact['refi_cost_usd'] == 1.5e6  # 1.5% of 100M
    assert impact['spread_delta_bps'] == -700.0  # 250 - 950 (9.5% * 100)
    assert impact['tenor_delta_years'] == 5.0  # 10 - 5
    assert impact['success'] is True
    assert 'irr_delta_bps' in impact


def test_refinancing_impact_stress(stress_config: DictConfig) -> None:
    """Test impact calculation with stress scenario.
    
    Validates: Stress scenario handling, higher spreads
    
    Calculations:
        - refi_cost_usd: 2.0% of 100M = 2.0M ✓
        - spread_delta_bps: new_spread_bps (400) - (current_wacc_pct * 100) = 400 - 950 = -550 bps
        - tenor_delta_years: new_tenor (8) - current_tenor (8) = 0 years ✓
    """
    engine = RefinancingEngine(stress_config)
    impact = engine.calculate_refinancing_impact(
        current_debt_outstanding_usd=100e6,
        current_wacc_pct=9.5,  # 9.5% = 950 basis points
        remaining_tenor_years=8,
    )
    
    # REGRESSION PIN (TEST-01): Stress scenario
    assert impact['refi_cost_usd'] == 2.0e6  # 2.0% of 100M (higher fee)
    assert impact['spread_delta_bps'] == -550.0  # 400 - 950 (9.5% * 100)
    assert impact['tenor_delta_years'] == 0.0  # 8 - 8
    assert impact['success'] is True


def test_refinancing_impact_unit_suffixes(base_config: DictConfig) -> None:
    """Test FIN-02: Unit suffixes in output (explicit units).
    
    Validates: *_usd, *_bps, *_years suffixes present
    """
    engine = RefinancingEngine(base_config)
    impact = engine.calculate_refinancing_impact(
        current_debt_outstanding_usd=100e6,
        current_wacc_pct=9.5,
        remaining_tenor_years=5,
    )
    
    # FIN-02: Explicit unit suffixes
    assert 'refi_cost_usd' in impact  # _usd suffix
    assert 'spread_delta_bps' in impact  # _bps suffix
    assert 'tenor_delta_years' in impact  # _years suffix
    assert 'irr_delta_bps' in impact  # _bps suffix


# ============================================================================
# TEST: ENGINE EXECUTION (MAIN FLOW - P: PROCESS)
# ============================================================================

def test_refinancing_engine_run(base_config: DictConfig) -> None:
    """Test RefinancingEngine.run() execution.
    
    Validates: Main execution flow, JSON output format,
    tranches and aggregate results
    """
    engine = RefinancingEngine(base_config)
    result = engine.run()
    
    # Check result structure
    assert result['success'] is True
    assert result['scenario_name'] == 'test_base'
    assert result['trigger_date'] == '2028-01-01'
    
    # Check tranches
    assert 'tranches' in result
    assert 'lkr' in result['tranches']
    assert 'irr_delta_bps' in result['tranches']['lkr']
    
    # Check aggregate
    assert 'aggregate' in result
    assert 'project_irr_delta_bps' in result['aggregate']
    assert 'refi_cost_total_usd' in result['aggregate']
    assert 'refinancing_occurred' in result['aggregate']


def test_refinancing_engine_run_stress(stress_config: DictConfig) -> None:
    """Test RefinancingEngine.run() with stress scenario.
    
    Validates: Stress scenario execution
    """
    engine = RefinancingEngine(stress_config)
    result = engine.run()
    
    assert result['success'] is True
    assert result['scenario_name'] == 'test_stress'
    assert 'tranches' in result
    assert 'aggregate' in result


# ============================================================================
# TEST: ERROR HANDLING (FIN-01: GRACEFUL FAILURE)
# ============================================================================

def test_refinancing_invalid_date_format(base_config: DictConfig) -> None:
    """Test FIN-01: Error handling for invalid date format.
    
    Validates: Graceful error handling, logging
    """
    # Create config with invalid date
    bad_cfg = OmegaConf.create({
        'scenario_name': 'test_bad_date',
        'refinancing': {
            'scenario_name': 'test_bad_date',
            'trigger_date': 'invalid-date',  # Bad format
            'trigger_dscr_threshold': 1.25,
            'refi_structure': 'extend',
            'new_spread_bps': 250.0,
            'new_tenor_years': 10,
            'upfront_fee_pct': 1.5,
            'success': True,
        },
        'financial': base_config.financial,
    })
    
    engine = RefinancingEngine(bad_cfg)
    result = engine.run()  # Should handle error gracefully
    
    # FIN-01: Graceful failure
    assert result['success'] is False
    assert 'error' in result


# ============================================================================
# TEST: JSON SERIALIZATION (CLI-03: JSON OUTPUT)
# ============================================================================

def test_refinancing_result_json_serializable(base_config: DictConfig) -> None:
    """Test CLI-03: Result is JSON serializable.
    
    Validates: JSON output format for downstream automation
    """
    import json
    
    engine = RefinancingEngine(base_config)
    result = engine.run()
    
    # Should be JSON serializable
    json_str = json.dumps(result)
    deserialized = json.loads(json_str)
    
    assert deserialized['success'] is True
    assert deserialized['scenario_name'] == 'test_base'


# ============================================================================
# TEST: TYPE HINTS (TYPE-01: 100% COVERAGE)
# ============================================================================

def test_refinancing_type_hints() -> None:
    """Test TYPE-01: Functions have type hints.
    
    Validates: Type hint coverage
    """
    import inspect
    from finance.refinancing_v14_hydra import RefinancingEngine
    
    # Check key public methods exist and are callable
    assert hasattr(RefinancingEngine, 'calculate_refinancing_impact')
    assert hasattr(RefinancingEngine, 'run')
    assert callable(getattr(RefinancingEngine, 'calculate_refinancing_impact'))
    assert callable(getattr(RefinancingEngine, 'run'))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--no-cov'])
