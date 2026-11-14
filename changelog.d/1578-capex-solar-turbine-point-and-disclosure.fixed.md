- **Blue Whale capex and solar resource: one turbine point, and the settled disclosure wording**
  (#1578 L-16 and the capex-config half of W-4). `conf/blue_whale_capex_solar_resource.yaml`
  no longer keeps its own, stale copy of the turbine point (79.752666 E, the #1530 setback spot).
  The runner reads the point from `conf/blue_whale_wind_siting.yaml` through the new
  `analytics.gis.shadow_flicker.placed_turbine_lat_lon`, and refuses a copy beside it. The
  descriptive `distance_to_turbine_m` in `docs/blue_whale/solar_resource_summary.json` moves
  from 123.4 m to 197.0 m (to DutchBay T2); every irradiance and energy figure is unchanged.
  The config's `disclosure_note`, and its copy in `docs/blue_whale/capex_blend_summary.json`,
  now carry the #1560 wording used by the scenarios. No KPI moves.
