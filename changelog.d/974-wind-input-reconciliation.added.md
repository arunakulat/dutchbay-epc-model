- **Surface the async wind path's capacity / capacity-factor supersession (#974)** — the async wind
  job already DERIVES the finance capacity (`num_turbines × turbine nameplate`) and capacity factor
  (from the selected `p_level` export) and the screening seam (#997) overwrites whatever the client
  submitted, so a mismatched submission no longer trips the CESSPIT-strict adapter drift guard. That
  overwrite was silent; `run_wind_job` now records an `input_reconciliation` note in the assessment
  provenance (submitted vs used, per-field drift percent, and a `superseded` flag past the adapter's
  0.5% tolerance) so the client is TOLD the derived physical basis superseded their advisory
  capacity / capacity factor, never left to wonder. Additive: a new key on the free-form
  `WindAssessment.provenance` dict (no contract-version change), and a no-op for a bare/legacy export
  with no derived physical keys. A new end-to-end regression test drives #974's exact case (client
  150 MW / CF 0.339 vs a 159.57 MW / P75-CF 0.228 assessment — both a capacity AND a capacity-factor
  mismatch) clean through the real service seam and asserts the surfaced supersession; unit tests cover
  the tolerance boundary and the bare-export no-op. `finance/` and `analytics/` untouched; the
  canonical lender-case byte-oracle is unchanged (this touches only the async wind-job orchestration).
  Refs #965, #974; builds on #997.
