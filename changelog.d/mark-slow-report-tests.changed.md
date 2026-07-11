- **Marked the slow report end-to-end tests.** The five report-rendering e2e tests in
  `tests/app/test_api.py` and `tests/integration/test_lender_report_e2e.py` (which dominate
  suite wall-time, ~184s / ~38%) now carry `@pytest.mark.slow`, so `pytest -m "not slow"`
  deselects them during local iteration. The coverage-gated full suite still runs them (no
  CI lane or make target uses `-m "not slow"`), so coverage and the 95% floor are unaffected.
