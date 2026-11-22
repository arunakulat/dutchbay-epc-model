- The lender report discloses the recomputed P90 cover of the committed debt (#1895). Its
  debt table prints the recomputed P90 case's minimum and average annual DSCR and LLCR
  (#1836) beside the P90/P50 ratio method. On `main` the lender case covers 1.06x, not the
  1.14x to 1.17x in the issue text. A scenario with no P50/P90 pair lists the rows under
  "Sections not run".
- An opt-in `Financing_Terms.p90_cover_min_dscr` sizes the debt against the recomputed P90
  case as well as P50. When a scenario declares it and the recomputed P90 case does not
  cover the committed debt at that minimum annual DSCR, the P50 sizing target is raised to
  the smallest value at which it does.
  - The run's debt result then carries a `p90_cover` block with the declared cover,
    whether it bound, the target it set and the recomputed P90 minimum DSCR before and
    after. The report prints it.
  - The term needs an `expected_results` P50/P90 pair and a DSCR sizing mode.
  - Strict pre-flight and the pipeline refuse a value below 1, a non-number, or a scenario
    that has no pair, naming the path.
  - It has no default. No committed scenario declares it, so no figure moves.
- Owner ruling on #1895 (option A, 22 Nov 2026): keep the 1.30x P50 sizing, disclose the
  recomputed P90 cover, and add the opt-in term.
