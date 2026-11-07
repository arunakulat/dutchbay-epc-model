- Blue Whale: the turbine stands on DutchBay T2, with zero wake (15.21.0 -> 15.22.0). Owner
  decision of 7 Nov 2026: "Blue Whale Turbine is replacing the T2 Dutchbay turbine - its on the
  exact same location - if not, recalculate location to match T2 location. As such wake does
  not apply"; on wake from T1 and T3, "Zero wake, disclose T1/T3 risk". Work item: #1353
  comment 6705598736.
  - `analytics/gis/shadow_flicker.py` gains a placement rule, `site.turbine_placement`:
    `reference_point` stands the tower on the configured reference point (DutchBay T2,
    8.2925 N, 79.7547 E, from `scripts/process_era5_wind_data.py`) and refuses one inside the
    coastal setback; `coastal_setback` keeps the earlier westward search. The turbine moves
    224 m east, 108 m from the nearest mapped coastline.
  - `analytics/gis/pv_array_layout.py` gains `site_fit.crane_pad_side` (east or west); the
    hardstand goes west of the tower, an assumption until a crane plan exists.
  - The wind yield does not change: the ERA5 cell and the NASA POWER blocks are identical at
    both positions. Wake stays zero, and the T1/T3 wake risk is disclosed in STATUS.md, not
    quantified.
  - Shadow flicker: 5 of 8 boundary points exceed 30 h/yr worst case; expected 733 h/yr at the
    north-east corner.
  - The lot's land maximum at 5 MW / 20 MWh falls from 191 to 186 tables. The turbine's shadow
    costs the solar + BESS array 0.203% of plane-of-array irradiance (was 0.130%). The
    fixed-battery sizing moves from 151 to 152 tables (a near tie); PR 3's and PR 4's sizes do
    not change.
  - Solar + BESS v0.7 (on 15.20.0's opex split and one construction period and 15.21.0's O&M
    indexation): project NPV USD -4,439,870 -> -4,440,000; equity IRR -5.12% -> -5.00%; solar O&M
    on 5,703.04 kWp. Hybrid v0.11 (superseded): project IRR 9.2829% -> 9.2817%. Wind is
    unchanged.
  - The sizings keep the basis they have had since 15.19.0 (single-currency opex, two
    construction periods, flat tariffs); the battery-size work moves them to the current basis.
