- Report an unresolved project IRR as undefined rather than 0.0 (#1494). When no rate in
  `finance/irr.py`'s search range solves the project cashflows, `calculate_scenario_kpis`
  logged "Project IRR undefined" and then let its stable-surface default write
  `project_irr = irr = 0.0`, which reads as a genuine break-even. `kpis.project_irr` and
  the `irr` alias are now `None` in that case, and the new `kpis.project_irr_status` says
  which statement the value makes: `computed`, `undefined`, or `not_computed` (no CFADS or
  capex to solve with, where the 0.0 placeholder is unchanged). `ScenarioResult.project_irr`
  is retyped to `float | None`. The pipeline's log lines print "undefined" instead of
  raising; the report verdict says the project IRR is undefined; the cost-of-equity sweep
  carries `None`; and the capex Monte Carlo and the capex-for-IRR-floor solver refuse with
  a message naming the capex, where they used to take 0.0 or raise a bare `KeyError`. On
  the API, `POST /v1/run-pipeline` gains `kpis.project_irr_status` and both it and
  `CaseResult.kpis` carry such an IRR as `null`; the public contract version moves from
  2.0 to **2.1** (MINOR, additive). The numeric KPI surface from `evaluate_with_overrides`
  still drops a `None` KPI, so an undefined project IRR is absent there, as an undefined
  equity IRR already was. The equity-waterfall 0.0 sentinel is unchanged.
  - KPI change, one committed scenario: `blue_whale_solar_bess_lot5b_2026` reported
    `project_irr = 0.0`; it now reports it as undefined (`None`). Its CFADS turn negative
    after the 15-year priority term, so its project NPV changes sign twice, near -19.2% and
    -1.7%, and the solver resolves no single rate. Its CFADS sum is below its capex, so its
    NPV is negative at every non-negative rate. Every other committed scenario's full
    result is unchanged apart from the new status key.
- Stop `approx_project_irr` returning no answer for a large project with a single root
  (#1494). Its `tol` is an absolute NPV tolerance of 1e-6 USD. On a large project the NPV is
  steep enough near the root that 50 bisection halvings pin the rate to about 1e-15 while
  |NPV| stays above 1e-6 USD, so the solver returned `None`. One example is the lender case
  with capex at USD 400m or 500m, whose true IRRs are about -7.8% and -9.4%. The solver
  now accepts the midpoint once the sign-change bracket is narrower than 1e-10 in rate.
  That check runs only after `max_iter` is exhausted, so every rate the solver already
  found is byte-identical, and an unconverged wide bracket still returns `None` (FIN-10).
  Cashflows whose NPV changes sign more than once (CFADS that turn negative late in life)
  still return `None`, and are now reported as undefined.
