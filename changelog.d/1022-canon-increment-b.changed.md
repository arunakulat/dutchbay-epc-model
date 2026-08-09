- **Tighten the remaining rounded/dict canonical-KPI consumers to `tests/_canon.py` (#955, Increment B)** —
  the semantic follow-up to Increment A. The unit tests that echoed the canonical
  `dutchbay_lendercase_2025Q4` economics as *rounded* pins (`0.014552`, `-79273039.21`, `1.30`) or as
  canonical-shaped dict payloads now import the named `tests/_canon.py` constants instead of repeating a
  literal, so a re-baseline updates one file: `test_curtailment_risk.py` (`project_irr`, `project_npv`,
  `min_dscr`, `min_dscr_period`), the two `test_default_off_preserves_canonical` base-canon guards
  `test_dsra_fund_at_close.py` and `test_debt_bind_p90.py` (`project_irr`, `equity_irr`, `min_dscr`),
  `test_grid_outage.py` (`project_npv`), `test_fx_integration_coverage.py`,
  `test_sens_dscr_coverage.py` and `test_wht_on_interest_cash_cost.py` (`min_dscr_period`), and
  `test_grid_screening_report_emit.py`'s `_STUB_KPIS` byte-identity yardstick (`project_irr`,
  `equity_irr`, `min_dscr`). Every migrated site is a faithful canon echo: the named constant equals the
  literal it replaces within each assertion's own tolerance, so no asserted value changes and the
  canonical oracle passes unchanged. Deliberately left as literals: coincidental `1.30`s that are *not*
  the canon `min_dscr_period` (config `dscr_floor`, DSCR-series fixture data, the deliberately-non-canon
  `test_surface_contract.py` and `test_tech_comparison_emit.py` mock stubs whose `min_dscr` of `1.30`
  differs from the canon `1.2857`) — `1.30` is one ULP from the canonical `1.2999999999999998`, so
  migrating a coincidental literal would silently corrupt a fixture — and the *structural-target*
  `min_dscr_period == 1.30` / fee-variant `min_dscr ~= 1.286` assertions in the directional
  `test_import_levies.py` / `test_senior_fees.py` tests, which pin "the sculpt holds the 1.30 target"
  for a variant rather than the base-canon vector. `finance/` and `analytics/` untouched. Ref #1022.
