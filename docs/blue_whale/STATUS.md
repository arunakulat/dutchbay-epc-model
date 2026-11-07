# Blue Whale: project status

Last updated: 2026-11-07. Stage: **concept screening (skeleton model, owner inputs outstanding)**.

## Configuration under study

From PR 4 (owner, 2026-11-01) Blue Whale is **two separate projects** on the same lot: the
turbine, built first, and a solar + BESS project sized under the PUCSL 2026 4 h BESS rules.

| Project | Component | Size | Notes |
|---|---|---|---|
| Wind (`scenarios/blue_whale_wind_lot5b_2026.yaml`) | Turbine | 1 x Envision EN-206/10.5 de-rated to 9.5 MW, 130 m hub, 206 m rotor | Owner decision 2026-11-01; tip height 233 m; built first. From PR 5 its yield rests on met mast 617725 (net CF 0.487560, 40.57 GWh; not lender-grade) |
| Solar + BESS (`scenarios/blue_whale_solar_bess_lot5b_2026.yaml`) | Solar PV | 5.70304 MWp DC (152 tables) at 5.0 MW AC, JinkoSolar Tiger Neo 3.0 670 W, fixed tilt 8 degrees, 17 x Huawei SUN2000-330KTL-H1 | PR 7: PV AC 5.0 MW so that reading A sits at its 10 MW limit; PV DC chosen for the owner's battery on the P50 after-tax project NPV. 152 tables from 15.22.0, with the turbine on DutchBay T2 (15.18.0-15.19.0: 151; PR 6: 4.01464 MWp, 3.5 MW AC; PR 4: 6.0032 MWp, 5.0 MW AC) |
| | BESS | **5.0 MW / 20.0 MWh (4 h), the owner's strategic choice** ("Fix 5 MW / 20 MWh"), charged only from the PV, discharged only 17:30-21:30 | PUCSL 2026 4 h rule. Not the value-based size: that is 1.0 MW / 4.0 MWh on 107 tables at 3.5 MW AC, USD 1.25M better at P50 after tax (PR 7 section) |

The combined view `scenarios/blue_whale_hybrid_lot5b_2026.yaml` (v0.8: 9.5 MW wind, 5.51544 MWp
at 5 MW AC, 5 MW / 24 MWh discharged 17:30-21:30 and 05:30-07:30) is superseded; from v0.7 (PR 5)
its wind block mirrors the wind project's, and from v0.8 (PR 6) its wind and BESS capex are the blended figures; nothing else in it has changed since v0.6. The sections from "Wind yield" to "Solar + BESS sizing and
pricing (v0.6)" below describe it and PR 1 to PR 3, as recorded then.

Funding: **fully LKR funded** (owner, 2026-10-28). Revenue, costs and debt are all LKR, so the
model runs with FX held flat and the USD columns are a constant-rate translation of LKR.

Model files: `scenarios/blue_whale_wind_lot5b_2026.yaml` and
`scenarios/blue_whale_solar_bess_lot5b_2026.yaml` (versions 0.3 and 0.3), and the superseded
`scenarios/blue_whale_hybrid_lot5b_2026.yaml` (version 0.8). Placeholders apart from the
configuration, the funding currency, the researched tariffs, the wind yield, the solar + BESS
size (the owner's 5 MW / 20 MWh battery and the PV chosen for it, PR 7), the cited PV capex and
the blended wind and BESS capex (PR 6).
Inputs register: [INPUTS_REQUIRED.md](INPUTS_REQUIRED.md).

## Site

Lot 5B in Plan 3641 (24 Mar 2010), Mutuwal village, GN Dutch Bay 633, Kalpitiya DS,
Puttalam District. Extent 23 A 0 R 0 P = 9.3077 ha. Owner: Blue Whale Resort (Pvt) Ltd
(PV 71488), by Deed of Transfer 318 (3 May 2010). Sea to the north and west, Puttalam lagoon
to the south. Rights of way over Lot 5I (9 m road) and Lot 3 of Plan 3215, and a shared jetty
on Lot 5D.

These facts come from the owner's scanned title pack, reviewed outside this repository. The
pack has not been ingested into `docs/source_materials/`, so they are not yet evidence of
record under `DATA-01`.

## Open risks

1. **Fit of the turbine.** The turbine stands on DutchBay T2's position (owner,
   2026-11-07), which falls in the north-east corner of the placeholder lot below. The
   233 m tip-height setback is breached on the north and east edges, the 30 m foundation
   reaches the north edge, the rotor overhangs land outside the lot by up to 88 m, and the
   worst-case shadow flicker exceeds 30 h/yr at five of the eight boundary points. A
   surveyed boundary (B03) and setbacks (B08) decide whether the turbine fits.
2. **Wake from DutchBay T1 and T3.** The yield assumes no wake. The turbine replaces T2,
   so T2 itself casts none (owner, 2026-11-07: "As such wake does not apply"). If the rest
   of the DutchBay array is built, T1 (624 m, bearing 21 degrees, 3.0 Blue Whale rotor
   diameters) and T3 (529 m, bearing 202 degrees, 2.6 diameters) stand roughly upwind in
   the north-east and south-west monsoons and would wake it. The owner chose zero wake
   with this risk disclosed (2026-11-07); it is not quantified.
3. **Coastal permitting.** Most of the lot is likely inside the Coast Conservation Act zone
   (CC&CRMD permit, IEE or EIA), with lagoon ecology and bird collision in scope.
4. **Component transport.** Blade and tower delivery over a 9 m right of way, or by the
   shared jetty, is unsurveyed.
5. **Title.** The 2010 misregistration was cured only in 2023 (Deed of Declaration 11619).
   Lenders will want a fresh registry search; 9 of the 12 listed title documents are missing
   from the scan.
6. **Landowner and project company differ.** A lease or transfer from Blue Whale Resort (Pvt)
   Ltd to the project company has to be documented.
7. **Revenue.** The tariffs are the researched PUCSL 2026 FiT and the BESS earns through the
   hourly dispatch below, but the offtake route is not confirmed and the priority window's
   clock hours come from a consultation, not the approved Annex 2. From PR 4 the turbine and
   the solar + BESS are separate projects, each under 10 MW on its own.
8. **The 10 MW contiguous-location limit (open legal question, PR 4).** The Electricity Act
   No. 36 of 2024, s.11(3) proviso, caps capacity "procured from a contiguous location using
   standard power purchase agreements on cumulative basis" at 10 MW. The 9.5 MW turbine stands
   on the same lot as the solar + BESS project. If the two count together, the turbine leaves
   0.5 MW and the pair exceeds the limit at every size considered, under either reading of the
   limit. For PUCSL, the NSO or counsel (input L01); see the PR 4 section below.

## Wind yield and siting screen (v0.4, 2026-11-01)

**Every figure in this section depends on a placeholder site.** No survey of Lot 5B exists
(input B03), so the lot is an assumed square of the deeded 9.3077 ha and the coastline is
OpenStreetMap's. Generated by `scripts/run_blue_whale_wind_siting_v14.py` from
`conf/blue_whale_wind_siting.yaml`.

### Owner decisions (2026-11-01)

- Turbine: "Use the EN-206/10.5, de-rated to 9.5mw, with derived results using the
  confidential curve PMD-004447 Rev A. Its not necessary to provide details of the curve, as
  long as the curve is used in your internal calculations."
- Site: "Assumed square, flagged".
- Position: "The turbine tip can go over the sea - as T2 location borders the sea, push the
  turbine as much as possible westwards towards the shore, respecting the coast conservation
  set backs - check EIA". **Superseded on 2026-11-07** (below).
- Position, 2026-11-07, verbatim: "Blue Whale Turbine is replacing the T2 Dutchbay turbine -
  its on the exact same location - if not, recalculate location to match T2 location. As
  such wake does not apply". The turbine had stood 224 m west of T2 (the westernmost
  setback point); it now stands on T2. On wake from the neighbouring DutchBay turbines she
  chose "Zero wake, disclose T1/T3 risk" (open risk 2).

### Placeholder site and turbine position

| Item | Value | Basis |
|---|---|---|
| Coastline | OSM `natural=coastline` ways 399832875, 399832880 and 399832872, retrieved 2026-11-01 | [`osm_coastline_near_t2.geojson`](osm_coastline_near_t2.geojson), (c) OpenStreetMap contributors, ODbL. Traced from aerial imagery; vertices 50 to 240 m apart near T2; accuracy not stated by OSM |
| Coastline at T2's latitude | 292 m west of DutchBay T2 (8.292500 N, 79.754700 E) | Interpolated between two OSM vertices 237 m apart |
| Coastal setback | 60 m: 25 m reservation and 35 m restricted area | CZ&CRMP 2024-2029, Table 6-1, segment 2 (Uchchamunai to Mohoththuwaram Split Northern Boundary, Medium (+)), measured from the Seaward Reference Line of section 6.4.1 |
| Turbine | **8.292500 N, 79.754700 E** (WGS84), DutchBay T2 | T2's recorded position (`scripts/process_era5_wind_data.py`), owner decision of 2026-11-07 (`site.turbine_placement: reference_point`). Until then 8.292500 N, 79.752666 E, 224 m west, the westernmost point on T2's latitude 60 m from the coastline |
| Lot | 305.09 m square, west edge on the coastline at bearing 28.1 degrees, centred on T2's latitude | [`site_placeholder_lot5b.geojson`](site_placeholder_lot5b.geojson): `surveyed: false`, `placeholder: true`. The edge departs from the coastline by at most 0.4 m |
| Distances from the tower | nearest mapped coastline 108.3 m (OSM way 399832872, south-east of the tower, along the lot's east side), its 60 m setback line 48.3 m; the sea coastline 257.6 m (way 399832880, west); lot edges west 257.6 m, north 14.9 m, south 290.2 m, east 47.4 m | |

The tower clears the 60 m CZ&CRMP setback of every mapped coastline way: the nearest is the
way along the lot's east side, 108.3 m away, whose setback (sea or lagoon, CZ&CRMP 6.5.4)
is itself an open question from PR 1. The setback figure is taken from the public plan
(statutory source). The run refuses a reference point inside the setback.

The rotor reaches up to 103 m from the tower: it stays 5 m short of the east-side coastline
way but passes 55 m into its setback strip, and it overhangs land outside the lot by up to
88 m (north and east). Both are **open questions**: whether a rotor may overhang the
reservation and restricted areas (section 6.4.3 lists what the reservation admits) and
land outside the lot. The lot itself is unchanged: it is still the assumed square on the
coastline at T2's latitude, so T2 falls in its north-east corner. A survey (B03) replaces
both.

### Wind yield

Superseded in PR 5 by the met-mast transfer (section "Wind resource from met mast 617725"
below). The ERA5 basis here is kept as the comparison.

| Item | Value |
|---|---|
| Resource | DutchBay ERA5-fitted Weibull, A 8.199 m/s and k 2.665 at 150 m (`scenarios/dutchbay_hybrid_bess_2025Q4.yaml`), moved to 130 m with shear 0.14: A 8.036 m/s, k unchanged |
| Air density | Curve corrected from its 1.148 kg/m3 basis to the 1.15 kg/m3 site density of the DutchBay scenario (IEC 61400-12-1 wind-speed scaling, factor 1.00058) |
| De-rate | Curve clipped at 9,500 kW (an assumption; an OEM de-rate mode may differ) |
| Gross AEP | 33.77 GWh, CF 40.58% on 9.5 MW |
| Losses | availability 97%, electrical 2%, curtailment 2%, other 1% (the DutchBay stack), no wake (the turbine replaces T2; owner, 2026-11-07; open risk 2): 7.77% in all |
| **Net AEP** | **31.15 GWh, CF 37.43%** (was 30.66 GWh, 10 MW x 35%) |
| Cross-check | The independent integrator agrees to 0.002% |

The ERA5 point is the DutchBay array centroid (8.27 N, 79.75 E), in the same ERA5 cell as
both T2 and the #1530 position, so the move to T2 (2026-11-07) does not change the yield. The basis
is reanalysis, not a site measurement (B07). Only derived figures are published; the curve is
held privately under `KALPITIYA60MW-WIND-HANDLING-2026-09-21`.

For the BESS work: no hourly wind series is built here. The ERA5 hourly tooling
(`wind_resource/era5_fetcher.py`, `wind_resource/arco_assessment.py`) and
`wind_resource.EnergyCalculator` can produce one, and the solar TMY is hourly.

### Tip-height setback

Tip height 233 m; setback 1.0 x tip height, the usual topple distance (no Sri Lankan
statutory figure is held, B08). At T2 the tower is within 233 m of the north and east edges
(14.9 m and 47.4 m), and 112,577 m2 of the 170,280 m2 setback disc lies outside the lot
(87,323 m2 at the #1530 position). A
233 m setback could not fit on this lot from any position: it exceeds the 152.5 m
half-width of the square.

### Shadow flicker

No receptor or building data exist, so the values below are at the lot's corners and edge
midpoints, and the map is a grid: [`shadow_flicker_grid.csv`](shadow_flicker_grid.csv), 100 m
spacing out to 2,100 m. Worst case: sun always out, rotor always turning and facing the sun,
sun above 3 degrees, within 10 rotor diameters, 2 m receptor height, 1-minute steps over
2026 (pvlib). Expected case: the worst case kept to hours with direct normal irradiance of at
least 120 W/m2 in the DutchBay PVGIS TMY, times the 93.0% chance that the rotor is turning;
rotor orientation is not credited, so it stays conservative.

With the turbine on T2 (2026-11-07):

| Receptor | Distance (m) | Worst case (h/yr) | Worst case (max min/day) | Expected (h/yr) |
|---|---|---|---|---|
| North-east corner | 50 | 2,194.4 | 400 | 1,856.6 |
| North edge midpoint | 106 | 1,425.9 | 320 | 1,260.8 |
| East edge midpoint | 146 | 0.0 | 0 | 0.0 |
| North-west corner | 258 | 423.5 | 183 | 340.9 |
| West edge midpoint | 292 | 437.4 | 152 | 359.3 |
| South-east corner | 294 | 0.0 | 0 | 0.0 |
| South edge midpoint | 309 | 0.0 | 0 | 0.0 |
| South-west corner | 388 | 273.0 | 127 | 209.1 |

Thresholds (config, sources in `conf/blue_whale_wind_siting.yaml`): 30 h/yr and 30 min/day
worst case, 8 h/yr expected (LAI 2002). Five of the eight points exceed all three (six at
the #1530 position). The grid is centred on the tower, so its figures barely move. On the
grid, the worst-case 30 h/yr area covers 1.67 km2 and reaches 1,487 m from the tower. Any
resort building or dwelling in that area is a receptor to assess; real receptors are owed
(B08).

## Solar + BESS unit (v0.5, 2026-11-01)

Generated by `scripts/run_blue_whale_solar_bess_v14.py` from `conf/blue_whale_solar_bess.yaml`,
which cites a source or states ASSUMPTION for every value. The land fit rests on the PR 1
placeholder lot. Modules: `analytics/gis/pv_array_layout.py` (array, land, site fit) and
`solar_resource/pv_bess_dispatch.py` (hourly PV, dispatch, engine mapping).

### Owner decisions (2026-11-01)

- Request: a 5 MW solar PV array on the latest JinkoSolar panel; a 5 MW x 6 h BESS; "the
  hybrid scheme is solar+BESS as one unit and then the turbine as the second unit"; land
  for the array.
- BESS: "Use the 17:30 - 21:30 window and add another 05:30 to 07:30 window for the remaining
  2 hours. The priority rate will only apply to the evening window".

### Module

JinkoSolar Tiger Neo 3.0, JKM670N-66QL6-BDV (series 650-670 W), from the manufacturer's
datasheet JKM650-670N-66QL6-BDV-F1-EU (distributor copy, SHA-256 in the config) and pv
magazine, 2025-09-05. The two agree on every value they share.

| Item | Value |
|---|---|
| STC | 670 W; Vmp 43.09 V, Imp 15.55 A; Voc 50.98 V, Isc 16.22 A; efficiency 24.80% |
| Temperature coefficients | Pmax -0.26 %/C, Voc -0.24 %/C, Isc +0.046 %/C |
| Mechanical | 2,382 x 1,134 x 30 mm, 32.5 kg, 264 cells (66 x 4), glass-glass |
| Limits | 1500 V DC (IEC), 35 A series fuse |
| Bifaciality | 85 +/- 5% (not modelled) |
| Warranty | 12-year product, 30-year power: 1% in year 1, then 0.35%/yr, at least 88.85% at year 30 |
| NOCT/NMOT | not stated by either source; the yield chain does not need it |

### Array and land

| Item | Value | Basis |
|---|---|---|
| "5 MW" | AC export capacity at the point of connection: PV inverter nameplate and the unit's export limit | Reading of the FiT plant capacity; a CEB offer decides it (B27) |
| DC/AC ratio | 1.20 target, 1.2006 installed | The DutchBay solar basis (`dutchbay_hybrid_bess_2025Q4.yaml`) |
| String | 28 modules: Voc 1,461.7 V at 15 C (limit 1,500 V); Vmp 1,206.5 V at STC, about 1,076 V at 70 C | Design minimum 15 C is an ASSUMPTION, below the TMY minimum of 21.14 C |
| Table | 2 portrait x 28 (two strings, 56 modules, 37.52 kWp), 4.784 m slant, 32.29 m long | ASSUMPTION: 2P tables |
| Count | 160 tables, 320 strings, 8,960 modules, **6.0032 MWp** | Rounded up to whole tables |
| Tilt and azimuth | 8 degrees, facing south | Near the 8.29 N site latitude; the DutchBay basis |
| No-shading pitch | 5.31 m (GCR 0.90): no row shading 09:00-15:00 on 21 Dec 2026, binding at 09:00 (sun 34.0 degrees) | pvlib solar position at the lot centroid |
| Design pitch | **6.74 m, GCR 0.71**, a 2.0 m clear aisle | ASSUMPTION: the shading rule alone leaves 0.58 m, too narrow to clean or maintain |
| BESS pad | 7 containers of 5,015 kWh / 762 kVA (power needs 7, energy 6; 35.1 MWh installed), 39.2 x 13.9 m pad; with 2 MV stations and 3 m clearance, 991 m2 | ASSUMPTION: Sungrow B-ST5015UX-6H-class 20-ft units, for the footprint only |
| Fenced area, compact block | **4.10 ha** (32 rows of 5 tables, 177.5 x 225.6 m with a 6 m perimeter, a 4 m north-south road every 8 tables, plus the BESS and MV group): 0.68 ha per MWp | ASSUMPTIONS in `land` |

### Fit on the placeholder lot

| Item | Area (m2) |
|---|---|
| Lot (placeholder square) | 93,077 |
| Coastal setback strip in the lot (60 m from every OSM coastline way, including the way along the lot's east edge) | 29,869 |
| Turbine foundation, 30 m diameter (ASSUMPTION, B05), outside the strip | 353 |
| Crane hardstand, 40 x 80 m east of the foundation (ASSUMPTION, B05) | 3,200 |
| **Usable** | **59,654** |
| Required fenced area (compact block) | 41,026 |
| Margin | 18,628 |

Packing east-west rows at the design pitch into the usable area, 6 m in from its edge, with
the BESS and MV group placed first as far east as fits: **191 tables fit against 160
needed, so the unit fits** (36 rows). The tables that fit would carry 7.17 MWp. After the
160 tables' row strips and the equipment group, about 2.28 ha of usable land remains. The
packing is indicative, not a layout:
[`pv_bess_layout_lot5b.geojson`](pv_bess_layout_lot5b.geojson).

The lot's east edge also lies on an OpenStreetMap coastline way, so the 60 m segment-2
setback is applied there too. The setback on that side may differ (CZ&CRMP 6.5.4 lagoon and
stream setbacks are an open question from PR 1). The tip-height setback and shadow flicker of
PR 1 are not PV exclusions; the PV output lost to the turbine's shadow is modelled from
15.19.0 (input B33; see "The turbine's shadow on the PV" below).

### PV yield

`solar_resource.pv_producer.compute_solar_aep` on the frozen PVGIS TMY
(`inputs/solar_tmy/kalpitiya_pvgis_tmy_8.27N_79.75E.csv`), 8 degree tilt, the module's
-0.26 %/C, the DutchBay 14% loss stack, PVWatts inverter at 96%: **8.9745 GWh**,
1,495 kWh/kWp, CF 20.49% on 5 MW AC (17.07% on 6.0032 MWp DC). Inverter clipping removes
16.9 MWh of DC. Year 1 at the warranted 99%: 8.8848 GWh. The hourly series, rebuilt with
the same chain, sums to the producer's figure (relative gap 2e-16):
[`pv_bess_hourly_tmy.csv`](pv_bess_hourly_tmy.csv) (year 1, hour-start UTC).

Not modelled: bifacial rear gain (no albedo or row-height basis for the site, and the
financed solar chain is monofacial under `solar_resource.bifacial_guard`). Turbine shading on
the PV was not modelled at this version; it is from 15.19.0 (input B33).

### BESS dispatch (year 1, over the TMY year)

The battery charges only from the PV, outside the windows, up to full (the owner's
dispatch). It discharges 17:30-21:30 (priority) and 05:30-07:30 (other rate, from the
previous day's charge). The unit's export is held to 5 MW. Round trip 0.85 AC-AC, with all
of the loss on discharge (the repository convention: 30 MWh is the energy a full charge
absorbs). The TMY year repeats, so the first morning draws on the last evening.

| Item | MWh |
|---|---|
| PV output | 8,884.75 |
| Charged from PV | 8,673.52 |
| Discharged 17:30-21:30 | 6,774.45 |
| Discharged 05:30-07:30 | 598.04 |
| PV exported directly (net of charging) | 211.24: 34.91 in the evening window, 146.17 in the morning window, 30.16 outside |
| Curtailed at the 5 MW limit | 0 |
| Conversion loss | 1,301.03 |
| Unit export | 7,583.73 |
| Equivalent full cycles | 289.1 per year |

| Rate | Energy (MWh) | LKR/kWh | Revenue (LKR) |
|---|---|---|---|
| Priority (evening window, years 1-15) | 6,809.35 | 50.10 | 341,148,664 |
| Other (morning window and outside the windows) | 774.37 | 20.72 | 16,044,988 |
| **Unit, year 1** | 7,583.73 | | **357,193,652** |

A rate follows the hour of export, as one meter at the connection point would measure it,
so the 34.91 MWh of PV exported in the evening window earns the priority rate. The PV
cannot fill the battery on most days: the array makes about 24.3 MWh a day against the
35.3 MWh both windows would need. Charging only what the evening window needs, instead of
filling the battery, earns 359.29 M LKR in year 1: 2.09 M LKR (0.6%) more, because PV
stored for the morning loses 15% and is then paid the same 20.72 as direct export.

### How the engine carries the unit

The engine bills one generation tariff and per-BESS revenue, and needs no new code here:

- `solar`: 5 MW with CF 0.173144, everything the unit exports (PV direct plus battery
  discharge), at the generation tariff;
- `bess_1`: `energy_tariff` at the 29.38 priority premium (50.10 - 20.72) on 267.0335
  cycles of 30 MWh x 0.85 (the priority-window export), for the 15-year priority term;
- the tariff: the year-1 energy-weighted blend of wind 25.73 and the unit's 20.72, 24.749.

Year 1: generation 958.51 M LKR plus BESS 200.06 M LKR equals the dispatcher's 357.19 M
LKR for the unit plus 801.38 M LKR of wind. Over 20 years the PV follows the warranty path
(1%, then 0.35%/yr). The solar degradation (0.364946%/yr) and the BESS
`mdsc_fade_pct_annual` (0.001529) are the geometric rates that match the dispatcher's sums;
the engine stays within 0.16% of the dispatcher in every year. Battery cell fade,
augmentation and availability are not modelled.

## Solar + BESS sizing and pricing (v0.6, 2026-11-01)

> **Historical Reference Note:** The sizing, decision grid, and KPIs in this section represent an intermediate design snapshot (v0.6, PR 3) superseded by PR 4 (two projects split), PR 5 (met-mast wind resource), PR 6 (blended capex), and PR 7 (the owner's 5 MW / 20 MWh battery; v0.8 / 15.18.0) and later PRs. See [Latest run](#latest-run-the-turbine-on-dutchbay-t2-15220-2026-11-07) for current figures.

With the turbine fixed (PR 1), a seeded Monte Carlo chose the PV DC capacity and the BESS energy of
the unit (`solar_resource/pv_bess_sizing.py`, `scripts/run_blue_whale_pv_bess_sizing_v14.py`,
`conf/blue_whale_pv_bess_sizing.yaml`). The result summary is
[pv_bess_sizing_summary.json](pv_bess_sizing_summary.json), which holds statistics only, no per-trial values.

### Owner decisions (2026-11-01)

Relayed on #1353 (comments 6554212671 and 6554297502):

- "We will fix the turbine and then run a new Montecarlo simulation to decide on the best sizing
  for the solar array and the BESS, given the current prices (take the pricing from internal
  corpus for turbine and BESS and search for jinkosolar pv array costs - including inverter costs
  for pv array." The coordinator's lease quotes these words; comment 6554212671 records them in
  its own words.
- "try huwawei or other reputed manufacturer's inverter prices with inverter specs matched to the
  jinkosolar array specs"
- "Use the 17:30 - 21:30 window and add another 05:30 to 07:30 window for the remaining 2 hours.
  The priority rate will only apply to the evening window"

### Method

- **Decision grid.** DC/AC 1.0, 1.1, 1.2, 1.3 and 1.4 on the unit's 5.0 MW AC, rounded up to whole
  37.52 kWp tables. BESS 10, 15, 20, 24, 25, 30, 35 and 40 MWh at 5 MW. Every one of the 40 sizes
  fits the placeholder lot (191 table positions; 1.4 needs 187) and the matched inverter fleet.
- **Dispatch.** PR 2's rules unchanged: PV-only charging; 17:30-21:30 at the priority rate, the
  rest 05:30-07:30 at the other rate; 5 MW combined export limit; the TMY year repeated. An array
  form of PR 2's dispatcher runs every trial and year at once, and it reproduces PR 2's scalar
  dispatcher to 1e-10 (`tests/solar/test_pv_bess_sizing.py`).
- **Evaluation.** Each trial's 20-year dispatch is mapped onto the engine with PR 2's
  `engine_representation` and evaluated through `evaluate_with_overrides`. Project NPV and IRR come
  from the engine (`finance.irr`). A unit-only pre-tax NPV (the unit's capex, revenue and O&M, no
  tax or debt) is reported alongside.
- **Uncertain inputs (seeded LHS, seed 20261101, 256 trials, the same draws at every size).**
  Module price, inverter price, PV BoP/EPC and BESS all-in price (triangular, from the cited
  ranges below); the long-term PV yield (normal, standard deviation 4.7%, from Solargis' +/-4-8%
  P90 annual GHI uncertainty); RTE (uniform 0.82-0.88, assumed); and the battery fade not recovered
  by augmentation (triangular 0, 0, 2%/yr, assumed). Model evaluations: 40 x (256 + 1) + 40
  curtailment cases = 10,320.
- **Objective.** The P50 of the Blue Whale project NPV, at the engine's own discount rate (the
  build-up WACC, 11.28-11.37% across sizes). With the turbine fixed, the change in project NPV
  between sizes is the unit's contribution after tax and debt sizing. P90 here is the value
  exceeded in 90% of trials.
- **Dispatch-rule constraint.** A size is eligible only if a full battery can export the whole
  4 h priority window at 5 MW (deliverable energy at the base RTE of 0.85 must reach at least
  20 MWh). This constraint was added after the first full run (35 sizes, without the 24 MWh step)
  chose DC/AC 1.0 with 10 MWh, a battery that delivers 8.5 MWh into the 20 MWh window. That
  unconstrained choice is still reported (P50 USD -7.681M). It is also where the per-kWh BESS
  price on a 4 h basis is least reliable, because PCS cost scales with MW.

### Prices (frozen with sources in `conf/blue_whale_pv_bess_pricing.yaml`)

| Item | Low | Mode | High | Basis |
|---|---|---|---|---|
| PV module, USD/Wp FOB China | 0.104 | 0.110 | 0.119 | OPIS via pv magazine, 31 Jul 2026: spot USD 0.104-0.119/W; above 650 W "high-$0.100/W to mid-$0.110/W" (mode assumed at its middle); CMM 0.108 on 25 Aug 2026 |
| Delivery to site, USD/Wp | 0.010 | 0.010 | 0.010 | ASSUMPTION |
| Inverter, USD/W nominal AC | 0.020 | 0.0311 | 0.045 | ASSUMPTION range: one retail listing (EUR 8,114.84 per SUN2000-330KTL-H1, 20 Oct 2026, at 1.15 USD/EUR assumed) and the Wood Mackenzie China-domestic floor (below USD 0.02/Wac by 2034) |
| PV BoP and EPC, USD/Wp | 0.354 | 0.462 | 0.545 | IRENA 2024 installed cost (global 691, Asia projection about 500, India 525 USD/kW) less module and inverter; the mode is the midpoint of India and global (ASSUMPTION); per kW DC assumed |
| BESS all-in, USD/kWh | 78.75 | 135.00 | 143.41 | Public NSO 250 variants (bid-implied, base, stress) in `scenarios/nso250_ltl_unit_*.yaml` |
| Turbine | fixed | 1,300/kW | fixed | Placeholder B09, inside the public 977-1,420 USD/kW range of `docs/knowledge_base/01_wind_epc_costs_and_scaling.md` |

No private Envision BESS offer price and no internal turbine price was used. The internal turbine
prices are in private developer packages whose handling notes allow no trace here, and the turbine
cost does not change which unit size is best.

### Inverter match

Huawei SUN2000-330KTL-H1 (datasheet, Huawei Smart PV): maximum DC 1,500 V against the string's
1,461.7 V Voc at 15 C; MPPT range 500-1,500 V (full load 930-1,300 V, from a search result) against
a string Vmp of about 1,076-1,207 V; 65 A per MPPT, so 4 strings of 15.55 A per tracker; 6
trackers, so 24 strings per inverter (Isc 4 x 16.22 = 64.9 A, against a 115 A limit); 300 kW
nominal AC. Seventeen units (5.1 MW nominal) carry the unit's 5.0 MW AC, at 18 strings on the most
loaded unit (DC/AC 1.1, 294 strings) and 22 at DC/AC 1.4. European efficiency 98.8% replaces PVWatts'
96% placeholder in the yield chain.

### Result

Cells in brackets fail the 4 h dispatch rule.

P50 project NPV, USD million

| DC/AC (MWp) | 10 MWh | 15 MWh | 20 MWh | 24 MWh | 25 MWh | 30 MWh | 35 MWh | 40 MWh |
|---|---|---|---|---|---|---|---|---|
| 1.0 (5.0277) | (-7.681) | (-7.882) | (-8.134) | -8.534 | -8.661 | -9.329 | -9.965 | -10.612 |
| 1.1 (5.5154) | (-7.764) | (-7.968) | (-8.186) | -8.500 | -8.629 | -9.304 | -9.943 | -10.576 |
| 1.2 (6.0032) | (-7.855) | (-8.059) | (-8.255) | -8.531 | -8.648 | -9.314 | -9.968 | -10.613 |
| 1.3 (6.5285) | (-7.970) | (-8.173) | (-8.370) | -8.598 | -8.722 | -9.391 | -10.044 | -10.707 |
| 1.4 (7.0162) | (-8.102) | (-8.303) | (-8.501) | -8.707 | -8.830 | -9.500 | -10.161 | -10.824 |

P90 project NPV (exceeded in 90% of trials), USD million

| DC/AC (MWp) | 10 MWh | 15 MWh | 20 MWh | 24 MWh | 25 MWh | 30 MWh | 35 MWh | 40 MWh |
|---|---|---|---|---|---|---|---|---|
| 1.0 (5.0277) | (-7.976) | (-8.219) | (-8.547) | -8.970 | -9.102 | -9.790 | -10.505 | -11.215 |
| 1.1 (5.5154) | (-8.087) | (-8.321) | (-8.617) | -8.963 | -9.089 | -9.767 | -10.487 | -11.201 |
| 1.2 (6.0032) | (-8.211) | (-8.434) | (-8.694) | -8.999 | -9.121 | -9.810 | -10.531 | -11.247 |
| 1.3 (6.5285) | (-8.356) | (-8.577) | (-8.822) | -9.097 | -9.214 | -9.908 | -10.639 | -11.353 |
| 1.4 (7.0162) | (-8.508) | (-8.725) | (-8.960) | -9.222 | -9.337 | -10.041 | -10.772 | -11.494 |

P50 project IRR

| DC/AC (MWp) | 10 MWh | 15 MWh | 20 MWh | 24 MWh | 25 MWh | 30 MWh | 35 MWh | 40 MWh |
|---|---|---|---|---|---|---|---|---|
| 1.0 (5.0277) | (4.49%) | (4.50%) | (4.45%) | 4.29% | 4.22% | 3.86% | 3.51% | 3.16% |
| 1.1 (5.5154) | (4.53%) | (4.54%) | (4.52%) | 4.42% | 4.35% | 3.98% | 3.64% | 3.30% |
| 1.2 (6.0032) | (4.55%) | (4.57%) | (4.56%) | 4.49% | 4.43% | 4.07% | 3.72% | 3.39% |
| 1.3 (6.5285) | (4.55%) | (4.58%) | (4.58%) | 4.54% | 4.48% | 4.12% | 3.76% | 3.43% |
| 1.4 (7.0162) | (4.54%) | (4.57%) | (4.58%) | 4.54% | 4.49% | 4.12% | 3.77% | 3.44% |

P90 project IRR

| DC/AC (MWp) | 10 MWh | 15 MWh | 20 MWh | 24 MWh | 25 MWh | 30 MWh | 35 MWh | 40 MWh |
|---|---|---|---|---|---|---|---|---|
| 1.0 (5.0277) | (4.29%) | (4.28%) | (4.20%) | 4.00% | 3.93% | 3.56% | 3.20% | 2.87% |
| 1.1 (5.5154) | (4.31%) | (4.31%) | (4.26%) | 4.13% | 4.07% | 3.70% | 3.34% | 3.01% |
| 1.2 (6.0032) | (4.33%) | (4.33%) | (4.30%) | 4.22% | 4.15% | 3.79% | 3.44% | 3.10% |
| 1.3 (6.5285) | (4.33%) | (4.34%) | (4.32%) | 4.26% | 4.20% | 3.84% | 3.50% | 3.16% |
| 1.4 (7.0162) | (4.31%) | (4.31%) | (4.31%) | 4.27% | 4.21% | 3.84% | 3.50% | 3.17% |

The chosen size is **DC/AC 1.1 (147 tables, 5.51544 MWp) with 5 MW / 24 MWh**: P50 project NPV USD
-8.500M, P90 -8.963M; P50 project IRR 4.42%, P90 4.13%; P50 equity IRR 1.74%. It beats the
runner-up (DC/AC 1.2, 24 MWh) in 90.6% of paired trials, but by only USD 29k at the median, so DC/AC
1.1 and 1.2 are practically tied. The 4 h rule binds: every eligible size loses value as the
battery grows, so 24 MWh (the first eligible step; the threshold is 23.53 MWh) is chosen. The
alternative objectives agree on 24 MWh and differ on DC/AC: P90 and mean NPV choose 1.1;
project and equity IRR choose 1.4; equity NPV chooses 1.0; unit pre-tax NPV chooses 1.3; minimum
DSCR is flat (0.868 at every size). Under the curtailment scenario (12.5% of daytime direct PV export
lost) the choice is unchanged.

Every size has a negative project NPV, and the unit alone does not earn the discount rate: its
pre-tax IRR at the chosen size is 9.66% at P50 (unit NPV USD -0.62M) against about 11.3%. So the
Monte Carlo ranks sizes; it does not show that the unit, or the project, is viable on these
placeholder financing and O&M inputs.

Base case at the chosen size, as written to the scenario (every price at its mode, yield 1, RTE
0.85, no residual fade): PV 8.4966 GWh (CF 19.40% on AC), year 1 at the warranted 99% 8,411.65 MWh;
discharge 6,607.05 MWh evening and 82.17 MWh morning; direct PV export 541.98 MWh; unit export
7,231.20 MWh (6,639.63 MWh in the priority window); 327.9 equivalent full cycles; unit revenue LKR
344.90M. Capex: PV USD 3,368,596 (USD 0.611/Wp) and BESS USD 3,240,000. The base case sits below the
P50 (USD -8.837M against -8.500M) because the BESS price range is skewed below its mode.

### Limitations

- The placeholder site, financing, O&M and grid inputs of earlier versions are unchanged.
- The BESS price is a 4 h-basis USD/kWh figure applied at every duration, and the all-in figure
  includes a 10% land share although the lot is owned.
- The inverter price is an assumption range, not a utility quote. Inverters are about 5% of the PV
  capex, so the choice does not hinge on them.
- IRENA's USD/kW basis (AC or DC) is not stated in its summary; reading it per kW DC is an assumption.
- `conf/blue_whale_solar_bess.yaml` and the committed hourly CSV and layout GeoJSON keep PR 2's
  owner-brief design (DC/AC 1.2, 30 MWh, 96% inverter). The tests run PR 2's dispatcher at the chosen
  size by overriding those three keys.
- The ordinary test suite exercises reduced grids only. Neither this run nor the suite is tail,
  convergence, lender or bankability evidence (`TEST-03`).

## Two projects, and the solar + BESS project under the PUCSL 2026 rules (PR 4, 2026-11-01)

> **Historical Reference Note:** The sizing (4.5 MW / 18 MWh), capacities, and KPIs in this section represent an intermediate design snapshot under PR 4 superseded by PR 5 (met-mast wind resource), PR 6 (blended capex), and PR 7 (the owner's 5 MW / 20 MWh battery; v0.8 / 15.18.0) and later PRs. See [Latest run](#latest-run-the-turbine-on-dutchbay-t2-15220-2026-11-07) for current figures.

### Owner decisions (2026-11-01)

Recorded on #1353 (comment 6556854201), quoted verbatim:

- "We will therefore consider the 10mw turbine separately from the solar+bess. It will be a
  separate project that will preceed the solar+BESS. Maximize BESS now within the solar+BESS
  parameters in order to gain the maximum benefit from the PUCSL evening tariff band"
- Objective: "Max value, MC decides (Recommended)"
- 10 MW reading: "Model both, flag it"
- Turbine: "Separate, risk flagged"

The earlier window decision, "Use the 17:30 - 21:30 window and add another 05:30 to 07:30
window for the remaining 2 hours. The priority rate will only apply to the evening window", gave
the morning window the remaining 2 hours of a 6 h battery. A 4 h battery has no remaining
hours, so that window is superseded by the decisions above and the PUCSL 4 h rule.

### Scenarios

| File | Project | Status |
|---|---|---|
| `scenarios/blue_whale_wind_lot5b_2026.yaml` | The 9.5 MW turbine, built first: #1530's position, CF 0.374256 and 31.15 GWh (derived results only), wind FiT 25.73, NSO, 20 years, USD 1,300/kW placeholder | v0.1 |
| `scenarios/blue_whale_solar_bess_lot5b_2026.yaml` | The solar + BESS project, sized below under reading A | v0.1 |
| `scenarios/blue_whale_hybrid_lot5b_2026.yaml` | The combined view of PR 3 | superseded; unchanged apart from a header note |

Each new scenario carries the hybrid's finance blocks unchanged (LKR debt 13.39%, 70% gearing,
12 years, 30% tax, FX flat). Each carries the whole USD 2.0M grid, civils and development
placeholder (B26) and USD 0.15M a year of insurance, land and SPV overhead (B28), because the two
are separate SPPAs. That double-counts against the hybrid view until B25 and B26 arrive.

### Legal and regulatory findings

The figures are frozen, with source URLs, sections, PDF SHA-256s and verbatim text, in
`conf/blue_whale_pucsl_fit_2026.yaml`. Each PDF was converted with MarkItDown (R26).

| Finding | Source |
|---|---|
| The BESS tariff covers solar PV plants "connected along with a Battery Energy Storage System"; wind is not covered | [PUCSL Methodology 2026 (Approved)](https://www.pucsl.gov.lk/wp-content/uploads/2026/07/The-Methodology-for-Renewable-Energy-Feed-in-Tariffs-2026-Approved.pdf), s.5.1 |
| "The battery shall have a 4-hour discharge duration." (dispatchable plants); "These BESS shall have a standard discharge duration of 4-hours, at the nominal capacity." (both kinds) | Methodology s.5.1.1, s.5.2.1.1, s.5.2.1.2 |
| Discharged energy = BESS capacity x depth of discharge x cycles x degradation; the charging tariff is divided by the RTE. The nameplate is therefore read as the energy a full battery delivers, with the loss booked on charge | Methodology s.5.1.2 |
| The BESS contract runs 15 years; then the standalone tariff for the rest of the SPPA. The PFT "would be as specified in the SPPA" | Methodology s.5.1; s.4.1, Table 3, note [1] |
| "Prioritized Feed in Time (PFT) - 1730h to 2130h" | [Consultation, July 2026](https://www.pucsl.gov.lk/wp-content/uploads/2026/07/Full-Consultation-Document-Feed-in-Tariff-Review-July-2026.pdf), s.2.3, Table 3 note |
| Reference case: 1 MW, 4 h, 182.52 MLKR/MW, O&M 3%, DoD 100%, 1.5%/yr degradation, 365 cycles, RTE 90%, first-year discharge 1.46 GWh, BESS component 27.57; 21.58 / 0.90 + 27.57 = 51.55, its proposed PFT tariff | Consultation, Annex 2, s.3.1 |
| Ground solar + BESS: priority 47.08 + 3.02 = 50.10; other periods 18.00 + 2.72 = 20.72. Wind 20.80 + 4.93 = 25.73 | Annex 2 (August 2026), s.1 and s.3 |
| "the maximum capacity of such renewable energy plants to be procured from a contiguous location using standard power purchase agreements on cumulative basis shall not exceed 10 MW" | [Electricity Act No. 36 of 2024](https://www.parliament.lk/uploads/acts/gbills/english/6347.pdf), s.11(3) first proviso |
| "standardized power purchase agreement" means "... for renewable energy based power plants having a maximum capacity of 10MW" | Act No. 36 of 2024, s.52 |
| The Minister's capacity Order covers "each renewable energy technology based power plant along with storage or ancillary services directly associated with such power plant" | [Amendment Act No. 14 of 2025](https://www.parliament.lk/uploads/acts/gbills/english/6385.pdf), s.11(3) |

**Two readings of the 10 MW limit** (owner: "Model both, flag it"). Neither is a legal opinion.

- **(A)** PV AC plus BESS power at most 10 MW: the 2025 amendment brings storage "directly
  associated" with the plant into its capacity. The conservative reading; the scenario takes it.
- **(B)** Export at the connection point at most 10 MW, with the PV AC and the BESS power each
  at most 10 MW.

**Open legal risk: the contiguous-location cumulative limit.** The turbine and the solar + BESS
project stand on the same lot. If PUCSL, the NSO or a court counts them "on cumulative basis" as
one "contiguous location", the 9.5 MW turbine leaves 0.5 MW, and the pair exceeds 10 MW at every
size considered here, under either reading. Sequencing the projects does not obviously avoid the
proviso. This is for PUCSL, the NSO or counsel (input L01).

### Method

- **Reused.** PR 3's module (`solar_resource/pv_bess_sizing.py`), its seed (20261101), its LHS
  sampler and 256 trials per point with common random numbers, its cited prices
  (`conf/blue_whale_pv_bess_pricing.yaml`, unchanged) and its uncertainty ranges (unchanged).
  PR 2's dispatcher and unit config, changed only through `unit_overrides` in
  `conf/blue_whale_solar_bess_project_sizing.yaml`.
- **BESS rules.** Energy = 4 x power, the energy a full battery delivers at nominal power; the
  0.85 round trip is booked on charge, each trial at its own RTE (0.82-0.88). Charging only from
  the co-located PV. Discharge only 17:30-21:30, at 50.10 for 15 years; every other kWh, and the
  window after year 15, at 20.72. PR 2's 5 MW export limit becomes 10 MW, which reading A never
  reaches and reading B is held to.
- **Decision grid.** PV DC 107, 120, 134, 147, 160 and 174 tables (4.01-6.53 MWp) and the land
  maximum, recomputed at each BESS size; PV AC 3.5-7.0 MW, keeping DC/AC within 1.0-1.5 and the
  inverter match; BESS power 1-10 MW (0.5 MW steps from 3 to 6). That is 325 sizes; every one fits the lot and passes the inverter match, and all 325 are evaluated.
- **Land maximum.** With the turbine kept (its foundation and crane pad excluded, as in PR 2),
  `analytics/gis/pv_array_layout.py` fits 191 tables (7.16632 MWp) at most BESS sizes (below). The container pad is sized from PR 2's
  6 h product, power-bound at 4 h, so this is conservative for large batteries.
- **Objective** ("Max value, MC decides"; the lease's "unit NPV at P50, with P90 and IRR
  reported"): the P50 of PR 3's unit pre-tax NPV at the engine's discount rate. The engine's
  project NPV, after the 30% tax, the 10% CFADS risk haircut and debt sizing, is reported beside
  it. Plant-level lines are the same at every size, so they do not change the ranking.
- **PV rule.** The objective chooses the PV over the whole grid. A base-case screen (one trial per point) suggested that value kept rising as the PV shrank, so a first production run (at 2270a402) held the PV at the lot's maximum; its P50 showed an interior PV optimum under reading A, so the committed run lets the objective choose and reports the best size at the lot's maximum beside it. The two runs gave identical results at every point.

### Result

Run of 2026-11-01 at 9bc593d7: seed 20261101, 325 grid points, every one evaluated with 256 LHS
trials plus the base case, then a curtailment and an RTE case at each point: 84,175 (325 x 257 + 2 x 325) model
evaluations in 4,131.3 s (`docs/blue_whale/solar_bess_project_sizing_summary.json`, a concise
record whose `result_sha256` identifies the full output). P90 is the value exceeded in 90% of
trials. Unit NPV is the unit pre-tax NPV at the engine's discount rate (about 11.47%); project
NPV is the engine's, after tax, the CFADS haircut and debt.

**Land maximum.** With the turbine kept, the placeholder lot takes 191 tables (7.16632 MWp) for BESS powers of 2 to 9 MW, 192 (7.20384 MWp) at 1 MW and 189 (7.09128 MWp) at 10 MW, where the larger container pad takes room. PR 2 found 191 at 5 MW / 30 MWh, so the coordinator's figure of about 191 tables or 7.17 MWp stands.

| Size | PV tables (MWp) | PV AC MW | BESS MW / MWh | Unit NPV P50 / P90 (USD) | Unit pre-tax IRR P50 / P90 | Project NPV P50 / P90 (USD) | Project IRR | Equity IRR P50 | Evening export, yr 1 P50 (MWh) | Revenue, yr 1 P50 (M LKR) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Reading A, chosen (committed)** | 160 (6.0032) | 5.0 | 4.5 / 18 | 11,747 / -468,482 | 11.48% / 10.26% | -4,532,537 / -4,964,560 | undefined | -3.28% | 6,382 | 352.8 |
| Reading A, PV at the lot's maximum | 191 (7.16632) | 5.5 | 4.5 / 18 | -18,240 / -554,979 | 11.39% / 10.16% | -4,739,097 / -5,203,888 | undefined | -2.76% | 6,485 | 390.1 |
| Reading A, largest BESS allowed | 147 (5.51544) | 4.0 | 6.0 / 24 | -556,391 / -1,194,458 | 10.07% / 8.46% | -5,063,379 / -5,614,768 | undefined | -3.98% | 6,985 | 349.9 |
| **Reading B, chosen (alternative)** | 191 (7.16632) | 6.0 | 5.5 / 22 | 36,391 / -540,752 | 11.48% / 10.26% | -4,858,708 / -5,355,066 | undefined | -2.15% | 7,769 | 425.0 |
| Revenue maximum (reading B only) | 191 (7.16632) | 7.0 | 9.0 / 36 | -1,299,670 / -2,154,663 | 9.07% / 7.43% | -6,257,428 / -6,977,450 | undefined | -3.02% | 9,271 | 464.5 |
| Reading B, largest BESS | 189 (7.09128) | 6.0 | 10.0 / 40 | -1,918,742 / -2,804,431 | 7.97% / 6.39% | -6,821,144 / -7,570,194 | undefined | -3.76% | 9,158 | 458.8 |

**Recommendation (reading A, committed): 160 tables (6.0032 MWp, DC/AC 1.2006, 17 x Huawei
SUN2000-330KTL-H1) at 5.0 MW AC, with a 4.5 MW / 18 MWh BESS.** PV AC + BESS = 9.5 MW. It beats the runner-up (174 tables, 5.5 MW AC, the same 4.5 MW battery) in 52.7% of paired trials, by USD 1,099 at the median: the PV size between 160 and 174 tables is a near tie. Against the best size with the PV at the lot's maximum (191 tables, 5.5 MW AC, 4.5 MW / 18 MWh; P50 USD -18,240), the chosen size is at least as good in 77.7% of paired trials, by USD 37,816 at the median. The battery is 4.5 MW / 18 MWh either way; only the PV changes.

**Reading B's choice (reported, not committed): 191 tables (7.16632 MWp, the lot's maximum) at
6.0 MW AC, with a 5.5 MW / 22 MWh BESS.** Its PV AC + BESS power is 11.5 MW, so reading A does not
allow it; its export never exceeds 10 MW (the battery discharges after sunset), which reading B
allows. Here the lot's maximum PV is also the best PV. It beats the runner-up (5 MW / 20 MWh at the same PV) in 56.3% of paired trials, by USD 5,203 at the median.

**Revenue maximum: 9 MW / 36 MWh with the PV at the lot's maximum and 7.0 MW AC**, LKR 464.5M
in year 1 at P50 and 9,271 MWh exported, all of it in the priority window. Reading A does not
allow it (7 + 9 = 16 MW); reading B does. It loses USD 1.30M of unit NPV at P50 against the
reading B choice: beyond about 22 MWh, each extra MWh of battery is filled on fewer days.

BESS power with the PV at the lot's maximum (best PV AC at each power):

| BESS MW / MWh | Reading A: PV AC MW, unit NPV P50 / P90 (USD) | Reading B: PV AC MW, unit NPV P50 / P90 (USD) | Evening export, yr 1 P50, reading B's size (MWh) | Revenue, yr 1 P50, reading B's size (M LKR) |
|---|---|---|---|---|
| 1.0 / 4 | 6.0: -315,451 / -759,541 | 6.0: -315,451 / -759,541 | 1,502.5 | 265.56 |
| 2.0 / 8 | 6.0: -203,120 / -657,908 | 6.0: -203,120 / -657,908 | 2,955.7 | 301.85 |
| 3.0 / 12 | 6.0: -108,694 / -602,537 | 6.0: -108,694 / -602,537 | 4,392.7 | 338.62 |
| 3.5 / 14 | 6.0: -59,054 / -567,764 | 6.0: -59,054 / -567,764 | 5,101.6 | 356.48 |
| 4.0 / 16 | 6.0: -19,260 / -542,705 | 6.0: -19,260 / -542,705 | 5,799.4 | 374.41 |
| 4.5 / 18 | 5.5: -18,240 / -554,979 | 6.0: 15,301 / -524,223 | 6,483.8 | 391.98 |
| 5.0 / 20 | 5.0: -72,013 / -626,343 | 6.0: 30,531 / -521,107 | 7,151.7 | 409.19 |
| 5.5 / 22 | not allowed | 6.0: 36,391 / -540,752 | 7,769.3 | 425.00 |
| 6.0 / 24 | not allowed | 6.0: 2,969 / -612,032 | 8,307.6 | 438.97 |
| 7.0 / 28 | not allowed | 6.0: -226,846 / -969,535 | 9,008.5 | 457.15 |
| 8.0 / 32 | not allowed | 6.0: -683,079 / -1,517,963 | 9,234.6 | 463.01 |
| 9.0 / 36 | not allowed | 6.0: -1,279,040 / -2,129,674 | 9,249.5 | 463.40 |
| 10.0 / 40 | not allowed | 6.0: -1,918,742 / -2,804,431 | 9,158.0 | 458.82 |

The BESS optimum is interior under both readings and close to the coordinator's pre-tax screen
(15-20 MWh, against an annualised cost of about 7.7 M LKR per MWh a year). Reading A binds: a
larger battery needs less PV AC, and with the lot's maximum PV the inverter match and the 1.5
DC/AC ceiling stop the PV AC below 5.0 MW, so 5 MW / 20 MWh (at 5.0 MW AC) is the largest
battery there, at a P50 of USD -72,013.

Best size at each PV level:

| PV tables (MWp) | Reading A: PV AC MW / BESS MW, unit NPV P50 (USD) | Reading B: PV AC MW / BESS MW, unit NPV P50 (USD) |
|---|---|---|
| 107 (4.01464) | 3.5 / 3.0: -19,372 | 3.5 / 3.0: -19,372 |
| 120 (4.50240) | 4.0 / 3.5: -17,908 | 4.0 / 3.5: -17,908 |
| 134 (5.02768) | 4.5 / 4.0: -6,469 | 4.5 / 4.0: -6,469 |
| 147 (5.51544) | 4.5 / 4.0: -330 | 4.5 / 4.0: -330 |
| 160 (6.00320) | 5.0 / 4.5: 11,747 | 5.0 / 4.5: 11,747 |
| 174 (6.52848) | 5.5 / 4.5: 11,204 | 5.5 / 5.0: 19,891 |
| 189 (7.09128) | - | 6.0 / 10.0: -1,918,742 |
| 191 (7.16632) | 5.5 / 4.5: -18,240 | 6.0 / 5.5: 36,391 |
| 192 (7.20384) | 6.0 / 1.0: -315,451 | 6.0 / 1.0: -315,451 |

**Other objectives.** Under reading A: the mean unit NPV chooses the same size; P90 unit NPV chooses 107 tables, 3.5 MW AC and 3 MW / 12 MWh (the smallest PV on the grid); unit pre-tax IRR chooses 147 tables, 4.5 MW AC and 4 MW / 16 MWh; equity IRR chooses 191 tables, 5.0 MW AC and 5 MW / 20 MWh. The engine's project NPV, equity NPV and minimum DSCR all choose a 1 MW / 4 MWh battery on the smallest PV. Under reading B the mean chooses reading B's size and equity IRR 6 MW / 24 MWh. Project IRR is undefined at almost every size; the size it ranks first has one trial with an IRR and means nothing.

**Sensitivities (base case at every point).** With the PUCSL reference RTE of 0.90, the base case at every point picks the same sizes as the Monte Carlo under both readings (reading A unit NPV USD -4,731, reading B USD 16,375). Under the curtailment scenario (12.5% of the PV exported outside the window lost) the base case picks 107 tables, 3.5 MW AC and 3 MW / 12 MWh under both readings: losing direct PV export makes PV beyond what the battery needs worth less. Base-case rankings use every price at its mode and so sit below the P50, which the BESS price range skews.

**What the result does and does not show.**
- Every size is within about USD 0.04M of zero unit NPV at P50 and negative at P90: the unit's
  pre-tax IRR at P50 (11.48%) only matches the engine's discount rate (about 11.47%). The Monte
  Carlo ranks sizes; it does not show that the project is viable.
- 97.8% of the sizes reading A allows, and 95.7% of those reading B allows, have a negative P50 unit NPV. The P90 unit NPV is negative at every size.
- On the engine's own terms the project loses value at every size: project NPV P50 about
  USD -4.5M to -6.8M, and no project IRR exists, because with O&M escalating 5% a year against
  a flat tariff, the CFADS turn negative after the 15-year priority term and the 20-year CFADS
  sum stays below the capex. The engine's project NPV prefers the smallest battery on the grid
  (1 MW / 4 MWh); after the 30% tax and the 10% CFADS haircut, the battery's margin is negative.
- The committed scenario's base case (every price at its mode) gives a unit NPV of USD -215,111,
  below its P50, because the BESS price range is skewed below its mode, as in PR 3.

### Limitations

- Placeholder site, financing, O&M and grid inputs, as in PR 3. The engine's discount rate is the
  build-up WACC (about 11.5% here), above the PUCSL consultation's 10.3%.
- The PUCSL O&M components are indexed yearly and the non-escalable components adjusted once at
  month 12; neither is modelled, while O&M escalates at 5% a year (B29). This is why the project's
  CFADS turn negative after the priority term.
- The BESS price is PR 3's 4 h-basis USD/kWh; at 4 h it now matches its basis. O&M is PR 3's
  USD 2.5/kWh-yr (about 1.9% of capex), below the consultation's 3%.
- AC coupling: PV clipped at its inverters is lost, not stored. A DC-coupled design could store
  some of it.
- PV AC is the inverters' active-power limit; a fleet of 300 kW units can exceed it by up to one
  unit's rating unless the plant controller caps it. If PUCSL counts inverter nameplate under
  reading A, that margin counts.
- The ordinary test suite runs reduced grids only. Neither this run nor the suite is tail,
  convergence, lender or bankability evidence (`TEST-03`).

## Wind resource from met mast 617725 (PR 5, 2026-11-01)

Work item: #1353 comment 6556910250. Owner direction, verbatim: "use the kalpitiya met-mast
evidence from RAG repo and interpolate to obtain wind rose and more detailed wind evidence. the
two locations are near to each other on the same coastline". Method, sources, tables and
limitations: [MET_MAST_TRANSFER_METHODS.md](MET_MAST_TRANSFER_METHODS.md); results
`met_mast_transfer_summary.json`; rose `met_mast_wind_rose_130m.png` and `.csv`.

**HOLD: not lender-grade.** The met-mast package's HOLD on annual, P50/P90 and lender use stands.

| Item | Value |
|---|---|
| Mast clock | UTC+05:30 (S2 pressure tide, temperature cycle and reference correlation) |
| MCP | Variance ratio by 16 reference sectors at 120 m against NASA POWER / MERRA-2; hourly R^2 0.610, daily r 0.881; own fits SSW, SW, WSW, W; omnidirectional elsewhere |
| Long term | 2015-2025; correction factor 0.916 on the concurrent 120 m mean (8.794 to 8.058 m/s) |
| Transfer | MERRA-2 turbine/mast cell ratio by sector (all-sector 1.014), direction -2.4 degrees |
| Turbine, 130 m | Mean 8.243 m/s; Weibull A 9.207 m/s, k 3.044; SW 26.6% of hours and 36.9% of wind energy; SSW-WSW 51.8% and 68.6% |
| Shear | 100-120 m exponent 0.10 (by sector 0.04-0.12) |
| TI (120 m) | 0.066 at 9-11 m/s, 0.0710 at 15-16 m/s (representative 0.090); not an IEC class |
| **Net AEP** | **40.57 GWh, CF 48.76%** (gross 43.99 GWh); was 31.15 GWh, 37.43% on #1530's ERA5 basis |
| Exceedance | 1-year sigma 13.2%: P90 33.73 GWh (1 year), 33.92 GWh (20 years) |
| Shadow flicker, expected | Rotor yawed to the long-term wind, turbine on T2: 733 h/yr at the north-east corner (worst case 2,194, #1530 expected 1,857); five of eight boundary points still above 8 h/yr |

Of the +9.43 GWh, the mean speed (7.14 to 8.24 m/s) gives +8.78, the steeper distribution
+0.53 and the sector split +0.12; density and losses are unchanged.

## Capex blend and solar resource (PR 6, 2026-11-01)

Work item: #1353 comment 6556975196. Owner decisions, verbatim: "in the next step, search for
the latest CAPEX figures for Wind and BESS from RAG and EPC corpus (Mannar, Mullikulam, NSO BESS
tender, and Kalpitiya) interpolate with China FOB pricing from a deep web search, indicate the
solar efficacy and strength at the Blue Whale location (provide references for the pvlab or any
other process through which these numbers are obtained) and update all YAML occasions in the
Blue Whale Scenario"; and "Derived blend may publish". Method, every source, the anchor
inventory and references: [CAPEX_AND_SOLAR_RESOURCE_METHODS.md](CAPEX_AND_SOLAR_RESOURCE_METHODS.md);
results `capex_blend_summary.json`, `solar_resource_summary.json`, `solar_resource_monthly.csv`.

**The disclosure surface moves on the owner's authority.** The wind and BESS capex are blends
that include private commercial inputs, and those inputs can be recovered exactly from the
published figures. Published on the owner's decision of 2026-11-01 (#1353 comment 6556975196);
the owner accepted the exact recoverability on 2026-11-07 (#1353 comment 6702419885).

| Item | Low | Mode | High | Was |
|---|---:|---:|---:|---|
| Wind, single 9.5 MW turbine, USD/kW (excluding the B26 line) | 728.16 | **936.84** | 1,341.16 | 1,300 placeholder |
| BESS, 4 h, USD per kWh contracted, all-in | 129.13 | **140.74** | 202.51 | 78.75 / 135.00 / 143.41 (NSO 250) |

Wind turbine capex USD 8,899,980 (was 12,350,000); wind project capex USD 10.90M with the B26
line (1,147 USD/kW). PV prices are unchanged from PR 3.

**Solar resource at the PV centroid (8.291526 N, 79.753204 E; 123 m from the turbine)**, pvlib
0.16.1 on the frozen TMY, which is PVGIS-ERA5 2005-2023 (its README's "SARAH3" was wrong:
SARAH3 does not cover the site; the README is corrected in PR 7):

| Item | Value |
|---|---:|
| GHI / DNI / DHI | 1,871.3 / 1,796.7 / 657.5 kWh/m2 |
| POA, 8 degrees, Hay-Davies | 1,885.9 kWh/m2 |
| Specific yield (6.0032 MWp, 5.0 MW AC, 14% losses) | 1,536.3 kWh/kWp |
| Performance ratio | 0.8146 |
| Capacity factor, AC / DC | 21.06% / 17.54% |
| PVGIS 5.3 PVcalc (ERA5, 14%) | 1,472.9 kWh/kWp (-4.1%) |
| Global Solar Atlas (Solargis 2.2.68): GHI / PVOUT | 2,047.7 kWh/m2 (+9.4%) / 1,632.5 kWh/kWp (+6.3%) |
| NASA POWER GHI, 2001-2025 / 2015-2025 | 2,070.6 / 2,046.1 kWh/m2 (+10.6% / +9.3%) |

The ERA5 TMY sits about 9% below the two satellite-based GHI figures, so the committed solar
basis is conservative; re-basing onto satellite irradiance is an open owner decision.

**The solar + BESS sizing moves.** PR 4's production run, re-run unchanged (seed 20261101,
325 points x 256 trials, 84,175 evaluations, 3,945 s) on the blended prices, now chooses **107
tables (4.01464 MWp), 3.5 MW AC and a 1.0 MW / 4.0 MWh BESS under both readings**: the smallest
PV and the smallest battery on the grid. Every eligible size has a negative P50 unit NPV.

| Size | Unit NPV P50 / P90 (USD) | Unit pre-tax IRR P50 | Project NPV P50 (USD) | Revenue yr 1 P50 (M LKR) |
|---|---|---|---|---|
| **Chosen, A and B: 107 tables, 3.5 MW AC, 1 MW / 4 MWh** | -312,629 / -571,313 | 10.14% | -4,079,718 | 164.8 |
| Runner-up: 107 tables, 4.0 MW AC, 1 MW / 4 MWh | chosen is at least as good in 100% of paired trials (by USD 18,611 at P50) | | | |
| Lot maximum PV: 192 tables, 6.0 MW AC, 1 MW / 4 MWh | -457,558 / -908,976 | 10.15% | -4,661,634 | 265.6 |
| PR 4's choice under A: 160 tables, 5.0 MW AC, 4.5 MW / 18 MWh | -684,370 / -1,207,111 | 9.79% | -5,178,503 | 352.8 |
| Revenue maximum under A: 191 tables, 5.0 MW AC, 5 MW / 20 MWh | -847,442 / -1,445,723 | 9.65% | -5,537,751 | 402.9 |
| Revenue maximum under B: 191 tables, 7.0 MW AC, 9 MW / 36 MWh | -2,638,469 / -3,634,557 | 6.98% | -7,533,633 | 464.5 |

The battery loses value at every size because its blended all-in (140.74, range 129.13-202.51
USD/kWh) now carries Sri Lankan levies and an EPC wrap, and its upper tail is wide. The choice
sits on the grid's lower boundary, so the optimum may be smaller still (or no battery, which
the PUCSL BESS tariff does not admit). The 12.5% curtailment scenario chooses 107 tables, 3.5 MW
AC and 3 MW. PR 3's hybrid sizing, re-run the same way, does not move (DC/AC 1.1, 5 MW / 24
MWh). The owner's "Maximize BESS" decision and this result conflict; see the PR's owner
decisions.

## The owner's battery and the after-tax objective (PR 7, 2026-11-01)

Work item: #1353 comment 6563070978. Owner decisions, verbatim: 1. committed size "Fix 5 MW / 20
MWh"; 2. objective "After-tax project NPV (Recommended)"; 4. solar basis "Keep ERA5, fix README
(Recommended)". Unchanged and confirmed: 3. levies "Prudent (current)"; 5. wind "Accept 40.57 GWh
(Recommended)"; 6. air density "Keep 1.15 (Recommended)"; 7. "Yes, east is shore".

**Objective.** The solar + BESS sizing now ranks on the P50 of the engine's **after-tax project
NPV** of the solar + BESS project scenario: every trial goes through
`analytics.evaluation_v14.evaluate_with_overrides`, whose project NPV discounts the CFADS after
the 30% corporate tax and the 10% CFADS haircut, less the capex, at the engine's own rate. P90
is reported beside it, and so is the unit's pre-tax NPV (PR 4's objective, still selectable in
`conf/blue_whale_solar_bess_project_sizing.yaml` and off by default).

**The battery is the owner's strategic choice, not the value-based size.** The project commits
BESS 5.0 MW / 20.0 MWh (4 h) with PV AC 5.0 MW, so reading A of the 10 MW limit sits at its
limit (5.0 + 5.0 = 10.0 MW). The PV DC for that battery comes from a reduced production run
(`conf/blue_whale_solar_bess_fixed_bess_sizing.yaml`; seed 20261101, the same 256 trials; every
whole table count from 134, DC/AC 1.0055, to the lot's maximum of 191 at this battery; 58 points,
15,022 evaluations, 724.7 s): **151 tables, 5.66552 MWp, DC/AC 1.1331**.

| PV tables (MWp) | DC/AC | After-tax project NPV P50 / P90 (USD) | Unit pre-tax NPV P50 / P90 (USD) | Equity IRR P50 |
|---|---|---|---|---|
| 134 (5.02768) | 1.0055 | -5,380,477 / -5,946,667 | -1,012,547 / -1,599,269 | -5.09% |
| 145 (5.44040) | 1.0881 | -5,334,185 / -5,912,640 | -881,587 / -1,470,292 | -4.49% |
| 148 (5.55296) | 1.1106 | -5,328,601 / -5,910,375 | -853,675 / -1,444,436 | -4.37% |
| **151 (5.66552), chosen** | **1.1331** | **-5,326,884 / -5,911,801** | **-829,383 / -1,421,478** | **-4.24%** |
| 152 (5.70304) | 1.1406 | -5,327,556 / -5,912,246 | -821,669 / -1,412,171 | -4.20% |
| 155 (5.81560) | 1.1631 | -5,330,070 / -5,915,507 | -806,780 / -1,386,760 | -4.11% |
| 160 (6.00320) | 1.2006 | -5,341,413 / -5,927,668 | -784,424 / -1,362,972 | -3.95% |
| 170 (6.37840) | 1.2757 | -5,375,348 / -5,980,237 | -768,460 / -1,349,668 | -3.72% |
| 191 (7.16632), lot maximum | 1.4333 | -5,537,751 / -6,164,183 | -847,442 / -1,445,723 | -3.46% |

The curve is flat near the choice: 151 tables is at least as good as 152 in 52.7% of paired
trials (by USD 316 at the median), and every count from 147 to 155 lies within USD 3,200 of it at
P50. No trial at any point has a project IRR. Under PR 4's objective (unit pre-tax NPV P50) the
same battery would take 171 tables; P90 after-tax prefers 148. Sensitivities (base case): the
12.5% curtailment scenario picks 152 tables, the 0.90 RTE case 146.

**The value-based size and the cost of the choice.** PR 4's full grid, re-run under the after-tax
objective (325 points x 256 trials, 84,175 evaluations, 3,922.8 s; every grid row identical to
PR 6's run), chooses **107 tables (4.01464 MWp), 3.5 MW AC and 1.0 MW / 4.0 MWh under both
readings**, the same size PR 6's unit pre-tax objective chose. It beats its runner-up (107
tables, 4.0 MW AC) in 100% of paired trials.

| Size | After-tax project NPV P50 / P90 (USD) | Unit pre-tax NPV P50 / P90 (USD) |
|---|---|---|
| Value-based: 107 tables, 3.5 MW AC, 1.0 MW / 4.0 MWh | -4,079,718 / -4,321,796 | -312,629 / -571,313 |
| **Committed: 151 tables, 5.0 MW AC, 5.0 MW / 20.0 MWh** | **-5,326,884 / -5,911,801** | **-829,383 / -1,421,478** |
| **Cost of the owner's choice** | **1,247,165 / 1,590,005** | **516,754 / 850,165** |

Committing 5 MW / 20 MWh gives up USD 1.25M of after-tax project NPV at P50 and USD 1.59M at
P90 against the value-based size. The figures are recorded in
`conf/blue_whale_solar_bess_fixed_bess_sizing.yaml` (`strategic_cost_usd`), and a test recomputes
them from the two committed summaries. Every eligible size on both grids has a negative P50
after-tax project NPV, so neither size is viable on these placeholder inputs.

**Solar basis.** ERA5 stays the basis; `inputs/solar_tmy/README.md` now says PVGIS-ERA5, not
SARAH3, citing #1540's finding, and reports the satellite figures (Global Solar Atlas PVOUT
+6.3%, about +9% GHI) as upside only. No data file changed.

## The turbine's shadow on the PV (input B33, 15.19.0, 2026-11-07)

Work item: #1353 comment 6568242480. Owner decisions, verbatim: "#1520 as is, Blue Whale PR
next" and, of the shadow work, "This PR has a material effect on Blue Whale" (2 Nov 2026).

**Method.** `solar_resource/pv_array_turbine_shading.py` runs #1518's shadow geometry
(`solar_resource/turbine_shading.py`: a tower strip and a projected rotor disc, both along the
sun ray) on each PV table of [`pv_bess_layout_lot5b.geojson`](pv_bess_layout_lot5b.geojson),
from the turbine in [`site_placeholder_lot5b.geojson`](site_placeholder_lot5b.geojson) and the
rotor and hub of `conf/blue_whale_wind_siting.yaml`. Every site input comes from those files, so
nothing in the code is specific to this site. Each table is sampled at 8 x 2 points, at the
TMY's half-hourly sun positions:

- the tower strip takes the whole beam;
- inside the rotor's shadow, and outside the tower strip, the turning blades take the blade
  solidity (0.04) of the beam;
- the rotor's yaw is weighted by the 130 m wind rose
  ([`met_mast_wind_rose_130m.csv`](met_mast_wind_rose_130m.csv), its 16 sectors folded onto 8
  orientations, since a disc and its reverse cast the same shadow).

The hourly retention, one less the shaded share of plane-of-array irradiance, multiplies the
plane-of-array irradiance that drives the PVWatts DC model, before clipping and before BESS
dispatch, in the unit runner and in all three sizings. The cell temperature stays on the
unshaded irradiance.

**Electrical mismatch: the optical floor.** A partial shadow across a string can cost more than
the light it blocks, through mismatch and bypass diodes, and field work reports MPPT
disturbance under turbine shadows (Dekker et al. 2023, J. Renewable Sustainable Energy 15,
063703). No published multiplier fits this array, and there is no string-level simulation
or site measurement, so the committed case applies none (`electrical_mismatch_multiplier: 1.0`).
A x3 stress is reported below. A string-level study or site measurement would replace the
floor.

**Result.** These are model estimates on placeholder inputs, not measurements.

| Array | Tables | Tower | Rotor (wind rose) | Optical loss | AC energy loss | Rotor yawed to the sun (sensitivity) |
|---|---|---|---|---|---|---|
| Solar + BESS project (committed) | 151 | 0.042% | 0.089% | **0.130%** | **0.136%** | 0.197% |
| Hybrid's unit (superseded) | 147 | 0.039% | 0.085% | 0.125% | 0.130% | 0.191% |

Losses are shares of the array's annual plane-of-array irradiance (optical) and of its AC
energy. The last column turns the rotor to face the sun's azimuth at every step, which is the
largest shadow a horizontal-axis rotor can cast. It is a sensitivity, not an upper bound on
the loss: the wind decides the yaw. #1518's sun-facing sphere case ("high") cannot happen
physically and is not quoted.

**Sizing.** All three sizings were re-run with the shadow on the same seed and trials. No size
changes: PR 3 keeps DC/AC 1.1 with 24 MWh; PR 4's value-based size stays 107 tables, 3.5 MW AC
and 1.0 MW / 4.0 MWh; the owner's battery keeps 151 tables at 5.0 MW AC. The owner's choice
now costs USD 1,251,428 of after-tax project NPV at P50 and 1,594,480 at P90 (was 1,247,165
and 1,590,005). The objective's P50 and P90 at every grid point move only by the shadow. The
equity figures reported beside them also take in #1398's debt-service shortfall carry, which
landed after the last runs. Some of the alternatives the full-grid summary reports (none
committed) move too:
- the best P50 unit pre-tax IRR moves from 191 tables, 6.0 MW AC and 2 MW / 8 MWh to the
  value-based size;
- the best P50 equity IRR moves to 191 tables at 6.0 MW AC with 4 MW / 16 MWh under reading A
  (was 5.0 MW AC with 5 MW / 20 MWh) and 5 MW / 20 MWh under reading B (was 6 MW / 24 MWh);
- the best P50 minimum DSCR under reading B moves from 4.0 to 3.5 MW AC.

The runs are at 391b0dc7 (all three summaries). Each summary's digest of the scenario file
differs from the committed scenario, because the scenario is written from the run, as on main.

**KPIs.** These run through `analytics.evaluation_v14.evaluate_with_overrides` in constant LKR,
base case only. The "before" values are main at 15.18.0 after #1398.

| Scenario | Project NPV (USD) | Equity NPV (USD) | Equity IRR | Min DSCR | Project IRR |
|---|---|---|---|---|---|
| Solar + BESS v0.4, optical floor | -4,997,611 (was -4,992,409) | -5,568,837 (was -5,564,410) | -8.44% (was -8.32%) | 0.8676 (was 0.8680) | undefined |
| Solar + BESS, x3 mismatch stress (not committed) | -5,008,092 | -5,577,755 | -8.69% | 0.8669 | undefined |
| Hybrid v0.9 (superseded) | -2,653,195 (was -2,649,382) | -5,058,080 (was -5,054,866) | 6.05% (unchanged to 2 dp) | 0.8678 | 8.73% (8.7315%, was 8.7349%) |
| Wind v0.3 | unchanged | unchanged | unchanged | unchanged | 10.81% |

Solar + BESS year 1: export 7,431.76 MWh (was 7,442.89), of which 6,799.68 MWh in the priority
window (was 6,803.29); revenue LKR 353.76M (was 354.10M). Under the x3 stress: export 7,409.52 MWh
and revenue LKR 353.08M.

**Limitations.** Diffuse and circumsolar irradiance are treated as unshaded, the ground is
flat, and the nacelle, hub overhang and tower taper are left out. The yaw follows the annual
wind rose, independent of hour and season. Shaded modules get no credit for running cooler.
The blade solidity is a time average with no blade planform. The electrical multiplier is a
declared treatment, not a simulation. Every one of these limitations is recorded in the
summary's `turbine_shading.limitations`. The losses are per table at its sample points, so
#1518's grid-edge truncation of a footprint (its review finding D-1) does not apply here.

## The turbine on DutchBay T2: layout, shading and sizing (15.22.0, 2026-11-07)

Work item: #1353 comment 6705598736. Owner decision, verbatim: "Blue Whale Turbine is replacing
the T2 Dutchbay turbine - its on the exact same location - if not, recalculate location to
match T2 location. As such wake does not apply" (2026-11-07). On wake from T1 and T3 she chose
"Zero wake, disclose T1/T3 risk" (open risk 2). The siting, flicker and wind figures for the
new position are in the sections above; the wind yield does not change.

**Layout.** The turbine now stands in the placeholder lot's north-east corner. The crane
hardstand (`site_fit.crane_pad_side`, new) goes on the tower's west side: on the east side it
would lie mostly outside the lot. This is an assumption until a crane plan exists. With the
tower, its exclusion and the hardstand in the corner, the lot holds **186 tables** at the owner's
5 MW / 20 MWh battery (191 before). The layout
([`pv_bess_layout_lot5b.geojson`](pv_bess_layout_lot5b.geojson)) and the hourly table
([`pv_bess_hourly_tmy.csv`](pv_bess_hourly_tmy.csv)) are regenerated.

**Shading.** The tower now stands nearer the array, so its shadow costs more. The method and
its limitations are unchanged (previous section). These are model estimates on placeholder
inputs, at the optical floor:

| Array | Tables | Tower | Rotor (wind rose) | Optical loss | AC energy loss | Rotor yawed to the sun (sensitivity) |
|---|---|---|---|---|---|---|
| Solar + BESS project (committed) | 152 | 0.082% | 0.121% | **0.203%** (was 0.130%) | **0.19%** (was 0.136%) | 0.258% |
| Hybrid's unit (superseded) | 147 | 0.076% | 0.115% | 0.192% (was 0.125%) | 0.18% (was 0.130%) | 0.243% |

**Sizing.** All three sizings were re-run on the same seed and trials. PR 3 keeps DC/AC 1.1
with 24 MWh. PR 4's value-based size stays 107 tables, 3.5 MW AC and 1.0 MW / 4.0 MWh. The
owner's battery moves from 151 to **152 tables (5.70304 MWp, DC/AC 1.1406)** at 5.0 MW AC
(`conf/blue_whale_solar_bess_fixed_bess_sizing.yaml`: every whole table count from 134 to 191,
of which 53 fit; 13,727 evaluations):

| PV tables (MWp) | DC/AC | After-tax project NPV P50 / P90 (USD) | Unit pre-tax NPV P50 / P90 (USD) | Equity IRR P50 |
|---|---|---|---|---|
| 134 (5.02768) | 1.0055 | -5,387,036 / -5,952,887 | -1,020,311 / -1,607,833 | -9.61% |
| 148 (5.55296) | 1.1106 | -5,335,273 / -5,917,521 | -863,948 / -1,453,787 | -7.63% |
| 151 (5.66552) | 1.1331 | -5,334,392 / -5,919,004 | -838,619 / -1,430,883 | -7.73% |
| **152 (5.70304), chosen** | **1.1406** | **-5,334,279 / -5,919,614** | **-831,885 / -1,421,663** | **-7.59%** |
| 153 (5.74056) | 1.1481 | -5,335,251 / -5,920,707 | -825,863 / -1,413,590 | -7.50% |
| 160 (6.00320) | 1.2006 | -5,348,600 / -5,935,362 | -794,204 / -1,372,569 | -7.04% |
| 186 (6.97872), lot maximum | 1.3957 | -5,498,250 / -6,123,830 | -832,635 / -1,423,465 | -5.23% |

The choice is a near tie: 152 tables is at least as good as 151 in 44.9% of paired trials, and
better by USD 392 at the median. Every count from 145 to 155 lies within USD 7,100 of it at P50.
The equity IRRs include #1398's debt-service shortfall carry, which landed after PR 7's run.
Sensitivities (base case): the 12.5% curtailment scenario picks 150 tables and the 0.90 RTE
case 146. The owner's choice now costs USD 1,253,066 of after-tax project NPV at P50 and
1,596,441 at P90 against the value-based size (was 1,251,428 and 1,594,480).

**Preview, not final.** These runs were made on #1561's head with this change applied; their
summaries record that local merge's `git_sha`, whose tree is this branch at the time. The
sizings are re-run once #1557 and the PUCSL O&M indexation land, and the figures here are
replaced then.

**KPIs.** Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case
only. "Was" is main at 15.19.0.

| Scenario | Project NPV (USD) | Equity NPV (USD) | Equity IRR | Min DSCR | Project IRR |
|---|---|---|---|---|---|
| Solar + BESS v0.5 | -4,998,968 (was -4,997,611) | -5,573,458 (was -5,568,837) | -8.12% (was -8.44%) | 0.8684 (was 0.8676) | undefined |
| Hybrid v0.10 (superseded) | -2,654,612 (was -2,653,195) | -5,059,274 (was -5,058,080) | 6.05% (unchanged to 2 dp) | 0.8678 | 8.73% (8.7303%, was 8.7315%) |
| Wind v0.3 | unchanged | unchanged | unchanged | unchanged | 10.81% |

The solar + BESS equity cash flows change sign more than once, so its equity IRR is not a
reliable ranking figure (audit residual L-13). Solar + BESS year 1: PV 8,676.59 MWh, export
7,479.55 MWh (was 7,431.76), of which 6,817.18 MWh in the priority window (was 6,799.68);
revenue LKR 355.27M (was 353.76M). The extra table outweighs the larger shadow.

## Latest run (the turbine on DutchBay T2, 15.22.0, 2026-11-07)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV (USD) | Equity NPV (USD) |
|---|---|---|---|---|---|
| Wind project (v0.3) | 10.81% (unchanged) | 8.63% | 0.868 | 69,109 | -1,737,634 |
| Solar + BESS project (v0.5, 5 MW / 20 MWh, 152 tables) | undefined (reported as 0.0) | -8.12% | 0.868 | -4,998,968 | -5,573,458 |
| Hybrid (v0.10, superseded) | 8.73% | 6.05% | 0.868 | -2,654,612 | -5,059,274 |

Every other input is still a placeholder, so these are not results.

## Earlier run (the turbine's shadow on the PV, 15.19.0, 2026-11-07)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only (after
#1398's debt-service shortfall carry, which moved the equity figures at 15.18.0):

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV (USD) | Equity NPV (USD) |
|---|---|---|---|---|---|
| Wind project (v0.3) | 10.81% (unchanged) | 8.63% | 0.868 | 69,109 | -1,737,634 |
| Solar + BESS project (v0.4, 5 MW / 20 MWh) | undefined (reported as 0.0) | -8.44% | 0.868 | -4,997,611 | -5,568,837 |
| Hybrid (v0.9, superseded) | 8.73% | 6.05% | 0.868 | -2,653,195 | -5,058,080 |

Every other input is still a placeholder, so these are not results.

## Earlier run (PR 7, the owner's battery, 15.18.0, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV (USD) | Equity NPV (USD) |
|---|---|---|---|---|---|
| Wind project (v0.3) | 10.81% (unchanged) | 9.06% | 0.868 | 69,109 | -1,489,263 |
| Solar + BESS project (v0.3, 5 MW / 20 MWh) | undefined (reported as 0.0) | -3.58% (was -11.32%) | 0.868 | -4,992,409 (was -4,027,656) | -5,395,403 (was -4,094,172) |
| Hybrid (v0.8, superseded) | 8.73% (unchanged) | 6.38% | 0.868 | -2,649,382 | -4,719,271 |

The larger battery earns the priority rate on 6,803 MWh in year 1 (was 1,481), which lifts the
equity IRR, but it costs USD 3.26M more capex, so the project NPV falls by USD 0.96M. Every other
input is still a placeholder, so these are not results.

## Earlier run (PR 6, capex blend and re-sizing, 15.17.0, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV (USD) | Equity NPV (USD) |
|---|---|---|---|---|---|
| Wind project (v0.3) | 10.81% (was 7.80%) | 9.06% (was 5.34%) | 0.868 | 69,109 (was -3,117,777) | -1,489,263 (was -4,679,503) |
| Solar + BESS project (v0.2, re-sized) | undefined (reported as 0.0) | -11.32% (was -3.28%) | 0.867 | -4,027,656 (was -4,771,737) | -4,094,172 (was -5,196,733) |
| Hybrid (v0.8, superseded) | 8.73% (was 6.90%) | 6.38% (was 4.33%) | 0.868 | -2,649,382 (was -5,718,864) | -4,719,271 (was -7,794,231) |

Every other input is still a placeholder, so these are not results.


## Earlier run (PR 5, met-mast wind resource, 15.16.0, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV (USD) | Equity NPV (USD) |
|---|---|---|---|---|---|
| Wind project (v0.2) | 7.80% (was 4.09%) | 5.34% (was 1.47%) | 0.868 | -3,117,777 (was -6,241,315) | -4,679,503 (was -7,318,639) |
| Hybrid (v0.7, superseded) | 6.90% (was 4.26%) | 4.33% (was 1.58%) | 0.867 | -5,718,864 (was -8,837,254) | -7,794,231 (was -10,441,094) |

The solar + BESS project does not move. Every other input is still a placeholder, so these are
not results.

## Earlier run (PR 4, two projects, 15.15.0, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV (USD) | Equity NPV (USD) |
|---|---|---|---|---|---|
| Wind project (v0.1) | 4.09% | 1.47% | 0.868 | -6,241,315 | -7,318,639 |
| Solar + BESS project (v0.1) | undefined (reported as 0.0) | -3.28% | 0.868 | -4,771,737 | -5,196,733 |
| Hybrid (v0.6, superseded) | 4.26% | 1.58% | 0.868 | -8,837,254 | -10,441,094 |

The hybrid does not move (its file gained only a header note). The two projects do not add up
to the hybrid: each carries its own USD 2.0M grid line and USD 0.15M a year of overhead, the
solar + BESS project is a different size, and it earns the priority rate only in 17:30-21:30.
The solar + BESS project has no project IRR: its 20-year CFADS sum stays below its capex, so
its NPV is negative at every discount rate. Every other input is still a placeholder, so these
are not results.

## Earlier run (v0.6, sized and priced solar + BESS unit, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:
project IRR 4.26% (was 3.58%), equity IRR 1.58% (was 0.92%), annual-view minimum DSCR 0.87,
project NPV USD -8.84M (was -10.20M). The rise is mostly lower capex: the unit now costs
USD 6.61M (PV 3.37M, BESS 3.24M) against USD 8.0M of placeholders (PV 4.25M, BESS 3.75M), on a
smaller battery. Every other input is still a placeholder, so these are not results.

## Earlier run (v0.5, solar + BESS unit, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:
project IRR 3.58% (was 3.15%), equity IRR 0.92% (was 0.51%), annual-view minimum DSCR 0.87.
Most of the rise is the BESS capex placeholder scaled to 30 MWh (USD 5.0M to 3.75M): with
the capex held at USD 23.6M the project IRR is 3.09%, so the unit's revenue on its own lowers
it by about 0.06 point. Every other input is still a placeholder, so these are not results.

## Earlier run (v0.4, wind yield and siting screen, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:
wind 9.5 MW at CF 37.43% (generation 14.5 MW), wind capex unchanged at the $1,300/kW
placeholder ($12.35M), tariff blend 24.77. Project IRR 3.15% (was 2.77%), equity IRR 0.51%
(was 0.06%), annual-view minimum DSCR 0.87. Holding the tariff at 24.76 gives 3.15% and
0.50%, so the re-blend moves IRR by under 0.01 point. Every other input is still a
placeholder, so these are not results.

## Earlier run (v0.3, researched inputs F02, F03 and F06, 2026-11-01)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR, base case only:
tariff 24.76 LKR/kWh (blended PUCSL 2026 FiT), BESS capacity charge LKR 1,752,500/MW-month,
LKR debt 13.39%, BESS 4 h. Project IRR 2.8%, equity IRR 0.1%, annual-view minimum DSCR
0.87. The lower BESS rate cuts year-1 BESS revenue from LKR 600m to LKR 210m (18% of year-1
revenue, was 44%); the higher tariff adds about LKR 170m of generation revenue. The FiT may
not apply if the < 10 MW limit counts per plant, and every other input is still a
placeholder, so these are not results. The sensitivities below were run on v0.2 and have not
been re-run.

## Earlier run (v0.2, placeholders, 2026-10-28)

Through `analytics.evaluation_v14.evaluate_with_overrides`, constant LKR:

| Case | Project IRR | Equity IRR |
|---|---|---|
| Base: 20.3 LKR/kWh, LKR debt 13.39%, BESS 4 h | 4.6% | 1.7% |
| Tariff 30 LKR/kWh | 8.0% | 5.5% |
| Tariff 45 LKR/kWh | 12.0% | 10.4% |
| Tariff 45 LKR/kWh, LKR debt 10% | 12.0% | 13.2% |
| No O&M escalation | 5.8% | 3.2% |
| BESS contract 20 years instead of 15 | 5.6% | 3.1% |
| BESS 5 h (50 MWh) | 4.1% | 1.3% |

Drivers: capex of about LKR 8.1 bn for 15 MW plus 40 MWh; the BESS capacity revenue (a
placeholder worth 44% of year-1 revenue) stopping after its 15-year contract; and LKR debt
at 13.39%, which costs more than the project earns, so leverage lowers equity returns.
The annual view reports a year-1 DSCR of 0.87 in every case, a first-year timing effect not
yet traced; the debt-period DSCR is 1.30. None of these figures is a result until the
priority-1 inputs replace the placeholders.

## Next steps

1. Owner supplies the priority-1 inputs in INPUTS_REQUIRED.md (and the input workbook).
2. Repeat the turbine screen and the PV and BESS fit on the surveyed boundary and vegetation
   line once B03 and B08 arrive.
3. Done in v0.6 (PR 3): inverter matching, cited PV and BESS pricing, and the Monte Carlo
   sizing (DC/AC 1.1, 24 MWh). Owner to confirm the 4 h rule and the 24 MWh battery against the
   6 h brief, and to supply EPC and BESS quotes (B15, B19). PR 2's notes, for the record: At DC/AC 1.2 the
   evening window is served by about 23.5 MWh of charge (20 MWh exported), and a 25 MWh
   battery earns slightly more than 30 MWh in year 1 (358.46 against 357.19 M LKR). At
   DC/AC 1.4 (7.02 MWp, 187 tables, which also fit) the unit earns 388.51 M LKR with 30 MWh.
4. Done in PR 4: the split into two projects and the solar + BESS sizing under the PUCSL 2026
   rules. Owner to decide the 10 MW reading (L01) and to obtain a PUCSL, NSO or counsel view on
   whether the turbine counts against the solar + BESS project; to confirm the committed
   reading A size; and to supply the PV EPC and BESS quotes (B15, B19).
5. Done in PR 5: the met-mast transfer. Owner to obtain the mast's documentation and a
   12-month record (met-mast evaluation section 9) and, for a bankable case, a site campaign
   (B07).
6. Done in PR 6: the wind and BESS capex blend, the solar resource at the site and the
   re-sizing. Quotes are still owed (B09, B15, B19).
7. Done in PR 7: the owner fixed the battery at 5 MW / 20 MWh ("Fix 5 MW / 20 MWh"), the sizing
   ranks on the after-tax project NPV, ERA5 stays the solar basis and the TMY README is
   corrected. The owner's choice costs USD 1.25M of after-tax project NPV at P50 (1.59M at P90)
   against the value-based 1 MW / 4 MWh. Owner to note that every size is value-negative on the
   placeholder inputs; quotes are still owed (B09, B15, B19).
8. Done in 15.19.0: the turbine's shadow on the PV (B33), on the optical floor. Owner to
   decide whether to commission a string-level shading study (the x3 stress costs a further
   USD 0.01M of project NPV) and to note that the shadow modelled here is optical only.
9. Replace placeholders in the scenarios, then run the v14 pipeline for base and P90 cases.
10. Assemble the DBPL feasibility study once the model has owner-sourced inputs.
