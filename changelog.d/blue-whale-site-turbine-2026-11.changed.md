- Blue Whale wind: turbine, placeholder site, coastal placement, setbacks and shadow
  flicker (15.12.0). Owner decisions of 1 Nov 2026: the Envision EN-206/10.5 de-rated to
  9.5 MW, its yield derived from the confidential curve PMD-004447 Rev A; an assumed square
  site, flagged; the turbine pushed west to the coast-conservation setback.
  - `scenarios/blue_whale_hybrid_lot5b_2026.yaml` v0.4: wind 9.5 MW, net CF 0.374256 and
    31.15 GWh (was 10 MW at 0.35), generation 14.5 MW, wind capex $12.35M at the unchanged
    $1,300/kW placeholder, tariff blend 24.77 (was 24.76). Gross 33.77 GWh, CF 40.58%, on the
    DutchBay ERA5 Weibull moved from 150 m to 130 m with shear 0.14 and the curve corrected
    from 1.148 to 1.15 kg/m3; losses 7.77% (availability 97%, electrical 2%, curtailment 2%,
    other 1%, no wake). The de-rate is modelled as the curve clipped at 9,500 kW.
  - The curve is read at run time from a path outside the repository and is never
    committed, printed or hashed (`KALPITIYA60MW-WIND-HANDLING-2026-09-21`). Publication of
    derived figures rests on the owner's decision of 1 Nov 2026. Section 4 of that handling
    note now records this promotion; its parent pin in
    `docs/source_materials/kalpitiya_60mw_2026/MANIFEST.sha256` is refreshed.
  - New `scripts/run_blue_whale_wind_siting_v14.py` (Hydra, JSON) and
    `conf/blue_whale_wind_siting.yaml`. The yield reuses `gross_aep_farm_gwh`,
    `density_velocity_factor` and `apply_losses`, and is cross-checked against the
    independent `gross_aep_weibull` (agreement 0.002%).
  - New `analytics/gis/shadow_flicker.py`: westernmost placement at a coastal setback, a
    coast-aligned square lot, a tip-height setback screen built on
    `analytics.gis.exclusion_mask.build_setback_zone`, and astronomical worst-case and
    expected shadow flicker from pvlib sun positions. Thresholds and their sources are in
    config: 30 h/yr and 30 min/day worst case, 8 h/yr expected (LAI 2002).
  - Placeholder site in `docs/blue_whale/`: the OpenStreetMap coastline near DutchBay T2
    (ODbL), the lot and turbine GeoJSON (`surveyed: false`, `placeholder: true`) and the
    flicker grid. The turbine is at 8.292500 N, 79.752666 E, 60 m from the mapped coastline
    under CZ&CRMP 2024-2029 Table 6-1 segment 2 (25 m reservation and 35 m restricted area).
    That is a westernmost bound: the plan measures from the vegetation line, which is not
    mapped. The 233 m tip-height setback is breached on three lot edges, and worst-case
    flicker exceeds 30 h/yr at six of eight boundary points. Rotor overhang over the sea,
    the reservation and land outside the lot is an open question.
  - KPI change, Blue Whale only: project IRR 2.77% -> 3.15%, equity IRR 0.06% -> 0.51%,
    minimum DSCR 0.869 -> 0.869. Pinned in `tests/finance/test_blue_whale_scenario_kpis.py`
    with responsiveness guards. The VERSION digests in the synthetic feeder placeholder and
    the D3B success digest move with the version only.
