# Blue Whale: inputs required from the owner

Configuration under study (from PR 4, two separate projects on Lot 5B Plan 3641, Kalpitiya):
**a wind project of 1 x Envision EN-206/10.5 de-rated to 9.5 MW, built first, and a solar +
BESS project of 5.66552 MWp of JinkoSolar Tiger Neo 3.0 670 W at 5.0 MW AC with a 5.0 MW /
20.0 MWh (4 h) BESS charged only from that PV** (PR 7: the battery is the owner's strategic
choice, "Fix 5 MW / 20 MWh", and the PV DC is chosen for it on the P50 after-tax project NPV; the
value-based size is 4.01464 MWp at 3.5 MW AC with 1.0 MW / 4.0 MWh, USD 1.25M better at P50; PR 4
had 6.0032 MWp, 5.0 MW AC and 4.5 MW / 18 MWh). Status and site
facts are in [STATUS.md](STATUS.md).

The scenarios `scenarios/blue_whale_wind_lot5b_2026.yaml` and
`scenarios/blue_whale_solar_bess_lot5b_2026.yaml` run today on placeholders; the combined
`scenarios/blue_whale_hybrid_lot5b_2026.yaml` (v0.8) is superseded but kept. Each
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
| B07 | Wind data at the site: any met mast or LiDAR campaign; for met mast 617725, its documentation (site identity, sensors, calibration, logger, flags) and a 12-month or longer record | `generation.technologies.wind.capacity_factor` | 0.487560 net (40.57 GWh, PR 5): met mast 617725 long-term corrected against NASA POWER / MERRA-2 and transferred 26.7 km to the turbine, losses 7.77%, no wake; not lender-grade (was 0.374256 on the DutchBay ERA5 Weibull) | 1 |
| B08 | Setbacks to the sea, lagoon, streams, roads and resort buildings, and any CC&CRMD guidance received; whether the rotor may overhang the coastal reservation, the sea and land outside the lot; positions of buildings and dwellings for shadow flicker | `conf/blue_whale_wind_siting.yaml` `coastal_setback`, `tip_setback`, `shadow_flicker` | Coast 60 m (CZ&CRMP 2024-2029 segment 2) from the OSM coastline; boundary 1.0 x tip height (233 m); no receptors, so flicker is reported at the lot boundary | 1 |
| B09 | Wind CAPEX: turbine supply, foundation, crane and transport, BOP (quote or budget) | `generation.technologies.wind.capex_usd` | $8,899,980 (PR 6): USD 936.84/kW x 9.5 MW, the blended single-turbine all-in mode (range 728.16-1,341.16 USD/kW; `conf/blue_whale_capex_solar_resource.yaml`, `docs/blue_whale/CAPEX_AND_SOLAR_RESOURCE_METHODS.md`). A blend that includes private commercial inputs, published on the owner's decision of 2026-11-01 (#1353 comment 6556975196). Was $12.35M ($1,300/kW placeholder). A quote is still owed | 1 |
| B10 | Wind O&M: OEM service agreement price, term and currency | `opex.currency_split.components` `wind_om` | $0.35M/yr, 70% USD / 30% LKR (owner, 2026-11-02; no OEM has priced a wind LTSA in either corpus) | 2 |
| B11 | Transport route survey: road access over Lot 5I and Lot 3 of Plan 3215, or the Lot 5D jetty | logistics risk | none | 2 |
| B12 | Degradation and availability guarantees | `degradation`, `availability_pct` | 0.6%/yr, 97% | 3 |

## C. Solar (the solar + BESS project)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B13 | Layout area available after setbacks and the turbine exclusion zone; fixed tilt or tracker | `conf/blue_whale_solar_bess.yaml` `array`, `land`, `site_fit` | Fixed tilt 8 degrees, 2P tables, pitch 6.74 m (GCR 0.71, a 2.0 m aisle assumed). With the turbine kept, the placeholder lot takes 191 tables (7.16632 MWp) at BESS powers of 2-9 MW, 192 at 1 MW and 189 at 10 MW (PR 4, recomputed; the container pad is a 6 h product's, power-bound at 4 h). The committed 151 tables (PR 7; 107 in PR 6, 160 in PR 4) fit, 40 below the 191-table maximum at 5 MW. Lagoon-side setback assumed equal to the 60 m sea setback. Every figure depends on B03 | 1 |
| B14 | Module and inverter selection, DC/AC ratio, PV AC | `conf/blue_whale_solar_bess.yaml` `module`, `array`, `pv_yield`; `conf/blue_whale_solar_bess_project_sizing.yaml` `recommendation`; `generation.technologies.solar` | Module chosen (owner): JinkoSolar Tiger Neo 3.0 670 W, datasheet-sourced. Inverter matched (PR 3): Huawei SUN2000-330KTL-H1, European efficiency 98.8%. PR 7: PV AC 5.0 MW (reading A at its 10 MW limit with the owner's 5 MW battery) and 151 tables (5.66552 MWp, DC/AC 1.1331, 17 inverters), chosen on the P50 after-tax project NPV by `conf/blue_whale_solar_bess_fixed_bess_sizing.yaml` (PR 6: 107 tables at 3.5 MW AC; PR 4: 160 tables, 5.0 MW AC). Project export CF 0.169675 with the turbine's shadow (B33; 0.169929 before) | 2 |
| B15 | Solar CAPEX (EPC quote or budget) | `generation.technologies.solar.capex_usd`; `conf/blue_whale_pv_bess_pricing.yaml` | Solar + BESS project: $3,455,943 (PR 7 size; PR 3's cited price modes, unchanged, on 5.66552 MWp and 17 inverters: modules 0.110 + 0.010 delivery, BoP/EPC 0.462 per Wp, inverters 0.0311 per W AC; was $2,448,480 on 4.01464 MWp in PR 6). An EPC quote is still owed | 1 |
| B16 | Solar O&M cost | `opex.currency_split.components` `solar_om`; `conf/blue_whale_pv_bess_pricing.yaml` `opex` | USD 10/kWp-yr placeholder: $0.057M/yr on 5.66552 MWp (PR 7 size), in LKR. Not sourced | 3 |
| B32 | Ground albedo and module height, for a bifacial gain | `conf/blue_whale_solar_bess.yaml` `pv_yield` | Not modelled: no basis, and the financed chain is monofacial (SOLAR-9) | 3 |
| B33 | PV output lost to the turbine's shadow | `conf/blue_whale_solar_bess.yaml` `pv_yield.turbine_shading` | CLOSED (15.19.0, model estimate): `solar_resource.pv_array_turbine_shading` runs #1518's shadow geometry on each PV table of the layout, with rotor yaw weighted by the 130 m wind rose, and derates the hourly plane-of-array irradiance before BESS dispatch. Solar + BESS project (151 tables): 0.130% of the array's plane-of-array irradiance and 0.136% of its AC energy, on the optical floor (no electrical-mismatch uplift; a x3 stress gives 0.408% of AC energy). Owner may supply a string-level simulation or site measurement to replace the floor | 2 |

## D. BESS (4 h, charged from the PV; the solar + BESS project)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B17 | Use case: firming the wind and solar, night-peak export, or capacity service to CEB. This decides the revenue model (F05) | `bess_1.revenue.model` | Decided (owner, 2026-11-01): PV-charged export at the PUCSL priority rate. From PR 4 the battery discharges only 17:30-21:30; the 05:30-07:30 window is superseded (a 4 h battery has no remaining hours) | closed |
| B18 | Duration and power | `bess_1.power_mw`, `energy_mwh`, `duration_h` | Duration fixed at 4 h by the PUCSL 2026 methodology (s.5.1.1, s.5.2.1), energy = 4 x power, read as delivered energy. Decided (owner, 2026-11-01, #1353 comment 6563070978): "Fix 5 MW / 20 MWh", a strategic choice. The value-based size under the after-tax objective is 1.0 MW / 4.0 MWh (PR 7's re-run of the full grid; PR 6 chose the same on unit pre-tax NPV), and the owner's battery costs USD 1,247,165 of after-tax project NPV at P50 (1,590,005 at P90). Revenue maximum 9 MW (36 MWh), allowed only under reading B | closed |
| B19 | BESS CAPEX: cells, PCS, EMS, containers, augmentation plan | `bess_1.capex_usd`; `conf/blue_whale_pv_bess_pricing.yaml` `bess` | $2,814,800 (PR 7 size): USD 140.74/kWh all-in on 20 MWh (PR 6's price), the blended mode (range 129.13-202.51; `conf/blue_whale_capex_solar_resource.yaml`): China FOB system prices blended with the Envision offers and a second OEM quotation, landed with PAL 5% + SSCL 2.5%, BoP, EPC 8%, augmentation and land. A blend that includes private commercial inputs, published on the owner's decision of 2026-11-01 (#1353 comment 6556975196). Was $562,960 on 4 MWh (PR 6) and $2,430,000 (USD 135.00/kWh on 18 MWh, PR 4). A quote is still owed | 1 |
| B20 | Round-trip efficiency, cycles per year, warranted fade, augmentation cost | `bess_1.revenue`, `conf/blue_whale_solar_bess_project_sizing.yaml` `unit_overrides`, `uncertainty` | RTE 0.85 AC-AC (repository value), from PR 4 all loss on charge (the PUCSL convention); Monte Carlo 0.82-0.88 (assumed); PUCSL's 0.90 reference case as a sensitivity. 338.5 equivalent full cycles/yr at 20 MWh (PR 7; 364.3 at 4 MWh in PR 6, 352.7 at 18 MWh in PR 4). No fade in the base case; residual fade 0-2%/yr in the Monte Carlo (assumed; PUCSL's reference case uses 1.5%/yr). O&M from 15.20.0 at USD 1.80/kWh-yr of DC installed (owner, 2026-11-02), converted to LKR at the wind project's value date, 333.79 (owner, 2026-11-07), on 22,000 kWh DC (20.0 MWh plus an assumed 10% DC oversize, until the supplier states the DC capacity); the sizing runs still priced the USD 2.5/kWh-yr placeholder (PUCSL's reference case: 3% of capex) | 2 |
| B21 | BESS footprint and spacing: product, container count, fire separation | `conf/blue_whale_solar_bess.yaml` `bess_footprint` | 20-ft units of 5,015 kWh / 762 kVA (a 6 h product), 3 m apart (assumed); at 4 h the count is set by power (7 units at 5 MW, PR 7; 6 at 4.5 MW). A 4 h product would need less land | 2 |
| B22 | Clock hours of the PUCSL Prioritized Feed-in Time, and whether PV exported in that window is paid the priority rate | `conf/blue_whale_pucsl_fit_2026.yaml` `priority_window`; `conf/blue_whale_solar_bess_project_sizing.yaml` `unit_overrides` | 17:30-21:30 (July 2026 consultation; Annex 2 states none; the methodology leaves the PFT to the SPPA). The rate follows the hour of export | 1 |

## E. Grid and project-wide

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B25 | Grid connection point: CEB substation, voltage (33 kV expected), line length, and any CEB grid study or connection offer | `project.grid_poi` | "TBD" | 1 |
| B26 | Grid, civils, development and owner's costs | `capex.usd_total` | $2.0M in EACH project (PR 4: separate SPPAs, separate connections assumed); the hybrid view carried $2.0M once | 1 |
| B27 | Export limit at the connection point, and expected curtailment | `project.curtailment_pct`; `conf/blue_whale_solar_bess_project_sizing.yaml` `unit_overrides`, `readings`, `curtailment_scenario` | Solar + BESS project: 10 MW (the standardised-PPA limit). Under reading A (committed) PV AC + BESS power is 10.0 MW (PR 7: 5.0 + 5.0, at the limit, which the limit admits), so export cannot exceed it. Scenario (not base): 12.5% of daytime direct PV export curtailed; the chosen sizes are unchanged under it | 2 |
| B28 | Insurance, security, SPV admin costs | `opex.usd_per_year` | $0.15M/yr with land, in EACH project (PR 4) | 2 |
| B29 | O&M escalation in LKR (contract indexation) | `opex.currency_split.lkr_escalation_pct` (and `opex.escalation_pct`, which must equal it) | 5%/yr (CBSL inflation target), on the LKR share | 2 |
| B34 | Opex currency split: the USD share of each opex line, USD O&M inflation, and the LKR depreciation the USD share bears | `opex.currency_split` | Wind 49% USD, solar + BESS 0% USD (from B10 and B20); USD 2.5%/yr (placeholder); depreciation derived by relative PPP from the two inflation inputs, 2.44%/yr (owner, 2026-11-07; was 5.89%/yr, the DutchBay cases' BIS 2005-2026 nominal rate). Owner rule of 2026-11-02 | 2 |
| B30 | Target COD and construction period | `project.cod_year`, `timeline.construction_years` | Wind 2028, solar + BESS 2029 (the turbine is built first; owner, 2026-11-01); 1 year each | 1 |
| B31 | Permits status: SLSEA provisional approval, CC&CRMD, CEA (IEE/EIA), Pradeshiya Sabha, UDA, CAA (turbine height), Wildlife and Forest | feasibility chapter | none | 2 |

## F. Financial term sheets

### Offtake (PPA / tariff)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F01 | PPA term (years) | `tariff.ppa_term_years`, `project.life_years` | 20 in each project (the CEB standardised PPA draft; the PUCSL methodology's s.3.1 tariff rests on a 20-year cash flow) | 1 |
| F02 | Offtaker and tender route (CEB competitive tender, SLSEA standardised tariff, or private offtake) | `ppa.offtaker` | National System Operator (Private) Limited, from 9 Mar 2026 (Gazette 2479/36); researched 2026-11-01, route still to confirm | 1 |
| F03 | Tariff (LKR/kWh) for wind and solar energy | `tariff.lkr_per_kwh` | PUCSL 2026 FiT (Annex 2): wind project 25.73; solar + BESS project 20.72 on every kWh plus the BESS premium (F06). The hybrid's blend (24.97218) is superseded | 1 |
| F04 | Tariff structure: fixed, CPI-indexed, USD-linked, tiered; any escalation | `tariff.tariff_type` | fixed | 1 |
| F05 | BESS revenue model: capacity charge, energy tariff for night-peak export, or none (firming only) | `bess_1.revenue.model` | `energy_tariff` from the hourly dispatch of the PV-charged BESS (owner, 2026-11-01). Was capacity charge | 2 |
| F06 | BESS rate: LKR/MW-month capacity charge, or LKR/kWh discharge tariff, and its contract term | `bess_1.revenue.*`; `conf/blue_whale_pucsl_fit_2026.yaml` | PUCSL Annex 2 (25 Aug 2026), ground solar + BESS: 50.10 in the priority window for 15 years, 20.72 otherwise. Carried as a 29.38 premium on 399.9815 engine cycles (an engine mapping of the 6,800 MWh year-1 priority export at 20 MWh, not a cycle count; 400.1935 and 6,803 MWh before the turbine's shadow, B33) | 1 |
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
