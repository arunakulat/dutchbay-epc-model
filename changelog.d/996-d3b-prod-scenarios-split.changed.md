- **Extend the expected_results split to the remaining production scenarios (#996 D3b)** — applies the
  D3 pattern to the four other production scenarios whose financial-KPI `expected_results` doubled as a
  smoke-test oracle: `dutchbay_capex_sinohydro_lean_2025Q4`, `dutchbay_capex_eia_prudent_2025Q4`,
  `dutchbay_lendercase_5usc_fixed_lkr`, and `mullikulam_2x50mw_mannar`. Each scenario's financial-KPI keys
  (project/equity IRR, NPV, DSCR, LLCR, PLCR — plus equity NPV/MOIC for mullikulam) move to a test-only
  golden fixture under `tests/fixtures/finance/`, and the corresponding smoke tests
  (`test_capex_cases_smoke`, `test_kalpitiya_5usc_smoke`, `test_mullikulam_mannar_smoke`) read the fixture
  at the same tolerances. Each scenario keeps only the values the engine + reconciliation guard consume at
  runtime (`net_aep_p50/p90_gwh`, `capacity_factor`); the smoke tests now assert those runtime inputs stay
  and the financial keys are gone, locking the split. With this, no production scenario doubles as its own
  regression oracle (#996). `finance/` and `analytics/` untouched; the canonical byte-identity oracle is
  unaffected (this touches only the four variant scenarios). Ref #996.
