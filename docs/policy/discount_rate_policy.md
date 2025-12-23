# Discount Rate Policy & Governance

**Version**: 1.0  
**Status**: Active  
**Owner**: Finance & Analytics Team  
**Last Updated**: 2025-12-23  
**Sprint**: 18 (P1 - Issue #7)

---

## Executive Summary

This document establishes **the canonical policy** for all discount rate calculations in the DutchBay EPC financial model. It defines:

1. **Rate definitions** (WACC, CoE, project vs equity rates)
2. **Unit normalization** (decimal vs percent, nominal vs real)
3. **Currency basis** (LKR vs USD rates)
4. **Config precedence rules** (scenario → WACC → fallback)
5. **Module consistency** (finance/* vs analytics/*)
6. **Lender reporting requirements**

**Critical Rule**: All modules **MUST** accept rates as decimals internally (0.12 = 12%). Any percent-to-decimal conversion **MUST** happen at config boundaries with explicit validation.

---

## 1. Definitions

### 1.1 Rate Types

| Rate Type | Symbol | Definition | Use Case |
|-----------|--------|------------|----------|
| **WACC (Nominal)** | WACC_n | Weighted average cost of capital after tax, nominal terms | Project-level NPV/IRR (unlevered cashflows) |
| **WACC (Real)** | WACC_r | WACC deflated by inflation: `(1+WACC_n)/(1+π) - 1` | Real cashflow discounting (if applicable) |
| **WACC (Prudential)** | WACC_p | WACC_n + prudential spread (default 100bps) | Conservative valuation for lenders |
| **Cost of Equity** | Ke / CoE | Return required by equity investors | Equity cashflow NPV/IRR |
| **Cost of Debt** | Kd | Pre-tax interest rate on debt | Debt service calculations |
| **Project Discount Rate** | r_proj | Generic project discount rate (often = WACC_n) | Legacy/config-specified rate |
| **Equity Discount Rate** | r_equity | Generic equity discount rate (often = Ke) | Equity NPV when CAPM not used |

### 1.2 Nominal vs Real

- **Nominal rates**: Include inflation, match nominal cashflows (most common)
- **Real rates**: Exclude inflation, match real (constant-dollar) cashflows
- **Default**: All cashflows in this model are **nominal LKR**, so use **nominal rates**
- **Conversion**: `real = (1 + nominal)/(1 + inflation) - 1` per Fisher equation

### 1.3 Levered vs Unlevered

| Term | Definition | Beta | Used For |
|------|------------|------|----------|
| **Unlevered (Asset)** | Pre-debt capital structure | β_asset | WACC calculation (asset risk) |
| **Levered (Equity)** | Post-debt capital structure | β_equity = β_asset × [1 + (1-T)×(D/E)] | Cost of equity via CAPM |

---

## 2. Unit Normalization

### 2.1 Internal Representation (STRICT RULE)

**All rates MUST be stored and passed as decimals internally:**

```python
# CORRECT
discount_rate = 0.12  # 12%
npv = calculate_npv(cashflows, discount_rate=0.12)

# INCORRECT (will break NPV calculations)
discount_rate = 12.0  # This is 1200%, not 12%
```

### 2.2 Config Boundary Normalization

**At config load time**, use `_pct_to_decimal()` helper (from `finance/wacc_v14.py`):

```python
def _pct_to_decimal(raw: Optional[float]) -> Optional[float]:
    """
    Interpret numeric as percent if > 1.0, else decimal.
    
    Examples:
        24.0   → 0.24  (24%)
        0.24   → 0.24  (24%)
        1.5    → 0.015 (1.5%)
        None   → None
    """
    if raw is None:
        return None
    if raw > 1.0:
        return raw / 100.0
    return raw
```

**Critical**: This conversion happens **once** at config load. Internal functions **NEVER** re-interpret units.

### 2.3 Validation

All rate-accepting functions **SHOULD** validate:

```python
def calculate_npv(cashflows: List[float], discount_rate: float) -> float:
    if not (0.0 <= discount_rate <= 1.0):
        raise ValueError(
            f"discount_rate must be decimal 0-1, got {discount_rate}. "
            f"Did you pass percent by mistake?"
        )
    # ... rest of function
```

**Exception**: Negative rates allowed in IRR solvers (for bisection bounds only, e.g. -0.9999).

---

## 3. Currency Basis

### 3.1 Rate Currency

| Cashflow Currency | Rate Basis | Note |
|-------------------|------------|------|
| **LKR** | LKR-based discount rate | Default for this model |
| **USD** | USD-based discount rate | If cashflows converted to USD |

**Critical**: Discount rate currency **MUST** match cashflow currency.

### 3.2 FX-Adjusted Rates

If model uses **multi-currency cashflows** (future feature):

```python
# Approximate USD → LKR rate conversion (Fisher-like)
r_lkr ≈ (1 + r_usd) × (1 + fx_depreciation_rate) - 1
```

**Current model**: All cashflows are LKR, so all rates are LKR-basis. No conversion needed.

---

## 4. Config Precedence Rules

### 4.1 Hierarchy (Strict Evaluation Order)

Discount rates are resolved in **strict precedence order**:

```
1. Scenario-specific config (scenarios/*.yaml)
   ↓ (if missing or null)
2. WACC calculation (finance/wacc_v14.py)
   ↓ (if missing or WACC disabled)
3. FAIL - no fallback constant allowed
```

**REMOVED**: `DEFAULT_DISCOUNT_RATE` from `constants.py` (CCCDIR compliance).

### 4.2 Scenario Config Specification

#### Option A: Direct Rates (Simple Mode)

```yaml
# scenarios/base_case_v14.yaml
financial:
  project_discount_rate: 12.0   # or 0.12 (auto-normalized)
  equity_discount_rate: 18.0    # or 0.18
```

**Effect**: Bypasses WACC calculation, uses specified rates directly.

#### Option B: WACC Mode (CAPM-Driven)

```yaml
# scenarios/base_case_v14.yaml
wacc:
  mode: capm
  risk_free: 5.0               # Risk-free rate (%)
  market_premium: 6.0          # Market risk premium (%)
  beta: 0.8                    # Asset beta
  gearing: 60.0                # D/V (%)
  cost_of_debt: 8.0            # Pre-tax cost of debt (%)
  tax_rate: 24.0               # Corporate tax rate (%)
  inflation_rate: 2.0          # Optional, for real WACC
  prudential_spread_bps: 100   # Lender markup (bps)

# If WACC specified, project_discount_rate = WACC_nominal
# and equity_discount_rate = CoE from CAPM
```

**Effect**: Calculates project and equity rates via CAPM, populates `WaccComponents`.

### 4.3 Rate Resolution Logic

```python
def get_project_discount_rate(config: Dict) -> float:
    """Canonical discount rate resolution."""
    # 1. Check scenario-specific override
    explicit_rate = config.get("financial", {}).get("project_discount_rate")
    if explicit_rate is not None:
        return _pct_to_decimal(explicit_rate)
    
    # 2. Try WACC calculation
    wacc_components = compute_wacc_from_config(config)
    if wacc_components:
        return wacc_components["wacc_nominal"]
    
    # 3. FAIL - no fallback allowed
    raise ValueError(
        "No discount rate specified. "
        "Add 'financial.project_discount_rate' or 'wacc' config block."
    )
```

**No silent fallback** - missing rates **MUST** fail loudly.

---

## 5. Module Consistency Rules

### 5.1 finance/* Module Rules

**Purpose**: Implement calculation logic (IRR, NPV, WACC, equity metrics).

**Rules**:
1. **NEVER** import or reference scenario configs directly
2. Accept discount rates as **function parameters only**
3. All rates **MUST** be decimals (0-1 range)
4. Validate rate inputs at function entry
5. **NO** hardcoded rates (e.g. no `default=0.12` in function signatures)

**Example (CORRECT)**:
```python
# finance/irr.py
def npv(rate: float, cashflows: Sequence[float]) -> float:
    """NPV calculation - rate must be decimal."""
    if rate <= -1.0:
        rate = -0.9999  # Numerical stability bound
    total = 0.0
    for t, cf in enumerate(cashflows):
        total += cf / ((1.0 + rate) ** t)
    return total
```

**Example (INCORRECT)**:
```python
# finance/irr.py - FORBIDDEN
from constants import DEFAULT_DISCOUNT_RATE  # ❌ REMOVED

def npv(rate: Optional[float] = None, ...):
    if rate is None:
        rate = DEFAULT_DISCOUNT_RATE  # ❌ Silent fallback
```

### 5.2 analytics/* Module Rules

**Purpose**: Orchestrate calculations, load configs, pass rates to finance/*.

**Rules**:
1. **MUST** load discount rates from scenario config
2. **MUST** normalize percent → decimal at config boundary
3. Pass rates explicitly to finance/* functions
4. **NO** direct calculation of discount rates (delegate to finance/wacc_v14.py)
5. Log rate sources for audit trail

**Example (CORRECT)**:
```python
# analytics/core/returns.py
def calculate_project_returns(cfads: List[float], config: ReturnsConfig) -> ProjectReturns:
    """Project returns - rate from config."""
    discount_rate = config.project_discount_rate  # Already normalized to decimal
    
    npv = calculate_npv(
        cashflows=cfads,
        discount_rate=discount_rate,  # Explicit pass-through
        start_period=config.operation_start_year
    )
    
    logger.info(f"NPV calculated with discount_rate={discount_rate:.4f}")
    return ProjectReturns(...)
```

### 5.3 Boundary Layer (Config Parsing)

**Location**: `analytics/core/returns.py::ReturnsConfig.from_yaml()`

**Responsibility**: Convert raw YAML → validated Pydantic models with normalized rates.

```python
class ReturnsConfig(BaseModel):
    project_discount_rate: float = Field(ge=0.0, le=1.0, description="Decimal 0-1")
    equity_discount_rate: float = Field(ge=0.0, le=1.0, description="Decimal 0-1")
    
    @classmethod
    def from_yaml(cls, config: Dict[str, Any]) -> "ReturnsConfig":
        """Parse and normalize rates from YAML."""
        project_dr_raw = config["returns"]["project_discount_rate"]
        equity_dr_raw = config["returns"]["equity_discount_rate"]
        
        # Normalize at boundary
        project_dr = _pct_to_decimal(project_dr_raw)
        equity_dr = _pct_to_decimal(equity_dr_raw)
        
        return cls(
            project_discount_rate=project_dr,
            equity_discount_rate=equity_dr,
            ...
        )
```

---

## 6. Lender Reporting Requirements

### 6.1 Disclosure Fields

All financial exports **MUST** include rate metadata:

```yaml
# outputs/scenario_summary.yaml
discount_rate_metadata:
  project_discount_rate: 0.12
  equity_discount_rate: 0.18
  rate_source: "wacc_capm"         # or "scenario_override"
  rate_basis: "nominal_lkr"        # nominal vs real, LKR vs USD
  wacc_mode: "capm"                # or "fixed"
  wacc_nominal: 0.12
  wacc_prudential: 0.13
  cost_of_equity: 0.18
  cost_of_debt_aftertax: 0.0608   # 8% × (1 - 0.24)
  inflation_rate: 0.02
  prudential_spread_bps: 100
```

### 6.2 Rate Provenance

Track **how** each rate was determined:

| Rate Source | Code | Description |
|-------------|------|-------------|
| `scenario_override` | SO | Directly specified in scenario YAML |
| `wacc_capm` | WC | Calculated via CAPM from WACC config |
| `wacc_fixed` | WF | Fixed rate from WACC config (non-CAPM) |
| `missing` | XX | ERROR - no rate found (should never happen in prod) |

**Example log line**:
```
INFO: Project NPV calculated: rate=0.1200 (12.00%), source=wacc_capm, basis=nominal_lkr
```

### 6.3 Prudential WACC Usage

For **lender reports**, use `wacc_prudential` (WACC + 100bps default):

```python
# Lender-facing NPV (conservative)
lender_npv = calculate_npv(cfads, discount_rate=wacc.wacc_prudential)

# Investor-facing NPV (base case)
investor_npv = calculate_npv(cfads, discount_rate=wacc.wacc_nominal)
```

**Reason**: Prudential spread provides downside buffer for credit assessment.

---

## 7. Edge Cases & Error Handling

### 7.1 Missing Rates

**Behavior**: **FAIL LOUD** - do not silently default.

```python
# CORRECT
if discount_rate is None:
    raise ValueError("Discount rate required but not found in config.")

# INCORRECT
discount_rate = discount_rate or 0.12  # ❌ Silent fallback
```

### 7.2 Percent-Decimal Ambiguity

**Example**: User specifies `1.5` – is this 1.5% or 150%?

**Rule**: Values > 1.0 are **assumed percent** and divided by 100.

```python
_pct_to_decimal(1.5)   # → 0.015 (1.5%)
_pct_to_decimal(0.015) # → 0.015 (1.5%)
```

**Limitation**: This heuristic **fails** for rates > 100% (e.g. 150%). For such cases, user **MUST** use decimal form (1.50).

### 7.3 Negative Rates (IRR Bounds Only)

**Allowed**: Only in IRR solver bounds (e.g. `lower_bound=-0.9999`).

**Forbidden**: Negative rates in NPV calculations (economically nonsensical).

```python
# finance/irr.py::npv()
if rate <= -1.0:
    rate = -0.9999  # Clamp to avoid division by zero
```

### 7.4 Out-of-Range Rates

**Validation**:
```python
if not (0.0 <= discount_rate <= 1.0):
    raise ValueError(
        f"Discount rate {discount_rate} out of valid range [0.0, 1.0]. "
        f"Rates > 100% are not supported."
    )
```

**Exception**: Bisection bounds in IRR solver may use `upper_bound=5.0` (500%) for numerical stability, but this is **NOT** a valid economic discount rate.

---

## 8. Testing Requirements

### 8.1 Guard Tests (Mandatory)

Create `tests/policy/test_discount_rate_policy.py` with:

1. **Test: Percent vs Decimal Ambiguity**
   - Verify `_pct_to_decimal(12.0) == 0.12`
   - Verify `_pct_to_decimal(0.12) == 0.12`

2. **Test: Config Precedence**
   - Scenario override takes precedence over WACC
   - WACC calculates if no override
   - Fails if neither provided

3. **Test: NPV Unit Consistency**
   - NPV with `rate=0.12` != NPV with `rate=12.0`
   - Latter should raise ValueError (out of range)

4. **Test: Rate Metadata Logging**
   - Verify all returns include `rate_source` and `rate_basis` fields

5. **Test: Currency Basis**
   - LKR cashflows with USD rate should fail (future feature)

### 8.2 Integration Tests

**File**: `tests/integration/test_returns_with_wacc.py`

```python
def test_wacc_override_precedence():
    """Scenario override takes precedence over WACC calculation."""
    config = {
        "financial": {
            "project_discount_rate": 10.0  # Override
        },
        "wacc": {
            "mode": "capm",
            "risk_free": 5.0,
            # ... full WACC config
        }
    }
    
    rate = get_project_discount_rate(config)
    assert rate == 0.10  # Uses override, not WACC
```

---

## 9. Migration Guide (Sprint 18+)

### 9.1 For Developers

**If you see this in code**:
```python
from constants import DEFAULT_DISCOUNT_RATE  # ❌ REMOVED
```

**Replace with**:
```python
# Option 1: Accept rate as parameter (preferred)
def my_function(cashflows: List[float], discount_rate: float):
    npv = calculate_npv(cashflows, discount_rate)

# Option 2: Load from config (at module boundaries only)
config = load_scenario_config("base_case_v14.yaml")
discount_rate = get_project_discount_rate(config)
```

### 9.2 For Config Authors

**Old (Sprint ≤ 17)**:
```yaml
# ❌ No explicit rate - used DEFAULT_DISCOUNT_RATE (0.12)
capex:
  usd_total: 50000000
```

**New (Sprint 18+)**:
```yaml
# ✅ Explicit rate required
financial:
  project_discount_rate: 12.0  # or use WACC mode

capex:
  usd_total: 50000000
```

---

## 10. Compliance Checklist

Before merging code that touches discount rates:

- [ ] All rates passed as **decimals** internally (0-1 range)
- [ ] Config boundary uses `_pct_to_decimal()` normalization
- [ ] Functions **validate** rate inputs (0 ≤ rate ≤ 1)
- [ ] No hardcoded rates (e.g. `default=0.12`)
- [ ] No imports from removed `constants.DEFAULT_DISCOUNT_RATE`
- [ ] Rate source logged for audit trail
- [ ] Lender outputs include rate metadata
- [ ] Guard tests pass (percent/decimal, precedence, metadata)

---

## 11. References

- **WACC Implementation**: [`finance/wacc_v14.py`](../../finance/wacc_v14.py)
- **IRR/NPV Core**: [`finance/irr.py`](../../finance/irr.py)
- **Returns Analytics**: [`analytics/core/returns.py`](../../analytics/core/returns.py)
- **Config Schema**: [`docs/CONFIG_SCHEMA.md`](../CONFIG_SCHEMA.md)
- **CCCDIR Principle**: Configuration in Config DIRectory (no hardcoded defaults)

---

## Appendix A: Quick Reference Table

| Scenario | Rate Source | Config Path | Internal Value |
|----------|-------------|-------------|----------------|
| Base case with CAPM | WACC (CAPM) | `wacc.mode=capm` | 0.12 (from WACC calc) |
| Base case override | Scenario config | `financial.project_discount_rate=12.0` | 0.12 |
| Prudential case | WACC + spread | `wacc.prudential_spread_bps=100` | 0.13 |
| Equity returns | CAPM CoE | Calculated from `wacc` block | 0.18 |
| Legacy config | **ERROR** | Missing rate | Raises ValueError |

---

## Appendix B: Formula Reference

### Fisher Equation (Nominal ↔ Real)
```
(1 + r_nominal) = (1 + r_real) × (1 + π)
r_real = [(1 + r_nominal) / (1 + π)] - 1
```

### CAPM Cost of Equity
```
Ke = Rf + β_equity × MRP
β_equity = β_asset × [1 + (1 - T) × (D/E)]
```

### After-Tax WACC
```
WACC = (E/V × Ke) + (D/V × Kd × (1 - T))
```

Where:
- `E/V` = equity-to-value ratio
- `D/V` = debt-to-value ratio (gearing)
- `T` = corporate tax rate
- `Kd` = pre-tax cost of debt

---

**Document End**

*This policy is legally binding for all financial calculations in the DutchBay EPC model. Deviations require written approval from Finance Team Lead.*
