- The 5 US-cent fixed-LKR lender variant's Monte Carlo runs its trials (#1762, R3 half).
  `scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml` declares `reconcile_breakdown:
  pro_rata` on its `capex.usd_total` sweep, so each trial scales every `capex.breakdown` line
  with the sampled total: a uniform CAPEX overrun or underrun across the line items, a new
  lender-facing CAPEX-risk assumption for this variant. Before this, the pre-sampling dry
  run refused the sweep (on main, the run stopped at trial 0). The scenario's deterministic
  run does not read the key, so no deterministic KPI moves. The capital-risk report for
  this variant still fails, now on undefined IRR observations, which #1763 and #1746 own.
  The same variant's tariff sweep is re-centred on its own tariff: `tariff.lkr_per_kwh` now
  spans 16.69 LKR/kWh +/-20% (13.352 to 20.028), where it carried the canonical lender
  case's 20.3 band and so sampled almost only upside. The band was dormant until the
  trials ran. Its Monte Carlo distributions move (KPI applied under owner delegation; the
  table is on the pull request), and more trials have an undefined project IRR, which
  #1763 owns.
