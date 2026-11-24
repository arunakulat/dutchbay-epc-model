- **Lender report: what-if cases and lender risk (opt-in)**: the command-line lender
  report can now surface the `#1403` non-canonical what-if cases (`analytics.what_if_cases`,
  with the `#1523` source, per-parameter provenance, and limitations preserved verbatim) for
  any scenario that matches a declared case's `base_scenario`, alongside the `FRAMEWORK-01`
  CASPER lender-risk blocks (`analytics.mc.exports.build_casper_risk_blocks`) guarded by
  `app.reports.capital_risk_emit` (`allow_toy_fallback` forced off, at least 1,000 trials,
  and zero toy-fallback trials permitted). Any part that does not apply or lacks an input is
  listed explicitly with its reason. Off by default (`lender_report.what_if_lender_risk.enabled`).
  It sits beside the committed case: no committed KPI moves (#1825 slice iv).
