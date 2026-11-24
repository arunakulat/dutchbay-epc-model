- **FX depreciation Monte Carlo band includes interannual realised-path variance (#1917; 15.36.0).**
  `analytics.fx.fx_calibration.long_run_depreciation_band` now accepts `horizon_years`
  (project life $H$) and computes the combined standard error
  $\sigma \sqrt{1/T + 1/H}$, adding the project-life realised-average variance to the
  historical-mean parameter variance (`horizon_years=None` remains available for the
  parameter-only lower bound). Both scenario Monte Carlo bands are re-derived with
  $H = \text{returns.project\_life\_years} = 20$:
  - DutchBay lender case (`fx.annual_depr`): 2.22%–9.57% → **0.70%–11.09%** around the
    5.89%/yr base.
  - Blue Whale wind (`opex.currency_split.usd_lkr_depreciation_pct`, USD opex share only):
    -1.11%–5.99% → **-2.58%–7.46%** around the 2.44%/yr relative-PPP base.
  Deterministic KPIs do not move. As merged (256 trials, seed 42; P10 / P50 / P90):
  - Lender case: equity NPV USD -124.7M / -97.1M / -70.1M → **-125.7M / -97.1M / -67.2M**;
    project NPV USD -121.4M / -93.0M / -63.6M → **-122.8M / -93.0M / -58.2M**; trials with
    no project/equity IRR root rise from 10/256 to **26/256** (#1456 / #1746), so project
    IRR P10 moves into the undefined tail (P50 -1.08% → -1.24%, P90 2.88% → 3.77%). Read
    equity NPV for the economic tail.
  - Blue Whale wind: equity NPV USD -3.57M / -0.84M / 1.77M → **-3.63M / -0.89M / 1.80M**;
    project NPV USD -1.66M / 1.40M / 4.75M → **-1.82M / 1.35M / 4.73M**; project IRR
    8.91% / 12.31% / 15.80% → **8.75% / 12.28% / 15.80%** (1/256 no-project-IRR-root trial).
