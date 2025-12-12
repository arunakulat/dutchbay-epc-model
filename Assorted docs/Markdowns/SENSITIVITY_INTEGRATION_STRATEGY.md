# 🏛️ COMPREHENSIVE SENSITIVITY MODULE INTEGRATION STRATEGY
## DutchBay EPC Model - Sprint 9 Architecture & Implementation Roadmap

**Date:** December 8, 2025
**Author:** FinTech/CFA Analysis Layer
**Status:** Strategic Discussion & Roadmap

---

## 📋 EXECUTIVE SUMMARY

The sensitivity module represents a **critical bridge** between:
- **Monte Carlo stochastic analysis** (probability distributions, tail risks)
- **Deterministic tornado analysis** (parameter importance ranking)
- **Project finance KPI surface** (IRR, NPV, DSCR, covenants)

**Key Finding:** The codebase follows a **layered architecture** that supports both:
1. **Parallel deterministic analysis** (sensitivity_v14.py) for lender decks
2. **Stochastic risk analysis** (monte_carlo_v14.py) for probability-weighted outcomes
3. **Scenario orchestration** (scenario_analytics.py) for batch optimization

This analysis establishes **best practices** from fintech, renewable energy project finance, and statistical risk analysis literature to integrate these systems optimally.

---

## 🏗️ PART 1: HOLISTIC CODEBASE ARCHITECTURE

### 1.1 Current Layer Stack (Bottom-Up)

```
┌─────────────────────────────────────────────────────────┐
│  CLI & Dashboards                                       │
│  (streamlit_app.py, run_scenario_analytics_v14.py)     │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│  Batch Orchestrators                                    │
│  (scenario_analytics.py, sensitivity_v14.py)           │
│  - Discover & parallelize scenarios                     │
│  - Apply schema guards (R5 compliance)                  │
│  - Aggregate results to DataFrames                      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│  Stochastic & Deterministic Engines                     │
│  (monte_carlo_v14.py, sensitivity_v14.py)              │
│  - Monte Carlo: parameter distributions + sampling      │
│  - Tornado: one-way parameter sweeps                    │
│  - Both feed into run_v14_pipeline()                    │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│  Canonical Finance Engine (V14 Pipeline)                │
│  (pipeline_v14.py, metrics.py)                          │
│  - build_annual_rows (cashflow engine)                  │
│  - apply_debt_layer / plan_debt (covenant tracking)     │
│  - calculate_scenario_kpis (single source of truth)     │
│  - WACC/discount rate resolution                        │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│  Finance Modules (Immutable)                            │
│  (cashflow_v14.py, debt_v14.py, wacc_v14.py)           │
│  - Domain logic (no sensitivity knowledge)              │
│  - DSCR covenants, balloon schedules, FX               │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│  Config & Contracts Layer                               │
│  (contracts_v14.py, config_schema.py, schema_guard.py) │
│  - Data validation & type safety (Pydantic v2)          │
│  - FX mapping, scenario validation (R5 compliance)      │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Where Sensitivity Module Fits

**Current Status:** ✅ **WELL-INTEGRATED** (no major rework needed)

The **sensitivity_v14.py** module sits cleanly at **Layer 3**, above the pipeline:
- Does NOT touch finance internals (cashflow, debt)
- Works ONLY through `run_v14_pipeline()` → `calculate_scenario_kpis()`
- Enables: tornado, breakeven, multi-metric analysis
- Complies with Go With The Flow (no duplication, single source of truth)

**Monte Carlo Integration:** ✅ **COMPATIBLE**
- monte_carlo_v14.py also uses `evaluate_with_overrides()` (which calls `run_v14_pipeline()` internally)
- Both stochastic and deterministic paths converge on same KPI surface
- **Common Random Numbers (CRN)**: Supported (Monte Carlo generates unit hypercube; scenarios sample from same distribution space)

---

## 🎓 PART 2: BEST PRACTICES FROM FINTECH & PROJECT FINANCE

### 2.1 Sensitivity Analysis in Renewable Energy Project Finance

**Academic & Industry Standards:**

| Standard | Application | DutchBay Status |
|----------|-------------|-----------------|
| **IRENA Risk Assessment Guidelines** | Use tornado for 5-10 key drivers | ✅ Implemented |
| **IFC Environmental & Social Framework** | Stress-test debt covenants under downside scenarios | ✅ Via DSCR tracking |
| **NREL Solar PV Proforma Handbook** | Multi-metric sensitivity (IRR, NPV, DSCR) | ✅ In sensitivity_v14.py |
| **US Energy Info Admin. – Cost Uncertainty** | Use triangular/normal distributions for key parameters | ✅ Monte Carlo support |
| **Moody's/S&P Project Finance Criteria** | Covenant breach probability, rating impact | ⚠️ Partial (post-hoc analysis available) |

**Key Insight from Literature:**
1. **Tornado charts** are **lender-facing** (communicate key drivers quickly)
2. **Monte Carlo** is **risk management** (probability of covenant breach, tail VaR)
3. **Breakeven analysis** is **strategic** (identify minimum tariff, maximum capex)
4. **Correlation structures** matter for:
   - Capex & debt tenor (both increase project cost)
   - Tariff & offtake volume (both affect revenue)
   - Exchange rate & debt repayment (LKR/USD exposure)

### 2.2 FinTech Best Practices: Parallel Analysis Workflows

**Pattern:** Modern fintech platforms (Blackrock Aladdin, Bloomberg, Risk Integrated) use **complementary engines**:

```
Input Config
    ↙              ↘
Deterministic     Stochastic
Tornado           Monte Carlo
    ↓                ↓
Single Metrics    Distributions
    ↓                ↓
Driver Ranking    Tail Risk (VaR, CVaR)
    ↓                ↓
────────────────────────────────────────
        Risk Dashboard
   (Integrated View)
```

**DutchBay Alignment:**
- ✅ We have both deterministic (tornado) and stochastic (Monte Carlo)
- ✅ Pipeline unifies both (single `run_v14_pipeline` call)
- ⚠️ Missing: tail risk quantification & correlation modeling

### 2.3 Statistical Best Practices

**From Taleb, Hull, Jorion:**
1. **Use LHS (Latin Hypercube Sampling) over random** ✅ Implemented
2. **Test for parameter dependencies** → Need correlation matrix
3. **Report percentiles, not just mean/std** ✅ Done (P10, P50, P90)
4. **Validate against historical data** → External validation step needed
5. **Document assumption sensitivity** → Needs sensitivity_assumptions.md

---

## 📊 PART 3: DETAILED FILE-BY-FILE ANALYSIS

### Core Files Requiring Integration (14 Total)

#### **TIER 1: Critical Refactoring Needed** (3 files)

| File | Issues | Severity | Fix |
|------|--------|----------|-----|
| **sensitivity_v14.py** (36KB) | Type hints (Dict→dict), Pydantic v2, docstring gaps | 🟡 MEDIUM | 20 min, add modern type hints |
| **sensitivity_heatmap.py** | Missing closing parens (2×), type hint style | 🔴 CRITICAL | 5 min, syntax fix + import cleanup |
| **parameter_solvers.py** | Type hints, potential circular imports | 🟡 MEDIUM | 15 min, refactor solver interface |

#### **TIER 2: Minor Polish** (6 files)

| File | Issues | Fix |
|------|--------|-----|
| **metrics.py** | Dict→dict, validate CFADS edge cases | Import `dict` types, add assertions |
| **scenario_analytics.py** | Discount rate precedence logic (correct but verbose) | Add docstring clarifying FIN-02 |
| **pipeline_v14.py** | WACC contract building has defensive checks | Already solid, minimal changes |
| **evaluate_scenario.py** | Thin wrapper, well-documented | Add parameter validation |
| **kpi_normalizer.py** | Type hints, export format handling | Standard polish |
| **scenario_loader.py** | YAML/JSON loading, FX validation | Already compliant, minimal changes |

#### **TIER 3: Supporting Infrastructure** (5 files)

| File | Purpose | Status |
|------|---------|--------|
| **schema_guard.py** | Validation gatekeeper (R5 compliance) | ✅ Mature, no changes |
| **config_schema.py** | Pydantic v2 config models | ✅ Already fixed |
| **sensitivity_tail_risk.py** | Stub for future tail risk calc | 🟡 Needs implementation (1KB) |
| **sensitivity_export.py** | Excel/chart export | 🟡 Add heatmap support |
| **sensitivity_visualization.py** | Plot generation | 🟡 Modern matplotlib patterns |

---

## 🔧 PART 4: IMPLEMENTATION ROADMAP

### Phase 1: Fix Critical Issues (2 hours) ⚠️ DO FIRST

**Objective:** Make all code syntactically valid & Pydantic v2 compliant

```bash
# 1. sensitivity_heatmap.py - Fix syntax errors
   - Add missing closing parens on lines 27-28, 33-34
   - Change Dict/Any imports to dict notation
   - Test: `python -m analytics.sensitivity_heatmap` should import cleanly

# 2. sensitivity_v14.py - Modernize type hints
   - Dict[str, Any] → dict[str, Any] throughout
   - Add __all__ export list
   - Ensure Pydantic v2 compliance on SensitivityRequest
   - Test: `pytest tests/analytics_layer/test_sensitivity_v14.py -v`

# 3. parameter_solvers.py - Interface cleanup
   - Review solver registration mechanism
   - Ensure no circular imports with monte_carlo_v14
   - Document get_solver() contract
   - Test: `python -c "from analytics.parameter_solvers import get_solver; print(get_solver('capex'))"` should work
```

### Phase 2: Integration Testing (3 hours)

**Objective:** Ensure monte_carlo + sensitivity work together

```bash
# 1. Unit Tests
   - Run existing sensitivity tests: pytest tests/analytics_layer/test_sensitivity_v14.py
   - Run monte carlo tests: pytest tests/analytics_layer/test_monte_carlo_v14.py
   - Verify both use same evaluate_with_overrides() path

# 2. Integration Tests
   - Create tests/api/test_monte_carlo_sensitivity_integration.py:
     * Run tornado on base scenario
     * Run monte carlo on same scenario
     * Compare ranges (MC P10-P90 should bracket tornado min-max)
     * Verify DSCR tracking in both paths

# 3. Regression Tests
   - Ensure all 282 passing tests still pass
   - Check coverage: sensitivity_v14.py should hit 85%+ (currently ~66%)
```

### Phase 3: Feature Completeness (4-5 hours)

**Objective:** Build out stub functionality

```bash
# 1. Tail Risk Quantification (sensitivity_tail_risk.py)
   - Implement: def enrich_tornado_with_tail_risk()
   - Calculate: Probability(DSCR < threshold) from MC results
   - Output: Attach risk scores to tornado drivers
   - Reference: Damodaran's tail risk framework

# 2. Correlation Modeling
   - Add: def compute_parameter_correlation_matrix()
   - Load from YAML: scenarios/sensitivity_correlations.yaml
   - Apply to: Monte Carlo sampling (LHS with correlation matrix)
   - Benchmark: Compare uncorrelated vs correlated results

# 3. Heatmap Enhancements
   - Fix: sensitivity_heatmap.py syntax issues
   - Add: Two-way sensitivity heatmap output (Excel compatible)
   - Test with: scenarios/ base case

# 4. Visualization Modernization
   - Update sensitivity_visualization.py for matplotlib 3.8+
   - Generate: Tornado charts with sensitivity bands
   - Output: PNG/PDF suitable for lender decks
```

### Phase 4: Documentation & Best Practices (2 hours)

**Objective:** Codify standards for future maintenance

```bash
# 1. Create: docs/SENSITIVITY_ARCHITECTURE.md
   - Explain layered approach (tornado vs MC)
   - When to use each method
   - Parameter definition checklist
   - Validation requirements (R5 compliance)

# 2. Create: scenarios/sensitivity_parameters_template.yaml
   - Example parameter definitions
   - Guidance on base_value, low_pct, high_pct ranges
   - Industry benchmarks (tariff ±15%, capex ±20%, etc.)

# 3. Create: CORRELATION_ASSUMPTIONS.md
   - Document which parameters are correlated (if any)
   - Cite academic literature (Damodaran, NREL)
   - Justify coefficients

# 4. Update: README.md in analytics/sensitivity/
   - Add code examples (tornado, breakeven, MC + sensitivity)
   - Link to academic references
   - Explain FIN-02 (discount rate precedence)
```

### Phase 5: Advanced Features (Optional, Future Sprints)

```bash
# 1. Optimization Layer
   - def optimize_from_sensitivity_insights()
   - Use tornado to identify key levers
   - Recommend parameter adjustments
   - Example: "Increase PPA tariff by X to achieve 15% IRR"

# 2. Scenario Recommendation Engine
   - Use MC tail risk + tornado drivers
   - Recommend: Conservative, Base, Optimistic scenarios
   - Output: Pre-configured YAML files

# 3. Lender Report Generation
   - Integration with export_helpers.py
   - Auto-generate: Risk matrix, tornado chart, probability waterfall
   - Compliance: IFC E&S standards, Moody's metrics

# 4. Real-Time Dashboard
   - Connect streamlit_app.py to sensitivity engines
   - Interactive parameter sliders
   - Live tornado + MC distribution updates
```

---

## 🎯 PART 5: DECISION FRAMEWORK

### Q: Should we refactor sensitivity module into submodules?

**Current:** Monolithic `sensitivity_v14.py` (36KB)

**Options:**
1. **Keep as-is** (simplest, 282 tests already passing)
2. **Split into:** `sensitivity/{tornado.py, breakeven.py, contracts.py}` (cleaner, requires test migration)

**Recommendation:** **KEEP AS-IS for now**
- Reason: Single file is easier to maintain during Pydantic v2 transition
- Future: Can refactor after tests stabilize (Sprint 10+)

### Q: How to handle parameter correlation in Monte Carlo?

**Current:** LHS samples are independent (no correlation)

**Best Practice:** Real projects have correlations:
- Capex ↔ Debt Tenor (both increase cost, typically +0.6 correlation)
- Tariff ↔ Offtake (both revenue drivers, +0.4 correlation)
- Exchange Rate ↔ FX hedging (inverse relationship)

**Recommendation:**
1. Phase 1: Document assumed independence
2. Phase 2: Add optional correlation matrix input to MC
3. Reference: Iman-Conover method or Cholesky decomposition

### Q: Should sensitivity integrate with lender covenants?

**Current:** Separate paths (sensitivity just perturbs params; debt covenants tracked independently)

**Best Practice:** Lenders care about:
- "What tariff breach triggers DSCR < 1.25?" → Use breakeven
- "Probability of DSCR breach in bad year?" → Use MC + covenant snapshot

**Recommendation:** ✅ **Already supported**
- `sensitivity_v14.py` can target "dscr_min" metric
- `monte_carlo_v14.py` outputs DSCR distribution
- `_build_debt_covenant_snapshot()` in pipeline_v14.py tracks breaches
- **No action needed** (architecture already correct)

---

## 📚 PART 6: ACADEMIC & INDUSTRY REFERENCES

### Referenced Standards & Papers

| Source | Relevance | Where Used |
|--------|-----------|-----------|
| Damodaran, A. (2012). *Valuing Young Companies* | Tail risk, sensitivity interpretation | sensitivity_tail_risk.py |
| IRENA (2019). Renewable Energy Project Finance Guidelines | Parameter ranges, stress scenarios | Parameter tuning |
| IFC E&S Framework (2012) | Covenant requirements, downside analysis | schema_guard.py, debt_covenants |
| Hull, J. (2021). *Risk Management & Financial Institutions* | Monte Carlo, VaR/CVaR | monte_carlo_v14.py |
| Moody's Project Finance Criteria | Rating methodology, coverage ratios | KPI calculation |
| NREL Solar Proforma (2021) | Cost assumptions, PPA sensitivity | Parameter templates |

### Open Questions for Industry Review

1. **Correlation Assumptions:** Which parameters should we assume correlated? (Capex↔Tenor, Tariff↔Volume, etc.)
2. **Tail Risk Thresholds:** At what probability should we flag covenant breach risk? (5%? 10%?)
3. **Lender Requirements:** Should we auto-generate Moody's/S&P-style risk matrices?
4. **Validation:** Do we have historical project data to validate distributions?

---

## ✅ PART 7: PRE-IMPLEMENTATION CHECKLIST

Before coding Phase 1, ensure:

- [ ] All 14 files downloaded and reviewed
- [ ] Current test suite runs cleanly (282/290 passing)
- [ ] Pydantic v2 migration complete on monte_carlo_v14.py ✅ (already done)
- [ ] Team agreement on correlation modeling approach
- [ ] Decision on sensitivity submodule refactoring (Phase 1 vs later)
- [ ] Lender input on covenant breach thresholds (for Phase 3)

---

## 🚀 RECOMMENDED EXECUTION ORDER

**Total Estimated Time:** 10-12 hours across 5 phases

```
Sprint 9 (This Week)
├─ Phase 1: Critical fixes (2h) ✅ DO THIS FIRST
├─ Phase 2: Integration testing (3h)
└─ Phase 3: Feature completeness (4-5h)

Sprint 10 (Next Week, Optional)
├─ Phase 4: Documentation (2h)
└─ Phase 5: Advanced features (Future)
```

---

**Analysis Complete.** Ready for implementation discussion? 🎯
