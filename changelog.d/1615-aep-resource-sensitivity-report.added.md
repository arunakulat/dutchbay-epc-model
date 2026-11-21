- **Lender report: wind-resource AEP sensitivity** — the command-line lender report gains a
  "Wind Resource Sensitivity — Net AEP" section built from the AEP cluster's resource-side
  tornado and Monte Carlo AEP (owner ruling on #1615, 2026-11-16: wire into reports). It is a
  labelled resource sensitivity beside the committed net P50/P90, reconciled against it with
  the reasons the figures differ, and supports no bankable resource claim. One report seam,
  `app/reports/aep_resource_sensitivity.py`, may import the two cluster modules; the boundary
  guard keeps finance, the API, `wind_resource/` and the runners closed. A scenario without the
  inputs lists the section under "Sections not run". No KPI moves (#1615 step B).
