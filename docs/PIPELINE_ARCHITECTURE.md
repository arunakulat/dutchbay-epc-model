# DutchBay Pipeline Architecture

## Overview

The DutchBay codebase has **two distinct pipelines** with different purposes:

1. **Lender-Grade Pipeline** (`analytics/pipeline_v14_enhanced.py`) - **CANONICAL**
2. **Wind-Only Pipeline** (`analytics/pipeline_v14.py`) - **LEGACY**

This document clarifies which to use when, and why they exist separately.

---

## 🎯 **Canonical Entry Point**

### **`run_full_pipeline_v14.py`** (Root CLI)

**Status**: ✅ **PRODUCTION - LENDER-GRADE**

**Imports**:
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline
```

**Runs**:
- ✅ Wind resource assessment (optional)
- ✅ **Cashflow model** (`finance.cashflow_v14.build_annual_rows`)
- ✅ **Debt structuring** (`finance.debt_v14.plan_debt`)
- ✅ **KPI calculation** (DSCR, LLCR, PLCR, IRR, NPV)
- ✅ **WACC computation**
- ✅ **ScenarioResult contract** (CASPER-compliant)

**Output Structure**:
```json
{
  "status": "success",
  "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
  "scenario_result": {
    "project_irr": 0.145,
    "min_dscr": 1.45,
    "dscr_series": [1.5, 1.6, ...],
    ...
  },
  "kpis": {
    "project_irr": 0.145,
    "equity_irr": 0.185,
    "min_dscr": 1.45,
    "llcr": 1.85,
    "plcr": 2.10,
    ...
  },
  "annual_rows": [
    {"year": 1, "cf_pre_debt": 15000000, ...},
    ...
  ],
  "debt_result": {
    "min_dscr": 1.45,
    "dscr_series": [1.5, 1.6, ...],
    ...
  }
}
```

**Usage**:
```bash
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
```

**Protected By**: `tests/api/test_run_full_pipeline_v14_lender_stack.py` (golden test)

---

## 📊 **Pipeline Comparison**

| Feature | Lender-Grade<br>`pipeline_v14_enhanced` | Wind-Only<br>`pipeline_v14` |
|---------|----------------------------------------|-----------------------------|
| **Status** | ✅ PRODUCTION CANONICAL | ⚠️ LEGACY (wind teams only) |
| **Wind Assessment** | Optional | ✅ Primary focus |
| **Cashflow Model** | ✅ `build_annual_rows()` | ❌ Missing |
| **Debt Structuring** | ✅ `plan_debt()` | ❌ Missing |
| **KPI Calculation** | ✅ DSCR/LLCR/PLCR/IRR/NPV | ❌ Missing |
| **WACC** | ✅ Computed | ❌ Missing |
| **Output Contract** | `ScenarioResult` | Wind data dict |
| **Lender Requirements** | ✅ Fully met | ❌ Incomplete |
| **Use For** | Financial analysis, MC, sensitivity | Wind resource studies only |

---

## 🔧 **Module Details**

### **1. Lender-Grade Pipeline** ⭐ **USE THIS**

**File**: `analytics/pipeline_v14_enhanced.py`

**Function**: `run_v14_pipeline_enhanced(config, validation_mode='strict', ...)`

**Alias**: `run_v14_pipeline` (for compatibility)

**What It Does**:
1. **Phase 1**: Config loading & schema validation
2. **Phase 2**: Cashflow engine (`build_annual_rows`)
3. **Phase 3**: Debt engine (`plan_debt`)
4. **Phase 4**: KPI & WACC calculation
5. **Phase 5**: `ScenarioResult` assembly (CASPER contract)
6. **Phase 6**: Final result packaging with metrics

**Returns**:
```python
{
  "status": "success",
  "scenario_result": ScenarioResult(...),  # CASPER contract
  "kpis": dict,                             # All metrics
  "annual_rows": list[dict],                # Cashflow schedule
  "debt_result": dict,                      # DSCR series, debt details
  "metrics": PipelineMetrics(...),          # Execution metrics
}
```

**When to Use**:
- ✅ Lender presentations
- ✅ Financial analysis
- ✅ Monte Carlo simulation
- ✅ Sensitivity analysis
- ✅ Optimization
- ✅ Any scenario requiring IRR/NPV/DSCR

**Import**:
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline

result = run_v14_pipeline(
    config="scenarios/base.yaml",
    validation_mode="strict"
)

print(f"Project IRR: {result['kpis']['project_irr']:.2%}")
print(f"Min DSCR: {result['debt_result']['min_dscr']:.2f}")
```

---

### **2. Wind-Only Pipeline** ⚠️ **LEGACY - LIMITED USE**

**File**: `analytics/pipeline_v14.py`

**Function**: `run_v14_pipeline(config, validation_mode='strict', ...)`

**What It Does**:
1. Schema validation (optional)
2. Wind resource assessment (ERA5 fetcher, Weibull, AEP)
3. Cashflow export (revenue approximation only)
4. **STOPS HERE** - no financial modeling

**Returns**:
```python
{
  "status": "success",
  "wind_assessment": {...},
  "aep_p50_mwh": 300000,
  "aep_p75_mwh": 280000,
  "capacity_factor_net_p75": 0.336,
  "revenue_annual_p75_usd": 19430000,  # Approximation only
  # ❌ NO annual_rows
  # ❌ NO debt_result
  # ❌ NO kpis
}
```

**When to Use**:
- ✅ Wind resource studies (turbine selection, layout)
- ✅ Quick AEP estimates
- ✅ Capacity factor analysis
- ❌ **NOT for lender presentations**
- ❌ **NOT for financial analysis**
- ❌ **NOT for MC/sensitivity**

**Import**:
```python
# Only for wind-focused analysis
from analytics.pipeline_v14 import run_v14_pipeline

result = run_v14_pipeline(
    config="scenarios/wind_study.yaml",
    validation_mode="off"  # Faster for wind-only
)

print(f"AEP P75: {result['aep_p75_mwh']:,.0f} MWh/year")
print(f"Net CF: {result['capacity_factor_net_p75']:.1f}%")
```

---

## 🚨 **Common Mistake: Wrong Pipeline Import**

### **WRONG** ❌
```python
# run_full_pipeline_v14.py (BEFORE FIX)
from analytics.pipeline_v14 import run_v14_pipeline  # ❌ WIND-ONLY

# Result: CLI promises "Wind-to-Finance" but delivers wind-only
# Missing: annual_rows, debt_result, kpis, scenario_result
```

### **CORRECT** ✅
```python
# run_full_pipeline_v14.py (AFTER FIX)
from analytics.pipeline_v14_enhanced import run_v14_pipeline  # ✅ LENDER-GRADE

# Result: Full lender stack with all metrics
# Includes: annual_rows, debt_result, kpis, scenario_result
```

**Protected By**: Golden test prevents regression:
- `tests/api/test_run_full_pipeline_v14_lender_stack.py`
- Asserts `annual_rows`, `debt_result`, `kpis` are present
- Fails fast if CLI gets rewired to wind-only

---

## 🎓 **Architectural Principles**

### **1. GWTF: Single Canonical Evaluation Gateway**

**Rule**: All analytics modules must call `pipeline_v14_enhanced.run_v14_pipeline()`

**Why**: Prevents:
- Direct imports of `finance.cashflow_v14`, `finance.debt_v14`
- Inconsistent evaluation patterns
- Version drift (v14 vs v14_enhanced vs legacy)

**Examples**:

✅ **CORRECT** (use gateway):
```python
# analytics/sensitivity_v14.py
from analytics.pipeline_v14_enhanced import run_v14_pipeline

def analyze_parameter(config, param):
    # Evaluate via gateway
    result = run_v14_pipeline(config)
    kpis = result['kpis']
    return kpis['project_irr']
```

❌ **WRONG** (direct import):
```python
# analytics/sensitivity_v14.py
from finance.cashflow_v14 import build_annual_rows  # ❌ Direct import
from finance.debt_v14 import plan_debt              # ❌ Bypasses gateway

def analyze_parameter(config, param):
    annual_rows = build_annual_rows(config)  # ❌ No validation
    debt_result = plan_debt(annual_rows, config)  # ❌ Inconsistent
    # ...
```

### **2. NO REGRESSION: Preserve Wind-Only for Backwards Compat**

**Rationale**:
- Wind teams may rely on `pipeline_v14.py` for quick AEP estimates
- Breaking their workflow would violate NO REGRESSION rule
- Solution: Keep wind-only pipeline, but document it as "limited use"

**Migration Path**:
1. ✅ `run_full_pipeline_v14.py` → Uses lender-grade (DONE)
2. ⏸️ Wind teams notified of lender-grade pipeline benefits
3. ⏸️ Optional: Create explicit `run_wind_assessment.py` CLI
4. ⏸️ Eventually deprecate `pipeline_v14.py` (far future)

### **3. CLEAR NAMING: Enhanced vs Wind-Only vs Legacy**

**Naming Convention**:
- `*_v14_enhanced.py` → Production-grade with full lender stack
- `*_v14.py` → Legacy or specialized (wind-only, old contracts)
- `*_v14_legacy.py` → Explicitly marked deprecated

**Examples**:
- `pipeline_v14_enhanced.py` → ✅ Lender-grade
- `pipeline_v14.py` → ⚠️ Wind-only (legacy)
- `monte_carlo_v14_enhanced.py` → ✅ Production MC
- `monte_carlo_v14.py` → ⚠️ Basic MC (legacy)

---

## 🔍 **How to Check Which Pipeline You're Using**

### **Method 1: Check Imports**
```python
# In your module:
import analytics.pipeline_v14_enhanced  # ✅ Lender-grade
import analytics.pipeline_v14           # ⚠️ Wind-only
```

### **Method 2: Check Output Keys**
```python
result = run_v14_pipeline(config)

if "annual_rows" in result and "debt_result" in result:
    print("✅ Using lender-grade pipeline")
else:
    print("⚠️ Using wind-only pipeline")
```

### **Method 3: Run Golden Test**
```bash
pytest tests/api/test_run_full_pipeline_v14_lender_stack.py -v

# If tests pass → CLI is correctly wired to lender-grade
# If tests fail → CLI is wired to wind-only (FIX IMMEDIATELY)
```

---

## 📚 **Usage Examples**

### **Example 1: Lender Presentation Analysis**
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline

result = run_v14_pipeline(
    config="scenarios/dutchbay_lendercase_2025Q4.yaml",
    validation_mode="strict",
    enable_monitoring=True
)

# Extract lender metrics
project_irr = result['kpis']['project_irr']
equity_irr = result['kpis']['equity_irr']
min_dscr = result['debt_result']['min_dscr']
llcr = result['kpis']['llcr']

print(f"Project IRR: {project_irr:.2%}")
print(f"Equity IRR: {equity_irr:.2%}")
print(f"Min DSCR: {min_dscr:.2f}")
print(f"LLCR: {llcr:.2f}")

# Export cashflow schedule
import pandas as pd
df = pd.DataFrame(result['annual_rows'])
df.to_excel("outputs/cashflow_schedule.xlsx", index=False)
```

### **Example 2: Monte Carlo Simulation**
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.monte_carlo_v14_enhanced import run_monte_carlo

# Monte Carlo MUST use lender-grade pipeline
mc_result = run_monte_carlo(
    base_config="scenarios/base.yaml",
    distributions=[
        MonteCarloDistribution("capex_total", "triangular", 180e6, 200e6, 220e6),
        MonteCarloDistribution("tariff_rate", "triangular", 0.072, 0.08, 0.088),
    ],
    n_iterations=10000,
    evaluation_gateway=run_v14_pipeline  # ✅ Explicitly use lender-grade
)

print(f"Project IRR P50: {mc_result['project_irr_p50']:.2%}")
print(f"Min DSCR P10: {mc_result['min_dscr_p10']:.2f}")
```

### **Example 3: Sensitivity Analysis**
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.sensitivity_v14 import run_tornado_sensitivity

# Sensitivity MUST use lender-grade pipeline
suite = run_tornado_sensitivity(
    base_config="scenarios/base.yaml",
    parameters=[
        ParameterRangeConfig("capex_total", 200e6, -0.1, 0.1),
        ParameterRangeConfig("tariff_rate", 0.08, -0.1, 0.1),
    ],
    metric="project_irr"
)

# Tornado chart will show correct IRR sensitivity
# (because it uses lender-grade pipeline internally)
```

### **Example 4: Wind Assessment Only** (Legacy Use)
```python
from analytics.pipeline_v14 import run_v14_pipeline as run_wind_pipeline

# Only for wind-focused studies
result = run_wind_pipeline(
    config="scenarios/wind_study.yaml",
    validation_mode="off"  # Faster
)

print(f"AEP P50: {result['aep_p50_mwh']:,.0f} MWh/year")
print(f"AEP P75: {result['aep_p75_mwh']:,.0f} MWh/year")
print(f"Gross CF: {result['wind_assessment']['energy_production']['gross_aep']['capacity_factor_gross']:.1f}%")

# ⚠️ DO NOT use this for financial analysis
# ⚠️ NO annual_rows, debt_result, or kpis available
```

---

## 🛡️ **Regression Protection**

### **Golden Test: `test_run_full_pipeline_v14_lender_stack.py`**

**Purpose**: Prevent future rewiring mistakes

**What It Checks**:
1. ✅ CLI output contains `annual_rows`
2. ✅ CLI output contains `debt_result`
3. ✅ CLI output contains `kpis`
4. ✅ CLI output contains `scenario_result`
5. ✅ All lender-critical keys present
6. ✅ Output quality (DSCR series length, IRR reasonableness)

**If This Test Fails**:
- Someone changed `run_full_pipeline_v14.py` import back to `pipeline_v14`
- Or `pipeline_v14_enhanced` broke its contract
- Or lender stack modules regressed

**Run It**:
```bash
pytest tests/api/test_run_full_pipeline_v14_lender_stack.py -v

# Expected output:
# ✅ test_cli_output_has_annual_rows PASSED
# ✅ test_cli_output_has_debt_result PASSED
# ✅ test_cli_output_has_kpis PASSED
# ✅ test_cli_output_has_scenario_result PASSED
# ✅ test_cli_output_has_all_lender_keys PASSED
```

---

## 🚀 **Migration Guide**

### **If You're Currently Using `pipeline_v14.py`**

**Step 1**: Check if you need lender metrics
- If YES (IRR/NPV/DSCR) → Migrate to `pipeline_v14_enhanced`
- If NO (AEP/CF only) → Continue using `pipeline_v14` (but consider migration)

**Step 2**: Update imports
```python
# BEFORE
from analytics.pipeline_v14 import run_v14_pipeline

# AFTER
from analytics.pipeline_v14_enhanced import run_v14_pipeline
```

**Step 3**: Update assertions (if any)
```python
# BEFORE (wind-only)
assert "aep_p75_mwh" in result

# AFTER (lender-grade)
assert "annual_rows" in result
assert "debt_result" in result
assert "kpis" in result
```

**Step 4**: Test thoroughly
```bash
pytest tests/ -v -k "your_test"
```

---

## 📊 **Summary Table**

| Scenario | Pipeline to Use | Rationale |
|----------|----------------|----------|
| **Lender presentation** | `pipeline_v14_enhanced` | Need DSCR, IRR, NPV, LLCR |
| **Financial analysis** | `pipeline_v14_enhanced` | Need annual_rows, debt_result |
| **Monte Carlo** | `pipeline_v14_enhanced` | Must sample IRR/DSCR |
| **Sensitivity analysis** | `pipeline_v14_enhanced` | Must vary IRR/DSCR |
| **Optimization** | `pipeline_v14_enhanced` | Must maximize IRR/minimize DSCR |
| **Wind resource study** | `pipeline_v14` (legacy) | AEP/CF only, no finance needed |
| **Quick AEP estimate** | `pipeline_v14` (legacy) | Fast execution, wind-only |

---

## 📝 **Key Takeaways**

1. **✅ USE `pipeline_v14_enhanced` for everything financial**
2. **⚠️ AVOID `pipeline_v14` unless wind-only is explicitly needed**
3. **🛡️ Golden test protects canonical CLI from rewiring**
4. **🎯 One canonical evaluation gateway (GWTF compliance)**
5. **🔄 NO REGRESSION: Wind-only preserved for backwards compat**

---

**Last Updated**: December 22, 2025  
**Branch**: `feature/add-finance-contracts-pydantic-v2-20251219`  
**Author**: Dutch Bay Wind Farm Team
