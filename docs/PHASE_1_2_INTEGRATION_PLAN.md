# Phase 1-2 Integration Plan

**Status**: Ready for execution
**Date**: December 13, 2025 | 9:00 PM IST
**Objective**: Wire tax layer and WACC into main financial model

---

## Overview

Phase 1-2 integration involves three main steps:

1. **Phase 1 Integration** (Tax Layer)
   - Replace old tax calculation in `cashflow_v14.py` with new `TaxProfile`
   - Wire interest from debt module
   - Update annual row calculations with deductible interest

2. **Phase 2 Integration** (WACC)
   - Calculate WACC at model initialization
   - Replace hardcoded discount rates with WACC
   - Wire into NPV/IRR calculations

3. **Testing & Validation**
   - Run end-to-end pipeline
   - Verify KPI calculations
   - Confirm backward compatibility

---

## Phase 1: Tax Layer Integration

### Step 1.1: Locate Current Tax Calculation

**File**: `finance/cashflow/cashflow_v14.py`

**Current behavior**:
```python
# Old approach: simple tax calculation
tax_lkr = taxable_income_lkr * tax_rate
```

**New approach**: Use `TaxProfile` and `build_tax_series()`

### Step 1.2: Import Phase 1 Components

**In `finance/cashflow/cashflow_v14.py`, add**:

```python
from finance.tax_profile import (
    TaxProfile,
    DepreciationSchedule,
    build_tax_series,
)
```

### Step 1.3: Create TaxProfile from Config

**In main calculation function**:

```python
def build_annual_rows(
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],  # From debt_v14
    # ... other params
) -> List[Dict[str, float]]:

    # Extract tax config
    tax_config = config.get("tax", {})

    # Create TaxProfile
    tax_profile = TaxProfile(
        tax_rate=float(tax_config.get("tax_rate", 0.25)),
        interest_deductible=bool(tax_config.get("interest_deductible", True)),
        depreciation_method=tax_config.get("depreciation_method", "straight_line"),
        asset_base=float(config.get("capex", {}).get("usd_total", 0.0)),
        depreciation_years=int(tax_config.get("depreciation_years", 20)),
        tax_holiday_years=int(tax_config.get("tax_holiday_years", 0)),
    )

    # Build depreciation schedule
    depreciation_schedule = DepreciationSchedule(
        method=tax_profile.depreciation_method,
        asset_base=tax_profile.asset_base,
        years=tax_profile.depreciation_years,
    )

    # ... rest of calculation
```

### Step 1.4: Calculate Interest Expense

**From debt module**:

```python
# debt_result comes from debt_v14.plan_debt()
annual_interest_usd = debt_result.get("interest_expense_series", [])

# Convert to LKR using FX curve
fx_rate = config.get("fx", {}).get("base_rate", 300.0)
annual_interest_lkr = [amt * fx_rate for amt in annual_interest_usd]
```

### Step 1.5: Build Tax Series

**For each year in the model**:

```python
# Build tax series
tax_series = build_tax_series(
    tax_profile=tax_profile,
    taxable_income_series=taxable_income_lkr,  # EBIT
    interest_expense_series=annual_interest_lkr,
    depreciation_schedule=depreciation_schedule,
    years=len(annual_rows),
)

# Extract results for each row
for idx, tax_result in enumerate(tax_series):
    annual_rows[idx]["tax_lkr"] = tax_result.tax_liability
    annual_rows[idx]["interest_expense_lkr"] = annual_interest_lkr[idx]
    annual_rows[idx]["depreciation_lkr"] = tax_result.depreciation
    annual_rows[idx]["taxable_income_lkr"] = tax_result.taxable_income
```

### Step 1.6: Update Post-Tax CFADS

**Calculate final CFADS**:

```python
# Post-tax CFADS = Pretax CFADS - Tax
for idx in range(len(annual_rows)):
    pretax_cfads = annual_rows[idx]["pretax_cfads_lkr"]
    tax = annual_rows[idx]["tax_lkr"]
    annual_rows[idx]["posttax_cfads_lkr"] = pretax_cfads - tax
```

---

## Phase 2: WACC Integration

### Step 2.1: Locate Current Discount Rate

**Files involved**:
- `finance/equity/irr.py` - uses hardcoded discount rate
- `analytics/evaluation_v14.py` - NPV calculations
- KPI calculators - use fixed 10% rate

**Current approach**: `DEFAULT_DISCOUNT_RATE = 0.10`

### Step 2.2: Calculate WACC at Model Initialization

**New file or existing orchestrator**:

```python
from finance.wacc_integration import (
    WaccComponents,
    WaccResult,
    calculate_wacc,
)

def initialize_wacc(
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
) -> WaccResult:
    """
    Calculate WACC once at model start using Phase 2 engine.
    """

    # Extract WACC inputs from config
    wacc_config = config.get("wacc", {})
    financing_config = config.get("financing", {})

    # Debt metrics from debt engine
    total_debt = float(debt_result.get("total_debt_usd", 0.0))

    # Equity metrics (use Phase 1-2 to calculate)
    # ... (will come from equity module)

    # Calculate WACC
    wacc_result = calculate_wacc(
        risk_free_rate=float(wacc_config.get("risk_free_rate", 0.05)),
        market_risk_premium=float(wacc_config.get("market_risk_premium", 0.06)),
        asset_beta=float(wacc_config.get("asset_beta", 0.8)),
        target_debt_to_value=float(wacc_config.get("target_debt_to_value", 0.6)),
        tax_rate=float(config.get("tax", {}).get("tax_rate", 0.25)),
        cost_of_debt=float(debt_result.get("avg_cost_of_debt", 0.06)),
        inflation_rate=float(wacc_config.get("inflation_rate", 0.04)),
    )

    return wacc_result
```

### Step 2.3: Replace Hardcoded Discount Rates

**In equity IRR/NPV calculations**:

```python
# OLD
DISCOUNT_RATE = 0.10  # hardcoded

# NEW
def calculate_equity_irr(
    cashflows: Sequence[float],
    discount_rate: Optional[float] = None,
) -> Optional[float]:
    """
    If discount_rate is None, use WACC from model initialization.
    """
    if discount_rate is None:
        # Retrieve from model state / config
        discount_rate = get_model_wacc().wacc_nominal

    return _irr(cashflows, discount_rate)
```

### Step 2.4: Wire WACC into KPI Calculations

**Update KPI functions**:

```python
from analytics.core.metrics import KPICalculator

def calculate_kpis(
    wacc_result: WaccResult,
    equity_cashflows: List[float],
    project_cashflows: List[float],
) -> Dict[str, float]:
    """
    Calculate all KPIs using WACC.
    """

    discount_rate = wacc_result.base.wacc_nominal

    return {
        "equity_irr": calculate_equity_irr(equity_cashflows, discount_rate),
        "project_irr": calculate_project_irr(project_cashflows, discount_rate),
        "equity_npv": calculate_equity_npv(equity_cashflows, discount_rate),
        "project_npv": calculate_project_npv(project_cashflows, discount_rate),
        "moic": calculate_moic(...),
        "wacc": discount_rate,
    }
```

---

## Integration Checklist

### Phase 1: Tax Layer
- [ ] Import `TaxProfile`, `DepreciationSchedule`, `build_tax_series` in `cashflow_v14.py`
- [ ] Extract tax config from input config
- [ ] Create `TaxProfile` instance
- [ ] Integrate interest from debt module
- [ ] Call `build_tax_series()` for all periods
- [ ] Update `annual_rows` with tax results
- [ ] Update CFADS calculation
- [ ] Test with sample scenario

### Phase 2: WACC
- [ ] Import `WaccResult`, `calculate_wacc` in orchestrator
- [ ] Create `initialize_wacc()` function
- [ ] Calculate WACC at model start
- [ ] Replace hardcoded `DEFAULT_DISCOUNT_RATE`
- [ ] Update equity IRR/NPV to use WACC
- [ ] Update KPI calculators
- [ ] Wire WACC into all discount rate usages
- [ ] Test with sample scenario

### Testing & Validation
- [ ] Run end-to-end pipeline with test scenario
- [ ] Verify tax calculations match Phase 1-2 tests
- [ ] Verify WACC calculations match Phase 2 tests
- [ ] Check backward compatibility (zero tax, old WACC)
- [ ] Validate KPI calculations
- [ ] Run full test suite

---

## Files to Modify

### Core Integration Files

1. **`finance/cashflow/cashflow_v14.py`**
   - Import Phase 1 components
   - Integrate tax calculation
   - Wire interest expense

2. **`finance/equity/equity_v14.py` or orchestrator**
   - Import Phase 2 components
   - Calculate WACC
   - Replace discount rate usages

3. **`analytics/core/metrics.py` or KPI module**
   - Update KPI calculations
   - Wire WACC into discount rates

### Supporting Files

4. **`analytics/orchestrators/scenario_analytics.py` or main runner**
   - Initialize WACC
   - Pass to all downstream functions

---

## Expected Outcomes

### After Phase 1 Integration
✅ Tax layer properly calculates taxable income with interest deductibility
✅ Depreciation schedule correctly applied
✅ Tax holiday periods honored
✅ Loss carryforward logic working
✅ Post-tax CFADS calculated accurately

### After Phase 2 Integration
✅ WACC calculated using CAPM formula
✅ Both nominal and real WACC available
✅ Prudential WACC (with haircut) calculated
✅ All NPV/IRR calculations use model WACC
✅ KPIs reflect correct discount rate

### Overall
✅ Phase 1-2 tests continue to pass (14/14)
✅ End-to-end pipeline works
✅ Backward compatible (old configs still work)
✅ Production-ready for deployment

---

## Success Metrics

1. **Code Quality**
   - [ ] All Phase 1-2 tests pass
   - [ ] No new import errors
   - [ ] Tax and WACC calculations verified

2. **Financial Accuracy**
   - [ ] Tax calculations match expected values
   - [ ] WACC matches CAPM formula
   - [ ] NPV/IRR calculations consistent

3. **Integration**
   - [ ] Cashflow engine uses new tax layer
   - [ ] KPI calculations use new WACC
   - [ ] All downstream functions working

4. **Testing**
   - [ ] Sample scenario runs end-to-end
   - [ ] KPIs match expected ranges
   - [ ] Backward compatibility verified

---

## Next Steps

1. **Immediate** (Next 1-2 hours)
   - Implement Phase 1 integration in `cashflow_v14.py`
   - Test with sample scenario
   - Verify tax calculations

2. **Short-term** (Next 2-3 hours)
   - Implement Phase 2 integration in KPI/equity modules
   - Wire WACC into all discount rate usages
   - Test end-to-end pipeline

3. **Follow-up** (Later today)
   - Run full test suite
   - Fix remaining mypy/pytest issues from legacy code
   - Prepare for production deployment

---

**Status**: Ready to begin integration
**Owner**: You (Aruna)
**Estimated time**: 2-3 hours for both phases
**Target completion**: Tonight
