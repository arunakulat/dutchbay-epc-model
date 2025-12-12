# DutchBay EPC Model v14 - Canonical Codebase Snapshot
**Date:** 2025-12-12T08:44 UTC
**Status:** PRODUCTION (Swimlane 2 Phase 1 Complete, Phase 2 Pending)
**Repository:** https://github.com/arunakulat/dutchbay-epc-model

---

## Executive Summary

This document is the **canonical codebase index** for the DutchBay EPC Model v14. It captures:

- **File structure** and module organization (164 core files across analytics, finance, tests, config)
- **Dependency graph** showing all module relationships, imports, and call chains
- **Current state** of Swimlane 2 (Phase 1 FX complete, Phase 2 sensitivity refactor pending)
- **Phase 2 readiness** assessment with task breakdown, dependencies, and acceptance criteria
- **GWTF compliance** status (Gateway pattern adherence)

This is the authoritative reference for Swimlane 2 Phase 2 work (SENS-001..006).

---

## 1. Codebase Inventory

### Total Stats
- **Total files in repo:** 337
- **Relevant files (analytics/finance/tests/config):** 164
- **Python scripts:** 156
- **Test files:** 90

### Folder Breakdown

| Folder | Files | Category | Status |
|--------|-------|----------|--------|
| analytics | 50 | Analytics layer (sensitivity, evaluation, schema validation) | Stable + Phase 2 pending |
| finance | 18 | Finance engine (cashflow, FX, debt, equity, WACC, IRR) | Stable (Phase 1 complete) |
| tests | 90 | Unit + integration + API tests | All passing (no coverage gate) |
| config | 5 | Hydra configuration files | Stable |
| api | 1 | API entry point | Stable |

### Key Scripts by Layer

#### Finance Layer (Core Engine)
- `finance/cashflow_v14.py` (19.5 KB) - Annual cashflow, CFADS, post-tax calculation
- `finance/cashflow_v14_params.py` (18.7 KB) - Parameter extraction & validation
- `finance/cashflow_v14_tax.py` (14.7 KB) - Tax profile & depreciation
- `finance/fx_v14.py` (8.3 KB) - **NEW Phase 1**: FX curve generation (scalar + structured)
- `finance/cashflow_v14_fx.py` (4.7 KB) - FX adapter (routes to fx_v14)
- `finance/debt_v14.py` (16.6 KB) - Debt servicing & coverage ratios
- `finance/equity_v14.py` (12.7 KB) - Equity metrics
- `finance/wacc_v14.py` (20 KB) - WACC calculation
- `finance/irr.py` (12.3 KB) - Internal rate of return

#### Analytics Layer (Gateway + Sensitivity + Validation)
- `analytics/evaluation_v14.py` (41 KB) - **GATEWAY** (single entry point to finance)
- `analytics/sensitivity_v14.py` (67.8 KB) - **NEEDS REFACTOR** (Phase 2 SENS-002)
- `analytics/contracts_v14.py` (42.5 KB) - CCCDIR dataclass contracts
- `analytics/schema_guard.py` (18.8 KB) - Config validation + FX block checker
- `analytics/pipeline_v14.py` (14.5 KB) - Pipeline orchestrator
- `analytics/monte_carlo_v14.py` (41 KB) - CASPER tail risk analysis
- `analytics/config_schema.py` (3.7 KB) - Schema enforcement
- Various sensitivity sub-modules (dashboard, export, visualization, etc.)

#### Test Layer
- 90 test files covering: FX validation, cashflow, schema guard, sensitivity, risk haircut, etc.
- **All FX + cashflow tests passing** (as of Sprint 10 completion)
- **No coverage gate enforced** (ignore 55% threshold during Phase 2)

---

## 2. Module Dependency Graph

### Canonical Relationships

```
┌─────────────────────────────────────────────────────────────────────┐
│                  External Callers (CLI, API, UI)                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              analytics/pipeline_v14 → evaluation_v14                │
│                    (Orchestration Gateway)                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
        ┌──────────────────────┐  ┌──────────────────────┐
        │ Sensitivity Analysis │  │ Finance Dispatch     │
        │ (Phase 2 pending)    │  │ (Stable)             │
        │                      │  │                      │
        │ sensitivity_v14.py   │  │ cashflow_v14         │
        │ (GWTF refactor)      │  │ debt_v14             │
        └──────────┬───────────┘  │ equity_v14           │
                   │              │ wacc_v14             │
        MUST USE→  │              │ irr.py               │
        evaluation │              │                      │
        _v14.py    │              └──────────┬───────────┘
                   │                         │
                   └─────────────┬───────────┘
                                 │
                    ┌────────────┴───────────┐
                    ▼                        ▼
            ┌────────────────────┐  ┌──────────────────┐
            │  Finance Core      │  │  Schema Validation│
            │                    │  │                  │
            │ cashflow_v14       │  │ schema_guard.py  │
            │ → cashflow_v14_fx  │  │ contracts_v14    │
            │   → fx_v14 ✓       │  │ (Phase 1 complete)│
            │ → cashflow_v14_tax │  └──────────────────┘
            │ → debt, equity,    │
            │   wacc, irr        │
            └────────────────────┘
```

### Import Rules (GWTF)

**✅ ALLOWED:**
- Analytics → Analytics: `from analytics.* import ...` ✓
- Analytics → Finance (via gateway): `from analytics.evaluation_v14 import evaluate_with_overrides` ✓
- Finance → Finance: `from finance.* import ...` ✓
- Tests → Anything: Full freedom ✓

**❌ FORBIDDEN:**
- Analytics → Finance (direct): `from finance.cashflow_v14 import ...` ❌ **VIOLATION IN SENS-002**
- Finance → Analytics: Never ✓

### Current GWTF Violations

**CRITICAL - Phase 2 Task SENS-002:**
- `analytics/sensitivity_v14.py` imports from `finance.cashflow_v14`, `finance.debt_v14`, etc. directly
- Must be refactored to use `evaluate_with_overrides()` gateway call only

---

## 3. FX Foundation Status (Phase 1 - COMPLETE)

### What Was Built
- **`finance/fx_v14.py`** - New FX engine supporting two modes:
  - **Scalar mode:** Single `lkr_per_usd` rate for entire project life
  - **Structured mode:** `base_rate` + `escalation_pct` (annual escalation curve)
  - Both modes support negative escalation (appreciation) and zero escalation (flat)

- **`finance/cashflow_v14_fx.py`** - Thin adapter over fx_v14
  - Routes old `_fx_curve()` calls to new engine
  - Handles legacy `start_lkr_per_usd + annual_depr` mode (backward compat)
  - All tests passing

- **`analytics/schema_guard._validate_fx_block()`** - CESSPIT validation
  - Rejects scalar (legacy v13) FX configs at the front door
  - Validates structured mode ranges (-10% to +10% escalation)
  - Clear error messages for all invalid cases

### Test Coverage (Phase 1)
- ✅ `tests/finance/test_fx_v14.py`: 16+ unit tests, 100% coverage
- ✅ `tests/test_schema_guard_fx.py`: 30 validation tests, all passing
- ✅ `tests/analytics_layer/test_schema_guard_fx.py`: Integration tests passing
- ✅ All FX/cashflow scenario regression tests passing

### Current Test Run Status
```
Tests: 149 passed (FX + cashflow selection)
Files: All FX validation, scenario loading, cashflow, schema guard tests green
Regressions: None detected on dutchbay_lendercase_2025Q4.yaml and test scenarios
Coverage: Ignored (55% threshold waived during Phase 2)
```

---

## 4. Sensitivity Layer Status (Phase 2 - PENDING)

### Current State (GWTF Violation)
```python
# ❌ TODAY (VIOLATION)
analytics/sensitivity_v14.py:
    from finance.cashflow_v14 import build_cashflow  # FORBIDDEN
    from finance.debt_v14 import ...

    def analyze_sensitivity(...):
        # Direct calls to finance functions
        cf = build_cashflow(modified_config)
```

### Phase 2 Target (GWTF Compliant)
```python
# ✅ AFTER SENS-002 REFACTOR
analytics/sensitivity_v14.py:
    from analytics.evaluation_v14 import evaluate_with_overrides
    from analytics.contracts_v14 import ShockSpec, ShockResult

    def analyze_sensitivity(config_path: str, shocks: List[ShockSpec]) -> SensitivitySuite:
        for shock in shocks:
            overrides = {shock.variable_name: shock.low_value}
            kpis = evaluate_with_overrides(config_path, overrides)
            # Result uses ShockResult contract
        return SensitivitySuite(...)
```

---

## 5. Phase 2 Readiness Breakdown

### Tasks (Total 21 hours, all P0)

| ID | Task | Hours | Status | Blocker |
|----|------|-------|--------|---------|
| SENS-001 | Add ShockSpec + ShockResult to contracts_v14 | 2 | Pending | None |
| SENS-002 | Refactor sensitivity_v14 (gateway only, no finance imports) | 8 | Pending | SENS-001 |
| SENS-004 | Create lint test (enforce no finance imports) | 2 | Pending | SENS-002 |
| SENS-005 | Extend sensitivity tests (80%+ coverage, contracts) | 6 | Pending | SENS-001, SENS-002 |
| SENS-006 | QA: Validate tornado outputs backward compat | 3 | Pending | SENS-001, SENS-002, SENS-005 |

### Task Sequence (Critical Path)
```
SENS-001 (2h)
    ↓
SENS-002 (8h) + SENS-005 (6h) [parallel possible, but tests depend on refactor]
    ↓
SENS-004 (2h)
    ↓
SENS-006 (3h)

Estimated Timeline: ~19 hours sequential (21 total with parallelization)
```

### Acceptance Criteria (Consolidated)

**SENS-001 Done When:**
- ✅ `ShockSpec` and `ShockResult` dataclasses defined with full type hints
- ✅ Mypy --strict passes
- ✅ Both classes have docstrings explaining fields and usage
- ✅ Can be imported: `from analytics.contracts_v14 import ShockSpec, ShockResult`

**SENS-002 Done When:**
- ✅ Zero direct `from finance.*` imports (lint test must pass)
- ✅ All shock logic uses `ShockSpec` input / `ShockResult` output
- ✅ All finance calls route through `evaluate_with_overrides()`
- ✅ Tornado outputs match previous format/magnitudes (QA validation)
- ✅ 80%+ test coverage on sensitivity_v14.py

**SENS-004 Done When:**
- ✅ Test file `tests/lint/test_sensitivity_imports.py` exists
- ✅ Test fails if forbidden imports found, passes if clean
- ✅ Test is part of standard test suite (`pytest tests/lint/`)

**SENS-005 Done When:**
- ✅ 20+ tests in `tests/analytics_layer/test_sensitivity_v14.py`
- ✅ Tests cover ShockSpec creation, ShockResult calculation, gateway integration
- ✅ 80%+ code coverage on sensitivity_v14.py
- ✅ All tests pass on clean Phase 2 refactor

**SENS-006 Done When:**
- ✅ Tornado outputs match Phase 1 to <0.1% tolerance
- ✅ Variable rankings identical (same order in tornado chart)
- ✅ Tested on real scenarios: dutchbay_lendercase_2025Q4.yaml + 3+ others
- ✅ QA sign-off document created

---

## 6. Data Lake Reference

### Canonical Script Manifest
See `canonical_datalake_scripts.csv` for full inventory with:
- Filepath, folder, tier (core_engine, gateway, contract, validation)
- Exports (functions, dataclasses)
- Internal finance imports
- Internal analytics imports
- Status (stable, needs_refactor, deprecated_adapter)
- Phase completion

### Example: Core Scripts

| Script | Exports | Imports Finance | Imports Analytics | Status |
|--------|---------|-----------------|-------------------|--------|
| finance/cashflow_v14.py | build_annual_cfads, build_annual_rows, CashflowResult | cashflow_v14_params, cashflow_v14_fx, cashflow_v14_tax | none | stable |
| finance/fx_v14.py | build_fx_curve_scalar, build_fx_curve_structured, build_fx_curve_from_config | none | none | stable (Phase 1) |
| analytics/evaluation_v14.py | evaluate_with_overrides, evaluate_with_casper_tail_risk, evaluate_scenario | cashflow_v14, debt_v14, equity_v14, wacc_v14, irr | contracts_v14, schema_guard | stable (gateway) |
| analytics/sensitivity_v14.py | analyze_sensitivity, build_tornado_chart | ❌ TODO: remove | evaluation_v14, contracts_v14 | needs_refactor (Phase 2) |
| analytics/contracts_v14.py | ScenarioDescriptor, CashflowResult, EvaluationResult, CapitalRiskBundle, ShockSpec, ShockResult | none | none | stable + phase2 expansion |

---

## 7. Call Chain Reference

### Entry Point: External → Pipeline → Gateway

```
run_full_pipeline_v14.py (Hydra CLI)
  ↓
analytics.pipeline_v14.run_v14_pipeline(config_path: str)
  ↓
analytics.evaluation_v14.evaluate_scenario(config: dict)
  ↓ (returns EvaluationResult with all KPIs)
```

### Sensitivity Flow: Current (VIOLATION) vs. Target (Phase 2)

**TODAY (Phase 1 - GWTF VIOLATION):**
```
sensitivity_v14.analyze_sensitivity(config, shocks)
  → [VIOLATION] import finance.cashflow_v14
  → [VIOLATION] call build_cashflow(modified_config)
  → Direct manipulation of internal state
```

**AFTER PHASE 2 (GWTF COMPLIANT):**
```
sensitivity_v14.analyze_sensitivity(config_path: str, shocks: List[ShockSpec])
  → build override dict from ShockSpec
  → call analytics.evaluation_v14.evaluate_with_overrides(config_path, overrides)
  → construct ShockResult from returned KPIs
  → return SensitivitySuite (aggregate of ShockResults)
```

### FX Flow: Established (Phase 1)

```
finance.fx_v14.build_fx_curve_scalar(rate, years)
  OR
finance.fx_v14.build_fx_curve_structured(base_rate, escalation_pct, years)
  ↓ (returns List[float])

Used by:
finance.cashflow_v14_fx._fx_curve(config, years)
  → calls fx_v14 appropriately
  → adapter for backward compat
  ↓
finance.cashflow_v14.build_annual_rows()
  → uses FX curve in CFADS calc
```

---

## 8. GWTF Compliance Status

### Green Zones (Compliant)
- ✅ Finance layer (all internal imports)
- ✅ Gateway (evaluation_v14 → all finance dispatches correctly)
- ✅ Contracts (pure dataclasses, no imports)
- ✅ Schema guard (validation only)
- ✅ FX engine (new, clean, no analytics imports)
- ✅ Tests (full freedom)
- ✅ Pipeline (uses gateway)

### Red Zones (Violations)
- ❌ Sensitivity_v14 imports finance directly (CRITICAL - Phase 2 SENS-002 fix)

### Remediation Path
1. **SENS-001:** Define contracts (ShockSpec, ShockResult)
2. **SENS-002:** Refactor sensitivity to use contracts + gateway only
3. **SENS-004:** Add lint test to prevent regression
4. **SENS-005:** Comprehensive test coverage
5. **SENS-006:** Backward compatibility validation

After Phase 2: **100% GWTF Compliant**

---

## 9. Files Generated (Datalake)

The canonical codebase snapshot includes these CSV datalakes:

1. **canonical_codebase_index.csv** (164 rows)
   - All relevant files with filepath, folder, classification, size, modification date

2. **codebase_dependencies.csv** (20 rows)
   - All module relationships, import sources, target modules, relationship types
   - Flags GWTF violations

3. **canonical_datalake_scripts.csv** (7 rows)
   - Key scripts with exports, imports, status, tier, phase, GWTF notes

4. **canonical_call_chains.csv** (5 rows)
   - Named call chains: External→Pipeline, Sensitivity (current & target), FX, Gateway

5. **phase2_readiness_assessment.csv** (5 rows)
   - SENS-001..006 tasks with hours, priority, dependencies, acceptance count

---

## 10. Quick Start for Phase 2 Implementation

### Prerequisites
- DutchBay EPC Model repo cloned: `https://github.com/arunakulat/dutchbay-epc-model`
- Python 3.11+, pytest, mypy installed
- Current branch: latest from main (includes Phase 1 FX work)

### Step 1: SENS-001 (Contracts)
```bash
# 1. Open analytics/contracts_v14.py
# 2. Add at end:

from dataclasses import dataclass

@dataclass
class ShockSpec:
    """Specification for a single parameter shock."""
    variable_name: str          # e.g., "project.capacity_factor"
    base_value: float
    low_pct: float              # e.g., -10 for 10% downside
    high_pct: float             # e.g., +10 for 10% upside
    label: str | None = None

@dataclass
class ShockResult:
    """Result of a single shock impact analysis."""
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str            # e.g., "project_irr"

    @property
    def impact(self) -> float:
        """Two-way impact (high - low) / 2"""
        return (self.high_metric - self.low_metric) / 2.0

# 3. Test
pytest tests/analytics_layer/test_sensitivity_v14.py -v --no-cov -k "contract"
```

### Step 2: SENS-002 (Refactor)
```bash
# 1. Backup original
cp analytics/sensitivity_v14.py analytics/sensitivity_v14_phase1_backup.py

# 2. Open analytics/sensitivity_v14.py
# 3. Remove all: from finance.*
# 4. Add: from analytics.evaluation_v14 import evaluate_with_overrides
# 5. Refactor core functions to use evaluate_with_overrides() gateway
# 6. Update all function signatures with ShockSpec/ShockResult

# 7. Test
pytest tests/analytics_layer/test_sensitivity_v14.py -v --no-cov
```

### Step 3: SENS-004 (Lint)
```bash
# 1. Create tests/lint/test_sensitivity_imports.py
# 2. Add test:

def test_sensitivity_no_direct_finance_imports():
    src = Path('analytics/sensitivity_v14.py').read_text()
    forbidden = re.findall(r'from finance\.\S+|import finance\.\S+', src)
    assert not forbidden, f"Forbidden imports: {forbidden}"

# 3. Run
pytest tests/lint/test_sensitivity_imports.py -v --no-cov
```

### Step 4: SENS-005 & SENS-006
- Extend tests with contracts, gateway calls, backward compat validation
- Run full regression suite
- QA sign-off

---

## 11. Governance Standards

All Phase 2 work must comply with:

- **GWTF:** Analytics must use evaluation_v14 gateway for all finance access (no direct imports)
- **CCCDIR:** All public APIs use typed contracts (ShockSpec, ShockResult, etc.)
- **CESSPIT:** Config validated via schema_guard before processing
- **CASPER:** Results include tail risk and sensitivity together

---

## 12. Contacts & References

- **Repository:** https://github.com/arunakulat/dutchbay-epc-model
- **Swimlane 2 Strategy:** SWIMLANE-2-BOOTSTRAP-v1.0.md, SWIMLANE-2-QUICK-REF.md
- **Phase 2 Tasks:** swimlane_2_detailed_tasks.csv
- **Previous Sprint:** Sprint 10 - FX Foundation (COMPLETE)

---

**Generated:** 2025-12-12T08:49 UTC
**Canonical Status:** Active (effective until next codebase upload)
**Next Update:** Upon completion of Phase 2 SENS-001..006 tasks
