# Step-by-Step Integration Guide

**Current Status**: Phase 1-2 refactoring complete (14/14 tests passing)
**Goal**: Wire tax + WACC into main financial model
**Duration**: ~2-3 hours

---

## Part A: Phase 1 Integration (Tax Layer)

### A1. Examine Current Cashflow Engine

```bash
# First, understand the current structure
grep -n "tax" finance/cashflow/cashflow_v14.py | head -20
grep -n "depreciation" finance/cashflow/cashflow_v14.py | head -20
grep -n "interest" finance/cashflow/cashflow_v14.py | head -20
```

Note:
- Where is tax currently calculated?
- How is depreciation handled?
- Where does interest come from?

### A2. Locate the Main Cashflow Builder Function

**File**: `finance/cashflow/cashflow_v14.py`

**Find function**: `build_annual_rows()` or similar

This function should:
- Take config + debt results as input
- Return list of annual dictionaries
- Each dict has: year, revenue, opex, taxes, etc.

### A3. Add Phase 1 Imports

**At top of `cashflow_v14.py`**:

```python
from finance.tax_profile import (
    TaxProfile,
    DepreciationSchedule,
    TaxResult,
    build_tax_series,
)
```

### A4. Create TaxProfile Helper Function

**Add this function to `cashflow_v14.py`**:

```python
def _create_tax_profile(config: Mapping[str, Any]) -> TaxProfile:
    """
    Extract tax configuration and create TaxProfile instance.

    Reads from config.tax or config.finance sections.
    """
    tax_cfg = config.get("tax", {}) or {}

    return TaxProfile(
        tax_rate=float(tax_cfg.get("tax_rate", 0.25)),  # Default 25%
        interest_deductible=bool(tax_cfg.get("interest_deductible", True)),
        depreciation_method=str(tax_cfg.get("depreciation_method", "straight_line")),
        asset_base=float(config.get("capex", {}).get("usd_total", 0.0)),
        depreciation_years=int(tax_cfg.get("depreciation_years", 20)),
        tax_holiday_years=int(tax_cfg.get("tax_holiday_years", 0)),
    )
```

### A5. Create Depreciation Schedule Helper

**Add to `cashflow_v14.py`**:

```python
def _create_depreciation_schedule(
    tax_profile: TaxProfile,
    num_years: int,
) -> DepreciationSchedule:
    """
    Create depreciation schedule from tax profile.
    """
    return DepreciationSchedule(
        method=tax_profile.depreciation_method,
        asset_base=tax_profile.asset_base,
        years=tax_profile.depreciation_years,
    )
```

### A6. Extract Interest Expense from Debt Module

**Add to `cashflow_v14.py`**:

```python
def _extract_interest_expense(
    debt_result: Mapping[str, Any],
    fx_rate: float,
    num_years: int,
) -> List[float]:
    """
    Extract annual interest expense in LKR from debt module result.

    Args:
        debt_result: Output from debt_v14.plan_debt()
        fx_rate: LKR per USD conversion rate
        num_years: Number of periods

    Returns:
        List of annual interest in LKR
    """
    # Try to get interest series from debt result
    interest_usd = debt_result.get("interest_expense_series", [])

    # If not available, try alternate keys
    if not interest_usd:
        interest_usd = debt_result.get("annual_interest_usd", [])

    # Convert to LKR
    interest_lkr = [
        float(amt or 0.0) * fx_rate
        for amt in interest_usd
    ]

    # Pad to num_years if needed
    while len(interest_lkr) < num_years:
        interest_lkr.append(0.0)

    return interest_lkr[:num_years]
```

### A7. Integrate Tax into Annual Rows Function

**Modify `build_annual_rows()` function**:

Find the part where tax is currently calculated. Replace it with:

```python
def build_annual_rows(
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    # ... other params ...
) -> List[Dict[str, float]]:

    # ... existing code to build base rows ...

    # PHASE 1 INTEGRATION: Create tax components
    tax_profile = _create_tax_profile(config)
    depreciation_schedule = _create_depreciation_schedule(
        tax_profile,
        len(annual_rows)
    )

    # Extract FX rate
    fx_cfg = config.get("fx", {}) or {}
    fx_rate = float(fx_cfg.get("base_rate", 300.0))

    # Get interest expense from debt module
    interest_expense_lkr = _extract_interest_expense(
        debt_result,
        fx_rate,
        len(annual_rows),
    )

    # Extract taxable income series (EBIT before interest deduction)
    taxable_income_before_interest = [
        annual_rows[i].get("ebit_lkr", 0.0)
        for i in range(len(annual_rows))
    ]

    # PHASE 1: Build tax series using new engine
    tax_series = build_tax_series(
        tax_profile=tax_profile,
        taxable_income_series=taxable_income_before_interest,
        interest_expense_series=interest_expense_lkr,
        depreciation_schedule=depreciation_schedule,
        years=len(annual_rows),
    )

    # Apply tax results to annual rows
    for idx, (tax_result, row) in enumerate(
        zip(tax_series, annual_rows)
    ):
        row["depreciation_lkr"] = tax_result.depreciation
        row["interest_expense_lkr"] = interest_expense_lkr[idx]
        row["taxable_income_lkr"] = tax_result.taxable_income
        row["tax_lkr"] = tax_result.tax_liability
        row["tax_holiday_flag"] = tax_result.tax_holiday_year

        # Update post-tax CFADS
        pretax_cfads = row.get("pretax_cfads_lkr", 0.0)
        row["posttax_cfads_lkr"] = pretax_cfads - tax_result.tax_liability

    return annual_rows
```

### A8. Test Phase 1 Integration

**Run this test**:

```bash
# First, verify Phase 1-2 tests still pass
pytest tests/test_phase_1_2_refactoring.py::TestPhase1TaxProfile -v

# If you have cashflow-specific tests, run them:
pytest tests/ -k cashflow -v

# Test with a sample scenario manually (create small test)
python -c "
import json
from finance.cashflow.cashflow_v14 import build_annual_rows

config = {
    'capex': {'usd_total': 100_000_000},
    'tax': {'tax_rate': 0.25, 'depreciation_years': 20},
    'fx': {'base_rate': 300.0},
    'project': {'years': 10},
}

debt_result = {
    'interest_expense_series': [5e6] * 10,  # 5M USD per year
}

rows = build_annual_rows(config, debt_result, ...)
print(json.dumps(rows[0], indent=2))
"
```

---

## Part B: Phase 2 Integration (WACC)

### B1. Examine Current Discount Rate Usage

```bash
# Find all hardcoded discount rates
grep -rn "0.10" finance/ analytics/ | grep -v test | grep -v "__pycache__"
grep -rn "DEFAULT_DISCOUNT_RATE" finance/ analytics/
grep -rn "discount" finance/equity/irr.py
```

Note where discount rate is used:
- IRR calculations?
- NPV calculations?
- KPI computations?

### B2. Locate KPI Calculator

**Likely locations**:
- `analytics/core/metrics.py`
- `finance/equity/equity_v14.py`
- `analytics/evaluation_v14.py`

### B3. Create WACC Initialization Function

**Add to `finance/equity/equity_v14.py` or new `finance/wacc_init.py`**:

```python
from finance.wacc_integration import (
    WaccResult,
    calculate_wacc,
)

def initialize_wacc(
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
) -> WaccResult:
    """
    Calculate WACC once at model initialization using Phase 2 engine.

    Args:
        config: Model configuration
        debt_result: Output from debt_v14.plan_debt()

    Returns:
        WaccResult with both nominal and prudential rates
    """

    wacc_cfg = config.get("wacc", {}) or {}
    tax_cfg = config.get("tax", {}) or {}
    debt_cfg = config.get("financing", {}) or {}

    # WACC inputs
    risk_free_rate = float(wacc_cfg.get("risk_free_rate", 0.05))
    market_risk_premium = float(wacc_cfg.get("market_risk_premium", 0.06))
    asset_beta = float(wacc_cfg.get("asset_beta", 0.8))
    tax_rate = float(tax_cfg.get("tax_rate", 0.25))
    inflation_rate = float(wacc_cfg.get("inflation_rate", 0.04))

    # Debt metrics
    total_debt_usd = float(debt_result.get("total_debt_usd", 0.0))
    avg_cost_of_debt = float(
        debt_result.get("weighted_avg_cost", 0.06)
    )

    # Calculate target debt-to-value
    # (can be from config or derived from debt/equity)
    target_d2v = float(wacc_cfg.get("target_debt_to_value", 0.6))

    # Call Phase 2 engine
    wacc_result = calculate_wacc(
        risk_free_rate=risk_free_rate,
        market_risk_premium=market_risk_premium,
        asset_beta=asset_beta,
        target_debt_to_value=target_d2v,
        cost_of_debt=avg_cost_of_debt,
        tax_rate=tax_rate,
        inflation_rate=inflation_rate,
    )

    return wacc_result
```

### B4. Replace Hardcoded Discount Rate

**In `finance/equity/equity_v14.py`**:

```python
# OLD
DEFAULT_DISCOUNT_RATE = 0.10  # Remove this

# NEW
def calculate_equity_irr(
    cashflows: Sequence[float],
    discount_rate: Optional[float] = None,
) -> Optional[float]:
    """
    Calculate equity IRR.

    If discount_rate is None, uses WACC from global model state.
    """
    if discount_rate is None:
        # Get WACC from model initialization (stored somewhere accessible)
        # For now, you can pass it explicitly
        discount_rate = 0.10  # Fallback

    return _irr(cashflows, discount_rate)
```

### B5. Wire WACC into KPI Calculation

**In your KPI calculator function**:

```python
def calculate_all_kpis(
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    equity_cashflows: List[float],
    project_cashflows: List[float],
) -> Dict[str, float]:
    """
    Calculate all KPIs using Phase 1-2 (tax + WACC).
    """

    # PHASE 2: Initialize WACC
    wacc_result = initialize_wacc(config, debt_result)
    discount_rate = wacc_result.base.wacc_nominal

    # Use WACC for all discount rate operations
    return {
        "equity_irr": calculate_equity_irr(equity_cashflows, discount_rate),
        "project_irr": calculate_project_irr(project_cashflows, discount_rate),
        "equity_npv": calculate_equity_npv(equity_cashflows, discount_rate),
        "project_npv": calculate_project_npv(project_cashflows, discount_rate),
        "wacc_nominal": wacc_result.base.wacc_nominal,
        "wacc_prudential": wacc_result.base.wacc_prudential,
        # ... other KPIs ...
    }
```

### B6. Test Phase 2 Integration

```bash
# Verify Phase 2 tests still pass
pytest tests/test_phase_1_2_refactoring.py::TestPhase2WaccIntegration -v

# Test WACC calculation
python -c "
from finance.wacc_integration import calculate_wacc

wacc = calculate_wacc(
    risk_free_rate=0.05,
    market_risk_premium=0.06,
    asset_beta=0.8,
    target_debt_to_value=0.6,
    cost_of_debt=0.06,
    tax_rate=0.25,
    inflation_rate=0.04,
)

print(f'WACC Nominal: {wacc.base.wacc_nominal:.2%}')
print(f'WACC Prudential: {wacc.base.wacc_prudential:.2%}')
"
```

---

## Part C: Full Integration Test

### C1. Run Phase 1-2 Tests

```bash
pytest tests/test_phase_1_2_refactoring.py -v
```

**Expected**: 14/14 PASS ✅

### C2. Run End-to-End Pipeline

```bash
# If you have a main pipeline runner
python -m analytics.orchestrators.scenario_analytics \
    --config scenarios/test/base_scenario.yaml

# Or create a simple integration test:
python -c "
import json
from finance.cashflow.cashflow_v14 import build_annual_rows
from finance.wacc_integration import calculate_wacc
from finance.equity.equity_v14 import calculate_equity_performance

# Load test scenario
with open('scenarios/test/base_scenario.yaml') as f:
    import yaml
    config = yaml.safe_load(f)

print('✓ Configuration loaded')

# Run Phase 1 (tax)
debt_result = {}  # Simulate debt output
rows = build_annual_rows(config, debt_result)
print(f'✓ Phase 1: {len(rows)} annual rows calculated')
print(f'  - Year 1 tax: {rows[0].get(\"tax_lkr\", 0):.0f}')

# Run Phase 2 (WACC)
wacc = calculate_wacc(...)
print(f'✓ Phase 2: WACC calculated = {wacc.base.wacc_nominal:.2%}')

print('\n✅ Integration test PASSED')
"
```

### C3. Verify KPI Accuracy

Check that:
- Tax calculations match Phase 1-2 test values
- WACC matches expected CAPM formula
- NPV/IRR use correct discount rate
- Final KPIs are reasonable

### C4. Test Backward Compatibility

```bash
# Run with old configuration (no tax, default WACC)
python -c "
config = {
    'tax': {'tax_rate': 0},  # No tax
    'wacc': {},  # Use defaults
}

# Should still work
rows = build_annual_rows(config, {})
print('✓ Backward compatible: works with old config')
"
```

---

## Success Checklist

### After Phase 1 Integration
- [ ] `build_annual_rows()` uses `TaxProfile`
- [ ] Tax calculation includes interest deductibility
- [ ] Depreciation schedule properly applied
- [ ] Post-tax CFADS calculated correctly
- [ ] Phase 1-2 tests still pass (14/14)

### After Phase 2 Integration
- [ ] `initialize_wacc()` function working
- [ ] WACC calculated at model start
- [ ] KPI functions use WACC as discount rate
- [ ] NPV/IRR calculations use correct rate
- [ ] Phase 1-2 tests still pass (14/14)

### Overall
- [ ] End-to-end pipeline runs successfully
- [ ] Sample scenario produces reasonable KPIs
- [ ] Backward compatibility maintained
- [ ] All tests pass

---

## Troubleshooting

### If tax calculation fails:
```python
# Check that interest expense is being extracted correctly
print("Interest series:", interest_expense_lkr)
print("Tax profile:", tax_profile)
print("Depreciation:", depreciation_schedule)
```

### If WACC fails:
```python
# Verify all inputs are present
print("Risk free rate:", risk_free_rate)
print("Market risk premium:", market_risk_premium)
print("Asset beta:", asset_beta)
print("Tax rate:", tax_rate)
```

### If tests fail:
```bash
# Run with full traceback
pytest tests/test_phase_1_2_refactoring.py -v --tb=long

# Run specific test
pytest tests/test_phase_1_2_refactoring.py::TestPhase1TaxProfile::test_calculate_tax_basic -v
```

---

## Next Steps After Integration

1. **Today (after integration works)**:
   - Commit integration changes
   - Tag release: `v1.2-integration`
   - Update documentation

2. **Tomorrow (legacy cleanup)**:
   - Fix remaining mypy issues
   - Fix legacy test imports
   - Run full test suite
   - Deploy to production

---

**Start time**: Now
**Estimated duration**: 2-3 hours
**Target completion**: Tonight
