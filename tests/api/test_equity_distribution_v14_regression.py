"""Regression test suite for Equity Distribution Module v14.

Tests cover:
- Pydantic v2 config validation
- Distribution waterfall logic
- Covenant compliance (DSCR, LLCR)
- Reserve requirements
- Tax-efficient timing
- Edge cases and error handling

Author: DutchBay Test Team
Date: December 16, 2025
"""

import pytest
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    DistributionWaterfall,
    EquityDistributionV14,
)


class TestEquityDistributionConfig:
    """Test Pydantic v2 configuration validation."""
    
    def test_default_config_valid(self) -> None:
        """Default configuration should be valid."""
        config = EquityDistributionConfig()
        assert config.enabled is True
        assert config.min_reserve_months == 6.0
        assert config.min_dscr_threshold == 1.20
        assert config.min_llcr_threshold == 1.10
        assert config.distribution_frequency == "annual"
        assert config.target_equity_return_pct == 15.0
    
    def test_dscr_validation_rejects_negative(self) -> None:
        """DSCR threshold must be positive."""
        with pytest.raises(ValueError, match="DSCR threshold.*not in valid range"):
            EquityDistributionConfig(min_dscr_threshold=-0.5)
    
    def test_dscr_validation_rejects_excessive(self) -> None:
        """DSCR threshold must be reasonable (<= 3.0)."""
        with pytest.raises(ValueError, match="DSCR threshold.*not in valid range"):
            EquityDistributionConfig(min_dscr_threshold=5.0)
    
    def test_llcr_validation_rejects_negative(self) -> None:
        """LLCR threshold must be positive."""
        with pytest.raises(ValueError, match="LLCR threshold.*not in valid range"):
            EquityDistributionConfig(min_llcr_threshold=-1.0)
    
    def test_llcr_validation_rejects_excessive(self) -> None:
        """LLCR threshold must be reasonable (<= 2.0)."""
        with pytest.raises(ValueError, match="LLCR threshold.*not in valid range"):
            EquityDistributionConfig(min_llcr_threshold=3.0)
    
    def test_reserve_months_validation_rejects_negative(self) -> None:
        """Reserve months must be non-negative."""
        with pytest.raises(ValueError, match="Reserve months.*not in valid range"):
            EquityDistributionConfig(min_reserve_months=-2.0)
    
    def test_reserve_months_validation_rejects_excessive(self) -> None:
        """Reserve months must be reasonable (<= 24)."""
        with pytest.raises(ValueError, match="Reserve months.*not in valid range"):
            EquityDistributionConfig(min_reserve_months=36.0)
    
    def test_distribution_frequency_validation_rejects_invalid(self) -> None:
        """Distribution frequency must be valid option."""
        with pytest.raises(ValueError, match="Frequency.*not in valid options"):
            EquityDistributionConfig(distribution_frequency="daily")
    
    def test_distribution_frequency_accepts_valid(self) -> None:
        """Valid distribution frequencies should be accepted."""
        for freq in ['annual', 'semi-annual', 'quarterly', 'monthly']:
            config = EquityDistributionConfig(distribution_frequency=freq)
            assert config.distribution_frequency == freq.lower()
    
    def test_equity_return_validation_rejects_negative(self) -> None:
        """Equity return target must be non-negative."""
        with pytest.raises(ValueError, match="Equity return.*not in valid range"):
            EquityDistributionConfig(target_equity_return_pct=-5.0)
    
    def test_equity_return_validation_rejects_excessive(self) -> None:
        """Equity return target must be reasonable (<= 50%)."""
        with pytest.raises(ValueError, match="Equity return.*not in valid range"):
            EquityDistributionConfig(target_equity_return_pct=75.0)


class TestDistributionWaterfall:
    """Test distribution waterfall logic."""
    
    def test_distributable_cash_basic(self) -> None:
        """Calculate distributable cash after debt service and reserves."""
        config = EquityDistributionConfig()
        waterfall = DistributionWaterfall(config)
        
        distributable = waterfall.calculate_distributable_cash(
            year=1,
            cfads=10_000_000,  # $10M CFADS
            debt_service=6_000_000,  # $6M debt service
            reserve_balance=2_000_000,  # $2M in reserve
            target_reserve=1_500_000,  # $1.5M target
        )
        
        # Expected: 10M - 6M - 0 (reserve already sufficient) = 4M
        assert distributable == 4_000_000
    
    def test_distributable_cash_with_reserve_shortfall(self) -> None:
        """Distributable cash reduced when reserve needs top-up."""
        config = EquityDistributionConfig()
        waterfall = DistributionWaterfall(config)
        
        distributable = waterfall.calculate_distributable_cash(
            year=1,
            cfads=10_000_000,  # $10M CFADS
            debt_service=6_000_000,  # $6M debt service
            reserve_balance=500_000,  # $500K in reserve
            target_reserve=1_500_000,  # $1.5M target
        )
        
        # Expected: 10M - 6M - (1.5M - 0.5M) = 3M
        assert distributable == 3_000_000
    
    def test_distributable_cash_insufficient(self) -> None:
        """No distribution when cash insufficient for debt + reserves."""
        config = EquityDistributionConfig()
        waterfall = DistributionWaterfall(config)
        
        distributable = waterfall.calculate_distributable_cash(
            year=1,
            cfads=5_000_000,  # $5M CFADS
            debt_service=6_000_000,  # $6M debt service (exceeds CFADS!)
            reserve_balance=500_000,
            target_reserve=1_500_000,
        )
        
        # Expected: Cannot distribute negative, so 0
        assert distributable == 0.0
    
    def test_covenant_check_all_pass(self) -> None:
        """Distribution allowed when all covenants pass."""
        config = EquityDistributionConfig(
            min_dscr_threshold=1.20,
            min_llcr_threshold=1.10,
        )
        waterfall = DistributionWaterfall(config)
        
        can_distribute, conditions = waterfall.check_distribution_covenants(
            dscr=1.30,  # Above 1.20 threshold
            llcr=1.15,  # Above 1.10 threshold
        )
        
        assert can_distribute is True
        assert conditions['dscr_ok'] is True
        assert conditions['llcr_ok'] is True
    
    def test_covenant_check_dscr_fails(self) -> None:
        """Distribution blocked when DSCR below threshold."""
        config = EquityDistributionConfig(
            min_dscr_threshold=1.20,
            min_llcr_threshold=1.10,
        )
        waterfall = DistributionWaterfall(config)
        
        can_distribute, conditions = waterfall.check_distribution_covenants(
            dscr=1.10,  # Below 1.20 threshold
            llcr=1.15,  # Above 1.10 threshold
        )
        
        assert can_distribute is False
        assert conditions['dscr_ok'] is False
        assert conditions['llcr_ok'] is True
    
    def test_covenant_check_llcr_fails(self) -> None:
        """Distribution blocked when LLCR below threshold."""
        config = EquityDistributionConfig(
            min_dscr_threshold=1.20,
            min_llcr_threshold=1.10,
        )
        waterfall = DistributionWaterfall(config)
        
        can_distribute, conditions = waterfall.check_distribution_covenants(
            dscr=1.30,  # Above 1.20 threshold
            llcr=1.05,  # Below 1.10 threshold
        )
        
        assert can_distribute is False
        assert conditions['dscr_ok'] is True
        assert conditions['llcr_ok'] is False
    
    def test_waterfall_single_tier(self) -> None:
        """Single equity tier receives 100% of distributable cash."""
        config = EquityDistributionConfig()
        waterfall = DistributionWaterfall(config)
        
        equity_tiers = [
            {'name': 'Class A Equity', 'priority': 1, 'target_pct': 100.0},
        ]
        
        distributions = waterfall.apply_waterfall(
            distributable_cash=1_000_000,
            equity_tiers=equity_tiers,
        )
        
        assert len(distributions) == 1
        assert distributions[0]['tier_name'] == 'Class A Equity'
        assert distributions[0]['amount'] == 1_000_000
        assert distributions[0]['pct_of_total'] == 100.0
    
    def test_waterfall_multi_tier(self) -> None:
        """Multi-tier waterfall distributes by priority."""
        config = EquityDistributionConfig()
        waterfall = DistributionWaterfall(config)
        
        equity_tiers = [
            {'name': 'Class A Equity', 'priority': 1, 'target_pct': 60.0},
            {'name': 'Class B Equity', 'priority': 2, 'target_pct': 100.0},  # Gets remainder
        ]
        
        distributions = waterfall.apply_waterfall(
            distributable_cash=1_000_000,
            equity_tiers=equity_tiers,
        )
        
        assert len(distributions) == 2
        assert distributions[0]['tier_name'] == 'Class A Equity'
        assert distributions[0]['amount'] == 600_000  # 60% of 1M
        assert distributions[1]['tier_name'] == 'Class B Equity'
        assert distributions[1]['amount'] == 400_000  # Remaining 40%


class TestEquityDistributionV14:
    """Test equity distribution calculator."""
    
    def test_disabled_returns_zero_distributions(self) -> None:
        """When disabled, no distributions occur."""
        config = EquityDistributionConfig(enabled=False)
        calculator = EquityDistributionV14(config)
        
        result = calculator.calculate(
            annual_data={
                'cfads': [10_000_000],
                'dscr': [1.50],
                'llcr': [1.20],
                'reserve_balance': [2_000_000],
            },
            debt_schedule={
                'debt_service_total': [5_000_000],
            },
            equity_investment=20_000_000,
        )
        
        assert result['enabled'] is False
        assert result['total_distributed'] == 0.0
        assert result['distribution_schedule'] == []
    
    def test_basic_distribution_single_year(self) -> None:
        """Basic distribution in a single year with passing covenants."""
        config = EquityDistributionConfig(
            min_dscr_threshold=1.20,
            min_llcr_threshold=1.10,
            min_reserve_months=6.0,
        )
        calculator = EquityDistributionV14(config)
        
        result = calculator.calculate(
            annual_data={
                'cfads': [10_000_000],
                'dscr': [1.50],  # Above threshold
                'llcr': [1.25],  # Above threshold
                'reserve_balance': [3_000_000],  # Sufficient
            },
            debt_schedule={
                'debt_service_total': [5_000_000],
            },
            equity_investment=20_000_000,
        )
        
        assert result['enabled'] is True
        assert result['total_distributed'] > 0
        assert len(result['distribution_schedule']) == 1
        assert result['distribution_schedule'][0]['blocked'] is False
        assert result['equity_multiple'] > 0
    
    def test_covenant_breach_blocks_distribution(self) -> None:
        """Distribution blocked when DSCR below threshold."""
        config = EquityDistributionConfig(
            min_dscr_threshold=1.20,
            min_llcr_threshold=1.10,
        )
        calculator = EquityDistributionV14(config)
        
        result = calculator.calculate(
            annual_data={
                'cfads': [10_000_000],
                'dscr': [1.10],  # BELOW threshold!
                'llcr': [1.25],
                'reserve_balance': [3_000_000],
            },
            debt_schedule={
                'debt_service_total': [5_000_000],
            },
            equity_investment=20_000_000,
        )
        
        assert result['total_distributed'] == 0.0
        assert len(result['blocked_years']) == 1
        assert result['distribution_schedule'][0]['blocked'] is True
        assert result['distribution_schedule'][0]['reason'] == 'covenant_breach'
    
    def test_multi_year_with_mixed_covenants(self) -> None:
        """Multi-year scenario with some years blocked."""
        config = EquityDistributionConfig(
            min_dscr_threshold=1.20,
            min_llcr_threshold=1.10,
        )
        calculator = EquityDistributionV14(config)
        
        result = calculator.calculate(
            annual_data={
                'cfads': [10_000_000, 12_000_000, 15_000_000],
                'dscr': [1.10, 1.30, 1.50],  # Year 1 blocked, Years 2-3 pass
                'llcr': [1.15, 1.20, 1.25],
                'reserve_balance': [3_000_000, 3_500_000, 4_000_000],
            },
            debt_schedule={
                'debt_service_total': [5_000_000, 5_000_000, 5_000_000],
            },
            equity_investment=20_000_000,
        )
        
        assert result['total_years'] == 3
        assert len(result['blocked_years']) == 1  # Only year 1 blocked
        assert 1 in result['blocked_years']
        assert result['total_distributed'] > 0  # Years 2-3 distributed
        assert result['distribution_schedule'][0]['blocked'] is True
        assert result['distribution_schedule'][1]['blocked'] is False
        assert result['distribution_schedule'][2]['blocked'] is False
