# 🎯 PATCH SET #1 EXECUTION CHECKLIST

**Status**: Ready for local dev implementation
**File**: analytics/sensitivity_v14.py
**Scope**: Surgical refactoring (evaluation_v14-only)

---

## ✅ Pre-Implementation Checklist

- [ ] **Verify file exists**: `analytics/sensitivity_v14.py` present
- [ ] **Verify gateway exists**: `analytics/evaluation_v14.py` with `evaluate_scenario()` function
- [ ] **Backup current**: `cp analytics/sensitivity_v14.py analytics/sensitivity_v14.py.bak`
- [ ] **All existing tests pass**: `pytest tests/ -k sensitivity -v` (baseline)

---

## 📝 Implementation Steps (In Order)

### Step 1: Replace Imports
**File**: `analytics/sensitivity_v14.py` (top of file)

```python
# REMOVE these lines:
from analytics.pipeline_v14 import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

# ADD this line:
from analytics.evaluation_v14 import evaluate_scenario
```

**Verification**: `grep -n "run_v14_pipeline\|load_scenario_config" analytics/sensitivity_v14.py`
**Expected**: Should see NO matches after step 1 is complete (not yet - they're in functions)

---

### Step 2: Add SensitivityResult Dataclass
**Location**: After imports, before `SensitivityRequest`

```python
@dataclass(slots=True)
class SensitivityResult:
    """
    Canonical sensitivity result surface for a single scenario config.

    base_kpis:
        KPI snapshot at unshocked (base) configuration.

    shocked_kpis:
        For each parameter_name, a mapping:
            shock_label -> KPI snapshot

        e.g.
            {
                "project.capex_usd_per_kw": {
                    "down": {...},
                    "up": {...},
                },
            }
    """

    base_kpis: Dict[str, float]
    shocked_kpis: Dict[str, Dict[str, Dict[str, float]]]
```

**Verification**: `python -c "from analytics.sensitivity_v14 import SensitivityResult; print(SensitivityResult.__name__)"`
**Expected**: `SensitivityResult`

---

### Step 3: Add _evaluate_base_kpis() Helper
**Location**: Before `_analyze_single_parameter()`

```python
def _evaluate_base_kpis(config_path: str | Path) -> Dict[str, float]:
    """
    Evaluate base (unshocked) KPIs for a scenario.

    All analytics must use this gateway, not the pipeline directly.
    """
    return evaluate_scenario(config_path=config_path, overrides=None)
```

**Verification**: `grep -n "_evaluate_base_kpis" analytics/sensitivity_v14.py`
**Expected**: Function defined + 3 calls in tornado runners

---

### Step 4: Refactor _analyze_single_parameter()
**Location**: Replace entire function body

Key changes:
1. Remove: `base_config = load_scenario_config(...)`
2. Remove: `low_config = _deep_merge_config(...)`
3. Remove: `low_pipeline_result = run_v14_pipeline(...)`
4. Remove: Extraction of `low_kpis = low_pipeline_result["kpis"]`
5. Add: `low_kpis = evaluate_scenario(config_path=..., overrides=...)`

**Verification**: `grep -c "run_v14_pipeline" analytics/sensitivity_v14.py`
**Expected**: 2 matches (only in run_breakeven_parameter objective function - next step)

---

### Step 5: Update run_tornado_sensitivity()
**Location**: Function body, around line ~450-470

Replace:
```python
base_config = load_scenario_config(base_config_path)
base_pipeline_result = run_v14_pipeline(
    config=base_config,
    validation_mode="strict",
)
base_kpis = base_pipeline_result["kpis"]
```

With:
```python
# Use evaluate_scenario gateway
base_kpis = _evaluate_base_kpis(base_config_path)
```

**Verification**: `grep -A 2 "base_config = load_scenario_config" analytics/sensitivity_v14.py | wc -l`
**Expected**: 2 matches remain (in run_multi_metric_tornado and run_breakeven_parameter)

---

### Step 6: Update run_multi_metric_tornado()
**Location**: Function body, around line ~550-570

Same replacement as Step 5:
```python
# OLD
base_config = load_scenario_config(base_config_path)
base_pipeline_result = run_v14_pipeline(...)
base_kpis = base_pipeline_result["kpis"]

# NEW
base_kpis = _evaluate_base_kpis(base_config_path)
```

**Verification**: `grep -n "base_config = load_scenario_config" analytics/sensitivity_v14.py`
**Expected**: 1 match (only in run_breakeven_parameter)

---

### Step 7: Update run_breakeven_parameter()
**Location**: Two places in function

**A. Base evaluation** (around line ~750):
```python
# OLD
base_config = load_scenario_config(base_config_path)
base_pipeline_result = run_v14_pipeline(...)
base_kpis = base_pipeline_result["kpis"]

# NEW
base_kpis = _evaluate_base_kpis(base_config_path)
```

**B. Inside objective() function** (around line ~810):
```python
# OLD
def objective(x: float) -> float:
    overrides = _build_nested_override(variable_name, x)
    base_config = load_scenario_config(base_config_path)
    override_config = _deep_merge_config(base_config, overrides)
    pipeline_result = run_v14_pipeline(
        config=override_config,
        validation_mode="strict",
    )
    kpis = pipeline_result["kpis"]

# NEW
def objective(x: float) -> float:
    overrides = _build_nested_override(variable_name, x)
    # Use evaluate_scenario gateway (handles merge + validation)
    kpis = evaluate_scenario(
        config_path=base_config_path,
        overrides=overrides,
    )
```

**Verification**: `grep -c "run_v14_pipeline\|load_scenario_config\|_deep_merge_config" analytics/sensitivity_v14.py`
**Expected**: 0 (all removed)

---

## 🧪 Validation Steps (After Implementation)

### A. Import Check
```bash
# Should show NO results
grep -r "run_v14_pipeline" analytics/sensitivity_v14.py
grep -r "load_scenario_config" analytics/sensitivity_v14.py
grep -r "_deep_merge_config(base_config" analytics/sensitivity_v14.py
```

### B. Type Checking
```bash
mypy analytics/sensitivity_v14.py analytics/evaluation_v14.py --strict
```

**Expected**: Clean (no warnings)

### C. Code Quality
```bash
black analytics/sensitivity_v14.py --check
ruff check analytics/sensitivity_v14.py
isort analytics/sensitivity_v14.py --check-only
```

**Expected**: All pass

### D. Functional Test (Quick)
```bash
python -c "
from analytics.sensitivity_v14 import _evaluate_base_kpis
try:
    kpis = _evaluate_base_kpis('scenarios/dutchbay_lendercase_2025Q4.yaml')
    print('✅ _evaluate_base_kpis() works!')
    print(f'   KPI keys: {list(kpis.keys())}')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

**Expected**: ✅ Gateway works, KPI keys match (project_irr, equity_irr, etc)

### E. Full Test Suite
```bash
pytest tests/analytics_layer/ -v -k sensitivity
```

**Expected**: All existing tests pass (same results as baseline)

---

## ⚠️ Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| **Missing dataclass import** | `NameError: name 'dataclass' not defined` | Add `from dataclasses import dataclass` |
| **Forgot to import evaluate_scenario** | `NameError: name 'evaluate_scenario' not found` | Add `from analytics.evaluation_v14 import evaluate_scenario` |
| **Left old pipeline calls** | `NameError: name 'run_v14_pipeline' not defined` | Remove remaining `run_v14_pipeline()` calls |
| **KPI key mismatch** | `KeyError: 'equity_irr'` | Verify evaluate_scenario returns correct KPI keys |
| **Type errors in SensitivityResult** | `TypeError: bad argument to dict()` | Ensure Dict[str, float] types match |

---

## 📊 Expected Outcomes

### Before Patch Set #1
```
sensitivity_v14.py imports:
  ✓ run_v14_pipeline (direct)
  ✓ load_scenario_config (direct)
  ✓ _deep_merge_config (internal)

Evaluation flow:
  sensitivity → load_config → merge config → run_pipeline → extract KPIs
```

### After Patch Set #1
```
sensitivity_v14.py imports:
  ✓ evaluate_scenario (from evaluation_v14)
  ✗ run_v14_pipeline (removed)
  ✗ load_scenario_config (removed)
  ✓ _deep_merge_config (still internal, not used for sensitivity)

Evaluation flow:
  sensitivity → evaluate_scenario → {load_config + merge + run_pipeline + extract} → KPIs
  (all hidden in evaluate_scenario)
```

### File Statistics
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Direct pipeline calls | 4 | 0 | -4 |
| Direct loader calls | 4 | 0 | -4 |
| evaluate_scenario calls | 0 | 5+ | +5 |
| Lines of code | ~1,100 | ~1,050 | -50 |
| Imports simplified | No | Yes | ✓ |

---

## 🚀 Next Steps

1. **Commit as Patch Set #1**: Use provided commit message
2. **PR with full details**: Reference Phase 1 architecture
3. **Code review**: Verify evaluate_scenario is the only entry point
4. **Test verification**: All sensitivity tests pass
5. **Merge to main**: Mark Patch Set #1 complete
6. **Phase 1B**: Add evaluate_scenario_from_dict() for lazy loading

---

## 📞 Questions?

If tests fail or you hit errors:

1. **Check error message**: Is it about imports, types, or KPI keys?
2. **Verify evaluate_scenario signature**: Does it match what sensitivity expects?
3. **Confirm KPI dict shape**: Is it `dict[str, float]` or wrapped differently?
4. **Review PATCH_SET_1_INSTRUCTIONS.md**: Detailed refactoring guide

Good luck! You've got this! 🚀
