- **Recomputed P90 downside beside the CFADS-ratio method (#1836)**:
  `analytics/finance/p90_recomputed_downside.py` re-runs every scenario with an
  `expected_results` P50/P90 pair at P90 energy (fixed opex, tax and waterfall recomputed by
  the engine) and sets it, and the ratio method, against the base case's committed debt.
  Minimum and average annual DSCR, LLCR and the difference are in
  `docs/finance/p90_recomputed_downside_summary.json` (Hydra CLI
  `scripts/run_p90_recomputed_downside_v14.py`). The per-row fixed-debt coverage moved,
  unchanged, from the Monte Carlo engine to `analytics/mc/fixed_debt_coverage.py`. No sizing,
  input or KPI change.
