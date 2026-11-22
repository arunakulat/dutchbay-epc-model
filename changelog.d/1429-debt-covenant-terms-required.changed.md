- The balloon limit and the DSRA target months have no code default (#1429, inventory
  groups D09 and D08; owner decision 2026-11-14). The debt engine used to fill an absent
  `constraints.max_balloon_pct` with 10% and absent DSRA months with 6, both Dutch Bay
  figures. Strict pre-flight (`validate_config_for_v14` with the `debt` module) now refuses
  a scenario that omits either, naming its YAML path, through
  `finance.debt_v14.resolve_max_balloon_pct` and `resolve_dsra_target_months`, and
  `plan_debt` refuses again where it reads them. A declared value that is null, a YAML
  boolean or not a finite number is refused rather than replaced. Both are project terms,
  not statutory values.
- The DSRA months keep their precedence under `Financing_Terms` (`dsra.target_months`, then
  `dsra_months`, then `reserves.dsra_months`), and are now read from the section the debt
  layer reads its other terms from: a scenario on the simple `financing:` or `debt:` schema,
  or with its terms at the top level, declares `dsra_months` there. Before, only
  `Financing_Terms` was read, so such a scenario always got 6 months.
- The owner's #920 ruling stands: 6 months stays a labelled assumption until a term sheet
  sets it. The figure is now the scenario's, published with its YAML path in
  `dsra_target_source` and labelled `assumption_no_term_sheet`; the funding months are no
  longer labelled `code_default`. The equity waterfall's `min_reserve_months` keeps its own
  fallback and label for now (inventory group E01).
- The covenant snapshot prints the limit the engine published with a balloon breach,
  instead of falling back to 10%.
- No figure moves. The 28 committed engine scenarios that already declared both terms give
  byte-identical KPIs, rows, debt and equity results. Five committed scenarios that leaned
  on the fallbacks (`example_a`, `example_b`, `good_unit_test`, `test/base_scenario` and
  `test_base_scenario`) now declare the values they were given, 10% and 6 months: their
  KPIs, rows and equity are byte-identical, and the only change in their debt result is
  `funding.dsra_target_source`, now the YAML path instead of `code_default`. Test fixtures that
  leaned on them do the same, and the D3C success digest is re-pinned because its fixture
  now declares both keys (main's engine gives the same digest with that fixture).
