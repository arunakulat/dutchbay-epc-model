- **The lender case's Monte Carlo samples FX depreciation (#1898, #924 study O-7).**
  `fx.annual_depr` was held at 5.89%/yr in every trial. It is now drawn per trial from a
  normal band of 2.22% to 9.57% (95%), the standard-error interval of the 20-year mean
  depreciation from the BIS vintage that sets the base
  (`analytics.fx.fx_calibration.long_run_depreciation_band`). The engine refuses an FX
  depreciation band with no `source`, and refuses sampling `fx.annual_depr` beside a
  calibrated FX driver that also sets it. Deterministic KPIs do not move; Monte Carlo
  distributions widen, and at the band's high end some trials have no solvable project IRR.
