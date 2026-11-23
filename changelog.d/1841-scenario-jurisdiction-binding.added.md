- Every committed scenario now binds to a registered jurisdiction pack (#1841 PR 3). A
  scenario names its jurisdiction in `project.jurisdiction`. The new registry
  `conf/jurisdiction_scenario_bindings.yaml` maps that name (`Sri Lanka`, `LK` or `LKA`, any
  case) to the Sri Lanka pack `dutchbay.jurisdiction.lk` 1.0.0, and
  `analytics/jurisdiction_packs/scenario_binding.py` turns it into one `JurisdictionBinding`
  per subject the pack covers (contract, supply, tax). A scenario with no jurisdiction or an
  unknown one is refused, with no fallback to Sri Lanka.
- Ten scenario files that had no `project.jurisdiction` now declare `Sri Lanka`, the
  jurisdiction the engine already applied to them: `contracts_edgecase_base_v14`,
  `dscr_sensitivity_example`, `dutchbay_mc_enhanced_2025Q4`, `dutchbay_sprint17_enhanced`,
  `example_a`, `example_b`, `example_fx_structured_blocks`, `good_unit_test`,
  `test/base_scenario` and `test_base_scenario`. A new test requires every scenario with a
  `project` section to bind and to resolve through the pack.
- Nothing in the engine reads the binding yet. The zero-diff scenario sweep shows no
  change to any figure.
