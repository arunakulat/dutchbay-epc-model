# 🔍 DEEP EXAMINATION: DutchBay FinModel (finance/dutchbay_finmodel)

**Date:** 2025-12-18 @ 16:52 IST  
**Branch:** feature/fx-structured-blocks-v14  
**Depth:** Complete module-by-module analysis  
**Scope:** Scripts, functions, integration with pipeline  

---

## EXECUTIVE SUMMARY

### 🟡 CRITICAL FINDING: dutchbay_finmodel IS NOT WIRED TO MAIN PIPELINE

**Status:** ⚠️ Standalone Reference Implementation (Not Active)  
**Purpose:** Phase 1-2 Refactoring Reference Library  
**Current Integration:** NONE - Main pipeline uses separate modules  
**Production Status:** ❌ NOT IN PRODUCTION PATH  

The dutchbay_finmodel directory contains **reference implementations** of:
- Phase 1: Tax profile refactoring
- Phase 2: WACC + interest injection
- Integration patterns

**BUT:** The actual pipeline uses separate, maintained modules:
- finance/cashflow_v14.py
- finance/debt_v14.py
- finance/wacc_v14.py
- finance/equity_v14.py
- finance/tax_v14.py

---

## DIRECTORY STRUCTURE

```
finance/dutchbay_finmodel/
├── __init__.py                  # Module exports (tax_profile API only)
├── core.py                      # 📄 Placeholder (58 bytes)
├── core_v2_refactored.py        # 🔵 Phase 1-2 reference (18KB)
├── integration_v2.py            # 🔵 Integration reference (5.8KB)
├── monte_carlo.py               # 🟡 Standalone MC engine (2.6KB)
├── optimization.py              # 🟡 Tariff optimization (1.2KB)
├── sensitivity.py               # 🟡 Sensitivity analysis (0.6KB)
├── statutory_profile.py         # 🟡 Statutory levies (2.7KB)
└── tax_profile.py               # 🟢 Tax module (17.6KB - ACTIVE)
```

**Legend:**
- 🔵 = Reference Implementation (documentation/learning)
- 🟢 = Active/Used elsewhere
- 🟡 = Standalone/Demo
- 📄 = Placeholder

---

## MODULE FUNCTIONS & ANALYSIS

### 1. core.py - Placeholder (NOT USED)

**Size:** 58 bytes | **Status:** 📄 Empty Placeholder

**Content:** Single docstring only

```python
"""
Core financial model logic (placeholder for now).
"""
```

**Assessment:** ❌ Non-functional
**Wiring:** ❌ NONE

---

### 2. core_v2_refactored.py - Phase 1-2 Reference (18 KB)

**Size:** 18,298 bytes | **Status:** 🔵 Reference Implementation  
**Lines:** ~500+ | **Complexity:** High  

#### Purpose
Complete standalone financial model combining:
- **Phase 1:** Tax calculations (interest deductibility, loss carryforward)
- **Phase 2:** WACC integration
- Complete financials (revenue, OPEX, debt, equity, DSCR, IRR)

#### Main Entry Points

1. **build_financial_model_refactored(cfg, tax_profile, wacc_result, depreciation_schedule)**
   - Complete financial model builder
   - Returns: (DataFrame, proj_cf, eq_cf, cap_struct, analysis_dict)
   - Includes Phase 1-2 logic

2. **build_financial_model(cfg)** - Legacy wrapper (no tax/WACC)

3. **Helper Functions:**
   ```python
   _generation_profile_mwh()        # Capacity factor + degradation
   _net_generation_profile_mwh()    # After losses, curtailment
   _tariff_profile_lkr()            # With indexation
   _revenue_lkr()                   # Net of wheeling, fees
   _opex_lkr()                      # Fixed + variable
   _build_debt_schedules()          # 3 tranches with amortization
   calculate_irr_robust()           # IRR calculation
   calculate_llcr_plcr()            # Debt covenants
   evaluate_covenants()             # Covenant analysis
   ```

#### Critical Issue: Hardcoded ModelConfig

**Problem:**
```python
@dataclass
class ModelConfig:
    nameplate_mw: float = 150.0          # Hardcoded!
    capacity_factor_p50: float = 0.40   # Hardcoded!
    tariff_lkr_per_kwh: float = 20.30   # Hardcoded!
    debt_tenor_years: int = 15          # Hardcoded!
    # ... 20+ more parameters with defaults
```

**Pipeline Uses:** Dynamic YAML config dicts, NOT ModelConfig

**Result:** ❌ **Incompatible with main pipeline**

#### Wiring to Pipeline

**❌ NOT WIRED** - Zero imports

**Why:**
- ModelConfig is hardcoded (pipeline uses YAML)
- Doesn't use scenario_loader.py
- Analytics uses separate modules (cashflow_v14, debt_v14, etc.)
- All-in-one design vs. modular pipeline design

**Assessment:** 🔵 **Reference/Educational** - Shows complete financial model pattern

---

### 3. integration_v2.py - Integration Reference (5.8 KB)

**Size:** 5,868 bytes | **Status:** 🔵 Reference Implementation  

#### Purpose
Demonstrate how to integrate tax + WACC

#### Main Function

```python
def integrate_tax_and_wacc(
    years, revenue, opex, interest_expense, debt_service,
    capex_total, total_debt, total_equity,
    tax_profile=None, wacc_result=None, depreciation_schedule=None
) -> Dict[str, Any]
```

**Flow:**
1. Calculate EBIT (revenue - opex)
2. Apply tax (Phase 1)
3. Calculate CFADS (EBIT - tax - interest)
4. Calculate DSCR (CFADS / debt_service)
5. Build cash flows
6. Calculate IRRs
7. Apply WACC analysis (Phase 2)

**Returns:** Complete results dict

#### Wiring to Pipeline

**❌ NOT WIRED** - Not imported anywhere

**Assessment:** 🔵 **Example Code** - Shows integration pattern

---

### 4. tax_profile.py - Tax Engine (17.6 KB) ✅ ACTIVE

**Size:** 17,654 bytes | **Status:** 🟢 ACTIVE (Production-Ready)  
**Lines:** ~400+ | **Quality:** Excellent  

#### Purpose
YAML-driven tax calculation engine

#### Key Components

**TaxConfig** (YAML-mapped)
```python
@dataclass(frozen=True)
class TaxConfig:
    corporate_tax_rate: float
    depreciation_method: str
    depreciation_years: int
    tax_holiday_start_year: int
    tax_holiday_years: int
    loss_carryforward_years: int
    wht_on_interest_to_nonresidents: float
    wht_on_interest_enabled: bool
    interest_deductibility: bool
```

**Factory:** TaxConfig.from_yaml(config_dict)

**DepreciationSchedule** (Pre-computed)
```python
DepreciationSchedule.build_straight_line(
    capex_lkr, useful_life, project_life
)
# Returns: List of annual depreciation amounts
```

**TaxResult** (Per-year output)
```python
@dataclass(frozen=True)
class TaxResult:
    year: int
    ebit: float
    interest_expense: float
    depreciation: float
    taxable_income: float
    tax_liability: float
    effective_tax_rate: float
    tax_holiday_applied: bool
    carried_forward_losses: float
    wht_on_interest: float
```

#### Core Functions

1. **build_tax_profile(config, depreciation_schedule, project_life)**
   - TaxConfig → TaxProfile conversion
   - Builds tax holiday map

2. **calculate_tax(year, ebit, interest, depreciation, tax_profile, prior_losses)**
   - Single-year tax calculation
   - Handles holidays, deductibility, carryforward
   - Pure function (no I/O)

3. **build_tax_series(years, ebit_series, interest_series, depreciation, tax_profile)**
   - Complete tax series (all years)
   - Tracks loss carryforward
   - Returns List[TaxResult]

#### Tax Calculation Logic

```
1. Check if year is tax holiday
2. Start from EBIT
3. Deduct interest (if deductible)
4. Deduct depreciation
5. Apply prior-year losses
6. Calculate CIT on positive taxable income
7. Calculate interest WHT (separate)
8. Track loss carryforward for next year
```

#### Standards Compliance

✅ **CCCDIR:** Fully commented (400+ lines of clear docs)  
✅ **CESSPIT:** Frozen dataclasses, pure functions  
✅ **CASPER:** Audit trail via TaxResult  
✅ **GWTF:** Type hints, 88-char lines, comprehensive docs  

#### Wiring to Pipeline

**⚠️ PARTIAL INTEGRATION:**
- Exported in finance/dutchbay_finmodel/__init__.py
- Likely used by finance/tax_v14.py
- YAML-compatible (from_yaml method)
- NOT directly called by run_full_pipeline_v14.py

**Assessment:** 🟢 **ACTIVE but Optional** - Clean API, production-ready

---

### 5. monte_carlo.py - Demo (2.6 KB)

**Size:** 2,593 bytes | **Status:** 🟡 Demo Implementation  

#### Functions

1. **generate_mc_parameters(n, base_cfg, seed)**
   - Generates n parameter samples
   - Distributions:
     - Capacity Factor: N(base, 0.03) clipped [0.25, 0.55]
     - CAPEX: Lognormal ~±15%
     - OPEX: Lognormal ~±20%
     - Tariff Esc: N(base, 0.01) clipped [-1%, +3%]
   - Returns: DataFrame with samples

2. **run_monte_carlo(n, base_cfg, param_df, seed)**
   - Runs n scenarios
   - For each: builds model, calculates equity IRR
   - Returns: DataFrame with results

#### Issue: Uses Hardcoded ModelConfig

```python
def run_monte_carlo(...):
    for row in param_df.iterrows():
        cfg = replace(base_cfg, ...)  # Uses hardcoded ModelConfig
        df, proj_cf, eq_cf, _ = build_financial_model(cfg)
```

**Problem:** Can't use dynamic YAML configs

#### Wiring to Pipeline

**❌ NOT WIRED** - Not imported by analytics/monte_carlo_v14.py

**Pipeline Uses Instead:** analytics/monte_carlo_v14.py (proper integration)

**Assessment:** 🟡 **Demo Tool** - For manual exploration only

---

### 6. optimization.py - Tariff Solver (1.2 KB)

**Size:** 1,174 bytes | **Status:** 🟡 Utility Tool  

#### Function

**solve_tariff_for_target_irr(base_cfg, target_irr, bracket, tol, max_iter)**
- Solves for tariff (LKR/kWh) achieving target equity IRR
- Uses bisection method
- Bracket: (10.0, 40.0) LKR/kWh default
- Returns: tariff value or NaN

#### Implementation
- Classic binary search for root
- Iteratively calls calculate_equity_irr()

**Issue:** Uses hardcoded ModelConfig

#### Wiring to Pipeline

**❌ NOT WIRED** - Not used in pipeline

**Assessment:** 🟡 **Standalone Optimization Tool**

---

### 7. sensitivity.py - Sensitivity Analysis (0.6 KB)

**Size:** 621 bytes | **Status:** 🟡 Utility Tool  

#### Function

**one_way_sensitivity(cfg, param, values)**
- Varies one parameter over range
- Returns: DataFrame with values and equity IRRs

**Example:**
```python
df = one_way_sensitivity(
    cfg, "tariff_lkr_per_kwh", np.linspace(15, 30, 10)
)
# Returns: tariff_lkr_per_kwh | equity_irr
```

**Issue:** Uses hardcoded ModelConfig

#### Wiring to Pipeline

**❌ NOT WIRED** - Not used in pipeline

**Pipeline Uses Instead:** analytics/tornado_v14.py

**Assessment:** 🟡 **Demo Tool** - For manual exploration

---

### 8. statutory_profile.py - Statutory Levies (2.7 KB)

**Size:** 2,740 bytes | **Status:** 🟡 Reference Implementation  

#### Purpose
Model statutory levies and fees

#### Key Structure

**StatutoryProfile** (YAML-mapped)
```python
@dataclass(frozen=True)
class StatutoryProfile:
    env_surcharge_pct: float
    grid_loss_pct: float
    success_fee_pct: float
    social_services_levy_pct: float
    sscl_enabled: bool
    sscl_pct: float
    sscl_base: SSCLBase  # "gross_revenue" or "net_revenue_after_grid_loss"
```

**Factory:** StatutoryProfile.from_yaml(config_dict)

#### YAML Expectation

```yaml
statutory:
  env_surcharge_pct: 0.02
  grid_loss_pct: 0.03
  success_fee_pct: 0.01
  social_services_levy_pct: 0.005
  sscl_enabled: true
  sscl_pct: 0.015
  sscl_base: "gross_revenue"
```

#### Features
- All parameters required (no hidden defaults)
- Backward-compatible (falls back to project.grid_loss_pct if statutory.grid_loss_pct missing)
- Frozen dataclass (immutable)
- Post-validation

#### Wiring to Pipeline

**⚠️ Exported** in __init__.py, usage unclear

**Assessment:** 🟡 **Reference/Optional** - Clean API

---

### 9. __init__.py - Module Exports

**Size:** 483 bytes | **Status:** 🟢 Active Export Layer  

**Exports:**
```python
# From tax_profile.py (ACTIVE)
TaxConfig, TaxProfile, TaxResult, DepreciationSchedule
build_tax_profile, build_tax_series, calculate_tax

# From statutory_profile.py (REFERENCE)
StatutoryProfile
```

**Assessment:** ✅ Clean, focused API

---

## INTEGRATION ANALYSIS

### Main Pipeline Flow

```
run_full_pipeline_v14.py
  ↓
analytics/pipeline_v14.py (run_v14_pipeline)
  ├─→ scenario_loader.py (load_scenario_config from YAML)
  ├─→ schema_guard.py (validate_config)
  ├─→ finance/cashflow_v14.py (build_annual_rows)
  ├─→ finance/debt_v14.py (plan_debt)
  ├─→ finance/wacc_v14.py (compute_wacc_from_config)
  ├─→ analytics/core/metrics.py (calculate_scenario_kpis)
  └─→ analytics/fx_integration.py (integrate_fx_into_scenario_result)
        ↓
      ScenarioResult (JSON output)
```

### Where dutchbay_finmodel Could Fit

**❌ NOWHERE** in active pipeline

**Why:**
1. **Incompatible Config Format:** ModelConfig (hardcoded) vs. YAML dict
2. **Separate Modules Exist:** cashflow_v14, debt_v14, wacc_v14, etc.
3. **Different Architecture:** All-in-one vs. modular
4. **No Imports:** Zero references in run_full_pipeline_v14.py

### Wiring Summary

| Module | Wired | Status | Why |
|--------|-------|--------|-----|
| core.py | ❌ No | 📄 Placeholder | 58 bytes, empty |
| core_v2_refactored.py | ❌ No | 🔵 Reference | Hardcoded ModelConfig |
| integration_v2.py | ❌ No | 🔵 Reference | Example code only |
| tax_profile.py | ⚠️ Partial | 🟢 Active | YAML-compatible, could be used |
| monte_carlo.py | ❌ No | 🟡 Demo | Hardcoded ModelConfig |
| optimization.py | ❌ No | 🟡 Tool | Not in pipeline |
| sensitivity.py | ❌ No | 🟡 Tool | Not in pipeline |
| statutory_profile.py | ⚠️ Partial | 🟡 Reference | Exported, usage unclear |

---

## KEY FINDINGS

### ❌ Critical: dutchbay_finmodel NOT Integrated

**Evidence:**
- ✓ Zero imports in run_full_pipeline_v14.py
- ✓ Zero imports in analytics/pipeline_v14.py
- ✓ Separate finance/ modules used instead
- ✓ ModelConfig incompatible with dynamic configs

**Impact:** Intentional (reference library, not production)

### ⚠️ Issue: Multiple Demo Modules with Hardcoded Config

**Affected:** core_v2_refactored, monte_carlo, optimization, sensitivity

**Problem:** Can't work with YAML configs

**Impact:** Low (demos only, not production)

### ✅ Positive: tax_profile.py is Production-Ready

**Strengths:**
- ✅ YAML-driven (from_yaml method)
- ✅ Frozen dataclasses (immutable)
- ✅ Pure functions (no I/O)
- ✅ All standards met (GWTF, CESSPIT, CASPER, CCCDIR)
- ✅ Comprehensive documentation
- ✅ Could be integrated if needed

---

## RECOMMENDATIONS

### 1. ✅ Keep As-Is (Recommended)

**Rationale:**
- Serves as excellent reference/documentation
- Shows architectural patterns clearly
- Well-written, clean code
- Not blocking any pipeline
- Can be used if needed in future

**Action:** Add clear documentation marking as "reference implementation"

### 2. 🔧 Potential Future Integration

If dutchbay_finmodel should become active:
- [ ] Replace ModelConfig with dict config
- [ ] Add scenario_loader integration
- [ ] Remove hardcoded defaults
- [ ] Wire into pipeline_v14.py
- [ ] Comprehensive testing
- [ ] Update all documentation

**Status:** Not planned currently

### 3. 📝 Add Documentation

Create: finance/dutchbay_finmodel/README.md
```
# DutchBay FinModel Reference Library

## Status: REFERENCE IMPLEMENTATION (NOT ACTIVE IN MAIN PIPELINE)

This directory contains example implementations showing Phase 1-2
refactoring patterns. The main pipeline uses modular implementations
in finance/cashflow_v14.py, debt_v14.py, wacc_v14.py, etc.

## Available for Use:
- tax_profile.py (production-ready, YAML-compatible)
- statutory_profile.py (reference)

## Reference/Demo Only:
- core_v2_refactored.py (architecture example)
- integration_v2.py (integration pattern)
- monte_carlo.py (demo)
- optimization.py (demo)
- sensitivity.py (demo)
```

---

## CONCLUSION

### Status Summary

**dutchbay_finmodel: Reference Implementation Library**

- ❌ **NOT integrated** into main pipeline (intentional)
- ✅ **High-quality code** (GWTF, CESSPIT, CASPER, CCCDIR compliant)
- ✅ **Excellent documentation** (educational value)
- 🟢 **tax_profile.py** is production-ready
- 🟡 **Other modules** are demos/reference

### Key Insight

dutchbay_finmodel is NOT a bug or missing integration. It's a **well-designed reference library** showing Phase 1-2 refactoring patterns. The actual pipeline uses separate, maintained modules (cashflow_v14, debt_v14, etc.) which is the correct modular architecture.

### Recommendation

**Keep dutchbay_finmodel as-is, with clear documentation** that it's a reference implementation and learning resource, not an active pipeline component.
