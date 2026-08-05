- **Downside debt sizing uses the ACTIVE assessment's P90/P50 (#996 D5)** — on the async
  location-assessment path, the finance scenario is seeded from a lender-case base whose frozen
  `expected_results.net_aep_p50/p90_gwh` are unrelated to this run's assessment. A new
  `app.jobs.runner.apply_active_resource_basis` injects the freshly-assessed P50/P90 net AEP (from
  the D4-wire `ResourceAssessment`) into the assessed scenario's `expected_results`, so when the
  case binds the downside (`Financing_Terms.bind_downside`), `finance.debt_v14._resolve_downside_ratio`
  sizes the P90 gearing off the LIVE P90/P50 ratio rather than the stale committed base. Wired into
  both screening paths — `run_wind_job` and the analysis path's `_build_assessed_scenario`. Injection,
  not deletion: all other `expected_results` keys are preserved (stripping the block wholesale is the
  known regression). Byte-neutral for non-binding cases — on the screening path the only runtime reader
  of these keys is `_resolve_downside_ratio` under `bind_downside` (the bankable reconciliation is
  skipped for screening), so the canonical wind-only lender case (which does not bind downside) is
  unchanged; `test_canonical_lendercase_economics_unchanged` passes. `finance/` and `analytics/`
  untouched. Ref #996.
