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

    base_fx_rate: float
    annual_depr_min: float
    annual_depr_max: float
    depr_steps: int
    shock_scenarios: list[dict[str, float]] | None = None
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

All affected tests use pytest import checks to skip gracefully when functions are unavailable.

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
