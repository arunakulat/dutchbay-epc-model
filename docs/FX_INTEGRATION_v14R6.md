# FX Integration Guide (v14R6)

**Version**: 1.0  
**Date**: 2025-12-18  
**Status**: Sprint 15 - COMPLETE  
**Refs**: Issue #31, Sprint 15 Pipeline Integration  

---

## Overview

This document describes the FX Structured Blocks integration for dutchbay-epc-model v14.
It provides the architecture, data contracts, and integration points for multi-currency project
scenarios.

**Key Goals**:
- Support multi-currency debt (LKR, USD, CNY)
- Track FX exposure by period and debt tranche
- Provide lender-grade FX risk metrics (VaR, CVaR, concentration)
- Integrate seamlessly into ScenarioResult for dashboarding

---

## Architecture

### Module Structure

```
analytics/
  contracts_v14.py              # ScenarioResult with fx_block, fx_curve, fx_risk_profile
  fx/
    __init__.py                 # FX module exports
    fx_contracts.py             # Data contracts (frozen dataclasses, CESSPIT)
    fx_builder.py               # Factory functions for FX computation
  fx_integration.py             # Main entry point: integrate_fx_into_scenario_result()
```

### Data Flow

```
Project Config (YAML)
       ↓
  [analytics.fx_builder.compute_fx_structured_block()]
       ↓
FXStructuredBlock + FXVolumetry
       ↓
  [compute_fx_curve()]
       ↓
FXCurveOutput (annual LKR/USD rates)
       ↓
  [compute_fx_risk_profile()]
       ↓
FXRiskProfile (VaR, CVaR, HHI)
       ↓
  [integrate_fx_into_scenario_result()]
       ↓
ScenarioResult (with FX fields)
       ↓
Lender Report / Dashboard
```

---

## Core Data Structures

### FXVolumetry

Per-period (annual) exposure snapshot.

```python
@dataclass(frozen=True)
class FXVolumetry:
    period: int                 # Year index (0-based)
    total_debt_lkr: float       # LKR outstanding
    total_debt_usd: float       # USD outstanding
    total_debt_cny: float       # CNY outstanding
    revenue_lkr: float          # Annual revenue in LKR
    revenue_usd: float          # Annual revenue in USD
    interest_lkr: float         # Annual interest in LKR
    principal_lkr: float        # Annual principal in LKR
```

### FXCurveOutput

Time-series FX rate projections.

```python
@dataclass(frozen=True)
class FXCurveOutput:
    years: List[int]            # [0, 1, 2, ..., n_periods-1]
    lkr_usd: List[float]        # Annual LKR/USD rates
    lkr_cny: Optional[...]       # Optional: LKR/CNY rates
    lkr_eur: Optional[...]       # Optional: LKR/EUR rates
    lkr_gbp: Optional[...]       # Optional: LKR/GBP rates
    source: str                 # 'base_case', 'stress', etc.
    notes: str                  # Documentation
```

**Usage**: `curve.get_rate(year=1, pair='lkr_usd')` returns LKR/USD rate for Year 1.

### FXRiskProfile

Lender-grade FX risk summary.

```python
@dataclass(frozen=True)
class FXRiskProfile:
    var_95_usd_million: float   # 95% VaR in USD millions
    cvar_95_usd_million: float  # 95% CVaR (expected shortfall)
    debt_lkr_pct: float         # % of debt in LKR
    debt_usd_pct: float         # % of debt in USD
    debt_cny_pct: float         # % of debt in CNY
    debt_concentration_hhi: float  # Herfindahl index [0, 1]
    revenues_lkr_pct: float     # % of revenues in LKR
    correlation_shock_scenario: str  # Stress test description
    worst_case_year: Optional[int]   # Year of max stress
    recovery_years_to_1x_llcr: Optional[int]  # Recovery time
```

**Usage**: Check `profile.is_high_risk(threshold=5.0)` to flag portfolios with VaR > $5M.

### FXStructuredBlock

Primary FX configuration and snapshot (attached to ScenarioResult).

```python
@dataclass(frozen=True)
class FXStructuredBlock:
    strategy: Literal[...]  # 'natural_hedge', 'fixed_ccy', 'hedged', 'blended'
    base_currency: str      # Usually 'USD'
    reporting_currency: str # Usually 'USD'
    volumetry: List[FXVolumetry]  # Annual exposure snapshots
    debt_tranches: Dict[str, str]  # Tranche -> Currency mapping
    revenue_currencies: List[str]   # ['LKR', 'USD', ...]
    fx_match_ratio: float   # % of debt matched to revenue currency [0, 100]
    hedging_coverage_pct: float  # % of FX exposure hedged [0, 100]
    notes: str              # Special FX assumptions
```

---

## Integration Points

### 1. ScenarioResult

FX blocks are attached as optional fields:

```python
@dataclass
class ScenarioResult:
    ...
    fx_block: Optional[FXStructuredBlock] = None
    fx_curve: Optional[FXCurveOutput] = None
    fx_risk_profile: Optional[FXRiskProfile] = None
    ...
```

### 2. Pipeline Execution

In `pipeline_v14.run_full_pipeline_v14()` (pseudocode):

```python
def run_full_pipeline_v14(config: Mapping[str, Any]) -> ScenarioResult:
    # ..existing computation...
    scenario_result = ScenarioResult(
        scenario_name=...,
        project_npv=...,
        ...
    )
    
    # NEW: Integrate FX blocks
    from analytics.fx_integration import integrate_fx_into_scenario_result
    scenario_result = integrate_fx_into_scenario_result(
        scenario_result=scenario_result,
        config=config,
        debt_result=debt_output,
        annual_rows=cf_rows,
    )
    
    return scenario_result
```

### 3. Lender Reports

FX risk profile is included in CASPER payloads:

```python
payload = build_casper_payload(
    scenario=scenario_result,
    baseline_kpis=...,
    ...,
    metadata={'fx_var_95_usd_million': scenario_result.fx_risk_profile.var_95_usd_million},
)
```

Dashboards display:
- FX match ratio and hedging coverage
- Debt concentration (HHI)
- Annual LKR/USD rates from curve
- VaR/CVaR tail risk metrics

---

## Configuration Example

**Project Config YAML**:

```yaml
Project:
  name: "SolarPark_MultiCcy"
  ...

FX:
  strategy: "blended"  # or 'natural_hedge', 'fixed_ccy', 'hedged'
  base_currency: "USD"
  reporting_currency: "USD"
  fx_match_ratio: 50.0  # 50% debt matched to revenue currency
  hedging_coverage_pct: 30.0  # 30% of FX exposure hedged
  
  curve:
    source: "base_case"
    spot_lkr_usd: 300.0
    lkr_usd: [300, 302, 305, 308, 310]  # Annual projections
    lkr_cny: [42, 42.5, 43, 43.5, 44]   # Optional: CNY rates
    notes: "PPP-adjusted with 2% annual LKR depreciation"
  
  revenue_currencies: ["LKR"]
  notes: "Natural hedge strategy: LKR revenues offset LKR debt service"

Financing_Terms:
  Tranches:
    - Name: "LKR_Tranche"
      Currency: "LKR"
      Principal: 5000000000  # LKR
    - Name: "USD_Tranche"
      Currency: "USD"
      Principal: 15000000   # USD
    - Name: "CNY_Tranche"
      Currency: "CNY"
      Principal: 100000000  # CNY (optional)
```

---

## Validation & Standards

### GWTF (Go With The Flow)

- Full type hints on all functions
- Clear module docstrings
- Comprehensive function docstrings with Args, Returns, Raises

### CASPER (Credit Assessment Processing Engine Result)

- VaR/CVaR metrics for lender risk assessment
- Debt concentration (HHI) for portfolio diversification
- Currency-by-currency breakdown for covenant monitoring

### CESSPIT (Careful Error Specification, Strict Principle Input Typology)

- All data structures frozen (immutable) via `@dataclass(frozen=True)`
- Fail-fast validation in `__post_init__` methods
- Type checking on all inputs to public functions
- Clear error messages for debugging

### CCCDIR (Completely Commented Code Directory)

- Every function fully commented
- Every parameter documented
- Examples provided in module docstrings
- No configuration shortcuts; explicit YAML/JSON only

---

## Testing

Key test cases (see `tests/test_fx_integration.py`):

1. **Contract Validation**
   - FXVolumetry: periods > 0, debt values >= 0
   - FXCurveOutput: years/rates length match, rates > 0
   - FXRiskProfile: VaR <= CVaR, debt pct sum ~100%, HHI in [0,1]
   - FXStructuredBlock: fx_match_ratio and hedging_coverage_pct in [0,100]

2. **Builder Functions**
   - `compute_fx_structured_block()`: handles missing tranches gracefully
   - `compute_fx_curve()`: flat curve fallback if not specified
   - `compute_fx_risk_profile()`: empty volumetry returns safe defaults

3. **Integration**
   - `integrate_fx_into_scenario_result()`: round-trip test (to_dict/from_dict)
   - Immutability: verify no in-place mutations
   - Error propagation: malformed config raises ValueError with clear message

---

## Troubleshooting

### Issue: `FXCurveOutput: years and lkr_usd must have same length`

**Cause**: Config curve arrays don't match timeline.

**Fix**:
```yaml
FX:
  curve:
    lkr_usd: [300, 302, 305]  # Must have exactly 3 elements if timeline is 3 years
```

### Issue: `FXRiskProfile: debt percentages must sum to ~100%`

**Cause**: Debt assignment across tranches is incomplete.

**Fix**: Ensure all tranches are listed in config and debt_result has complete data.

### Issue: FX risk profile shows `is_high_risk() = True`

**Action**: Review VaR/CVaR metrics in lender report. Consider hedging or debt restructuring.

---

## Future Enhancements

- Monte Carlo simulation of FX rates + DSCR correlation
- Forward curve and hedging instrument pricing
- Multi-tranche netting and offset analysis
- Real-time FX rate updates from market feeds
- Scenario-based covenant analysis (e.g., "LKR -10% shock")

---

## References

- **Issue #31**: v14R6 FX Mapping Requirement
- **Sprint 15**: Pipeline Integration
- **Contracts**: `analytics/contracts_v14.py`
- **FX Module**: `analytics/fx/`
- **Builder**: `analytics/fx_integration.py`

---

**EOF - docs/FX_INTEGRATION_v14R6.md**
