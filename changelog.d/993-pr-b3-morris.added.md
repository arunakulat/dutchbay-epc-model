- **Async analysis jobs — Morris global sensitivity (#993 PR-B3)** — `POST /v1/jobs/analysis`
  gains `analysis_type='morris'`: a bounded Morris elementary-effects global-SA screening
  (mu_star / sigma ranking) over the freshly-ASSESSED screening case, reusing the same job
  lifecycle and screening seam as the MC and tornado paths (Dolphin). Drivers are the
  scenario's `monte_carlo.parameters`, so — like `mc` — the request boundary requires a
  non-empty list-form block (CESSPIT); `n_trajectories` is bounded 4–64. The sweep runs
  fully IN-MEMORY: the SALib problem is built from the in-memory drivers
  (`build_problem(params=...)`) and evaluated via a `raw_config` evaluator, which is the
  crucial correctness point — a path-based `run_morris(config_path)` writes the screening
  scenario to a temp file and `load_scenario_config` then trips the frozen-bankable
  `AepReconciliationError` on the fresh capacity factor (#996). The in-memory drive bypasses
  that entirely while still honouring #993 (the live CF, not the stale form input). The
  engine's native dict (per-driver mu_star/sigma, ranking, and the `flat_metric` /
  `nan_poisoned` / `masked` disclosures) is carried verbatim in the `AnalysisResult`
  envelope. SALib is a declared dependency; the real-engine test skips cleanly where it is
  absent (`importorskip`). Additive: `morris` is a new value on the existing envelope, so no
  API contract bump; `finance/` and `analytics/` are untouched and the canonical KPIs stay
  byte-identical. Ref #788.
