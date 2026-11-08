- Require `returns.project_discount_rate` in every v14 scenario and remove the hard-coded
  `DEFAULT_DISCOUNT_RATE = 0.10` (#1429). The pipeline now discounts at the declared rate
  whenever `wacc.drives_discount_rate` is not set, and falls back to it, rather than to
  0.10, when a driving WACC resolves no `wacc_nominal`. One resolver serves pre-flight and
  the KPI pass. A missing, null, boolean, non-numeric, non-finite or out-of-range
  (outside `[0, 1)`) value fails at pre-flight wherever the `cashflow` module is
  validated (every pipeline run), naming the path. `calculate_scenario_kpis`
  no longer assumes a rate: a caller passes one or a config that declares one.
  `scenarios/edge_extreme_stress.yaml` declared 0.12 but was discounted at 0.10. It is
  now discounted at 0.12, so its project NPV moves from USD -110.99m to -119.80m; its
  equity IRR is unchanged. Five scenarios that declared no rate (`example_a`,
  `example_b`, `good_unit_test`, `test_base_scenario` and `test/base_scenario`) now
  declare 0.10 and do not move. Every other committed scenario is byte-identical,
  including the canonical lender case. The 12 committed scenario files that already
  failed pre-flight still fail with the same exception type; 10 of them (six top-level
  scenarios, the three `scenarios/overrides/` fragments and one scratch file) now also
  name the missing rate in the same error. Released as 15.26.0.
