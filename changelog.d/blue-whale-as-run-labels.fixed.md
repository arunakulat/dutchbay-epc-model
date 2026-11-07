- **Blue Whale sizing summaries carry their as-run model version again.** The 2026-11-02 renumbering
  of the Blue Whale stack (#1530 to #1541) relabelled `spec.model_version` in
  `docs/blue_whale/pv_bess_sizing_summary.json`, `solar_bess_project_sizing_summary.json` and
  `solar_bess_fixed_bess_sizing_summary.json` from the as-run 15.15.0 to 15.17.0. As a result,
  `pv_bess_sizing_summary.json`'s own `spec.result_sha256` no longer verified. The three files are
  restored, byte for byte, to the bytes their runs wrote. No figure changes, and no KPI moves.
