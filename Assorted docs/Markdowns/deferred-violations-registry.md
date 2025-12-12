# DEFERRED VIOLATIONS REGISTRY
## Go With The Flow: Known Issues for Future Resolution

**Purpose:** Track violations intentionally deferred during Phase 2 cleanup for resurrection during module integration.

**Last Updated:** 2025-11-27
**Phase:** 2 (Manual Cleanup)
**Status:** Deferred (scheduled for integration sprint)

---

## PHASE 2 DEFERRED VIOLATIONS

### Category: F821 (Undefined Names - Dead Code)

These violations exist in **experimental/demo modules** that are not yet integrated into the main v14 pipeline. They represent forward-looking code that references features planned but not yet implemented.

| File | Line | Violation | Type | Reason | Action | Ticket |
|------|------|-----------|------|--------|--------|--------|
| `analytics/sensitivity/dashboard_demo.py` | 19 | `enrich_tornado_with_tail_risk` | F821 | Function doesn't exist (planned feature) | Add `# noqa: F821` OR implement function | TBD |
| `analytics/sensitivity/dashboard_demo.py` | 19 | `montecarlo_result` | F821 | Variable doesn't exist (planned parameter) | Add `# noqa: F821` OR pass as param | TBD |
| `analytics/sensitivity/dashboard_demo.py` | 20 | `optimize_from_sensitivity_insights` | F821 | Function doesn't exist (planned feature) | Add `# noqa: F821` OR implement function | TBD |
| `analytics/sensitivity_visualization.py` | 75 | `multi_metric_suite_to_dataframe` | F821 | Function doesn't exist (planned feature) | Add `# noqa: F821` OR implement function | TBD |

---

### Category: F541 (F-Strings Without Placeholders)

These are in CI/automation scripts (non-core logic). Low priority but should be cleaned up.

| File | Count | Reason | Action |
|------|-------|--------|--------|
| `go_with_the_flow_ci_enhanced.py` | ~20 | Debug/logging statements using f-strings | Convert to regular strings or add placeholders |
| `go_with_the_flow_ci_v2_final.py` | ~10 | CI logging | Same as above |

---

### Category: E501 (Line Too Long - 92 > 88 chars)

**Count:** 129 violations
**Reason:** Complex logic, manual line breaks would hurt readability
**Action:** Review per file during integration; may accept some as-is if justified

---

### Category: E402 (Import Not at Top of File)

**Count:** 35 violations
**Reason:** Conditional imports, deferred module loading in `analytics/fx/`
**Status:** Intentional (marked for future refactor)
**Action:** Move to top OR document with `# noqa: E402` if conditional import is necessary

---

## INTEGRATION CHECKLIST

When integrating experimental modules into main v14 pipeline:

- [ ] Review F821 violations in `dashboard_demo.py` and `sensitivity_visualization.py`
- [ ] Decide: implement missing functions OR mark with `# noqa: F821`
- [ ] Fix F541 (f-strings) in CI scripts
- [ ] Review E501 line length issues per file
- [ ] Refactor E402 conditional imports OR document intent
- [ ] Re-run full flake8 + pytest suite
- [ ] Update this registry with resolution status

---

## Go With The Flow Principle

**Deferred violations are TODO markers.** They indicate:
1. **Incomplete features** that will be implemented later
2. **Experimental code** not yet merged into main pipeline
3. **Technical debt** acknowledged and tracked

This registry ensures violations don't get lost and are systematically resolved during the next integration cycle.

---

## Tracking

To resurface these violations later:

```bash
# Search for all deferred violations
grep -r "# noqa: F821\|# noqa: F541\|# noqa: E402" analytics/ finance/ tests/

# Run flake8 with specific codes
flake8 analytics/sensitivity/ --select=F821,F541,E402

# Check registry before integration
cat DEFERRED_VIOLATIONS_REGISTRY.md
```

---

## Contact

For questions about these deferred violations, refer to:
- **Phase 2 commit:** `phase2-manual-cleanup-v3` branch
- **Sprint:** Flake8 cleanup sprint (Nov 2025)
- **Owner:** Architecture team
