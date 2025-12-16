# Sprint 11 - Tax Profile Verification & Test Execution

**Date:** December 16, 2025  
**Status:** 🚀 READY FOR EXECUTION  
**Branch:** `sprint-11-tax-profile`

---

## Quick Start (5 Minutes)

### 1. Switch to Feature Branch
```bash
git checkout sprint-11-tax-profile
cd DutchBay_EPC_Model
```

### 2. Activate Virtual Environment
```bash
source .venv311/bin/activate
# or on Mac:
source .venv311/bin/activate
```

### 3. Run Tax Profile Tests
```bash
pytest tests/finance/test_cashflow_v14_tax_refactored.py -v --tb=short
```

**Expected Result:**
```
======================== 22 passed in 0.5s ========================
```

---

## Detailed Test Coverage

### Test File Location

```
tests/
└── finance/
    └── test_cashflow_v14_tax_refactored.py  (313 lines, 22 tests)
```

### Test Structure

```
test_cashflow_v14_tax_refactored.py
├── TestTaxProfile (7 tests)
│  ├── test_tax_profile_initialization_valid
│  ├── test_tax_profile_is_frozen
│  ├── test_tax_profile_validation_rate_too_high
│  ├── test_tax_profile_validation_rate_negative
│  ├── test_tax_profile_validation_holiday_years_negative
│  ├── test_tax_profile_validation_holiday_start_year_zero
│  ├┠── test_is_in_tax_holiday_* (3 tests)
│  
├── TestBuildTaxProfile (6 tests)
│  ├── test_depreciation_schedule_length_equals_project_life
│  ├── test_depreciation_schedule_too_short_padded
│  ├── test_depreciation_schedule_too_long_trimmed
│  ├── test_depreciation_sum_respects_capex_and_enhancement
│  ├── test_depreciation_zero_when_capex_none
│  └── test_depreciation_zero_when_* (2 more)
│  
├── TestCalculateTaxForYear (8 tests)
│  ├── test_tax_during_holiday_is_zero
│  ├── test_tax_after_holiday_is_applied
│  ├── test_interest_shield_enabled_reduces_tax
│  ├── test_interest_shield_disabled_ignores_interest
│  ├── test_interest_shield_comparison
│  ├── test_negative_taxable_income_floors_to_zero
│  ├── test_tax_rate_zero_results_in_zero_tax
│  └── test_depreciation_* (2 more)
│  
└── TestIntegrationScenarios (2 tests)
   ├── test_full_scenario_3year_holiday_20year_depreciation
   └── test_lender_case_strong_cfads_scenario
   └── test_stressed_scenario_low_cfads
```

---

## Test Execution Scripts

### Script 1: Run All Tax Profile Tests

```bash
#!/bin/bash
# run_tax_tests.sh

echo "🪟 Tax Profile Test Suite"
echo "==================================="

pytest tests/finance/test_cashflow_v14_tax_refactored.py -v \
  --tb=short \
  --color=yes

echo ""
echo "Exit code: $?"
```

### Script 2: Run Individual Test Classes

```bash
# Test TaxProfile validation
pytest tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile -v

# Test depreciation schedule building
pytest tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile -v

# Test annual tax calculation
pytest tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear -v

# Test realistic scenarios
pytest tests/finance/test_cashflow_v14_tax_refactored.py::TestIntegrationScenarios -v
```

### Script 3: Run with Coverage Report

```bash
pytest tests/finance/test_cashflow_v14_tax_refactored.py \
  -v \
  --cov=finance.cashflow_v14_tax \
  --cov-report=html \
  --cov-report=term-missing

echo "Coverage report generated in htmlcov/index.html"
```

### Script 4: Run with Performance Timing

```bash
pytest tests/finance/test_cashflow_v14_tax_refactored.py \
  -v \
  --durations=10  # Show 10 slowest tests
```

---

## Expected Test Results by Category

### Category 1: TaxProfile Initialization (7 tests)

| Test | Expected | Notes |
|------|----------|-------|
| valid_init | ✅ PASS | Creates profile without error |
| frozen | ✅ PASS | AttributeError on mutation attempt |
| rate_too_high | ✅ PASS | Raises ValueError for rate > 1.0 |
| rate_negative | ✅ PASS | Raises ValueError for rate < 0.0 |
| holiday_years_negative | ✅ PASS | Raises ValueError for years < 0 |
| start_year_zero | ✅ PASS | Raises ValueError for year < 1 |
| holiday_logic | ✅ PASS | is_in_tax_holiday() works correctly |

### Category 2: Depreciation Schedule (6 tests)

| Test | Expected | Notes |
|------|----------|-------|
| length_matches | ✅ PASS | len(schedule) == project_life_years |
| short_padded | ✅ PASS | Zero-padded if depreciation_years < project_life_years |
| long_trimmed | ✅ PASS | Trimmed if depreciation_years > project_life_years |
| sum_correct | ✅ PASS | sum(schedule[:dep_years]) == capex × enhancement |
| capex_none | ✅ PASS | All zeros if capex is None |
| capex_negative | ✅ PASS | All zeros if capex <= 0 |

### Category 3: Tax Calculation (8 tests)

| Test | Expected | Notes |
|------|----------|-------|
| holiday_zero | ✅ PASS | tax = 0.0 during holiday |
| after_holiday | ✅ PASS | tax calculated after holiday |
| shield_enabled | ✅ PASS | Interest reduces taxable income |
| shield_disabled | ✅ PASS | Interest ignored when disabled |
| shield_compare | ✅ PASS | With shield < without shield |
| negative_income | ✅ PASS | Negative taxable floored to 0 |
| zero_rate | ✅ PASS | rate=0 → tax=0 |
| beyond_schedule | ✅ PASS | depreciation=0 if year > schedule length |

### Category 4: Integration Scenarios (2 tests)

| Test | Expected | Notes |
|------|----------|-------|
| full_3yr_holiday | ✅ PASS | Holiday logic + depreciation + interest |
| lender_case | ✅ PASS | Strong CFADS, meaningful interest shield |

---

## Manual Verification Checklist

After running tests, verify:

### Code Quality
- [ ] All imports resolve correctly
- [ ] No warnings or deprecation notices
- [ ] Type hints pass mypy check

```bash
mypy finance/cashflow_v14_tax.py --strict
```

- [ ] Code follows PEP 8

```bash
pylint finance/cashflow_v14_tax.py
```

### Functionality Verification

```python
# Test 1: Basic profile creation
from finance.cashflow_v14_tax import TaxProfile, build_tax_profile

profile = build_tax_profile(
    corporate_tax_rate=0.24,
    capex_depreciable_lkr=100_000_000,
    depreciation_years=20,
    enhanced_capital_allowance_pct=1.0,
    tax_holiday_years=3,
)
assert profile.corporate_tax_rate == 0.24
assert len(profile.depreciation_schedule_lkr) == 25  # default project life
print("✅ Test 1: Basic profile creation - PASSED")

# Test 2: Tax calculation with holiday
from finance.cashflow_v14_tax import calculate_tax_for_year

tax_y1, dep_y1 = calculate_tax_for_year(
    profile=profile,
    pretax_cfads_lkr=50_000_000,
    interest_expense_lkr=10_000_000,
    year_index=0,
)
assert tax_y1 == 0.0  # In holiday
assert dep_y1 == 5_000_000.0  # 100M / 20
print("✅ Test 2: Tax calculation with holiday - PASSED")

# Test 3: Tax calculation after holiday
tax_y4, dep_y4 = calculate_tax_for_year(
    profile=profile,
    pretax_cfads_lkr=50_000_000,
    interest_expense_lkr=10_000_000,
    year_index=3,  # Year 4, after 3-year holiday
)
expected_tax = (50_000_000 - 5_000_000 - 10_000_000) * 0.24  # 8.4M
assert tax_y4 == expected_tax
print("✅ Test 3: Tax calculation after holiday - PASSED")

print("\n✅ All manual tests PASSED")
```

---

## Test Output Examples

### Successful Run

```
$ pytest tests/finance/test_cashflow_v14_tax_refactored.py -v --tb=short

======================== test session starts =========================
platform darwin -- Python 3.11.0, pytest-7.4.3, pluggy-1.1.1
rootdir: /Users/aruna/DutchBay_EPC_Model
configfile: pyproject.toml
collected 22 items

tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_tax_profile_initialization_valid PASSED [ 4%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_tax_profile_is_frozen PASSED [ 9%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_tax_profile_validation_rate_too_high PASSED [ 13%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_tax_profile_validation_rate_negative PASSED [ 18%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_tax_profile_validation_holiday_years_negative PASSED [ 22%]
tests/finance/test_cashflow_v14_tax_refactoring_validation_holiday_start_year_zero PASSED [ 27%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_is_in_tax_holiday_no_holiday PASSED [ 31%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile::test_depreciation_schedule_length_equals_project_life PASSED [ 36%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile::test_depreciation_schedule_too_short_padded PASSED [ 40%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile::test_depreciation_schedule_too_long_trimmed PASSED [ 45%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile::test_depreciation_sum_respects_capex_and_enhancement PASSED [ 50%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile::test_depreciation_zero_when_capex_none PASSED [ 54%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestBuildTaxProfile::test_depreciation_zero_when_capex_negative PASSED [ 59%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear::test_tax_during_holiday_is_zero PASSED [ 63%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear::test_tax_after_holiday_is_applied PASSED [ 68%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear::test_interest_shield_enabled_reduces_tax PASSED [ 72%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear::test_interest_shield_disabled_ignores_interest PASSED [ 77%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear::test_negative_taxable_income_floors_to_zero PASSED [ 81%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestCalculateTaxForYear::test_tax_rate_zero_results_in_zero_tax PASSED [ 86%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestIntegrationScenarios::test_full_scenario_3year_holiday_20year_depreciation PASSED [ 90%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestIntegrationScenarios::test_lender_case_strong_cfads_scenario PASSED [ 95%]
tests/finance/test_cashflow_v14_tax_refactored.py::TestIntegrationScenarios::test_stressed_scenario_low_cfads PASSED [100%]

======================== 22 passed in 0.48s ==========================
```

### What Happens if Tests Fail

If a test fails, you'll see:

```
FAILED tests/finance/test_cashflow_v14_tax_refactored.py::TestTaxProfile::test_tax_profile_validation_rate_too_high - ValueError: corporate_tax_rate must be 0.0–1.0; got 1.5

===================== 1 failed, 21 passed in 0.5s ======================
```

**Action:** Check the error message and trace. Likely causes:
1. TaxProfile validation not working
2. Import error
3. Module not found

---

## Debugging Guide

### Issue 1: Module Import Error

```
ModuleNotFoundError: No module named 'finance.cashflow_v14_tax'
```

**Solution:**
```bash
# Verify file exists
ls -la finance/cashflow_v14_tax.py

# Check __init__.py exports it
grep "cashflow_v14_tax" finance/__init__.py

# Try importing directly
python -c "from finance.cashflow_v14_tax import TaxProfile; print('OK')"
```

### Issue 2: Test Discovery Failure

```
ERROR collecting tests/finance/test_cashflow_v14_tax_refactored.py
```

**Solution:**
```bash
# Check test file syntax
python -m py_compile tests/finance/test_cashflow_v14_tax_refactored.py

# Run pytest with verbose collection
pytest tests/finance/test_cashflow_v14_tax_refactored.py --collect-only -v
```

### Issue 3: Assertion Errors

```
AssertionError: assert 8400000.0 == 8400001.0
```

**Solution:**
```bash
# Check for floating-point precision issues
# Use pytest.approx() for float comparisons
assert tax == pytest.approx(expected_tax)  # Tolerance: 1e-6
```

---

## Performance Benchmarks

**Expected execution time:** < 1 second for all 22 tests

### Timing Breakdown

```bash
pytest tests/finance/test_cashflow_v14_tax_refactored.py --durations=10

========================= slowest 10 durations ==========================

test_full_scenario_3year_holiday_20year_depreciation      0.012s
test_lender_case_strong_cfads_scenario                    0.008s
test_depreciation_sum_respects_capex_and_enhancement      0.005s
test_interest_shield_comparison                           0.004s
test_tax_profile_validation_rate_too_high                 0.003s
...

========================= 22 passed in 0.48s ==========================
```

---

## Next Steps

### After Tests Pass ✅

1. **Create Pull Request**
   ```bash
   git push origin sprint-11-tax-profile
   # Then open PR on GitHub
   ```

2. **Request Code Review**
   - Tag: @arunakulat
   - Assign reviewers
   - Check CI/CD pipeline

3. **Merge to sprint-11**
   ```bash
   git checkout sprint-11
   git merge sprint-11-tax-profile
   ```

4. **Move to Phase 1b (WACC Integration)**
   - Create branch: `sprint-11-wacc-integration`
   - Implement WAACProfile
   - Integrate interest injection

---

## Reference Commands

### Common pytest Options

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Stop after first failure
pytest -x

# Show slowest tests
pytest --durations=10

# Run specific test by name
pytest -k test_tax_during_holiday_is_zero

# Show coverage
pytest --cov=finance.cashflow_v14_tax

# Generate HTML coverage report
pytest --cov=finance.cashflow_v14_tax --cov-report=html
```

---

## Support & Troubleshooting

**Questions?**
- Check: SPRINT_11_PHASE_1A_IMPLEMENTATION.md (design details)
- Review: finance/cashflow_v14_tax.py (source code)
- Read: tests/finance/test_cashflow_v14_tax_refactored.py (test examples)

**Stuck?**
- Run with `--tb=long` for full traceback
- Add `print()` statements and run with `-s` flag
- Check git log for recent changes

---

**Status:** 🚀 READY FOR TESTING

**Next Step:** Execute test suite and verify all 22 tests pass!
