# Test Suite Migration Execution Plan

## Current Status (Post-Contracts Migration)

**Contracts Tests:** ✅ 33/33 PASSING  
**Full Suite:** ⚠️ 86 failed, 480 passed

## Failure Categories Analysis

### Category 1: Missing Tax Fields (~40 failures)
**Status:** ✅ Automated Fix Available

**Affected Tests:**
- `tests/api/test_tax_v14_*`
- `tests/analytics_layer/test_casper_*`
- Various integration tests

**Error Pattern:**
```python
KeyError: 'corporate_tax_rate'
KeyError: 'depreciation_start_year'
```

**Fix:**
```bash
python scripts/fix_test_configs_tax.py
```

**Expected Outcome:** ~40 tests will pass

---

### Category 2: Dataclass vs Pydantic Mismatch (~20 failures)
**Status:** ✅ Automated Fix Available

**Affected Contracts:**
- `BreakevenResult`
- `TailRiskSnapshot`

**Error Pattern:**
```python
AttributeError: 'BreakevenResult' object has no attribute 'model_validate'
```

**Fix:**
```bash
python scripts/migrate_remaining_contracts.py
```

**Expected Outcome:** ~20 tests will pass

---

### Category 3: Refinancing Module API Changes (~15 failures)
**Status:** ⚠️ Manual Fix Required

**Affected Tests:**
- `tests/refinancing/test_refinancing_optimizer.py`
- `tests/refinancing/test_refinancing_scenarios.py`
- `tests/refinancing/test_refinancing_triggers.py`

**Error Pattern:**
```python
TypeError: __init__() got an unexpected keyword argument 'config'
```

**Old API:**
```python
optimizer = RefinancingOptimizer(
    config=full_config,
    scenario_result=scenario
)
```

**New API:**
```python
optimizer = RefinancingOptimizer(
    scenario_result=scenario,
    refinancing_config=full_config['refinancing']  # Extract nested section
)
```

**Files to Update:**
1. `tests/refinancing/test_refinancing_optimizer.py` (lines 45, 78, 112)
2. `tests/refinancing/test_refinancing_scenarios.py` (lines 34, 89)
3. `tests/refinancing/test_refinancing_triggers.py` (lines 23, 56)

**Expected Outcome:** ~15 tests will pass

---

### Category 4: FX Configuration Validation (~13 failures)
**Status:** ⚠️ Manual Fix Required

**Affected Tests:**
- `tests/integration/test_fx_monte_carlo_integration.py`
- `tests/test_fx_pipeline_integration.py`
- Various FX scenario tests

**Error Pattern:**
```python
ValidationError: Field required [type=missing, input_value=...]
  fx.base_currency
  fx.volatility_pct
```

**Required FX Config Structure:**
```yaml
fx:
  base_currency: USD
  project_currency: LKR
  base_rate: 330.0
  volatility_pct: 5.0
  correlation_to_revenue: -0.3
  hedge_ratio: 0.0  # Optional
  structured_blocks:  # Optional
    - block_type: forward
      notional_usd: 10000000
      strike_rate: 330.0
```

**Files to Update:**
1. `tests/configs/fx_baseline.yaml`
2. `tests/configs/fx_stress.yaml`
3. `tests/integration/fixtures/fx_monte_carlo_config.yaml`

**Expected Outcome:** ~13 tests will pass

---

## Execution Steps

### Step 1: Pull Latest Changes

```bash
git pull origin feature/add-finance-contracts-pydantic-v2-20251219
```

### Step 2: Run Automated Fixes

**Option A: Run Individual Scripts**
```bash
# Fix 1: Migrate contracts
python scripts/migrate_remaining_contracts.py

# Fix 2: Update test configs
python scripts/fix_test_configs_tax.py

# Verify contracts
pytest tests/finance/test_contracts.py -v
```

**Option B: Run Master Script**
```bash
chmod +x scripts/run_all_fixes.sh
./scripts/run_all_fixes.sh
```

**Expected After Step 2:**
- Contracts: 33/33 ✅
- Estimated suite: ~26 failed, 540 passed

### Step 3: Manual Refinancing Fixes

**Update refinancing test files:**

```python
# File: tests/refinancing/test_refinancing_optimizer.py

# OLD:
optimizer = RefinancingOptimizer(
    config=config,
    scenario_result=scenario
)

# NEW:
optimizer = RefinancingOptimizer(
    scenario_result=scenario,
    refinancing_config=config.get('refinancing', {})
)
```

Repeat for all refinancing test files.

**Verify:**
```bash
pytest tests/refinancing/ -v
```

**Expected After Step 3:**
- Estimated suite: ~13 failed, 553 passed

### Step 4: Manual FX Config Fixes

**Add FX structure to test configs:**

```yaml
# tests/configs/fx_baseline.yaml
fx:
  base_currency: USD
  project_currency: LKR
  base_rate: 330.0
  volatility_pct: 5.0
  correlation_to_revenue: -0.3
```

**Verify:**
```bash
pytest tests/integration/test_fx_monte_carlo_integration.py -v
pytest tests/test_fx_pipeline_integration.py -v
```

**Expected After Step 4:**
- Target: 0-5 failed, 561-566 passed ✅

### Step 5: Full Validation

```bash
# Run complete test suite
pytest

# Run with coverage
pytest --cov=analytics --cov=finance --cov-report=html

# Check coverage report
open htmlcov/index.html
```

---

## Success Criteria

- [ ] Contracts tests: 33/33 passing ✅
- [ ] Analytics layer: >90% passing
- [ ] Refinancing tests: 100% passing
- [ ] FX integration: 100% passing
- [ ] Full suite: >95% passing (560+ tests)
- [ ] No critical regressions
- [ ] Migration guide complete

---

## Rollback Procedures

### If automated scripts fail:

```bash
# Revert contracts file
git checkout HEAD -- analytics/contracts_v14.py

# Revert config changes
git checkout HEAD -- tests/configs/
git checkout HEAD -- configs/
```

### If manual fixes break tests:

```bash
# Stash changes
git stash

# Revert to last working commit
git reset --hard 889cac82

# Review what went wrong
git stash show -p
```

---

## Timeline Estimate

**Automated Fixes:** 5 minutes
- Run scripts: 2 min
- Verify tests: 3 min

**Manual Fixes:** 30 minutes
- Refinancing updates: 15 min
- FX config updates: 10 min
- Testing & validation: 5 min

**Total:** ~35-40 minutes

---

## Post-Migration Tasks

1. **Documentation**
   - Update README with Pydantic v2 notes
   - Add validator documentation to contracts
   - Update API examples

2. **Code Quality**
   - Run linter: `ruff check analytics/contracts_v14.py`
   - Run type checker: `mypy analytics/contracts_v14.py`
   - Format: `ruff format analytics/`

3. **Performance**
   - Benchmark validation overhead
   - Profile test suite runtime
   - Optimize slow validators if needed

4. **Communication**
   - Update team on breaking changes
   - Document migration in CHANGELOG
   - Tag release: `v14.4.0-pydantic-v2`

---

**Migration Owner:** Aruna Kulatunga  
**Sprint:** 9 (Pydantic v2 Migration)  
**Date:** December 20, 2025  
**Status:** Ready for Execution
