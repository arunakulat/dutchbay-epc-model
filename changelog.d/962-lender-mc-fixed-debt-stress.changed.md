- The lender case's Monte Carlo now runs fixed-debt stress (#962 item 4, owner ruling
  2026-11-15). `scenarios/dutchbay_lendercase_2025Q4.yaml` declares
  `monte_carlo.fixed_debt_stress: true`, so each trial's CFADS is also tested against the debt
  service committed at financial close, not only against debt re-sized for that trial. The
  result is internal model metadata, written only to the run's `metadata.fixed_debt_stress`.
  No report, KPI or summary reads it, and no summary or trial value changes. The one other
  metadata change on a lender run with the stress on is that `metadata.var_cvar` no longer
  lists `wacc_is_real`, a boolean flag with no meaningful VaR, because the stress path
  evaluates full results.
- Web-app Monte Carlo jobs never run the stress (owner decision 2026-11-15). They are seeded
  from the lender case, but they are screening runs, and the job returns the whole metadata
  block to API clients with no basis label. `app/jobs/analysis_runner.py` therefore sends the
  engine a copy of the assessed scenario with `monte_carlo.fixed_debt_stress` set to false, so
  a web job's result is as before this change (except the config hash, which any edit to the
  scenario file moves). The stress stays on the main lender case only: the 5 US-cent variant
  and the Kalpitiya lender case do not declare it (owner decision 2026-11-15).
- What the diagnostic measures: the minimum, over the periods with committed debt service, of
  trial CFADS divided by that period's committed service, on an unfolded per-period basis. It
  is not the covenant basis. The covenant test folds the bridge period's service into
  operating year 1, which is where the deterministic case's 1.22x minimum DSCR comes from; the
  stress does not fold, so it reads that year at about 2.4x. At the base case the stress
  minimum sits exactly at the 1.30x covenant, because debt is sculpted to leave no headroom in
  operating years 2 to 14, so any trial with a CFADS shortfall in one of those 13 years shows
  as a breach. Bringing the stress onto the covenant basis is a separate engine change
  (#1728). Under F-5 the diagnostic supports no covenant, lender or IC representation.
- The fixed-debt test fixture's "off" case now sets the stress off explicitly, since the lender
  case turns it on. A new test pins that turning the stress on leaves the lender case's Monte
  Carlo summary and trials unchanged, and another that a web job sends the stress off.
