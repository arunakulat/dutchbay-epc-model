# Blue Whale hybrid: inputs required from the owner

Configuration under study: **1 x 10 MW wind turbine, 5 MWp solar PV, and a 10 MW BESS of
4 h (40 MWh) or 5 h (50 MWh)**, on Lot 5B Plan 3641, Kalpitiya. Status and site facts are in
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
| B03 | Site survey with coordinates (WGS84) of the boundary and proposed turbine, PV and BESS positions | resource coordinates (to add) | none | 1 |
| B04 | The 9 title documents missing from the scan, and a current Land Registry search on folio D 65/97 | lender due diligence | n/a | 2 |

## B. Wind (1 x 10 MW)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B05 | Turbine shortlist: OEM, model, rotor diameter, hub height, IEC class (a 10 MW machine on a 9.3 ha coastal lot is large, so setbacks decide whether it fits) | `turbine` block (to add) | none | 1 |
| B06 | Certified power curve and thrust curve for that model | `resource.power_curve` (to add) | none | 1 |
| B07 | Wind data at the site: any met mast or LiDAR campaign. Failing that, confirm use of the DutchBay ERA5 series and met mast 617725 | `generation.technologies.wind.capacity_factor` | 0.35 (DutchBay per-turbine gross less losses, no wake) | 1 |
| B08 | Setbacks to the sea, lagoon, streams, roads and resort buildings, and any CC&CRMD guidance received | layout check | none | 1 |
| B09 | Wind CAPEX: turbine supply, foundation, crane and transport, BOP (quote or budget) | `generation.technologies.wind.capex_usd` | $13.0M ($1,300/kW) | 1 |
| B10 | Wind O&M: OEM service agreement price and term | `opex.usd_per_year` | $0.35M/yr | 2 |
| B11 | Transport route survey: road access over Lot 5I and Lot 3 of Plan 3215, or the Lot 5D jetty | logistics risk | none | 2 |
| B12 | Degradation and availability guarantees | `degradation`, `availability_pct` | 0.6%/yr, 97% | 3 |

## C. Solar (5 MWp)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B13 | Layout area available after setbacks and the turbine exclusion zone; fixed tilt or tracker | `resource.solar` (to add) | none | 1 |
| B14 | Module and inverter selection, DC/AC ratio | `generation.technologies.solar.capacity_factor` | 0.1685 (DutchBay pvlib P50) | 2 |
| B15 | Solar CAPEX (EPC quote or budget) | `generation.technologies.solar.capex_usd` | $4.25M ($850/kW) | 1 |
| B16 | Solar O&M cost | `opex.usd_per_year` | $0.05M/yr | 3 |

## D. BESS (10 MW x 4 to 5 h)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B17 | Use case: firming the wind and solar, night-peak export, or capacity service to CEB. This decides the revenue model (F05) | `bess_1.revenue.model` | `capacity_charge` | 1 |
| B18 | Duration: 4 h (40 MWh) or 5 h (50 MWh) as the base case | `bess_1.energy_mwh`, `duration_h` | 40 MWh, 4 h | 1 |
| B19 | BESS CAPEX: cells, PCS, EMS, containers, augmentation plan | `bess_1.capex_usd` | $5.0M ($125/kWh) | 1 |
| B20 | Round-trip efficiency, cycles per year, warranted fade, augmentation cost | `bess_1.revenue` | not set | 2 |

## E. Grid and project-wide

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| B25 | Grid connection point: CEB substation, voltage (33 kV expected), line length, and any CEB grid study or connection offer | `project.grid_poi` | "TBD" | 1 |
| B26 | Grid, civils, development and owner's costs | `capex.usd_total` | $2.0M | 1 |
| B27 | Export limit at the connection point, and expected curtailment | `project.curtailment_pct` | 0% | 2 |
| B28 | Insurance, security, SPV admin costs | `opex.usd_per_year` | $0.15M/yr with land | 2 |
| B29 | O&M escalation basis | `opex.escalation_pct` | 0% | 3 |
| B30 | Target COD and construction period | `project.cod_year`, `timeline.construction_years` | 2028, 1 year | 1 |
| B31 | Permits status: SLSEA provisional approval, CC&CRMD, CEA (IEE/EIA), Pradeshiya Sabha, UDA, CAA (turbine height), Wildlife and Forest | feasibility chapter | none | 2 |

## F. Financial term sheets

### Offtake (PPA / tariff)

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F01 | PPA term (years) | `tariff.ppa_term_years`, `project.life_years` | 20 | 1 |
| F02 | Offtaker and tender route (CEB competitive tender, SLSEA standardised tariff, or private offtake) | `ppa.offtaker` | CEB | 1 |
| F03 | Tariff (LKR/kWh) for wind and solar energy, and whether it is one blended tariff or two | `tariff.lkr_per_kwh` | 20.3 (DutchBay) | 1 |
| F04 | Tariff structure: fixed, CPI-indexed, USD-linked, tiered; any escalation | `tariff.tariff_type` | fixed | 1 |
| F05 | BESS revenue model: capacity charge, energy tariff for night-peak export, or none (firming only) | `bess_1.revenue.model` | capacity charge | 1 |
| F06 | BESS rate: LKR/MW-month capacity charge, or LKR/kWh discharge tariff, and its contract term | `bess_1.revenue.*` | LKR 5.0M/MW-month, 15 years | 1 |
| F07 | Take-or-pay or deemed-energy terms for curtailment | revenue protection | none | 2 |
| F08 | Payment terms, security (letter of credit, Treasury guarantee) | `ppa.payment_terms_days` | 30 days | 2 |

### Debt

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F10 | Lenders being approached and the debt currency mix (LKR, USD commercial, DFI) | `Financing_Terms.mix` | 45% LKR / 10% DFI / 45% USD | 1 |
| F11 | Interest rate per tranche: base rate and margin, fixed or floating | `Financing_Terms.rates` | LKR 13.39%, DFI 6.5%, USD 7.5% | 1 |
| F12 | Maximum gearing | `Financing_Terms.debt_ratio` | 70% | 1 |
| F13 | Tenor and grace (interest-only) period | `tenor_years`, `interest_only_years` | 12 years, 1 year | 1 |
| F14 | Repayment profile: sculpted to DSCR or fixed annuity | `amortization_style` | auto (sculpted) | 2 |
| F15 | Sizing and lock-up DSCR, default DSCR | `target_dscr`, `min_dscr` | 1.30, 1.20 | 1 |
| F16 | Reserves: DSRA months, MRA for BESS augmentation | `reserves.dsra_months` | 6 months | 2 |
| F17 | Fees: upfront, commitment, agency | `fees.upfront_pct` | 1% upfront | 2 |
| F18 | Hedging: FX and interest-rate hedge cost | FX exposure | none | 2 |

### Equity and returns

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F20 | Equity sponsors and shares; any shareholder loan | equity structure | none | 2 |
| F21 | Land contributed as equity, and at what value | `capex.usd_total` | not included | 2 |
| F27 | Target equity IRR (hurdle) | `returns.equity_discount_rate` | 12% | 1 |

### Macro, tax and incentives

| ID | Input | Replaces (YAML field) | Placeholder now | Priority |
|---|---|---|---|---|
| F25 | FX basis: confirm the pinned USD/LKR or supply a newer one | `fx.start_lkr_per_usd` | 333.79 (2026-Q2) | 3 |
| F30 | BOI status and any tax holiday or concession | `tax.tax_holiday_*` | none | 2 |
| F31 | Corporate tax rate and any special regime | `tax.corporate_tax_rate` | 30% | 3 |
