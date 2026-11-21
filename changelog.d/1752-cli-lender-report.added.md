- **Command-line lender report, HTML and a DBPL-01 PDF** — `run_full_pipeline_v14.py` gains an
  `emit_lender_report` emitter (follows `emit_all`) that writes the combined lender report
  `POST /v1/cases/report.pdf` builds, through `app.reports.report_orchestration` with the
  production sensitivity profile (tornado, Morris, PAWN), plus the capital-risk section. The
  Monte Carlo is the capital-risk emitter's own when it ran in the run, otherwise it runs under
  the same lender guards (toy fallback off, at least 1,000 trials). Every section left out is
  listed on the report with its reason, the cover carries the F-5 notice, and the PDF is printed
  through the DBPL print core. The API report is unchanged. No KPI moves (#1752).
