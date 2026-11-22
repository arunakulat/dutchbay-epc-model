- **Recomputed P90 downside beside each scenario's sizing downside (#1836)**:
  `analytics/finance/p90_recomputed_downside.py` re-runs every scenario with an
  `expected_results` P50/P90 pair at P90 energy (fixed opex, tax and waterfall recomputed by
  the engine) and sets it against the base case's committed debt, beside two CFADS-scaling
  approximations: the downside factor the scenario's own sizing used (read from the
  engine's `dual_dscr` detail: P90/P50 only where `bind_downside` is set, otherwise the flat
  `dscr_p99_downside_factor`, which does not bind the gearing) and the P90/P50 ratio.
  Minimum and average annual DSCR, LLCR and the differences are in
  `docs/finance/p90_recomputed_downside_summary.json` (Hydra CLI
  `scripts/run_p90_recomputed_downside_v14.py`). Against the flat 0.80 factor the
  recomputed P90 is milder on some scenarios and harsher on others; the summary reports
  each. The per-row fixed-debt coverage moved, unchanged, from the Monte Carlo engine to
  `analytics/mc/fixed_debt_coverage.py`. No sizing, input or KPI change.
