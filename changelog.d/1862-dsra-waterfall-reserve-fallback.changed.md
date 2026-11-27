- Equity waterfall reserve months now fall back to the declared DSRA months (#1862 DOM-1,
  #1429 E01):
  - `finance.equity_distribution_v14_hydra.resolve_equity_min_reserve_months` resolves
    `<equity_section>.min_reserve_months` (case-insensitive key) and, when absent, falls
    back to `finance.debt_v14.resolve_dsra_target_months` with no 6-month code default.
  - Both paths are bounded to `[0, 24]` and refuse null, boolean, non-numeric, non-finite,
    or out-of-range values naming the exact YAML path in both `_build_distribution_config`
    and `analytics.schema_guard` strict pre-flight.
  - `equity_distribution.equity_summary.min_reserve_months_source` now records the
    declared DSRA key (e.g. `Financing_Terms.reserves.dsra_months`) when
    `min_reserve_months` is not explicitly authored under the equity section.
- No committed scenario figure moves: every committed scenario declares 6 DSRA months.
