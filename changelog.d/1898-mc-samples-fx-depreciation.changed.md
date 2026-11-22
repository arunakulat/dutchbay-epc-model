- **The Monte Carlo samples FX depreciation (#1898, #924 study O-7; 15.36.0).** Each
  scenario's Monte Carlo held its FX depreciation fixed. The DutchBay lender case now draws
  `fx.annual_depr` per trial from a normal band of 2.22% to 9.57% (95%) around its 5.89%/yr
  base: the standard-error interval of the 20-year mean depreciation from the BIS vintage
  that sets the base (`analytics.fx.fx_calibration.long_run_depreciation_band`). The band
  is parameter uncertainty only, so it is a lower bound on lifetime FX risk (#1917). Blue
  Whale wind keeps its flat reporting rate (owner, 2026-10-28) and draws only the LKR
  depreciation of its USD opex share, `opex.currency_split.usd_lkr_depreciation_pct`, from
  -1.11% to 5.99% around its 2.44% PPP base, with the same BIS half-width (owner,
  2026-11-22). The engine refuses an FX depreciation band with no `source`, and refuses
  sampling `fx.annual_depr` beside a calibrated FX driver that also sets it. Deterministic
  KPIs do not move. As merged (256 trials, seed 42), against a control run with the new
  band collapsed onto its base, which isolates the FX effect from the re-stratified draws
  (P10 / P50 / P90):
  - Lender case: equity NPV USD -122.8M / -96.6M / -71.1M -> -124.7M / -97.1M / -70.1M;
    project IRR -4.01% / -0.97% / 1.73% -> -5.23% / -1.08% / 2.88%; project NPV USD
    -119.3M / -93.2M / -66.6M -> -121.4M / -93.0M / -63.6M. 10 of 256 trials, all at
    depreciation draws of 6.9% or more, now have no project IRR or equity IRR root and are
    ranked worst (#1746). Above about 6.4%/yr the equity cash flows change sign three times,
    so the equity IRR lower tail (P10 -17.6% -> -52.7%) is root-ambiguous (#1456) and is not
    a measure of risk; read equity NPV.
  - Blue Whale wind: project IRR 9.17% / 12.41% / 15.80% -> 8.91% / 12.31% / 15.80%;
    equity IRR P10 6.56% -> 6.27%; equity NPV P10 USD -3.4M -> -3.6M. The upper tail does
    not move.
