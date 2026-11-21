- Monte Carlo IRR statistics say how many trials they leave out, and the capital-risk
  report shows each IRR metric with that coverage instead of refusing (bundle F5; #1763,
  #1746 step 1). A trial whose cash flow changes sign more than once has no unique IRR.
  Each IRR statistic is taken over its defined trials, as before, and no figure changes
  for a run in which every trial has a defined IRR.
  - Summary (`analytics/mc/aggregate.py`): every metric's summary gains `defined_count`
    and `excluded_count`. An IRR that excludes trials gains `coverage_note`, also listed
    under `metadata.irr_coverage_notes`, and a warning is logged. `MonteCarloResult`
    gains `project_irr_excluded_count`.
  - Lender risk table (`analytics/mc/exports.py`): an IRR row that excludes trials gains a
    `coverage_note` column; CASPER's JSON conversion carries it as text.
  - Capital-risk report (`analytics/capital_risk_layer_v14.py`): built when only IRR
    observations are incomplete (owner ruling 2026-11-16, "Report with coverage"). Each
    IRR metric's VaR/CVaR, mean, percentiles and the probability below the equity hurdle
    are over its defined trials, recorded in `CapitalRiskReport.irr_coverage`. NPV, DSCR,
    LLCR and PLCR keep the complete-cohort refusal, and an IRR with fewer than 20 defined
    trials is still refused.
  - Report, web and API: the note is stated before the capital-risk figures, each return
    metric shows its defined-of-total trials, and the hurdle probability states its trial
    count. API contract 2.3 (additive): `CapitalRiskMetric` gains `defined_count`,
    `total_count` and `coverage_note`; `CapitalRiskSurface` gains `irr_coverage_notes`
    and `hurdle_defined_count`.
  - The ranking of undefined-IRR trials (#1746 step 2) is a separate R3 change.
