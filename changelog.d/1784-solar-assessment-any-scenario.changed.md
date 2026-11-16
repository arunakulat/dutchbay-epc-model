- The solar assessment report now runs on any solar scenario (#1784, after the owner's
  2026-11-16 ruling that all code must be available to any scenario, and the card "drop the
  site, reuse its code"). Its code moves into `app/reports/solar_assessment.py`, which reads
  the location, PV design, tariff, capex, covenant and Monte Carlo drivers from the scenario,
  takes its breakevens from `solve_tariff_breakeven`, forces the Monte Carlo toy fallback off,
  and renders a DBPL PDF. `scripts/generate_solar_assessment_report.py` is a thin command line
  that requires `--scenario`. The one site's settings, its narrative, its national GHI grid,
  the country outline, place labels and the illustrative bifacial uplift are removed. An
  analysis or map that cannot run is listed in the report with its reason. No engine,
  scenario or KPI figure moves.
