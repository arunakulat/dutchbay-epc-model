# Governance Architecture Decision Record: DOC-02 Ruleset & Workflow Reconciliation

- **Status**: Accepted (Owner Option 2 Resolution)
- **Date**: 2026-11-12
- **Issue**: [#1565](https://github.com/arunakulat/dutchbay-epc-model/issues/1565)
- **Predecessor Reference**: #1452 (Retrospective review, Finding F-1 / Remediation R-6)
- **Classification**: R2 Semantic Risk Class (governance ruleset reconciliation).

---

## 1. Problem Statement & Audit Diagnosis

### The Discrepancy
As identified in Remediation R-6 of the retrospective assurance review of PR #1452:
1. **Rule Text (`DOC-02`)**:
   - `DOC-02` description stated: "Any change that can impact IRR, DSCR, NPV, or covenant logic must update the model CHANGELOG and bump the VERSION. Such changes require regression test updates and explicit reviewer sign-off."
   - The enforcement column asserted: "CI checks verify VERSION and CHANGELOG changes for PRs touching `analytics/` or `finance/`; regression tests must be updated before merge."
2. **Missing CI Enforcement**:
   - No such check existed in `.github/workflows/` or `scripts/ci/` comparing `VERSION` or `CHANGELOG.md` against an `analytics/` or `finance/` diff.
3. **Template Contradiction**:
   - `.github/pull_request_template.md` instructed writers to create a fragment: `Changelog fragment added under changelog.d/ (not an edit to CHANGELOG.md)`, with no exception for KPI-moving changes.

### Architectural Reality: Fragment-Based Workflow
The repository deliberately uses a Towncrier/Scriv-style changelog fragment pattern (`changelog.d/<id>.<category>.md`). As documented in `changelog.d/README.md`:
- Writing directly to `CHANGELOG.md`'s `[Unreleased]` block in every PR guarantees merge conflicts between concurrent PRs, forcing rebases and duplicate full CI runs.
- Similarly, bumping `VERSION` directly on individual PR branches creates immediate merge conflicts when multiple PRs land before a release cut.
- Release cuts are performed via `scripts/compile_changelog.py` and `scripts/github/gh_tools.py`, which compile accumulated fragments into `CHANGELOG.md` and bump `VERSION`.

---

## 2. Decision: Option 2 (Reconcile CSV to Actual Governed Workflow)

Between the two options offered in Issue #1565:
- **Option 1**: Force direct edits to `VERSION` and `CHANGELOG.md` on KPI-moving PRs and reconcile the template. (Rejected: breaks concurrency, creates merge conflict storms, contradicts Towncrier design).
- **Option 2 (Selected)**: Correct the CSV's enforcement text to what is actually enforced. Make fragments plus a release-time bump the documented route, and require the KPI-moving PR's fragment to state the as-merged figures.

### Changes Applied:
1. **Canonical Ruleset CSV (`go_with_the_flow_rules_v3_0_clean.csv`)**:
   - Updated `DOC-02` description:
     `"Any change that can impact IRR, DSCR, NPV, or covenant logic must include a changelog fragment under changelog.d/ recording the as-merged figures, and update regression tests with explicit reviewer sign-off. Release cuts compile fragments into CHANGELOG and bump VERSION."`
   - Updated `DOC-02` enforcement:
     `"PR template requires a 'Financial impact' section and a changelog fragment under changelog.d/; reviewer sign-off verifies as-merged figures; release cuts compile fragments into CHANGELOG.md and bump VERSION; regression tests must be updated before merge."`
   - The false assertion claiming that a CI check directly verified `VERSION` and `CHANGELOG.md` changes has been removed.

2. **Automated Verification Guard (`tests/lint/test_doc02_reconciliation.py`)**:
   - Added pytest tests that pin:
     - Active status of `DOC-02`.
     - Absence of the historical false CI claim (negative control).
     - Explicit requirement for `changelog.d/` fragments recording as-merged figures.
     - Strict alignment across `go_with_the_flow_rules_v3_0_clean.csv`, `.github/pull_request_template.md`, and `changelog.d/README.md`.

---

## 3. Reviewer Checklist for DOC-02 (RECRUIT-01)
When reviewing any PR modifying `analytics/` or `finance/`:
1. Check `### Scope`: does it declare KPI impact (`none` vs `stated in "Financial impact" below`)?
2. If KPI impact is declared:
   - Does `### Financial impact` detail affected KPIs, direction, and magnitude?
   - Does a changelog fragment under `changelog.d/` record the exact as-merged figures?
   - Are regression tests updated and re-baselined with citations?
3. Verify that `CHANGELOG.md` is NOT modified directly on the branch; fragments are folded only at release cuts.
