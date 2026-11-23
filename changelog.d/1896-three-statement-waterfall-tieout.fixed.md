- **Reconcile three-statement cash flow and balance sheet to the equity waterfall**
  (`#1896`, `#924` study O-1). Previously, `analytics.three_statement` swept 100% of
  post-debt free cash to equity with no DSRA reserve, no covenant lock-up, no risk-haircut
  or dividend/interest WHT alignment, and unlevered tax — causing Year 1 over-distributions
  and negative closing cash during refinance / cash-sweep years while the balance sheet
  still balanced on the equity plug.
  - `build_three_statement_from_run` now resolves the equity-facing (levered-tax) rows and
    equity waterfall schedule (`finance.equity_distribution_v14_hydra`), seeds `opening_cash`
    when `Financing_Terms.dsra.fund_at_close` is set, and reconciles distributions, dividend
    withholding tax, DSRA reserve balances/movements, lock-up/retention cash, and closing
    cash period by period across all runnable scenarios.
  - `TieOutStatus` adds `waterfall_reconciles` and `max_abs_waterfall_residual` (included in
    `all_pass`), and `verify_three_statement_waterfall_tieout` asserts period-by-period
    equality and non-negative closing cash.
  - Report three-statement tables (`Financial Statements (USD)`) now match the equity
    waterfall; zero deterministic KPIs move.
