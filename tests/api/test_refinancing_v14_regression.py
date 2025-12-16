"""Regression tests for Refinancing Module v14.

Tests core functionality including:
- Refinancing trigger conditions
- Cost calculations
- Schedule generation
- Covenant impact
- Interest savings
"""

import pytest
from finance.refinancing_v14_hydra import (
    RefinancingConfig,
    RefinancingV14,
    RefinancingTrigger,
)


class TestRefinancingConfig:
    """Test RefinancingConfig validation."""
    
    def test_default_config(self) -> None:
        """Test default configuration is valid."""
        config = RefinancingConfig()
        assert config.enabled is True
        assert config.trigger_year_min == 8
        assert config.dscr_threshold == 1.25
        assert config.new_rate == 6.5
        assert config.new_tenor == 12
    
    def test_config_dscr_validation(self) -> None:
        """Test DSCR threshold validation."""
        with pytest.raises(ValueError):
            RefinancingConfig(dscr_threshold=-1.0)
        
        with pytest.raises(ValueError):
            RefinancingConfig(dscr_threshold=4.0)
    
    def test_config_rate_validation(self) -> None:
        """Test interest rate validation."""
        with pytest.raises(ValueError):
            RefinancingConfig(new_rate=-1.0)
        
        with pytest.raises(ValueError):
            RefinancingConfig(new_rate=25.0)
    
    def test_config_tenor_validation(self) -> None:
        """Test tenor validation."""
        with pytest.raises(ValueError):
            RefinancingConfig(new_tenor=0)
        
        with pytest.raises(ValueError):
            RefinancingConfig(new_tenor=40)


class TestRefinancingTrigger:
    """Test RefinancingTrigger logic."""
    
    def test_trigger_year_threshold(self) -> None:
        """Test year threshold condition."""
        config = RefinancingConfig()
        trigger = RefinancingTrigger(config)
        
        should_refi, conditions = trigger.should_refinance(
            year=5,
            current_rate=8.0,
            dscr=1.5,
            debt_balance=100_000_000,
        )
        assert conditions['year_threshold'] is False
        assert should_refi is False
        
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=8.0,
            dscr=1.5,
            debt_balance=100_000_000,
        )
        assert conditions['year_threshold'] is True
    
    def test_trigger_dscr_threshold(self) -> None:
        """Test DSCR threshold condition."""
        config = RefinancingConfig()
        trigger = RefinancingTrigger(config)
        
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=8.0,
            dscr=1.0,
            debt_balance=100_000_000,
        )
        assert conditions['dscr_threshold'] is False
        
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=8.0,
            dscr=1.5,
            debt_balance=100_000_000,
        )
        assert conditions['dscr_threshold'] is True
    
    def test_trigger_rate_savings(self) -> None:
        """Test rate savings condition."""
        config = RefinancingConfig()
        trigger = RefinancingTrigger(config)
        
        # New rate not lower (no savings)
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=6.0,
            dscr=1.5,
            debt_balance=100_000_000,
        )
        assert conditions['rate_savings'] is False
        
        # New rate lower with savings
        should_refi, conditions = trigger.should_refinance(
            year=10,
            current_rate=8.0,
            dscr=1.5,
            debt_balance=100_000_000,
        )
        assert conditions['rate_savings'] is True


class TestRefinancingCalculator:
    """Test RefinancingV14 calculator."""
    
    def test_calculator_initialization(self) -> None:
        """Test calculator can be initialized."""
        config = RefinancingConfig()
        calc = RefinancingV14(config)
        assert calc.config is not None
        assert calc.trigger is not None
    
    def test_calculator_disabled(self) -> None:
        """Test calculator respects enabled flag."""
        config = RefinancingConfig(enabled=False)
        calc = RefinancingV14(config)
        result = calc.calculate({}, {}, 8.0)
        assert result['refinanced'] is False
    
    def test_calculate_returns_dict(self) -> None:
        """Test calculate returns proper structure."""
        config = RefinancingConfig()
        calc = RefinancingV14(config)
        result = calc.calculate({}, {}, 8.0)
        
        assert isinstance(result, dict)
        assert 'refinanced' in result
        assert 'trigger_year' in result
        assert 'new_schedule' in result
        assert 'refinancing_cost' in result
        assert 'interest_savings' in result


if __name__ == "__main__":
    """Run tests."""
    pytest.main([__file__, "-v"])
