- **Async analysis jobs — Monte Carlo (#993 PR-B1)** — a new `POST /v1/jobs/analysis`
  runs a bounded analysis engine off the request path over the freshly-ASSESSED
  screening case, reusing the existing job lifecycle wholesale (store, `JobRecord`,
  owner isolation, the `GET /v1/jobs/{id}` status + SSE routes; Dolphin — no duplicated
  lifecycle). PR-B1 wires the canonical Monte-Carlo engine (`analysis_type='mc'`,
  200–20000 trials); `tornado` and `morris` follow. The job honours #993: it recomputes
  the active assessed case (the live capacity factor, never the stale form input) via the
  same `RunMode.SCREENING` overwrite/physical-only seam the finance path uses, then runs
  the engine on that scenario — so the risk analytics are screening-grade, never a
  bankable re-pin. Fail-loud at the request boundary (CESSPIT): the job requires
  `wind.resource_mode='weibull'` (deterministic, network-free, bounded) and a variant
  whose resolved scenario carries a list-form `monte_carlo.parameters` block
  (`lendercase`); the `redis` backend returns 501 until its arq task lands. The MC driver
  bands remain the committed lender-authored envelope; divergence from the fresh base is
  surfaced honestly in `metadata['base_outside_bounds']`, not silently re-centred.
  Additive: the public API contract bumps 1.1 → 1.2 (a new `AnalysisResult` envelope; no
  existing model changed). `finance/` and `analytics/` are untouched and the canonical
  KPIs stay byte-identical. Ref #788.
