- Scenarios can declare four optional blocks for the site analyses (#1754, U1 of the owner's
  2026-11-16 ruling that every scenario includes them): `storage_options` (wind battery
  options), `solar_storage_sizing` (PV + BESS sizing), `financing_screening` (FX and tenor
  screening) and `equipment_cost_parity`. Each holds what is site-specific (location, sizes,
  technology, tariff inputs and file references) under a shared envelope of site, retrieval
  date and sources. `analytics/site_analysis_blocks.py` defines the contracts, and the
  pre-flight schema guard checks a block only when a scenario declares it: unknown keys,
  wrong types, out-of-range values and missing files fail loud, naming the path. Every
  analysis is on by default (owner ruling 2026-11-16): `plan_site_analyses()` lists all
  four for any scenario, planning to run each one whose block is declared and listing the
  rest as `not_applicable` with the reason. No
  scenario declares a block yet and no analysis reads one yet, so nothing changes for any
  committed scenario: no engine, scenario or KPI figure moves. The F-5 hold applies.
