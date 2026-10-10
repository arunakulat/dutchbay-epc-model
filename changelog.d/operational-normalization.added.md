- Add deterministic, provenance-bound operational CSV normalization and QA receipts with exact
  source, upstream-lineage, method and derived-artifact digests; complete mapped/excluded column
  accounting; explicit row-exclusion receipts; strict canonical units; UTC/DST treatment using a
  versioned timezone database; calendar-aware cadence, coverage, duplicate, gap, drift and finite
  value checks; and explicit complete-bucket energy-sum or interval-average-power aggregation on a
  UTC elapsed-time basis. The layer performs no silent sorting, imputation, unit conversion or
  resampling and remains hard-fenced from AEP, finance and reliance outputs (#1332).
