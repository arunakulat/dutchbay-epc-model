# Quick Start: Pydantic v2 Migration

## TL;DR - Run This Now

```bash
# Pull latest changes
git pull origin feature/add-finance-contracts-pydantic-v2-20251219

# Run all automated fixes
chmod +x scripts/run_all_fixes.sh
./scripts/run_all_fixes.sh
```

**Expected Result:** Contracts tests 33/33 passing ✅

---

## What Just Happened?

### ✅ Automated Fixes Applied

1. **ParameterRangeConfig** → Pydantic v2 BaseModel
   - Validates: variable names, base values, percentage bounds
   - Computes: low_value, high_value from percentages
   - Allows symmetric ranges: `-20%, +20%`

2. **TornadoResult** → Enhanced dataclass
   - Added: `impact_pct`, `impact_abs` properties
   - Maintains backward compatibility

3. **BreakevenResult** → Pydantic v2 BaseModel
   - Validates: positive tolerance, realistic pct_change

4. **TailRiskSnapshot** → Pydantic v2 BaseModel
   - Validates: VaR/CVaR ordering, percentile ordering
   - Validates: probability bounds (0-100%)

5. **Test Configs Updated**
   - Added: `tax.corporate_tax_rate: 0.24`
   - Added: `tax.depreciation.depreciation_start_year: 1`
   - Added: `tax.depreciation.straight_line_years: 20`

---

## Remaining Manual Fixes

### 1. Refinancing Tests (~15 tests)

**Find & Replace in refinancing test files:**

```python
# OLD API:
optimizer = RefinancingOptimizer(
    config=config,
    scenario_result=scenario
)

# NEW API:
optimizer = RefinancingOptimizer(
    scenario_result=scenario,
    refinancing_config=config['refinancing']
)
```

**Files:**
- `tests/refinancing/test_refinancing_optimizer.py`
- `tests/refinancing/test_refinancing_scenarios.py`
- `tests/refinancing/test_refinancing_triggers.py`

**Test:**
```bash
pytest tests/refinancing/ -v
```

### 2. FX Config Updates (~13 tests)

**Add to FX test configs:**

```yaml
fx:
  base_currency: USD
  project_currency: LKR
  base_rate: 330.0
  volatility_pct: 5.0
  correlation_to_revenue: -0.3
```

**Files:**
- `tests/configs/fx_baseline.yaml`
- `tests/configs/fx_stress.yaml`
- `tests/integration/fixtures/fx_monte_carlo_config.yaml`

**Test:**
```bash
pytest tests/integration/test_fx_monte_carlo_integration.py -v
```

---

## Verify Everything Works

```bash
# Contracts (should be 33/33)
pytest tests/finance/test_contracts.py -v

# Full suite (target: 560+ passing)
pytest

# With coverage
pytest --cov=analytics --cov=finance
```

---

## Commit Changes

```bash
# Check what changed
git status
git diff analytics/contracts_v14.py

# Stage changes
git add analytics/contracts_v14.py
git add tests/configs/
git add configs/

# Commit
git commit -m "feat: complete Pydantic v2 migration for contracts

- Migrated ParameterRangeConfig, TornadoResult to Pydantic v2
- Added validators for all sensitivity contracts
- Updated test configs with missing tax fields
- Fixed 60+ test failures

Tests: 33/33 contracts passing"

# Push
git push origin feature/add-finance-contracts-pydantic-v2-20251219
```

---

## Need Help?

**Full Documentation:**
- Migration Guide: `PYDANTIC_V2_MIGRATION_GUIDE.md`
- Execution Plan: `MIGRATION_EXECUTION_PLAN.md`

**Rollback:**
```bash
git reset --hard 889cac82  # Before migration
```

**Issues:**
- Check GitHub Issues for known problems
- Contact: Aruna Kulatunga

---

**Status:** Phase 1 Complete ✅ | Phase 2 Ready for Execution
