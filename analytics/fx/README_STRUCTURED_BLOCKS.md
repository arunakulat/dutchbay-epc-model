# FX Structured Blocks - User Guide

**v14 Comprehensive FX Risk Management Framework**

## Overview

This module provides production-grade FX analytics for the DutchBay EPC
model, following v14R6 structured blocks requirements. All configurations
use typed dataclasses with full validation.

## Quick Start

### Basic FX Configuration

```python
from analytics.fx.fx_contracts import FXStructuredBlock
from analytics.fx.fx_loader import (
    build_fx_curve_from_block,
    load_fx_structured_block,
)

# Option 1: Direct construction
fx_block = FXStructuredBlock(
    start_lkr_per_usd=375.0,
    annual_depr=0.03,
    base_currency="USD",
    target_currency="LKR",
    volatility=0.10,
)

# Option 2: Load from YAML config
raw_config = {
    "fx": {
        "start_lkr_per_usd": 375.0,
        "annual_depr": 0.03,
        "volatility": 0.10,
    }
}
fx_block = load_fx_structured_block(raw_config)

# Generate FX curve
curve = build_fx_curve_from_block(fx_block, years=20)
print(f"Year 10 rate: {curve.rates[10]:.2f} LKR/USD")
```

### Multi-Regime Scenarios

```python
from analytics.fx.fx_contracts import (
    FXRegimeScenario,
    FXStructuredBlock,
    RegimeType,
)

# Base case scenario (60% probability)
base_fx = FXStructuredBlock(
    start_lkr_per_usd=375.0,
    annual_depr=0.03,
    regime=RegimeType.RECENT,
)

base_scenario = FXRegimeScenario(
    scenario_name="Base Case",
    structured_block=base_fx,
    probability=0.6,
    years=20,
)

# Stressed scenario (10% probability)
stressed_fx = FXStructuredBlock(
    start_lkr_per_usd=375.0,
    annual_depr=0.06,
    volatility=0.20,
    regime=RegimeType.STRESSED,
)

stressed_scenario = FXRegimeScenario(
    scenario_name="Stressed",
    structured_block=stressed_fx,
    probability=0.1,
    years=20,
    apply_shock=True,
    shock_magnitude=0.15,
)
```

## Advanced Features

### Sensitivity Analysis (Tornado)

```python
from analytics.fx.fx_contracts import (
    FXSensitivityConfig,
    FXStructuredBlock,
)

base_block = FXStructuredBlock(
    start_lkr_per_usd=375.0,
    annual_depr=0.03,
)

sens_config = FXSensitivityConfig(
    base_block=base_block,
    parameter_name="annual_depr",
    low_value=0.01,
    high_value=0.05,
    num_steps=5,
)

# Generate tornado analysis
for step in range(sens_config.num_steps):
    depr_rate = (
        sens_config.low_value
        + (sens_config.high_value - sens_config.low_value)
        * step
        / (sens_config.num_steps - 1)
    )
    # Run model with depr_rate
    # Calculate IRR impact
```

### Monte Carlo Simulations (100k paths)

```python
from analytics.fx.fx_contracts import (
    FXMonteCarloConfig,
    FXStructuredBlock,
    VolatilityMethod,
)

base_block = FXStructuredBlock(
    start_lkr_per_usd=375.0,
    annual_depr=0.03,
    volatility=0.10,
)

mc_config = FXMonteCarloConfig(
    base_block=base_block,
    num_simulations=100_000,
    time_horizon_years=20,
    volatility_method=VolatilityMethod.HISTORICAL_STD,
    seed=42,  # For reproducibility
)

# Run Monte Carlo simulation
# Generate risk metrics (VaR, CVaR, etc.)
```

### FX Risk Profile (Lender-Grade)

```python
from analytics.fx.fx_contracts import FXRiskProfile

# After running simulations, create risk profile
risk_profile = FXRiskProfile(
    scenario_name="Base Case",
    var_95=15.0,  # 95% VaR in currency units
    var_99=22.5,  # 99% VaR
    expected_shortfall=18.0,  # CVaR
    max_drawdown_pct=12.5,  # Max drawdown as %
    sharpe_ratio=0.85,  # Risk-adjusted return
    volatility_realized=0.10,  # Realized vol
)

print(f"VaR (95%): {risk_profile.var_95:.2f}")
print(f"Sharpe: {risk_profile.sharpe_ratio:.2f}")
```

## YAML Configuration

### Structured Block in Scenario File

```yaml
# scenarios/scenario_base.yaml
project:
  name: "DutchBay 150MW Wind"
  capacity_mw: 150
  life_years: 20

fx:
  start_lkr_per_usd: 375.0
  annual_depr: 0.03
  base_currency: "USD"
  target_currency: "LKR"
  regime: "recent"
  volatility: 0.10
  correlation_with_revenue: 0.0
  hedge_ratio: 0.0
  metadata:
    source: "Central Bank historical data"
    period: "2020-2023"
```

### Multi-Regime Scenario

```yaml
# scenarios/scenario_multi_regime.yaml
fx_scenario:
  scenario_name: "Base Case"
  probability: 0.6
  years: 20
  apply_shock: false
  fx:
    start_lkr_per_usd: 375.0
    annual_depr: 0.03
    volatility: 0.10
```

### Sensitivity Configuration

```yaml
# scenarios/sensitivity_fx.yaml
fx_sensitivity:
  parameter_name: "annual_depr"
  low_value: 0.01
  high_value: 0.05
  num_steps: 5
  base_fx:
    start_lkr_per_usd: 375.0
    annual_depr: 0.03
```

### Monte Carlo Configuration

```yaml
# scenarios/monte_carlo_fx.yaml
fx_monte_carlo:
  num_simulations: 100000
  time_horizon_years: 20
  volatility_method: "historical_std"
  seed: 42
  base_fx:
    start_lkr_per_usd: 375.0
    annual_depr: 0.03
    volatility: 0.10
```

## API Reference

### Core Contracts

#### `FXStructuredBlock`

Core FX configuration per v14R6.

**Attributes:**
- `start_lkr_per_usd` (float): Initial exchange rate
- `annual_depr` (float): Annual depreciation rate (decimal)
- `base_currency` (str): Base currency code (default: "USD")
- `target_currency` (str): Target currency code (default: "LKR")
- `regime` (RegimeType): Regime classification
- `volatility` (float): Annual volatility (default: 0.10)
- `correlation_with_revenue` (float): Correlation with revenue (-1 to 1)
- `hedge_ratio` (float): Hedged proportion (0 to 1)
- `metadata` (dict): Additional metadata

**Raises:**
- `ValueError`: If parameters outside valid ranges

#### `FXRegimeScenario`

Multi-regime scenario configuration.

**Attributes:**
- `scenario_name` (str): Scenario identifier
- `structured_block` (FXStructuredBlock): FX config
- `probability` (float): Probability weight (0-1)
- `years` (int): Projection years
- `apply_shock` (bool): Apply one-time shock
- `shock_magnitude` (float): Shock size if applied

#### `FXRiskProfile`

Lender-grade risk analytics output.

**Attributes:**
- `scenario_name` (str): Associated scenario
- `var_95` (float): 95% Value at Risk
- `var_99` (float): 99% Value at Risk
- `expected_shortfall` (float): Conditional VaR (CVaR)
- `max_drawdown_pct` (float): Max drawdown as %
- `sharpe_ratio` (float): Risk-adjusted return
- `volatility_realized` (float): Realized volatility
- `correlation_matrix` (tuple): Multi-currency correlation

### Loader Functions

#### `load_fx_structured_block(raw_config: dict) -> FXStructuredBlock`

Load FX structured block from raw config dict.

**Args:**
- `raw_config`: Config dict with 'fx' key

**Returns:**
- Validated FXStructuredBlock

**Raises:**
- `KeyError`: If 'fx' key missing
- `ValueError`: If config invalid

#### `build_fx_curve_from_block(block, years, include_confidence_interval=False)`

Generate FX rate curve from structured block.

**Args:**
- `block`: FXStructuredBlock configuration
- `years`: Number of projection years
- `include_confidence_interval`: Include 95% CI (default: False)

**Returns:**
- FXCurveOutput with rates and optional CI

## Testing

```bash
# Run all FX structured block tests
pytest tests/test_fx_structured_blocks.py -v

# Run specific test class
pytest tests/test_fx_structured_blocks.py::TestFXStructuredBlockValidation -v

# Run with coverage
pytest tests/test_fx_structured_blocks.py --cov=analytics.fx --cov-report=html
```

## Migration from Legacy Configs

### Before (v13 - Scalar FX)

```yaml
fx: 375.0  # ❌ Not supported in v14
```

### After (v14 - Structured Block)

```yaml
fx:  # ✅ v14 compliant
  start_lkr_per_usd: 375.0
  annual_depr: 0.03
```

## Best Practices

1. **Always use structured blocks**: Scalar FX configs are rejected in v14.

2. **Validate early**: Use `validate_fx_structured_config()` before loading.

3. **Include volatility**: Even if zero, explicitly set for clarity.

4. **Document regime**: Use metadata to track data sources and periods.

5. **100k simulations**: For lender-grade Monte Carlo, use 100,000+ paths.

6. **Set seeds**: Use `seed` parameter for reproducible Monte Carlo results.

7. **Test edge cases**: Appreciation scenarios (negative depr), zero vol, etc.

## Troubleshooting

### Error: "Scalar 'fx' configs not supported in v14"

**Solution**: Migrate to structured block format:

```yaml
fx:
  start_lkr_per_usd: 375.0
  annual_depr: 0.03
```

### Error: "Missing 'fx' key in config"

**Solution**: Ensure top-level 'fx' key exists in YAML.

### Error: "start_lkr_per_usd must be > 0"

**Solution**: Check FX rate is positive and non-zero.

### Error: "correlation_with_revenue must be in [-1, 1]"

**Solution**: Correlation must be between -1 and 1 inclusive.

## References

- **v14R6**: FX mapping requirement (structured blocks mandatory)
- **v2.3V239**: Frozen dataclasses (immutable configs)
- **v2.3V236**: Full type hints (mypy-strict compliance)
- **Issue #31**: FX structured blocks implementation

## Support

For questions or issues:
1. Check test suite: `tests/test_fx_structured_blocks.py`
2. Review docstrings in `fx_contracts.py` and `fx_loader.py`
3. Consult Go with the Flow v2.3 ruleset

---

**Last Updated**: Sprint 9 Day 5, December 2025
**Authors**: DutchBay EPC Model Team
**Version**: v14R6 compliant
