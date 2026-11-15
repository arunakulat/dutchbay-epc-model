- The lender case's Monte Carlo now runs fixed-debt covenant stress (#962 item 4, owner ruling
  2026-11-15). `scenarios/dutchbay_lendercase_2025Q4.yaml` declares
  `monte_carlo.fixed_debt_stress: true`, so each trial's CFADS is also tested against the debt
  service committed at financial close, not only against debt re-sized for that trial (which
  pins min DSCR at the sculpt target and makes the breach probability about zero by
  construction). The result is reported only in the run's `metadata.fixed_debt_stress`; no
  report, KPI or summary reads it, and the existing Monte Carlo summary is unchanged (identical
  on 64 trials, seed 42).
- On 512 trials (seed 42) the lender case breaches its 1.30x covenant in 82.4% of trials under
  fixed debt, with a P10 / P50 / P90 minimum DSCR of 0.86x / 1.12x / 1.36x. This is consistent
  with the deterministic lender case, whose minimum DSCR already sits below 1.30x (#1668). Under
  F-5 these figures support no covenant, lender or IC representation.
- The fixed-debt test fixture's "off" case now sets the stress off explicitly, since the lender
  case turns it on.
