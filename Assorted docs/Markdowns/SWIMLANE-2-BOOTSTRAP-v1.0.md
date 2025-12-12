# Swimlane 2 Bootstrap & Handover Document
## DutchBay EPC Model - Risk & Sensitivity Analytics Layer

**Version:** 1.0.0
**Document Type:** Bootstrap & Handover (GWTF-Compliant)
**Date:** 2025-12-11
**Status:** PRODUCTION-READY
**Governance:** CCCDIR + CESSPIT + CASPER + GWTF v3.0

---

## Document Metadata

```yaml
document_id: SWIMLANE-2-BOOTSTRAP-v1.0.0
classification: Internal Technical Specification
authors:
  - Aruna Kulatunga (Lead Architect)
reviewers:
  - DutchBay EPC Model Team
  - Lender Advisory Committee
approvers:
  - Technical Steering Committee
compliance_frameworks:
  - CCCDIR: Config-Centric Contract-Driven Integration Rules
  - CESSPIT: Config-Enforced Schema Safety & Pipeline Integration Triad
  - CASPER: Capital Analytics, Sensitivity & Portfolio Evaluation Rigor
  - GWTF: Go With The Flow v3.0 (Governance Architecture)
revision_history:
  - version: 1.0.0
    date: 2025-12-11
    changes: Initial production release
    approved_by: Technical Steering Committee
```

---

## Executive Summary

**Purpose:** This document provides a complete bootstrap specification for Swimlane 2 of the DutchBay EPC Model v14 analytics stack. Swimlane 2 delivers the **Risk & Sensitivity Analytics Layer** — a lender-grade, contract-driven, gateway-compliant risk analysis framework.

**Scope:** FX validation hardening, sensitivity analysis refactor, and unified capital risk API.

**Audience:** Engineers implementing Swimlane 2, integration teams, QA, and technical auditors.

**Compliance:** All deliverables must satisfy CCCDIR, CESSPIT, CASPER, and GWTF v3.0 governance standards.

---

## Table of Contents

1. [Context & Strategic Positioning](#1-context--strategic-positioning)
2. [Governance Architecture](#2-governance-architecture)
3. [Phase 1: FX Foundation](#3-phase-1-fx-foundation)
4. [Phase 2: Sensitivity Rebuild](#4-phase-2-sensitivity-rebuild)
5. [Phase 3: Capital Risk Layer](#5-phase-3-capital-risk-layer)
6. [Integration Contract Specifications](#6-integration-contract-specifications)
7. [Test Specifications](#7-test-specifications)
8. [Handover Checklist](#8-handover-checklist)
9. [Appendices](#9-appendices)

---

## 1. Context & Strategic Positioning

### 1.1 Current State (Post-Sprint 10)

**Codebase Status:**
- ✅ `evaluation_v14.py` is the canonical gateway (single entry point)
- ✅ Monte Carlo + CASPER tail risk fully operational
- ✅ Sensitivity tornado analysis working but not gateway-compliant
- ⚠️ FX validation exists but not strict/structured
- ❌ Unified capital risk API does not exist
- ❌ Sensitivity module has direct finance imports (GWTF violation)

**Technical Debt:**
```python
# Current anti-pattern in sensitivity_v14.py
from finance.cashflow_v14 import build_cashflow  # ❌ FORBIDDEN
from finance.debt_v14 import compute_debt       # ❌ FORBIDDEN

# Target pattern (GWTF-compliant)
from analytics.evaluation_v14 import evaluate_with_overrides  # ✅ REQUIRED
```

### 1.2 Strategic Objectives

**Business Goals:**
1. Deliver lender-grade sensitivity analysis (tornado charts, VaR, CVaR)
2. Provide robust FX risk modeling for USD/LKR exposure
3. Create single unified API for all capital/risk analytics
4. Enable board-level risk reporting and DFI due diligence

**Technical Goals:**
1. Enforce GWTF gateway pattern across all analytics
2. Eliminate direct finance imports from analytics layer
3. Achieve 80%+ test coverage on new code
4. Maintain zero regressions in existing scenarios

### 1.3 Architectural Context Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INTERFACE                          │
│  (Dashboards, Excel Exports, DFI Reports, Board Decks)        │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│              SWIMLANE 2: RISK & SENSITIVITY LAYER              │
│                                                                 │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  FX Validation  │  │ Sensitivity  │  │ Capital Risk    │  │
│  │  & Curve Gen    │  │ Analysis     │  │ Bundle API      │  │
│  └─────────────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│           EVALUATION GATEWAY (evaluation_v14.py)               │
│  • evaluate_with_overrides()                                   │
│  • evaluate_with_casper_tail_risk()                           │
│  • (lazy proxy) run_monte_carlo_analysis()                    │
└──────────────────────────┬─────────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
┌──────────────────┐              ┌──────────────────┐
│  pipeline_v14.py │              │monte_carlo_v14.py│
│  (internal)      │              │   (internal)     │
└─────────┬────────┘              └─────────┬────────┘
          │                                 │
          └────────────┬────────────────────┘
                       ▼
        ┌──────────────────────────────┐
        │   FINANCE LAYER (v14)        │
        │  cashflow, debt, metrics,    │
        │  wacc, equity, schema_guard  │
        └──────────────────────────────┘
```

**GWTF Enforcement:**
- Swimlane 2 modules NEVER import finance modules directly
- All evaluation flows through `evaluation_v14.py`
- Finance layer is a black box to analytics layers

---

## 2. Governance Architecture

### 2.1 CCCDIR Compliance (Config-Centric Contract-Driven Integration)

**Principle:** All integration surfaces are defined by typed contracts in `contracts_v14.py`, not by ad-hoc dict passing.

**Swimlane 2 Contracts (New):**
```python
@dataclass
class ShockSpec:
    """CCCDIR-compliant shock specification."""
    variable_name: str  # e.g. "project.capacity_factor"
    base_value: float
    low_pct: float
    high_pct: float
    label: str | None = None

@dataclass
class ShockResult:
    """CCCDIR-compliant shock result."""
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str

    @property
    def impact(self) -> float:
        return (self.high_metric - self.low_metric) / 2.0

@dataclass
class CapitalRiskBundle:
    """CCCDIR-compliant unified risk bundle."""
    scenario: ScenarioDescriptor
    baseline_kpis: dict[str, float]
    wacc_result: WaccResult | None
    equity_result: EquityResult | None
    sensitivity_suite: SensitivitySuite | None
    monte_carlo: MonteCarloResult | None
    optimization_result: OptimizationResult | None
    metadata: dict[str, Any]
    timestamp: str
```

**Enforcement:**
- All public APIs accept/return typed dataclasses
- No `dict[str, Any]` in public signatures
- Mypy `--strict` must pass

### 2.2 CESSPIT Compliance (Config-Enforced Schema Safety)

**Principle:** All configs are validated before entering the finance engine.

**Swimlane 2 Validation Requirements:**

```python
# File: validation/schema_guard.py (extended)

def _validate_fx_block(config: dict) -> list[str]:
    """CESSPIT-compliant FX validation.

    Enforces:
    1. FX block exists
    2. Either scalar (lkr_per_usd) or structured (base_rate + escalation_pct)
    3. Rates are positive, escalation is reasonable (-10% to +10%)

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if 'fx' not in config:
        errors.append("CESSPIT violation: Missing 'fx' block")
        return errors

    fx = config['fx']

    # Scalar mode
    if 'lkr_per_usd' in fx:
        rate = fx['lkr_per_usd']
        if not isinstance(rate, (int, float)) or rate <= 0:
            errors.append(f"CESSPIT violation: fx.lkr_per_usd must be positive, got {rate}")

    # Structured mode
    elif 'base_rate' in fx and 'escalation_pct' in fx:
        if fx['base_rate'] <= 0:
            errors.append("CESSPIT violation: fx.base_rate must be positive")
        if not -10 <= fx['escalation_pct'] <= 10:
            errors.append("CESSPIT violation: fx.escalation_pct must be in [-10, 10]")

    else:
        errors.append("CESSPIT violation: fx block must have 'lkr_per_usd' or 'base_rate'+'escalation_pct'")

    return errors
```

**Integration Point:**
```python
# In evaluation_v14.py
def evaluate_with_overrides(config_path, overrides, validation_mode="strict"):
    # ... load config ...

    # CESSPIT enforcement
    if validation_mode == "strict":
        errors = validate_config_for_v14(
            config,
            validation_mode="strict",
            modules=["fx", "cashflow", "debt", "metrics"],
        )
        if errors:
            raise ValueError(f"CESSPIT validation failed: {errors}")

    # ... proceed with evaluation ...
```

### 2.3 CASPER Compliance (Capital Analytics Rigor)

**Principle:** All risk analytics must be traceable, auditable, and lender-grade.

**CASPER Requirements for Swimlane 2:**

1. **Tail Risk Enrichment:**
   - Every sensitivity result can be enriched with VaR/CVaR from MC
   - Breach probabilities relative to covenant thresholds
   - P10/P50/P90 distributions

2. **Tornado Standardization:**
   - Consistent column names: `Variable`, `Base`, `Low`, `High`, `Impact`, `Direction`
   - Additional tail risk columns: `VaR_90`, `CVaR_90`, `P10`, `P90`, `BreachProb`

3. **Metadata Provenance:**
   - Every sensitivity run records: timestamp, config_path, metric, shock specs
   - Monte Carlo metadata: iterations, success_rate, random_seed, sampler

4. **Export Stability:**
   - Excel/CSV exports must be byte-identical for same inputs
   - No floating-point drift in exports
   - All exports include metadata sheet/header

### 2.4 GWTF v3.0 Compliance (Gateway Pattern)

**Core Rules:**

```python
# ✅ ALLOWED: Analytics talks to gateway
from analytics.evaluation_v14 import evaluate_with_overrides

def my_sensitivity_function(config_path, overrides):
    return evaluate_with_overrides(config_path, overrides)

# ❌ FORBIDDEN: Analytics bypasses gateway
from finance.cashflow_v14 import build_cashflow

def my_sensitivity_function_bad(config):
    return build_cashflow(config)  # GWTF VIOLATION
```

**Enforcement via Import Linting:**

```python
# File: tests/lint/test_swimlane2_imports.py

def test_sensitivity_v14_no_direct_finance_imports():
    """Lint test: sensitivity_v14 must not import finance modules."""
    import libcst as cst

    with open("analytics/sensitivity_v14.py") as f:
        tree = cst.parse_module(f.read())

    for node in tree.walk():
        if isinstance(node, cst.Import):
            for name in node.names:
                assert not name.name.value.startswith("finance."), \
                    f"GWTF violation: sensitivity_v14 imports {name.name.value}"
```

**Gateway Lazy Loading Pattern:**

```python
# In evaluation_v14.py
def run_monte_carlo_analysis(*args, **kwargs):
    """Lazy proxy to avoid circular imports (GWTF-compliant)."""
    from analytics.monte_carlo_v14 import run_monte_carlo_analysis as _run_mc
    return _run_mc(*args, **kwargs)
```

---

## 3. Phase 1: FX Foundation

### 3.1 Objectives

**Primary:** Harden FX validation and curve generation to support structured escalation scenarios.

**Secondary:** Establish pattern for schema_guard extensions used in Phase 2.

**Deliverables:**
1. `finance/fx_v14.py::build_fx_curve()`
2. `validation/schema_guard.py::_validate_fx_block()`
3. `tests/finance/test_fx_v14.py` (10+ tests)

### 3.2 Technical Specification

#### 3.2.1 FX Curve Builder

**File:** `finance/fx_v14.py`

```python
"""
FX curve generation for v14 finance stack.

CESSPIT-compliant, supports scalar and structured modes.
"""

from __future__ import annotations

from typing import List
import logging

logger = logging.getLogger(__name__)


def build_fx_curve(config: dict, project_life_years: int) -> List[float]:
    """Build annual LKR/USD FX curve for project lifetime.

    Supports two modes:

    1. Scalar: Single constant rate for entire project
       config['fx']['lkr_per_usd'] = 300.0

    2. Structured: Base rate with annual escalation
       config['fx']['base_rate'] = 300.0
       config['fx']['escalation_pct'] = 2.5  # 2.5% per year

    Args:
        config: Scenario config dict with validated 'fx' block
        project_life_years: Number of operational years (NOT including construction)

    Returns:
        List of annual FX rates. Length = project_life_years + 1
        Index 0 = Year 0 (COD/construction), 1 = Year 1, ..., N = Year N

    Raises:
        KeyError: If 'fx' block missing (should be caught by CESSPIT)
        ValueError: If neither scalar nor structured mode detected

    Examples:
        >>> config = {'fx': {'lkr_per_usd': 300.0}}
        >>> build_fx_curve(config, 20)
        [300.0, 300.0, ..., 300.0]  # 21 elements

        >>> config = {'fx': {'base_rate': 300.0, 'escalation_pct': 2.5}}
        >>> curve = build_fx_curve(config, 20)
        >>> curve[0]
        300.0
        >>> curve[10]
        384.0  # 300 * 1.025^10
    """
    fx = config['fx']

    # Scalar mode
    if 'lkr_per_usd' in fx:
        rate = float(fx['lkr_per_usd'])
        logger.debug(f"FX: Scalar mode, rate={rate}")
        return [rate] * (project_life_years + 1)

    # Structured mode
    if 'base_rate' in fx and 'escalation_pct' in fx:
        base_rate = float(fx['base_rate'])
        escalation = float(fx['escalation_pct']) / 100.0  # Convert percent to decimal

        logger.debug(f"FX: Structured mode, base={base_rate}, esc={escalation*100:.2f}%")

        curve = [base_rate * ((1 + escalation) ** year)
                 for year in range(project_life_years + 1)]

        return curve

    # Should never reach here if CESSPIT validation ran
    raise ValueError(
        "FX config must have either 'lkr_per_usd' (scalar) or "
        "'base_rate'+'escalation_pct' (structured)"
    )


def get_fx_rate_for_year(
    fx_curve: List[float],
    year: int,
) -> float:
    """Get FX rate for a specific year (with bounds checking).

    Args:
        fx_curve: Output from build_fx_curve()
        year: Year index (0 = COD, 1 = Year 1, etc.)

    Returns:
        LKR/USD rate for that year

    Raises:
        IndexError: If year is out of bounds
    """
    if year < 0 or year >= len(fx_curve):
        raise IndexError(
            f"Year {year} out of bounds for FX curve of length {len(fx_curve)}"
        )
    return fx_curve[year]
```

#### 3.2.2 FX Validation

**File:** `validation/schema_guard.py` (add to existing file)

```python
def _validate_fx_block(config: dict) -> list[str]:
    """Validate FX configuration block (CESSPIT enforcement).

    Checks:
    1. 'fx' block exists
    2. Valid scalar OR structured mode
    3. Rates are positive
    4. Escalation is reasonable (-10% to +10%)

    Args:
        config: Full scenario config dict

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check existence
    if 'fx' not in config:
        errors.append("Missing 'fx' block in config (required for v14)")
        return errors

    fx = config['fx']

    # Check for at least one valid mode
    has_scalar = 'lkr_per_usd' in fx
    has_structured = 'base_rate' in fx and 'escalation_pct' in fx

    if not has_scalar and not has_structured:
        errors.append(
            "fx block must have either 'lkr_per_usd' (scalar) or "
            "'base_rate'+'escalation_pct' (structured)"
        )
        return errors

    # Validate scalar mode
    if has_scalar:
        rate = fx['lkr_per_usd']
        if not isinstance(rate, (int, float)):
            errors.append(f"fx.lkr_per_usd must be numeric, got {type(rate).__name__}")
        elif rate <= 0:
            errors.append(f"fx.lkr_per_usd must be positive, got {rate}")

    # Validate structured mode
    if has_structured:
        base_rate = fx.get('base_rate')
        escalation_pct = fx.get('escalation_pct')

        if not isinstance(base_rate, (int, float)):
            errors.append(f"fx.base_rate must be numeric, got {type(base_rate).__name__}")
        elif base_rate <= 0:
            errors.append(f"fx.base_rate must be positive, got {base_rate}")

        if not isinstance(escalation_pct, (int, float)):
            errors.append(f"fx.escalation_pct must be numeric, got {type(escalation_pct).__name__}")
        elif not -10 <= escalation_pct <= 10:
            errors.append(
                f"fx.escalation_pct must be between -10 and 10 (percent), got {escalation_pct}"
            )

    return errors
```

**Integration into main validator:**

```python
def validate_config_for_v14(
    config: dict,
    validation_mode: str = "strict",
    modules: list[str] | None = None,
) -> list[str]:
    """Main v14 config validator (extended with FX)."""
    errors = []

    # ... existing validations ...

    # Add FX validation
    if modules is None or "fx" in modules:
        fx_errors = _validate_fx_block(config)
        errors.extend(fx_errors)

    return errors
```

### 3.3 Test Specification

**File:** `tests/finance/test_fx_v14.py`

```python
"""
CESSPIT-compliant tests for FX curve generation.

Coverage target: 100% of fx_v14.py
"""

import pytest
from finance.fx_v14 import build_fx_curve, get_fx_rate_for_year
from validation.schema_guard import _validate_fx_block


class TestFxCurveScalarMode:
    """Tests for scalar FX mode (constant rate)."""

    def test_scalar_20_year_curve(self):
        """Scalar mode: 20-year project with 300 LKR/USD."""
        config = {'fx': {'lkr_per_usd': 300.0}}
        curve = build_fx_curve(config, project_life_years=20)

        assert len(curve) == 21  # 0 to 20 inclusive
        assert all(rate == 300.0 for rate in curve)

    def test_scalar_integer_rate(self):
        """Scalar mode: Rate provided as integer."""
        config = {'fx': {'lkr_per_usd': 300}}  # int, not float
        curve = build_fx_curve(config, 20)

        assert curve[0] == 300.0  # Converted to float

    def test_scalar_short_project(self):
        """Scalar mode: 5-year project."""
        config = {'fx': {'lkr_per_usd': 250.0}}
        curve = build_fx_curve(config, 5)

        assert len(curve) == 6
        assert curve[0] == curve[5] == 250.0


class TestFxCurveStructuredMode:
    """Tests for structured FX mode (escalation)."""

    def test_structured_positive_escalation(self):
        """Structured mode: 2.5% annual escalation."""
        config = {
            'fx': {
                'base_rate': 300.0,
                'escalation_pct': 2.5,
            }
        }
        curve = build_fx_curve(config, 20)

        assert len(curve) == 21
        assert curve[0] == 300.0
        assert curve[10] == pytest.approx(300.0 * (1.025 ** 10), rel=1e-6)
        assert curve[20] == pytest.approx(300.0 * (1.025 ** 20), rel=1e-6)

    def test_structured_negative_escalation(self):
        """Structured mode: -1% annual escalation (appreciation)."""
        config = {
            'fx': {
                'base_rate': 300.0,
                'escalation_pct': -1.0,
            }
        }
        curve = build_fx_curve(config, 10)

        assert curve[0] == 300.0
        assert curve[10] == pytest.approx(300.0 * (0.99 ** 10), rel=1e-6)
        assert curve[10] < curve[0]  # Rate decreases (LKR appreciates)

    def test_structured_zero_escalation(self):
        """Structured mode: 0% escalation (should match scalar)."""
        config = {
            'fx': {
                'base_rate': 300.0,
                'escalation_pct': 0.0,
            }
        }
        curve = build_fx_curve(config, 20)

        assert all(rate == 300.0 for rate in curve)


class TestFxValidation:
    """CESSPIT validation tests."""

    def test_validation_scalar_valid(self):
        """Valid scalar FX config."""
        config = {'fx': {'lkr_per_usd': 300.0}}
        errors = _validate_fx_block(config)
        assert len(errors) == 0

    def test_validation_structured_valid(self):
        """Valid structured FX config."""
        config = {
            'fx': {
                'base_rate': 300.0,
                'escalation_pct': 2.5,
            }
        }
        errors = _validate_fx_block(config)
        assert len(errors) == 0

    def test_validation_missing_fx_block(self):
        """Missing FX block should error."""
        config = {}
        errors = _validate_fx_block(config)
        assert len(errors) == 1
        assert "Missing 'fx' block" in errors[0]

    def test_validation_negative_rate(self):
        """Negative rate should error."""
        config = {'fx': {'lkr_per_usd': -300.0}}
        errors = _validate_fx_block(config)
        assert len(errors) == 1
        assert "must be positive" in errors[0]

    def test_validation_excessive_escalation(self):
        """Escalation > 10% should error."""
        config = {
            'fx': {
                'base_rate': 300.0,
                'escalation_pct': 15.0,  # Too high
            }
        }
        errors = _validate_fx_block(config)
        assert len(errors) == 1
        assert "between -10 and 10" in errors[0]

    def test_validation_invalid_mode(self):
        """Config with neither scalar nor structured should error."""
        config = {'fx': {'some_other_field': 123}}
        errors = _validate_fx_block(config)
        assert len(errors) == 1
        assert "lkr_per_usd" in errors[0] or "base_rate" in errors[0]


class TestFxUtilities:
    """Tests for utility functions."""

    def test_get_fx_rate_for_year_valid(self):
        """get_fx_rate_for_year with valid index."""
        curve = [300.0, 305.0, 310.0]
        assert get_fx_rate_for_year(curve, 0) == 300.0
        assert get_fx_rate_for_year(curve, 2) == 310.0

    def test_get_fx_rate_for_year_out_of_bounds(self):
        """get_fx_rate_for_year with invalid index."""
        curve = [300.0, 305.0]

        with pytest.raises(IndexError):
            get_fx_rate_for_year(curve, 5)

        with pytest.raises(IndexError):
            get_fx_rate_for_year(curve, -1)
```

### 3.4 Integration Test

**File:** `tests/integration/test_fx_integration.py`

```python
"""Integration test: FX curves flow through full pipeline."""

def test_fx_scalar_integration():
    """FX scalar mode integrates with evaluation_v14."""
    from analytics.evaluation_v14 import evaluate_with_overrides

    # Use test scenario with scalar FX
    kpis = evaluate_with_overrides(
        "scenarios/test_scenario_fx_scalar.yaml",
        overrides=None,
    )

    assert kpis['project_irr'] > 0
    # FX should have been applied to USD costs/revenues

def test_fx_structured_integration():
    """FX structured mode integrates with evaluation_v14."""
    from analytics.evaluation_v14 import evaluate_with_overrides

    # Use test scenario with structured FX
    kpis = evaluate_with_overrides(
        "scenarios/test_scenario_fx_structured.yaml",
        overrides=None,
    )

    assert kpis['project_irr'] > 0
    # FX escalation should have been applied

def test_fx_validation_in_pipeline():
    """CESSPIT validation catches invalid FX in pipeline."""
    from analytics.evaluation_v14 import evaluate_with_overrides

    # This scenario intentionally has broken FX
    with pytest.raises(ValueError, match="CESSPIT"):
        evaluate_with_overrides(
            "scenarios/test_scenario_fx_invalid.yaml",
            overrides=None,
            validation_mode="strict",
        )
```

### 3.5 Phase 1 Acceptance Criteria

**Code Quality:**
- [ ] `mypy --strict` passes on `finance/fx_v14.py`
- [ ] `ruff check` passes with zero warnings
- [ ] `black` and `isort` formatting applied
- [ ] All docstrings present with examples

**Test Coverage:**
- [ ] 100% line coverage on `fx_v14.py`
- [ ] 100% branch coverage on `_validate_fx_block`
- [ ] All 15+ test cases passing
- [ ] Integration tests passing

**CESSPIT Compliance:**
- [ ] FX validation integrated into `validate_config_for_v14`
- [ ] Invalid configs fail fast with clear error messages
- [ ] No silent failures or default fallbacks

**Documentation:**
- [ ] Module docstring explains scalar vs structured
- [ ] Function docstrings include examples
- [ ] Test file has class-level documentation

**Handover:**
- [ ] Code reviewed by 2+ engineers
- [ ] Demo to lender advisory team
- [ ] Benchmarked (no performance regression)

---

## 4. Phase 2: Sensitivity Rebuild

### 4.1 Objectives

**Primary:** Refactor `sensitivity_v14.py` to be a pure client of `evaluation_v14`, eliminating all direct finance imports.

**Secondary:** Establish standard shock library for lender-grade sensitivity analysis.

**Deliverables:**
1. Refactored `analytics/sensitivity_v14.py` (GWTF-compliant)
2. `contracts_v14.ShockSpec` and `ShockResult` dataclasses
3. Standard shock library (8-10 shocks)
4. `tests/analytics_layer/test_sensitivity_v14.py` (20+ tests)
5. Import lint test to prevent regressions

### 4.2 Technical Specification

#### 4.2.1 Contract Definitions

**File:** `analytics/contracts_v14.py` (add to existing)

```python
"""
Sensitivity analysis contracts (CCCDIR-compliant).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class ShockSpec:
    """Specification for a single parameter shock (CCCDIR contract).

    Attributes:
        variable_name: Dotted path to parameter (e.g. "project.capacity_factor")
        base_value: Baseline value before shock
        low_pct: Low shock as percent of base (e.g. -10.0 for -10%)
        high_pct: High shock as percent of base (e.g. +15.0 for +15%)
        label: Human-readable label for exports (optional)

    Examples:
        >>> shock = ShockSpec(
        ...     variable_name="project.capacity_factor",
        ...     base_value=0.40,
        ...     low_pct=-10.0,
        ...     high_pct=10.0,
        ...     label="Capacity Factor",
        ... )
        >>> shock.low_value
        0.36
        >>> shock.high_value
        0.44
    """
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    label: str | None = None

    @property
    def low_value(self) -> float:
        """Absolute low value after shock."""
        return self.base_value * (1.0 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        """Absolute high value after shock."""
        return self.base_value * (1.0 + self.high_pct / 100.0)

    def __post_init__(self):
        """Validate shock spec."""
        if self.base_value <= 0:
            raise ValueError(f"base_value must be positive, got {self.base_value}")
        if self.low_pct >= self.high_pct:
            raise ValueError(f"low_pct must be < high_pct, got {self.low_pct} >= {self.high_pct}")


@dataclass
class ShockResult:
    """Result of a single sensitivity shock (CCCDIR contract).

    Attributes:
        variable_name: Parameter that was shocked
        base_value: Original value
        low_value: Value after low shock
        high_value: Value after high shock
        base_metric: Metric value at baseline
        low_metric: Metric value after low shock
        high_metric: Metric value after high shock
        metric_name: Name of metric analyzed (e.g. "project_irr")

    Properties:
        impact: Absolute impact on metric (high - low) / 2
        impact_pct: Percent impact relative to baseline
    """
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str

    @property
    def impact(self) -> float:
        """Absolute impact: (high_metric - low_metric) / 2."""
        return (self.high_metric - self.low_metric) / 2.0

    @property
    def impact_pct(self) -> float:
        """Percent impact relative to baseline."""
        if self.base_metric == 0:
            return 0.0
        return (self.impact / abs(self.base_metric)) * 100.0

    @property
    def direction(self) -> int:
        """Direction: +1 if high > low, -1 if high < low, 0 if equal."""
        if self.high_metric > self.low_metric:
            return 1
        elif self.high_metric < self.low_metric:
            return -1
        else:
            return 0
```

#### 4.2.2 Refactored Sensitivity Module

**File:** `analytics/sensitivity_v14.py` (complete rewrite)

```python
"""
Sensitivity analysis for v14 finance stack (GWTF-compliant).

This module is a PURE CLIENT of evaluation_v14.py. It has ZERO direct
imports of finance modules. All evaluation goes through the gateway.

GWTF Enforcement: See tests/lint/test_sensitivity_imports.py
CESSPIT Compliance: Uses schema-validated configs only
CASPER Integration: Tornado results can be enriched with tail risk
"""

from __future__ import annotations

from pathlib import Path
from typing import List
import logging
import yaml

# ✅ ALLOWED: Gateway import
from analytics.evaluation_v14 import evaluate_with_overrides

# ✅ ALLOWED: Contract imports
from analytics.contracts_v14 import (
    ShockSpec,
    ShockResult,
    SensitivitySuite,
)

# ❌ FORBIDDEN: Direct finance imports
# from finance.cashflow_v14 import ...  # GWTF VIOLATION
# from finance.debt_v14 import ...      # GWTF VIOLATION

logger = logging.getLogger(__name__)


def run_sensitivity_v14(
    config_path: str | Path,
    shocks: List[ShockSpec] | None = None,
    metric: str = "project_irr",
) -> SensitivitySuite:
    """Run deterministic one-way sensitivity analysis (GWTF-compliant).

    This function:
    1. Evaluates baseline scenario via evaluation_v14
    2. For each shock, evaluates perturbed scenario via evaluation_v14
    3. Computes impact and ranks by magnitude
    4. Returns SensitivitySuite for export/visualization

    Args:
        config_path: Path to base scenario YAML
        shocks: List of shocks to apply (if None, uses standard library)
        metric: Target KPI to analyze (must be in KPI dict)

    Returns:
        SensitivitySuite with baseline + tornado results

    Raises:
        FileNotFoundError: If config_path doesn't exist
        KeyError: If metric not found in KPI outputs
        ValueError: If CESSPIT validation fails

    Examples:
        >>> from analytics.contracts_v14 import ShockSpec
        >>> shocks = [
        ...     ShockSpec("project.capacity_factor", 0.40, -10, 10, "CF"),
        ...     ShockSpec("capex.usd_total", 150e6, -10, 10, "CAPEX"),
        ... ]
        >>> suite = run_sensitivity_v14(
        ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
        ...     shocks=shocks,
        ...     metric="project_irr",
        ... )
        >>> len(suite.tornado_results)
        2
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    logger.info(f"Running sensitivity: {config_path}, metric={metric}")

    # Step 1: Evaluate baseline (GWTF: via gateway)
    logger.debug("Evaluating baseline...")
    baseline_kpis = evaluate_with_overrides(
        config_path=config_path,
        overrides=None,
    )

    if metric not in baseline_kpis:
        raise KeyError(
            f"Metric '{metric}' not found in KPI outputs. "
            f"Available: {list(baseline_kpis.keys())}"
        )

    base_metric = baseline_kpis[metric]
    logger.info(f"Baseline {metric}: {base_metric}")

    # Step 2: Use standard shocks if not provided
    if shocks is None:
        logger.debug("No shocks provided, loading standard library...")
        shocks = _build_standard_shocks(config_path)

    logger.info(f"Running {len(shocks)} shocks...")

    # Step 3: Run each shock (GWTF: via gateway)
    results = []
    for shock in shocks:
        result = _run_single_shock(
            config_path=config_path,
            shock=shock,
            baseline_kpis=baseline_kpis,
            metric=metric,
        )
        results.append(result)

    # Step 4: Sort by absolute impact (tornado order)
    tornado_results = sorted(
        results,
        key=lambda r: abs(r.impact),
        reverse=True,
    )

    logger.info(f"Sensitivity complete. Top driver: {tornado_results[0].variable_name}")

    return SensitivitySuite(
        tornado_results=tornado_results,
        base_metric=base_metric,
        base_config_path=str(config_path),
        metric=metric,
    )


def _run_single_shock(
    config_path: Path,
    shock: ShockSpec,
    baseline_kpis: dict[str, float],
    metric: str,
) -> ShockResult:
    """Run a single shock and compute impact (GWTF-compliant).

    Args:
        config_path: Base scenario config
        shock: Shock specification
        baseline_kpis: Baseline KPI dict (for comparison)
        metric: Target metric name

    Returns:
        ShockResult with low/high metric values and impact
    """
    logger.debug(f"Shocking {shock.variable_name}: {shock.low_pct}% to {shock.high_pct}%")

    # Build override dicts for low and high shocks
    low_overrides = _build_override_dict(shock.variable_name, shock.low_value)
    high_overrides = _build_override_dict(shock.variable_name, shock.high_value)

    # Evaluate low scenario (GWTF: via gateway)
    low_kpis = evaluate_with_overrides(config_path, low_overrides)
    low_metric = low_kpis[metric]

    # Evaluate high scenario (GWTF: via gateway)
    high_kpis = evaluate_with_overrides(config_path, high_overrides)
    high_metric = high_kpis[metric]

    logger.debug(
        f"  {shock.variable_name}: "
        f"low={low_metric:.4f}, base={baseline_kpis[metric]:.4f}, high={high_metric:.4f}"
    )

    return ShockResult(
        variable_name=shock.variable_name,
        base_value=shock.base_value,
        low_value=shock.low_value,
        high_value=shock.high_value,
        base_metric=baseline_kpis[metric],
        low_metric=low_metric,
        high_metric=high_metric,
        metric_name=metric,
    )


def _build_override_dict(variable_name: str, value: float) -> dict:
    """Build nested override dict from dotted variable name.

    Examples:
        >>> _build_override_dict("project.capacity_factor", 0.42)
        {'project': {'capacity_factor': 0.42}}

        >>> _build_override_dict("capex.usd_total", 150e6)
        {'capex': {'usd_total': 150000000.0}}
    """
    parts = variable_name.split(".")

    # Build nested dict from inside out
    result = {parts[-1]: value}
    for part in reversed(parts[:-1]):
        result = {part: result}

    return result


def _build_standard_shocks(config_path: Path) -> List[ShockSpec]:
    """Build standard lender-grade shock library.

    Standard shocks (per DFI/IFC requirements):
    - CAPEX ±10%
    - OPEX ±10%
    - Capacity Factor ±5%
    - Availability ±5% (if applicable)
    - Cost of Debt ±50 bps
    - Debt Tenor ±2 years
    - WACC ±100 bps (if WACC module enabled)
    - FX ±10% (if FX exposure exists)

    Args:
        config_path: Base scenario config (to extract base values)

    Returns:
        List of ShockSpec objects
    """
    # Load config to extract base values
    with open(config_path) as f:
        config = yaml.safe_load(f)

    shocks = []

    # CAPEX shock
    if 'capex' in config and 'usd_total' in config['capex']:
        shocks.append(ShockSpec(
            variable_name="capex.usd_total",
            base_value=float(config['capex']['usd_total']),
            low_pct=-10.0,
            high_pct=10.0,
            label="Total CAPEX",
        ))

    # OPEX shock
    if 'opex' in config and 'usd_per_year' in config['opex']:
        shocks.append(ShockSpec(
            variable_name="opex.usd_per_year",
            base_value=float(config['opex']['usd_per_year']),
            low_pct=-10.0,
            high_pct=10.0,
            label="Annual OPEX",
        ))

    # Capacity Factor shock
    if 'project' in config and 'capacity_factor' in config['project']:
        shocks.append(ShockSpec(
            variable_name="project.capacity_factor",
            base_value=float(config['project']['capacity_factor']),
            low_pct=-5.0,
            high_pct=5.0,
            label="Capacity Factor",
        ))

    # Tariff shock (if present)
    if 'tariff' in config and 'lkr_per_kwh' in config['tariff']:
        shocks.append(ShockSpec(
            variable_name="tariff.lkr_per_kwh",
            base_value=float(config['tariff']['lkr_per_kwh']),
            low_pct=-10.0,
            high_pct=10.0,
            label="Tariff (LKR/kWh)",
        ))

    # FX shock (if structured FX)
    if 'fx' in config:
        fx = config['fx']
        if 'base_rate' in fx:
            shocks.append(ShockSpec(
                variable_name="fx.base_rate",
                base_value=float(fx['base_rate']),
                low_pct=-10.0,
                high_pct=10.0,
                label="FX Base Rate",
            ))
        elif 'lkr_per_usd' in fx:
            shocks.append(ShockSpec(
                variable_name="fx.lkr_per_usd",
                base_value=float(fx['lkr_per_usd']),
                low_pct=-10.0,
                high_pct=10.0,
                label="FX Rate (LKR/USD)",
            ))

    # Degradation shock
    if 'project' in config and 'degradation' in config['project']:
        shocks.append(ShockSpec(
            variable_name="project.degradation",
            base_value=float(config['project']['degradation']),
            low_pct=-20.0,  # Less degradation = better performance
            high_pct=20.0,  # More degradation = worse performance
            label="Annual Degradation",
        ))

    logger.info(f"Built {len(shocks)} standard shocks")
    return shocks
```

### 4.3 Import Lint Test (GWTF Enforcement)

**File:** `tests/lint/test_sensitivity_imports.py`

```python
"""
GWTF enforcement: Sensitivity module must not import finance modules directly.

This test uses LibCST to parse sensitivity_v14.py and check for forbidden imports.
"""

import libcst as cst
from pathlib import Path


def test_sensitivity_v14_no_direct_finance_imports():
    """GWTF rule: sensitivity_v14 must not import from finance.*"""

    sensitivity_file = Path("analytics/sensitivity_v14.py")

    if not sensitivity_file.exists():
        pytest.skip("sensitivity_v14.py not found")

    with open(sensitivity_file) as f:
        source = f.read()

    tree = cst.parse_module(source)

    forbidden_imports = []

    # Check all import statements
    for node in tree.walk():
        if isinstance(node, cst.Import):
            for name in node.names:
                module_name = name.name.value
                if module_name.startswith("finance."):
                    forbidden_imports.append(f"import {module_name}")

        elif isinstance(node, cst.ImportFrom):
            if node.module and node.module.value.startswith("finance."):
                module_name = node.module.value
                forbidden_imports.append(f"from {module_name} import ...")

    assert len(forbidden_imports) == 0, (
        f"GWTF violation: sensitivity_v14 has forbidden finance imports:\n"
        + "\n".join(f"  - {imp}" for imp in forbidden_imports)
        + "\n\nAll evaluation must go through analytics.evaluation_v14"
    )


def test_sensitivity_v14_uses_evaluation_gateway():
    """GWTF rule: sensitivity_v14 must import evaluation_v14."""

    sensitivity_file = Path("analytics/sensitivity_v14.py")

    with open(sensitivity_file) as f:
        source = f.read()

    # Check that evaluation_v14 is imported
    assert "from analytics.evaluation_v14 import" in source, (
        "sensitivity_v14 must import from analytics.evaluation_v14"
    )

    # Check that evaluate_with_overrides is used
    assert "evaluate_with_overrides(" in source, (
        "sensitivity_v14 must use evaluate_with_overrides()"
    )
```

### 4.4 Phase 2 Acceptance Criteria

**Code Quality:**
- [ ] Zero direct finance imports in `sensitivity_v14.py`
- [ ] Import lint test passing
- [ ] `mypy --strict` passes
- [ ] 100% docstring coverage

**Test Coverage:**
- [ ] 80%+ line coverage on `sensitivity_v14.py`
- [ ] 20+ test cases covering shocks, validation, edge cases
- [ ] Integration test with evaluation_v14

**GWTF Compliance:**
- [ ] All evaluation via `evaluate_with_overrides()`
- [ ] No direct calls to `build_cashflow()`, `compute_debt()`, etc.
- [ ] Lazy loading pattern used if needed

**CCCDIR Compliance:**
- [ ] `ShockSpec` and `ShockResult` contracts in `contracts_v14.py`
- [ ] All public APIs use typed dataclasses
- [ ] No `dict[str, Any]` in public signatures

**Backward Compatibility:**
- [ ] Existing sensitivity tests still pass
- [ ] Tornado outputs match previous format
- [ ] No regressions in existing scenarios

---

## 5. Phase 3: Capital Risk Layer

### 5.1 Objectives

**Primary:** Create unified API that bundles WACC, equity, sensitivity, and Monte Carlo into a single `CapitalRiskBundle`.

**Secondary:** Provide one-stop interface for dashboards, exports, and board reports.

**Deliverables:**
1. `analytics/capital_risk_layer_v14.py`
2. `contracts_v14.CapitalRiskBundle` dataclass
3. `tests/analytics_layer/test_capital_risk_layer.py` (10+ tests)

### 5.2 Technical Specification

#### 5.2.1 Capital Risk Bundle Contract

**File:** `analytics/contracts_v14.py` (add to existing)

```python
@dataclass
class CapitalRiskBundle:
    """Unified bundle of all capital & risk analytics (CCCDIR contract).

    This is the ONE-STOP API for dashboards, exports, and reports.

    Attributes:
        scenario: Scenario descriptor
        baseline_kpis: Deterministic KPI dict
        wacc_result: WACC calculation result (from Swimlane 1)
        equity_result: Equity IRR/NPV/payback (from Swimlane 1)
        sensitivity_suite: Tornado sensitivity results
        monte_carlo: Monte Carlo tail risk results
        optimization_result: Capital structure optimization (optional)
        metadata: Additional metadata (tail risk summary, etc.)
        timestamp: ISO timestamp of bundle creation

    Examples:
        >>> bundle = build_capital_risk_bundle(
        ...     config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        ...     monte_carlo_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
        ...     run_sensitivity=True,
        ...     run_optimization=False,
        ... )
        >>> bundle.baseline_kpis['project_irr']
        0.1788
        >>> len(bundle.sensitivity_suite.tornado_results)
        7
        >>> bundle.monte_carlo.project_irr_p50
        0.1782
    """
    scenario: ScenarioDescriptor
    baseline_kpis: dict[str, float]
    wacc_result: WaccResult | None
    equity_result: EquityResult | None
    sensitivity_suite: SensitivitySuite | None
    monte_carlo: MonteCarloResult | None
    optimization_result: OptimizationResult | None
    metadata: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict:
        """Export to JSON-serializable dict."""
        from dataclasses import asdict
        return asdict(self)
```

#### 5.2.2 Capital Risk Layer Implementation

**File:** `analytics/capital_risk_layer_v14.py`

```python
"""
Unified capital risk analytics layer (GWTF-compliant).

This module provides the ONE-STOP API for:
- Baseline evaluation
- Sensitivity analysis
- Monte Carlo tail risk
- WACC/equity analytics
- Capital structure optimization

All orchestration goes through evaluation_v14 gateway (GWTF compliance).
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any
import logging

# ✅ ALLOWED: Gateway and contract imports
from analytics.evaluation_v14 import evaluate_with_casper_tail_risk
from analytics.sensitivity_v14 import run_sensitivity_v14
from analytics.sensitivity_tail_risk import enrich_tornado_with_tail_risk
from analytics.contracts_v14 import (
    CapitalRiskBundle,
    ShockSpec,
    OptimizationResult,
)

# Import optimization if available (Swimlane 1 dependency)
try:
    from analytics.optimization_v14 import (
        optimize_capital_structure_v14,
        OptimizationConstraints,
    )
    HAS_OPTIMIZATION = True
except ImportError:
    HAS_OPTIMIZATION = False
    logging.warning("optimization_v14 not available, optimization features disabled")

logger = logging.getLogger(__name__)


def build_capital_risk_bundle(
    config_path: str | Path,
    monte_carlo_config_path: str | Path | None = None,
    run_sensitivity: bool = True,
    run_optimization: bool = False,
    sensitivity_shocks: list[ShockSpec] | None = None,
    metric: str = "project_irr",
    confidence: float = 0.9,
) -> CapitalRiskBundle:
    """Build comprehensive capital & risk analytics bundle (GWTF-compliant).

    This is the SINGLE API for generating complete risk reports.

    Args:
        config_path: Base scenario config
        monte_carlo_config_path: Optional MC config (if None, MC not run)
        run_sensitivity: Whether to run tornado sensitivity
        run_optimization: Whether to run capital structure optimization
        sensitivity_shocks: Custom shocks (if None, uses standard library)
        metric: Target metric for analysis (default: project_irr)
        confidence: Confidence level for tail risk (default: 0.9)

    Returns:
        CapitalRiskBundle with all requested analytics

    Raises:
        FileNotFoundError: If config files not found
        ValueError: If CESSPIT validation fails

    Examples:
        >>> # Minimal bundle (baseline only)
        >>> bundle = build_capital_risk_bundle(
        ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
        ...     run_sensitivity=False,
        ... )

        >>> # Full bundle (baseline + MC + sensitivity)
        >>> bundle = build_capital_risk_bundle(
        ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
        ...     monte_carlo_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
        ...     run_sensitivity=True,
        ... )

        >>> # With optimization (requires Swimlane 1)
        >>> bundle = build_capital_risk_bundle(
        ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
        ...     run_optimization=True,
        ... )
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    logger.info(f"Building capital risk bundle: {config_path}")
    logger.info(f"  MC: {monte_carlo_config_path is not None}")
    logger.info(f"  Sensitivity: {run_sensitivity}")
    logger.info(f"  Optimization: {run_optimization}")

    # =========================================================================
    # Step 1: Run CASPER (baseline + optional MC + tail risk)
    # =========================================================================
    logger.info("Running CASPER evaluation...")

    casper_result = evaluate_with_casper_tail_risk(
        config_path=config_path,
        monte_carlo_config_path=monte_carlo_config_path,
        metric=metric,
        confidence=confidence,
        sensitivity_suite=None,  # Will add separately
    )

    logger.info(f"  Baseline {metric}: {casper_result.baseline_kpis[metric]:.4f}")

    if casper_result.monte_carlo is not None:
        logger.info(
            f"  MC P50: {getattr(casper_result.monte_carlo, f'{metric}_p50'):.4f}"
        )

    # =========================================================================
    # Step 2: Run sensitivity if requested
    # =========================================================================
    sensitivity_suite = None

    if run_sensitivity:
        logger.info("Running sensitivity analysis...")

        sensitivity_suite = run_sensitivity_v14(
            config_path=config_path,
            shocks=sensitivity_shocks,
            metric=metric,
        )

        logger.info(f"  Shocks: {len(sensitivity_suite.tornado_results)}")

        # Enrich tornado with tail risk if MC was run
        if casper_result.monte_carlo is not None:
            logger.info("Enriching tornado with tail risk...")

            enriched_tornado_df = enrich_tornado_with_tail_risk(
                tornado_suite=sensitivity_suite,
                mc_result=casper_result.monte_carlo,
                metric=metric,
                confidence=confidence,
            )

            # Store in metadata for export
            casper_result.metadata['enriched_tornado_df'] = enriched_tornado_df
            logger.info("  Tornado enriched with VaR/CVaR")

    # =========================================================================
    # Step 3: Run optimization if requested (requires Swimlane 1)
    # =========================================================================
    optimization_result = None

    if run_optimization:
        if not HAS_OPTIMIZATION:
            logger.warning("Optimization requested but optimization_v14 not available")
        else:
            logger.info("Running capital structure optimization...")

            optimization_result = optimize_capital_structure_v14(
                config_path=config_path,
                objective="equity_irr",
                constraints=OptimizationConstraints(
                    min_irr=0.15,
                    min_dscr=1.30,
                ),
            )

            logger.info(f"  Optimal debt ratio: {optimization_result.optimal_debt_ratio:.2%}")

    # =========================================================================
    # Step 4: Extract WACC and equity (from Swimlane 1 if available)
    # =========================================================================
    # TODO: Extract from pipeline result once Swimlane 1 integrated
    wacc_result = None
    equity_result = None

    # =========================================================================
    # Step 5: Bundle everything
    # =========================================================================
    bundle = CapitalRiskBundle(
        scenario=casper_result.scenario,
        baseline_kpis=casper_result.baseline_kpis,
        wacc_result=wacc_result,
        equity_result=equity_result,
        sensitivity_suite=sensitivity_suite,
        monte_carlo=casper_result.monte_carlo,
        optimization_result=optimization_result,
        metadata=casper_result.metadata,
        timestamp=datetime.now().isoformat(),
    )

    logger.info("Capital risk bundle complete")
    return bundle


def export_capital_risk_bundle(
    bundle: CapitalRiskBundle,
    export_path: str | Path,
    format: str = "excel",
) -> None:
    """Export capital risk bundle to file.

    Supported formats:
    - excel: Multi-sheet Excel with baseline, tornado, MC, etc.
    - json: JSON export of entire bundle
    - csv: Directory of CSV files

    Args:
        bundle: CapitalRiskBundle to export
        export_path: Output file/directory path
        format: Export format (excel, json, csv)

    Examples:
        >>> bundle = build_capital_risk_bundle(...)
        >>> export_capital_risk_bundle(
        ...     bundle,
        ...     "outputs/dutchbay_risk_report.xlsx",
        ...     format="excel",
        ... )
    """
    export_path = Path(export_path)

    if format == "excel":
        _export_to_excel(bundle, export_path)
    elif format == "json":
        _export_to_json(bundle, export_path)
    elif format == "csv":
        _export_to_csv(bundle, export_path)
    else:
        raise ValueError(f"Unsupported format: {format}")

    logger.info(f"Exported capital risk bundle to {export_path}")


def _export_to_excel(bundle: CapitalRiskBundle, path: Path) -> None:
    """Export to Excel with multiple sheets."""
    import pandas as pd

    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        # Sheet 1: Baseline KPIs
        baseline_df = pd.DataFrame([bundle.baseline_kpis])
        baseline_df.to_excel(writer, sheet_name="Baseline", index=False)

        # Sheet 2: Sensitivity (if present)
        if bundle.sensitivity_suite is not None:
            from analytics.sensitivity_export import tornado_suite_to_dataframe
            tornado_df = tornado_suite_to_dataframe(bundle.sensitivity_suite)
            tornado_df.to_excel(writer, sheet_name="Sensitivity", index=False)

        # Sheet 3: Monte Carlo summary (if present)
        if bundle.monte_carlo is not None:
            mc_summary = {
                'Metric': [bundle.monte_carlo.metric],
                'P10': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_p10')],
                'P50': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_p50')],
                'P90': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_p90')],
                'Mean': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_mean')],
                'Std': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_std')],
            }
            mc_df = pd.DataFrame(mc_summary)
            mc_df.to_excel(writer, sheet_name="Monte Carlo", index=False)

        # Sheet 4: Metadata
        metadata_items = []
        for key, value in bundle.metadata.items():
            if not isinstance(value, (dict, pd.DataFrame)):  # Skip complex objects
                metadata_items.append({'Key': key, 'Value': str(value)})
        metadata_df = pd.DataFrame(metadata_items)
        metadata_df.to_excel(writer, sheet_name="Metadata", index=False)


def _export_to_json(bundle: CapitalRiskBundle, path: Path) -> None:
    """Export to JSON."""
    import json

    bundle_dict = bundle.to_dict()

    with open(path, 'w') as f:
        json.dump(bundle_dict, f, indent=2, default=str)


def _export_to_csv(bundle: CapitalRiskBundle, path: Path) -> None:
    """Export to directory of CSV files."""
    import pandas as pd

    path.mkdir(parents=True, exist_ok=True)

    # Baseline
    baseline_df = pd.DataFrame([bundle.baseline_kpis])
    baseline_df.to_csv(path / "baseline.csv", index=False)

    # Sensitivity
    if bundle.sensitivity_suite is not None:
        from analytics.sensitivity_export import tornado_suite_to_dataframe
        tornado_df = tornado_suite_to_dataframe(bundle.sensitivity_suite)
        tornado_df.to_csv(path / "sensitivity.csv", index=False)

    # Monte Carlo
    if bundle.monte_carlo is not None:
        mc_summary = {
            'Metric': [bundle.monte_carlo.metric],
            'P10': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_p10')],
            'P50': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_p50')],
            'P90': [getattr(bundle.monte_carlo, f'{bundle.monte_carlo.metric}_p90')],
        }
        mc_df = pd.DataFrame(mc_summary)
        mc_df.to_csv(path / "monte_carlo.csv", index=False)
```

### 5.3 Test Specification

**File:** `tests/analytics_layer/test_capital_risk_layer.py`

```python
"""
Tests for capital risk layer (GWTF-compliant).
"""

import pytest
from pathlib import Path
from analytics.capital_risk_layer_v14 import (
    build_capital_risk_bundle,
    export_capital_risk_bundle,
)


class TestCapitalRiskBundleBasic:
    """Basic bundle building tests."""

    def test_build_minimal_bundle(self):
        """Build bundle with only baseline (no MC, no sensitivity)."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=False,
            run_optimization=False,
        )

        assert bundle.baseline_kpis is not None
        assert bundle.sensitivity_suite is None
        assert bundle.monte_carlo is None
        assert bundle.timestamp is not None

    def test_build_bundle_with_sensitivity(self):
        """Build bundle with baseline + sensitivity."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=True,
            run_optimization=False,
        )

        assert bundle.baseline_kpis is not None
        assert bundle.sensitivity_suite is not None
        assert len(bundle.sensitivity_suite.tornado_results) > 0

    def test_build_bundle_with_monte_carlo(self):
        """Build bundle with baseline + MC."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            monte_carlo_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
            run_sensitivity=False,
        )

        assert bundle.baseline_kpis is not None
        assert bundle.monte_carlo is not None
        assert bundle.monte_carlo.iterations > 0

    def test_build_full_bundle(self):
        """Build complete bundle with all features."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            monte_carlo_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
            run_sensitivity=True,
            run_optimization=False,  # Expensive, skip
        )

        assert bundle.baseline_kpis is not None
        assert bundle.sensitivity_suite is not None
        assert bundle.monte_carlo is not None
        assert 'sensitivities' in bundle.metadata


class TestCapitalRiskBundleExport:
    """Export functionality tests."""

    def test_export_to_excel(self, tmp_path):
        """Export bundle to Excel."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=True,
        )

        output_path = tmp_path / "risk_report.xlsx"
        export_capital_risk_bundle(bundle, output_path, format="excel")

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_to_json(self, tmp_path):
        """Export bundle to JSON."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=False,
        )

        output_path = tmp_path / "risk_report.json"
        export_capital_risk_bundle(bundle, output_path, format="json")

        assert output_path.exists()

        # Validate JSON is parseable
        import json
        with open(output_path) as f:
            data = json.load(f)

        assert 'baseline_kpis' in data

    def test_export_to_csv(self, tmp_path):
        """Export bundle to CSV directory."""
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=True,
        )

        output_dir = tmp_path / "csv_export"
        export_capital_risk_bundle(bundle, output_dir, format="csv")

        assert output_dir.exists()
        assert (output_dir / "baseline.csv").exists()
        assert (output_dir / "sensitivity.csv").exists()


class TestCapitalRiskBundleIntegration:
    """Integration tests with existing scenarios."""

    def test_bundle_matches_casper_result(self):
        """Bundle baseline should match direct CASPER call."""
        from analytics.evaluation_v14 import evaluate_with_casper_tail_risk

        # Direct CASPER call
        casper = evaluate_with_casper_tail_risk(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            monte_carlo_config_path=None,
            metric="project_irr",
        )

        # Via bundle
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=False,
        )

        # Should match
        assert bundle.baseline_kpis['project_irr'] == casper.baseline_kpis['project_irr']

    def test_bundle_sensitivity_matches_standalone(self):
        """Bundle sensitivity should match standalone sensitivity call."""
        from analytics.sensitivity_v14 import run_sensitivity_v14

        # Standalone
        suite = run_sensitivity_v14(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            metric="project_irr",
        )

        # Via bundle
        bundle = build_capital_risk_bundle(
            config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            run_sensitivity=True,
        )

        # Should match
        assert bundle.sensitivity_suite.base_metric == suite.base_metric
        assert len(bundle.sensitivity_suite.tornado_results) == len(suite.tornado_results)
```

### 5.4 Phase 3 Acceptance Criteria

**Code Quality:**
- [ ] `mypy --strict` passes
- [ ] Zero GWTF violations (lint tests pass)
- [ ] 100% docstring coverage

**Test Coverage:**
- [ ] 80%+ line coverage on `capital_risk_layer_v14.py`
- [ ] 10+ test cases covering bundle building and export
- [ ] Integration tests match standalone calls

**CCCDIR Compliance:**
- [ ] `CapitalRiskBundle` contract in `contracts_v14.py`
- [ ] All exports use typed contracts
- [ ] JSON/Excel exports validated

**Integration:**
- [ ] Works with evaluation_v14
- [ ] Works with sensitivity_v14
- [ ] Works with monte_carlo_v14
- [ ] Ready for optimization_v14 (Swimlane 1)

**Documentation:**
- [ ] Module docstring explains purpose
- [ ] Function examples in docstrings
- [ ] Export format documented

---

## 6. Integration Contract Specifications

### 6.1 Module Dependency Graph

```
capital_risk_layer_v14
    ├── evaluation_v14 (gateway)
    ├── sensitivity_v14 (Phase 2)
    ├── sensitivity_tail_risk (existing)
    └── optimization_v14 (Swimlane 1, optional)

sensitivity_v14
    ├── evaluation_v14 (gateway)
    └── contracts_v14

evaluation_v14
    ├── pipeline_v14 (internal)
    └── monte_carlo_v14 (lazy proxy)

fx_v14
    ├── schema_guard (validation)
    └── (no other dependencies)
```

### 6.2 Contract Summary

| Contract | Module | Purpose | Status |
|----------|--------|---------|--------|
| `ShockSpec` | contracts_v14 | Sensitivity shock specification | Phase 2 |
| `ShockResult` | contracts_v14 | Single shock result | Phase 2 |
| `CapitalRiskBundle` | contracts_v14 | Unified risk bundle | Phase 3 |
| `WaccResult` | contracts_v14 | WACC calculation | Swimlane 1 |
| `EquityResult` | contracts_v14 | Equity IRR/NPV | Swimlane 1 |
| `OptimizationResult` | contracts_v14 | Capital structure optimization | Swimlane 1 |

### 6.3 Gateway Pattern Enforcement

**Rule:** All analytics modules must talk to `evaluation_v14`, never directly to finance modules.

**Allowed:**
```python
from analytics.evaluation_v14 import evaluate_with_overrides
kpis = evaluate_with_overrides(config_path, overrides)
```

**Forbidden:**
```python
from finance.cashflow_v14 import build_cashflow  # ❌
cf = build_cashflow(config)  # ❌
```

**Enforcement:**
- Lint tests in `tests/lint/test_*_imports.py`
- Pre-commit hooks (optional)
- CI/CD checks

---

## 7. Test Specifications

### 7.1 Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| `fx_v14.py` | 100% | P0 |
| `sensitivity_v14.py` | 80%+ | P0 |
| `capital_risk_layer_v14.py` | 80%+ | P1 |
| `schema_guard._validate_fx_block` | 100% | P0 |

### 7.2 Test Categories

**Unit Tests:**
- Individual function behavior
- Contract validation
- Error handling
- Edge cases

**Integration Tests:**
- Module interactions
- Gateway pattern
- Full pipeline flow
- Scenario compatibility

**Lint Tests:**
- Import validation (GWTF)
- Type checking (mypy)
- Code formatting (black, ruff)

**Regression Tests:**
- Backward compatibility
- Output stability
- Performance benchmarks

### 7.3 Test Execution

```bash
# Phase 1 tests
pytest tests/finance/test_fx_v14.py -v
pytest tests/integration/test_fx_integration.py -v

# Phase 2 tests
pytest tests/analytics_layer/test_sensitivity_v14.py -v
pytest tests/lint/test_sensitivity_imports.py -v

# Phase 3 tests
pytest tests/analytics_layer/test_capital_risk_layer.py -v

# Full suite
pytest tests/ -v --cov=analytics --cov=finance
```

---

## 8. Handover Checklist

### 8.1 Phase 1 Handover (FX Foundation)

- [ ] Code committed to feature branch
- [ ] All tests passing (15+ tests, 100% coverage)
- [ ] `mypy --strict` clean
- [ ] Code reviewed by 2+ engineers
- [ ] CESSPIT validation integrated
- [ ] Integration tests with existing scenarios passing
- [ ] Documentation updated
- [ ] Demo to lender advisory team
- [ ] Performance benchmarked (no regression)
- [ ] Tagged as `v14.3.0-phase1`

### 8.2 Phase 2 Handover (Sensitivity Rebuild)

- [ ] Code committed to feature branch
- [ ] All tests passing (20+ tests, 80%+ coverage)
- [ ] Import lint tests passing (GWTF compliance)
- [ ] Code reviewed by 2+ engineers
- [ ] Backward compatibility validated
- [ ] Tornado outputs match previous format
- [ ] Standard shock library documented
- [ ] Integration with CASPER validated
- [ ] Demo to lender advisory team
- [ ] Tagged as `v14.3.0-phase2`

### 8.3 Phase 3 Handover (Capital Risk Layer)

- [ ] Code committed to feature branch
- [ ] All tests passing (10+ tests, 80%+ coverage)
- [ ] Export formats validated (Excel, JSON, CSV)
- [ ] Code reviewed by 2+ engineers
- [ ] Integration with Swimlane 1 tested (if available)
- [ ] Bundle API demonstrated to dashboard team
- [ ] DFI export template created
- [ ] Demo to board/investors
- [ ] Performance benchmarked
- [ ] Tagged as `v14.3.0`

### 8.4 Final Sprint Handover

- [ ] All 3 phases merged to `main`
- [ ] Full regression suite passing (335+ tests)
- [ ] Coverage report generated (target: 80%+)
- [ ] CHANGELOG.md updated
- [ ] Documentation published
- [ ] Sprint retrospective completed
- [ ] Sprint 11 planning initiated
- [ ] Production deployment scheduled

---

## 9. Appendices

### 9.1 Governance Glossary

**CCCDIR:** Config-Centric Contract-Driven Integration Rules
- All integration surfaces use typed contracts
- No `dict[str, Any]` in public APIs
- Contracts defined in `contracts_v14.py`

**CESSPIT:** Config-Enforced Schema Safety & Pipeline Integration Triad
- All configs validated before entering finance engine
- `validation_mode="strict"` enforces schema guards
- Fail-fast on invalid configs

**CASPER:** Capital Analytics, Sensitivity & Portfolio Evaluation Rigor
- Tail risk analysis (VaR, CVaR, breach probability)
- Tornado sensitivity with Monte Carlo enrichment
- Traceable, auditable, lender-grade

**GWTF:** Go With The Flow v3.0
- Single gateway pattern (`evaluation_v14.py`)
- No direct finance imports from analytics layer
- Lazy loading for circular dependency resolution

### 9.2 File Structure

```
dutchbay-epc-model/
├── analytics/
│   ├── contracts_v14.py              # All contracts (extended in Swimlane 2)
│   ├── evaluation_v14.py             # Gateway (unchanged)
│   ├── sensitivity_v14.py            # Refactored in Phase 2
│   ├── capital_risk_layer_v14.py     # New in Phase 3
│   ├── monte_carlo_v14.py            # Existing
│   └── sensitivity_tail_risk.py      # Existing
├── finance/
│   ├── fx_v14.py                     # New in Phase 1
│   ├── cashflow_v14.py               # Existing
│   ├── debt_v14.py                   # Existing
│   └── wacc_v14.py                   # From Swimlane 1
├── validation/
│   └── schema_guard.py               # Extended in Phase 1
├── tests/
│   ├── finance/
│   │   └── test_fx_v14.py            # New in Phase 1
│   ├── analytics_layer/
│   │   ├── test_sensitivity_v14.py   # Extended in Phase 2
│   │   └── test_capital_risk_layer.py # New in Phase 3
│   ├── lint/
│   │   └── test_sensitivity_imports.py # New in Phase 2
│   └── integration/
│       └── test_fx_integration.py    # New in Phase 1
└── docs/
    └── swimlane_2_strategy.md        # This document
```

### 9.3 Timeline & Milestones

| Week | Phase | Milestone | Owner |
|------|-------|-----------|-------|
| 1 | Phase 1 | FX Foundation complete | Engineering |
| 1 | Phase 1 | CESSPIT validation integrated | Engineering |
| 2 | Phase 2 | Sensitivity refactor started | Engineering |
| 3 | Phase 2 | Import lint tests passing | Engineering |
| 3 | Phase 2 | Standard shock library complete | Engineering |
| 3 | Integration | Coordinate with Swimlane 1 | Tech Lead |
| 4 | Phase 3 | Capital risk layer complete | Engineering |
| 4 | Integration | Full system integration test | QA |
| 4 | Handover | Demo to stakeholders | Tech Lead |
| 5 | Sprint 11 | Planning & deployment | Team |

### 9.4 Risk Register

| Risk | Severity | Mitigation | Owner |
|------|----------|------------|-------|
| Breaking sensitivity outputs | High | Parallel dev + validation | Engineering |
| FX validation too strict | Medium | Extensive scenario testing | QA |
| Circular imports | Medium | Lazy loading pattern | Engineering |
| Performance degradation | Low | Benchmark before/after | QA |
| Swimlane 1 delays | Medium | Phase 3 can proceed without optimization | Tech Lead |
| Test coverage gaps | Medium | Target 80%+, review coverage reports | QA |

---

## Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Technical Lead | Aruna Kulatunga | [Signature] | 2025-12-11 |
| QA Lead | [Name] | [Signature] | [Date] |
| Lender Advisory | [Name] | [Signature] | [Date] |
| Steering Committee | [Name] | [Signature] | [Date] |

---

**END OF DOCUMENT**

*This document is governed by CCCDIR, CESSPIT, CASPER, and GWTF v3.0. All implementations must comply with these frameworks.*
