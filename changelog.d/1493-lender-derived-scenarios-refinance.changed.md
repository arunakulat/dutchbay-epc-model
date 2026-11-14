- The four scenarios that describe themselves as sharing the lender case's debt stack now
  resolve the scheduled-maturity balloon the same way the lender case does (#1493, after
  #1396 / #1492). `dutchbay_capex_eia_prudent_2025Q4`, `dutchbay_capex_sinohydro_lean_2025Q4`,
  `dutchbay_hybrid_bess_2025Q4` and `dutchbay_hybrid_windsolar_2025Q4` move from
  `balloon_treatment: cash_sweep` to `refinance`, on the lender case's assumed
  `constraints.refinancing` terms (3 years, +2% over the average debt rate, and
  `max_refinance_pct` 0.50, which no engine code reads yet). The terms are ASSUMPTIONS with
  no term-sheet basis. A capex or technology comparison against the canon no longer mixes in
  a balloon-treatment difference.
- The two capex variants carry a balloon (12.6% and 16.4% of debt), so their equity figures
  move. Equity IRR: EIA prudent -9.09% -> -9.25%, Sinohydro lean -6.26% -> -6.36%. Equity NPV
  falls by about USD 0.01m and USD 0.06m. Project IRR, project NPV and `min_dscr` are
  unchanged, because balloon resolution sits below CFADS. The refinanced tranche breaches
  the scenario's 1.30 covenant in both (minimum coverage 1.08x and 0.82x). Under F-5 that
  block supports no covenant, lender or IC representation.
- The two hybrids fully amortise under P90-bound sizing (balloon 0%), so the change moves
  none of their figures.
- The capex variants' balloon comments said "~55%" and "~58%"; they now give the current
  12.6% and 16.4%.
