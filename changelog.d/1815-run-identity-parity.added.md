The executive workbook now carries a `Manifest` sheet with the run's identity fields
(config hash, engine version, git SHA, generation time, manifest schema version, validation
mode and seed), read back by `read_workbook_run_manifest`. The new `analytics.run_identity`
helpers (`run_identity`, `require_same_run_identity`) check that the API response, the report
context and the workbook carry the same run identity, and name every field that differs
(#1815, inventory gap W-1).
