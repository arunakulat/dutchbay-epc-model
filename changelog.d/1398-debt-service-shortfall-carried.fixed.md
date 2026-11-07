- **`P2-F3-01` — the equity waterfall carries a debt-service shortfall instead of clamping
  it to zero.** `finance/equity_distribution_v14_hydra.py` used to compute cash after debt
  service as `max(0, CFADS - debt service - interest WHT)`, so a year whose CFADS could
  not meet scheduled service cost equity nothing and the gap disappeared. The gap is now
  funded in a fixed, disclosed order: a DSRA draw up to the reserve balance, then cash the
  SPV already holds for the sponsor (lockup-trapped cash, then retained holdback or
  un-swept cash), then a sponsor cure booked as a negative equity cash flow in that year,
  the same cash-call treatment a balloon shortfall already received. Each annual row now
  publishes `debt_service_shortfall_usd`, `dsra_draw_usd`, `spv_cash_applied_usd` and
  `sponsor_cure_usd`, and `cf_after_debt_usd` is published signed. The equity summary
  totals each source and counts `debt_service_shortfall_years`, and the KPI surface
  carries `equity_debt_service_shortfall_years` and `equity_sponsor_cure_usd`. A warning
  names each shortfall year. Project IRR, project NPV, CFADS and DSCR are upstream of the
  waterfall and do not move. The canonical lender case has no shortfall year and is
  byte-identical. As merged (measured at `cd283c5d` against its parent `efe219d0`), 16
  other committed scenarios with a DSCR<1 year report lower equity returns. The largest
  are `dutchbay_pessimistic_2025Q4` (equity IRR -7.56% to undefined) and
  `edge_extreme_stress` (-12.77% to undefined): their equity never receives a positive
  distribution once the shortfalls are cured, so no rate solves their cash flows. The
  others: the Blue Whale hybrid (6.38% to 6.05%), wind (9.06% to 8.63%) and solar + BESS
  (-3.58% to -8.32%) screening cases, `ceb_solar_bess_nightpeak_10mw` (9.79% to 9.29%),
  `ceb_bess_10mw_capacity_charge` (-10.52% to -12.41%), `dutchbay_basecase_2025Q4` (-2.90%
  to -3.14%) and the eight NSO250 long-term-loan variants (0.1 to 0.4 points lower). In 11
  of the 16 the only shortfall year is year 1, where the debt side folds in the service of
  a synthetic half-year bridge period that the equity rows receive no CFADS for; that
  asymmetry predates this change and is tracked on #1564. The `F-5` bar and #1110's `HOLD`
  are untouched.
