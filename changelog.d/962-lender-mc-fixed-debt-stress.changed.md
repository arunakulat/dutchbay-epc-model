- The lender case's Monte Carlo now runs fixed-debt stress (#962 item 4, owner ruling
  2026-11-15). `scenarios/dutchbay_lendercase_2025Q4.yaml` declares
  `monte_carlo.fixed_debt_stress: true`, so each trial's CFADS is also tested against the debt
  service committed at financial close, not only against debt re-sized for that trial. The
  result is internal model metadata, written only to the run's `metadata.fixed_debt_stress`.
  No report, KPI or summary reads it, and no summary or trial value changes. The one other
  metadata change is that `metadata.var_cvar` no longer lists `wacc_is_real`, a boolean flag
  with no meaningful VaR, because the stress path evaluates full results.
- What the diagnostic measures: the minimum, over the periods with committed debt service, of
  trial CFADS divided by that period's committed service, on an unfolded per-period basis. It
  is not the covenant basis. The covenant test folds the bridge period's service into
  operating year 1, and the deterministic minimum DSCR comes from the balloon test; the stress
  applies neither. At the base case the stress minimum sits exactly at the 1.30x covenant,
  because debt is sculpted to leave no headroom in 13 operating years, so any trial with a
  CFADS shortfall in one of those years shows as a breach. Bringing the stress onto the
  covenant basis is a separate engine change (#1728). Under F-5 the diagnostic supports no
  covenant, lender or IC representation.
- The fixed-debt test fixture's "off" case now sets the stress off explicitly, since the lender
  case turns it on. A new test pins that turning the stress on leaves the lender case's Monte
  Carlo summary and trials unchanged.
