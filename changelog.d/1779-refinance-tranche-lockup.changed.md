- The distribution lock-up now also tests a refinanced balloon tranche (#1779, bundling plan
  F9). Balloon service sits outside the scheduled DSCR (#1396), so a year that services only
  the refinanced tranche had no scheduled DSCR, was never locked, and paid equity while the
  tranche's own coverage was below the covenant; the sponsor was then called for cash in the
  years after. Each year the tranche is serviced, its published coverage
  (`debt_result.refinance.coverage_by_period`) is now tested against the scenario's lock-up
  threshold (`equity_distribution.min_dscr_threshold`, else `constraints.min_dscr_covenant`),
  with the tolerance the scheduled test uses. A year below it traps its distribution. On a
  refinance, as on a cash sweep, a later shortfall is met from lockup-trapped cash and then
  retentions before any sponsor cash call, and what is left is released by the usual cure:
  the next year that is not locked. Each equity row publishes `refinance_coverage` and
  `refinance_tranche_locked`.
- **Equity KPIs move on the two capex variants**:
  `dutchbay_capex_sinohydro_lean_2025Q4` (years 15 to 17 locked; equity IRR -6.36% to -6.25%,
  equity NPV USD -77.05M to -77.09M, equity multiple 0.431x to 0.433x, total distributed
  USD 38.43M to 38.61M) and `dutchbay_capex_eia_prudent_2025Q4` (years 16 and 17 locked;
  equity IRR -9.25% to -9.21%, equity NPV USD -144.07M to -144.09M). The lender case now
  reports its three refinance years as locked (`equity_covenant_locked_years` 1 to 4), but no
  cash is trapped there, so its distributions and every other KPI are unchanged. Project IRR,
  DSCR, the debt result and every other committed scenario are unchanged. Released as
  15.31.0.
