- Follow-ups from the review of #1860, the #1429 DSRA-months and balloon-limit slice (#1862):
  - `dsra.fund_at_close` is now read from the same financing section as the DSRA months
    (`Financing_Terms`, else `financing`, else `debt`, else the top level). On the simple
    `financing:` or `debt:` schema the flag was ignored without a message while the months
    were honoured.
  - The two required terms are range-checked. `constraints.max_balloon_pct` must lie between
    0 and 1: a limit written as a percentage (`10`) is refused, not read as 1000%, which no
    balloon would breach. The DSRA months may not be negative. Strict pre-flight and the debt
    engine refuse the same values, naming the path.
  - The lender report reads the `constraints` section as the engine does, in any case, so a
    scenario keyed `Constraints:` has its own limits tested by the report too, not the
    report's default.
  - The financing questionnaire asks for `constraints.max_balloon_pct`, now a required term
    with no default.
- No figure moves: every committed scenario declares a balloon limit of 0.10 or 0.15 and 6
  DSRA months under `Financing_Terms`.
