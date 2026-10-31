- After maturity the debt engine now carries the balloon as the debt it is (#1503,
  #1504). Under `cash_sweep` and `bullet` it accrues interest at the facility's blended
  rate (`avg_debt_rate`) until it is repaid, as the refinance already did; a sweep whose
  cash cannot pay the interest capitalises it into `balloon_residual`. `debt_outstanding`
  now follows the balloon actually outstanding instead of staying at the structural
  balloon to the horizon, and the senior credit-support fee is charged on that balance,
  so it stops once the balloon is repaid. `debt_result` gains `balloon_interest`, the
  per-period interest inside `balloon_resolution`, which the three-statement builder now
  books as interest for every treatment. On the canonical lender case only the fee
  moves (USD 15.11M to 13.14M): equity IRR -30.54% to -26.44%, project IRR -0.142% to
  -0.060%, project NPV USD -91.57M to -91.40M, PLCR 1.324 to 1.328; min DSCR, LLCR and
  the facility do not move. Cash-swept cases that clear their balloon lose equity
  (sinohydro_lean -5.68% to -6.26%, kalpitiya -5.47% to -6.07%, eia_prudent -8.64% to
  -8.89%); those whose sweep never clears keep their equity IRR and report a larger
  unpaid balance. None of these figures supports a lender, IC, covenant or Board
  representation while the F-5 and #1110 holds stand.
