# Finance Contracts Package

**Sprint 16 Consolidation** | **Status:** Complete

## Overview

This package provides unified data contracts for the v14 analytics pipeline using Pydantic V2. All pipeline modules must import analytics result types from this package to ensure contract compliance.

### Rationale for Organization

**Before (Fragmented):**
```
analytics/
├── contracts_v14.py           # Main Pydantic V2 contracts (10KB)
├── contracts_v14.py.bak2      # Old backup file
├── contractsv14.py           # Typo duplicate?
└── contracts/                # Partial subfolder
    ├── __init__.py            # Limited re-exports
    └── _phase_3_sensitivity.py # Legacy contracts
```

**After (Organized):**
```
analytics/
├── contracts_v14.py           # ✅ Source of truth (remains at root for backward compat)
└── contracts/                # 🆕 UNIFIED PACKAGE
    ├── __init__.py            # Complete re-exports from contracts_v14.py
    ├── README.md              # This documentation
    └── _phase_3_sensitivity.py # Legacy backward compat
```

---

## Public API

### Version Tracking

```python
from analytics.contracts import CASPER_CONTRACT_VERSION

print(CASPER_CONTRACT_VERSION)  # "v1.0"
```

### Monte Carlo (Sprint 16 - Issue #43)

```python
from analytics.contracts import (
    Distribution,
    DerivedParameter,
    MonteCarloScenario,
    MonteCarloResult,
)

# Define distribution for parameter
dist = Distribution(
    dist_type="normal",
    parameters={"mean": 0.08, "std": 0.02}
)

# Complete MC scenario
scenario = MonteCarloScenario(
    scenario_name="capex_risk",
    n_iterations=10000,
    sampling_method="lhs",
    seed=42,
    distributions={
        "capex_shock": dist
    }
)

# Process result
result = MonteCarloResult(
    scenario_name="capex_risk",
    n_iterations=10000,
    mean=0.127,
    std=0.032,
    p10=0.089,
    p50=0.125,
    p90=0.168,
    min_value=0.045,
    max_value=0.235,
    metric_name="project_irr",
    sampling_method="lhs"
)
```

**Features:**
- Frozen Pydantic models (immutable)
- Built-in validation (dist_type, sampling_method)
- Support for derived parameters
- VaR/CVaR risk metrics

### WACC Contracts

```python
from analytics.contracts import WaccComponents, WaccResult, ScenarioResult

# WACC breakdown
wacc = WaccComponents(
    mode="nominal",
    wacc_nominal=0.092,
    wacc_real=None,
    wacc_prudential=0.102,
    risk_free_rate=0.045,
    market_risk_premium=0.065,
    asset_beta=0.85,
    target_debt_to_equity=1.5,
    target_debt_to_value=0.60,
    target_equity_to_value=0.40,
    cost_of_debt_pretax=0.055,
    cost_of_debt_aftertax=0.044,
    equity_beta_levered=1.28,
    cost_of_equity=0.128,
    tax_rate=0.20,
    inflation_rate=None,
    prudential_spread_bps=100
)

# Complete WACC result
wacc_result = WaccResult(
    base=wacc,
    prudential_rate=0.102,
    prudential_npv=45_000_000
)
```

### FX Contracts (Sprint 15 - Issue #31)

```python
from analytics.contracts import (
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
)

# These are re-exported from analytics.fx.fx_contracts
# Full documentation in analytics/fx/README.md
```

### Sensitivity Analysis

```python
from analytics.contracts import (
    ParameterRangeConfig,
    TornadoResult,
    SensitivitySuite,
    BreakevenResult,
)

# Parameter shock configuration
param = ParameterRangeConfig(
    variable_name="finance.capex_usd",
    base_value=100_000_000,
    low_pct=-10.0,  # -10%
    high_pct=10.0,  # +10%
    label="CAPEX"
)

# Tornado result
tornado = TornadoResult(
    metric_name="capex_usd",
    base_metric=0.125,
    shock_results=[ShockResult(
        low_case=0.112,
        high_case=0.138,
        impact=0.026
    )],
    label="CAPEX",
    impact_abs=0.026
)

# Breakeven analysis
breakeven = BreakevenResult(
    variable="finance.capex_usd",
    target_metric="project_irr",
    target_value=0.10,
    breakeven_value=112_500_000,
    status="success",
    bracket=(90_000_000, 130_000_000)
)
```

### CASPER Unified Result

```python
from analytics.contracts import CasperResult

result = CasperResult(
    scenario="dutchbay_lendercase_2025Q4",
    baseline_kpis={
        "project_irr": 0.125,
        "project_npv": 45_000_000,
        "dscr_min": 1.35
    },
    sensitivities={...},
    monte_carlo={...}
)

print(result.contract_version())  # "v1.0"
```

---

## Backward Compatibility

### All Old Imports Still Work

**Old way (still functional):**
```python
# Direct import from v14 file
from analytics.contracts_v14 import MonteCarloScenario, WaccResult

# Legacy sensitivity contracts
from analytics.contracts import ShockSpec, StandardShockLibrary
```

**New way (recommended):**
```python
# Unified package import
from analytics.contracts import (
    MonteCarloScenario,
    WaccResult,
    ShockSpec,  # Legacy still available
    StandardShockLibrary,  # Legacy still available
)
```

**Both import patterns work identically.** Existing code requires **zero changes**.

---

## File Organization

### Current Structure (Phase 1)

During Phase 1, the source file remains at root for maximum backward compatibility:

```
analytics/
├── contracts_v14.py           # ✅ SOURCE OF TRUTH (stays at root)
│                             #    - All Pydantic V2 contracts
│                             #    - 400+ lines, fully typed
│                             #    - Monte Carlo (Sprint 16)
│                             #    - WACC, FX, Sensitivity
│
└── contracts/                # 🆕 UNIFIED PACKAGE
    ├── __init__.py            # Re-exports from contracts_v14.py
    ├── README.md              # This documentation
    └── _phase_3_sensitivity.py # Legacy contracts (backward compat)
```

### Planned Structure (Phase 2 - Future)

```
analytics/
└── contracts/
    ├── __init__.py            # Public API
    ├── README.md              # Documentation
    ├── core.py                # From contracts_v14.py (WACC, Scenario)
    ├── monte_carlo.py         # MC contracts
    ├── sensitivity.py         # Sensitivity contracts
    ├── casper.py              # CASPER unified result
    └── _legacy.py             # From _phase_3_sensitivity.py
```

**Note:** Phase 2 requires careful import updates and testing. Deferred to Sprint 17.

---

## Usage Examples

### Basic Scenario Evaluation

```python
from analytics.contracts import ScenarioResult, WaccResult
from analytics.pipeline_v14 import run_v14_pipeline

# Run pipeline
result = run_v14_pipeline(
    config_path="scenarios/dutchbay_base.yaml",
    validation_mode="strict"
)

# Result is a ScenarioResult contract
assert isinstance(result, ScenarioResult)

print(f"Project IRR: {result.project_irr:.2%}")
print(f"Min DSCR: {result.min_dscr:.2f}")
print(f"WACC: {result.wacc.base.wacc_nominal:.2%}")
```

### Monte Carlo Analysis

```python
from analytics.contracts import MonteCarloScenario, Distribution
from analytics.monte_carlo_engine import run_monte_carlo

# Define scenario
scenario = MonteCarloScenario(
    scenario_name="revenue_risk",
    n_iterations=10000,
    sampling_method="lhs",
    seed=42,
    distributions={
        "tariff_shock": Distribution(
            dist_type="normal",
            parameters={"mean": 0.0, "std": 0.05}
        ),
        "capacity_factor_shock": Distribution(
            dist_type="beta",
            parameters={"alpha": 5, "beta": 2, "scale": 0.1}
        )
    }
)

# Run simulation
mc_result = run_monte_carlo(scenario, base_config_path="scenarios/base.yaml")

# Analyze results
print(f"Mean IRR: {mc_result.mean:.2%}")
print(f"10th percentile: {mc_result.p10:.2%}")
print(f"90th percentile: {mc_result.p90:.2%}")
print(f"VaR(95%): {mc_result.var_95:.2%}")
```

### Sensitivity Analysis

```python
from analytics.contracts import ParameterRangeConfig, SensitivityRequest
from analytics.sensitivity_v14 import run_tornado_sensitivity

# Define parameters to shock
request = SensitivityRequest(
    base_config_path="scenarios/dutchbay_base.yaml",
    parameters=[
        ParameterRangeConfig(
            variable_name="finance.capex_usd",
            base_value=100_000_000,
            low_pct=-10,
            high_pct=10,
            label="CAPEX"
        ),
        ParameterRangeConfig(
            variable_name="revenue.tariff_usd_per_mwh",
            base_value=85.0,
            low_pct=-15,
            high_pct=15,
            label="Tariff"
        )
    ],
    metric="project_irr"
)

# Run tornado
tornado_results = run_tornado_sensitivity(request)

# Rank by impact
for result in sorted(tornado_results, key=lambda x: x.impact_abs, reverse=True):
    print(f"{result.label}: {result.impact_abs:.2%} impact")
```

---

## Architecture Principles

### GWTF (Go-With-The-Flow)

- **Single source:** `contracts_v14.py` is the canonical definition
- **Clear delegation:** Package re-exports, doesn't redefine
- **Predictable imports:** Old and new patterns both work

### CESSPIT (Comprehensive Error Handling)

- **Fail-fast:** Pydantic validation at instantiation
- **Clear errors:** Validation messages specify exact issue
- **Type safety:** All fields fully type-annotated

### CASPER (Contract-First Design)

- **Frozen models:** All contracts are immutable (Pydantic `frozen=True`)
- **Explicit validation:** Field validators for complex constraints
- **Version tracking:** `CASPER_CONTRACT_VERSION` for compatibility

### CCCDIR (Clear, Complete, Consistent Documentation)

- **Package-level:** This README
- **Module-level:** Comprehensive docstrings in `contracts_v14.py`
- **Field-level:** Every field documented with `Field(description=...)`
- **Usage examples:** Practical code samples throughout

---

## Testing

### Contract Validation Tests

```python
import pytest
from pydantic import ValidationError
from analytics.contracts import Distribution, MonteCarloScenario

def test_distribution_validation():
    """Test distribution type validation."""
    # Valid
    dist = Distribution(
        dist_type="normal",
        parameters={"mean": 0.0, "std": 1.0}
    )
    
    # Invalid dist_type
    with pytest.raises(ValidationError):
        Distribution(
            dist_type="invalid",
            parameters={}
        )

def test_monte_carlo_scenario_validation():
    """Test MC scenario validation."""
    # Valid
    scenario = MonteCarloScenario(
        scenario_name="test",
        n_iterations=1000,
        distributions={}
    )
    
    # Invalid: n_iterations must be > 0
    with pytest.raises(ValidationError):
        MonteCarloScenario(
            scenario_name="test",
            n_iterations=0,
            distributions={}
        )

def test_backward_compatibility():
    """Verify all old imports still work."""
    # Old imports
    from analytics.contracts_v14 import MonteCarloScenario as Old
    
    # New imports
    from analytics.contracts import MonteCarloScenario as New
    
    # Should be same class
    assert Old is New
```

### Run Tests

```bash
# From repository root
pytest tests/test_contracts.py -v

# Test specific contract
pytest tests/test_contracts.py::test_monte_carlo_scenario_validation -v
```

---

## Related Documentation

- [Sprint 16 Reorganization Complete](../../docs/SPRINT_16_REORGANIZATION_COMPLETE.md)
- [FX Contracts](../fx/README.md)
- [Sensitivity Analysis](../sensitivity/REORGANIZATION.md)
- [GWTF Framework](../../docs/gwtf_framework.md)
- [Pipeline Documentation](../../docs/pipeline_v14.md)

---

## Changelog

### Sprint 16 (December 21, 2025)

**Phase 1: Package Consolidation**
- ✅ Updated `__init__.py` with complete re-exports from `contracts_v14.py`
- ✅ Added comprehensive documentation (this README)
- ✅ Maintained 100% backward compatibility
- ✅ Zero breaking changes

**Deferred to Sprint 17:**
- ⏸️ Move `contracts_v14.py` content into `/contracts/` submodules
- ⏸️ Create separate files: `core.py`, `monte_carlo.py`, `sensitivity.py`
- ⏸️ Add comprehensive test suite for all contracts
- ⏸️ Performance optimization for Pydantic validation

---

## Contributing

### Adding New Contracts

1. **Add to** `contracts_v14.py` (for now)
2. **Re-export from** `contracts/__init__.py`
3. **Update** this README with usage examples
4. **Add tests** in `tests/test_contracts.py`
5. **Update** `__all__` in both files

### Phase 2 Migration (Future)

When moving to Phase 2:

1. Create modular files in `/contracts/` subfolder
2. Update imports in `__init__.py`
3. Keep `contracts_v14.py` as deprecated stub with deprecation warnings
4. Update all documentation
5. Run full test suite
6. Update CI/CD pipelines

---

**Document Status:** ✅ Complete  
**Last Updated:** December 21, 2025, 7:24 AM +0530  
**Sprint:** 16  
**Maintained By:** Sprint 16 Engineering Team
