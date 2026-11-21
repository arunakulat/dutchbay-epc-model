- **Lender report: F-5 line and a "not computed" tornado** — every lender report built through
  `app.reports.report_orchestration` (the API route and the command-line report) now carries the
  F-5 non-reliance notice on its cover and as a caption beside the tornado. When the tornado has
  no usable driver rows, the section keeps its heading and says it was not computed, with the
  sweep's outcome, instead of being left out silently. Report text only; no KPI moves (#1818).
