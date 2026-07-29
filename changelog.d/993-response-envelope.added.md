- **Async wind jobs surface the full screening assessment (#993)** — a `CaseResult` now
  carries an optional `wind_assessment` block exposing all three exceedance levels
  (P50/P75/P90 net AEP in GWh + net capacity factors), resource provenance and grade
  (screening — never bankable, #961), site metadata, the assessed data period, and the
  fitted wind statistics (mean wind speed, Weibull A/k). Previously the pipeline computed
  the full assessment and the job discarded all but the single billed P-level. Additive:
  the public API contract bumps 1.0 → 1.1 (a new optional field); plain finance cases
  leave it `null` and existing consumers are unaffected.
