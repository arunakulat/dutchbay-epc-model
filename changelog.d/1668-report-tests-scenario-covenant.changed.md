- The lender report now tests a scenario's own covenant thresholds (#1668, owner decision
  2026-11-14: "scenario - 1.3"). The minimum-DSCR floor comes from
  `constraints.min_dscr_covenant` and the balloon ceiling from `constraints.max_balloon_pct`.
  `config/report_defaults.yaml` (1.20x and 40%) applies only to a threshold the scenario
  does not declare. The covenant table and verdict notes say which source each threshold
  came from. The report and the engine now judge the same covenant, so they are one source
  of truth (FRAMEWORK-03).
- **One verdict changes.** The lender case's minimum DSCR (1.22x) met the 1.20x report
  default and now breaches its 1.30x covenant. Its headline is unchanged
  ("Value-destructive"), and its balloon row already followed the engine's breach flag.
  The covenant table now shows the 10% ceiling instead of 40%.
- A minimum DSCR sculpted to exactly the covenant (it reads 1.2999999999999998) is compared
  with the engine's 1e-9 lock-up tolerance (#1508), so it is "Met", not a breach. Without
  it, committed cases sized to 1.30x (at least the EIA-prudent capex variant, the hybrid
  BESS case and the Kalpitiya lender case) would have printed a false breach.
- No engine figure changes. The F-5 hold applies: no figure here supports a covenant,
  lender or IC representation.
