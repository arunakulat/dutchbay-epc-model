# 📊 QUICK REFERENCE: SENSITIVITY MODULE INTEGRATION AT A GLANCE

## Current State Assessment

```
┌─────────────────────────────────────────────────────────────────┐
│ DUTCHBAY EPC MODEL - SENSITIVITY LAYER MATURITY                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ Architecture:        ████████████████████░ (90%) STRONG           │
│ Type Safety:        ██████████░░░░░░░░░░░ (50%) NEEDS WORK       │
│ Test Coverage:      ██████████████░░░░░░░ (66%) GOOD             │
│ Integration:        █████████████████░░░░ (80%) GOOD             │
│ Documentation:      ███████░░░░░░░░░░░░░░ (35%) WEAK             │
│                                                                   │
│ Overall Readiness: 🟡 PHASE 1 CRITICAL FIXES NEEDED             │
│ Time to Production: ~11-12 hours (5 phases)                     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Three-Tier Integration Framework

### TIER 1: CRITICAL ISSUES (2 hours)
| File | Issue | Fix |
|------|-------|-----|
| `sensitivity_heatmap.py` | Syntax: Missing `)` (2×) | Add closing parens |
| `sensitivity_v14.py` | Type hints: `Dict` → `dict` | Use PEP 585 |
| `parameter_solvers.py` | Circular imports check | Verify import order |

**Command:** `pytest tests/ -v` → All 282+ tests must pass ✅

---

### TIER 2: INTEGRATION (3 hours)
| Task | Benefit |
|------|---------|
| Test tornado + MC convergence | Verify consistent KPI surface |
| DSCR tracking in both engines | Ensure covenant data flows |
| Coverage → 85% (sensitivity_v14) | Reduce regression risk |

**Command:** `pytest tests/api/test_monte_carlo_sensitivity_integration.py -v` → New tests pass ✅

---

### TIER 3: FEATURES (4-5 hours)
| Feature | Impact | Timeline |
|---------|--------|----------|
| Tail risk (P(DSCR breach)) | Lender risk metrics | Phase 3 |
| Correlation modeling | Realistic MC scenarios | Phase 3 |
| Heatmap exports | Lender-facing output | Phase 3 |

**Command:** `python -c "from analytics.sensitivity.sensitivity_tail_risk import calculate_covenant_breach_probability"` → Import works ✅

---

## Architecture: How Sensitivity Fits

```
                    CLI / Dashboards
                          ↑
              ┌─────────────────────────┐
              │  Batch Orchestrator     │
              │ (scenario_analytics.py) │
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
  ┌──────────┐    ┌──────────────┐    ┌──────────┐
  │ Tornado  │    │  Breakeven   │    │Monte Carlo│
  │Sensitivity│    │   Solver     │    │Analysis  │
  └─────┬────┘    └──────┬───────┘    └────┬──────┘
        │                │                  │
        └────────────────┼──────────────────┘
                         ↓
            ┌─────────────────────────┐
            │  run_v14_pipeline()     │
            │ (canonical engine)      │
            └────────────┬────────────┘
                         ↓
            ┌─────────────────────────┐
            │ calculate_scenario_kpis │
            │ (single source of truth)│
            └─────────────────────────┘
```

**Key Insight:** Both sensitivity AND Monte Carlo converge on same KPI calculation
→ **Consistent results, different perspectives on risk**

---

## Parameter Sensitivity Workflow

```
1. DEFINE PARAMETERS (YAML)
   ├─ variable_name: "project.capex_usd_per_kw"
   ├─ base_value: 1200.0
   ├─ low_pct: -20.0 (20% reduction)
   └─ high_pct: +20.0 (20% increase)

2. SENSITIVITY ANALYSIS (Two Engines)
   ├─ Tornado:        Loop params, vary one at a time
   └─ Monte Carlo:    Sample from distributions

3. OUTPUT (Same Interface)
   ├─ project_irr: [p10, p50, p90]
   ├─ project_npv: [p10, p50, p90]
   ├─ dscr_min:    [p10, p50, p90]
   └─ dscr_breach_prob: [float]

4. REPORTING (Lender-Ready)
   ├─ Tornado chart (parameter importance)
   ├─ Risk matrix (breach probability)
   ├─ Excel summary (all metrics)
   └─ Recommendations (adjust tariff/capex)
```

---

## What Gets Fixed in Each Phase

### Phase 1: SYNTAX + TYPE SAFETY (2h)
```python
# BEFORE (Python 2 era)
from typing import Dict, List, Any
def process(data: Dict[str, Any]) -> List[float]:
    pass

# AFTER (PEP 585, modern Python)
def process(data: dict[str, Any]) -> list[float]:
    pass
```
✅ **Outcome:** 282+ tests pass, zero type errors

### Phase 2: INTEGRATION TESTS (3h)
```python
# NEW: test_monte_carlo_sensitivity_integration.py
def test_tornado_and_monte_carlo_convergence():
    tornado_base_irr = 15.2%
    mc_median_irr = 15.1%
    assert abs(tornado_base_irr - mc_median_irr) < 1%  # ✅ PASS
```
✅ **Outcome:** Tornado + MC use same pipeline

### Phase 3: TAIL RISK + CORRELATION (4-5h)
```python
# NEW: calculate_covenant_breach_probability()
# ENHANCE: MC with correlation matrix
# EXPORT: Heatmap to Excel with conditional formatting
```
✅ **Outcome:** Lender-ready risk metrics

### Phase 4: DOCUMENTATION (2h)
```
docs/SENSITIVITY_ARCHITECTURE.md
scenarios/sensitivity_parameters_template.yaml
tutorials/tornado_analysis_quickstart.md
```
✅ **Outcome:** Users can run sensitivity without help

---

## Best Practices From Industry

| Practice | Source | DutchBay Status |
|----------|--------|-----------------|
| **Tornado before Monte Carlo** | IRENA, Damodaran | ✅ Implemented (phase 1) |
| **DSCR sensitivity for lenders** | Moody's/S&P criteria | ✅ Implemented (phase 1) |
| **P(breach) for rating** | Risk frameworks | ⚠️ Phase 3 (in progress) |
| **Breakeven analysis** | Strategic planning | ✅ Implemented (phase 2) |
| **Correlation modeling** | Financial theory | ⚠️ Phase 3 (in progress) |
| **Multiple scenarios** | Best practice | ✅ Batch orchestrator ready |

---

## Risk Profiles & Confidence Levels

```
Risk of Phase 1 (Syntax fixes):         🟢 VERY LOW (mechanical changes)
Risk of Phase 2 (Integration tests):    🟢 LOW (defensive patterns already in place)
Risk of Phase 3 (New features):         🟡 MEDIUM (new code, but parallel to existing)
Risk of Phase 4 (Documentation):        🟢 NONE (pure documentation)
```

---

## Timeline & Deliverables

```
Sprint 9 (This Week)
├─ Monday (2h)  → Phase 1: Critical fixes + syntax
│                ↓ Deliverable: 282+ tests passing ✅
├─ Wednesday (3h) → Phase 2: Integration testing
│                ↓ Deliverable: Tornado + MC convergence verified ✅
└─ Friday (4-5h) → Phase 3: Feature completeness
                 ↓ Deliverable: Tail risk + correlation + exports ✅

Sprint 10 (Next Week, Optional)
├─ Phase 4: Documentation (2h)
│          ↓ Deliverable: User guide + architecture docs ✅
└─ Phase 5: Advanced features (lender reports, optimization)
           ↓ Deliverable: PowerPoint generation, scenario recommendation

Total Effort: 11-12 hours
Production Ready: End of Sprint 9
Lender Ready: End of Sprint 10
```

---

## Success Metrics

**After Phase 1 (2h):**
- [ ] 282+ tests pass
- [ ] Zero Pydantic v2 warnings
- [ ] `mypy` clean

**After Phase 2 (3h):**
- [ ] Tornado base case = MC median (within 1%)
- [ ] DSCR tracked consistently
- [ ] 85%+ coverage in sensitivity_v14.py

**After Phase 3 (4-5h):**
- [ ] `enrich_tornado_with_tail_risk()` working
- [ ] MC with correlation matrix working
- [ ] Heatmap exports to Excel with formatting

**After Phase 4 (2h):**
- [ ] 5 key documentation files created
- [ ] User can run `dutchbay-cli sensitivity --help` and understand usage
- [ ] Parameter template provided

---

## One-Page Cheat Sheet

### How to Run Sensitivity Analysis (Post-Phase 1)

```bash
# 1. Define parameters (YAML)
cat > config/tornado_drivers.yaml << EOF
parameters:
  - variable_name: project.capex_usd_per_kw
    base_value: 1200.0
    low_pct: -20.0
    high_pct: 20.0
EOF

# 2. Run tornado
dutchbay-cli sensitivity \
  --base-scenario scenarios/dutchbay_base.yaml \
  --parameters config/tornado_drivers.yaml \
  --metric project_irr \
  --output results/tornado.xlsx

# 3. Run Monte Carlo (Phase 3+)
dutchbay-cli sensitivity \
  --base-scenario scenarios/dutchbay_base.yaml \
  --parameters config/tornado_drivers.yaml \
  --use-monte-carlo --n-iterations 1000 \
  --enable-correlation \
  --output results/mc_analysis.xlsx

# 4. View results
open results/tornado.xlsx  # Tornado chart
open results/mc_analysis.xlsx  # Distribution + risk metrics
```

---

## FAQ

**Q: Why not just use Monte Carlo and skip tornado?**
A: Tornado is O(n) fast (n=parameters), MC is O(n×m) (m=iterations). Lenders expect 1-sec tornado for quick decisions.

**Q: When should I use correlation?**
A: Real projects have it. Phase 3 adds it. For Phase 1-2, assume independence (conservative).

**Q: How do I validate results?**
A: Phase 2 integration test: tornado base case should match MC median within 1%.

**Q: Can I run sensitivity on custom metrics?**
A: Yes! Any KPI from `calculate_scenario_kpis()` works (IRR, NPV, DSCR, etc.).

**Q: What about negative DSCR or NaN values?**
A: Handled defensively. See `_clean_dscr_series()` in metrics.py (already robust).

---

## Next Steps

1. **Review** this document (5 min read)
2. **Approve** Phase 1 scope (decision: keep monolithic, add modern type hints)
3. **Execute** Phase 1 (2 hours, run tests, commit)
4. **Report** results (282+ tests pass? → Proceed to Phase 2)
5. **Iterate** through Phases 2-4

---

**Status: READY FOR APPROVAL & EXECUTION** 🚀

Contact: [Your Name]
Date: December 8, 2025
Sprint: 9 (EPC Model Risk Analysis)
