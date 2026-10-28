- **#1457: a tornado survives an undefined KPI at a driver point.**
  `analytics/sensitivity/engine.py` raised `KeyError` when the swept metric was missing
  from an evaluation, which is how the KPI surface reports an equity IRR with no solving
  rate (#1436). One such point ended the whole tornado and failed the web `/analysis`
  job; the 22.8% assessed lender case with its balloon refinanced (#1396 part B) has no
  equity IRR at the base or at 17 of 21 driver points. The sweep now records a point
  whose metric arrives undefined (`None`, missing or non-finite) as `nan`, never 0.0,
  and logs the metric, the driver case and the value it took, as the optimiser already
  did (#782). Each affected tornado lists its `metadata['undefined_cases']`; the suite
  carries `undefined_base`, `undefined_points` and `undefined_drivers`, and
  `flat_metric` judges only the defined bars. A metric undefined at every evaluation
  (the signature of a mistyped key) raises `ValueError` in strict mode. Over JSON the
  undefined values travel as `null`, and the lender report's tornado shows them as
  absent. The disclosure sees only the absent-key path: a 0.0 the KPI surface
  substitutes upstream (`analytics/core/metrics.py:494` for an unsolvable project IRR,
  `:466` for an equity IRR with no equity-distribution result) is recorded as defined,
  so `undefined_points: 0` does not show that every point solved. A sweep whose metric
  is defined everywhere is unchanged, and no KPI or canon figure moves.
