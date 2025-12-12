# Sprint 9: Monte Carlo & Sensitivity Integration Strategy
## The Final Mile: Integrating Risk Analytics into the Pipeline

**Date:** December 9, 2025
**Status:** Analysis & Planning Phase
**Target:** Production-grade Integration

---

## EXECUTIVE SUMMARY

You're at the final integration point of Sprint 9. The Monte Carlo (`monte_carlo_v14.py`, 38.7 KB) and Sensitivity (`sensitivity_v14.py`, 38.3 KB) modules are feature-complete and tested. The pipeline infrastructure is in place. **What's missing: Orchestration—the glue that connects these modules into `run_full_pipeline_v14.py`.**

### Current State (WHERE WE ARE)

**✅ Core Modules Ready:**
- `analytics/monte_carlo_v14.py` — Stochastic sampling, probability distributions, scenario generation
- `analytics/sensitivity_v14.py` — Tornado analysis, parameter variation, sensitivity indices
- `analytics/pipeline_v14.py` — Base pipeline orchestration (14.5 KB, 2025-12-07)
- `run_full_pipeline_v14.py` — Entry point (1.8 KB, mostly stub)

**✅ Test Coverage:**
- 278 passing tests across 324 total
- Monte Carlo: 31 regression tests + 1 toy regression (test_monte_carlo_v14.py, 27.3 KB)
- Sensitivity: 15 core tests + 12 comprehensive tests + 5 regression tests
- Integration: schema validation, contract tests, lender suite tests all passing

**✅ Configuration Layer:**
- `config/monte_carlo_defaults.yaml` — Sampling, correlation matrices
- `config/sensitivity_defaults.yaml` — Tornado, Pareto configurations
- `config/run_full_pipeline_v14.yaml` — Pipeline orchestration config

**✅ Export & Reporting:**
- `sensitivity_export.py` — CSV/Excel output formatting
- `executive_workbook.py` — Aggregation for workbook sheets
- `export_helpers.py` — KPI normalization, data contracts

**⚠️ Known Issues (2 failing tests):**
1. **Import issue:** `test_no_forbidden_pipeline_imports` expects `analytics.scenarioloader` but actual module is `scenario_loader`
   - **Fix:** Create alias module `analytics/scenarioloader.py` that re-exports from `scenario_loader`
2. **Missing lazy load:** `test_evaluate_with_overrides_attaches_dscr_min_alias` — `evaluate_scenario` not exposed in `analytics/__init__.py`
   - **Fix:** Add lazy loader for `evaluate_scenario` function

---

## WHERE WE SHOULD BE

### Vision: Production-Grade Integration

```
Input Config (YAML)
        ↓
┌─────────────────────────────────────┐
│ run_full_pipeline_v14.py            │  ← PRIMARY ORCHESTRATOR
│  - Validates config schema          │
│  - Runs core DCF (cashflow/debt)    │
│  - Conditionally triggers:          │
│      • sensitivity_v14 (if enabled) │
│      • monte_carlo_v14 (if enabled) │
│  - Merges results                   │
│  - Exports workbook/CSV/JSON        │
└─────────────────────────────────────┘
        ↓ ↓ ↓
    ┌─────┴─────┬──────────┐
    ↓           ↓          ↓
CASHFLOW      DEBT      EQUITY
    ↓           ↓          ↓
    └─────┬─────┴──────────┘
          ↓
      METRICS (KPIs)
          ↓
    ┌─────┴─────────────────────┐
    ↓                           ↓
SENSITIVITY             MONTE CARLO
(Tornado, Pareto)       (Risk, Probs)
    ↓                           ↓
    └─────────┬─────────────────┘
              ↓
     EXECUTIVE WORKBOOK
     (Multi-sheet XLSX)
```

### Key Integration Points

**1. Parameter Management**
- Central config schema validation (schema_guard.py)
- Parameter resolution: scenario overrides → pipeline config → defaults
- CASPER pattern: Config-Aware Scenario Parameter Engine Registry

**2. Risk Analytics Triggering**
- Sensitivity: Always runs (deterministic tornado)
- Monte Carlo: Conditional on `enable_monte_carlo: true`
- Proper dependency wiring via lazy imports

**3. Result Merging**
- Core KPIs from base pipeline
- Sensitivity metrics (tornado factors, Pareto fronts)
- Monte Carlo outcomes (percentiles, breach probabilities, VaR)
- Multi-dimensional aggregation in executive workbook

**4. Export Layer**
- CSV: Sensitivity/MC results as time series
- JSON: Full result dictionary with metadata
- XLSX: Multi-sheet workbook (KPIs, sensitivity, risk summary, covenants)

---

## HOW WE GET THERE: 5-STEP INTEGRATION PLAN

### Step 1: Fix Import Issues (Immediate, ~30 min)

**Problem:** Lint tests failing due to module naming inconsistency

**Actions:**
```bash
# 1. Create alias module for backward compatibility
cat > analytics/scenarioloader.py << 'EOF'
"""Alias module for scenario_loader.

This module provides a consistent import path:
  from analytics.scenarioloader import load_scenario_config

Instead of:
  from analytics.scenario_loader import load_scenario_config
"""

from analytics.scenario_loader import load_scenario_config

__all__ = ["load_scenario_config"]
EOF

# 2. Update sensitivity_v14.py imports to use alias
# Change: from analytics.scenario_loader import load_scenario_config
# To: from analytics.scenarioloader import load_scenario_config

# 3. Add evaluate_scenario to analytics/__init__.py lazy loader
# In __getattr__ function, add:
if name == "evaluate_scenario":
    from analytics.evaluate_scenario import evaluate_scenario
    return evaluate_scenario
```

**Why:** Ensures linter tests pass and imports are consistent with test expectations.

---

### Step 2: Refactor `run_full_pipeline_v14.py` Core Logic (1-2 hours)

**Current State:** ~1.8 KB stub
**Target:** 300-400 KB orchestrator with full conditional logic

**Structure:**
```python
# run_full_pipeline_v14.py - ORCHESTRATION LAYER

def run_v14_pipeline(
    config: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Main entry point for full v14 pipeline.

    Flow:
    1. Validate and merge configs
    2. Run core DCF (cashflow, debt, equity, metrics)
    3. Conditionally run sensitivity
    4. Conditionally run Monte Carlo
    5. Merge results into unified KPI dict
    6. Return for export/workbook generation
    """

    # === PHASE 1: CONFIG PREPARATION ===
    # - Load scenario config
    # - Apply overrides
    # - Validate schema (schema_guard)
    # - Resolve all parameters

    resolved_config = _prepare_configuration(config, overrides, validation_mode)

    # === PHASE 2: CORE FINANCIAL CALCULATIONS ===
    # Run in order: cashflow → debt → equity → metrics
    # This produces baseline KPIs

    base_result = _run_core_pipeline(resolved_config)
    # Returns:
    # {
    #   "project_irr": float,
    #   "project_npv": float,
    #   "min_dscr": float,
    #   "max_debt_usd": float,
    #   "kpis": {...},
    #   "cashflow_rows": [...],
    #   "debt_schedule": [...],
    # }

    # === PHASE 3: SENSITIVITY ANALYSIS (ALWAYS) ===
    # Tornado: How does each parameter affect IRR, DSCR, etc.?

    sensitivity_result = _run_sensitivity(resolved_config, base_result)
    # Returns:
    # {
    #   "tornado": {"param": {"low": float, "high": float, "range": float}},
    #   "pareto_front": [...],
    #   "sensitivity_indices": {...},
    # }

    # === PHASE 4: MONTE CARLO ANALYSIS (CONDITIONAL) ===
    # If enable_monte_carlo=True in config

    monte_carlo_result = None
    if resolved_config.get("analytics", {}).get("enable_monte_carlo", False):
        monte_carlo_result = _run_monte_carlo(resolved_config, base_result)
        # Returns:
        # {
        #   "percentiles": {10: float, 50: float, 90: float},
        #   "breach_probabilities": {"min_dscr": float, ...},
        #   "value_at_risk": float,
        #   "samples": [...],  # Raw sample data
        # }

    # === PHASE 5: RESULT MERGING ===
    # Flatten everything into single KPI dictionary

    merged_result = _merge_results(
        base_result,
        sensitivity_result,
        monte_carlo_result,
    )

    return merged_result
```

**Key Functions to Implement:**
1. `_prepare_configuration()` — Config validation & resolution
2. `_run_core_pipeline()` — DCF pipeline (delegate to existing modules)
3. `_run_sensitivity()` — Sensitivity orchestration
4. `_run_monte_carlo()` — MC orchestration (conditional)
5. `_merge_results()` — Flatten to single dict

---

### Step 3: Implement Result Merging Logic (1-2 hours)

**Challenge:** Multiple result dictionaries → Single flat KPI dict

**Solution: Contract-Aware Merging**

```python
def _merge_results(
    base: dict[str, Any],
    sensitivity: dict[str, Any],
    monte_carlo: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Merge results following Go With The Flow rules:
    - No key collisions (use prefixes if needed)
    - Preserved structure for nested dicts
    - Flattened KPIs for top-level access
    """

    result = {}

    # 1. Copy base KPIs directly
    result.update(base)  # project_irr, project_npv, min_dscr, kpis, etc.

    # 2. Sensitivity metrics under 'sensitivity' namespace
    result["sensitivity"] = sensitivity

    # 3. Monte Carlo under 'monte_carlo' namespace
    if monte_carlo:
        result["monte_carlo"] = monte_carlo
        # Also expose key metrics at top level with prefix
        result["monocarlo_var"] = monte_carlo.get("value_at_risk")
        result["monocarlo_dscr_breach_prob"] = monte_carlo["breach_probabilities"].get("min_dscr")

    # 4. Add metadata
    result["analysis_metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "modules_run": ["cashflow", "debt", "equity", "metrics", "sensitivity",
                       "monte_carlo" if monte_carlo else None],
        "scenario_name": base.get("scenario_name", "unknown"),
    }

    return result
```

**Result Shape:**
```python
{
    # Base KPIs (from core pipeline)
    "scenario_name": str,
    "project_irr": float,
    "project_npv": float,
    "min_dscr": float,
    "max_debt_usd": float,

    # Detailed breakdowns
    "kpis": {...},
    "cashflow_rows": [...],
    "debt_schedule": [...],
    "equity_schedule": [...],

    # Sensitivity results (tornado, Pareto)
    "sensitivity": {
        "tornado": {"capacity_mw": {...}, "tariff_lkr_per_kwh": {...}},
        "pareto_front": [...],
        "sensitivity_indices": {...},
    },

    # Monte Carlo results (if enabled)
    "monte_carlo": {
        "percentiles": {10: float, 50: float, 90: float},
        "breach_probabilities": {"min_dscr": float, "llcr": float},
        "value_at_risk": float,
        "samples": [...],
    },

    # Top-level convenience metrics
    "monocarlo_var": float,
    "monocarlo_dscr_breach_prob": float,

    # Metadata
    "analysis_metadata": {
        "timestamp": str,
        "modules_run": [str],
        "scenario_name": str,
    },
}
```

---

### Step 4: Connect Export Layer (1 hour)

**Ensure Executive Workbook Aggregates Properly**

```python
# In executive_workbook.py or new export coordinator

def build_full_workbook(
    merged_result: dict[str, Any],
    output_path: str = "exports/analysis_result.xlsx",
) -> str:
    """
    Build multi-sheet Excel workbook from merged results.

    Sheets:
    1. "Executive Summary" — Key KPIs, IRR, DSCR, NPV
    2. "Cashflow" — Annual cashflow rows
    3. "Sensitivity" — Tornado factors, Pareto
    4. "Monte Carlo" — Risk percentiles, breach probs
    5. "Covenants" — DSCR/LLCR over time
    6. "Debt Schedule" — Principal, interest, balance
    """

    # Use openpyxl to build multi-sheet workbook
    # Format: KPI_normalizer to standardize units
    # Export: One value per cell (no nested dicts)

    workbook = Workbook()

    # Sheet 1: Executive Summary
    _add_summary_sheet(workbook, merged_result)

    # Sheet 2: Cashflow
    _add_cashflow_sheet(workbook, merged_result["cashflow_rows"])

    # Sheet 3: Sensitivity
    _add_sensitivity_sheet(workbook, merged_result["sensitivity"])

    # Sheet 4: Monte Carlo (if present)
    if "monte_carlo" in merged_result:
        _add_monte_carlo_sheet(workbook, merged_result["monte_carlo"])

    # ... save to output_path
    return output_path
```

**Why This Matters:** Users need actionable insights in a familiar format (Excel). The workbook is the deliverable.

---

### Step 5: Testing & Validation (2-3 hours)

**Create Integration Test Suite**

```python
# tests/test_full_pipeline_integration.py

def test_full_pipeline_basic_scenario():
    """Smoke test: pipeline runs end-to-end."""
    config = load_scenario_config("scenarios/good_unit_test.yaml")
    result = run_v14_pipeline(config)

    # Assert structure
    assert "project_irr" in result
    assert "sensitivity" in result
    assert "analysis_metadata" in result

    # Assert values in valid range
    assert 0 <= result["project_irr"] <= 1.0
    assert result["min_dscr"] > 0

def test_monte_carlo_conditional():
    """MC only runs if enabled."""
    config_no_mc = {"analytics": {"enable_monte_carlo": False}}
    result = run_v14_pipeline(config_no_mc)
    assert "monte_carlo" not in result

    config_yes_mc = {"analytics": {"enable_monte_carlo": True}}
    result = run_v14_pipeline(config_yes_mc)
    assert "monte_carlo" in result

def test_result_export_to_workbook():
    """Results can be exported to Excel."""
    config = load_scenario_config("scenarios/good_unit_test.yaml")
    result = run_v14_pipeline(config)

    output_path = build_full_workbook(result, "/tmp/test.xlsx")
    assert Path(output_path).exists()

    # Verify sheets
    wb = load_workbook(output_path)
    assert "Executive Summary" in wb.sheetnames
    assert "Sensitivity" in wb.sheetnames
```

---

## CASPER & GO WITH THE FLOW PRINCIPLES

### CASPER (Configuration, Aggregation, Scenario, Parameters, Engine, Results)

**Applied to Integration:**

| Component | Role | Implementation |
|-----------|------|-----------------|
| **C**onfiguration | Central schema definition | `schema_guard.py` validates all inputs |
| **A**ggregation | Multi-module result merging | `_merge_results()` in `run_v14_pipeline` |
| **S**cenario | Named test/prod configs | `scenarios/*.yaml` files |
| **P**arameters | Resolution & override | `_prepare_configuration()` layer |
| **E**ngine | Core computation modules | `cashflow_v14`, `sensitivity_v14`, `monte_carlo_v14` |
| **R**esults | Unified output contract | Single dict with typed fields |

### Go With The Flow Rules v3.0 (from CSV)

**Key Rules Applied:**

1. **"Explicit over implicit"** — All parameter sources documented, no hidden defaults
2. **"Namespace preservation"** — Use prefixes for metric groups (e.g., `monte_carlo_var`, `sensitivity_tornado`)
3. **"Schema as contract"** — Result dict validated against defined schema
4. **"Lazy loading for circular deps"** — Avoid hard imports in `__init__.py`
5. **"Export at step boundaries"** — Each phase has clear output format

---

## RISK MITIGATION

### Identified Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Import cycles** | Module load failures | Already using lazy loading in `analytics/__init__.py` |
| **Result shape changes** | Workbook export breaks | Define strict TypedDict contracts |
| **Performance** | MC sampling takes >30s | Add parallel sampling with `concurrent.futures` |
| **Stochastic variance** | Results change per run | Seed numpy RNG in `monte_carlo_v14` |
| **Missing edge cases** | Test suite gaps | Run against all scenarios in `scenarios/` dir |

---

## DELIVERABLES CHECKLIST

- [ ] Step 1: Fix imports (scenarioloader alias, evaluate_scenario lazy load)
- [ ] Step 2: Refactor `run_full_pipeline_v14.py` with conditional logic
- [ ] Step 3: Implement `_merge_results()` and result flattening
- [ ] Step 4: Connect executive workbook export
- [ ] Step 5: Integration test suite (minimum 5 tests)
- [ ] All 324 pytest tests passing
- [ ] Manual test: `python run_full_pipeline_v14.py --config scenarios/good_unit_test.yaml`
- [ ] Output validation: Excel file generated with all sheets

---

## TIMELINE ESTIMATE

| Step | Duration | Owner | Status |
|------|----------|-------|--------|
| 1. Import fixes | 0.5 hr | You | Ready to execute |
| 2. Refactor pipeline | 1.5-2 hr | You | Spec complete |
| 3. Result merging | 1-2 hr | You | Logic designed |
| 4. Export connection | 1 hr | You | Functions exist |
| 5. Testing | 2-3 hr | You | Test cases sketched |
| **TOTAL** | **6-8.5 hours** | | **This session** |

---

## SUCCESS CRITERIA

✅ **Code Quality:**
- All 324 pytest tests passing
- No linter/mypy failures
- Type hints on all public functions

✅ **Functional:**
- `run_v14_pipeline(config)` accepts YAML config and returns typed dict
- Sensitivity metrics included in baseline results
- Monte Carlo results optional based on config flag
- Excel workbook generation works with all sheets

✅ **Documentation:**
- Docstrings explain CASPER pattern
- README updated with integration flow diagram
- Example usage in `run_full_pipeline_v14.py` comments

✅ **Integration:**
- Existing tests remain passing (no regressions)
- New integration tests cover end-to-end flow
- Result shape matches contracts in sensitivity/contracts

---

## NEXT STEPS

1. **Immediate (Now):** Fix imports (Step 1)
2. **Next 2 hours:** Refactor pipeline core (Step 2)
3. **Next 2 hours:** Implement merging (Step 3)
4. **Final hour:** Testing & validation (Steps 4-5)

This is the final assembly. Everything you need is built. Now it's orchestration.

---

**Remember:** CASPER is about clear contracts at boundaries. Go With The Flow is about respecting those contracts. Do both, and Sprint 9 is done. 🎯
