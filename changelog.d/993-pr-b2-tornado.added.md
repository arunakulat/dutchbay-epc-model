- **Async analysis jobs — tornado (#993 PR-B2)** — `POST /v1/jobs/analysis` gains
  `analysis_type='tornado'`: a bounded one-way sensitivity sweep over the freshly-ASSESSED
  screening case, reusing the same job lifecycle and screening seam as the Monte-Carlo path
  (Dolphin — no duplicated lifecycle or engine logic). Drivers come from the canonical default
  library (CAPEX, OPEX, capacity factor, tariff, corporate tax, debt tenor, plus incremental
  grid curtailment), skipping any key absent from the config so there are no flat bars. The
  sweep runs in-memory over the assessed dict, so it honours #993 (the live capacity factor,
  never the stale form input) and — unlike a path-based sweep — bypasses the frozen-bankable
  reconciliation on the fresh screening CF (#996). Fail-loud (CESSPIT): a request whose
  resolved scenario yields no drivers is rejected before the engine runs, and `metric` is
  restricted to the non-degenerate set (`project_irr`, `equity_irr`, `project_npv`). Additive:
  `tornado` is a new value carried by the existing `AnalysisResult` envelope, so there is no
  API contract bump; `finance/` and `analytics/` are untouched and the canonical KPIs stay
  byte-identical. Ref #788.
