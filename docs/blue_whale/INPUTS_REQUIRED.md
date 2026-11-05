# Blue Whale hybrid: inputs required from the owner

Configuration under study: **1 x Envision EN-206/10.5 wind turbine de-rated to 9.5 MW, and a
solar + BESS unit of 5 MW AC (6.0032 MWp of JinkoSolar Tiger Neo 3.0 670 W) with a 5 MW x 6 h
(30 MWh) BESS charged only from that PV**, on Lot 5B Plan 3641, Kalpitiya. Status and site facts are in
[STATUS.md](STATUS.md).

The scenario `scenarios/blue_whale_hybrid_lot5b_2026.yaml` runs today on placeholders. Each
row below names the field it replaces and the placeholder now standing in for it. An input
supplied as a document (quote, study, term sheet) goes under `docs/source_materials/`
under `DATA-01`, with its manifest, before a value derived from it enters the YAML.

Priority: **1** blocks a credible screening result. **2** is needed for a bankable
feasibility study. **3** refines the result.

## A. Project, site and land

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B01 | Project company: legal name, PV number, shareholders, and its relationship to Blue Whale Resort (Pvt) Ltd | `project.developer` | "Blue Whale Limited (to be confirmed)" | 1 |
| B02 | Land arrangement: lease or transfer from the landowner, term, annual rent or premium | `opex` land lease line | inside the 0.15M overhead line | 1 |
| B03 | Site survey with coordinates (WGS84) of the boundary and proposed turbine, PV and BESS positions, and the permanent vegetation line or back-dune toe on the beach | `conf/blue_whale_wind_siting.yaml` `site`; `docs/blue_whale/site_placeholder_lot5b.geojson` | Assumed 9.3077 ha square on the OpenStreetMap coastline at DutchBay T2's latitude, flagged `surveyed: false` (owner, 2026-11-01). Every wind, setback and flicker figure depends on it | 1 |
| B04 | The 9 title documents missing from the scan, and a current Land Registry search on folio D 65/97 | lender due diligence | n/a | 2 |

## B. Wind (1 x 9.5 MW)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B05 | Turbine: the owner chose the Envision EN-206/10.5 de-rated to 9.5 MW at 130 m hub (2026-11-01). Still owed: the OEM's de-rate mode, IEC class, foundation and hardstand footprint | `generation.technologies.wind`; `conf/blue_whale_wind_siting.yaml` `turbine`; `conf/blue_whale_solar_bess.yaml` `site_fit` | De-rate modelled as the curve clipped at 9,500 kW; tower centre on the setback line (no foundation radius). For the PV fit: a 30 m foundation and a 40 x 80 m crane hardstand east of it | 1 |
| B06 | Certified power curve and thrust curve for that model, and for the 9.5 MW mode | read at run time from a private path (`BLUE_WHALE_POWER_CURVE_CSV`) | PMD-004447 Rev A (10.5 MW, held privately under `KALPITIYA60MW-WIND-HANDLING-2026-09-21`; owner, 2026-11-01). A curve for the de-rated mode is still owed | 1 |
| B07 | Wind data at the site: any met mast or LiDAR campaign. Failing that, confirm use of the DutchBay ERA5 series and met mast 617725 | `generation.technologies.wind.capacity_factor` | 0.374256 net (31.15 GWh): the private curve over the DutchBay ERA5 Weibull at 130 m, losses 7.77%, no wake | 1 |
| B08 | Setbacks to the sea, lagoon, streams, roads and resort buildings, and any CC&CRMD guidance received; whether the rotor may overhang the coastal reservation, the sea and land outside the lot; positions of buildings and dwellings for shadow flicker | `conf/blue_whale_wind_siting.yaml` `coastal_setback`, `tip_setback`, `shadow_flicker` | Coast 60 m (CZ&CRMP 2024-2029 segment 2) from the OSM coastline; boundary 1.0 x tip height (233 m); no receptors, so flicker is reported at the lot boundary | 1 |
| B09 | Wind CAPEX: turbine supply, foundation, crane and transport, BOP (quote or budget) | `generation.technologies.wind.capex_usd` | $12.35M ($1,300/kW x 9.5 MW) | 1 |
| B10 | Wind O&M: OEM service agreement price and term | `opex.usd_per_year` | $0.35M/yr | 2 |
| B11 | Transport route survey: road access over Lot 5I and Lot 3 of Plan 3215, or the Lot 5D jetty | logistics risk | none | 2 |
| B12 | Degradation and availability guarantees | `degradation`, `availability_pct` | 0.6%/yr, 97% | 3 |

## C. Solar (5 MW AC, one unit with the BESS)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B13 | Layout area available after setbacks and the turbine exclusion zone; fixed tilt or tracker | `conf/blue_whale_solar_bess.yaml` `array`, `land`, `site_fit` | Fixed tilt 8 degrees, 2P tables, pitch 6.74 m (GCR 0.71, a 2.0 m aisle assumed); 4.10 ha fenced; fits the placeholder lot, with 191 table positions against 160 needed (v0.5). Lagoon-side setback assumed equal to the 60 m sea setback. Every figure depends on B03 | 1 |
| B14 | Module and inverter selection, DC/AC ratio | `conf/blue_whale_solar_bess.yaml` `module`, `array`, `pv_yield`; `generation.technologies.solar.capacity_factor` | Module chosen (owner): JinkoSolar Tiger Neo 3.0 670 W, datasheet-sourced. DC/AC 1.20 (DutchBay basis); PVWatts inverter at 96% until PR 3 picks one. String of 28 at a 15 C design minimum (assumed). Unit CF 0.173144 (v0.5) | 2 |
| B15 | Solar CAPEX (EPC quote or budget) | `generation.technologies.solar.capex_usd` | $4.25M, unchanged: $850/kW AC on 5 MW ($708/kWp on 6.0032 MWp). PR 3 prices it | 1 |
| B16 | Solar O&M cost | `opex.usd_per_year` | $0.05M/yr | 3 |
| B32 | Ground albedo and module height, for a bifacial gain | `conf/blue_whale_solar_bess.yaml` `pv_yield` | Not modelled: no basis, and the financed chain is monofacial (SOLAR-9) | 3 |
| B33 | PV output lost to the turbine's shadow | `losses.turbine_shading_pct` | Not modelled; #1520 (`solar_resource.turbine_shading`) estimates it once merged | 2 |

## D. BESS (5 MW x 6 h, charged from the PV)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B17 | Use case: firming the wind and solar, night-peak export, or capacity service to CEB. This decides the revenue model (F05) | `bess_1.revenue.model` | Decided (owner, 2026-11-01): PV-charged export, 17:30-21:30 at the priority rate and 05:30-07:30 at the other rate; `energy_tariff` from the hourly dispatch | closed |
| B18 | Duration | `bess_1.energy_mwh`, `duration_h` | 30 MWh, 6 h (owner, 2026-11-01). The PV fills it on few days; PR 3 sizes it | 1 |
| B19 | BESS CAPEX: cells, PCS, EMS, containers, augmentation plan | `bess_1.capex_usd` | $3.75M: the unchanged ~$125/kWh basis scaled to 30 MWh (was $5.0M on 40 MWh). PR 3 prices it | 1 |
| B20 | Round-trip efficiency, cycles per year, warranted fade, augmentation cost | `bess_1.revenue`, `conf/blue_whale_solar_bess.yaml` `bess` | RTE 0.85 AC-AC (repository value), all loss on discharge; 289 equivalent full cycles/yr from the dispatch; cell fade and augmentation not modelled; 30 MWh treated as usable | 2 |
| B21 | BESS footprint and spacing: product, container count, fire separation | `conf/blue_whale_solar_bess.yaml` `bess_footprint` | 7 x 20-ft units of 5,015 kWh / 762 kVA, 3 m apart (assumed) | 2 |
| B22 | Clock hours of the PUCSL Prioritized Feed-in Time, and whether PV exported in that window is paid the priority rate | `conf/blue_whale_solar_bess.yaml` `dispatch.windows`, `tariff` | 17:30-21:30 (July 2026 consultation; Annex 2 states none). The rate follows the hour of export | 1 |

## E. Grid and project-wide

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B25 | Grid connection point: CEB substation, voltage (33 kV expected), line length, and any CEB grid study or connection offer | `project.grid_poi` | "TBD" | 1 |
| B26 | Grid, civils, development and owner's costs | `capex.usd_total` | $2.0M | 1 |
| B27 | Export limit at the connection point, and expected curtailment | `project.curtailment_pct`; `conf/blue_whale_solar_bess.yaml` `dispatch.export_limit_mw` | 0%; the solar + BESS unit is held to a combined 5 MW (read as its FiT plant capacity), which curtails nothing in the TMY year | 2 |
| B28 | Insurance, security, SPV admin costs | `opex.usd_per_year` | $0.15M/yr with land | 2 |
| B29 | O&M escalation in LKR (contract indexation) | `opex.escalation_pct` | 5%/yr (CBSL inflation target) | 2 |
| B30 | Target COD and construction period | `project.cod_year`, `timeline.construction_years` | 2028, 1 year | 1 |
| B31 | Permits status: SLSEA provisional approval, CC&CRMD, CEA (IEE/EIA), Pradeshiya Sabha, UDA, CAA (turbine height), Wildlife and Forest | feasibility chapter | none | 2 |

## F. Financial term sheets

### Offtake (PPA / tariff)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F01 | PPA term (years) | `tariff.ppa_term_years`, `project.life_years` | 20 | 1 |
| F02 | Offtaker and tender route (CEB competitive tender, SLSEA standardised tariff, or private offtake) | `ppa.offtaker` | National System Operator (Private) Limited, from 9 Mar 2026 (Gazette 2479/36); researched 2026-11-01, route still to confirm | 1 |
| F03 | Tariff (LKR/kWh) for wind and solar energy, and whether it is one blended tariff or two | `tariff.lkr_per_kwh` | 24.749 (v0.5): energy-weighted blend of the PUCSL 2026 FiT, wind 25.73 and the solar + BESS unit's other-period 20.72; the priority 50.10 is carried as the BESS premium (researched 2026-11-01). Open: whether the < 10 MW limit counts per technology, per unit or per plant | 1 |
| F04 | Tariff structure: fixed, CPI-indexed, USD-linked, tiered; any escalation | `tariff.tariff_type` | fixed | 1 |
| F05 | BESS revenue model: capacity charge, energy tariff for night-peak export, or none (firming only) | `bess_1.revenue.model` | `energy_tariff` from the hourly dispatch of the PV-charged BESS (owner, 2026-11-01). Was capacity charge | 2 |
| F06 | BESS rate: LKR/MW-month capacity charge, or LKR/kWh discharge tariff, and its contract term | `bess_1.revenue.*`; `conf/blue_whale_solar_bess.yaml` `tariff` | PUCSL Annex 2 (25 Aug 2026), ground solar + BESS: 50.10 in the priority window for 15 years, 20.72 otherwise. Carried as a 29.38 premium on 267.0335 cycles (v0.5). Was LKR 1,752,500/MW-month (NSO 250 MW bid-clearing level) | 1 |
| F07 | Take-or-pay or deemed-energy terms for curtailment | revenue protection | none | 2 |
| F08 | Payment terms, security (letter of credit, Treasury guarantee) | `ppa.payment_terms_days` | 30 days | 2 |

### Debt

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F10 | Lenders being approached. Currency is settled: fully LKR funded (owner, 2026-10-28) | `Financing_Terms.mix` | 100% LKR (owner) | 1 |
| F11 | LKR loan rate: base (e.g. AWPR) and margin, fixed or floating, reset terms | `Financing_Terms.rates.lkr_nominal` | 13.39% (UIP-implied, not a quote) | 1 |
| F12 | Maximum gearing | `Financing_Terms.debt_ratio` | 70% | 1 |
| F13 | Tenor and grace (interest-only) period | `tenor_years`, `interest_only_years` | 12 years, 1 year | 1 |
| F14 | Repayment profile: sculpted to DSCR or fixed annuity | `amortization_style` | auto (sculpted) | 2 |
| F15 | Sizing and lock-up DSCR, default DSCR | `target_dscr`, `min_dscr` | 1.30, 1.20 | 1 |
| F16 | Reserves: DSRA months, MRA for BESS augmentation | `reserves.dsra_months` | 6 months | 2 |
| F17 | Fees: upfront, commitment, agency | `fees.upfront_pct` | 1% upfront | 2 |
| F18 | Interest-rate hedge, if the LKR loan floats; FX cover only for USD-priced equipment during construction | debt cost | none | 2 |

### Equity and returns

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F20 | Equity sponsors and shares; any shareholder loan | equity structure | none | 2 |
| F21 | Land contributed as equity, and at what value | `capex.usd_total` | not included | 2 |
| F27 | Target equity IRR in LKR (hurdle) | `returns.equity_discount_rate`, `wacc.cost_of_equity` | 12% (a USD figure; an LKR hurdle is higher) | 1 |

### Macro, tax and incentives

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F25 | USD/LKR for converting USD-priced capex quotes (the model runs in constant LKR) | `fx.start_lkr_per_usd` | 333.79 (2026-Q2) | 2 |
| F30 | BOI status and any tax holiday or concession | `tax.tax_holiday_*` | none | 2 |
| F31 | Corporate tax rate and any special regime | `tax.corporate_tax_rate` | 30% | 3 |
