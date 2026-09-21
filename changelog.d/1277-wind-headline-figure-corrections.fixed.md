- Correct the AEP headline figure named in the wind drift-detection docstrings. Both
  VALIDATE-mode checkers (`wind_resource/weibull_fit.py`, `wind_resource/arco_assessment.py`)
  described 483.6 GWh as "the auditable headline" and the Monte-Carlo AEP note called
  402.6 GWh "the canonical"; both were retired by the ERA5 re-baseline, and the committed
  headline is the bankable net P50 464.3 GWh. Calibrating an acceptable drift against a
  superseded baseline inverts the purpose of the modules that detect drift. Also adds the
  missing `synthetic_mcp_measurement.py` row to `docs/MODULE_REFERENCE.md`, the only one of
  the 17 `wind_resource/` modules that was undocumented, with a guard so a module can no
  longer go undescribed unnoticed. Docs-only; no behaviour change.
