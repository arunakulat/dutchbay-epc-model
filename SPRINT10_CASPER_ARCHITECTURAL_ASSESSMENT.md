# CASPER Aggregation Layer - Architectural Assessment & Correction

**Date**: 2025-12-15  
**Status**: CRITICAL CLARIFICATION NEEDED  
**Source**: Executive architectural review

---

## Assessment Summary

The "Sprint 9 - Build the Mansion" document is **not a Sprint 9 deliverable**. It is a **Sprint 10+ architectural vision** that requires correction before implementation.

### What's Correct (Strong Signals)

✅ **Diagnosis is 100% accurate**
- v14 already has: cashflow, debt, WACC, sensitivity, Monte Carlo
- Missing: single canonical aggregation surface
- Solution: CASPER as composition, not refactor

✅ **Architecture instinct is sound**
- Use existing building blocks (ScenarioResult, CashflowResult, etc.)
- Don't break or replace existing code
- CASPER = unified read interface

✅ **Build sequence is mostly sane**
- Finalize CasperResult structure
- Implement analytics/casper_v14.py
- Wire mode=casper into pipeline
- Add tests & documentation

---

## What's Dangerous (Must Be Fixed)

### ❌ Gap 1: Scope Mislabeling

**Problem**: Document implies CASPER is Sprint 9  
**Reality**: CASPER is Sprint 10+  
**Risk**: Scope confusion, incorrect timeline expectations

**Fix Required**:  
Explicitly label as:
"Sprint 10+ Architectural Build Plan (Post-Stabilization)"

### ❌ Gap 2: Missing Contract Freeze

**Problem**: Jumps straight to implementation without locked schema  
**Reality**: Must freeze CasperResult structure before any code  
**Risk**: Mid-implementation scope creep, breaking changes

**Fix Required**:  
Before writing casper_v14.py:
- Freeze field names
- Freeze optional vs required
- Freeze determinism guarantees
- Freeze what NOT to include

### ❌ Gap 3: Dangerous Determinism Language

**Problem**: "Fine-tune how much sensitivity/MC should be on by default"  
**Reality**: CASPER is read-only aggregation, NOT execution policy  
**Risk**: Accidental mutation of seeds, implicit mode changes

**Fix Required**:  
Explicitly state:
- CASPER consumes results
- CASPER does NOT decide execution
- Execution policy lives in CLI/YAML/pipeline

---

## Corrected Framing (What CASPER Actually Is)

### Purpose

Define a **read-only, deterministic aggregation layer** that unifies pipeline results without altering execution semantics or adding new computations.

CASPER is a **composition**, not a refactor.

### Non-Goals (Critical)

- ❌ Do NOT refactor cashflow, debt, WACC, sensitivity
- ❌ Do NOT re-run pipeline logic
- ❌ Do NOT add new computations
- ❌ Do NOT mutate random seeds
- ❌ Do NOT implicitly enable Monte Carlo or sensitivity
- ❌ Do NOT write files by default
- ❌ Do NOT change execution policy

### Goals

- ✅ Aggregate existing results
- ✅ Provide unified read interface
- ✅ Preserve all original data
- ✅ Maintain determinism guarantees

---

## Frozen CasperResult Contract (Before Code)

Must lock this structure **before implementation**:

```
CasperResult:
  - scenario_name: str
  - base_config_path: str
  - timestamp: datetime
  - metadata: dict[str, Any]
  
  - cashflow: CashflowResult
  - wacc: WaccResult
  - debt: TrancheDebtProfile
  - covenants: DebtCovenantSnapshot
  
  - sensitivity: Optional[SensitivitySuite]
  - monte_carlo: Optional[MonteCarloResult]
```

**Rule 1: Aggregation Only**
- Read from existing results (YES)
- Compute new values (NO)
- Mutate inputs (NO)

**Rule 2: No Execution Decisions**
- CASPER receives pre-computed results
- CASPER does not decide what to run
- Execution policy stays external

**Rule 3: Determinism Boundaries**
- Same inputs → Same CasperResult (always)
- Random seeds are set BEFORE CASPER
- CASPER cannot override sampling

**Rule 4: No Default Side Effects**
- Writing is external to CASPER
- Pipeline/CLI decides when/whether to write
- CASPER returns pure data

---

## Integration Point (How It Plugs In)

```
run_full_pipeline_v14.py
  ├─ Load base scenario
  ├─ Run cashflow              → CashflowResult
  ├─ Run WACC                  → WaccResult
  ├─ Run debt                  → TrancheDebtProfile
  ├─ Run covenants             → DebtCovenantSnapshot
  ├─ [OPTIONAL] Run sensitivity → SensitivitySuite
  ├─ [OPTIONAL] Run MC         → MonteCarloResult
  │
  └─ BUILD CASPER (composition)
      ↓
      CasperResult
        ├─ cashflow (from step 2)
        ├─ wacc (from step 3)
        ├─ debt (from step 4)
        ├─ covenants (from step 5)
        ├─ sensitivity (from step 6, if run)
        └─ monte_carlo (from step 7, if run)
```

---

## What Does NOT Change

✅ All existing result types unchanged  
✅ All existing tests unchanged  
✅ All existing execution paths unchanged  
✅ Random seeds NOT altered  
✅ Sensitivity resolution NOT altered  
✅ Monte Carlo iteration count NOT altered

---

## What IS New

✅ CasperResult dataclass (frozen, immutable)  
✅ Composition logic in analytics/casper_v14.py  
✅ mode=casper in run_full_pipeline_v14.py  
✅ Tests for CasperResult creation  
✅ Documentation of aggregation contract

---

## Blunt Verdict

| Aspect | Rating | Notes |
|--------|--------|-------|
| Vision | Excellent | Correct architectural instinct |
| Timing Label | Wrong | Sprint 9 → Sprint 10+ |
| Risk | Medium | If taken literally without fixes |
| Fix Complexity | Low | Reframe + contract freeze |

---

## Recommended Next Steps

### Immediate (This Sprint)

1. ✅ Accept this architectural assessment
2. ✅ Reposition document as "Sprint 10 Design Memo"
3. ✅ Freeze CasperResult contract (locked schema)
4. ✅ Explicitly state non-goals
5. ✅ Document determinism boundaries

### Then (When Ready)

6. Implement analytics/casper_v14.py
7. Wire mode=casper into pipeline
8. Add smoke tests
9. Add linting
10. Document

---

## Action Items for Approval

- [ ] Reposition "Sprint 9 - Build the Mansion" as Sprint 10+ design memo
- [ ] Freeze CasperResult schema (no changes without approval)
- [ ] Document determinism boundaries explicitly
- [ ] State non-goals clearly
- [ ] Prepare code review checklist

---

**Status: Ready for contract freeze approval before implementation**

