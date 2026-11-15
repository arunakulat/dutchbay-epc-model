- The lender case's Monte Carlo no longer substitutes toy KPIs for a failed trial (#962 item 1,
  owner ruling 2026-11-15). `scenarios/dutchbay_lendercase_2025Q4.yaml` now declares
  `monte_carlo.allow_toy_fallback: false`, so a trial whose full v14 evaluation raises stops the
  run instead of reporting fabricated figures. A healthy run is unchanged: on main and on this
  change, a 64-trial lender run (seed 42) gives an identical summary with no failed or toy
  trials. The engine default and declared run modes are unchanged; this settles the lender case
  only, without declaring `run.mode: lender`, whose report grade would imply lender reliance
  under the F-5 HOLD.
