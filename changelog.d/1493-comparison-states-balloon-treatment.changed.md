- The cross-technology comparison section of the lender report states, for each compared
  case, the balloon its run left at scheduled maturity and how that run resolves it
  (`refinance`, `cash_sweep` and so on, or "no balloon arises"). It also carries a caveat when
  the cases that carry a balloon resolve it in different ways, because their equity figures
  then include the treatment difference, not only the technology or capex difference (#1493,
  third clause; the first two landed with #1735). Both values are read from each run's
  published `debt_result` (`balloon_treatment`, `balloon_remaining`); nothing is recomputed.
  No KPI and no committed scenario output changes; the section is still emitted only when a
  run opts in with `tech_comparison.scenarios`.
