- Add deterministic, provenance-bound operational CSV normalization and QA receipts with exact
  source, upstream-lineage, method and derived-artifact digests; complete mapped/excluded column
  accounting; explicit row-exclusion receipts; strict canonical units; UTC/DST treatment using
  caller-supplied, hash-bound TZif bytes; normalized-asset group universes; population-exact
  calendar/fixed cadence, coverage, duplicate, gap, drift, ordering and finite value checks; and
  explicit complete-bucket exact-energy-sum or bounded half-even average-power aggregation on a UTC
  elapsed-time basis. Caller-supplied TZif containers and provenance text are revalidated with
  bounded parsing before standard-library use, including RFC 9636 indicator relationships,
  month-end leap semantics, start-truncated v4 corrections and expiration records. Malformed parser
  inputs, Python-incompatible offsets and datetime-range failures are closed, and four-digit UTC
  years are host-independent. Results reconcile retained sources, methods, specs, canonical bytes
  and receipts at construction, including deterministic source replay that rejects substituted
  normalized measurements. The layer performs no silent sorting, imputation, unit conversion or
  resampling and remains hard-fenced from AEP, finance and reliance outputs (#1332).
