- Resolve the lender case's scheduled-maturity balloon by refinance instead of cash sweep
  (#1396 part B, audit P3-COV-03, owner decision 1A). Since #1397 the structural balloon
  is USD 28.63m. Cash sweep retired USD 18.83m of it and left USD 9.80m unpaid at project
  end. `scenarios/dutchbay_lendercase_2025Q4.yaml` now sets `balloon_treatment: refinance`
  on the YAML terms `constraints.refinancing` (3 years, +2% over the average debt rate,
  12.18%), and raises `max_refinance_pct` from 0.10 to 0.50 so the cap admits the ~39%
  balloon. Both are ASSUMPTIONS with no term-sheet basis, and `max_refinance_pct` is not
  read by any engine code yet.
- **The refinanced tranche is not serviceable on these terms.** Its service is USD 11.96m
  a year against USD 3.29-4.09m of cash available, so coverage is 0.28-0.34x against the
  1.30 floor, and `debt_result.refinance.coverage_breach` is `true`. Equity funds the
  shortfall of about USD 24.8m. Owner F-5 boundary call (2026-10-28, option A): the
  block stays in the engine output, annual, labelled `assumption_no_term_sheet`, and
  supports no covenant, lender or IC representation until the within-year event
  calendar (#1395) and real refinance terms land. It shows these terms do not work. The
  lender report does not show the block yet; surfacing it there with that caveat is
  #1491.
- Canon re-baseline (15.8.0): equity IRR -9.99% -> -30.54%, equity NPV -USD 93.09m ->
  -USD 95.64m. Project IRR, project NPV, `min_dscr`, LLCR, PLCR and total CFADS are
  unchanged, because balloon resolution sits below CFADS and outside scheduled service.
- **One directional pin no longer holds, and is replaced rather than hidden.** With the
  full import-levy stack paid, equity NPV falls (-USD 95.6m -> -USD 125.8m) but equity IRR
  rises slightly (-30.54% -> -30.12%). The balloon is almost unchanged (USD 28.61m vs
  28.63m): at a ~-30% rate the equity injections in operating years 17-19 dominate the
  IRR, so it no longer ranks outcomes (#1456). The test now asserts that equity NPV
  falls. With interest deductibility off, the equity gap widens to +537bps, because the
  smaller facility leaves a larger balloon (USD 31.55m) to refinance.
- **Two optimiser tests now optimise equity NPV instead of equity IRR.** Under the
  refinance canon the late equity injections dominate a ~-30% IRR: maximising equity IRR
  picks the dearest debt mix (60% LKR, no DFI), and it is non-monotone in contingency.
  Equity NPV keeps the correct ordering (cheap DFI first, contingency strictly costly).
  The analytical finding is #1456. The tornado crash this exposes on an assessed
  low-wind case is fixed separately under #1457, which lands first.
