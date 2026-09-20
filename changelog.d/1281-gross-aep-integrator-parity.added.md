- Pin the agreement between the two analytic gross-AEP integrators. WIND-3 recorded that
  `analytics.wind.aep_tornado.gross_aep_farm_gwh` (the production path) and
  `wind_resource.bankable_aep.gross_aep_weibull` (no production caller) "were verified to
  agree to < 0.1%", but nothing executed the comparison — and the second integrator's whole
  value is being an independently written oracle for the first, which an unchecked oracle is
  not. `tests/analytics/test_gross_aep_integrator_parity.py` now pins the agreement at 0.05%
  across every curve in the store and a sweep of the plausible site resource range. Also
  states in both modules which one the lender path actually calls, so a reviewer looking for
  the live gross-AEP maths is not sent to the module whose name implies it.
