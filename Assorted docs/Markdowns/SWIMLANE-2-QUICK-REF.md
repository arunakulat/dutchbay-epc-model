# Swimlane 2 Quick Reference
## DutchBay EPC Model - Implementation Cheat Sheet

**Version:** 1.0.0
**Date:** 2025-12-11
**Companion to:** SWIMLANE-2-BOOTSTRAP-v1.0.md

---

## 🎯 What is Swimlane 2?

**Risk & Sensitivity Analytics Layer** — Lender-grade tornado analysis, FX validation, and unified capital risk API.

**Timeline:** 4 weeks (3 phases)
**Complexity:** Medium (refactoring required)
**Dependencies:** Evaluation_v14 (complete), Swimlane 1 (optional for Phase 3)

---

## 🏗️ Three Phases at a Glance

### Phase 1: FX Foundation (Week 1) ⚡ LOW RISK
**Goal:** Harden FX validation and curve generation

**Deliverables:**
- `finance/fx_v14.py` with `build_fx_curve()`
- `validation/schema_guard.py` with `_validate_fx_block()`
- `tests/finance/test_fx_v14.py` (15+ tests, 100% coverage)

**Why First:** FX feeds everything — must be rock solid before sensitivity

---

### Phase 2: Sensitivity Rebuild (Week 2-3) ⚠️ MEDIUM RISK
**Goal:** Make sensitivity_v14 a pure client of evaluation_v14 (GWTF compliance)

**Deliverables:**
- Refactored `analytics/sensitivity_v14.py` (zero finance imports)
- `contracts_v14.ShockSpec` and `ShockResult` dataclasses
- Standard shock library (CAPEX, OPEX, CF, FX, etc.)
- Import lint test (`test_sensitivity_imports.py`)

**Critical:** Remove all `from finance.*` imports, use `evaluate_with_overrides()` only

---

### Phase 3: Capital Risk Layer (Week 4) ⚡ LOW RISK
**Goal:** Unified API for all capital/risk analytics

**Deliverables:**
- `analytics/capital_risk_layer_v14.py`
- `contracts_v14.CapitalRiskBundle` dataclass
- Export functions (Excel, JSON, CSV)
- `tests/analytics_layer/test_capital_risk_layer.py`

**Why Last:** Needs Phase 2 complete, optionally integrates Swimlane 1 (WACC/Equity/Optimization)

---

## 🔒 Governance Rules (CCCDIR + CESSPIT + CASPER + GWTF)

### GWTF (Gateway Pattern)
```python
# ✅ CORRECT
from analytics.evaluation_v14 import evaluate_with_overrides
kpis = evaluate_with_overrides(config_path, overrides)

# ❌ FORBIDDEN
from finance.cashflow_v14 import build_cashflow
cf = build_cashflow(config)  # Bypasses gateway
```

### CCCDIR (Contract-Driven)
All public APIs use typed dataclasses from `contracts_v14.py`
- No `dict[str, Any]` in signatures
- Mypy `--strict` must pass

### CESSPIT (Schema Safety)
All configs validated via `validate_config_for_v14(validation_mode="strict")`
- Fail-fast on invalid configs
- Clear error messages

### CASPER (Lender Rigor)
All risk outputs include:
- Tail risk (VaR, CVaR, breach prob)
- Tornado sensitivity with MC enrichment
- Traceable metadata

---

## 📋 Acceptance Criteria Checklist

### Phase 1 Complete When:
- [ ] 100% test coverage on `fx_v14.py`
- [ ] CESSPIT validation integrated
- [ ] All existing scenarios still pass
- [ ] `mypy --strict` clean

### Phase 2 Complete When:
- [ ] Zero direct finance imports (lint test passes)
- [ ] 80%+ test coverage
- [ ] Tornado outputs match previous format
- [ ] Standard shock library has 8+ shocks

### Phase 3 Complete When:
- [ ] Bundle API works end-to-end
- [ ] Excel/JSON/CSV exports validated
- [ ] Integration with Swimlane 1 tested (if available)
- [ ] Demo to stakeholders complete

---

## 🚀 Quick Start

### For Engineers Starting Phase 1:
```bash
# 1. Create feature branch
git checkout -b feature/swimlane2-phase1-fx

# 2. Create files
touch finance/fx_v14.py
touch tests/finance/test_fx_v14.py

# 3. Copy code from SWIMLANE-2-BOOTSTRAP-v1.0.md Section 3.2

# 4. Run tests
pytest tests/finance/test_fx_v14.py -v --cov=finance.fx_v14

# 5. Check compliance
mypy --strict finance/fx_v14.py
ruff check finance/fx_v14.py
black finance/fx_v14.py
```

### For Engineers Starting Phase 2:
```bash
# 1. Create feature branch
git checkout -b feature/swimlane2-phase2-sensitivity

# 2. Backup current sensitivity
cp analytics/sensitivity_v14.py analytics/sensitivity_v14_old.py

# 3. Refactor per SWIMLANE-2-BOOTSTRAP-v1.0.md Section 4.2

# 4. Run import lint
pytest tests/lint/test_sensitivity_imports.py -v

# 5. Validate outputs match
pytest tests/analytics_layer/test_sensitivity_v14.py -v
```

### For Engineers Starting Phase 3:
```bash
# 1. Ensure Phase 2 complete
pytest tests/analytics_layer/test_sensitivity_v14.py -v

# 2. Create feature branch
git checkout -b feature/swimlane2-phase3-capital-risk

# 3. Create files
touch analytics/capital_risk_layer_v14.py
touch tests/analytics_layer/test_capital_risk_layer.py

# 4. Implement per SWIMLANE-2-BOOTSTRAP-v1.0.md Section 5.2

# 5. Test exports
pytest tests/analytics_layer/test_capital_risk_layer.py -v
```

---

## 📦 New Contracts (contracts_v14.py)

### Phase 2 Contracts:
```python
@dataclass
class ShockSpec:
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    label: str | None = None

@dataclass
class ShockResult:
    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str
```

### Phase 3 Contract:
```python
@dataclass
class CapitalRiskBundle:
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

---

## 🧪 Test Strategy

### Coverage Targets:
- **fx_v14.py:** 100% (P0)
- **sensitivity_v14.py:** 80%+ (P0)
- **capital_risk_layer_v14.py:** 80%+ (P1)

### Test Categories:
1. **Unit:** Individual function behavior
2. **Integration:** Module interactions via gateway
3. **Lint:** Import validation (GWTF)
4. **Regression:** Backward compatibility

### Running Tests:
```bash
# Phase-specific
pytest tests/finance/test_fx_v14.py -v
pytest tests/analytics_layer/test_sensitivity_v14.py -v
pytest tests/analytics_layer/test_capital_risk_layer.py -v

# Lint tests (GWTF enforcement)
pytest tests/lint/test_sensitivity_imports.py -v

# Full suite
pytest tests/ -v --cov=analytics --cov=finance

# Type checking
mypy --strict analytics/ finance/
```

---

## 🔗 Integration Points

### With Existing Code:
- **evaluation_v14:** Single gateway for all evaluation (no changes needed)
- **monte_carlo_v14:** Already integrated, provides tail risk (no changes)
- **contracts_v14:** Add new contracts (Phase 2 & 3)
- **schema_guard:** Add FX validation (Phase 1)

### With Swimlane 1 (Optional):
- **wacc_v14:** Extract `WaccResult` for bundle
- **equity_v14:** Extract `EquityResult` for bundle
- **optimization_v14:** Use in `build_capital_risk_bundle()` if available

---

## ⚠️ Common Pitfalls

### Phase 1:
❌ **Forgetting to handle both scalar and structured FX modes**
✅ Test both `lkr_per_usd` (scalar) and `base_rate+escalation_pct` (structured)

### Phase 2:
❌ **Importing finance modules directly**
✅ Always use `evaluate_with_overrides()` from evaluation_v14

❌ **Not using typed contracts**
✅ All shocks use `ShockSpec`, all results use `ShockResult`

### Phase 3:
❌ **Assuming Swimlane 1 is complete**
✅ Make WACC/equity/optimization optional (`| None` types)

❌ **Not testing all export formats**
✅ Test Excel, JSON, and CSV exports

---

## 📞 Getting Help

**For GWTF questions:** Check `evaluation_v14.py` docstrings
**For contract questions:** Check `contracts_v14.py` dataclass definitions
**For test patterns:** Check existing `test_monte_carlo_v14.py`
**For validation:** Check `schema_guard.py` existing validators

**Full documentation:** SWIMLANE-2-BOOTSTRAP-v1.0.md (this is the source of truth)

---

## 🎓 Key Concepts

### GWTF Gateway Pattern:
Analytics never talk to finance directly — always through `evaluation_v14.py`

### Override Dictionary Pattern:
```python
# To override project.capacity_factor to 0.42:
overrides = {'project': {'capacity_factor': 0.42}}
kpis = evaluate_with_overrides(config_path, overrides)
```

### Standard Shock Library:
Lender-grade shocks: CAPEX±10%, OPEX±10%, CF±5%, FX±10%, etc.

### Capital Risk Bundle:
ONE API for all risk analytics — baseline + sensitivity + MC + WACC + equity + optimization

---

## ✅ Definition of Done

### Phase 1:
- FX validation works for scalar and structured modes
- 100% test coverage
- All scenarios pass
- CESSPIT integrated

### Phase 2:
- Zero direct finance imports
- Import lint test passes
- Standard shock library documented
- Tornado outputs match previous

### Phase 3:
- Bundle API demonstrated
- All export formats validated
- Integration with Swimlane 1 tested
- DFI template created

### Sprint Complete:
- All 3 phases merged
- 335+ tests passing
- Coverage report ≥80%
- CHANGELOG.md updated
- Demo to stakeholders

---

**END OF QUICK REFERENCE**

*For detailed specifications, see SWIMLANE-2-BOOTSTRAP-v1.0.md*
