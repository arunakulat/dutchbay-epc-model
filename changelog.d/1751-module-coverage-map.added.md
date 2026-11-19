- `docs/MODULE_COVERAGE_MAP.md` (#1751) lists every module in `analytics`, `finance`, `app`,
  `wind_resource` and `solar_resource` with where its results end up: the pipeline run, an
  emitter step, the lender report, the web app, only a script (or run as one), or nowhere at runtime (with
  the reason, such as "tests only"). `scripts/module_coverage_map.py` writes it from a LibCST
  import scan and keeps the hand-written notes; `tests/lint/test_module_coverage_map.py`
  fails when a module is added or removed without the map, or when a module's status or
  entry point no longer matches the imports. No engine, scenario or KPI figure changes.
