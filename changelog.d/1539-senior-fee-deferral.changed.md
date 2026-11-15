- On a capitalising cash sweep, a senior credit-support fee that the period's cash cannot pay
  is now deferred and carried forward (#1539, owner ruling 2026-11-15). Before this the full
  fee was charged even when it exceeded the period's available cash, so equity could be asked
  for more than the period generated. In the debt engine the fee due (this period's fee plus
  any deferred) is paid first, up to the period's cash, and the rest carries forward as the
  first claim on later cash. ASSUMPTION: the deferred fee bears no interest. The ruling does
  not say, and the owner may change it. `bullet` and `refinance` defer nothing.
- The equity waterfall settles the deferred fee ahead of equity. The engine measures the
  period's cash on the sizing basis, which can be lower than the cash the equity waterfall
  holds. So each year the waterfall pays the deferred balance from cash left for equity, then
  from cash the SPV holds for the sponsor (lockup-trapped, then retained), before any
  distribution, trap or retention. At the horizon it pays from the terminal release before
  any of it reaches the sponsor. It never makes a cash call for the fee. If the engine's own
  later cash pays arrears the waterfall already settled, the difference goes back to equity
  cash, so no fee is paid twice. The arrears rank behind scheduled service, the reserve
  top-up and the engine's balloon sweep.
- New outputs:
  - `debt_result`: `senior_fee_deferred_usd`, the balance carried at the end of each
    balloon period, and `senior_fee_deferred_residual`. `senior_fee_usd` is the fee paid.
  - Annual rows: `senior_fee_deferred_usd`.
  - Equity rows: `senior_fee_arrears_settled_usd` and `senior_fee_arrears_usd`.
  - Equity summary: `total_senior_fee_arrears_settled_usd` and
    `senior_fee_unpaid_at_horizon_usd`.
  - KPI: `senior_fee_deferred_residual`, beside `balloon_residual`. It is the fee still unpaid
    after the waterfall, or the engine's figure when no waterfall runs.

  A warning is logged when any fee is unpaid at the horizon. The new KPI takes the lender
  vector from 42 to 43 keys, so the TRAIN-01 KPI schema in the steward skill and its policy
  test move with it.
- An unpaid fee at the horizon is charged to no one. Against paying it, it raises project NPV,
  equity NPV and PLCR.
- Limits (follow-up #1736):
  - Fee the waterfall settles reaches neither the tax deduction, project NPV, LLCR and PLCR,
    nor the three statements. They all read the engine's paid series.
  - The balloon sweep itself still measures cash on the sizing basis.
  - The engine does not know which arrears the waterfall has settled. When its own later cash
    pays them again, it takes that cash out of its balloon sweep, and the waterfall hands the
    same amount back to equity. The fee is still paid once, but in that period cash reaches
    equity while the balloon, a senior claim, is left unswept. No committed scenario or stress
    reaches this, because there the sizing-basis cash only declines.
  - `senior_fee_deferred_residual` names two figures: in `debt_result` the engine's arrears
    before the waterfall, and on the KPI surface the fee still unpaid after it.
  - The unpaid-fee warning is logged only when the equity waterfall runs.
- No figure moves on any committed scenario. Every cash-sweep scenario has a senior fee rate of
  0, and the only fee-bearing scenario, the lender case, refinances. So no committed scenario
  reaches a deferral, and this branch is exercised only by tests, including an end-to-end
  stress on a temporary config. The census covers the 48 YAML files tracked under
  `scenarios/**`, with 0 differences in KPIs, debt result and equity distribution beyond the
  new keys, which are all zero.
