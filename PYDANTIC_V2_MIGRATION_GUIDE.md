# Pydantic v2 Migration Guide - DutchBay EPC Model

## Overview

This guide covers the complete Pydantic v1 → v2 migration for the DutchBay EPC financial model contracts.

**Status:** Phase 1 Complete ✅ (ParameterRangeConfig, TornadoResult)

## Phase 1: Core Sensitivity Contracts ✅ COMPLETE

### What Was Migrated

1. **ParameterRangeConfig** (dataclass → Pydantic BaseModel)
   - Added validators for variable_name, base_value, percentages
   - Validation: `high_pct >= abs(low_pct)` (allows symmetric ranges)
   - Computed properties: `low_value`, `high_value`

2. **TornadoResult** (dataclass → dataclass with properties)
   - Added `impact_pct`, `impact_abs` computed properties
   - Maintains dataclass for backward compatibility

### Test Results

```bash
tests/finance/test_contracts.py: 33/33 PASSED ✅
```

## Phase 2: Remaining Contracts Migration

### Step 1: Migrate Core Risk Contracts

**Run the migration script:**

```bash
git pull origin feature/add-finance-contracts-pydantic-v2-20251219
python scripts/migrate_remaining_contracts.py
```

**Contracts to Migrate:**

1. **BreakevenResult**
   - Validators: positive tolerance, realistic pct_change bounds
   - Migration: dataclass → Pydantic BaseModel

2. **TailRiskSnapshot**
   - Validators: VaR/CVaR ordering, percentile ordering, probability bounds
   - Model validator for cross-field validation

**Note:** `MonteCarloResult` already migrated as legacy stub with `extra="allow"`

### Step 2: Fix Test Configuration Files

**Problem:** ~40 tests fail due to missing tax fields in YAML configs

**Run the config fixer:**

```bash
python scripts/fix_test_configs_tax.py
```

**Adds missing fields:**
- `tax.corporate_tax_rate: 0.24` (24% default)
- `tax.depreciation.depreciation_start_year: 1`
- `tax.depreciation.straight_line_years: 20`

### Step 3: Update Refinancing Module Tests

**Problem:** Refinancing API constructor signature changed

**Manual fixes needed:**

```python
# OLD (v1):
result = RefinancingOptimizer(
    config=config,
    scenario_result=scenario
)

# NEW (v2):
result = RefinancingOptimizer(
    scenario_result=scenario,
    refinancing_config=config['refinancing']  # Extract nested config
)
```

**Files to update:**
- `tests/refinancing/test_refinancing_optimizer.py`
- `tests/refinancing/test_refinancing_scenarios.py`

### Step 4: Fix FX Configuration Validation

**Problem:** FX configs missing required fields for Pydantic v2 strict validation

**Add to test FX configs:**

```yaml
fx:
  base_currency: USD
  project_currency: LKR
  base_rate: 330.0
  volatility_pct: 5.0
  correlation_to_revenue: -0.3
```

## Validation Strategy

### 1. Field Validators (`@field_validator`)

Use for single-field validation:

```python
@field_validator("variable_name")
@classmethod
def validate_variable_name(cls, v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Variable name cannot be empty")
    return v
```

### 2. Model Validators (`@model_validator`)

Use for cross-field validation:

```python
@model_validator(mode="after")
def validate_bounds(self) -> "ParameterRangeConfig":
    if self.high_pct < abs(self.low_pct):
        raise ValueError(f"High bound must be >= absolute value of low bound")
    return self
```

### 3. Computed Properties

For derived fields:

```python
@computed_field
@property
def low_value(self) -> float:
    return self.base_value * (1 + self.low_pct / 100)
```

## Testing Checklist

- [ ] Step 1: Run contracts migration script
- [ ] Step 2: Run config fixer script  
- [ ] Step 3: Manually update refinancing tests
- [ ] Step 4: Add FX fields to test configs
- [ ] Verify: `pytest tests/finance/test_contracts.py -v` (33/33)
- [ ] Verify: `pytest tests/analytics_layer/ -v` (most should pass)
- [ ] Verify: `pytest tests/refinancing/ -v` (after manual fixes)
- [ ] Full suite: `pytest` (target: 500+ passing)

## Migration Patterns

### Pattern 1: Simple Dataclass → BaseModel

```python
# Before
@dataclass
class MyContract:
    field1: str
    field2: float

# After
class MyContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)
    
    field1: str
    field2: float
    
    @field_validator("field2")
    @classmethod
    def validate_field2(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"field2 must be positive, got {v}")
        return v
```

### Pattern 2: Dataclass with Defaults → BaseModel with Defaults

```python
# Before
@dataclass
class MyContract:
    required_field: str
    optional_field: Optional[float] = None
    default_field: int = 10

# After
class MyContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    required_field: str
    optional_field: Optional[float] = None
    default_field: int = 10
```

### Pattern 3: Computed Properties

```python
# Before (dataclass with @property)
@dataclass
class MyContract:
    base: float
    pct: float
    
    @property
    def computed(self) -> float:
        return self.base * (1 + self.pct / 100)

# After (Pydantic with @computed_field)
class MyContract(BaseModel):
    base: float
    pct: float
    
    @computed_field
    @property
    def computed(self) -> float:
        return self.base * (1 + self.pct / 100)
```

## Common Issues & Solutions

### Issue 1: `NameError: name 'field_validator' is not defined`

**Solution:** Add import
```python
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
```

### Issue 2: `ValidationError: High bound must be > absolute value of low bound`

**Solution:** Changed validator logic to `>=` (allows symmetric ranges)
```python
if self.high_pct < abs(self.low_pct):  # Changed from <=
```

### Issue 3: Missing `corporate_tax_rate` in test configs

**Solution:** Run `scripts/fix_test_configs_tax.py`

### Issue 4: `TypeError: __init__() got unexpected keyword argument`

**Solution:** Check if dataclass still has `@dataclass` decorator (should be removed)

## Rollback Plan

If migration causes issues:

```bash
# Revert to previous commit
git reset --hard 889cac82  # Before migration scripts

# Or revert specific file
git checkout HEAD~1 -- analytics/contracts_v14.py
```

## Next Steps (Sprint 13)

1. Migrate remaining dataclasses:
   - `WaccComponents`
   - `CashflowResult`
   - `DebtCovenantSnapshot`
   - `EquityResult`
   - `ScenarioResult`

2. Add Pydantic v2 serialization:
   - `model_dump()` instead of `asdict()`
   - JSON schema generation
   - API integration with FastAPI

3. Performance optimization:
   - Profile validation overhead
   - Add `@lru_cache` for computed properties
   - Benchmark vs. dataclass baseline

## Resources

- [Pydantic v2 Migration Guide](https://docs.pydantic.dev/2.0/migration/)
- [Pydantic v2 Validators](https://docs.pydantic.dev/2.0/concepts/validators/)
- [Computed Fields](https://docs.pydantic.dev/2.0/concepts/computed_fields/)

---

**Migration Lead:** Aruna Kulatunga  
**Sprint:** 9 (Pydantic v2 Upgrade)  
**Date:** December 20, 2025  
**Status:** Phase 1 Complete ✅, Phase 2 Ready for Execution
