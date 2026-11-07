- PUCSL escalable O&M tariff indexed yearly (15.20.0 -> 15.21.0). Audit residual L-9 (#1537 domain
  F-3). The owner answered "should it be indexed?" with "yes" on 2026-11-07. Work item #1353
  comment 6705449182.
  - `finance.tariff_indexation` reads an optional `tariff.om_indexation`. It holds
    `escalable_om_lkr_per_kwh`, `basis` and `pre_operation_years`, plus the basis inputs:
    `ccpi_fx_weighted` takes `ccpi_weight`, `lkr_usd_weight`, `ccpi_inflation_pct` and
    `lkr_usd_depreciation_pct` (a percent, or `relative_ppp` with `usd_inflation_pct`), and
    `fixed_rate` takes `annual_rate_pct`. It fails loud on unknown keys, missing inputs, weights
    that do not sum to 1, out-of-range rates and an escalable part above the tariff. The year's
    tariff is `lkr_per_kwh + escalable x ((1 + g) ** (t + pre_operation_years) - 1)`, so an
    override of `tariff.lkr_per_kwh` moves only the non-escalable base.
  - Both annual-row builders apply the indexed tariff. An `energy_tariff` BESS block may declare
    `escalable_om_lkr_per_kwh`, which rides the same index. A block that declares it without the
    scenario index is refused. Without either block the output is identical.
  - Basis: the PUCSL *Methodology for RE Feed-in Tariffs 2026 (Approved)*, s.3.1 item 2. The
    Commission publishes the yearly rate "considering CCPI and LKR/USD exchange rate variations".
    No weights are published. The placeholder (input B35) is the methodology's own 70% LKR/USD /
    30% CCPI weighting for the non-escalable adjustment, on CCPI 5% (B29) and LKR/USD 2.44%
    (relative PPP on USD 2.5%, B34): 3.21%/yr from operating year 1. The consultation assumed
    3.85%/yr O&M escalation in its BESS case.
  - Blue Whale wind v0.5 (4.93 of 25.73 indexed): project IRR 12.41% -> 13.13%, equity IRR
    10.54% -> 11.55%, project NPV USD 1,342,632 -> 1,956,797.
  - Blue Whale solar + BESS v0.6 (2.72 of 20.72, and 0.30 of the 29.38 premium: the priority
    rate's 3.02 is 2.72 / 0.90 RTE): project NPV USD -4,517,261 -> -4,439,870, equity IRR
    -7.00% -> -5.12%. The sizing runs priced flat tariffs and are not re-run; the battery-size PR
    re-runs them on this basis.
  - Hybrid v0.10 (superseded; the blend 4.596111 of 24.97308): project IRR 8.73% -> 9.28%.
  - Year-1 DSCR does not move in any scenario: the index is 1.0 in operating year 1.
  - Not modelled: the month-12 FX/CCPI adjustment of the non-escalable part, the three-yearly
    true-up to market rates and any escalation between the 2026 base year and COD.
