- The four scenarios that describe themselves as sharing the lender case's debt stack now
  resolve the scheduled-maturity balloon the same way the lender case does (#1493, after
  #1396 / #1492). `dutchbay_capex_eia_prudent_2025Q4`, `dutchbay_capex_sinohydro_lean_2025Q4`,
  `dutchbay_hybrid_bess_2025Q4` and `dutchbay_hybrid_windsolar_2025Q4` move from
  `balloon_treatment: cash_sweep` to `refinance`, on the lender case's assumed
  `constraints.refinancing` terms (3 years, +2% over the average debt rate, and
  `max_refinance_pct` 0.50, which no engine code reads yet). The terms are ASSUMPTIONS with
  no term-sheet basis. A capex or technology comparison against the canon no longer mixes in
  a balloon-treatment difference. It still mixes in a fee difference: the lender case carries
  1.75% a year of senior credit-support fees (guarantee and political-risk insurance), and
  these four carry none.
- The two capex variants carry a balloon (12.6% and 16.4% of debt), so their equity figures
  move. Equity IRR: EIA prudent -9.09% -> -9.25%, Sinohydro lean -6.26% -> -6.36%. Equity NPV
  falls by about USD 0.01m and USD 0.06m. MOIC moves 0.265 -> 0.262 and 0.436 -> 0.431, and
  cash-on-cash 1.32% -> 1.31% and 2.18% -> 2.16%. Total equity distributed falls by about
  USD 0.44m in each.
- Sinohydro lean now needs sponsor cash in two years. Its refinanced tranche's coverage is
  1.02x, 0.92x and 0.82x, so in years 16 and 17 project cash does not cover the annuity, and
  equity pays in USD 0.36m and USD 0.84m (USD 1.20m). The engine books these calls as negative
  distributions, so `equity_sponsor_cure_usd` and `equity_debt_service_shortfall_years` stay 0
  and do not show them. Total equity distributed (USD 38.43m) is net of the calls; gross
  distributions are USD 39.63m. The equity cash flows now change sign three times, so the
  engine marks the -6.36% equity IRR as unreliable for ranking (`equity_irr_ranks_reliably`
  false, #1456): rank on equity NPV. EIA prudent has no call (coverage 1.33x, 1.20x, 1.08x).
- LLCR and PLCR rise by less than 0.001 because levered CFADS rises. The levered tax pass
  deducts balloon interest when it is paid (#1505), and the refinance pays more interest than
  the sweep did (the premium of 2%), so post-tax CFADS in the refinance years rises by about
  27% of the extra interest. The ratios divide by a fixed opening principal, so only the
  numerator moves. The same CFADS feeds the dual-DSCR capacity detail
  (`dual_dscr.debt_sized` rises by about USD 11k and USD 15k); the facility, the solved
  gearing and the balloon do not move.
- Project IRR and project NPV are unlevered, so they do not move. `min_dscr` does not move,
  because no in-tenor period changes, and `balloon_pct` is fixed by the sculpt before the
  treatment applies. The refinanced tranche breaches the scenario's 1.30 covenant in both
  capex variants (minimum coverage 1.08x and 0.82x). Under F-5 that block supports no
  covenant, lender or IC representation.
- The two hybrids fully amortise under P90-bound sizing (balloon 0%), so the change moves
  none of their figures.
- The capex variants' balloon comments said "~55%" and "~58%"; they now give the current
  12.6% and 16.4%.
