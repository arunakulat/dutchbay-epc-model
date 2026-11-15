- On a capitalising cash sweep, a senior credit-support fee that the period's cash cannot pay
  is now deferred and carried forward (#1539, owner ruling 2026-11-15). Before this the full
  fee was charged even when it exceeded the period's available cash, so equity could be asked
  for more than the period generated. The fee due (this period's fee plus any deferred) is paid
  first, up to the period's cash; the rest carries forward without interest and is paid first
  from later cash. `debt_result` publishes `senior_fee_deferred_usd` (the balance carried at
  the end of each balloon period) and `senior_fee_deferred_residual` (any fee still unpaid at
  the horizon); `senior_fee_usd` is the fee actually paid. `bullet` and `refinance` defer
  nothing. Both keys are appended after `balloon_interest_paid`, and the D3C result facade
  routes them as opaque artifacts with the other balloon series.
- No figure moves. No committed scenario combines a cash sweep with a fee its cash cannot pay:
  all 33 scenarios that run on `main` give identical KPIs, debt and equity results apart from
  the two new keys.
