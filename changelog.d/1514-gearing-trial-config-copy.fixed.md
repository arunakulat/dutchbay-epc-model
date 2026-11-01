- Debt sizing no longer deep-copies the whole scenario for every trial gearing (#1514).
  Since #1451 sized debt as a fixed point, each pipeline run makes several sizing passes,
  and each pass's gearing scan copied the scenario about 130 times to change one number.
  That copy was about 70% of a lender-case run and tripled the full CI test run on
  2026-10-27. `_solve_gearing_for_dscr` and `_resize_for_amortization` now copy only the
  top-level mapping and the `Financing_Terms` section for each trial. A lender-case run
  takes 0.142 s instead of 0.437 s. No computed value changes: full results on every
  committed scenario that runs are byte-identical, and
  `tests/finance/test_gearing_trial_config_copy.py` pins each solve against the
  deep-copy recipe.
