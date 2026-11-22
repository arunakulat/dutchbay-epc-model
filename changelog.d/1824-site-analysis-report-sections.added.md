- **Site-analysis report sections** — one report section per site analysis a scenario
  declares (wind battery options, equipment cost parity, FX and tenor screening, PV + BESS
  sizing) and one for the wind resource transfer they read. Each section shows its status
  (completed, stale, not run, failed or not applicable), its screening labels (no lender P90,
  the wind + BESS tariff working assumption, the contiguous-location standardised-PPA limit)
  and where its figures came from. `scripts/run_site_analysis_v14.py` runs any analysis for
  any scenario and writes a summary stamped with its code and config digests; a report marks
  that summary stale once either digest no longer matches, and a lint test keeps every
  committed summary current. The command-line lender report (`emit_lender_report`, #1752) builds these sections for the run's effective scenario; a builder that cannot run is listed under the sections not run. A report whose caller passes no sections is byte-identical. No
  KPI moves. HOLD union unchanged: F-5, #1110, v15.6.1 (#1824).
