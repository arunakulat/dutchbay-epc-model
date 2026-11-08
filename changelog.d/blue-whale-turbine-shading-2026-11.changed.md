- Blue Whale: the turbine's shadow on the PV, input B33 (15.18.0 -> 15.19.0). Owner decisions of
  2 Nov 2026: "#1520 as is, Blue Whale PR next" and "This PR has a material effect on Blue
  Whale". Work item: #1353 comment 6568242480.
  - New `solar_resource/pv_array_turbine_shading.py` runs #1518's shadow geometry on each PV
    table of the layout. The rotor yaw is weighted by the 130 m wind rose. The result is an
    hourly retention of plane-of-array irradiance, applied before PVWatts and before BESS
    dispatch (`hourly_pv(..., poa_retention=...)`) in the unit runner and in all three sizings.
    `conf/blue_whale_solar_bess.yaml` declares the block, `turbine_shading_modelled: true` and
    the electrical-mismatch treatment (the optical floor, x1).
  - `solar_resource/turbine_shading.py` (#1518) addresses its review findings:
    - blade shadow is counted only outside the tower strip (A-1);
    - integer counts and a non-mapping block are refused instead of truncated (A-2);
    - the sun-facing case is documented as unattainable (D-2);
    - a ray-trace test pins the yaw convention (D-5).
  - Solar + BESS project (151 tables): 0.130% of plane-of-array irradiance, 0.136% of AC energy.
    Sizes are unchanged in all three re-runs. Scenario v0.4: project NPV USD -4,992,409 ->
    -4,997,611; equity IRR -8.32% -> -8.44%. A x3 mismatch stress gives -5,008,092.
  - Hybrid v0.9 (superseded): project IRR 8.7349% -> 8.7315%. Wind is unchanged.
