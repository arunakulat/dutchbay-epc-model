- Direct tax now reads statutory parameters from the scenario's resolved jurisdiction pack
  (#1841 PR 4). When `project.jurisdiction` is declared, `finance/cashflow_v14_tax.py`,
  `finance/equity_distribution_v14_hydra.py`, and `finance/wacc_v14.py` resolve corporate
  income tax, tax-loss carry-forward years, asset-class depreciation lives, and interest /
  dividend withholding tax rates from `conf/jurisdiction_packs/lk/1.0.0.yaml` through
  `analytics/jurisdiction_packs/resolver.py`.
  - Direct tax resolves only operating-period year-end valuation dates (`YYYY-12-31`),
    excluding pre-COD construction years, with no mid-period pro-rating.
  - Conflict records (`not_run_conflict`), unsupported jurisdictions or packs
    (`not_run_unsupported_jurisdiction`), unknown jurisdictions, out-of-window valuation
    dates, and overrides without provenance fail closed.
  - Explicit runtime overrides in `analytics/evaluation_v14.py` and
    `analytics/evaluate_scenario.py`, as well as synthetic test fixtures via
    `tax.pack_overrides`, carry provenance into the resolver. Gate A zero-diff sweep
    across all 33 committed runnable scenarios shows zero KPI differences.
