# SENS-001 Quick Reference: ShockSpec & ShockResult Contracts

**Sprint 10 – Phase 2 – CCCDIR Compliant**
**Status:** ✅ COMPLETE – Ready for SENS-002 Implementation

---

## Import Signature

```python
from analytics.contracts_v14 import (
    ShockSpec,
    ShockResult,
    SensitivitySuite,
    StandardShockLibrary,
)
```

---

## ShockSpec – Input Contract

**Define a shock to apply to a variable**

```python
shock = ShockSpec(
    variable_name="project.capacity_factor",    # Dotted path in config
    base_value=0.42,                            # Current value (for context)
    low_pct=-10.0,                              # Downside shock (%)
    high_pct=+10.0,                             # Upside shock (%)
    label="Capacity Factor"                     # Human-readable (optional)
)

# Computed properties
shock.low_value    # 0.378 (base * 1.10)
shock.high_value   # 0.462 (base * 1.10)
```

**Validation Rules:**
- `variable_name` cannot be empty
- `low_pct`, `high_pct` ∈ [-100, 100]
- Asymmetric OK (e.g., -5% downside, +20% upside for cost overrun)

---

## ShockResult – Output Contract

**Record the impact of a shock on a metric**

```python
result = ShockResult(
    variable_name="project.capacity_factor",    # From ShockSpec
    base_value=0.42,                            # From ShockSpec
    low_value=0.378,                            # After low shock
    high_value=0.462,                           # After high shock
    base_metric=0.1788,                         # Baseline IRR
    low_metric=0.1650,                          # IRR with low shock
    high_metric=0.1950,                         # IRR with high shock
    metric_name="project_irr",                  # What metric was measured
    label="Capacity Factor",                    # Optional, for charts
    metadata={'calc_time_ms': 142.5}            # Optional metadata
)

# Computed properties
result.impact       # 0.015 (1.5%) – Two-way impact for tornado ranking
result.direction    # 'positive' – 'positive' if low_metric < base_metric
result.sensitivity  # 0.85 – % metric change per 1% variable change
```

**Key Properties:**
- **impact**: `abs(high_metric - low_metric) / 2.0` → Used for tornado sorting
- **direction**: Sign of metric sensitivity (positive/negative/neutral)
- **sensitivity**: Elasticity – useful for cross-variable comparison

---

## SensitivitySuite – Collection Contract

**Bundle all shocks for one metric into a tornado**

```python
suite = SensitivitySuite(
    metric_name="project_irr",
    scenario=scenario_descriptor,
    shock_results=[result1, result2, result3, ...],  # One per variable
    baseline_value=0.1788,
    analysis_timestamp="2025-12-12T09:15:00Z"
)

# Key method
ranking = suite.tornado_ranking    # ShockResults sorted by impact (high to low)
```

---

## StandardShockLibrary – Pre-Configured Reference Shocks

**Use lender-grade standard shocks for consistency**

```python
from analytics.contracts_v14 import StandardShockLibrary

shocks = [
    StandardShockLibrary.capex_overrun(150.0),      # ±10% CAPEX
    StandardShockLibrary.opex_variation(25.0),      # ±10% OPEX
    StandardShockLibrary.capacity_factor(0.42),     # ±10% Capacity Factor
    StandardShockLibrary.power_price(8.5),          # ±15% Power Price
    StandardShockLibrary.fx_usd_lkr(330.0),        # ±10% USD/LKR FX
    StandardShockLibrary.debt_tenor(18.0),          # ±20% Debt Tenor
    StandardShockLibrary.interest_rate(0.07),       # ±200 bps Interest Rate
]
```

---

## Typical Workflow (Phase 2)

```python
# 1. Define shocks
shocks = [
    ShockSpec("project.capacity_factor", 0.42, -10, +10, "Capacity Factor"),
    ShockSpec("project.capex_millions", 150.0, -5, +20, "CAPEX Overrun"),
    # ... more shocks
]

# 2. Analyze via gateway (GWTF compliant)
from analytics.evaluation_v14 import evaluate_with_overrides

results = []
for shock in shocks:
    # Low scenario
    overrides_low = {shock.variable_name.split('.')[0]: {shock.variable_name.split('.')[-1]: shock.low_value}}
    kpis_low = evaluate_with_overrides(config_path, overrides_low)

    # High scenario
    overrides_high = {shock.variable_name.split('.')[0]: {shock.variable_name.split('.')[-1]: shock.high_value}}
    kpis_high = evaluate_with_overrides(config_path, overrides_high)

    # Build result
    result = ShockResult(
        variable_name=shock.variable_name,
        base_value=shock.base_value,
        low_value=shock.low_value,
        high_value=shock.high_value,
        base_metric=baseline_kpis['project_irr'],
        low_metric=kpis_low['project_irr'],
        high_metric=kpis_high['project_irr'],
        metric_name='project_irr',
        label=shock.label
    )
    results.append(result)

# 3. Create suite (tornado)
suite = SensitivitySuite(
    metric_name="project_irr",
    scenario=scenario,
    shock_results=results,
    baseline_value=baseline_kpis['project_irr'],
    analysis_timestamp=datetime.utcnow().isoformat()
)

# 4. Use for tornado chart
ranking = suite.tornado_ranking  # Sorted by impact
for result in ranking:
    print(f"{result.label}: {result.impact:.3%} impact")
```

---

## Export (For Excel, JSON, CSV)

```python
# Export to dict (JSON-serializable)
dict_result = result.to_dict()
# {
#     'variable_name': 'project.capacity_factor',
#     'base_metric': 0.1788,
#     'low_metric': 0.1650,
#     'high_metric': 0.1950,
#     'impact': 0.015,
#     'direction': 'positive',
#     'sensitivity': 0.85,
#     ...
# }

# Export suite
dict_suite = suite.to_dict()

# Export bundle (Phase 3)
json_str = bundle.to_json()  # Complete JSON export
```

---

## GWTF Compliance Rules

**Use contracts, not dicts:**
```python
# ✅ CORRECT
def analyze(config_path: str, shocks: list[ShockSpec]) -> SensitivitySuite:
    ...

# ❌ WRONG
def analyze(config_path: str, shocks: list[dict]) -> dict:
    ...
```

**Route through gateway, not direct finance imports:**
```python
# ✅ CORRECT
from analytics.evaluation_v14 import evaluate_with_overrides
kpis = evaluate_with_overrides(config_path, overrides)

# ❌ WRONG
from finance.cashflow_v14 import build_cashflow
cf = build_cashflow(config)
```

---

## Field Reference Table

| Contract | Field | Type | Purpose |
|---|---|---|---|
| ShockSpec | variable_name | str | Dotted config path |
| | base_value | float | Current value |
| | low_pct | float | Downside shock % |
| | high_pct | float | Upside shock % |
| | label | Optional[str] | Display name |
| **ShockResult** | **variable_name** | **str** | **From spec** |
| | base_value | float | From spec |
| | low_value | float | Computed low |
| | high_value | float | Computed high |
| | base_metric | float | Baseline metric |
| | low_metric | float | Metric @ low |
| | high_metric | float | Metric @ high |
| | metric_name | str | IRR, NPV, etc. |
| | label | Optional[str] | Display name |
| | metadata | dict | Audit trail |

---

## Computed Properties Reference

| Property | Contract | Formula | Use Case |
|---|---|---|---|
| low_value | ShockSpec | base_value × (1 + low_pct/100) | Config override |
| high_value | ShockSpec | base_value × (1 + high_pct/100) | Config override |
| impact | ShockResult | abs(high - low) / 2 | Tornado ranking |
| direction | ShockResult | Sign of (low - base) | Impact direction |
| sensitivity | ShockResult | (% Δ metric) / (% Δ variable) | Elasticity |
| tornado_ranking | SensitivitySuite | Sorted by impact | Chart generation |

---

## Validation & Error Messages

**ShockSpec:**
```
ValueError: variable_name cannot be empty
ValueError: low_pct must be in [-100, 100], got 150.0
ValueError: high_pct must be in [-100, 100], got 150.0
Warning: low_pct > high_pct (unusual but allowed)
```

**ShockResult:**
```
ValueError: variable_name cannot be empty
ValueError: metric_name cannot be empty
```

---

## Governance Compliance

| Framework | Status | Details |
|---|---|---|
| **CCCDIR** | ✅ | All APIs typed, no dicts |
| **CESSPIT** | ✅ | Validation in __post_init__() |
| **CASPER** | ✅ | Metadata fields, audit trail |
| **GWTF** | ✅ | Config-driven, contract-first, layered |

---

## Next Steps

**SENS-002:** Use these contracts to refactor `sensitivity_v14.py`
- Import contracts
- Remove direct finance imports
- Use `evaluate_with_overrides()` gateway
- Implement `analyze_sensitivity(config_path, shocks: list[ShockSpec]) -> SensitivitySuite`

**SENS-005:** Write unit tests for these contracts
**SENS-006:** Validate backward compatibility with existing tornado outputs

---

**Quick Ref Version:** 1.0
**Date:** 2025-12-12
**CCCDIR/CESSPIT/CASPER/GWTF Compliant** ✅
