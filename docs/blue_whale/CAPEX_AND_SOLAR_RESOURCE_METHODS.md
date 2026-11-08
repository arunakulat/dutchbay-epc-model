# Blue Whale capex blend and solar resource: methods (PR 6)

- Work item: <https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6556975196>
- Configuration: `conf/blue_whale_capex_solar_resource.yaml` (every source frozen with its
  verbatim figure, DATA-01)
- Code: `solar_resource/blue_whale_site_inputs.py`; Hydra CLI
  `scripts/run_blue_whale_capex_solar_resource_v14.py`
- Outputs: `docs/blue_whale/capex_blend_summary.json`, `docs/blue_whale/solar_resource_summary.json`,
  `docs/blue_whale/solar_resource_monthly.csv`
- Status: screening inputs for a placeholder site. Not a cost estimate, an energy yield
  assessment or lender evidence. No `HOLD` is lifted.

## Owner decisions

Quoted verbatim from the work item:

- Request: "in the next step, search for the latest CAPEX figures for Wind and BESS from RAG
  and EPC corpus (Mannar, Mullikulam, NSO BESS tender, and Kalpitiya) interpolate with China FOB
  pricing from a deep web search, indicate the solar efficacy and strength at the Blue Whale
  location (provide references for the pvlab or any other process through which these numbers
  are obtained) and update all YAML occasions in the Blue Whale Scenario"
- Private-price handling: "Derived blend may publish"

**The disclosure surface moves on the owner's authority** (`AGENTS.md` "Four ways a corpus
commit goes wrong", item 2). The wind and BESS figures below are blends that include private
commercial inputs, and those inputs can be recovered exactly from the published figures.
Published on the owner's decision of 2026-11-01 (#1353 comment 6556975196); the owner accepted
the exact recoverability on 2026-11-07 (#1353 comment 6702419885). The private anchors are not
written out in this repository; they are read at run time from a file outside it.

## 1. Capex anchors

Every anchor, normalised to USD per kW of installed wind capacity, or USD per kWh of contracted
4 h BESS energy. Private anchors are listed by type only.

### Wind

| Anchor | Kind | Date | Scope | Basis | Use |
|---|---|---|---|---|---|
| Northwest-coast 50 MW tender (`docs/knowledge_base/01_wind_epc_costs_and_scaling.md` §1) | public | tender, undated in the knowledge base | turbine supply (Chinese OEM, bonded), and the EPC less turbine and transport | USD 389.80/kW on 50 MW, restated to 348.04 per installed kW (56 MW); BoP 345.99 per installed kW | turbine supply weight 0.25 (freight +6% added); BoP weight 1/3 |
| Mullikulam 2 x 50 MW scenario WBS (`scenarios/mullikulam_2x50mw_mannar.yaml`) | public | model input | foundation, erection, collection, site works, management, contingency | USD 197.19 per installed kW | BoP weight 1/3 |
| DutchBay 150 MW developer rough cost estimate (`DUTCHBAY150MW-PACKAGE-HANDLING-2026-09-21`) | private, blended only | 2025 | turbine equipment line; wind plant less turbine equipment | per installed kW (unit rating inferred) | turbine supply weight 0.25 (treated as CIF); BoP weight 1/3 |
| DutchBay canonical lender case and Kalpitiya case (`scenarios/dutchbay_lendercase_2025Q4.yaml`, `scenarios/kalpitiya_lendercase_160m_fitted.yaml`) | public | 2025 Q4 | all-in, 150-160 MW | USD 1,000/kW | comparison only (a modelled base, not a quote) |
| DutchBay EIA prudent and SINOHYDRO lean cases (`scenarios/dutchbay_capex_*_2025Q4.yaml`) | public | September 2025 EIA | all-in, 150 MW, BESS excluded | USD 1,420/kW and 977/kW | comparison only |
| IRENA 2024 global onshore (knowledge base) | public | 2025-07 | total installed cost | USD 1,041/kW | comparison only |
| Mannar CEB1 (knowledge base) | public | COD 2021 | utility build, grid inclusive | about USD 2,480/kW | comparison only (upper bound) |
| Kalpitiya 60 MW Envision proposal (`KALPITIYA60MW-WIND-HANDLING-2026-09-21`) | private | 2026-09 | proposal | - | no figure entered the blend |

### BESS

| Anchor | Kind | Date | Scope | Basis | Use |
|---|---|---|---|---|---|
| Envision 10 MW / 40 MWh offer, public per-kWh restatement (`scenarios/nso250_ltl_unit_base.yaml`) | public figure; split private | 2026-08-31 | CIF Colombo excluding duty and taxes: DC block, PCS and MV, SCADA and EMS, commissioning guidance, transport | USD 99.50 per kWh contracted | equipment weight 0.125 |
| Envision 11 MW / 44 MWh offer (`scenarios/nso250_ltl_unit_upside.yaml`) | public figure; split private | 2026-08-31 | as above | USD 98.68 per kWh contracted | equipment weight 0.125 |
| Second OEM quotation (`NSO250MW-OFFERS-HANDLING-2026-09-04`) | private, blended only | 2026-08-31 | containers, PCS and MV skid, EMS, commissioning; one site; no Incoterm | per kWh contracted (11 MW x 4 h assumed) | equipment weight 0.25 (treated as FOB, freight +4%) |
| NSO 250 bid-implied equipment (`scenarios/nso250_ltl_unit_bidimplied.yaml`) | public | 2026-09 | what the winning bids can carry at 14%, not a price | USD 48.88 per kWh contracted | comparison only (the private bid-opening analysis behind it was not used further) |
| NSO 250 build-up (`scenarios/nso250_ltl_unit_base.yaml`) | public | 2026-09 | BoP 14.00, augmentation 8.00 per kWh, land and auxiliaries 10% of total | per kWh contracted | BoP (low, mode), augmentation, land share |
| DutchBay 150 MW estimate, BESS line | private | 2025 | no MW, MWh or duration stated | not normalisable | not used |

## 2. China FOB evidence

| Item | Figure, verbatim | Source (date) | USD at 6.7220 CNY/USD |
|---|---|---|---|
| Wind turbine export, "China-like" markets | "约2000~3000元/kW（含运费、5年质保，不含长期维护）"; 2026E unit price 2,700 元/kW | Soochow Securities, wind 2026 mid-year strategy (2026-07-24), <https://pdf.dfcfw.com/pdf/H3_AP202607241827319006_1.pdf> | 297.53 / 401.67 / 446.30 per kW, including freight |
| Wind turbine, emerging markets | "as low as $400,000 per MW in some emerging markets" | Wood Mackenzie via GreentechLead (2026-09-17) | 400 per kW (corroboration) |
| Wind turbine, China domestic onshore with tower | "1822、2128元/kW" (Nov, Dec 2025) | Soochow Securities (2026-07-24) | includes Chinese VAT; comparison only |
| LFP system, 4 h, China awarded | "RMB 0.52-0.58/Wh range; RMB 0.53/Wh weighted average" (September 2026) | TrendForce via EnergyTrend (2026-10-16), <https://www.energytrend.com/research/20261016-52306.html> | 69.78 per kWh DC at the mode, VAT removed |
| LFP system, CNNC 2.98 GWh | "RMB 0.4995-0.5329/Wh" | SMM (2026-10-16) | 65.76 per kWh DC at the low, VAT removed |
| LFP system, Huadian 12 GWh | "around CNY 0.54/Wh ($78.8/kWh)" | ESS News (2026-03-11) | corroboration |
| BESS core equipment delivered from China | "costs around $75/kWh when delivered from China ... per unit of usable battery capacity"; enclosures "close to 90%"; "oversize the installed capacity by at least 10%" | Ember, "How cheap is battery storage?" (2025-12-11) | DC/contracted 1.10; DC-block share 0.90 |
| Exchange rate | "1美元对人民币6.7220元" | CFETS central parity, 2026-10-16 | - |

PV module and inverter prices are unchanged from PR 3. The search found no OPIS module reading
newer than PR 3's July-August 2026 figures.

## 3. Blend method

Each case (low, mode, high) takes every uncertain input at that case, so the range is an
envelope rather than a percentile range. Weights sum to one (checked).

**Levies** follow `finance/import_levies.py`'s cascade with the repository's own rates: duties
= CIF x (CID + PAL + SSCL); VAT on CIF plus duties, and on the domestic share too in the
full-stack posture; no VAT when relieved. Postures: low = bonded (PAL 0, SSCL 2.5%, VAT
relieved; `scenarios/nso250_ltl_unit_base.yaml`); mode = prudent (PAL 5%, SSCL 2.5%, VAT
relieved; `scenarios/dutchbay_lendercase_2025Q4.yaml`); high = full stack paid (PAL 5%, SSCL
2.5%, VAT 18% on the whole capex; `scenarios/overrides/import_levies_full_stack_paid.yaml`). CID
is 0 throughout, as the repository records.

**Wind, USD per kW of 9.5 MW, excluding the plant-level grid, civils and development line
(input B26):**

```
CIF      = (0.5 x FOB_web + 0.25 x 1.06 x KB_tender + 0.25 x DB150_turbine) x 1.005
all-in   = CIF + duties + VAT + inland + 0.05 x (CIF + inland) + BoP_farm x k
k        = (1 - s) + s x (50 / 9.5)^(1 - 0.7)       # knowledge base: shared infrastructure ~ MW^0.7
BoP_farm = (KB_bop + DB150_bop + Mullikulam_bop) / 3   # low: smallest; high: largest
```

The single-machine premium `k` is the knowledge base's own scaling rule applied to the shared
fraction `s` of BoP (mobilisation, engineering, site works, management): 0.3 / 0.4 / 0.5
(assumption), giving k = 1.194 / 1.258 / 1.323. Inland transport is 20 / 40 / 70 USD/kW and the
EPC wrap 3 / 5 / 8% (assumptions).

**BESS, USD per kWh contracted:**

```
web      = CNY/Wh x 1000 / 1.13 / 6.7220 x 1.10 x 1.04     # VAT out, DC to contracted, freight
EQ_CIF   = 0.5 x web + 0.125 x ENV10 + 0.125 x ENV11 + 0.25 x 1.04 x OEM_H
all-in   = ((EQ_CIF + duties + VAT + BoP) x (1 + epc) + 8.00) / (1 - 0.10)
```

BoP 14 / 14 / 30 (NSO 250's 14; Ember's low-cost-grid EPC 30) and EPC 5 / 8 / 12%
(assumption). The DC-block share is the weighted blend of each anchor's share.

## 4. Results

| | Low | Mode | High |
|---|---:|---:|---:|
| **Wind, single 9.5 MW turbine, USD/kW (excluding B26)** | **728.16** | **936.84** | **1,341.16** |
| Turbine CIF (blend, insured) | 447.55 | 499.88 | 522.31 |
| Duties | 11.19 | 37.49 | 39.17 |
| VAT | 0 | 0 | 204.58 |
| Inland transport | 20.00 | 40.00 | 70.00 |
| EPC wrap | 14.03 | 26.99 | 47.38 |
| BoP, farm scale | 197.19 | 264.22 | 345.99 |
| Single-machine factor | 1.194 | 1.258 | 1.323 |
| BoP, single machine | 235.39 | 332.47 | 457.71 |
| **BESS, 4 h, USD per kWh contracted** | **129.13** | **140.74** | **202.51** |
| DC block (CIF) | 74.56 | 76.53 | 79.77 |
| PCS and EMS (CIF) | 12.33 | 12.65 | 13.19 |
| Duties | 2.17 | 6.69 | 6.97 |
| VAT | 0 | 0 | 26.58 |
| BoP | 14.00 | 14.00 | 30.00 |
| EPC margin | 5.15 | 8.79 | 17.75 |
| Augmentation reserve | 8.00 | 8.00 | 8.00 |
| Land and auxiliaries | 12.91 | 14.07 | 20.25 |

At the mode the wind project (turbine 8,899,980 plus the USD 2.0M B26 line) is USD 10.90M, or
1,147 USD/kW. That sits inside the repository's public range (977 lean, 1,000 canonical, 1,041
IRENA, 1,420 EIA prudent) and below the USD 1,300/kW placeholder it replaces. The BESS mode is
4.3% above PR 3's 135.00, mainly because the Blue Whale scenarios carry no `taxes_indirect`
block, so the levies now sit in the capex, and because of the EPC wrap; the blended equipment
CIF (89.19) is 10% below the Envision restatement.

## 5. Solar resource and efficacy at the site

**Site.** The area centroid of the 160 PV tables in `docs/blue_whale/pv_bess_layout_lot5b.geojson`:
8.291526 N, 79.753204 E. It is 123 m from the turbine (8.2925 N, 79.752666 E) and 2.42 km from
the TMY's grid point (8.27 N, 79.75 E). Over 123 m the resource is the same as at the turbine;
the geometry changes the annual POA by 0.002%.

**Irradiance record.** `inputs/solar_tmy/kalpitiya_pvgis_tmy_8.27N_79.75E.csv` (SHA-256
`c71c9c8b...`). Its README says PVGIS-SARAH3. That is not correct: PVGIS-SARAH3 does not cover
the site (the PVGIS 5.3 API answers "Location out of the spatial coverage of the radiation
database selected. Please, selectanother database (PVGIS-ERA5)."), and the PVGIS 5.3 TMY at the
same point is built on PVGIS-ERA5, 2005-2023, and reproduces the frozen file (first row, months
selected, annual GHI 1,871.34 kWh/m2). The frozen TMY is an ERA5 TMY. The README was outside
PR 6's allowlist; PR 7 corrects it on the owner's decision "Keep ERA5, fix README (Recommended)"
(#1353 comment 6563070978), with the satellite figures reported as upside.

**Model (pvlib 0.16.1).** The repository's chain, the TMY branch of
`solar_resource.pv_producer.compute_solar_aep`: NREL SPA solar position; Hay-Davies
transposition (albedo 0.25); Faiman cell temperature on the TMY's hourly temperature and wind;
PVWatts DC with the module's -0.26 %/C; PVWatts inverter at 98.8% (Huawei SUN2000-330KTL-H1
European efficiency) clipped at 5.0 MW AC; the DutchBay 14% flat loss stack. Array: JinkoSolar
Tiger Neo 3.0 JKM670N-66QL6-BDV, 6.0032 MWp (160 tables), 5.0 MW AC, tilt 8 degrees, azimuth 180
(conf/blue_whale_solar_bess.yaml). Bifacial gain and turbine shading are not modelled. Run at
the TMY point, the stepped chain reproduces `compute_solar_aep` to 3.9e-16.

| Annual (at the PV centroid) | Value |
|---|---:|
| GHI | 1,871.34 kWh/m2 |
| DNI | 1,796.67 kWh/m2 |
| DHI | 657.49 kWh/m2 |
| POA, Hay-Davies, 8 degrees | 1,885.86 kWh/m2 |
| POA, isotropic (pvlib; independent closed form agrees to 1e-9) | 1,883.17 kWh/m2 |
| DC energy | 10,896.0 MWh |
| AC energy before the 14% stack | 10,724.0 MWh |
| Net AC energy (before the warranted year-1 1%) | 9,222.6 MWh |
| Specific yield | **1,536.3 kWh/kWp/yr** |
| Performance ratio | **0.8146** |
| AC capacity factor (5.0 MW) | **21.06%** |
| DC capacity factor (6.0032 MWp) | **17.54%** |

Loss breakdown, as shares of the POA x kWp reference (11,321.2 MWh): temperature and irradiance
-3.76% (POA-weighted cell temperature 39.4 C at a 27.0 C mean ambient); inverter efficiency and
clipping -1.52% (138 clipping hours); the 14% stack -13.26%; total -18.54%, which is 1 - PR.
Angle-of-incidence and spectral losses are not modelled separately by PVWatts.

Monthly values are in `docs/blue_whale/solar_resource_monthly.csv`.

### Cross-checks

| Source | GHI | DNI | DHI | POA / GTI | Specific yield (kWh/kWp) | Yield vs pvlib |
|---|---:|---:|---:|---:|---:|---:|
| pvlib on the frozen ERA5 TMY (this note) | 1,871.3 | 1,796.7 | 657.5 | 1,885.9 (8 deg) | 1,536.3 | - |
| PVGIS 5.3 PVcalc, PVGIS-ERA5 2005-2023, c-Si, 8 deg, south, 14% loss | - | - | - | 1,933.9 (8 deg) | 1,472.9 | -4.1% |
| Global Solar Atlas, Solargis model 2.2.68 (data to 2025), PVOUT c-Si at 9 deg | 2,047.7 | 1,499.1 | 911.9 | 2,067.8 (9 deg) | 1,632.5 | +6.3% |
| NASA POWER climatology 2001-2025 (SYN1DEG), x 365 | 2,070.6 | 1,485.2 | 866.3 | - | - | - |
| NASA POWER annual mean 2015-2025 | 2,046.1 | - | - | - | - | - |

**Why they differ.**

- **GHI.** The two satellite-based sources agree with each other (Solargis 2,047.7, NASA POWER
  2015-2025 2,046.1, within 0.1%) and sit **9.4% above** the ERA5 TMY (1,871.3). ERA5 is a
  reanalysis whose cloud fields are known to bias surface irradiance in the humid tropics; the
  satellite products observe the clouds. The ERA5 basis is therefore conservative for GHI.
- **Beam and diffuse.** ERA5 has more beam and much less diffuse (DNI 1,796.7, DHI 657.5) than
  Solargis (1,499.1, 911.9) and NASA POWER (1,485.2, 866.3). At an 8-10 degree tilt this partly
  offsets the GHI gap, so the POA gap is 9.6% against Solargis.
- **Specific yield.** PVGIS uses the same ERA5 irradiance, but its own loss models (AOI -2.7%,
  temperature and irradiance -9.36%, spectral +0.41%, then 14%; total -23.84%), so it lands 4.1%
  below this note, mostly through its larger thermal loss and a modelled AOI loss. Global Solar
  Atlas PVOUT uses Solargis irradiance (9.6% more POA) and Solargis' own default losses rather
  than 14%; it is 6.3% above.
- **Implication.** On satellite irradiance the array would yield roughly 6-9% more than the
  committed basis. The committed CFs stay on the frozen TMY; a re-baseline onto a
  satellite-based TMY is a separate decision (see the PR's challenge points).

## 6. Effect on the sizing

PR 4's production sizing (`scripts/run_blue_whale_pv_bess_sizing_v14.py --config-name
blue_whale_solar_bess_project_sizing`, seed 20261101, 325 points x 256 trials) was re-run
unchanged on the blended prices. **The choice moves**: 107 tables (4.01464 MWp), 3.5 MW AC and
1.0 MW / 4.0 MWh under both readings, the grid's smallest PV and battery (PR 4: 160 tables,
5.0 MW AC, 4.5 MW / 18 MWh). Every eligible size has a negative P50 unit NPV; the chosen size's
is USD -312,629 (P90 -571,313). At that size the PV alone gives 6,180.5 MWh before the warranted
1%, a specific yield of 1,539.5 kWh/kWp (AC CF 20.16%, DC CF 17.57%). PR 3's hybrid sizing,
re-run the same way, does not move (DC/AC 1.1, 5 MW / 24 MWh). Details: `STATUS.md`.

PR 7 (owner decisions of 2026-11-01, #1353 comment 6563070978): the sizing ranks on the P50
after-tax project NPV, which chooses the same 107 tables, 3.5 MW AC and 1.0 MW / 4.0 MWh, but
the project commits the owner's 5 MW / 20 MWh battery with 151 tables (5.66552 MWp) at 5.0 MW AC
(152 tables, 5.70304 MWp, from 15.22.0 with the turbine on DutchBay T2). The cost of that
choice and the PV curve are in `STATUS.md`.

## 7. References

- Anderson, K. S., Hansen, C. W., Holmgren, W. F., Jensen, A. R., Mikofski, M. A., and
  Driesse, A. (2023). pvlib python: 2023 project update. *Journal of Open Source Software*,
  8(92), 5994. doi:10.21105/joss.05994.
- Holmgren, W. F., Hansen, C. W., and Mikofski, M. A. (2018). pvlib python: a python package
  for modeling solar energy systems. *Journal of Open Source Software*, 3(29), 884.
  doi:10.21105/joss.00884.
- European Commission Joint Research Centre, PVGIS 5.3 (PVcalc and TMY API, PVGIS-ERA5),
  <https://re.jrc.ec.europa.eu/api/v5_3/>, retrieved 2026-11-01.
- Global Solar Atlas 2.x, long-term averages API, Solargis model 2.2.68, data version 1.7,
  <https://api.globalsolaratlas.info/data/lta>, retrieved 2026-11-01.
- NASA POWER API v2.10.1 climatology and v2.10.0 monthly, parameter ALLSKY_SFC_SW_DWN (also
  ALLSKY_SFC_SW_DNI, ALLSKY_SFC_SW_DIFF), community RE, <https://power.larc.nasa.gov/>,
  retrieved 2026-11-01.
- Hay, J. E., and Davies, J. A. (1980). Calculation of the solar radiation incident on an
  inclined surface (Hay-Davies transposition, as implemented in pvlib).
- Faiman, D. (2008). Assessing the outdoor operating temperature of photovoltaic modules.
  *Progress in Photovoltaics*, 16(4), 307-315 (as implemented in pvlib).
- The capex sources are listed with their verbatim figures in
  `conf/blue_whale_capex_solar_resource.yaml`.

## Assumptions

Freight and insurance on FOB-basis anchors (6% wind, 4% BESS); marine insurance 0.5% on wind
CIF; one exchange rate for all CNY figures; Chinese tender prices include 13% VAT; DC/contracted
1.10; the developer estimate's turbine line is delivered and its unit rating is inferred; the
second OEM quotation is FOB on an 11 MW x 4 h site; shared fraction of wind BoP 0.3-0.5; inland
transport 20-70 USD/kW; EPC wraps; no escalation of 2024-2025 anchors to 2026; the levy postures
are the repository's, not a ruling for this project (`boi_approved: false`).

## Limitations

- The blend is a screening estimate. No quote for the Blue Whale turbine or BESS exists
  (inputs B09, B19).
- Each wind blend and the BESS equipment blend contain one private anchor, so a reader holding
  the public anchors and weights can back that anchor out from the published intermediate
  figures. The owner's decision accepts this.
- The range is an envelope (all low, all high), not a probability interval.
- The solar figures rest on an ERA5 TMY that sits about 9% below satellite GHI at this site.
