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
  equity IRR already was. The equity-waterfall 0.0 sentinel is unchanged. Every committed
  scenario has a defined project IRR, so no committed KPI value moves.
