# Missing Functions - Sprint 18+ Backlog

**Status:** To Be Implemented  
**Priority:** Medium (tests are skipped, not blocking)  
**Created:** 2025-12-24  
**Last Updated:** 2025-12-24

---

## Overview

This document tracks 4 missing functions that are referenced in tests but not yet implemented. These are Sprint 18+ features that require dedicated implementation effort.

**Impact:** Non-blocking - affected tests are automatically skipped when functions are unavailable.

---

## Missing Functions

### 1. `size_debt_with_dual_dscr`

**Module:** `finance.debt_v14`  
**Purpose:** Debt sizing with dual DSCR constraints (operational + prudential)  
**Affected Tests:**
- `tests/analytics/test_dscr_sensitivity.py`
- `tests/finance/test_debt_dual_dscr.py`
- `tests/integration/test_dual_dscr_integration.py`
- `tests/integration/test_pipeline_end_to_end.py`

**Expected Signature:**
```python
def size_debt_with_dual_dscr(
    cashflows: list[float],
    dscr_operational: float,
    dscr_prudential: float,
    interest_rate: float,
    tenor_years: int,
    construction_years: int = 0,
) -> dict[str, Any]:
    """
    Size debt capacity using dual DSCR constraints.
    
    Returns:
        dict with keys:
        - max_debt: float
        - operational_limit: float
        - prudential_limit: float
        - binding_constraint: str
        - debt_schedule: list[dict]
    """
    ...
```

**Implementation Notes:**
- Must respect both operational (e.g., 1.30x) and prudential (e.g., 1.50x) DSCR thresholds
- Return binding constraint (which DSCR is tighter)
- Generate full debt schedule with principal/interest breakdown
- Consider construction period with interest-only payments

**Related:** DSCR sensitivity analysis, lender prudential requirements

---

### 2. `analyze_tax_optimization_sensitivity`

**Module:** `analytics.tax_sensitivity_v14`  
**Purpose:** Sensitivity analysis for tax optimization parameters  
**Affected Tests:**
- `tests/analytics/test_tax_sensitivity.py`

**Expected Signature:**
```python
def analyze_tax_optimization_sensitivity(
    base_config: dict[str, Any],
    parameters: list[str],
    ranges: dict[str, tuple[float, float, int]],
    metric: str = "equity_irr",
) -> SensitivitySuite:
    """
    Run sensitivity analysis on tax optimization parameters.
    
    Parameters:
    - base_config: Scenario configuration
    - parameters: List of tax params (e.g., ['tax_rate', 'depreciation_years'])
    - ranges: Parameter ranges as {param: (min, max, steps)}
    - metric: Output metric to analyze
    
    Returns:
        SensitivitySuite with tornado results
    """
    ...
```

**Implementation Notes:**
- Support tax_rate, depreciation_years, loss_carryforward_years
- Integrate with existing `analytics.sensitivity.engine`
- Use `TornadoResult` contract from `contracts_v14`
- Consider tax shield effects and timing

**Related:** Tax optimization, accelerated depreciation, loss carryforward

---

### 3. `FXSensitivityConfig`

**Module:** `analytics.fx_sensitivity_real`  
**Purpose:** Configuration dataclass for FX sensitivity analysis  
**Affected Tests:**
- `tests/analytics_layer/test_fx_sensitivity_real.py`

**Expected Definition:**
```python
@dataclass(frozen=True)
class FXSensitivityConfig:
    """Configuration for FX sensitivity analysis."""
    
    base_fx_rate: float  # LKR/USD at start
    annual_depr_min: float  # Min annual depreciation (e.g., 0.0)
    annual_depr_max: float  # Max annual depreciation (e.g., 0.10)
    depr_steps: int  # Number of steps (e.g., 5)
    
    # Optional: shock scenarios
    shock_scenarios: list[dict[str, float]] | None = None
    
    # Metrics to track
    metrics: list[str] = field(default_factory=lambda: ["equity_irr", "dscr_min"])
```

**Implementation Notes:**
- Must integrate with `analytics.fx_curve` for time-varying FX
- Support both gradual depreciation and shock scenarios
- Consider USD debt exposure vs LKR revenue
- Output should be `SensitivitySuite` compatible

**Related:** FX risk, currency mismatch, lender covenants

---

### 4. `extract_cashflow_params`

**Module:** `finance.cashflow_v14_params`  
**Purpose:** Extract cashflow parameters from scenario config for reuse  
**Affected Tests:**
- `tests/integration/test_degradation_flow.py`

**Expected Signature:**
```python
def extract_cashflow_params(
    config: dict[str, Any],
    validation_mode: str = "strict",
) -> dict[str, Any]:
    """
    Extract and normalize cashflow parameters from config.
    
    Returns:
        dict with keys:
        - capex_usd: float
        - opex_annual_usd: float
        - generation_mwh_annual: float
        - tariff_usd_per_mwh: float
        - fx_start_lkr_per_usd: float
        - fx_annual_depr: float
        - degradation_rate_annual: float
        - discount_rate: float
    """
    ...
```

**Implementation Notes:**
- Validate all required parameters present
- Apply defaults for optional params
- Convert legacy config formats to v14 structure
- Raise `ValueError` with clear messages on validation failures

**Related:** Config normalization, parameter extraction, validation

---

## Test Skip Strategy

All affected tests use pytest's `importlib` check to skip gracefully:

```python
import importlib.util
import pytest

# Check if function is available
spec = importlib.util.find_spec("finance.debt_v14")
if spec is not None:
    try:
        from finance.debt_v14 import size_debt_with_dual_dscr
        HAS_DUAL_DSCR = True
    except ImportError:
        HAS_DUAL_DSCR = False
else:
    HAS_DUAL_DSCR = False

@pytest.mark.skipif(not HAS_DUAL_DSCR, reason="size_debt_with_dual_dscr not implemented")
def test_dual_dscr_sizing():
    ...
```

**Current Skip Count:** 3 integration tests + 4 unit test modules

---

## Implementation Priority

### High Priority (Sprint 19)
1. **`size_debt_with_dual_dscr`** - Critical for lender modeling
2. **`FXSensitivityConfig`** - Important for currency risk analysis

### Medium Priority (Sprint 20)
3. **`analyze_tax_optimization_sensitivity`** - Tax strategy optimization
4. **`extract_cashflow_params`** - Config refactoring support

---

## Implementation Checklist

For each function:
- [ ] Create implementation file with function
- [ ] Add comprehensive docstring with examples
- [ ] Write unit tests (minimum 5 test cases)
- [ ] Add integration test
- [ ] Update `__all__` exports
- [ ] Update this document (move to "Completed" section)
- [ ] Verify affected tests now pass
- [ ] Update CI configuration if needed

---

## Related Documentation

- [Sprint 18 Implementation Plan](SPRINT_18_IMPLEMENTATION_PLAN.md)
- [Dolphin Strategy](SPRINT_9_HANDOVER.md)
- [GWTF Compliance](compliance/GWTF_COMPLIANCE.md)

---

## Notes

- These functions were identified during Sprint 18 Dolphin Strategy implementation
- All are **non-blocking** - main codebase works without them
- Tests skip gracefully with clear messages
- Priority based on user/lender requirements
- Implementation should follow GWTF/CESSPIT/CASPER patterns

---

**Maintained by:** DutchBay EPC Model Team  
**Review Cadence:** Every sprint planning session  
**Last Reviewed:** Sprint 18 (2025-12-24)
