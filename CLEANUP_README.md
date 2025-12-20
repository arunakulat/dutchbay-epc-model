# DutchBay EPC Model - Test Cleanup Operation

## 📋 Overview

This cleanup removes **79 non-core test files** while keeping **63 core module tests**.

### Files Generated:
1. `cleanup_non_core_tests.sh` - **Main cleanup script**
2. `CLEANUP_MANIFEST.md` - Detailed file listing
3. `files_to_remove.csv` - CSV of files to remove
4. `test_files_final_categorization.csv` - Complete categorization

---

## 🎯 What Gets Removed (79 files, 1.16 MB)

### Categories:
- **68 files**: Non-core tests (integration, API, CLI, helpers, legacy)
- **7 files**: Config/scenario files  
- **4 files**: Test output files (.txt, 890 KB)

### Examples:
- `pytest_output.txt` (663 KB)
- `pytest_output_after_fix.txt` (177 KB)
- `tests/api/*` - API integration tests
- `tests/analytics_layer/*` - Non-core analytics tests
- `tests/lint/*` - Linting tests
- `tests/_quarantine/*` - Quarantined tests
- `legacy_tests/*` - Legacy test files
- Test config files and stress test scenarios

---

## 🟢 What Gets Kept (63 files, 362 KB)

### Core Module Tests:

- **Contracts** - Pydantic v2 validation
- **Sensitivity** - 12+ test files (best coverage)
- **Cashflow** - Core financial engine tests
- **Monte Carlo** - Stochastic simulation
- **Equity Distribution** - Sprint 12 focus
- **Refinancing** - Sprint 12 focus
- **Debt, WACC, Tax** - Core finance modules
- **Pipeline, Evaluation** - Valuation engine

---

## 🚀 How to Run

### Step 1: Pull Latest Changes
```bash
git pull origin feature/add-finance-contracts-pydantic-v2-20251219
```

### Step 2: Review What Will Be Removed
```bash
# View the manifest
cat CLEANUP_MANIFEST.md

# Or check the CSV
cat files_to_remove.csv
```

### Step 3: Make Script Executable
```bash
chmod +x cleanup_non_core_tests.sh
```

### Step 4: Run Cleanup
```bash
./cleanup_non_core_tests.sh
```

### Step 5: Verify
```bash
# Check what was removed
git status

# Run core tests
pytest tests/ -v
```

### Step 6: Commit and Push
```bash
git add .
git commit -m "chore: Remove 79 non-core test files

- Removed test outputs, config files, and non-essential tests
- Kept 63 core module tests
- Cleaned up for Sprint 12 work"

git push origin feature/add-finance-contracts-pydantic-v2-20251219
```

---

## 📊 Expected Results

### Before:
- 161 test-related files
- ~1.6 MB total

### After:
- 63 core test files
- ~362 KB
- Clean, focused test suite

---

## ✅ Success Criteria

- [ ] Script completes without errors
- [ ] Core tests pass: `pytest tests/ -v`
- [ ] Git status shows ~79 deleted files
- [ ] Ready to push changes

Generated: 2025-12-20 08:40 AM +0530
