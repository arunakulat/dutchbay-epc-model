- DutchBay drops from 15 to 14 turbines, because the Blue Whale turbine stands on T2 (15.22.0 ->
  15.23.0). Owner decision of 8 Nov 2026, asked "does DutchBay drop to 14 turbines now that
  Blue Whale replaces T2?": "yes". Work item #1577 (#1353 comment 6716047327).
  - Six scenarios on the IEA 10 MW layout move: the lender case, the 5 US-cent case, the two
    capex cases and the two hybrids. 14 x 10.6383 MW = 148.9 MW (was 159.6); the hybrids are
    198.9 MW (was 209.6).
  - Wake: 7.28% -> 7.32%. The 15-turbine value is scaled by a live PyWake ratio on the
    recorded layout, with the turbine at T2 kept in the flow as a waker and out of the energy
    count (`model_wake_loss(counted=...)`, new). Inputs in `conf/dutchbay_wake_14_turbines.yaml`;
    results in `docs/wind/dutchbay_14_turbine_wake_summary.json`, from
    `scripts/run_dutchbay_wake_rebaseline_v14.py`. The turbine at T2 is modelled with the IEA
    machine as a proxy. Sensitivities: 7.15% with T2 removed from the flow, 7.24% on the 650 m
    row.
  - Energy: gross 554.1 -> 517.2 GWh; modelled net P50 473.8 -> 442.1; bankable P50 464.3 ->
    433.2; P90 (1 yr) 404.4 -> 377.3; net CF 0.332 (unchanged). Hybrid P50 538.1 -> 507.0.
  - Costs: the per-turbine capex lines (WTG supply, foundations, erection) and opex lines (O&M
    contract, land lease) take 14/15 of their 15-turbine figures; the site-wide lines stay. The
    lender capex is USD 151.41M (was 159.6M, now USD 1,016.84/kW) and opex USD 2.85M/yr (was
    3.0M). The lender import share follows the WTG share, 0.69 -> 0.6788. Monte Carlo capex and
    opex bands are re-centred on the new bases.
  - The grid screen's plant rating is 148.9 MVA. The "150 MW" label stays. The grid connection
    is not re-sized: its capex is site-wide and the CEB interconnection study is pending.
  - Lender case: project IRR -0.060% -> -0.251%; equity IRR -23.01% -> -23.37%; project NPV
    USD -91.40M -> -88.03M; min DSCR 1.2196 -> 1.2214; total CFADS USD 166.93M -> 155.46M;
    senior debt USD 63.37M -> 58.87M.
  - The lender covenant snapshot moves PASS -> REVIEW. The per-period sculpt still lands at
    1.30, but the folded year-1 coverage `plan_debt` reports is 1.2961 (was 1.3024), under the
    1.30 target. Year 5 also counts, at one ULP under 1.30, through the snapshot's strict `<`
    (a pre-existing boundary fragility).
  - The web wizard's prefilled form is 148.9 MW at CF 0.332 and USD 159.12M. Its former
    150 MW x 0.35 (460 GWh) no longer reconciles with the 433.2 GWh lender AEP, so a
    one-click run would have been refused.
  - The #923 synthetic feeder keeps a 15-turbine basis, frozen byte-for-byte at
    `legacy_scenarios/dutchbay_lendercase_2025Q4_15_turbines.yaml`: it exercises a 150 MW
    export cap that a 148.9 MW plant never reaches.
  - Not solved: T1 and T3 stand about 2.5-3 rotor diameters from the turbine at T2, a loads and
    site-suitability question as well as a wake one (#1568 domain review N-1).
