# Debt Module Naming Conventions

**Sprint 18 - Issue #5: Debt Naming Clarity**

## Problem Statement

The `_m` suffix in debt module fields (e.g., `principal_m`, `idc_m`) is ambiguous:

- Does `_m` mean **millions** (scaling factor)?
- Does `_m` mean **currency** (e.g., meters, or some other unit)?
- Why do we have BOTH `principal` and `principal_m`?

### Current Implementation

From `finance/debt_v14.py` line 478-495:

```python
return {
    # ...
    "lkr": {
        "principal": principal_by.get("lkr", 0.0),
        "principal_m": principal_by.get("lkr", 0.0),  # ALIAS
        "idc": idc_by.get("lkr", 0.0),
        "idc_m": idc_by.get("lkr", 0.0),  # ALIAS
    },
    # ...
}
```

**Observation**: `principal` and `principal_m` are **identical values** (aliases), not different units.

---

## Clarification: What Does `_m` Mean?

### Official Definition

**`_m` = MILLIONS (USD)**

The `_m` suffix indicates the value is expressed in **millions of USD**, not a different currency or unit.

### Examples

| Field | Value | Interpretation |
|-------|-------|----------------|
| `principal_m` | `50.0` | $50 million USD |
| `idc_m` | `5.2` | $5.2 million USD (capitalized interest) |
| `total_idc_m` | `12.8` | $12.8 million USD (total IDC across tranches) |
| `debt_total` | `100.0` | $100 million USD (no suffix, implicit millions) |

### Why Both `principal` AND `principal_m`?

**Backward Compatibility**

The debt module historically used inconsistent naming:
- Some callers expected `principal` (no suffix)
- Some callers expected `principal_m` (explicit millions)

To avoid breaking changes, v14 provides BOTH as aliases pointing to the same value.

```python
# These are IDENTICAL
assert debt_result["lkr"]["principal"] == debt_result["lkr"]["principal_m"]
assert debt_result["usd"]["idc"] == debt_result["usd"]["idc_m"]
```

---

## Default Units in v14

### Debt Module Convention

All debt-related values in `finance/debt_v14.py` are in **USD millions** unless explicitly noted otherwise.

| Field | Units | Notes |
|-------|-------|-------|
| `principal`, `principal_m` | USD millions | Post-IDC capitalized principal |
| `idc`, `idc_m` | USD millions | Interest During Construction |
| `total_idc`, `total_idc_m` | USD millions | Aggregate IDC across tranches |
| `debt_total` | USD millions | Total debt before IDC |
| `max_debt_usd` | USD millions | Maximum debt capacity |
| `debt_outstanding` | USD millions | Time-series of outstanding debt |
| `debt_service_total` | USD millions | Time-series of annual debt service |

### Why USD?

Project finance models at DutchBay use USD as the **base currency** for:
- International lender reporting (World Bank, ADB, IFC)
- Cross-border debt tranches (USD commercial, DFI loans)
- CAPEX benchmarking (global EPC costs)

Local currency (LKR) appears in:
- Revenue streams (PPA tariffs in LKR)
- Operating expenses (LKR-denominated OPEX)
- Tax calculations (LKR tax base)

---

## Naming Convention Standards

### Suffix Semantics

| Suffix | Meaning | Example |
|--------|---------|----------|
| `_m` | Millions (USD) | `principal_m = 50.0` → $50M |
| `_usd` | USD currency (any scale) | `capex_usd = 100.0` → $100M |
| `_lkr` | LKR currency (millions) | `revenue_lkr = 15000.0` → LKR 15B |
| `_pct` | Percentage (0-100) | `debt_ratio_pct = 70.0` → 70% |
| `_bps` | Basis points | `spread_bps = 250` → 2.50% |
| (none) | Context-dependent | `debt_total` → USD millions (by convention) |

### Preferred Naming (Future v15)

For v15 refactoring, consider explicit currency suffixes:

```python
# CURRENT (v14)
"principal_m": 50.0  # Ambiguous: millions of what?

# PROPOSED (v15)
"principal_usd_m": 50.0  # Clear: millions of USD
"principal_lkr_m": 7500.0  # Clear: millions of LKR
```

This avoids ambiguity when handling multi-currency debt tranches.

---

## Usage Examples

### Example 1: Accessing Debt Results

```python
from finance.debt_v14 import plan_debt

debt_result = plan_debt(annual_rows=rows, config=config)

# Both are valid (aliases)
print(f"LKR Principal: ${debt_result['lkr']['principal']:.1f}M")
print(f"LKR Principal: ${debt_result['lkr']['principal_m']:.1f}M")

# Output:
# LKR Principal: $35.0M
# LKR Principal: $35.0M
```

### Example 2: Lender Report Formatting

```python
def format_debt_summary(debt_result: Dict[str, Any]) -> str:
    """Format debt summary for lender reports."""
    
    # Extract principal values (use _m for clarity)
    lkr_principal = debt_result["lkr"]["principal_m"]
    usd_principal = debt_result["usd"]["principal_m"]
    dfi_principal = debt_result["dfi"]["principal_m"]
    
    total = lkr_principal + usd_principal + dfi_principal
    
    return f"""
    Debt Structure (USD Millions)
    ==============================
    LKR Tranche:  ${lkr_principal:>8.1f}M
    USD Tranche:  ${usd_principal:>8.1f}M
    DFI Tranche:  ${dfi_principal:>8.1f}M
    ─────────────────────────────
    Total Debt:   ${total:>8.1f}M
    """
```

### Example 3: Converting to Absolute USD

```python
def convert_to_absolute_usd(debt_m: float) -> float:
    """Convert debt from millions to absolute USD.
    
    Args:
        debt_m: Debt in USD millions (e.g., 50.0 = $50M)
    
    Returns:
        Absolute USD value (e.g., 50_000_000.0)
    """
    return debt_m * 1_000_000

# Example
principal_m = 50.0  # $50M
principal_abs = convert_to_absolute_usd(principal_m)
print(f"{principal_abs:,.0f}")  # Output: 50,000,000
```

---

## Testing Guidance

### Test Case 1: Verify Alias Equivalence

```python
def test_principal_aliases_are_equal():
    """Both principal and principal_m must return same value."""
    debt_result = plan_debt(annual_rows=rows, config=config)
    
    for tranche in ["lkr", "usd", "dfi"]:
        principal = debt_result[tranche]["principal"]
        principal_m = debt_result[tranche]["principal_m"]
        
        assert principal == principal_m, (
            f"{tranche}: principal != principal_m"
        )
```

### Test Case 2: Units Validation

```python
def test_debt_values_in_millions():
    """Debt values should be in reasonable millions range."""
    debt_result = plan_debt(annual_rows=rows, config=config)
    
    total_debt = debt_result["debt_total"]
    
    # For typical 100MW wind farm: $100-200M
    assert 50.0 <= total_debt <= 500.0, (
        f"Debt {total_debt:.1f}M outside expected range"
    )
```

---

## Migration Path (v14 → v15)

### Phase 1: Deprecation Warnings (v14.5)

Add deprecation warnings when `principal_m` is accessed:

```python
import warnings

class DebtResultWithDeprecations(dict):
    def __getitem__(self, key):
        if key.endswith("_m"):
            warnings.warn(
                f"'{key}' suffix deprecated. Use explicit currency suffix.",
                DeprecationWarning,
                stacklevel=2
            )
        return super().__getitem__(key)
```

### Phase 2: New Fields (v15.0)

Introduce explicit currency suffixes:

```python
# v15 debt result structure
return {
    "lkr": {
        "principal_usd_m": 35.0,  # NEW: explicit currency
        "principal_m": 35.0,      # DEPRECATED: kept for compat
        "principal": 35.0,        # DEPRECATED: kept for compat
    },
}
```

### Phase 3: Removal (v16.0)

Remove deprecated aliases:

```python
# v16 debt result structure (breaking change)
return {
    "lkr": {
        "principal_usd_m": 35.0,  # ONLY explicit form
        # "principal_m" removed
        # "principal" removed
    },
}
```

---

## Quick Reference Card

### Debt Module Units Cheat Sheet

```
┌─────────────────────────────────────────────────┐
│          DEBT MODULE UNITS (v14)                │
├─────────────────────────────────────────────────┤
│ Field              Units        Example         │
├─────────────────────────────────────────────────┤
│ principal_m        USD millions  50.0 = $50M    │
│ idc_m              USD millions  5.2 = $5.2M    │
│ debt_total         USD millions  100.0 = $100M  │
│ dscr_min           Ratio         1.30 = 1.30x   │
│ tenor_years        Years         15 = 15 years  │
│ interest_rate      Decimal       0.08 = 8%      │
├─────────────────────────────────────────────────┤
│ REMEMBER: All debt in USD MILLIONS by default   │
└─────────────────────────────────────────────────┘
```

---

## Frequently Asked Questions

### Q1: Why not use `_usd_m` suffix everywhere?

**A**: Backward compatibility. Existing tests and reports expect `principal_m`. We provide aliases to avoid breaking changes. Future versions (v15+) will use explicit `_usd_m`.

### Q2: Are LKR tranches also in USD millions?

**A**: Yes! The "LKR tranche" refers to the debt SOURCE (Sri Lankan banks), but the AMOUNT is still denominated in USD millions for consistency. Actual LKR conversion happens at the FX rate level.

### Q3: What if I need absolute USD (not millions)?

**A**: Multiply by 1,000,000:

```python
principal_absolute = debt_result["lkr"]["principal_m"] * 1e6
```

### Q4: How do I know if a field is in millions?

**A**: If the field name contains `_m` or is documented as "USD millions" in docstrings, it's in millions. When in doubt, check the test assertions for expected ranges.

---

## Summary

✅ **`_m` = MILLIONS (USD)**, not currency  
✅ **`principal` and `principal_m` are ALIASES** (same value)  
✅ **All debt values default to USD millions** unless noted  
✅ **Future v15 will use explicit `_usd_m` suffix** for clarity  
✅ **Migration path preserves backward compatibility**  

---

## References

- `finance/debt_v14.py` - Debt planning module
- `tests/api/test_debt_construction_idc_regression_v14.py` - Test fixtures
- Sprint 18 Issue #5: Debt naming clarity
- CASPER Framework: Contract-explicit naming
- CCCDIR: Comprehensive documentation standards

---

## Version History

| Version | Date       | Changes |
|---------|------------|--------|
| 1.0     | 2025-12-23 | Initial naming conventions doc (Sprint 18, Issue #5) |

---

**END OF NAMING CONVENTIONS**
