- Blue Whale solar + BESS sizing (15.12.0). Owner decisions of 1 Nov 2026: fix the turbine and
  run a new Monte Carlo to size the solar array and the BESS on current prices, pricing the
  inverter from Huawei or another tier-1 maker matched to the JinkoSolar string; the BESS
  windows stay 17:30-21:30 (priority) and 05:30-07:30.
  - New `solar_resource/pv_bess_sizing.py`: a decision grid (DC/AC 1.0-1.4 on 5 MW AC, BESS 10-40 MWh
    at 5 MW) over seeded LHS trials (`analytics.mc.samplers`, common random numbers). An array
    form of PR 2's dispatcher, checked against it, runs every trial and year at once. PR 2's
    `engine_representation` and `evaluate_with_overrides` evaluate each trial, and a unit-only
    pre-tax NPV and IRR come from `finance.irr`. The module matches the inverter to the
    datasheet, checks the lot fit, and admits only sizes that can export the full 4 h priority
    window.
  - New `conf/blue_whale_pv_bess_pricing.yaml`: every price frozen with its URL, retrieval date
    and figure. Modules USD 0.104-0.119/Wp FOB (OPIS via pv magazine, Jul-Aug 2026). Huawei
    SUN2000-330KTL-H1 datasheet, with an inverter price range of USD 0.020-0.045/W that is an
    assumption (one retail listing and the Wood Mackenzie floor). PV BoP and EPC USD
    0.354-0.545/Wp derived from IRENA 2024 installed costs. BESS USD 78.75-143.41/kWh all-in
    (mode 135.00) from the public NSO 250 scenarios. No private offer or turbine price was used.
  - New `conf/blue_whale_pv_bess_sizing.yaml` and `scripts/run_blue_whale_pv_bess_sizing_v14.py`
    (Hydra, JSON, explicit seed, requested and effective counts). The committed result is
    `docs/blue_whale/pv_bess_sizing_summary.json`: 10,320 evaluations, statistics only.
  - Result: DC/AC 1.1 (147 tables, 5.51544 MWp) with 5 MW / 24 MWh. P50 project NPV USD
    -8,499,899 and P90 -8,962,702; P50 project IRR 4.42% and P90 4.13%. It beats DC/AC 1.2 in
    90.6% of paired trials, by USD 29k at the median. The 4 h rule binds: without it the P50
    NPV favours DC/AC 1.0 with 10 MWh, a battery that cannot serve the window. Every size has a
    negative project NPV.
  - `scenarios/blue_whale_hybrid_lot5b_2026.yaml` v0.6 carries the chosen size's base case: solar
    capex USD 3,368,596 and CF 0.165096; BESS 24 MWh / 4.8 h, capex USD 3,240,000, 325.4723 cycles;
    tariff blend 24.786; capex USD 20,958,596; O&M USD 615,154 (placeholder rates scaled). The
    wind is unchanged.
  - KPI change, Blue Whale only: project IRR 3.58% -> 4.26%, equity IRR 0.92% -> 1.58%, minimum
    DSCR 0.868 -> 0.868, project NPV USD -10.20M -> -8.84M. Pinned in
    `tests/finance/test_blue_whale_scenario_kpis.py`, which now has capex responsiveness guards.
    PR 2's dispatcher tests run at the chosen size. The VERSION digests in the synthetic feeder
    placeholder and the D3B success digest move with the version only.
