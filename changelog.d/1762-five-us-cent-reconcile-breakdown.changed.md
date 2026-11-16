- The 5 US-cent fixed-LKR lender variant's Monte Carlo runs its trials (#1762, R3 half).
  `scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml` declares `reconcile_breakdown:
  pro_rata` on its `capex.usd_total` sweep, so each trial scales every `capex.breakdown` line
  with the sampled total: a uniform CAPEX overrun or underrun across the line items, a new
  lender-facing CAPEX-risk assumption for this variant. Before this, the pre-sampling dry
  run refused the sweep (on main, the run stopped at trial 0). The scenario's deterministic
  run does not read the key, so no deterministic KPI moves. The capital-risk report for
  this variant still fails, now on undefined IRR observations, which #1763 and #1746 own.
