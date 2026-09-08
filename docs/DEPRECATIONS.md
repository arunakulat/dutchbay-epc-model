# Deprecated debt-series alias

`plan_debt()["raw_dscr_series"]` remains a plain-list value alias of the positional
`dscr_series` introduced with the F2/F3 contract in model version 15.5.0. Prefer
`dscr_series` for debt-period indexing or `dscr_periods` for explicit year labels and
folded covenant coverage. Compact `ScenarioResult.dscr_series` retains its existing
contract and is not a period index.

The plain dictionary/list result is required by the D3B/D3C exact JSON freeze.
Direct dictionary access therefore cannot warn without breaking that contract.
`finance.debt_v14.deprecated_raw_dscr_series` emits the tested DeprecationWarning;
direct alias access remains warning-free and is explicitly retained.

Removal is not part of F2/F3. Retain the alias for at least one subsequent release
and two completed sprints; no removal sprint is scheduled. The migration owner is
the finance maintenance coordinator. A separate reviewed removal must name its
sprint and establish zero remaining consumers, an announcement, and compatibility
acceptance. Known consumers to migrate include `api/pipeline_api.py`,
`analytics/executive_workbook.py`, `analytics/mc/engine.py`, and the result facade.
This conservative retention is the explicit lifecycle exception to assigning an
unverified sprint number. No release or lender authority is conferred.
