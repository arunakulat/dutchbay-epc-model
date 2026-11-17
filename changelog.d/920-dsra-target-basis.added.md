- Both DSRA month figures are now labelled as assumptions, with the key that set each one
  (#920, owner ruling 2026-11-15: keep the reserve at 6 months of debt service as a labelled
  assumption until a term sheet sets it). The model holds two figures:
  - `debt_result["funding"]` carries `dsra_target_basis` (`assumption_no_term_sheet`, the
    same label the refinanced tranche's terms carry), `dsra_target_source` and
    `dsra_target_governs`. These months size a reserve funded at financial close, and only
    when `Financing_Terms.dsra.fund_at_close` is on; otherwise `dsra_target_governs` says
    they size nothing (`nothing_reserve_sized_by_equity_min_reserve_months`).
  - `equity_distribution.equity_summary` carries `min_reserve_months_source` and
    `min_reserve_months_basis` beside `min_reserve_months`. These months size the reserve the
    equity waterfall builds from operating cash, in every mode.
- Each source is the YAML path that set the figure, or `code_default` when the engine's
  6-month fallback did. That includes a winning key that is null or not a number: the months
  and the source are now resolved in one walk, so a source name never sits beside a figure
  its key did not set.
- No figure moves: all 33 scenarios that run on `main` give identical KPIs, debt and equity
  results apart from the new keys. On the funding side, 28 read
  `Financing_Terms.reserves.dsra_months` and 5 use the code default; no committed scenario
  turns `fund_at_close` on, so those months size nothing today. No committed scenario authors
  `min_reserve_months`, so the reserve in the cash flows is the 6-month code default in all 33.
  Unifying the two figures is #1399 part B.
- The labels reach the results dict only. The web API's `FundingBlock` and the lender
  report's reserve sentence do not show them yet.
