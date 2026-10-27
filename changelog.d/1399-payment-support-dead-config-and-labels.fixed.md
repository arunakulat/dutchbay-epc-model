- **`P3-COV-05` part A — dead payment-support config is refused, and the reserve and
  guarantee bases are stated.** `Financing_Terms.reserves.receivables_guarantee_months` was
  declared in 16 committed scenarios and two reproduction copies, usually as nine months of
  "CEB payment risk", but nothing in the engine read it. The v14 pre-flight
  (`analytics/schema_guard.py`, step 1g) now refuses the key wherever it appears under
  `Financing_Terms`, naming its path (`FRAMEWORK-02`: no silent dead config), the key is
  removed from every committed scenario, and `scripts/ci/validate.py` no longer lists it as
  an allowed reserve. `debt_result.funding` now records `dsra_at_close_basis`
  (`none_built_from_operating_cash` unless `Financing_Terms.dsra.fund_at_close` is on) and a
  `payment_support` block stating that `use_revenue_guarantee` only loads a fee into the
  cost of debt and that no payment-support cash flow is modelled. The lender report's
  Sources & Uses page states a zero DSRA at close and the absence of payment support instead
  of omitting the row, and `docs/MODULE_REFERENCE.md` records both bases. No financial
  formula or KPI changes: a KPI oracle over the 29 committed scenarios that run, compared as
  `float.hex()`, is identical before and after; the other eight fail pre-flight at both trees
  for reasons that predate this change. Part B (funding form, target months and any
  receivables support) waits on authenticated term-sheet terms (#920). The `F-5` bar and
  #1110's `HOLD` are untouched.
