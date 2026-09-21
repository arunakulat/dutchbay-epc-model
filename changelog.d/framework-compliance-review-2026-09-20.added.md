- Add `docs/Framework_Compliance_Review_2026-09-20.md`, the compliance review of the 20 September
  2026 work against GWTF, CASPER, CESSPIT and CCCDIR. It records per framework what the rule
  requires, what was followed and what was not, and it clears both merged pull requests
  (#1272 and #1273) and four of the five open drafts.
- The review's substantive finding is that four tracked files contradict the canonical ruleset on
  what the frameworks mean. `go_with_the_flow_rules_v3_0_clean.csv` rows `FRAMEWORK-01/02/03` are
  canonical and test-pinned; `.github/SPRINT_WORKFLOW_CHECKLIST.md`, `docs/AUDIT_CASHFLOW_V14_FINAL.md`,
  `docs/SPRINT_16_REORGANIZATION_COMPLETE.md` and a `Full Dolphin Rules` file in the DutchBay_RAG
  repository each give different expansions. The last of those states a CASPER expansion that
  appears nowhere in the canonical source. Recorded here; the reconciliation is its own change.
- Also recorded: `DOC-02` states its enforcement as a CI check verifying VERSION and CHANGELOG for
  pull requests touching `analytics/` or `finance/`, and no such check exists.
- Documentation only. No code, configuration or scenario input is touched, and no KPI is reachable
  from this change.
