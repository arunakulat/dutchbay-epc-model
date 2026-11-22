- **The Monte Carlo samples FX depreciation (#1898, #924 study O-7).** Each scenario's
  Monte Carlo held its FX depreciation fixed. The DutchBay lender case now draws
  `fx.annual_depr` per trial from a normal band of 2.22% to 9.57% (95%) around its 5.89%/yr
  base: the standard-error interval of the 20-year mean depreciation from the BIS vintage
  that sets the base (`analytics.fx.fx_calibration.long_run_depreciation_band`). Blue Whale
  wind keeps its flat reporting rate (owner, 2026-10-28) and draws only the LKR depreciation
  of its USD opex share, `opex.currency_split.usd_lkr_depreciation_pct`, from -1.11% to
  5.99% around its 2.44% PPP base, with the same BIS half-width (owner, 2026-11-22). The
  engine refuses an FX depreciation band with no `source`, and refuses sampling
  `fx.annual_depr` beside a calibrated FX driver that also sets it. Deterministic KPIs do
  not move; Monte Carlo distributions widen, and at the lender band's high end some trials
  have no solvable IRR.
