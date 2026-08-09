- **Make the async wind path's capacity / capacity factor OPTIONAL (derive-authoritative) (#1023)**
  — on the asynchronous live-ERA5 wind job a client may now OMIT `inputs.capacity_mw` /
  `inputs.capacity_factor`. They are Optional on `WindFarmInputs` (default `None`); when omitted,
  `to_overrides()` leaves the `project.capacity_mw` / `project.capacity_factor` and
  `turbine.total_capacity_mw` keys out of the override dict, so the committed base scenario variant's
  value survives the deep-merge and the async screening seam (#997) derives + overwrites the physical
  basis from `num_turbines × turbine nameplate` and the selected `p_level`. The SYNC wizard is
  unweakened: `app/web/routes.py::_inputs_from_form` still REQUIRES both fields and rejects an
  omission with the same `pydantic.ValidationError` (`type='missing'`) shape the route already
  normalises into per-field error rows. `run_wind_job`'s `input_reconciliation` provenance note now
  tolerates a `None` submission, recording an omitted field as
  `{"submitted": null, "used": <derived>, "drift_pct": null, "superseded": false,
  "derived_only": true}` — the derived basis is still surfaced, never flagged as a supersession. The
  report assumptions register shows a `derived (screening)` placeholder for an omitted capacity /
  capacity factor instead of formatting `None`. When BOTH values are present every touched surface —
  `to_overrides()`, the reconciliation note, the assumptions rows — is byte-identical to before, and
  the canonical lender-case finance byte-oracle is unchanged (`finance/` and `analytics/` untouched;
  this is async wind-job orchestration + the wizard input surface only). New tests cover the async
  omission end-to-end (derives + succeeds through the real service seam, derived_only surfaced), the
  sync rejection of a missing / blank capacity, the `to_overrides()` byte-identity, and the report
  placeholder. Refs #974, #1023.
