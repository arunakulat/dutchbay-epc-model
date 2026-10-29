- **`P2-F3-01` — the equity waterfall carries a debt-service shortfall instead of clamping
  it to zero.** `finance/equity_distribution_v14_hydra.py` used to compute cash after debt
  service as `max(0, CFADS - debt service - interest WHT)`, so a year whose CFADS could not
  meet scheduled service cost equity nothing and the gap disappeared. The gap is now funded
  in a fixed, disclosed order: a DSRA draw up to the reserve balance, then cash the SPV
  already holds for the sponsor (lockup-trapped cash, then retained holdback or un-swept
  cash), then a sponsor cure booked as a negative equity cash flow in that year, the same
  cash-call treatment a balloon shortfall already received. Each annual row now publishes
  `debt_service_shortfall_usd`, `dsra_draw_usd`, `spv_cash_applied_usd` and
  `sponsor_cure_usd`, and `cf_after_debt_usd` is published signed. The equity summary
  totals each source and counts `debt_service_shortfall_years`, and the KPI surface carries
  `equity_debt_service_shortfall_years` and `equity_sponsor_cure_usd`. A warning names each
  shortfall year. Project IRR, project NPV, CFADS and DSCR are upstream of the waterfall and
  do not move. The canonical lender case has no shortfall year and is byte-identical; 13
  other committed scenarios with a DSCR<1 year report lower equity returns, the largest
  being `dutchbay_pessimistic_2025Q4` (equity IRR -7.43% to -54.39%) and
  `edge_extreme_stress` (-12.77% to undefined: its equity never receives a positive
  distribution once the shortfalls are cured, so no rate solves its cash flows). The `F-5`
  bar and #1110's `HOLD` are untouched.
