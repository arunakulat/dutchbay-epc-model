- The cross-technology comparison section of the lender report states, for each compared
  case, the balloon its run left at scheduled maturity and how that run resolves it
  (`refinance`, `cash_sweep` and so on, or "no balloon arises"). It also carries a caveat when
  the treatments that act on the compared cases differ, because their figures then include the
  treatment difference, not only the technology or capex difference: equity figures most of
  all, and in some cases project IRR, project NPV and CFADS too. A treatment counts where it
  can act: on a case that carries a balloon, and always for `amortize`, which resizes the debt
  to leave none. A case left with no balloon under a treatment that acts only on a balloon is
  like for like and raises no caveat (#1493, third clause; the first two landed with #1735). Both values are read from each run's
  published `debt_result` (`balloon_treatment`, `balloon_remaining`); nothing is recomputed.
  No KPI and no committed scenario output changes; the section is still emitted only when a
  run opts in with `tech_comparison.scenarios`.
