- **Battery dispatch property tests (#1838)**: Hypothesis tests for both dispatch paths
  (`analytics/wind/wind_bess_options.py` `dispatch()` and `analytics/storage_dispatch.py`)
  pin energy conservation, SOC bounds, the export cap, window rules, the reserve floor,
  monotonicity, a single RTE booking and the standby-loss exclusion. Tests only; no code,
  output or KPI change.
