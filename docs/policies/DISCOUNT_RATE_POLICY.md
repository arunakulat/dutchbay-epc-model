# Discount Rate Policy - DutchBay V14 Financial Modeling

**Version:** 1.0  
**Date:** 2025-12-23  
**Author:** DutchBay Analytics Team  
**Status:** Approved  
**Compliance:** CASPER, CESSPIT, GWTF

---

## Executive Summary

This policy establishes clear guidelines for discount rate selection, calculation, and application across the DutchBay V14 financial modeling pipeline. All project finance models must follow these standards to ensure consistency, transparency, and lender-grade accuracy.

**Key Principle:** Discount rates must be **explicit, config-driven, and traceable** through the entire calculation chain.

---

## 1. Discount Rate Hierarchy

### 1.1 Priority Order

When calculating NPV, the system follows this hierarchy:

```
1. Explicit config parameter (highest priority)
   ↓
2. Calculated WACC (if debt structure provided)
   ↓
3. DEFAULT_DISCOUNT_RATE constant (fallback only)
```

### 1.2 Rate Types

The v14 pipeline distinguishes between three discount rate concepts:

| Rate Type | Purpose | Typical Range | Config Key |
|-----------|---------|---------------|------------|
| **Project Discount Rate** | Discount project-level CFADS | 8-12% | `returns.project_discount_rate` |
| **Equity Discount Rate** | Discount equity cashflows | 12-18% | `returns.equity_discount_rate` |
| **WACC** | Weighted average cost of capital | 7-10% | Calculated from debt/equity structure |

**Why Different Rates?**
- **Project rate**: Reflects entire project risk (debt + equity blended)
- **Equity rate**: Reflects equity investor risk (higher due to leverage)
- **WACC**: Theoretical market-based rate for entire firm

---

## 2. WACC Calculation Methodology

### 2.1 Standard Formula

```
WACC = (E/V) × Re + (D/V) × Rd × (1 - Tc)

Where:
  E = Market value of equity
  D = Market value of debt
  V = E + D (total firm value)
  Re = Cost of equity (expected return on equity)
  Rd = Cost of debt (interest rate on debt)
  Tc = Corporate tax rate
```

### 2.2 Component Calculations

#### Cost of Equity (Re) - CAPM Method

```
Re = Rf + β × (Rm - Rf)

Where:
  Rf = Risk-free rate (10-year government bond yield)
  β = Beta (equity volatility vs market)
  Rm = Expected market return
  (Rm - Rf) = Equity risk premium
```

**Typical Values:**
- **Risk-free rate (Rf):** 3-5% (Sri Lanka: 10-12%, USA: 4-5%)
- **Beta (β):** 0.8-1.2 (renewable energy projects)
- **Market risk premium:** 5-7%

#### Cost of Debt (Rd)

```
Rd = Base rate + Credit spread

Where:
  Base rate = LIBOR / SOFR / Local benchmark
  Credit spread = Project-specific risk premium
```

**Typical Values:**
- **Base rate:** SOFR + 200-400 bps
- **All-in debt cost:** 6-9% for investment-grade projects

### 2.3 WACC Implementation in V14

```python
# config/scenarios/dutchbay_lendercase_2025Q4.yaml
financing:
  debt_ratio: 0.70          # D/V = 70%
  equity_ratio: 0.30        # E/V = 30%
  debt_interest_rate: 0.08  # Rd = 8%
  equity_return_target: 0.15 # Re = 15%

tax:
  corporate_tax_rate: 0.24  # Tc = 24%

# Calculated WACC:
# WACC = 0.30 × 0.15 + 0.70 × 0.08 × (1 - 0.24)
#      = 0.045 + 0.04256
#      = 8.76%
```

---

## 3. Module-Specific Guidelines

### 3.1 `finance/irr.py` (NPV Engine - Singleton)

**Rule:** All NPV calculations MUST use `finance.irr.npv()`.

```python
from finance.irr import npv

# ✅ CORRECT - Uses singleton NPV engine
project_npv = npv(rate=0.10, cashflows=cfads_series)

# ❌ WRONG - Reimplements NPV logic
project_npv = sum(cf / (1 + 0.10)**i for i, cf in enumerate(cfads_series))
```

**Why?** 
- Single source of truth (GWTF R7)
- Consistent precision handling
- Configurable bounds for rate validation
- Centralized error handling

### 3.2 `finance/equity_v14.py` (Equity Performance)

**Rule:** Use `equity_discount_rate` for equity NPV, fallback to `DEFAULT_DISCOUNT_RATE`.

```python
def calculate_equity_npv(
    cashflows: Sequence[Number],
    *,
    discount_rate: Optional[float] = None,
) -> Optional[float]:
    rate = float(
        discount_rate if discount_rate is not None 
        else DEFAULT_DISCOUNT_RATE
    )
    return _npv_wrapper(rate, cashflows)
```

**Caller Responsibility:**
```python
from constants import DEFAULT_EQUITY_DISCOUNT_RATE

# ✅ CORRECT - Explicit rate from config
equity_npv = calculate_equity_npv(
    cashflows=equity_cf,
    discount_rate=config.returns.equity_discount_rate
)

# ⚠️ ACCEPTABLE - Uses fallback (but log warning)
equity_npv = calculate_equity_npv(cashflows=equity_cf)
```

### 3.3 `analytics/core/returns.py` (Returns Module)

**Rule:** Use `ReturnsConfig` with explicit rate validation.

```python
class ReturnsConfig(BaseModel):
    project_discount_rate: float = Field(
        ge=0.0, le=1.0, 
        description="Project discount rate (decimal)"
    )
    equity_discount_rate: float = Field(
        ge=0.0, le=1.0,
        description="Equity discount rate (decimal)"
    )
    
    @field_validator('equity_discount_rate')
    @classmethod
    def equity_rate_should_exceed_project_rate(cls, v, info):
        project_rate = info.data.get('project_discount_rate')
        if project_rate and v < project_rate:
            logger.warning(
                f"Equity discount rate ({v:.2%}) is lower than "
                f"project rate ({project_rate:.2%}). "
                f"This is unusual - equity should bear higher risk."
            )
        return v
```

### 3.4 `analytics/core/metrics.py` (Metrics Gateway)

**Rule:** Pass discount rate explicitly to all NPV calculations.

```python
def calculate_project_metrics(config: Dict) -> ProjectMetrics:
    # ✅ Extract rate from config
    discount_rate = config['returns']['project_discount_rate']
    
    # ✅ Pass explicitly
    project_npv = project_npv_from_cfads(
        rate=discount_rate,
        cfads_series=cfads,
        capex_total=capex
    )
    
    return ProjectMetrics(
        project_npv=project_npv,
        discount_rate_used=discount_rate,  # ✅ Track for audit
        ...
    )
```

### 3.5 Exports (`exports/summary_export.py`)

**Rule:** All export files must include `discount_rate_used` metadata.

```python
# JSON export metadata
{
  "summary": {
    "project_npv_lkr": 5692483712.45,
    "equity_npv_lkr": 1234567890.12,
    "discount_rate_used": 0.10,          # ✅ Project rate
    "equity_discount_rate_used": 0.15,   # ✅ Equity rate
    "discount_rate_source": "config",    # ✅ Provenance
    "wacc_calculated": 0.0876            # ✅ For reference
  }
}
```

---

## 4. Config-Driven Rate Management

### 4.1 Canonical Config Structure

```yaml
# config/scenarios/dutchbay_lendercase_2025Q4.yaml

returns:
  # PRIMARY RATES (required)
  project_discount_rate: 0.10    # 10% - project WACC
  equity_discount_rate: 0.15     # 15% - equity target return
  
  # OPTIONAL RATES (for MIRR)
  finance_rate: 0.08             # Cost of borrowing (Rd)
  reinvest_rate: 0.10            # Reinvestment assumption
  
financing:
  debt_ratio: 0.70               # 70% debt
  debt_interest_rate: 0.08       # 8% interest
  
tax:
  corporate_tax_rate: 0.24       # 24% tax rate

# CALCULATED (not in config, computed at runtime):
# wacc = 0.3 × 0.15 + 0.7 × 0.08 × (1 - 0.24) = 8.76%
```

### 4.2 Validation Rules

```python
@field_validator('returns')
@classmethod
def validate_discount_rates(cls, returns_config):
    proj_rate = returns_config['project_discount_rate']
    eq_rate = returns_config['equity_discount_rate']
    
    # Rule 1: Equity rate should exceed project rate
    if eq_rate < proj_rate:
        logger.warning(
            f"Equity rate ({eq_rate:.2%}) < Project rate ({proj_rate:.2%}). "
            f"Typically equity risk > project risk."
        )
    
    # Rule 2: Rates should be reasonable
    if proj_rate < 0.05 or proj_rate > 0.20:
        raise ValueError(
            f"Project discount rate {proj_rate:.2%} outside "
            f"typical range (5-20%)"
        )
    
    if eq_rate < 0.10 or eq_rate > 0.30:
        raise ValueError(
            f"Equity discount rate {eq_rate:.2%} outside "
            f"typical range (10-30%)"
        )
    
    return returns_config
```

---

## 5. Lender Reporting Requirements

### 5.1 Mandatory Disclosures

All financial models presented to lenders MUST include:

1. **Discount Rate Table:**
   ```
   | Rate Type           | Value | Source     | Justification           |
   |---------------------|-------|------------|-------------------------|
   | Project Discount    | 10.0% | WACC calc  | Debt 70%, Equity 30%    |
   | Equity Discount     | 15.0% | CAPM       | β=1.0, ERP=7%, Rf=8%    |
   | WACC (calculated)   | 8.8%  | Formula    | After-tax debt cost     |
   ```

2. **NPV Sensitivity to Discount Rate:**
   ```
   | Discount Rate | Project NPV (LKR M) | Change vs Base |
   |---------------|---------------------|----------------|
   | 8%            | 6,200               | +8.9%          |
   | 10% (base)    | 5,692               | —              |
   | 12%           | 5,234               | -8.0%          |
   ```

3. **Rate Selection Methodology:**
   - Document how WACC was calculated
   - Justify equity risk premium selection
   - Explain any deviations from market benchmarks

### 5.2 Export Metadata

```python
# exports/summary_export.py
summary_metadata = {
    "discount_rates": {
        "project_discount_rate": 0.10,
        "equity_discount_rate": 0.15,
        "wacc_calculated": 0.0876,
        "source": "config_explicit",  # or "wacc_calculated" or "default_fallback"
        "methodology": "CAPM for equity, debt interest for Rd, 70/30 debt/equity",
        "risk_free_rate": 0.08,
        "equity_beta": 1.0,
        "market_risk_premium": 0.07,
        "debt_interest_rate": 0.08,
        "tax_rate": 0.24
    }
}
```

---

## 6. Testing Requirements

### 6.1 Rate Pass-Through Tests

```python
def test_discount_rate_pass_through(base_config):
    """Ensure discount rate from config reaches NPV calculation."""
    config = base_config.copy()
    config['returns']['project_discount_rate'] = 0.12  # 12%
    
    result = evaluate_scenario(config)
    
    # ✅ Assert rate was used
    assert result.metadata['discount_rate_used'] == 0.12
    
    # ✅ Assert NPV changed appropriately
    # Higher discount rate → lower NPV
    base_npv = evaluate_scenario(base_config).project_npv
    assert result.project_npv < base_npv
```

### 6.2 WACC Calculation Tests

```python
def test_wacc_calculation():
    """Verify WACC formula implementation."""
    # Given
    debt_ratio = 0.70
    equity_ratio = 0.30
    cost_of_debt = 0.08
    cost_of_equity = 0.15
    tax_rate = 0.24
    
    # When
    wacc = calculate_wacc(
        debt_ratio=debt_ratio,
        equity_ratio=equity_ratio,
        cost_of_debt=cost_of_debt,
        cost_of_equity=cost_of_equity,
        tax_rate=tax_rate
    )
    
    # Then
    expected = 0.3 * 0.15 + 0.7 * 0.08 * (1 - 0.24)
    assert abs(wacc - expected) < 1e-6
    assert abs(wacc - 0.0876) < 1e-4  # 8.76%
```

### 6.3 Sensitivity Tests

```python
def test_npv_sensitivity_to_discount_rate(base_config):
    """NPV should decrease as discount rate increases."""
    rates = [0.08, 0.10, 0.12, 0.15]
    npvs = []
    
    for rate in rates:
        config = base_config.copy()
        config['returns']['project_discount_rate'] = rate
        result = evaluate_scenario(config)
        npvs.append(result.project_npv)
    
    # ✅ Assert monotonic decrease
    assert npvs == sorted(npvs, reverse=True)
```

---

## 7. Common Pitfalls and Solutions

### 7.1 Pitfall: Hardcoded Discount Rates

❌ **WRONG:**
```python
def calculate_project_npv(cfads_series):
    discount_rate = 0.10  # ❌ Hardcoded!
    return npv(discount_rate, cfads_series)
```

✅ **CORRECT:**
```python
def calculate_project_npv(cfads_series, config: Dict):
    discount_rate = config['returns']['project_discount_rate']
    return npv(discount_rate, cfads_series)
```

### 7.2 Pitfall: Using Project Rate for Equity NPV

❌ **WRONG:**
```python
# Using project rate for equity (underestimates equity risk)
equity_npv = calculate_equity_npv(
    cashflows=equity_cf,
    discount_rate=config.returns.project_discount_rate  # ❌ Too low!
)
```

✅ **CORRECT:**
```python
equity_npv = calculate_equity_npv(
    cashflows=equity_cf,
    discount_rate=config.returns.equity_discount_rate  # ✅ Reflects equity risk
)
```

### 7.3 Pitfall: Missing Rate Metadata in Exports

❌ **WRONG:**
```json
{
  "project_npv": 5692483712.45
  // ❌ No discount rate disclosed!
}
```

✅ **CORRECT:**
```json
{
  "project_npv": 5692483712.45,
  "discount_rate_used": 0.10,
  "discount_rate_source": "config"
}
```

---

## 8. Framework Compliance

### 8.1 CASPER Compliance

- ✅ **Clear API:** `discount_rate` parameter is explicit and typed
- ✅ **Predictable Errors:** Pydantic validation for rate ranges (0-100%)
- ✅ **Contract-Driven:** `ReturnsConfig` enforces rate requirements

### 8.2 CESSPIT Compliance

- ✅ **Config Explicit:** No hardcoded rates, all from YAML
- ✅ **Schema Strict:** Pydantic validates rate ranges
- ✅ **Pre-flight Integrity:** Config validation before pipeline execution

### 8.3 GWTF Compliance

- ✅ **R7 Singleton:** `finance.irr.npv()` is the only NPV implementation
- ✅ **R16 No Circular Imports:** Rate constants in `constants.py`, NPV logic in `finance.irr`
- ✅ **R3 No Argparse:** Rates from YAML, not command-line arguments

---

## 9. Decision Matrix

Use this matrix to select the appropriate discount rate:

| Calculation Type | Use This Rate | Config Key | Typical Value |
|------------------|---------------|------------|---------------|
| Project NPV | `project_discount_rate` | `returns.project_discount_rate` | 8-12% |
| Equity NPV | `equity_discount_rate` | `returns.equity_discount_rate` | 12-18% |
| DSCR Calculation | Not applicable | — | — |
| IRR Calculation | Not applicable (IRR is calculated) | — | — |
| Profitability Index | Same as NPV calculation | — | — |
| MIRR | `finance_rate` & `reinvest_rate` | `returns.finance_rate`, `returns.reinvest_rate` | 6-10%, 8-12% |

---

## 10. References

### 10.1 Internal Documentation

- `finance/irr.py` - Core NPV/IRR engine
- `finance/equity_v14.py` - Equity performance metrics
- `analytics/core/returns.py` - Returns calculation module
- `constants.py` - DEFAULT_DISCOUNT_RATE and other constants

### 10.2 External Standards

- **Damodaran, A.** (2012). *Investment Valuation: Tools and Techniques for Determining the Value of Any Asset*. Wiley.
- **Brealey, R., Myers, S., & Allen, F.** (2020). *Principles of Corporate Finance*. McGraw-Hill.
- **IFC** (2015). *Disclosure and Transparency in Project Finance*. World Bank Group.

### 10.3 Industry Benchmarks

- **BNEF** (2024). *Renewable Energy WACC Benchmarks* - 7-10% for wind projects
- **IEA** (2024). *World Energy Investment* - Discount rate guidance for emerging markets
- **IRENA** (2023). *Renewable Power Generation Costs* - Regional WACC data

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-23 | DutchBay Analytics Team | Initial policy document |

---

## Approval

**Policy Owner:** DutchBay V14 Core Team  
**Approved By:** Sprint 18 Technical Review  
**Effective Date:** 2025-12-23  
**Next Review:** 2026-Q2 (6 months)

---

**Questions?** Contact the DutchBay Analytics Team or open an issue with label `discount-rate`.
