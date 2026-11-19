- A Monte Carlo trial with no defined IRR now ranks below every defined trial in the
  Monte Carlo summary and the lender risk table (bundle F6; #1746 step 2, owner ruling
  2026-11-15). A percentile that falls on those trials is reported as undefined, at or
  below the lowest defined IRR, rather than as a number taken from the defined trials
  only. Upper percentiles are read from the same ranking and move down a little; the
  mean and standard deviation stay over the defined trials and say so; the IRR minimum
  is undefined and `min_defined` keeps the lowest defined value. A run whose trials all
  have a defined IRR is unchanged. API contract 2.4 (additive, `engine_result` only).
  The capital-risk report keeps the step 1 coverage disclosure.
