# DutchBay Pipeline Architecture

**Canonical Reference for Pipeline Usage Patterns**

This document explains the DutchBay two-pipeline architecture, canonical evaluation surfaces, and correct usage patterns. Read this to avoid wiring errors and silent correctness bugs.

---

## 🎯 **Executive Summary**

**The Golden Rules**:
1. **Root CLI** (`run_full_pipeline_v14.py`) → Always uses lender-grade pipeline
2. **Evaluation Gateway** (`analytics.evaluation_v14`) → Always uses lender-grade pipeline
3. **All analytical engines** (sensitivity, MC, optimization) → Use evaluation gateway
4. **Wind-only assessment** → Use `analytics.pipeline_v14` explicitly

**Critical Insight**: We have TWO pipelines with different output contracts. Using the wrong one causes silent correctness bugs.

---

## 📊 **The Two-Pipeline Design**

### **Pipeline 1: Lender-Grade (Enhanced)**

**Location**: `analytics/pipeline_v14_enhanced.py`

**Purpose**: Complete wind-to-finance analysis with debt structuring and lender KPIs.

**Execution Flow**:
```
Wind Assessment → Cashflow Model → Debt Structuring → KPI Calculation
```

**Output Contract** (`ScenarioResult`):
- `annual_rows`: Annual cashflow schedule (25 years)
- `debt_result`: DSCR series, min_dscr, covenant tracking
- `kpis`: project_irr, equity_irr, min_dscr, avg_dscr, llcr, plcr
- `metrics`: Execution metrics and audit trail
- Full CASPER compliance (audit trail)

**When to Use**:
- Lender presentations
- Sensitivity analysis
- Monte Carlo risk analysis
- Optimization studies
- CASPER tail risk analysis
- Any analysis requiring debt covenants or leveraged returns

**Import Pattern**:
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline

result = run_v14_pipeline(
    config=config,
    validation_mode="strict",
    validation_modules=["cashflow", "debt"]
)

# Access lender outputs:
min_dscr = result["debt_result"]["min_dscr"]
project_irr = result["kpis"]["project_irr"]
equity_irr = result["kpis"]["equity_irr"]
annual_cashflows = result["annual_rows"]
```

---

### **Pipeline 2: Wind-Only (Legacy)**

**Location**: `analytics/pipeline_v14.py`

**Purpose**: Energy assessment for wind engineering teams. Does NOT include finance stack.

**Execution Flow**:
```
Wind Assessment → Energy Calculation → Revenue Estimate
```

**Output Contract** (`WindAssessment`):
- `aep_p50_mwh`: P50 annual energy production
- `aep_p75_mwh`: P75 (conservative) AEP
- `capacity_factor_pct`: Average capacity factor
- `revenue_annual_p75_usd`: Simple revenue estimate
- Wind resource statistics (Weibull, losses)

**When to Use**:
- Wind resource assessment only
- Turbine selection studies
- Site comparison (no finance)
- Quick energy estimates
- **Do NOT use for**: Lender analysis, sensitivity with debt, optimization

**Import Pattern**:
```python
from analytics.pipeline_v14 import WindPipeline

wind_result = WindPipeline.run_complete_assessment(
    config=config,
    turbine_model="Vestas_V150_5.6MW"
)

# Access wind outputs:
aep_p50 = wind_result.aep_p50_mwh
capacity_factor = wind_result.capacity_factor_pct
```

**⚠️ Warning**: This pipeline does NOT produce:
- Debt structuring
- DSCR/LLCR/PLCR
- Leveraged returns (equity IRR)
- Annual cashflow schedules
- Covenant tracking

If you need any of these, use the lender-grade pipeline.

---

## 🚪 **Canonical Entry Points (GWTF Compliance)**

### **1. Root CLI** → `run_full_pipeline_v14.py`

**Purpose**: Command-line interface for complete wind-to-finance analysis.

**Wiring**: ✅ Uses `analytics.pipeline_v14_enhanced` (lender-grade)

**Usage**:
```bash
python run_full_pipeline_v14.py config=scenarios/lender_case.yaml
```

**Output**: JSON to stdout with full lender stack

**Protected By**: `tests/api/test_run_full_pipeline_v14_is_lender_pipeline.py`

---

### **2. Evaluation Gateway** → `analytics.evaluation_v14`

**Purpose**: Canonical evaluation surface for all analytical engines.

**Wiring**: ✅ Uses `analytics.pipeline_v14_enhanced` (lender-grade)

**Functions**:
- `evaluate_with_overrides(config_path, overrides)` → Single scenario with shocks
- `evaluate_scenario_from_dict(config, overrides)` → In-memory config
- `evaluate_with_casper_tail_risk(...)` → Full CASPER orchestration

**Usage**:
```python
from analytics.evaluation_v14 import evaluate_with_overrides

# Base case
kpis_base = evaluate_with_overrides(
    config_path="scenarios/base.yaml",
    overrides={}
)

# Shocked scenario (CAPEX +20%)
kpis_shocked = evaluate_with_overrides(
    config_path="scenarios/base.yaml",
    overrides={"finance": {"capex_total_usd": 240e6}}
)

# Compare
irr_impact = kpis_shocked["project_irr"] - kpis_base["project_irr"]
print(f"CAPEX shock IRR impact: {irr_impact * 100:.2f}%")
```

**Used By**:
- `analytics/sensitivity_v14.py` (tornado analysis)
- `analytics/monte_carlo_v14.py` (MC engine)
- Optimization modules
- CASPER orchestration

**Protected By**: `tests/api/test_evaluation_v14_lender_stack.py`

---

## 🔬 **Integration Pattern for Analytical Engines**

**Golden Rule**: Analytical engines should NEVER import pipelines directly. Always use the evaluation gateway.

### **❌ Wrong Pattern** (causes silent bugs):

```python
# In sensitivity_v14.py (WRONG)
from analytics.pipeline_v14 import run_v14_pipeline  # Wind-only!

def run_sensitivity(base_config, shocks):
    results = []
    for shock in shocks:
        config = apply_shock(base_config, shock)
        result = run_v14_pipeline(config)  # Missing debt/KPIs!
        results.append(result)
    return results
```

**Problem**: Gets wind-only outputs. Tornado chart missing debt covenant impacts.

---

### **✅ Correct Pattern** (uses evaluation gateway):

```python
# In sensitivity_v14.py (CORRECT)
from analytics.evaluation_v14 import evaluate_scenario_from_dict

def run_sensitivity(base_config, shocks):
    results = []
    for shock in shocks:
        kpis = evaluate_scenario_from_dict(
            config=base_config,
            overrides=shock
        )
        results.append(kpis)  # Gets lender KPIs!
    return results
```

**Benefit**: Automatic access to full lender stack. Tornado chart shows debt impacts.

---

## 🛡️ **Regression Prevention (Golden Tests)**

To prevent future wiring errors, we have **golden tests** that fail immediately if canonical surfaces get rewired incorrectly.

### **Test 1: Root CLI must produce lender outputs**

**File**: `tests/api/test_run_full_pipeline_v14_is_lender_pipeline.py`

**Validates**:
- CLI output contains `annual_rows`
- CLI output contains `debt_result` with `min_dscr`
- CLI output contains `kpis` with `project_irr`, `equity_irr`, `llcr`, `plcr`

**Failure Message**: "CLI rewired to wind-only pipeline"

---

### **Test 2: Evaluation gateway must return lender KPIs**

**File**: `tests/api/test_evaluation_v14_lender_stack.py`

**Validates**:
- `evaluate_with_overrides()` returns dict with lender KPIs
- All required keys present: `project_irr`, `equity_irr`, `min_dscr`, `avg_dscr`, `llcr`, `plcr`
- Shock mechanism works (CAPEX increase reduces IRR)

**Failure Message**: "Evaluation gateway missing lender KPIs. Check import on line 11."

---

## 📝 **Usage Decision Tree**

```
Do you need debt structuring or lender KPIs?
├── YES → Use analytics.pipeline_v14_enhanced
│        OR use analytics.evaluation_v14 (preferred)
│
└── NO → Do you need wind assessment only?
           ├── YES → Use analytics.pipeline_v14 (explicit)
           └── NO → You probably need the lender pipeline

Are you building an analytical engine?
├── YES → Use analytics.evaluation_v14 (canonical gateway)
└── NO → Use appropriate pipeline directly
```

---

## 🔄 **Migration Guide**

If you have existing code importing the wrong pipeline:

### **Scenario 1: Sensitivity/MC/Optimization**

**Old (Broken)**:
```python
from analytics.pipeline_v14 import run_v14_pipeline

def my_analysis(config):
    result = run_v14_pipeline(config)
    return result["kpis"]  # KeyError: 'kpis' not in wind-only output!
```

**New (Fixed)**:
```python
from analytics.evaluation_v14 import evaluate_scenario_from_dict

def my_analysis(config):
    kpis = evaluate_scenario_from_dict(config)
    return kpis  # Gets lender KPIs automatically
```

---

### **Scenario 2: Direct Pipeline Call**

**Old (Broken)**:
```python
from analytics.pipeline_v14 import run_v14_pipeline

result = run_v14_pipeline(config)
min_dscr = result["debt_result"]["min_dscr"]  # KeyError!
```

**New (Fixed)**:
```python
from analytics.pipeline_v14_enhanced import run_v14_pipeline

result = run_v14_pipeline(config)
min_dscr = result["debt_result"]["min_dscr"]  # Works!
```

---

## 📊 **Output Contract Comparison**

| Output Key | Lender Pipeline | Wind-Only Pipeline |
|------------|----------------|--------------------|
| `annual_rows` | ✅ 25-year cashflow schedule | ❌ Not included |
| `debt_result` | ✅ DSCR series, covenants | ❌ Not included |
| `kpis` | ✅ IRR, NPV, DSCR, LLCR, PLCR | ❌ Not included |
| `scenario_result` | ✅ Full ScenarioResult | ❌ Not included |
| `aep_p50_mwh` | ✅ Included in scenario | ✅ Primary output |
| `aep_p75_mwh` | ✅ Included in scenario | ✅ Primary output |
| `capacity_factor_pct` | ✅ Included in scenario | ✅ Primary output |
| `revenue_annual_p75_usd` | ✅ Included in scenario | ✅ Primary output |

---

## ⚙️ **Framework Compliance Summary**

- **GWTF** (Gateway): Single canonical evaluation surface ✅
- **CESSPIT**: Fail-fast on missing KPIs ✅
- **CASPER**: Full audit trail in lender pipeline ✅
- **CCCDIR**: Comprehensive documentation ✅
- **TEST-01**: Golden tests lock in behavior ✅

---

## 📞 **Support**

If you're unsure which pipeline to use:
1. Check this document's decision tree
2. Check golden tests for expected outputs
3. When in doubt, use `analytics.evaluation_v14` (safe default)

**Last Updated**: December 2025 (Sprint 9)

**Maintainer**: Dutch Bay Wind Farm Team
