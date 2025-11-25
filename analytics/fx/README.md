# FX Analytics Subpackage (v14)

Advanced FX modeling, correlation analysis, and risk metrics for project finance.

## Modules

### `fx_contracts.py`
Type-safe dataclasses for FX configuration and output:
- `FXRegimeConfig`: Dual-regime FX model configuration
- `FXCurveOutput`: Generated FX rate curves
- `FXCorrelationMatrix`: FX correlation structures

### `fx_loader.py`
Unified FX data loading and curve generation:
- `load_fx_regime()`: Load YAML FX configuration
- `discover_fx_files()`: Find all FX YAML files
- `build_fx_curve()`: Generate FX rate curve

### `processor.py`
Dual-regime FX data processor (migrated from root).

### `correlation.py`
FX correlation engine and risk metrics (VaR/CVaR).

### `risk.py`
Risk metrics: DSCR distributions, LLCR, PLCR, coverage ratios.

### `returns.py`
Project and equity return calculations.

## Independence

This subpackage is **independent** from the core v14 pipeline.
It can be used standalone or integrated later as features stabilize.

## Usage


from analytics.fx import FXRegimeConfig, build_fx_curve

config = FXRegimeConfig(
base_currency='USD',
target_currency='LKR',
regime_type='recent',
years=20,
annual_depr=0.03,
start_rate=330.0
)

curve = build_fx_curve(config)
print(curve.rates) # [330.0, 319.9, 310.1, ...]

## Migration Status

- ✅ Modules moved from root
- ✅ Contracts defined
- ✅ Loader implemented
- ⏳ Integration tests (future)
- ⏳ Advanced features (future)

## Part of

Sprint Day 5, Task 2 - FX-Risk Analytics Subpackage
