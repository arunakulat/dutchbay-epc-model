- The new `tests/finance/test_gearing_warm_start_walk.py` pins the warm-started
  gearing walk's one-step boundaries (a hint one grid step above or below the answer,
  and a hint at the step floor) and the walk up to a binding `debt_ratio` cap (#1514
  follow-up to #1527, review findings A-1 and D-1). Seven walk mutants, including the
  three that survived #1527's tests, now each fail a test. Three code comments about
  the warm start are corrected. No engine behaviour changes.
