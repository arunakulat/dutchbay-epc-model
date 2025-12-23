# FX Integration Flag Tracking Guidelines

**Sprint 18 - Issue #2: Truthful FX Activity Tracking**

## Problem Statement

The current codebase may set FX integration flags based on configuration presence rather than actual usage. This creates misleading boolean indicators that suggest FX features were applied when they weren't, undermining audit trails and lender confidence.

### Anti-Pattern Example

```python
# BAD: Flag set from config presence, not actual usage
fx_cfg = config.get("fx", {})
flags = {
    "fx_structured_applied": bool(fx_cfg),  # True even if empty dict!
    "fx_curve_applied": True,  # Hardcoded, no actual check
}
```

### Consequence

- Lender reports show "FX hedging enabled" when no hedging occurred
- Debug logs mislead developers investigating FX issues  
- Covenant monitoring flags false positives for FX exposure
- Audit trails become unreliable

---

## Solution: Truthful Flag Tracking

### Core Principles

1. **Evidence-Based**: Flags must reflect ACTUAL actions, not config presence
2. **Explicit Checks**: Use presence validation (`is not None`, `len > 0`)
3. **Separate Concerns**: Track structured blocks vs curve application independently
4. **Document Semantics**: Clear docstrings explain what each flag means

### Flag Definitions

| Flag | Meaning | Set to `True` When |
|------|---------|-------------------|
| `fx_structured_applied` | FX structured block was loaded and used | `FXStructuredBlock` object is not None AND has non-default values |
| `fx_curve_applied` | FX rate curve was applied to cashflows | FX curve rates were actually used in revenue/debt conversions |
| `fx_hedging_enabled` | FX hedging coverage was applied | `hedging_coverage_pct > 0` in structured block |
| `fx_natural_hedge_detected` | Natural hedge was computed | `fx_match_ratio > 0.8` (>80% match) |

---

## Implementation Patterns

### Pattern 1: Structured Block Validation

```python
def check_fx_structured_applied(fx_block: Optional[FXStructuredBlock]) -> bool:
    """Check if FX structured block was actually applied.
    
    Returns True only if:
    - FX block exists (not None)
    - Has meaningful configuration (non-default strategy or volumetry)
    
    Returns False if:
    - FX block is None
    - FX block has all default values (strategy='blended', no volumetry)
    """
    if fx_block is None:
        return False
    
    # Check for non-default configuration
    has_volumetry = len(fx_block.volumetry) > 0
    has_tranches = len(fx_block.debt_tranches) > 0
    has_hedging = fx_block.hedging_coverage_pct > 0.0
    
    # At least ONE meaningful config must be present
    return has_volumetry or has_tranches or has_hedging
```

### Pattern 2: Curve Application Validation

```python
def check_fx_curve_applied(
    fx_curve: Optional[FXCurveOutput],
    annual_rows: List[Dict[str, Any]]
) -> bool:
    """Check if FX curve rates were actually applied to cashflows.
    
    Returns True only if:
    - FX curve exists (not None)
    - FX rates from curve were used in at least one cashflow row
    
    Returns False if:
    - FX curve is None
    - Cashflows use flat/default FX rates (no curve application)
    """
    if fx_curve is None:
        return False
    
    if not annual_rows:
        return False
    
    # Check if any row has fx_rate matching curve rates
    curve_rates_set = set(fx_curve.lkr_usd)
    for row in annual_rows:
        fx_rate = row.get("fx_rate")
        if fx_rate is not None and fx_rate in curve_rates_set:
            return True  # Found evidence of curve application
    
    return False  # No evidence found
```

### Pattern 3: Hedging Coverage Validation

```python
def check_fx_hedging_enabled(fx_block: Optional[FXStructuredBlock]) -> bool:
    """Check if FX hedging was actually configured.
    
    Returns True only if hedging coverage percentage > 0.
    """
    if fx_block is None:
        return False
    
    return fx_block.hedging_coverage_pct > 0.0
```

---

## Integration Points

### 1. Cashflow Construction

When building `CashflowResult`, compute flags from actual objects:

```python
from analytics.contracts_v14 import CashflowResult
from analytics.fx.fx_contracts import FXStructuredBlock, FXCurveOutput

def build_cashflow(
    config: Dict[str, Any],
    fx_block: Optional[FXStructuredBlock],
    fx_curve: Optional[FXCurveOutput],
    annual_rows: List[Dict[str, Any]],
) -> CashflowResult:
    """Build cashflow with truthful FX flags."""
    
    # Compute flags from actual usage
    flags = {
        "fx_structured_applied": check_fx_structured_applied(fx_block),
        "fx_curve_applied": check_fx_curve_applied(fx_curve, annual_rows),
        "fx_hedging_enabled": check_fx_hedging_enabled(fx_block),
    }
    
    return CashflowResult(
        years=[...],
        annual_rows=annual_rows,
        # ... other fields ...
        flags=flags,
    )
```

### 2. Scenario Result Integration

Propagate flags to `ScenarioResult` for export:

```python
from analytics.contracts_v14 import ScenarioResult

def build_scenario_result(
    cashflow: CashflowResult,
    fx_block: Optional[FXStructuredBlock],
    fx_curve: Optional[FXCurveOutput],
) -> ScenarioResult:
    """Build scenario result with FX integration metadata."""
    
    return ScenarioResult(
        scenario_name="base_case",
        # ... other fields ...
        fx_block=fx_block,  # Store actual object, not just flag
        fx_curve=fx_curve,  # Store actual object
        cashflow=cashflow,  # Contains truthful flags
    )
```

---

## Testing Strategy

### Test Case 1: No FX Configuration

```python
def test_no_fx_config_sets_false_flags():
    """Flags should be False when FX not configured."""
    config = {"finance": {"capex_usd": 100.0}}  # No 'fx' key
    
    cashflow = build_cashflow(
        config=config,
        fx_block=None,
        fx_curve=None,
        annual_rows=[],
    )
    
    assert cashflow.flags["fx_structured_applied"] is False
    assert cashflow.flags["fx_curve_applied"] is False
    assert cashflow.flags["fx_hedging_enabled"] is False
```

### Test Case 2: FX Configured But Not Used

```python
def test_fx_configured_but_not_used():
    """Flags should be False when FX configured but not applied."""
    config = {
        "fx": {
            "strategy": "blended",
            "base_currency": "USD",
            # No volumetry, no hedging
        }
    }
    
    fx_block = load_fx_structured_block(config)
    
    cashflow = build_cashflow(
        config=config,
        fx_block=fx_block,
        fx_curve=None,  # No curve applied
        annual_rows=[{"fx_rate": 300.0}],  # Flat rate, not from curve
    )
    
    # Block exists but has no meaningful config
    assert cashflow.flags["fx_structured_applied"] is False
    # No curve applied
    assert cashflow.flags["fx_curve_applied"] is False
```

### Test Case 3: FX Fully Applied

```python
def test_fx_fully_applied():
    """Flags should be True when FX actually used."""
    config = {
        "fx": {
            "strategy": "natural_hedge",
            "hedging_coverage_pct": 75.0,
            "volumetry": [
                {"period": 1, "total_debt_usd": 50.0, "revenue_lkr": 100.0}
            ],
        }
    }
    
    fx_block = load_fx_structured_block(config)
    fx_curve = FXCurveOutput(
        years=[1, 2, 3],
        lkr_usd=[310.0, 315.0, 320.0],
        source="scenario_config",
    )
    
    annual_rows = [
        {"year": 1, "fx_rate": 310.0},  # Matches curve
        {"year": 2, "fx_rate": 315.0},
        {"year": 3, "fx_rate": 320.0},
    ]
    
    cashflow = build_cashflow(
        config=config,
        fx_block=fx_block,
        fx_curve=fx_curve,
        annual_rows=annual_rows,
    )
    
    assert cashflow.flags["fx_structured_applied"] is True  # Has volumetry
    assert cashflow.flags["fx_curve_applied"] is True  # Rates match curve
    assert cashflow.flags["fx_hedging_enabled"] is True  # Coverage > 0
```

---

## Migration Checklist

To implement truthful FX flag tracking:

- [ ] Create helper functions: `check_fx_structured_applied()`, `check_fx_curve_applied()`, `check_fx_hedging_enabled()`
- [ ] Update cashflow construction to use helpers instead of hardcoded flags
- [ ] Add integration tests for all three test cases above
- [ ] Update `CashflowResult` docstring to document flag semantics
- [ ] Add flag validation to scenario export logic
- [ ] Update lender report templates to use flags correctly

---

## Benefits

### For Developers
- Clear debugging signals when FX issues occur
- Self-documenting code (flags match reality)
- Easier to validate FX integration in tests

### For Lenders
- Accurate FX exposure reporting
- Reliable audit trails for covenant monitoring
- Clear visibility into hedging strategies

### For Compliance
- ✅ CASPER: Contract-explicit flag semantics
- ✅ CESSPIT: Evidence-based tracking (not config-based)
- ✅ GWTF: Single source of truth for FX status
- ✅ CCCDIR: Comprehensive documentation

---

## References

- Sprint 15: FX Integration v14R6 (structured blocks)
- Sprint 18: Pipeline Integrity Fixes (this issue)
- CESSPIT Framework: Evidence-based validation
- Dolphin Strategy: Surgical fixes, zero regression

---

## Version History

| Version | Date       | Changes |
|---------|------------|--------|
| 1.0     | 2025-12-23 | Initial guidelines (Sprint 18, Issue #2) |

---

## Authors

DutchBay v14 Team
Sprint 18: Pipeline Integrity Fixes

---

**END OF GUIDELINES**
