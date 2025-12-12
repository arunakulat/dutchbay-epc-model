# 🛠️ SENSITIVITY MODULE INTEGRATION - IMPLEMENTATION ROADMAP
## Phase-by-Phase Execution Plan with Code Artifacts

---

## PHASE 1: CRITICAL FIXES (2 hours) 🔴 PRIORITY 1

### File 1: sensitivity_heatmap.py

**Issues:**
```python
# Line 27-28: Missing closing parenthesis
x_vals = param_x.base_value * (
    1.0 + np.linspace(param_x.low_pct, param_x.high_pct, steps) / 100.0
    # ❌ MISSING: )

# Line 33-34: Same issue
y_vals = param_y.base_value * (
    1.0 + np.linspace(param_y.low_pct, param_y.high_pct, steps) / 100.0
    # ❌ MISSING: )
```

**Fix:**
```python
# Line 27-28: FIXED
x_vals = param_x.base_value * (
    1.0 + np.linspace(param_x.low_pct, param_x.high_pct, steps) / 100.0
)

# Line 33-34: FIXED
y_vals = param_y.base_value * (
    1.0 + np.linspace(param_y.low_pct, param_y.high_pct, steps) / 100.0
)

# Type hints: Dict → dict (Pydantic v2)
from typing import Any
# Instead of: from typing import Dict, Any
# Change: def _build_nested_override(variable_name: str, value: Any) -> Dict[str, Any]:
# To:     def _build_nested_override(variable_name: str, value: Any) -> dict[str, Any]:
```

**Test Command:**
```bash
python -c "from analytics.sensitivity_heatmap import run_two_way_sensitivity; print('✅ Import OK')"
```

---

### File 2: sensitivity_v14.py

**Primary Issues:**
1. Type hints: `Dict[str, Any]` → `dict[str, Any]`
2. Missing `__all__` export list
3. Pydantic v2 compliance on `SensitivityRequest`

**Changes (Sample):**
```python
# Line 1: Add future annotations (if not present)
from __future__ import annotations

# Lines 3-5: Update imports
from typing import Any  # Remove Dict, List from typing
import pandas as pd

# Remove:
# from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

# Instead use built-in types:
# dict[str, Any]
# list[str]
# tuple[str, ...]

# Line ~30: Add __all__ export
__all__ = [
    "SensitivityRequest",
    "run_tornado_sensitivity",
    "run_multi_metric_tornado",
    "run_breakeven_parameter",
    "tornado_suite_to_dataframe",
    "multi_metric_suite_to_dataframe",
]

# Line ~60: Ensure SensitivityRequest is Pydantic v2 compatible
@dataclass(frozen=True)  # ✅ This is fine (uses dataclass, not Pydantic)
class SensitivityRequest:
    base_config_path: str
    parameters: list[ParameterRangeConfig]
    override_labels: dict[str, str] | None = None
    metric: str = "project_irr"
```

**Test Command:**
```bash
pytest tests/analytics_layer/test_sensitivity_v14.py -v --tb=short
# Should see: 16 tests, all passing
```

---

### File 3: parameter_solvers.py

**Issue:** Solver registration + imports

**Current Pattern:**
```python
def get_solver(derive_from: str):
    """Return solver callable for given derive_from key."""
    solvers = {
        "target_project_irr": solve_for_capex,  # Example
        "target_dscr": solve_for_debt_tenor,    # Example
    }
    return solvers[derive_from]
```

**Requirement:** No circular imports with monte_carlo_v14.py

**Fix:**
```python
# Ensure imports are at module level, not circular:
from analytics.evaluate_scenario import evaluate_with_overrides

# ✅ OK: parameter_solvers imports from evaluate_scenario
# ✅ OK: monte_carlo_v14 imports from parameter_solvers
# ❌ NOT OK: parameter_solvers imports from monte_carlo_v14 (CIRCULAR)
```

**Test Command:**
```bash
python -c "from analytics.monte_carlo_v14 import run_monte_carlo; from analytics.parameter_solvers import get_solver; print('✅ No circular imports')"
```

---

### Validation Commands (All 3 Files)

```bash
# 1. Syntax check
python -m py_compile analytics/sensitivity_heatmap.py
python -m py_compile analytics/sensitivity_v14.py
python -m py_compile analytics/parameter_solvers.py

# 2. Type check (mypy)
mypy analytics/sensitivity_heatmap.py --ignore-missing-imports
mypy analytics/sensitivity_v14.py --ignore-missing-imports

# 3. Linting (ruff)
ruff check analytics/sensitivity_heatmap.py
ruff check analytics/sensitivity_v14.py
ruff check analytics/parameter_solvers.py

# 4. All sensitivity tests
pytest tests/analytics_layer/test_sensitivity_v14.py -v

# 5. All monte carlo tests (ensure no breakage)
pytest tests/analytics_layer/test_monte_carlo_v14.py -v

# 6. Integration test
pytest tests/api/test_monte_carlo_regression_toy.py -v
```

**Expected Result:** ✅ 282+ tests passing, zero linting errors

---

## PHASE 2: INTEGRATION TESTING (3 hours) 🟡 PRIORITY 2

### Goal: Verify Monte Carlo + Sensitivity Work Together

### Test 1: Unit Test Suite Validation

**File:** `tests/api/test_monte_carlo_sensitivity_integration.py` (NEW)

```python
import pytest
from analytics.monte_carlo_v14 import run_monte_carlo
from analytics.sensitivity_v14 import run_tornado_sensitivity, SensitivityRequest
from analytics.contracts_v14 import ParameterRangeConfig

def test_tornado_and_monte_carlo_use_same_pipeline():
    """Verify both engines converge on run_v14_pipeline."""
    # 1. Run tornado on base scenario
    request = SensitivityRequest(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        parameters=[
            ParameterRangeConfig(
                variable_name="project.capex_usd_per_kw",
                base_value=1200.0,
                low_pct=-10.0,
                high_pct=10.0,
            ),
        ],
        metric="project_irr",
    )
    tornado_suite = run_tornado_sensitivity(request)

    # 2. Run monte carlo (10 iterations for speed)
    mc_results = run_monte_carlo(
        mc_config_path="config/monte_carlo_defaults.yaml",
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        n_iterations=10,
    )

    # 3. Verify ranges make sense
    tornado_result = tornado_suite.tornado_results[0]
    base_irr = tornado_result.base_irr
    mc_base = mc_results["default"].project_irr_p50  # Median IRR

    # Should be reasonably close (same scenario, same pipeline)
    assert abs(base_irr - mc_base) < 0.01, \
        f"Tornado base={base_irr}, MC median={mc_base} – mismatch!"

    # 4. Verify MC range brackets tornado range
    mc_irr_p10 = mc_results["default"].project_irr_p10
    mc_irr_p90 = mc_results["default"].project_irr_p90

    assert mc_irr_p10 <= tornado_result.low_irr, \
        f"MC P10={mc_irr_p10} should ≤ tornado low={tornado_result.low_irr}"
    assert mc_irr_p90 >= tornado_result.high_irr, \
        f"MC P90={mc_irr_p90} should ≥ tornado high={tornado_result.high_irr}"

def test_dscr_tracking_across_both_engines():
    """Verify DSCR reported consistently in tornado and MC."""
    # Tornado: directly test DSCR metric
    request = SensitivityRequest(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        parameters=[...],
        metric="dscr_min",  # DSCR sensitivity
    )
    tornado_suite = run_tornado_sensitivity(request)

    # MC: check DSCR distribution
    mc_results = run_monte_carlo(...)

    # Both should report dscr_min_p50 in same ballpark
    assert tornado_suite.base_metric >= 1.0, "Base DSCR should be positive"
    assert mc_results["default"].dscr_min_p50 >= 1.0, "MC DSCR should be positive"

def test_no_circular_imports():
    """Ensure monte_carlo_v14 ↔ parameter_solvers ↔ sensitivity_v14 work together."""
    from analytics.monte_carlo_v14 import run_monte_carlo
    from analytics.sensitivity_v14 import run_tornado_sensitivity
    from analytics.parameter_solvers import get_solver

    # All should import without error
    assert callable(run_monte_carlo)
    assert callable(run_tornado_sensitivity)
    assert callable(get_solver)
```

### Test 2: Regression Tests

```bash
# Ensure all existing tests still pass with refactored files
pytest tests/ -v --tb=short -k "not slow"

# Expected: 282+ passed, 8 skipped
```

### Test 3: Coverage Analysis

```bash
# Generate coverage report
pytest tests/ --cov=analytics --cov-report=html

# Check target files
# - sensitivity_v14.py: Should be 85%+ (currently ~66%)
# - monte_carlo_v14.py: Should stay at 88%+ ✅
```

---

## PHASE 3: FEATURE COMPLETENESS (4-5 hours) 🟢 PRIORITY 3

### Feature 1: Tail Risk Quantification

**File:** `analytics/sensitivity/sensitivity_tail_risk.py` (IMPLEMENT)

```python
"""
Tail risk enrichment: Calculate probability of covenant breach
from Monte Carlo results.

Reference: Damodaran, A. (2012). Valuing Young Companies.
"""

from dataclasses import dataclass
from typing import Any
import numpy as np

@dataclass
class TailRiskScore:
    """Tail risk metrics for a parameter."""
    variable_name: str
    probability_dscr_below_threshold: float  # P(DSCR < 1.25)
    expected_shortfall: float  # E[DSCR | DSCR < 1.25]
    value_at_risk_95: float  # VaR at 95%
    conditional_value_at_risk: float  # CVaR (expected tail loss)

def calculate_covenant_breach_probability(
    mc_results: dict[str, Any],
    covenant_threshold: float = 1.25,
) -> float:
    """
    Calculate P(min_dscr < covenant_threshold) from MC distribution.

    Args:
        mc_results: Output from run_monte_carlo_analysis()
        covenant_threshold: Lender-required minimum DSCR

    Returns:
        float: Probability of breach (0 to 1)
    """
    dscr_series = np.array(mc_results["dscr_series"])
    n_below = np.sum(dscr_series < covenant_threshold)
    return float(n_below) / len(dscr_series)

def enrich_tornado_with_tail_risk(
    tornado_suite,  # From sensitivity_v14.py
    mc_results,  # From monte_carlo_v14.py
    covenant_threshold: float = 1.25,
) -> dict[str, Any]:
    """
    Attach tail risk scores to tornado drivers.

    Creates a mapping: variable_name → TailRiskScore

    Use Case: Lender sees not just "tariff affects IRR by 5%" (tornado)
              but also "tariff impacts have 15% probability of DSCR breach" (tail risk)

    Returns:
        {
            "project.capex_usd_per_kw": TailRiskScore(...),
            "project.tariff_lkr_per_kwh": TailRiskScore(...),
            ...
        }
    """
    breach_prob = calculate_covenant_breach_probability(
        mc_results, covenant_threshold
    )

    # Return enriched tornado with risk scores
    enriched = {}
    for result in tornado_suite.tornado_results:
        var_name = result.variable
        enriched[var_name] = TailRiskScore(
            variable_name=var_name,
            probability_dscr_below_threshold=breach_prob,
            # (Simplified; real version would need parameter-specific breakdown)
            expected_shortfall=0.0,
            value_at_risk_95=0.0,
            conditional_value_at_risk=0.0,
        )

    return enriched
```

**Test:**
```bash
pytest tests/analytics_layer/test_sensitivity_tail_risk.py -v
```

### Feature 2: Correlation Modeling

**File:** `analytics/sensitivity/sensitivity_correlations.yaml` (NEW)

```yaml
# Parameter correlation matrix for Monte Carlo
# Use case: Capex & debt tenor often move together

parameters:
  - variable_name: "project.capex_usd_per_kw"
    base_value: 1200.0
    low_pct: -20.0
    high_pct: 20.0

  - variable_name: "project.tariff_lkr_per_kwh"
    base_value: 12.5
    low_pct: -10.0
    high_pct: 10.0

correlations:
  # (capex, tariff): uncorrelated (independent drivers)
  - pair: ["project.capex_usd_per_kw", "project.tariff_lkr_per_kwh"]
    coefficient: 0.0
    reason: "Independent market factors"

  # Future: Add FX rate, debt tenor correlations
```

**Code Integration (monte_carlo_v14.py):**
```python
# Add to run_monte_carlo_analysis():

# Load correlation matrix (if available)
correlations = _load_parameter_correlations("scenarios/sensitivity_correlations.yaml")

# Apply Cholesky decomposition to unit hypercube samples
if correlations:
    unit_samples = _apply_correlation_matrix(unit_samples, correlations)
```

### Feature 3: Enhanced Heatmap Export

**File:** `analytics/sensitivity_heatmap.py` (EXTEND)

```python
# Add to existing code:

def export_heatmap_to_excel(
    df: pd.DataFrame,
    filename: str,
    title: str = "Two-Way Sensitivity Analysis",
) -> None:
    """
    Export heatmap data to Excel with formatting.

    Creates:
    - Data sheet: Raw sensitivity matrix
    - Chart sheet: Conditional formatting (red=low, green=high)
    """
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sensitivity Data")

        # Add conditional formatting
        workbook = writer.book
        worksheet = writer.sheets["Sensitivity Data"]

        # Color scheme: Red (low) → Yellow (mid) → Green (high)
        # Standard for lender presentations
```

---

## PHASE 4: DOCUMENTATION (2 hours) 📖 PRIORITY 4

### Document 1: SENSITIVITY_ARCHITECTURE.md

```markdown
# Sensitivity Analysis Architecture

## When to Use

| Method | Use Case | Output | Time |
|--------|----------|--------|------|
| **Tornado** | Rank parameter importance | Bar chart + ranking | 1 sec |
| **Breakeven** | Find minimum requirement (e.g., tariff) | Single value | 5 sec |
| **Monte Carlo** | Probability distribution, tail risk | P10/P50/P90 | 30 sec |
| **Two-Way Heatmap** | Parameter interaction effects | Matrix + chart | 10 sec |

## Integration with Monte Carlo

Both engines use the same `run_v14_pipeline()`:
- Tornado: Deterministic, fixed shocks
- Monte Carlo: Stochastic, sampled parameters

Result: **Consistent KPI surface**, different perspectives on risk.

## Best Practices

1. **Always start with tornado** – Identify key drivers quickly
2. **Use MC for tail risk** – Probability of covenant breach
3. **Document assumptions** – Parameter ranges, correlations
4. **Validate against history** – Compare to past projects
```

### Document 2: Parameter Definition Template

**File:** `scenarios/sensitivity_parameters_template.yaml`

```yaml
# Template for defining sensitivity parameters
# Reference: NREL Solar Proforma Handbook, Damodaran

parameters:
  # CAPEX Parameters
  - variable_name: "project.capex_usd_per_kw"
    description: "Total project capital cost per kW"
    base_value: 1200.0  # USD/kW (typical for 2025 utility-scale solar)
    low_pct: -20.0      # -20% scenario (cost learning curve)
    high_pct: 20.0      # +20% scenario (supply chain risk)
    unit: "USD/kW"
    industry_benchmark:
      p25: 1000.0
      p50: 1200.0
      p75: 1500.0
    references:
      - "IRENA (2023): Renewable Cost Database"
      - "NREL Annual Technology Baseline"

  # Operational Parameters
  - variable_name: "project.tariff_lkr_per_kwh"
    description: "PPA tariff rate"
    base_value: 12.5
    low_pct: -15.0      # Downside: market compression
    high_pct: 15.0      # Upside: long-term escalation
    unit: "LKR/kWh"
    # Add correlations (see sensitivity_correlations.yaml)

  # Financing Parameters
  - variable_name: "finance.tenor_years"
    description: "Debt tenor"
    base_value: 18.0
    low_pct: -15.0      # Shorter tenor (stricter lender)
    high_pct: 15.0      # Longer tenor (favorable terms)
    unit: "years"
```

---

## PHASE 5: ADVANCED FEATURES (Optional, Sprint 10+) 🚀

### Feature: Scenario Recommendation Engine

```python
def recommend_scenarios(
    tornado_suite,
    mc_results,
    n_scenarios: int = 3,
) -> dict[str, dict[str, float]]:
    """
    Recommend Conservative / Base / Optimistic parameter sets
    based on tornado rankings and MC distribution.

    Returns:
        {
            "conservative": {"tariff_pct": -10, "capex_pct": +15, ...},
            "base": {"tariff_pct": 0, "capex_pct": 0, ...},
            "optimistic": {"tariff_pct": +15, "capex_pct": -10, ...},
        }
    """
```

### Feature: Lender Report Generation

```python
def generate_lender_report(
    scenario_result,
    tornado_suite,
    mc_results,
    output_path: str,
) -> None:
    """
    Auto-generate PowerPoint deck with:
    - Risk matrix
    - Tornado chart
    - Probability waterfall (covenant breach)
    - Debt structure summary

    Compliance: IFC E&S, Moody's methodology
    """
```

---

## 📋 EXECUTION CHECKLIST

```
PHASE 1: Critical Fixes
  ☐ Fix sensitivity_heatmap.py syntax (2 missing parens)
  ☐ Update type hints (Dict → dict) in sensitivity_v14.py
  ☐ Verify parameter_solvers.py has no circular imports
  ☐ Run all tests: pytest tests/ -v → 282+ passing

PHASE 2: Integration Testing
  ☐ Create test_monte_carlo_sensitivity_integration.py
  ☐ Verify tornado + MC ranges align
  ☐ Check DSCR tracking across both engines
  ☐ Coverage: sensitivity_v14.py → 85%+

PHASE 3: Feature Completeness
  ☐ Implement sensitivity_tail_risk.py (covenant breach prob)
  ☐ Create sensitivity_correlations.yaml template
  ☐ Extend sensitivity_heatmap.py for Excel export
  ☐ Update sensitivity_visualization.py for modern matplotlib

PHASE 4: Documentation
  ☐ Write SENSITIVITY_ARCHITECTURE.md
  ☐ Create parameter definition template
  ☐ Document correlation assumptions
  ☐ Update README in analytics/sensitivity/

PHASE 5: Advanced (Optional, Sprint 10+)
  ☐ Scenario recommendation engine
  ☐ Lender report generation
  ☐ Real-time dashboard integration
```

---

## 🎯 SUCCESS CRITERIA

By end of Phase 3, the system should:

✅ **Correctness:**
- 282+ tests passing
- Zero Pydantic v2 warnings
- Zero circular imports

✅ **Integration:**
- Tornado + MC produce consistent KPI results
- Both engines track DSCR covenant status
- Parameter perturbations work in both paths

✅ **Usability:**
- Clear parameter templates (YAML)
- Documented best practices
- Lender-friendly outputs (tornado, heatmap, risk scores)

✅ **Maintainability:**
- Type hints 90%+ coverage
- Docstrings for all public functions
- No dead code or stubs

---

**Status: Ready for Phase 1 Implementation** 🚀
