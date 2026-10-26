- Make the balloon `refinance` treatment honest before any scenario relies on it (#1396,
  P3-COV-03). Its tenor and rate premium now come only from
  `constraints.refinancing.refinance_tenor_years` and `refinance_rate_premium`: the engine's
  silent 3-year / +2% fallback is removed, and a scenario that selects `refinance` without
  both terms is refused at v14 pre-flight, naming the missing path. A refinance tenor that
  would run past the modelled timeline is refused instead of being compressed into the final
  period. `debt_result["refinance"]` now publishes the tranche: its terms and their basis
  (`assumption_no_term_sheet`), the interest/principal split of each payment, and a coverage
  test against the scenario's DSCR covenant. The three statements treat the interest inside
  refinance payments as interest rather than debt retirement, so the debt tie-out holds
  under refinance. No committed scenario selects `refinance`, so the canonical KPI vector is
  unchanged; switching the lender case onto it is a separate, owner-held re-baseline.
