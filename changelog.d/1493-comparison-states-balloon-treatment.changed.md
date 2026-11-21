- The cross-technology comparison section of the lender report states, for each compared
  case, the balloon its run left at scheduled maturity and how that run resolves it
  (`refinance`, `cash_sweep` and so on, or "no balloon arises"). It also carries a caveat when
  the compared cases publish different treatments, because their figures then include the
  treatment difference, not only the technology or capex difference: equity figures most of
  all, and in some cases project IRR, project NPV and CFADS too. That holds even for a
  case left with no balloon: a treatment can change the debt itself (an `amortize` case is
  resized to leave none) (#1493,
  third clause; the first two landed with #1735). Both values are read from each run's
  published `debt_result` (`balloon_treatment`, `balloon_remaining`); nothing is recomputed.
  No KPI and no committed scenario output changes; the section is still emitted only when a
  run opts in with `tech_comparison.scenarios`.
