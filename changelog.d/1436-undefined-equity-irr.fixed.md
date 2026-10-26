- Report an undefined equity IRR as undefined rather than 0.0 (#1436). When no discount
  rate solves the equity cashflows, the waterfall already returned `None`, but the KPI
  surface kept the metrics layer's 0.0 sentinel, so the worst cases (for example a 6-year
  balloon refinance on the lender case) read as break-even. `kpis.equity_irr` is now
  `None` in that case; the report shows "undefined" in the KPI table and says so in the
  verdict; the cost-of-equity sweep carries `None`; and the capex Monte Carlo refuses
  rather than take a percentile over it. The API's `KpiCard.value` may now be `null`
  (with `display` "undefined") for such a KPI, so the public contract version moves
  from 1.2 to 1.3. Defined equity IRRs, and the canonical KPI vector, are unchanged.
