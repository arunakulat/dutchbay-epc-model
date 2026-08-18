- **Typed QSTS feeder provenance and canonical-finance refusal (#923-A).** An existing
  `feeder_model_path` is no longer treated as proof of a real feeder. Every enabled
  path-backed QSTS declares `input_kind` as a utility/site model, synthetic placeholder, or
  test fixture; the shared `CurtailmentShareResult` carries generated/observed/site and
  canonical-finance eligibility flags. Synthetic/test feeders may execute advisory solver
  diagnostics, but the finance seam fails loudly if one is presented for canonical KPI
  movement. The committed lender case remains default-off and its canon is unchanged.
