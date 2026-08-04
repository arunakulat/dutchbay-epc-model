- **Validate the resource assessment on the live location-assessment path (#996 D4-wire)** — the
  async wind/analysis job's shared assessment step (`app/jobs/runner.py::default_assessment`) now
  projects its `run_complete_assessment` result into the frozen `ResourceAssessment` contract and
  carries it on `AssessmentResult`. Construction is the guard: it fails loud
  (`ResourceAssessmentError`) if the `AEP = capacity × 8760 × CF` identity (net AEP MWh→GWh,
  capacity factor percent→decimal) or the `P90 ≤ P75 ≤ P50` monotonicity is violated for the live
  assessment — the #996 "AEP validated for the active selected P-level" / monotonicity criterion,
  enforced on real pipeline output. It is lenient on ABSENCE (a bare export or partial result
  degrades to `None`, never crashing a job) and strict only on INCONSISTENCY. The downside-debt
  slice will read the assessment's P90/P50 ratio from here. Screening-grade (#961). `finance/` and
  `analytics/` untouched; canonical KPIs byte-identical. Ref #996.
