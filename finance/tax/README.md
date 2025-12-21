# Tax Package

**Sprint 16 Iteration 5** | **Status:** Complete

## Overview

This package provides unified tax calculation functionality for the v14 analytics pipeline, including depreciation scheduling, corporate tax computations, and future support for tax holidays and enhanced capital allowances.

### Rationale for Organization

**Before (Fragmented):**
```
finance/
├── tax_v14.py                  # Main tax calculator (small, 100 lines)
├── tax_profile_v14_hydra.py    # Legacy hydra integration
├── cashflow_v14_tax.py         # Tax-integrated cashflow (backup exists)
├── cashflow_v14_tax.py.bak     # Backup file (NEEDS CLEANUP)
└── dutchbay_finmodel/
    └── tax_profile.py          # Legacy tax profile
```

**After (Organized):**
```
finance/
├── tax_v14.py                  # ✅ SOURCE OF TRUTH (stays at root for backward compat)
└── tax/                        # 🆕 UNIFIED PACKAGE
    ├── __init__.py             # Public API (re-exports from tax_v14.py)
    ├── README.md               # This documentation
    ├── depreciation.py         # Enhanced depreciation methods (future)
    ├── validators.py           # Tax config validation (future)
    └── holidays.py             # Tax holiday support (future)
```

---

## Public API

### Tax Calculator

```python
from finance.tax import TaxCalculatorV14

# Initialize from config
tax_calc = TaxCalculatorV14(config={
    "tax": {
        "corporate_tax_rate": 0.30,
        "depreciation_method": "straight_line",
        "depreciation_years": 15
    }
})

# Calculate depreciation schedule
asset_value = 100_000_000  # $100M
operational_years = 20

depreciation = tax_calc.calculate_depreciation(
    asset_value=asset_value,
    operational_years=operational_years
)

# Result: [6,666,667, 6,666,667, ..., 6,666,667, 0, ..., 0]
# 15 years of depreciation, then 5 years of zero

print(f"Annual depreciation: ${depreciation[0]:,.0f}")
print(f"Total depreciated: ${sum(depreciation):,.0f}")
```

### Standalone Depreciation

```python
from finance.tax import calculate_depreciation_schedule

# Direct function call (no config needed)
schedule = calculate_depreciation_schedule(
    asset_value=100_000_000,
    method="straight_line",
    years=15,
    operational_years=20
)

print(f"Year 1 depreciation: ${schedule[0]:,.0f}")
print(f"Year 16 depreciation: ${schedule[15]:,.0f}")  # Should be 0
```

### Configuration Structure

```yaml
# In scenario YAML file
tax:
  corporate_tax_rate: 0.30  # 30% corporate tax
  depreciation_method: straight_line
  depreciation_years: 15
  
  # Future enhancements
  tax_holiday_years: 5  # First 5 years tax-free
  enhanced_capital_allowance: 1.5  # 150% first-year allowance
  loss_carryforward_years: 20  # Years to carry forward losses
```

---

## Tax Calculation Examples

### Basic Straight-Line Depreciation

```python
from finance.tax import TaxCalculatorV14

# Scenario: $100M asset, 15-year depreciation, 30% tax rate
config = {
    "tax": {
        "corporate_tax_rate": 0.30,
        "depreciation_method": "straight_line",
        "depreciation_years": 15
    }
}

tax_calc = TaxCalculatorV14(config)

# Annual EBITDA: $15M
ebitda = 15_000_000

# Year 1 calculations
depreciation_schedule = tax_calc.calculate_depreciation(
    asset_value=100_000_000,
    operational_years=20
)

ebit = ebitda - depreciation_schedule[0]
tax = ebit * tax_calc.corporate_rate
net_income = ebit - tax

print(f"EBITDA: ${ebitda:,.0f}")
print(f"Depreciation: ${depreciation_schedule[0]:,.0f}")
print(f"EBIT: ${ebit:,.0f}")
print(f"Tax (30%): ${tax:,.0f}")
print(f"Net Income: ${net_income:,.0f}")

# Output:
# EBITDA: $15,000,000
# Depreciation: $6,666,667
# EBIT: $8,333,333
# Tax (30%): $2,500,000
# Net Income: $5,833,333
```

### Integration with Cashflow

```python
from finance.tax import TaxCalculatorV14
from finance.cashflow_v14 import CashFlowEngine

# Initialize both
tax_calc = TaxCalculatorV14(config)
cashflow = CashFlowEngine(config)

# Generate depreciation once
depreciation_schedule = tax_calc.calculate_depreciation(
    asset_value=config["finance"]["capex_usd"],
    operational_years=20
)

# Use in annual cashflow loop
for year in range(20):
    ebitda = cashflow.calculate_ebitda(year)
    depreciation = depreciation_schedule[year]
    
    ebit = ebitda - depreciation
    tax = max(0, ebit * tax_calc.corporate_rate)  # No negative taxes
    
    cashflow.tax_paid[year] = tax
    cashflow.net_income[year] = ebit - tax
```

---

## Depreciation Methods

### Current: Straight-Line

**Formula:**
```
Annual Depreciation = Asset Value / Depreciation Years
```

**Example:**
- Asset Value: $100M
- Years: 15
- Annual: $6.67M for 15 years, then $0

### Future: Declining Balance

**Formula:**
```
Year N Depreciation = (Asset Value - Cumulative Depreciation) * Rate
Rate = 1 / Depreciation Years
```

**Example (not yet implemented):**
```python
# Future API
from finance.tax.depreciation import DecliningBalanceDepreciation

depreciator = DecliningBalanceDepreciation(
    asset_value=100_000_000,
    years=15,
    rate=0.10  # 10% annual
)

schedule = depreciator.calculate(operational_years=20)
```

### Future: Double Declining Balance

**Formula:**
```
Rate = 2 / Depreciation Years
Year N Depreciation = (Asset Value - Cumulative) * Rate
```

---

## Validation (Future Enhancement)

### Tax Config Validation

```python
# Future API
from finance.tax.validators import validate_tax_config

try:
    validate_tax_config({
        "corporate_tax_rate": 0.30,
        "depreciation_method": "straight_line",
        "depreciation_years": 15
    })
except ValueError as e:
    print(f"Invalid tax config: {e}")

# Validation checks:
# - corporate_tax_rate in [0, 1]
# - depreciation_method in supported methods
# - depreciation_years > 0
# - tax_holiday_years < operational_years
```

### Depreciation Input Validation

```python
# Future API
from finance.tax.validators import validate_depreciation_inputs

try:
    validate_depreciation_inputs(
        asset_value=100_000_000,
        years=15,
        operational_years=20
    )
except ValueError as e:
    print(f"Invalid inputs: {e}")

# Validation checks:
# - asset_value > 0
# - years > 0
# - operational_years >= years
# - method is supported
```

---

## Integration Points

### With Cashflow Module

```python
# In cashflow_v14.py
from finance.tax import TaxCalculatorV14

class CashFlowEngine:
    def __init__(self, config):
        self.tax_calc = TaxCalculatorV14(config)
        self.depreciation_schedule = self.tax_calc.calculate_depreciation(
            asset_value=config["finance"]["capex_usd"],
            operational_years=self.operational_years
        )
    
    def calculate_annual_tax(self, year, ebit):
        """Calculate tax with depreciation shield."""
        depreciation = self.depreciation_schedule[year]
        taxable_income = ebit - depreciation
        return max(0, taxable_income * self.tax_calc.corporate_rate)
```

### With Pipeline Module

```python
# In pipeline_v14.py
from finance.tax import TaxCalculatorV14

def run_v14_pipeline(config_path):
    config = load_scenario_config(config_path)
    
    # Initialize tax calculator
    tax_calc = TaxCalculatorV14(config)
    
    # Pass to cashflow engine
    cashflow = CashFlowEngine(config, tax_calculator=tax_calc)
    
    # Run pipeline...
```

---

## Testing

### Unit Tests

```python
import pytest
from finance.tax import (
    TaxCalculatorV14,
    calculate_depreciation_schedule,
)

def test_straight_line_depreciation():
    """Test basic straight-line depreciation."""
    schedule = calculate_depreciation_schedule(
        asset_value=100_000,
        method="straight_line",
        years=10,
        operational_years=15
    )
    
    assert len(schedule) == 15
    assert schedule[0] == 10_000  # Annual depreciation
    assert schedule[9] == 10_000  # Last depreciation year
    assert schedule[10] == 0  # Post-depreciation years
    assert sum(schedule) == 100_000  # Total equals asset value

def test_tax_calculator_initialization():
    """Test tax calculator config parsing."""
    config = {
        "tax": {
            "corporate_tax_rate": 0.25,
            "depreciation_years": 12
        }
    }
    
    calc = TaxCalculatorV14(config)
    assert calc.corporate_rate == 0.25
    assert calc.tax_config["depreciation_years"] == 12

def test_tax_calculator_defaults():
    """Test default values when config missing."""
    calc = TaxCalculatorV14({})
    assert calc.corporate_rate == 0.30  # Default 30%

def test_depreciation_edge_cases():
    """Test edge cases in depreciation calculation."""
    # Years equals operational years
    schedule1 = calculate_depreciation_schedule(100_000, "straight_line", 10, 10)
    assert len(schedule1) == 10
    assert schedule1[-1] == 10_000
    
    # Years exceeds operational years (should cap)
    schedule2 = calculate_depreciation_schedule(100_000, "straight_line", 15, 10)
    assert len(schedule2) == 10
    assert all(d == 10_000 for d in schedule2)  # No zero years
```

### Integration Tests

```python
def test_tax_cashflow_integration():
    """Test tax calculator integration with cashflow."""
    from finance.tax import TaxCalculatorV14
    from finance.cashflow_v14 import CashFlowEngine
    
    config = load_test_config()
    
    tax_calc = TaxCalculatorV14(config)
    cashflow = CashFlowEngine(config)
    
    # Verify depreciation used in cashflow
    assert hasattr(cashflow, "depreciation_schedule")
    assert len(cashflow.depreciation_schedule) == cashflow.operational_years
```

### Run Tests

```bash
# From repository root
pytest finance/tests/test_tax.py -v

# Test specific function
pytest finance/tests/test_tax.py::test_straight_line_depreciation -v

# With coverage
pytest finance/tests/test_tax.py --cov=finance.tax --cov-report=html
```

---

## Future Enhancements

### Sprint 17 Roadmap

#### 1. Enhanced Depreciation Methods (2h)

**Create** `finance/tax/depreciation.py`:
- `DecliningBalanceDepreciation` class
- `DoubleDecliningDepreciation` class
- `UnitOfProductionDepreciation` class
- `DepreciationFactory` for method selection

#### 2. Tax Validation (1h)

**Create** `finance/tax/validators.py`:
- `validate_tax_config()` - Comprehensive config validation
- `validate_depreciation_inputs()` - Input sanity checks
- `TaxConfigSchema` - Pydantic model for tax config

#### 3. Tax Holidays (2h)

**Create** `finance/tax/holidays.py`:
- `TaxHolidayCalculator` class
- Support for graduated tax rates
- Loss carryforward tracking

#### 4. Enhanced Capital Allowances (1h)

**Enhance** `tax_v14.py`:
- First-year allowance multipliers
- Accelerated depreciation for specific asset classes
- Investment tax credit support

#### 5. Comprehensive Testing (2h)

**Create** `finance/tests/test_tax_comprehensive.py`:
- Edge case coverage
- Integration tests with cashflow
- Scenario-based validation tests
- Performance benchmarks

**Total:** 8 hours (Sprint 17)

---

## Backward Compatibility

### All Old Imports Work

```python
# Old way (still works)
from finance.tax_v14 import TaxCalculatorV14
from finance.tax_v14 import calculate_depreciation_schedule

# New way (recommended)
from finance.tax import TaxCalculatorV14
from finance.tax import calculate_depreciation_schedule

# Both create identical objects
old_calc = TaxCalculatorV14(config)  # From tax_v14.py
new_calc = TaxCalculatorV14(config)  # From tax package

assert type(old_calc) == type(new_calc)  # Same class
```

### Migration Guide

No migration required! All existing code continues to work. However, new code should use the package import:

**Update your imports gradually:**

```python
# Step 1: Add new imports alongside old ones
from finance.tax_v14 import TaxCalculatorV14  # Old (still works)
from finance.tax import TaxCalculatorV14 as TaxCalc  # New

# Step 2: Test both work identically
assert TaxCalculatorV14 is TaxCalc

# Step 3: Remove old imports in next code review
from finance.tax import TaxCalculatorV14  # Only new
```

---

## Related Documentation

- [Sprint 16 Reorganization Complete](../../docs/SPRINT_16_REORGANIZATION_COMPLETE.md)
- [Cashflow Module](../cashflow_v14.py)
- [WACC Module](../wacc_v14.py)
- [Finance Package Overview](../README.md) (to be created)
- [GWTF Framework](../../docs/gwtf_framework.md)

---

## Changelog

### Sprint 16 Iteration 5 (December 21, 2025)

**Phase 1: Package Creation**
- ✅ Created `/finance/tax/` package
- ✅ Created `__init__.py` with re-exports
- ✅ Created comprehensive README (this document)
- ✅ Maintained 100% backward compatibility
- ✅ Zero breaking changes

**Identified for Sprint 17:**
- ⏸️ Enhanced depreciation methods
- ⏸️ Tax config validation
- ⏸️ Tax holiday support
- ⏸️ Comprehensive test suite
- ⏸️ Integration with cashflow module hardening

---

## Contributing

### Adding New Tax Features

1. **Add to** `tax_v14.py` (source of truth)
2. **Re-export from** `tax/__init__.py`
3. **Update** this README with usage examples
4. **Add tests** in `tests/test_tax.py`
5. **Update** `__all__` in both files

### Code Style

- Follow Google-style docstrings
- Type hints for all functions
- Comprehensive inline comments
- Error handling with clear messages
- GWTF/CESSPIT/CASPER/CCCDIR compliance

---

**Document Status:** ✅ Complete  
**Last Updated:** December 21, 2025, 7:38 AM +0530  
**Sprint:** 16 (Iteration 5)  
**Maintained By:** Sprint 16 Engineering Team
