- The DSRA target is now published as an assumption, with the key it came from (#920, owner
  ruling 2026-11-15: keep the reserve at 6 months of debt service as a labelled assumption until
  a term sheet sets it). `debt_result["funding"]` carries `dsra_target_basis`
  (`assumption_no_term_sheet`, the same label the refinanced tranche's terms carry) and
  `dsra_target_source`: the YAML path the months were read from, or `code_default` when a
  scenario authors none and the engine's 6-month fallback applies. No figure moves: all 33
  scenarios that run on `main` give identical KPIs, debt and equity results apart from the two
  new keys. 28 read `Financing_Terms.reserves.dsra_months`; 5 use the code default.
