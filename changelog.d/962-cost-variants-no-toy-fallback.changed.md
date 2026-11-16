- The lender case's two CAPEX cost variants, `scenarios/dutchbay_capex_eia_prudent_2025Q4.yaml`
  and `scenarios/dutchbay_capex_sinohydro_lean_2025Q4.yaml`, now declare
  `monte_carlo.allow_toy_fallback: false` (#962 item 1; owner ruling 2026-11-16 extending the
  #1721 ruling to these variants). A Monte Carlo trial whose full v14 evaluation raises now
  stops the run instead of reporting fabricated figures.
- A healthy run is unchanged: a 64-trial run (seed 42) of each variant gives an identical
  summary with the fallback on and off, with no failed or toy trials. No deterministic KPI
  changes. The engine default and declared run modes are unchanged.
