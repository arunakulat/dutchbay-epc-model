- **Lender case sized to the annual covenant DSCR (#1845, 15.33.0, KPI-moving)**: a new
  `Financing_Terms.sizing_dscr_basis` (`period`, the default and the behaviour before, or
  `annual_covenant`). On `annual_covenant` the sculpt takes the half-year bridge's service
  out of operating year 1, and the gearing solve also holds every covenant year
  (`dscr_by_year`) at `target_dscr`. `scenarios/dutchbay_lendercase_2025Q4.yaml` opts in
  (owner decision 2026-11-22): its year-1 covenant DSCR rises from 1.2214 to 1.30 with less
  senior debt. No other scenario changes.
