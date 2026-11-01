- The levered-tax debt-sizing fixed point now warm-starts each pass's gearing scan at
  the previous pass's answer (#1514 follow-up, after #1516). Each pass used to rescan
  about 130 trial gearings from `debt_ratio` down, although the answer moves by at most
  a few steps between passes. A lender-case run takes 0.041 s instead of 0.142 s, which
  is faster than before #1451 (0.061 s). The scan visits the same grid of gearings, so
  it returns the same value whenever min DSCR is non-increasing in gearing. That holds
  on every solve checked: 14,588 warm-started solves across every committed scenario,
  the report sensitivity runs and the MC and wizard tests were re-run cold, with no
  difference. Full results on every committed scenario are byte-identical, and
  `tests/finance/test_gearing_warm_start.py` re-checks each warm-started solve of the
  lender case against the cold scan.
