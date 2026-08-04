- **Lender-case financial-KPI oracle extracted to a golden fixture (#996 D3)** — the canonical
  `scenarios/dutchbay_lendercase_2025Q4.yaml` no longer carries its own financial-KPI regression
  targets (`project_irr`, `equity_irr`, `project_npv_m_usd`, `min_dscr`, `avg_dscr`, `llcr`,
  `plcr`) inside `expected_results`, so a runtime-input scenario no longer doubles as its own
  regression oracle. Those numbers move to a test-only golden fixture
  (`tests/fixtures/finance/lendercase_expected_kpis.json`), and
  `tests/finance/test_lendercase_expected_results.py` reads them from there at the same
  tolerances. The scenario keeps exactly the values the engine and the reconciliation guard read
  at runtime — `net_aep_p50_gwh` / `net_aep_p90_gwh` (AEP reconciliation + downside-debt ratio)
  and `capacity_factor` — and a new `test_lendercase_scenario_retains_aep_inputs` locks that split
  in (moving `net_aep` would flip the downside ratio to the flat fallback and disarm the guard).
  The re-baseline provenance narrative stays in the scenario as documentation. `finance/` and
  `analytics/` untouched; the canonical KPI vector is byte-identical (verified against
  `test_multitech_generation.py::test_canonical_lendercase_economics_unchanged`). Ref #996.
