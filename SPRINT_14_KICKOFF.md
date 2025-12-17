# Sprint 14: Architecture Consolidation & Risk Analytics
**Duration:** 2 weeks
**Start Date:** December 18, 2025
**Goal:** Eliminate architectural debt, implement risk layer

## Objectives
1. Replace scalar FX with structured FX block (#31)
2. Integrate canonical WACC_v14 (#28)
3. Add EquityResult to ScenarioResult (#29)
4. Rebuild sensitivity_v14 (#32)
5. Implement optimization_v14 (#30)
6. Create capital_risk_layer_v14 facade (#33)
7. Add CI import guard (#36)
8. Document FX/WACC/Equity integration (#34, #35)
9. Document AEP chain of custody (#27)

## Success Criteria
- ✅ All 10 GitHub issues closed
- ✅ 50+ new test cases passing
- ✅ CI import guards enforcing architecture
- ✅ Complete documentation for all new modules
- ✅ Zero regressions in existing tests
- ✅ Architecture v15 foundation ready

## Sprint Backlog
See GitHub Issues #27-36 for detailed requirements.

## Daily Checklist
- [ ] Day 1-2: Issue #31 (FX block)
- [ ] Day 3-4: Issue #28 (WACC)
- [ ] Day 5: Issue #29 (EquityResult) + #36 (CI guard)
- [ ] Day 6-7: Issue #32 (Sensitivity)
- [ ] Day 8-9: Issue #30 (Optimization)
- [ ] Day 10: Issue #33 (Risk layer) + #34 (Docs) + #27 (AEP docs)

## Tech Stack
- Python 3.11
- Pydantic v2 (schema guards)
- Pytest (50+ tests)
- GWTF v3.0 rules enforcement
- R23 minimalist standard
