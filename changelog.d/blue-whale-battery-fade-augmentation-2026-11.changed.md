- Blue Whale: the solar + BESS battery fades and is augmented (#1578 L-11). Owner, 14 Nov
  2026: take the fade from the OEM's performance curve in the private corpus; augment "when
  capacity falls below 80%"; for the augmentation cost, "use an assumption". KPIs applied under
  the owner's delegation of 7 Nov 2026. No VERSION bump (#1625).
  - `solar_resource/pv_bess_sizing.py`: a strict `battery_health` block in the project sizing
    config. The battery loses `fade_pct_per_year` of its nameplate energy a year, linearly,
    plus each trial's residual fade; before any year that would start below
    `augment_below_soh`, cells restore `restore_to_soh`, at `augmentation_usd_per_kwh` per kWh
    added, paid in that year (the engine's `augmentation_schedule`, written so that it moves the
    cash only) and in the unit's own cash flow. With `replaces_price_reserve` every BESS price
    drops the augmentation reserve the all-in holds. Two new one-at-a-time inputs move the fade
    rate and the augmentation price. PR 3's sizing is unchanged.
  - `conf/blue_whale_solar_bess_project_sizing.yaml`: fade 1.5533%/yr, a linear rate derived from
    the OEM curve (the curve stays outside the repository; a test re-derives the rate when
    `DUTCHBAY_BLUE_WHALE_PRIVATE_SOH_CURVE` names it); augment below 80% SoH to the nameplate;
    USD 103.55/kWh added (ASSUMPTION: the pricing config's equipment line, paid as stated); the
    USD 8.89/kWh reserve removed; residual fade 0/0/0.5%/yr (was 0/0/2); three new cases.
  - Result (seed 20261101, 256 trials, 514 points): the choice does not move, 107 tables,
    3.5 MW AC and 0.1 MW / 0.4 MWh, still the grid floor. P50 after-tax project NPV USD
    -4,440,814 (was -4,441,537), P90 -4,721,216 (was -4,721,153). The floor beats 0.2 MW by
    USD 17,539 and 1.0 MW by 164,883 (paired P50, 100% of trials). 17 of 18 one-at-a-time
    cases keep it; a 10% higher priority rate picks 0.3 MW by USD 418, a near tie. In the base
    case, 0.2 MW overtakes it at a BESS all-in of USD 115.8/kWh (published basis) or a priority
    rate of LKR 54.99/kWh. The sizing config's recommendation comment no longer restates run figures,
    because the summary records its digest.
  - Solar + BESS scenario v0.10: bess_1 capex 56,296 -> 52,740 (USD 131.85/kWh); an
    augmentation of USD 8,363.90 before year 14; fade 0.0004990 -> 0.0110508; solar degradation
    0.362809 -> 0.359233. Project NPV USD -4,477,787 -> -4,479,214; equity NPV -4,557,056 ->
    -4,557,964; min DSCR 0.8717 -> 0.8719; equity multiple -0.099 -> -0.103; IRRs stay
    undefined. Wind and the hybrid do not move.
  - Not modelled: the RTE's decline with age, the curve's duty scaled to this battery's
    cycling (the residual fade stands for it), O&M on added cells.
