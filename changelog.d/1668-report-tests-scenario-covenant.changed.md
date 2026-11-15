- The lender report now tests a scenario's own covenant thresholds (#1668, owner decision
  2026-11-14: "scenario - 1.3"). The minimum-DSCR floor comes from
  `constraints.min_dscr_covenant` and the balloon ceiling from `constraints.max_balloon_pct`.
  `config/report_defaults.yaml` (1.20x and 40%) applies only to a threshold the scenario
  does not declare. The covenant table and verdict notes say which source each threshold
  came from. Where the scenario declares its covenants, the report and the engine now judge
  the same covenant (FRAMEWORK-03). Every committed Dutch Bay, Blue Whale, Kalpitiya, NSO and
  CEB case declares them. A scenario that does not keeps the labelled report defaults, while
  the engine's own fallbacks differ (follow-up below).
- **Two verdicts change.** Two cases met the 1.20x report default and now breach their
  1.30x covenant: the lender case (minimum DSCR 1.22x) and the optimistic case (1.21x). In
  both, the IC summary gains a high-severity covenant-breach flag ("Minimum DSCR ... breaches
  the lender floor"). Neither headline changes ("Value-destructive" in both). No balloon
  verdict changes, because the balloon row already followed the engine's breach flag. The
  covenant table now shows the scenario's 10% ceiling instead of 40%.
- A minimum DSCR sculpted to exactly the covenant (it reads 1.2999999999999998) is compared
  with the engine's 1e-9 lock-up tolerance (#1508), so it is "Met", not a breach. Without
  it, committed cases sized to 1.30x (at least the EIA-prudent capex variant, the hybrid
  BESS case and the Kalpitiya lender case) would have printed a false breach.
- No engine figure changes. The F-5 hold applies: no figure here supports a covenant,
  lender or IC representation.
- Follow-up: the report reads only `constraints.min_dscr_covenant`. The engine's shared
  resolver (`analytics.mc.covenant.resolve_min_dscr_covenant`) falls back through
  `Financing_Terms.target_dscr` and others, and an undeclared balloon ceiling is 10% in the
  engine but 40% in the report.
