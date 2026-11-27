- Canonical CFADS completeness and fixed-debt covenant qualification (#1991, part of #924):
  - `analytics/mc/fixed_debt_coverage.py`: `fixed_debt_coverage_by_row` now enforces a fail-closed
    completeness check. Required covenant rows are determined strictly from committed base debt
    service (`svc > 0`), including allocated bridge debt service. The evaluator fails closed
    (returns `[]`) on any missing, duplicate, or nonfinite required row, or malformed committed
    schedule (bad period/row indices, non-contiguous operating rows, unmapped positive service,
    or invalid bridge/construction alignment). Zero-service rows require no trial CFADS.
  - `analytics/mc/engine.py`: Fixed-debt stress percentiles and breach probability are calculated
    strictly when every trial produces complete covenant coverage (`len(fixed_dscr_vals) == n and n > 0`),
    eliminating partial-sample survivor bias. Permissive runs with incomplete trials record
    `fixed_debt_stress = {"status": "unavailable", "reason": ..., "n": ..., "n_requested": ...}` while
    preserving unrelated valid metrics.
  - `analytics/finance/p90_recomputed_downside.py`: Recomputed P90 downside requires complete covenant
    coverage across all evaluated views (`ratio_rows`, `down_rows`, `own_rows_cov`, and `sizing_rows`
    if present), failing closed with `status: "unavailable"` upon any missing covenant row.
