- **The coverage gate no longer reports cancelled shards as a coverage regression** — the
  95% floor is enforced downstream of a 6-way pytest-split matrix, but the gate combined
  whatever shard artifacts it happened to receive. Cancellation is routine (the workflow's
  `concurrency` group cancels in-flight PR runs on a newer push) and a cancelled shard still
  runs its `always()` upload step, so the download succeeded while carrying a partial set.
  Combining that subset produced a real percentage over an incomplete tree, which the floor
  then announced as a floor breach: on run `33960436162` (PR #1233) three of six shards were
  cancelled and the gate printed `TOTAL 89.72%` and `Coverage failure: total of 89.72 is less
  than fail-under=95.00`. Nothing was wrong with coverage — half the suite never reported.
  This is the #1121 misattribution (naming a cause for a non-success result that was really a
  cancellation) in the one form it left behind: the gate did not misreport a job result, it
  computed a real number from incomplete input. The gate now counts its shard data files
  against `TOTAL_SHARDS` **before** combining and, when the count is short, blocks with
  `coverage not enforced: N of M shard artifacts present` instead of a percentage. The floor
  is unchanged at 95% and a missing shard still blocks — a shard that never reported means the
  floor was never measured, which is not a pass. `TOTAL_SHARDS` moved to workflow-level `env`
  so the matrix and the gate share one definition, and the coverage job now publishes an
  `enforced` output so `Test Summary`'s coverage line can tell a genuine breach from a gate
  that never measured anything. Governed by `tests/lint/test_coverage_gate_policy.py`.
