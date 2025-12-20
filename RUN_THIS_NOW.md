# 🚨 RUN THIS NOW - Fix Remaining Test Failures

## The Problem

You ran Phase 1 fixes successfully (contracts are working), but **86 tests still fail** because:

1. ❌ `TornadoResult.model_validate()` doesn't exist (it's a dataclass, not Pydantic)
2. ❌ Tests use old field names (`tornado_results` instead of `tornado_ranking`)
3. ❌ Test configs missing `corporate_tax_rate` and `depreciation_start_year`

## The Solution - 3 Commands

```bash
# Step 1: Pull the new fix scripts
git pull origin feature/add-finance-contracts-pydantic-v2-20251219

# Step 2: Run Phase 2 targeted fixes
chmod +x scripts/run_phase2_fixes.sh
./scripts/run_phase2_fixes.sh

# Step 3: Verify improvement
pytest --tb=short
```

## What Phase 2 Fixes Do

### Fix 1: `TornadoResult.model_validate()` → `TornadoResult()`
**File:** `analytics/sensitivity_v14.py`  
**Problem:** Code calls `.model_validate()` on a dataclass  
**Solution:** Use direct instantiation

**Before:**
```python
return TornadoResult.model_validate({...})
```

**After:**
```python
return TornadoResult({...})
```

**Fixes:** ~15 test failures

---

### Fix 2: Update Field Names
**Files:** All `test_*.py` files  
**Problem:** Tests use deprecated field names

**Changes:**
```python
# Before → After
tornado_results=  →  tornado_ranking=
technology=       →  technology_type=
metric=           →  metric_name=
variable=         →  variable_name=
```

**Fixes:** ~10 test failures

---

### Fix 3: Add Tax Fields to Inline Configs
**Files:** Test files with inline dict configs  
**Problem:** Configs created in tests missing tax fields

**Adds:**
```python
'tax': {
    'corporate_tax_rate': 0.24,
    'depreciation': {
        'depreciation_start_year': 1,
        'straight_line_years': 20
    }
}
```

**Fixes:** ~5-10 test failures

---

## Expected Results

**Before Phase 2:**
- ❌ 86 failures, 494 passing

**After Phase 2:**
- ✅ ~56-66 failures, ~514-524 passing
- 🎯 20-30 tests fixed automatically

**Remaining failures will be:**
- Refinancing API changes (manual fix)
- FX config validation (manual fix)
- Edge cases requiring code review

## If Something Goes Wrong

### Rollback
```bash
git stash  # Save your changes
git reset --hard HEAD~3  # Go back before Phase 2 fixes
```

### Check What Changed
```bash
# See Phase 2 changes
git diff HEAD~3..HEAD analytics/sensitivity_v14.py
git diff HEAD~3..HEAD tests/
```

## Next Steps After Phase 2

1. **Commit Phase 2 fixes:**
   ```bash
   git add -A
   git commit -m "fix: Phase 2 targeted fixes - 20-30 tests passing"
   git push origin feature/add-finance-contracts-pydantic-v2-20251219
   ```

2. **Manual fixes for remaining failures:**
   - See `MIGRATION_EXECUTION_PLAN.md` for detailed steps
   - Focus on refinancing and FX tests
   - Review edge cases individually

3. **Target final state:**
   - ✅ 560+ tests passing (95%+)
   - ✅ All contracts migrated to Pydantic v2
   - ✅ Full test coverage maintained

---

**Don't wait - run Phase 2 now!** ⚡

```bash
git pull origin feature/add-finance-contracts-pydantic-v2-20251219
chmod +x scripts/run_phase2_fixes.sh
./scripts/run_phase2_fixes.sh
```
