- Blue Whale solar + BESS unit (15.13.0). Owner decisions of 1 Nov 2026: a 5 MW PV array on
  the latest JinkoSolar panel and a 5 MW x 6 h BESS, run as one unit beside the turbine; the
  BESS discharged 17:30-21:30 at the priority rate and 05:30-07:30 at the other rate.
  - New `analytics/gis/pv_array_layout.py`: module warranty path, cold-Voc string length,
    tables, no-shading row pitch from pvlib solar position with a clear-aisle floor, the
    fenced area of a compact block with roads, MV stations and a containerised BESS pad, and
    a packed fit on PR 1's placeholder lot less the coastal setback, the turbine foundation
    and its crane hardstand.
  - New `solar_resource/pv_bess_dispatch.py`: the hourly series of `compute_solar_aep`'s
    pvlib chain, pinned to its annual energy; a PV-only-charging BESS dispatcher with a
    combined export limit and a repeating TMY year; energy and revenue by rate; the
    degradation path; and the mapping of the unit onto the engine's `solar` and `bess_1`
    blocks without engine code. It stays scenario-local because #1472's hourly ledger is not
    on `main`. PV shading by the turbine is #1520's and is not modelled; nor is bifacial gain.
  - New `scripts/run_blue_whale_solar_bess_v14.py` (Hydra, JSON) and
    `conf/blue_whale_solar_bess.yaml`, with the module's datasheet values and every
    assumption marked. Generated `docs/blue_whale/pv_bess_hourly_tmy.csv` and
    `docs/blue_whale/pv_bess_layout_lot5b.geojson`.
  - Results: 160 tables of 56 modules (8,960, 6.0032 MWp), strings of 28 (1,461.7 V at
    15 C); pitch 6.74 m, GCR 0.71 (the no-shading rule alone gives 5.31 m); 4.10 ha fenced;
    191 table positions fit the usable 5.97 ha of the lot. PV 8.9745 GWh (CF 20.49% on AC).
    Year 1: discharge 6,774 MWh evening and 598 MWh morning, PV direct export 211 MWh, no
    curtailment, 289 equivalent full cycles, unit revenue LKR 357.2M (341.1M priority,
    16.0M other).
  - `scenarios/blue_whale_hybrid_lot5b_2026.yaml` v0.5: solar 5 MW AC at CF 0.173144 (the
    unit's export) and degradation 0.364946%; `bess_1` 5 MW / 30 MWh / 6 h as an
    `energy_tariff` priority premium of 29.38 on 267.0335 cycles for 15 years; tariff blend
    24.749 (was 24.77); BESS capex placeholder scaled to 30 MWh ($3.75M, was $5.0M). The
    wind is unchanged. The engine reproduces the dispatcher's revenue in year 1 and within
    0.16% in later years.
  - KPI change, Blue Whale only: project IRR 3.15% -> 3.58%, equity IRR 0.51% -> 0.92%,
    minimum DSCR 0.869 -> 0.868. With the capex held, project IRR is 3.09%. Pinned in
    `tests/finance/test_blue_whale_scenario_kpis.py` with responsiveness guards and an
    engine-against-dispatcher revenue test. The VERSION digests in the synthetic feeder
    placeholder and the D3B success digest move with the version only.
