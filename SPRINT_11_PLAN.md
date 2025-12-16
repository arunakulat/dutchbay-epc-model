# Sprint 11 - Phase 1-2 Migration Planning

**Start Date:** December 16, 2025
**Target Duration:** 1-2 sprints
**Branch:** `sprint-11`
**Base:** Sprint 10 (v14.0.1)

---

## Executive Summary

Migrate Phase 1-2 tax and WACC modules from legacy to v14 architecture. These modules are currently stubbed/skipped and need implementation to support:
- Tax holiday calculations
- Depreciation schedule management
- WACC (Weighted Average Cost of Capital) integration
- Interest deductibility modeling

---

## Current State (Sprint 10)

### ✅ Working
- Monte Carlo simulations (v14.0.1)
- Cashflow calculations
- Risk haircuts
- Covenants analysis
- Sensitivity analysis
- CASPER tail risk

### ⚠️ Deferred (Awaiting Phase 1-2 Migration)
```
Legacy modules (not migrated):
  ❌ finance.tax_profile
  ❌ finance.wacc_integration
  
Test status:
  SKIPPED: tests/test_phase_1_2_refactoring.py
  (47 tests, awaiting implementation)
```

---

## Sprint 11 Objectives

### Phase 1: Tax Profile Implementation
**Goal:** Implement `finance/tax_profile.py` module

#### Sub-tasks
1. **TaxProfile Class**
   - [ ] Create frozen dataclass
   - [ ] Validate tax_rate (0.0 to 1.0)
   - [ ] Tax holiday year management
   - [ ] Interest deductibility flag
   - [ ] Unit tests (6 tests)

2. **DepreciationSchedule Class**
   - [ ] Build straight-line schedule
   - [ ] Calculate book value trajectory
   - [ ] Handle project life mismatches
   - [ ] Unit tests (3 tests)

3. **Tax Calculation Engine**
   - [ ] Calculate taxable income
   - [ ] Apply tax holidays
   - [ ] Interest deductibility shield
   - [ ] Depreciation handling
   - [ ] Unit tests (10 tests)

4. **Integration Tests**
   - [ ] 3-year holiday + 20-year depreciation
   - [ ] Lender case scenarios
   - [ ] Stress scenarios
   - [ ] Integration tests (3 tests)

**Acceptance Criteria:**
- ✅ 22 tests passing
- ✅ All backward compatibility maintained
- ✅ Type hints complete
- ✅ Docstrings for all public methods

### Phase 2: WACC Integration
**Goal:** Implement `finance/wacc_integration.py` module

#### Sub-tasks
1. **WACC Components**
   - [ ] WaccComponents dataclass
   - [ ] CAPM beta calculations
   - [ ] Cost of equity (CoE)
   - [ ] Cost of debt (after-tax adjustment)
   - [ ] Unit tests (2 tests)

2. **WACC Calculation**
   - [ ] Nominal WACC formula
   - [ ] Real WACC (inflation-adjusted)
   - [ ] Prudential rate (100 bps buffer)
   - [ ] Unit tests (3 tests)

3. **Integration with IRR/NPV**
   - [ ] Compare project IRR vs WACC
   - [ ] Value creation/destruction metric
   - [ ] Margin in basis points
   - [ ] Unit tests (2 tests)

4. **Integration Tests**
   - [ ] Full scenario with WACC overlay
   - [ ] Backward compatibility
   - [ ] Scenario comparisons
   - [ ] Integration tests (1 test)

**Acceptance Criteria:**
- ✅ 8 tests passing
- ✅ All backward compatibility maintained
- ✅ Type hints complete
- ✅ Docstrings for all public methods

### Phase 3: Test Suite Enablement
**Goal:** Enable `tests/test_phase_1_2_refactoring.py`

#### Sub-tasks
1. [ ] Remove `pytest.mark.skip` from module
2. [ ] Verify all 47 tests pass
3. [ ] Add to CI/CD pipeline
4. [ ] Document Phase 1-2 contract

**Acceptance Criteria:**
- ✅ All 47 tests enabled and passing
- ✅ Integration with v14 architecture validated
- ✅ Performance within acceptable bounds

---

## Architecture Notes

### Design Principles
1. **Immutability:** TaxProfile and WaccComponents as frozen dataclasses
2. **Validation:** Comprehensive input validation with clear error messages
3. **Separation of Concerns:** Tax and WACC logic isolated from pipeline
4. **Backward Compatibility:** v1 behavior preserved for zero tax_rate scenarios
5. **Type Safety:** Full type hints throughout

### Integration Points
```
v14 Pipeline
    ↓
┌─────────────────────────────────┐
│ Cashflow Calculation v14        │
├─────────────────────────────────┤
│ • Build annual rows             │
│ • Calculate CFADS               │
│ • Apply risk haircuts           │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ TAX PROFILE (Sprint 11)         │  ← NEW
├─────────────────────────────────┤
│ • Tax holiday handling          │
│ • Depreciation schedule         │
│ • Interest deductibility        │
│ • Taxable income calculation    │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Post-Tax CFADS                  │
│ (v14 already working)           │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ WACC INTEGRATION (Sprint 11)    │  ← NEW
├─────────────────────────────────┤
│ • CAPM beta calculations        │
│ • Cost of equity/debt           │
│ • WACC calculation              │
│ • Value creation metrics        │
└────────┬────────────────────────┘
         ↓
    Metrics & KPIs
```

### File Structure
```
finance/
├── tax_profile.py        (Sprint 11) - NEW
│   ├── TaxProfile class
│   ├── DepreciationSchedule class
│   └── Tax calculation functions
├── wacc_integration.py   (Sprint 11) - NEW
│   ├── WaccComponents class
│   ├── WACC calculation functions
│   └── Integration functions
├── cashflow_v14.py       (v14.0.1 ✅)
├── covenants.py          (v14.0.1 ✅)
└── ...

tests/
├── test_phase_1_2_refactoring.py (Currently SKIPPED)
│   ├── TestPhase1TaxProfile (22 tests)
│   ├── TestPhase2WaccIntegration (8 tests)
│   └── TestBackwardCompatibility (3 tests)
└── ...
```

---

## Risk Assessment

### High Priority Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Tax holiday interactions | Medium | Comprehensive unit tests |
| Depreciation schedule edge cases | Medium | Boundary testing |
| WACC CAPM assumptions | Medium | Document assumptions |
| Backward compatibility | High | Test v1 behavior scenarios |

### Medium Priority Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Floating point precision | Low | Use pytest.approx() |
| Performance regression | Low | Benchmark against v1 |
| Documentation gaps | Low | Comprehensive docstrings |

---

## Success Criteria

### Code Quality
- ✅ 33 new tests passing (22 tax + 8 wacc + 3 compat)
- ✅ Zero regressions in existing 277 tests
- ✅ Type hints 100% complete
- ✅ Docstrings for all public APIs
- ✅ Code coverage > 90%

### Performance
- ✅ No degradation in cashflow calculation speed
- ✅ WACC calculation < 100ms per scenario
- ✅ Tax calculation < 50ms per year

### Documentation
- ✅ API reference for TaxProfile
- ✅ API reference for WaccComponents
- ✅ Integration guide with examples
- ✅ Migration guide from v1

### Backward Compatibility
- ✅ All v1 scenarios still work
- ✅ Deprecation path clear for old APIs
- ✅ No breaking changes to public interface

---

## Implementation Strategy

### Phase 1a: Tax Profile (Days 1-3)
```bash
# Branch: sprint-11-tax-profile
git checkout -b sprint-11-tax-profile

# Create tax_profile.py
# Implement:
#  - TaxProfile class + tests
#  - DepreciationSchedule class + tests
#  - Basic tax calculation

# Run tests
pytest tests/finance/test_cashflow_v14_tax_refactored.py -v

# If passing: Create PR for review
```

### Phase 1b: Tax Integration (Days 4-5)
```bash
# Branch: sprint-11-tax-integration
git checkout -b sprint-11-tax-integration

# Complete tax calculation engine
# Add integration tests
# Handle edge cases

# Merge back to sprint-11
```

### Phase 2a: WACC Implementation (Days 6-7)
```bash
# Branch: sprint-11-wacc-implementation
git checkout -b sprint-11-wacc-implementation

# Implement wacc_integration.py
# WACC calculations
# Value creation metrics

# Run tests
pytest tests/finance/test_cashflow_v14_tax_refactored.py -v
```

### Phase 2b: WACC Integration (Days 8-9)
```bash
# Branch: sprint-11-wacc-integration
git checkout -b sprint-11-wacc-integration

# Complete integration
# Enable test_phase_1_2_refactoring.py
# Final validation

# Merge back to sprint-11
```

### Final Validation (Day 10)
```bash
# On sprint-11 branch
git checkout sprint-11

# Run full test suite
pytest -m "not slow" -v

# Expected: 310+ tests passing (277 existing + 33 new)

# If all green: Create PR to main
# Request review from team
```

---

## Definitions of Done

### Per Phase
**Phase 1 (Tax):**
- [ ] TaxProfile class implemented
- [ ] DepreciationSchedule implemented
- [ ] 22 unit tests passing
- [ ] Backward compatibility verified
- [ ] Code review passed

**Phase 2 (WACC):**
- [ ] WaccComponents class implemented
- [ ] WACC calculations working
- [ ] 8 unit tests passing
- [ ] Value creation metrics functional
- [ ] Code review passed

**Phase 3 (Integration):**
- [ ] test_phase_1_2_refactoring.py fully enabled
- [ ] All 47 tests passing
- [ ] Integration with v14 validated
- [ ] Performance benchmarked
- [ ] Documentation complete

---

## Testing Strategy

### Unit Tests (22 for Tax, 8 for WACC)
```python
# Example structure
class TestTaxProfile:
    def test_creation_valid(self): ...
    def test_frozen_immutability(self): ...
    def test_validation_tax_rate_bounds(self): ...
    def test_tax_holiday_years(self): ...
    ...

class TestDepreciationSchedule:
    def test_straight_line_basic(self): ...
    def test_book_value_trajectory(self): ...
    def test_project_life_mismatch(self): ...

class TestTaxCalculation:
    def test_basic_calculation(self): ...
    def test_holiday_effect(self): ...
    def test_interest_deductibility(self): ...
    ...
```

### Integration Tests (3 for Tax, 1 for WACC)
```python
class TestIntegrationScenarios:
    def test_lender_case_strong_cfads(self): ...
    def test_stressed_scenario_low_cfads(self): ...
    def test_tax_wacc_combined_pipeline(self): ...
```

### Regression Tests
```bash
# Ensure existing 277 tests still pass
pytest tests/ -m "not slow" -v
# Expected: 277 passed (no new failures)
```

---

## Timeline Estimate

| Phase | Task | Days | Status |
|-------|------|------|--------|
| **1a** | Tax Profile Implementation | 3 | TODO |
| **1b** | Tax Integration & Edge Cases | 2 | TODO |
| **2a** | WACC Implementation | 2 | TODO |
| **2b** | WACC Integration | 2 | TODO |
| **3** | Final Validation & Testing | 1 | TODO |
| | **TOTAL** | **10 days** | |

**Estimated Completion:** ~2 weeks (Dec 23-27 + Jan 6-10)

---

## Dependencies & Prerequisites

### Code Dependencies
- ✅ v14 architecture (Sprint 10 complete)
- ✅ Cashflow module (working)
- ✅ Covenants module (working)
- ✅ Risk haircuts (working)

### Knowledge Dependencies
- [ ] Review `tests/test_phase_1_2_refactoring.py` for contract
- [ ] Understand tax holiday logic
- [ ] Understand WACC/CAPM formulas
- [ ] Review v1 implementations for reference

### Infrastructure Dependencies
- ✅ pytest infrastructure (working)
- ✅ CI/CD pipeline (working)
- ✅ Type checking (mypy configured)

---

## Communication Plan

### Daily
- [ ] Update progress in commit messages
- [ ] Document blockers or questions

### Per Phase
- [ ] Create PR with test results
- [ ] Request code review
- [ ] Document design decisions

### Sprint End
- [ ] Create release notes (like Sprint 10)
- [ ] Update version number (14.0.2)
- [ ] Merge to main
- [ ] Tag release

---

## References & Resources

### Tax Profile References
- See: `tests/test_phase_1_2_refactoring.py` (TestPhase1TaxProfile)
- See: `tests/finance/test_cashflow_v14_tax_refactored.py` (already passing)

### WACC References
- See: `tests/test_phase_1_2_refactoring.py` (TestPhase2WaccIntegration)
- CAPM Formula: `CoE = Rf + β(Rm - Rf)`
- WACC Formula: `WACC = (E/V × CoE) + (D/V × CoD × (1 - Tc))`

### v1 Implementation References
- Legacy tax calculations (for backward compatibility testing)
- Legacy WACC calculations

---

## Next Steps

1. ✅ **Create sprint-11 branch** ← DONE
2. ✅ **Review this plan**
3. [ ] **Pull sprint-11 locally**
4. [ ] **Create sprint-11-tax-profile sub-branch**
5. [ ] **Start Phase 1a implementation**

---

**Sprint 11 Kickoff:** December 16, 2025
**Branch:** `sprint-11`
**Status:** 🚀 READY TO START
