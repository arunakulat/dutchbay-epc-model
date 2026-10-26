- Report an undefined equity IRR as undefined rather than 0.0 (#1436). When no discount
  rate solves the equity cashflows, the waterfall already returned `None`, but the KPI
  surface kept the metrics layer's 0.0 sentinel, so the worst cases (for example a 6-year
  balloon refinance on the lender case) read as break-even. `kpis.equity_irr` is now
  `None` in that case; the report shows "undefined" in the KPI table and says so in the
  verdict; the cost-of-equity sweep carries `None`; and the capex Monte Carlo refuses
  rather than take a percentile over it. On the API, `KpiCard.value` and the values of
  `CaseResult.kpis` may now be `null` for such a KPI (an absent key still means "not
  computed"), which retypes two response fields; the contract-version consequence is
  recorded in `app/api/responses.py`. Defined equity IRRs, and the canonical KPI vector,
  are unchanged.
- Known consequence, tracked separately on #1353: the Monte Carlo aggregator excludes a
  trial with any missing metric from every metric, so a trial with an undefined equity IRR
  now leaves the DSCR, IRR and NPV distributions too. That drops the worst draws and moves
  the minimum and P10 DSCR optimistically (a measured three-trial example: 1.05 to 1.31).
  Before this change the same trial was kept, at a false 0% equity IRR.
