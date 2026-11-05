# Blue Whale: inputs required from the owner

Configuration under study (from PR 4, two separate projects on Lot 5B Plan 3641, Kalpitiya):
**a wind project of 1 x Envision EN-206/10.5 de-rated to 9.5 MW, built first, and a solar +
BESS project of 6.0032 MWp of JinkoSolar Tiger Neo 3.0 670 W at 5.0 MW AC with a 4.5 MW /
18 MWh (4 h) BESS charged only from that PV** (reading A of the 10 MW limit). Status and site
facts are in [STATUS.md](STATUS.md).

The scenarios `scenarios/blue_whale_wind_lot5b_2026.yaml` and
`scenarios/blue_whale_solar_bess_lot5b_2026.yaml` run today on placeholders; the combined
`scenarios/blue_whale_hybrid_lot5b_2026.yaml` (v0.6) is superseded but kept. Each
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

## C. Solar (the solar + BESS project)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B13 | Layout area available after setbacks and the turbine exclusion zone; fixed tilt or tracker | `conf/blue_whale_solar_bess.yaml` `array`, `land`, `site_fit` | Fixed tilt 8 degrees, 2P tables, pitch 6.74 m (GCR 0.71, a 2.0 m aisle assumed). With the turbine kept, the placeholder lot takes 191 tables (7.16632 MWp) at BESS powers of 2-9 MW, 192 at 1 MW and 189 at 10 MW (PR 4, recomputed; the container pad is a 6 h product's, power-bound at 4 h). The committed 160 tables fit with room to spare. Lagoon-side setback assumed equal to the 60 m sea setback. Every figure depends on B03 | 1 |
| B14 | Module and inverter selection, DC/AC ratio, PV AC | `conf/blue_whale_solar_bess.yaml` `module`, `array`, `pv_yield`; `conf/blue_whale_solar_bess_project_sizing.yaml` `recommendation`; `generation.technologies.solar` | Module chosen (owner): JinkoSolar Tiger Neo 3.0 670 W, datasheet-sourced. Inverter matched (PR 3): Huawei SUN2000-330KTL-H1, European efficiency 98.8%. PR 4's Monte Carlo (reading A) chooses 160 tables (6.0032 MWp) at 5.0 MW AC (DC/AC 1.2006, 17 inverters). Reading B would take 191 tables at 6.0 MW AC. Project export CF 0.182870 | 2 |
| B15 | Solar CAPEX (EPC quote or budget) | `generation.technologies.solar.capex_usd`; `conf/blue_whale_pv_bess_pricing.yaml` | Solar + BESS project: $3,652,472 (PR 4, cited price modes on 6.0032 MWp and 17 inverters: modules 0.110 + 0.010 delivery, BoP/EPC 0.462 per Wp, inverters 0.0311 per W AC). An EPC quote is still owed | 1 |
| B16 | Solar O&M cost | `opex.usd_per_year`; `conf/blue_whale_pv_bess_pricing.yaml` `opex` | USD 10/kWp-yr placeholder: $0.060M/yr on 6.0032 MWp (PR 4). Not sourced | 3 |
| B32 | Ground albedo and module height, for a bifacial gain | `conf/blue_whale_solar_bess.yaml` `pv_yield` | Not modelled: no basis, and the financed chain is monofacial (SOLAR-9) | 3 |
| B33 | PV output lost to the turbine's shadow | `losses.turbine_shading_pct` | Not modelled; #1520 (`solar_resource.turbine_shading`) estimates it once merged | 2 |

## D. BESS (4 h, charged from the PV; the solar + BESS project)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B17 | Use case: firming the wind and solar, night-peak export, or capacity service to CEB. This decides the revenue model (F05) | `bess_1.revenue.model` | Decided (owner, 2026-11-01): PV-charged export at the PUCSL priority rate. From PR 4 the battery discharges only 17:30-21:30; the 05:30-07:30 window is superseded (a 4 h battery has no remaining hours) | closed |
| B18 | Duration and power | `bess_1.power_mw`, `energy_mwh`, `duration_h` | Duration fixed at 4 h by the PUCSL 2026 methodology (s.5.1.1, s.5.2.1), energy = 4 x power, read as delivered energy. Power 4.5 MW (18 MWh) from PR 4's Monte Carlo under reading A; 5.5 MW (22 MWh) under reading B; revenue maximum 9 MW (36 MWh), allowed only under reading B. Owner to confirm | 1 |
| B19 | BESS CAPEX: cells, PCS, EMS, containers, augmentation plan | `bess_1.capex_usd`; `conf/blue_whale_pv_bess_pricing.yaml` `bess` | $2,430,000 (PR 4): USD 135.00/kWh all-in on 18 MWh, the public NSO 250 base (a 4 h-basis price, now applied at 4 h); Monte Carlo range 78.75-143.41. A quote is still owed | 1 |
| B20 | Round-trip efficiency, cycles per year, warranted fade, augmentation cost | `bess_1.revenue`, `conf/blue_whale_solar_bess_project_sizing.yaml` `unit_overrides`, `uncertainty` | RTE 0.85 AC-AC (repository value), from PR 4 all loss on charge (the PUCSL convention); Monte Carlo 0.82-0.88 (assumed); PUCSL's 0.90 reference case as a sensitivity. 352.7 equivalent full cycles/yr at 18 MWh. No fade in the base case; residual fade 0-2%/yr in the Monte Carlo (assumed; PUCSL's reference case uses 1.5%/yr). O&M USD 2.5/kWh-yr placeholder (PUCSL's reference case: 3% of capex) | 2 |
| B21 | BESS footprint and spacing: product, container count, fire separation | `conf/blue_whale_solar_bess.yaml` `bess_footprint` | 20-ft units of 5,015 kWh / 762 kVA (a 6 h product), 3 m apart (assumed); at 4 h the count is set by power (6 units at 4.5 MW). A 4 h product would need less land | 2 |
| B22 | Clock hours of the PUCSL Prioritized Feed-in Time, and whether PV exported in that window is paid the priority rate | `conf/blue_whale_pucsl_fit_2026.yaml` `priority_window`; `conf/blue_whale_solar_bess_project_sizing.yaml` `unit_overrides` | 17:30-21:30 (July 2026 consultation; Annex 2 states none; the methodology leaves the PFT to the SPPA). The rate follows the hour of export | 1 |

## E. Grid and project-wide

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B25 | Grid connection point: CEB substation, voltage (33 kV expected), line length, and any CEB grid study or connection offer | `project.grid_poi` | "TBD" | 1 |
| B26 | Grid, civils, development and owner's costs | `capex.usd_total` | $2.0M in EACH project (PR 4: separate SPPAs, separate connections assumed); the hybrid view carried $2.0M once | 1 |
| B27 | Export limit at the connection point, and expected curtailment | `project.curtailment_pct`; `conf/blue_whale_solar_bess_project_sizing.yaml` `unit_overrides`, `readings`, `curtailment_scenario` | Solar + BESS project: 10 MW (the standardised-PPA limit). Under reading A (committed) PV AC + BESS power is 9.5 MW, so the limit never binds. Scenario (not base): 12.5% of daytime direct PV export curtailed; the chosen sizes are unchanged under it | 2 |
| B28 | Insurance, security, SPV admin costs | `opex.usd_per_year` | $0.15M/yr with land, in EACH project (PR 4) | 2 |
| B29 | O&M escalation in LKR (contract indexation) | `opex.escalation_pct` | 5%/yr (CBSL inflation target) | 2 |
| B30 | Target COD and construction period | `project.cod_year`, `timeline.construction_years` | Wind 2028, solar + BESS 2029 (the turbine is built first; owner, 2026-11-01); 1 year each | 1 |
| B31 | Permits status: SLSEA provisional approval, CC&CRMD, CEA (IEE/EIA), Pradeshiya Sabha, UDA, CAA (turbine height), Wildlife and Forest | feasibility chapter | none | 2 |

## F. Financial term sheets

### Offtake (PPA / tariff)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F01 | PPA term (years) | `tariff.ppa_term_years`, `project.life_years` | 20 in each project (the CEB standardised PPA draft; the PUCSL methodology's s.3.1 tariff rests on a 20-year cash flow) | 1 |
| F02 | Offtaker and tender route (CEB competitive tender, SLSEA standardised tariff, or private offtake) | `ppa.offtaker` | National System Operator (Private) Limited, from 9 Mar 2026 (Gazette 2479/36); researched 2026-11-01, route still to confirm | 1 |
| F03 | Tariff (LKR/kWh) for wind and solar energy | `tariff.lkr_per_kwh` | PUCSL 2026 FiT (Annex 2): wind project 25.73; solar + BESS project 20.72 on every kWh plus the BESS premium (F06). The hybrid's blend (24.786) is superseded | 1 |
| F04 | Tariff structure: fixed, CPI-indexed, USD-linked, tiered; any escalation | `tariff.tariff_type` | fixed | 1 |
| F05 | BESS revenue model: capacity charge, energy tariff for night-peak export, or none (firming only) | `bess_1.revenue.model` | `energy_tariff` from the hourly dispatch of the PV-charged BESS (owner, 2026-11-01). Was capacity charge | 2 |
| F06 | BESS rate: LKR/MW-month capacity charge, or LKR/kWh discharge tariff, and its contract term | `bess_1.revenue.*`; `conf/blue_whale_pucsl_fit_2026.yaml` | PUCSL Annex 2 (25 Aug 2026), ground solar + BESS: 50.10 in the priority window for 15 years, 20.72 otherwise. Carried as a 29.38 premium on 417.3444 engine cycles (an engine mapping of the 6,385 MWh priority export, not a cycle count) | 1 |
| F07 | Take-or-pay or deemed-energy terms for curtailment | revenue protection | none | 2 |
| F08 | Payment terms, security (letter of credit, Treasury guarantee) | `ppa.payment_terms_days` | 30 days | 2 |

### Legal

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| L01 | Whether the 10 MW standardised-PPA limit is read as PV AC + BESS power (reading A) or as export at the connection point (reading B), and whether the 9.5 MW turbine on the same lot counts against the solar + BESS project as a "contiguous location" on a "cumulative basis" (Act No. 36 of 2024, s.11(3) proviso; Amendment Act No. 14 of 2025, s.11(3)). A PUCSL or NSO ruling, or counsel's opinion | `conf/blue_whale_solar_bess_project_sizing.yaml` `readings`; both new scenarios | Both readings modelled (owner: "Model both, flag it"); reading A committed. The cumulative question is open: if the turbine counts, the pair exceeds 10 MW at every size | 1 |

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
