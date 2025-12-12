# Swimlane 2 Implementation Strategy
## DutchBay EPC Model - Risk & Sensitivity Layer

**Version:** 1.0
**Date:** December 11, 2025
**Sprint:** 10-11
**Status:** Planning → Implementation

---

## Executive Summary

Swimlane 2 focuses on building the **Risk & Sensitivity Analytics Layer** that sits above the core finance engine and provides lender-grade risk analysis capabilities. This includes FX validation, sensitivity analysis refactoring, and a unified capital risk API.

**Key Metrics:**
- Total Tasks: 13
- P0 (Critical Path): 6 tasks
- P1 (Important): 7 tasks
- Current Status: 1 complete, 1 partial, 11 pending
- Estimated Duration: 4 weeks (parallel with Swimlane 1)
- Risk Level: Medium (code refactoring required)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│              External Callers (UI, API, Export)           │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│          analytics/evaluation_v14.py (Gateway)            │
│  • evaluate_with_overrides()                             │
│  • evaluate_with_casper_tail_risk()                      │
└────────────────────────┬─────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────────┐ ┌────────────┐ ┌──────────────────────┐
│ FX Validation  │ │Sensitivity │ │ Capital Risk Layer   │
│ (Phase 1)      │ │(Phase 2)   │ │ (Phase 3)            │
└────────────────┘ └────────────┘ └──────────────────────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │    finance layer + pipeline   │
          │  (cashflow, debt, metrics)    │
          └──────────────────────────────┘
```

---

## Phase 1: FX Foundation (Week 1)

### Objective
Establish solid FX validation and curve generation as the foundation for all downstream analytics.

### Tasks

#### 2.1.1: Implement `_validate_fx_block` in schema_guard
**File:** `validation/schema_guard.py`

```python
def _validate_fx_block(config: dict) -> list[str]:
    """Validate FX configuration block.

    Supports two modes:
    1. Scalar: Single LKR/USD rate for entire project life
    2. Structured: Annual escalation curve with base rate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    fx = config.get('fx', {})

    if not fx:
        errors.append("Missing 'fx' block in config")
        return errors

    # Check for required mode
    if 'lkr_per_usd' in fx:
        # Scalar mode
        rate = fx['lkr_per_usd']
        if not isinstance(rate, (int, float)) or rate <= 0:
            errors.append(f"fx.lkr_per_usd must be positive number, got {rate}")
    elif 'base_rate' in fx and 'escalation_pct' in fx:
        # Structured mode
        if fx['base_rate'] <= 0:
            errors.append("fx.base_rate must be positive")
        if not -10 <= fx['escalation_pct'] <= 10:
            errors.append("fx.escalation_pct must be between -10 and 10")
    else:
        errors.append("fx block must have either 'lkr_per_usd' (scalar) or 'base_rate'+'escalation_pct' (structured)")

    return errors
```

**Tests:**
- Scalar FX valid
- Structured FX valid
- Missing FX block
- Invalid escalation rate
- Negative base rate

#### 2.1.2: Create `build_fx_curve(config, life_years)`
**File:** `finance/fx_v14.py`

```python
from typing import List
import numpy as np

def build_fx_curve(config: dict, project_life_years: int) -> List[float]:
    """Build LKR/USD FX curve for project lifetime.

    Args:
        config: Scenario config with 'fx' block
        project_life_years: Number of years to generate

    Returns:
        List of annual LKR/USD rates (length = project_life_years + 1)
        Index 0 = construction/COD, 1 = Year 1, etc.
    """
    fx = config['fx']

    # Scalar mode
    if 'lkr_per_usd' in fx:
        rate = float(fx['lkr_per_usd'])
        return [rate] * (project_life_years + 1)

    # Structured mode
    base_rate = float(fx['base_rate'])
    escalation = float(fx['escalation_pct']) / 100.0

    curve = [base_rate * ((1 + escalation) ** year)
             for year in range(project_life_years + 1)]

    return curve
```

**Tests:**
- Scalar mode returns flat curve
- Structured mode applies escalation correctly
- Curve length matches project life + 1
- Escalation math validated against hand calculation

#### 2.1.3: Add FX tests
**File:** `tests/finance/test_fx_v14.py`

```python
def test_scalar_fx_curve():
    config = {'fx': {'lkr_per_usd': 300.0}}
    curve = build_fx_curve(config, 20)
    assert len(curve) == 21
    assert all(rate == 300.0 for rate in curve)

def test_structured_fx_curve():
    config = {'fx': {'base_rate': 300.0, 'escalation_pct': 2.0}}
    curve = build_fx_curve(config, 20)
    assert len(curve) == 21
    assert curve[0] == 300.0
    assert curve[10] == pytest.approx(300.0 * 1.02**10, rel=1e-4)

def test_fx_validation_scalar():
    config = {'fx': {'lkr_per_usd': 300.0}}
    errors = _validate_fx_block(config)
    assert len(errors) == 0

def test_fx_validation_missing():
    config = {}
    errors = _validate_fx_block(config)
    assert "Missing 'fx' block" in errors[0]
```

### Deliverables
- ✅ `finance/fx_v14.py` with `build_fx_curve()`
- ✅ `validation/schema_guard.py` with `_validate_fx_block()`
- ✅ `tests/finance/test_fx_v14.py` with 8+ tests
- ✅ All tests green before Phase 2

### Risk Mitigation
- **Low risk:** Net new code, no existing dependencies
- **Validation:** Run against all existing scenarios to ensure backward compatibility

---

## Phase 2: Sensitivity Rebuild (Week 2-3)

### Objective
Refactor sensitivity_v14 to be a pure client of evaluation_v14, with standardized shock specs and no direct finance imports.

### Current State Analysis
```python
# Current (broken pattern):
from finance.cashflow_v14 import build_cashflow  # ❌ FORBIDDEN
result = build_cashflow(...)  # ❌ Direct call

# Target (correct pattern):
from analytics.evaluation_v14 import evaluate_with_overrides  # ✅
result = evaluate_with_overrides(config_path, overrides)  # ✅
```

### Tasks

#### 2.2.1: Rebuild sensitivity_v14 around evaluation_v14

**Key Changes:**
1. Remove all `from finance.*` imports
2. Replace direct finance calls with `evaluate_with_overrides()`
3. Use `ShockSpec` contract for parameter overrides
4. Return `SensitivitySuite` contract

**Before:**
```python
def analyze_single_parameter(config, param_name, low, high):
    # Direct manipulation of config
    modified_config = copy.deepcopy(config)
    modified_config[param_name] = low
    cf_result = build_cashflow(modified_config)  # ❌
    return cf_result.project_irr
```

**After:**
```python
def analyze_single_parameter(
    config_path: Path,
    shock: ShockSpec,
) -> ShockResult:
    # Build override dict
    overrides = build_nested_override(shock.variable_name, shock.low_value)

    # Call through gateway
    kpis = evaluate_with_overrides(config_path, overrides)  # ✅

    return ShockResult(
        variable_name=shock.variable_name,
        low_value=shock.low_value,
        low_metric=kpis[shock.metric],
        ...
    )
```

#### 2.2.2: Create `ShockSpec` dataclass

**File:** `analytics/contracts_v14.py`

```python
@dataclass
class ShockSpec:
    """Specification for a single sensitivity shock."""
    variable_name: str  # e.g. "project.capacity_factor"
    base_value: float
    low_pct: float  # e.g. -10.0 for -10%
    high_pct: float  # e.g. +15.0 for +15%
    label: str | None = None  # Human-readable label

    @property
    def low_value(self) -> float:
        return self.base_value * (1 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        return self.base_value * (1 + self.high_pct / 100.0)

@dataclass
class ShockResult:
    """Result of a single sensitivity shock."""
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str  # e.g. "project_irr"

    @property
    def impact(self) -> float:
        """Absolute impact on metric."""
        return (self.high_metric - self.low_metric) / 2.0
```

#### 2.2.3: Implement `run_sensitivity_v14`

**File:** `analytics/sensitivity_v14.py`

```python
def run_sensitivity_v14(
    config_path: str | Path,
    shocks: List[ShockSpec] | None = None,
    metric: str = "project_irr",
) -> SensitivitySuite:
    """Run deterministic sensitivity analysis.

    Args:
        config_path: Path to base scenario YAML
        shocks: List of shocks to apply (if None, use standard library)
        metric: Target metric to analyze

    Returns:
        SensitivitySuite with baseline + shocked results
    """
    config_path = Path(config_path)

    # Get baseline
    baseline_kpis = evaluate_with_overrides(config_path, overrides=None)
    base_metric = baseline_kpis[metric]

    # Use standard shocks if not provided
    if shocks is None:
        shocks = _build_standard_shocks(config_path)

    # Run each shock
    results = []
    for shock in shocks:
        result = _run_single_shock(config_path, shock, baseline_kpis, metric)
        results.append(result)

    # Sort by impact
    tornado_results = sorted(results, key=lambda r: abs(r.impact), reverse=True)

    return SensitivitySuite(
        tornado_results=tornado_results,
        base_metric=base_metric,
        base_config_path=str(config_path),
        metric=metric,
    )
```

#### 2.2.5: Add standard shock families

**File:** `analytics/sensitivity_v14.py`

```python
def _build_standard_shocks(config_path: Path) -> List[ShockSpec]:
    """Build standard lender-grade shock library.

    Returns shocks for:
    - CAPEX ±10%
    - OPEX ±10%
    - Capacity Factor ±5%
    - Availability ±5%
    - Cost of Debt ±50 bps
    - Debt Tenor ±2 years
    - WACC ±100 bps (if WACC module enabled)
    - FX ±10% (if FX risk exposure)
    """
    # Load config to get base values
    with open(config_path) as f:
        config = yaml.safe_load(f)

    shocks = [
        ShockSpec(
            variable_name="capex.usd_total",
            base_value=config['capex']['usd_total'],
            low_pct=-10.0,
            high_pct=10.0,
            label="Total CAPEX",
        ),
        ShockSpec(
            variable_name="opex.usd_per_year",
            base_value=config['opex']['usd_per_year'],
            low_pct=-10.0,
            high_pct=10.0,
            label="Annual OPEX",
        ),
        ShockSpec(
            variable_name="project.capacity_factor",
            base_value=config['project']['capacity_factor'],
            low_pct=-5.0,
            high_pct=5.0,
            label="Capacity Factor",
        ),
        # Add more standard shocks...
    ]

    return shocks
```

### Deliverables
- ✅ `analytics/sensitivity_v14.py` (refactored, ~500 lines)
- ✅ `contracts_v14.ShockSpec` and `ShockResult` dataclasses
- ✅ `tests/analytics_layer/test_sensitivity_v14.py` (10+ tests)
- ✅ Standard shock library (8-10 shocks)
- ✅ All existing sensitivity tests still passing

### Risk Mitigation
- **Medium risk:** Refactoring existing code
- **Strategy:**
  - Create `sensitivity_v14_new.py` first
  - Validate against existing outputs
  - Swap files once validated
  - Keep old version in git history

---

## Phase 3: Capital Risk Integration (Week 4)

### Objective
Create a unified API that combines WACC, equity, sensitivity, and Monte Carlo into a single "capital risk bundle" for dashboards and exports.

### Tasks

#### 2.3.1-2.3.2: Create capital_risk_layer_v14.py and contracts

**File:** `analytics/contracts_v14.py`

```python
@dataclass
class CapitalRiskBundle:
    """Unified bundle of all capital & risk analytics."""

    # Core results
    scenario: ScenarioDescriptor
    baseline_kpis: dict[str, float]

    # Capital structure
    wacc_result: WaccResult | None
    equity_result: EquityResult | None

    # Risk analytics
    sensitivity_suite: SensitivitySuite | None
    monte_carlo: MonteCarloResult | None

    # Optimization (if requested)
    optimization_result: OptimizationResult | None

    # Metadata
    metadata: dict[str, Any]
    timestamp: str
```

#### 2.3.3: Implement `build_capital_risk_bundle`

**File:** `analytics/capital_risk_layer_v14.py`

```python
def build_capital_risk_bundle(
    config_path: str | Path,
    monte_carlo_config_path: str | Path | None = None,
    run_sensitivity: bool = True,
    run_optimization: bool = False,
    metric: str = "project_irr",
    confidence: float = 0.9,
) -> CapitalRiskBundle:
    """Build comprehensive capital & risk analytics bundle.

    This is the ONE-STOP API for dashboards, exports, and reports.

    Args:
        config_path: Base scenario config
        monte_carlo_config_path: Optional MC config
        run_sensitivity: Whether to run tornado analysis
        run_optimization: Whether to run capital structure optimization
        metric: Target metric for risk analysis
        confidence: Confidence level for tail risk (default 90%)

    Returns:
        CapitalRiskBundle with all requested analytics
    """
    config_path = Path(config_path)

    # 1. Run CASPER (baseline + MC + tail risk)
    casper_result = evaluate_with_casper_tail_risk(
        config_path=config_path,
        monte_carlo_config_path=monte_carlo_config_path,
        metric=metric,
        confidence=confidence,
        sensitivity_suite=None,  # Will add separately
    )

    # 2. Run sensitivity if requested
    sensitivity_suite = None
    if run_sensitivity:
        sensitivity_suite = run_sensitivity_v14(
            config_path=config_path,
            shocks=None,  # Use standard library
            metric=metric,
        )

        # Enrich tornado with tail risk if MC was run
        if casper_result.monte_carlo is not None:
            # This adds VaR, CVaR, breach prob to tornado table
            enriched_tornado = enrich_tornado_with_tail_risk(
                tornado_suite=sensitivity_suite,
                mc_result=casper_result.monte_carlo,
                metric=metric,
                confidence=confidence,
            )
            # Store in metadata for export
            casper_result.metadata['enriched_tornado_df'] = enriched_tornado

    # 3. Run optimization if requested
    optimization_result = None
    if run_optimization:
        optimization_result = optimize_capital_structure_v14(
            config_path=config_path,
            objective="equity_irr",
            constraints=OptimizationConstraints(
                min_irr=0.15,
                min_dscr=1.30,
            ),
        )

    # 4. Bundle everything
    return CapitalRiskBundle(
        scenario=casper_result.scenario,
        baseline_kpis=casper_result.baseline_kpis,
        wacc_result=None,  # TODO: Extract from pipeline
        equity_result=None,  # TODO: Extract from pipeline
        sensitivity_suite=sensitivity_suite,
        monte_carlo=casper_result.monte_carlo,
        optimization_result=optimization_result,
        metadata=casper_result.metadata,
        timestamp=datetime.now().isoformat(),
    )
```

#### 2.3.4: Add capital risk bundle tests

**File:** `tests/analytics_layer/test_capital_risk_layer.py`

```python
def test_build_capital_risk_bundle_smoke():
    """Smoke test: build bundle with all features."""
    bundle = build_capital_risk_bundle(
        config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        monte_carlo_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
        run_sensitivity=True,
        run_optimization=False,  # Expensive, skip for smoke
    )

    assert bundle.baseline_kpis is not None
    assert bundle.sensitivity_suite is not None
    assert bundle.monte_carlo is not None
    assert len(bundle.sensitivity_suite.tornado_results) > 0
    assert bundle.metadata['tail_risk_summary'] is not None

def test_build_capital_risk_bundle_minimal():
    """Test minimal bundle (no MC, no sensitivity)."""
    bundle = build_capital_risk_bundle(
        config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        run_sensitivity=False,
        run_optimization=False,
    )

    assert bundle.baseline_kpis is not None
    assert bundle.sensitivity_suite is None
    assert bundle.monte_carlo is None
```

### Deliverables
- ✅ `analytics/capital_risk_layer_v14.py` (~200 lines)
- ✅ `contracts_v14.CapitalRiskBundle` dataclass
- ✅ `tests/analytics_layer/test_capital_risk_layer.py` (5+ tests)
- ✅ Integration with CASPER, sensitivity, optimization

### Risk Mitigation
- **Low risk:** Net new code, clear interfaces
- **Strategy:** Build incrementally, test each component before integration

---

## Implementation Timeline

| Week | Phase | Deliverables | Dependencies |
|------|-------|--------------|--------------|
| 1 | FX Foundation | fx_v14.py, schema_guard validation, tests | None |
| 2-3 | Sensitivity Rebuild | sensitivity_v14.py refactored, ShockSpec, tests | FX complete |
| 4 | Capital Risk Layer | capital_risk_layer_v14.py, bundle contract, tests | Sensitivity + WACC/Equity from Swimlane 1 |

**Total Duration:** 4 weeks
**Critical Path:** FX → Sensitivity → Capital Risk Layer
**Parallel Work:** Can proceed alongside Swimlane 1 (WACC/Equity/Optimization)

---

## Success Criteria

### Phase 1 Success
- ✅ All FX tests passing
- ✅ FX validation integrated into schema_guard
- ✅ No regressions in existing scenarios

### Phase 2 Success
- ✅ All sensitivity tests passing
- ✅ No direct finance imports in sensitivity_v14
- ✅ Standard shock library covers 8+ parameters
- ✅ Tornado outputs match existing format

### Phase 3 Success
- ✅ Capital risk bundle API functional
- ✅ Integration tests passing
- ✅ Can generate full risk report in single call
- ✅ Exports remain stable (Excel, JSON, CSV)

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing sensitivity outputs | High | Parallel development + validation |
| FX validation too strict | Medium | Extensive testing on all scenarios |
| Circular imports | Medium | Lazy loading + clear dependency graph |
| Performance degradation | Low | Benchmark before/after, optimize if needed |
| Test coverage gaps | Medium | Target 80%+ coverage for new code |

---

## Dependencies on Swimlane 1

Phase 3 (Capital Risk Layer) requires:
- `WaccResult` from Swimlane 1.1
- `EquityResult` from Swimlane 1.2
- `optimize_capital_structure_v14` from Swimlane 1.3

**Coordination Point:** End of Week 3 - sync with Swimlane 1 team to ensure contracts are aligned.

---

## Post-Implementation Checklist

- [ ] All tests passing (pytest coverage > 80%)
- [ ] Type checking clean (mypy --strict)
- [ ] Linting clean (ruff, black, isort)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Integration tests with existing scenarios
- [ ] Performance benchmarks recorded
- [ ] Code review completed
- [ ] Merged to main branch
- [ ] Tagged as v14.3.0

---

## Next Steps

1. **Immediate:** Start Phase 1 (FX Foundation)
2. **Week 2:** Begin Phase 2 (Sensitivity) once FX tests pass
3. **Week 4:** Integrate with Swimlane 1 deliverables for Phase 3
4. **Week 5:** Full system integration test + Sprint 11 planning

---

**Document Owner:** Aruna
**Last Updated:** December 11, 2025
**Review Cycle:** Weekly during Sprint 10-11
