# 🧹 POST-PUSH TEST CLEANUP ANALYSIS

**Purpose:** Identify and remove test cruft after v14 fixes are pushed
**Timing:** Run this AFTER `git push origin main`
**Scope:** Analyze `/tests/api/` folder for duplicates and stale files

---

## 📊 ANALYSIS CHECKLIST

### Step 1: Identify Duplicate/Variant Test Files

Look for files with patterns like:
- `test_*_v13.py` vs `test_*_v14.py` → Only keep v14
- `test_*_refactored.py` vs `test_*.py` → Keep the better version
- `test_*_regression.py` vs `test_*_regression_v14.py` → Consolidate

**Common test file patterns to watch:**
```
tests/api/test_covenants_*.py        # Check for duplicates
tests/api/test_debt_*.py             # Check v13 vs v14 versions
tests/api/test_scenario_*.py         # Check for variants
tests/api/test_*_refactored.py       # Check if original still exists
```

### Step 2: Run Cleanup Analysis Script

```bash
cd ~/DutchBay_EPC_Model

# List all test files with counts
ls -lh tests/api/test_*.py | wc -l

# Show files sorted by modification date
ls -lt tests/api/test_*.py | head -20

# Find potential duplicates (same name + variant)
ls tests/api/test_*.py | sed 's/_v13\|_v14\|_refactored\|\.py//g' | sort | uniq -d
```

### Step 3: Categorize Files

Create a matrix:

| File Name | Status | Version | Keep? | Reason |
|-----------|--------|---------|-------|--------|
| `test_covenants_v14.py` | ✅ | v14 | YES | Current |
| `test_covenants_lendercase_2025Q4.py` | ❓ | v14 | ? | Check |
| `test_covenants_lendercase_refactored.py` | ❓ | v14 | ? | Check |
| `test_debt_construction_idc_regression_v14.py` | ✅ | v14 | YES | Current |
| `test_debt_v14_construction.py` | ✅ | v14 | YES | Current |
| ... | ... | ... | ... | ... |

---

## 🔍 CLEANUP RULES (Go-with-the-Flow)

### Rule 1: Keep ONLY v14
- ❌ Remove all `*_v13.py` files
- ❌ Remove all `*_legacy.py` files
- ✅ Keep all `*_v14.py` files
- ✅ Keep all `test_*.py` without version suffix (assume current)

### Rule 2: Consolidate Variants
- If both `test_X.py` and `test_X_refactored.py` exist:
  - If refactored is better → Keep refactored, remove original
  - If original is better → Keep original, remove refactored
  - If identical → Keep one, remove other

### Rule 3: Remove Stale Artifacts
- ❌ Remove `*.bak` files (backups)
- ❌ Remove `*_old.py`, `*_deprecated.py`, etc.
- ❌ Remove test files with TODO comments (incomplete)
- ✅ Keep all active, passing tests

### Rule 4: Document Removals
Create a file `CLEANUP_LOG.md` documenting:
- What was removed
- Why it was removed
- When it was removed
- Alternative file if consolidated

---

## 📋 SUSPECTED FILES FOR CLEANUP

Based on earlier context, these files might be candidates:

### Likely to Remove:
```
tests/api/test_debt_construction_idc_regression.py.bak    # Backup - remove
tests/api/test_*_v13.py                                   # Old version
tests/api/test_*_legacy.py                                # Deprecated
tests/api/test_*_old.py                                   # Stale
```

### Likely to Keep:
```
tests/api/test_debt_v14_construction.py                   # FIXED ✅
tests/api/test_scenario_analytics_schema_guard_integration.py  # FIXED ✅
tests/api/test_debt_construction_idc_regression_v14.py    # PINS UPDATED ✅
tests/api/test_covenants_v14.py                           # Current
tests/api/test_covenants_v14_refactored.py                # Check if better
```

### Need Manual Review:
```
tests/api/test_covenants_lendercase_2025Q4.py            # ? Active/duplicate?
tests/api/test_covenants_lendercase_refactored.py        # ? Variant/consolidate?
```

---

## 🚀 CLEANUP SCRIPT (Template)

```bash
#!/bin/bash
# Post-push test cleanup
# Run AFTER: git push origin main

cd ~/DutchBay_EPC_Model

echo "📊 Test Folder Cleanup Analysis"
echo "================================"
echo ""

# Count files
TOTAL=$(ls tests/api/test_*.py | wc -l)
echo "Total test files: $TOTAL"
echo ""

# List potential duplicates
echo "Potential duplicates (same base name, different variants):"
ls tests/api/test_*.py | sed 's/_v13\|_v14\|_refactored\|\.py//g' | sort | uniq -d
echo ""

# List backup files to remove
echo "Backup files to remove:"
ls tests/api/*.bak 2>/dev/null || echo "None found"
echo ""

# List by modification date
echo "Recently modified files (last 10):"
ls -lt tests/api/test_*.py | head -10
echo ""

echo "✅ Analysis complete. Review suggestions above."
```

---

## 📝 POST-CLEANUP CHECKLIST

- [ ] All v14 tests passing
- [ ] No duplicate test files
- [ ] No backup files (*.bak)
- [ ] No stale/_old/_v13 files
- [ ] Cleanup decisions documented
- [ ] All removals committed to git
- [ ] Coverage still ≥ 55%
- [ ] Full CI pipeline passing

---

## 🎯 FINAL STATE (After Cleanup)

```
tests/api/
├── test_bad_missing_tax_schema_guard.py              ✅ Keep
├── test_cashflow_module.py                          ✅ Keep
├── test_cashflow_tax_and_life.py                    ✅ Keep
├── test_cashflow_v14.py                             ✅ Keep
├── test_config_schema_guard.py                      ✅ Keep
├── test_covenants_v14.py                            ✅ Keep
├── test_covenants_v14_refactored.py                 ? Review/consolidate
├── test_covenants_lendercase_2025Q4.py              ? Review/consolidate
├── test_covenants_lendercase_refactored.py          ? Review/consolidate
├── test_debt_construction_idc_regression_v14.py     ✅ Keep (JUST FIXED)
├── test_debt_v14_construction.py                    ✅ Keep (JUST FIXED)
├── test_scenario_analytics_schema_guard_integration.py ✅ Keep (JUST FIXED)
└── [all others that are active v14 tests]           ✅ Keep
```

**Target:** Reduce from current count to ~15-20 focused, non-redundant tests

---

## 🔗 NEXT STEPS

1. **Commit & Push current fixes:**
   ```bash
   git add tests/api/test_debt_v14_construction.py
   git add tests/api/test_scenario_analytics_schema_guard_integration.py
   git add tests/api/test_debt_construction_idc_regression_v14.py
   git commit -m "refactor(tests): v14 API alignment - fix 3 failing tests"
   git push origin main
   ```

2. **After push, run cleanup analysis:**
   ```bash
   bash cleanup_test_analysis.sh > cleanup_report.txt
   ```

3. **Review cleanup decisions:**
   - Go through files identified for removal
   - Consolidate variants if needed
   - Document in CLEANUP_LOG.md

4. **Execute cleanup:**
   ```bash
   git rm tests/api/[files_to_remove]
   git commit -m "test(cleanup): remove duplicate/stale test artifacts"
   git push origin main
   ```

---

**Status:** Ready to push! 🚀
**Cleanup:** Can begin immediately after push ✅
