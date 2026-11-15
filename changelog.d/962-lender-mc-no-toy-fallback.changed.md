- The lender cases' Monte Carlo no longer substitutes toy KPIs for a failed trial (#962 item 1,
  owner ruling 2026-11-15, extended the same day to the 5 US-cent variant and Kalpitiya).
  `scenarios/dutchbay_lendercase_2025Q4.yaml`, `scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml`
  and `scenarios/kalpitiya_lendercase_160m_fitted.yaml` now declare
  `monte_carlo.allow_toy_fallback: false`, so a trial whose full v14 evaluation raises stops the
  run instead of reporting fabricated figures. The web app's `lendercase` Monte Carlo jobs are
  seeded from the first file, so they stop on a failed trial too.
- A healthy run is unchanged. On main and on this change, a 64-trial lender run (seed 42) gives
  an identical summary with no failed or toy trials, and a 16-trial Kalpitiya run (seed 42)
  gives an identical summary with the fallback on and off, with no failed or toy trials.
- The 5 US-cent variant's Monte Carlo now stops. It derives CAPEX from its breakdown
  (`capex.derive_from_breakdown`), so every trial refuses the sampled `capex.usd_total`. On main,
  every trial of that run fell back to toy KPIs: 16 of 16 at seed 42. The fix belongs to a
  follow-up on #962.
- The engine default and declared run modes are unchanged. This settles the lender cases only,
  without declaring `run.mode: lender`, whose report grade would imply lender reliance under
  the F-5 HOLD.
