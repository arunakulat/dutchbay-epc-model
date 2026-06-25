# Onshore Wind EPC Costs: Benchmarks & Scaling Methodology

This reference establishes a defensible cost basis for onshore wind EPC in Sri Lanka and the broader South-Asia market, and documents the bottom-up methodology used to scale a tendered 50 MW line-item cost base to the 60 MW and 150 MW project sizes evaluated in this repository's scenarios. It pairs a real, line-itemed tender benchmark with published industry benchmarks (IRENA, Lazard, NREL/IEA), and resolves both into the financial and economic capex cases consumed by the model.

For the downstream finance treatment of these capex figures (IRR / NPV / DSCR, gearing, the flat-LKR tariff constraint), see the model's scenario set and the project economics documented elsewhere in this repository.

> **External-benchmark note (deep-research update, 2026-06-25).** The published-benchmark claims in §2 and §4 were re-verified against primary sources (IRENA *Renewable Power Generation Costs in 2024*, released 22 July 2025; Lazard *LCOE+ v18.0*, June 2025; NREL *Cost of Wind Energy Review: 2024 Edition*; ADB/CEB Mannar project disclosures; Sri Lanka Customs / KPMG on the bonded-warehouse scheme). Confirmed figures, corrections, and items that could not be independently verified are catalogued in **"External validation & sources"** near the end of this document. The project-specific tender, EIA and PPA figures are internal/non-public and are not externally verifiable; they are preserved as-is.

## 1. A Tendered 50 MW Coastal-Wind EPC Benchmark (Sri Lanka)

The single most useful anchor for Sri Lankan onshore wind capex is a tendered, fully line-itemed EPC cost summary for a **50 MW wind farm on Sri Lanka's northwest coast, under a bonded-warehouse scheme** — a Chinese EPC contractor paired with a Chinese turbine OEM. It sits in the same northwest-coast wind corridor as the projects in this repository's scenarios, so it is a direct, in-corridor comparable rather than a global proxy.

### 1.1 Headline figures

The fleet is **10 turbines of 5.6 MW nameplate, derated to 5.0 MW each** — 56 MW installed behind a 50 MW operating basis (see §1.4). All figures are USD; the subtotal and tax-inclusive total reconcile exactly.

| Metric | Amount | Per kW (50 MW basis) |
|---|---|---|
| Sub-total (pre-tax EPC) | $44,490,413 | **$889.81/kW** |
| Total incl. SSCL 2.5% + VAT 18% | $48,839,573 | **$976.79/kW** |
| Wind turbine supply alone | $19.49M | $389.80/kW (43.8% of subtotal) |
| Procurement (turbine + BOP) | $23.73M | $474.61/kW |
| Balance of plant (BOP only) | $4.24M | $84.81/kW |
| Civil works | $6.10M | $121.98/kW |
| Installation / erection | $4.16M | $83.19/kW |
| Engineering & design | $1.14M | $22.85/kW |
| Transportation (sea + inland) | $5.62M | **$112.50/kW (12.6%)** |

This **~$890/kW pre-tax / ~$977/kW all-in** benchmark sits materially below the conventional ~$1,300/kW Sri Lanka anchor (§2): Chinese EPC-plus-turbine packages set the low end of the cost curve. It also sits well below the only fully-disclosed *built* Sri Lankan onshore reference — CEB's 103.5 MW Mannar wind farm at $256.7M (~$2,480/kW all-in, COD 2021), which is a sovereign-financed, grid-inclusive utility build rather than a lean private EPC (see §2 and external validation).

### 1.2 The turbine as the dominant line item

Turbine supply alone is **43.8% of the pre-tax EPC** ($389.80/kW). On a *global modeled* basis, turbines have historically represented the bulk of total installed cost — roughly **64–84%** in IRENA's wind cost-analysis work (a range that originates in IRENA's 2012 *Wind Power* cost study and is widely quoted since; treat it as an order-of-magnitude share, not a current figure). The lower share in this tender reflects the northwest-coast site's heavier loading of in-country logistics, civil works and local services. Because the turbine dominates, it is the single largest swing variable in any scaled estimate — Chinese OEM pricing (~$390/kW) versus US/NREL-class turbine pricing (~$1,100/kW, NREL reference order of magnitude) is the difference between a sub-$1,000/kW and a >$1,700/kW project (see §4).

### 1.3 Logistics share — an island cost driver

Transportation (sea freight plus inland haulage to a remote site) is **$5.62M, or 12.6% of the EPC** — a real cost driver for an island, remote-site project that should not be under-modeled. Larger turbine classes (e.g. 10 MW units with longer blades and heavier nacelles) carry disproportionately higher logistics costs, so this category does not scale linearly with capacity (§3).

### 1.4 Overplanting and the export cap (10 × 5.6→5.0 MW)

The 5.6 → 5.0 MW derate is a **CEB grid-connection / PPA export cap, not a turbine limitation**. This is a classic overplanting configuration: 56 MW of turbines sit behind a hard 50 MW export ceiling.

- Output above 50 MW is curtailed, but the 6 MW of headroom holds the 50 MW cap firmer across more of the wind distribution → higher *effective* capacity factor / availability on the 50 MW revenue basis.
- This must be modeled as a **production cap, not a nameplate**: revenue is bounded at 50 MW, and any P50 AEP figure must be read post-curtailment against the 50 MW cap.
- On a 56 MW *rated* basis the same EPC implies $794.47/kW pre-tax / $872.13/kW all-in — useful only as a sanity cross-check; the operating (50 MW) basis is the correct denominator for revenue economics.

### 1.5 The bonded-warehouse import-duty shelter

Under the **bonded-warehouse scheme**, duty and VAT on imported equipment are deferred/exempted during construction so that SSCL (2.5%) and VAT (18%) fall only on the local services / civil / installation base (≈$20.8M / $21.3M), **not** on the bonded turbine and BOP imports. The all-in tax burden is therefore far below the nominal 20.5% of subtotal it would otherwise imply (here ~$4.35M, ~9.8% of subtotal). This is a **capex-side import-tax shelter** and must be kept distinct from income-tax treatment (corporate tax regime documented separately).

This treatment is consistent with Sri Lanka's published bonded-warehouse facility rules: the scheme grants "exemptions from selected duties and taxes on approved capital goods during the construction period" (plant, machinery, equipment, spares and sector-specific construction materials), administered by Sri Lanka Customs. A Ministry of Finance amendment effective 15 October 2025 explicitly extended eligibility to **renewable energy storage facilities (≥1 MWh)** — relevant if a BESS is later brought inside the bonded scope. See external validation for the primary references.

## 2. South-Asia Onshore Wind Cost Benchmarks

The tendered northwest-coast figure is corroborated and bounded by published industry benchmarks. The important caveat throughout: IRENA / Lazard / Wood Mackenzie figures are **global or US modeled costs** (China-weighted in IRENA's case), while most country-level evidence is **auction PPA tariffs or single utility builds** (≠ lean EPC capex ≠ all-in LCOE). No clean primary South-Asia *private-EPC* capex/MW figure survives independent verification, so the SL anchor below is constructed, not cited.

| Source / basis | Total installed cost | O&M | Notes |
|---|---|---|---|
| **IRENA — Renewable Power Generation Costs in 2024** (released 22 Jul 2025) | **$1,041/kW** global wtd-avg (2024 USD) | — | LCOE **$0.034/kWh**, CF **34%**; LCOE +3% vs 2023; **5-yr global TIC stabilising $850–1,000/kW**, **Asia ~$850/kW**; **China LCOE $0.029/kWh** (lowest), China = 70% of 2024 installs |
| **Lazard LCOE+ v18.0 (Jun 2025, US basis)** | **$1,900–2,300/kW** (total capital cost) | **$24.50–40.00/kW-yr** fixed; **$0 variable** | 30-yr life, CF 30–55%, LCOE **$37–86/MWh**; onshore-wind LCOE up ~49% since 2020 (CAGR ~8%) |
| **NREL — Cost of Wind Energy Review: 2024 Edition** | US land-based reference (turbine ~$1,100/kW class; full $/kW [unverified here]) | — | Reference project 25-yr life, 5-yr MACRS, 2.5% inflation; used in this repo for energy-side identity & CF only |
| **Sri Lanka — Mannar (CEB1), built 2021** | **~$2,480/kW all-in** ($256.7M / 103.5 MW) | — | 30× Vestas V126-3.45MW; CEB-owned, ADB-financed ($200M loan + $56.7M CEB), grid + sovereign-cost inclusive → upper bound, not a lean private EPC |
| **Sri Lanka anchor (constructed)** | **$1,300/kW** | **$22/kW-yr**, 2.5%/yr USD escalation | Above IRENA-global (imported turbines + 220 kV grid + remote NW-coast BoP); below US (Lazard) and well below the grid-inclusive Mannar utility build |

> Notes on corrections vs the prior draft: the previous "Bangladesh ~$1,900–2,100/kW" line was an unsourced proxy and has been replaced with the **verifiable, in-country Mannar reference**. The previous "Lazard up ~55% YoY" was imprecise — Lazard v18.0 reports an onshore-wind LCOE rise of **~49% over 2020–2025 (≈8% CAGR)**, not a single-year 55% jump; corrected above.

### 2.1 The Sri Lanka $1,300/kW anchor and its composition

The $1,300/kW anchor is set above IRENA's 2024 global average ($1,041/kW) to reflect imported turbines, 220 kV grid interconnection, and remote northwest-coast balance-of-plant, while staying well below US modeled costs (Lazard $1,900–2,300/kW) and the grid-inclusive Mannar build (~$2,480/kW). The indicative component split used:

| Component | Share |
|---|---|
| Turbine | ~69% |
| Balance of plant | ~16% |
| Grid | ~8% |
| Development / owner's costs | ~3.5% |
| Financing | ~2% |
| Contingency | ~1.5% |

Operating expenditure is anchored at **$22/kW-yr** (just below the Lazard low end of $24.50/kW-yr, SL-adjusted), escalated at **2.5%/yr in USD** so that LKR-denominated O&M carries both USD inflation and FX depreciation. This O&M anchor is conservative-low against Lazard's US fixed-O&M band ($24.50–40.00/kW-yr); it is justified by lower local labour cost but should be stress-tested upward in sensitivity.

### 2.2 Reconciling the anchors

The northwest-coast tender ($890–977/kW) and the SL anchor ($1,300/kW) are not in conflict — they bracket the realistic *private-EPC* range. The tender is the **lean Chinese-EPC floor**; the $1,300/kW anchor is the **prudent feasibility/lender base** that absorbs grid, financing and contingency the tender either externalizes or omits. The IRENA 2024 global average ($1,041/kW) sits between them, and the Lazard US band ($1,900–2,300/kW) and the Mannar utility build (~$2,480/kW) sit above — confirming that the SL anchor is conservatively placed but not implausibly high. Both internal anchors are used: the prudent anchor for base-case underwriting, the tendered figure as the optimistic / cost-discipline case.

## 3. Bottom-Up Scaling Methodology

To estimate capex at 60 MW and 150 MW from the 50 MW line-item base, each EPC category is scaled by a rule reflecting its physical and commercial behaviour, rather than scaling the headline $/kW flat. The result is **planning-grade (±20%)**.

### 3.1 Per-category scaling rules

| Category | Scaling rule | Rationale |
|---|---|---|
| **Wind-island scope** — turbine supply, foundations, erection, array cable | **Linear with MW** | Per-turbine cost is largely fixed; total scales with turbine count / capacity |
| **Shared infrastructure** — switchyard, on-site substation, engineering, mobilisation | **~MW^0.7** | Genuine economies of scale; one substation / one mobilisation serves a larger plant |
| **Logistics / transportation** | **Scaled up for heavier units** (e.g. ×2.6 for a 10 MW-class plant vs the 5 MW base) | Larger blades/nacelles carry disproportionately higher freight and inland-haul cost |
| **Permits / development** | **~Fixed** | Largely independent of plant size within this range |
| **Insurance** | **% of works** (~4.42% of subtotal) | Premium tracks the insured construction value |
| **Bonded SSCL / VAT** | **Local base only**, at effective bonded rates (~1.17% / ~8.61% of subtotal) | Imports remain sheltered; tax falls only on local services/civil/install |
| **Contingency** | **5% of subtotal** | Standard feasibility-grade allowance |

Project-specific transmission is **excluded** from the EPC where it is a separate, third-party (e.g. CEB-developed) line; only the on-site gen-tie / substation is carried.

### 3.2 Financial vs Economic cost

Two cost concepts must be kept distinct, following standard feasibility/EIA practice:

- **Financial cost** — the actual cash outlay an investor incurs, including all taxes and transfers. This is the figure used for equity and debt sizing.
- **Economic cost** — the resource cost to society, derived by (a) **removing transfer payments** (import duties, local indirect taxes that are receipts to government, not real resource use) and (b) applying a **Standard Conversion Factor (SCF ≈ 0.95)** to convert market prices to shadow/border prices. Economic cost is used for EIRR / ENPV / BCR analysis, not for equity returns.

In the worked rebuild below, economic cost is obtained by netting out a transfer-payment adjustment and applying SCF 0.95, yielding a figure roughly 6% below the financial cost.

## 4. Resulting Capex Cases in the Model

Two cost cases anchor the model, differing almost entirely in turbine/equipment pricing. The **turbine $/kW is the swing variable**: holding owner's costs constant, substituting Chinese-bid turbine pricing for the EIA's implied equipment cost moves the whole project by ~31%.

### 4.1 DutchBay 150 MW — lean vs prudent

The lean case is built by substituting the tendered-benchmark-scaled hard costs (equipment + civil) into the disclosed EIA build while **keeping the EIA's owner's costs unchanged**, then recomputing 5% contingency, the transfer adjustment, and SCF 0.95. BESS is excluded throughout (it is outside the disclosed economic/financial cost).

| EIA line | EIA (prudent) | Lean (tendered-benchmark basis) |
|---|---|---|
| a.1 Equipment & installation | $162.77M | $104.89M (scaled non-civil + insurance) |
| a.2 Construction / civil | $22.41M | $17.03M (scaled civil) |
| a.3 Other (land / mgmt / dev) — kept | $17.65M | $17.65M |
| a.4 Contingency (5%) | $10.14M | $6.98M |
| **A — Financial cost** | **$212.97M ($1,420/kW)** | **$146.55M ($977/kW)** |
| **C — Economic cost (× SCF 0.95)** | **$200.90M ($1,339/kW)** | **$137.80M ($919/kW)** |

The lean rebuild lands **−$66.4M / −31%** below the EIA's own number, placing DutchBay almost exactly at the northwest-coast site tender $/kW (~$977). The spread is driven almost entirely by turbine/equipment pricing (Chinese-bid ~$390/kW vs the EIA's implied ~$700–900/kW). Both the EIA ($1,420/kW) and lean ($977/kW) figures bracket the IRENA-2024 global average ($1,041/kW) and sit below the Lazard US band — an externally-sane envelope.

### 4.2 Turbine sensitivity (the swing)

| Turbine basis | Implied project $/kW (150 MW) | Status |
|---|---|---|
| tendered-benchmark Chinese-bid (~$390/kW) | **$977/kW** | Primary lean case |
| EIA implied (~$700–900/kW equipment) | **$1,420/kW** | Prudent / feasibility base |
| NREL US turbine (~$1,100/kW class) | ~$1,723/kW | Discarded — overshoots the EIA's own anchor |

A US/NREL 10 MW-class turbine is used only for energy-side identity and capacity factor (CF ~35.4%); its *cost* is not adopted, since it overshoots even the conservative EIA capex and pushes the project toward the Lazard US band rather than a South-Asia cost basis.

### 4.3 Kalpitiya 50 MW

On the same tendered-benchmark basis, EPC-only and excluding BESS: **$44.40M = $888/kW** pre-SL-tax (≈$975/kW with SSCL + VAT) — consistent with the tendered 50 MW benchmark, as expected for a comparable size and turbine class.

### 4.4 How these flow into the model

Both DutchBay cost cases are carried as capex-sensitivity variants of the canonical lender case — resource, tariff and debt assumptions held identical, only capex differing — so the marginal effect of capex is cleanly isolated. Against a flat-LKR tariff the lean $977/kW case only marginally improves returns over the canonical ~$1,000/kW base, while the prudent $1,420/kW case drives gearing and returns down sharply. The consistent finding across both is that the **flat-LKR tariff, not capex, is the binding economic constraint** — capex discipline narrows but does not close the gap. See this repository's scenario files and the EIA/PPA reference documents for the downstream finance treatment.

## External validation & sources

Deep-research re-verification of the externally-verifiable claims (2026-06-25). Figures are quoted in the source's own basis/units. Project-specific tender/EIA/PPA numbers are internal and not externally verifiable; they are unchanged.

**IRENA — *Renewable Power Generation Costs in 2024*** (IRENA, released 22 July 2025; all values in 2024 USD)
- Onshore wind **global weighted-average total installed cost = USD 1,041/kW** — **CONFIRMED** (was $1,041/kW). Source: https://www.irena.org/Publications/2025/Jul/Renewable-Power-Generation-Costs-in-2024 and the summary PDF https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2025/Jul/IRENA_TEC_RPGC_in_2024_Summary_2025.pdf
- Onshore wind **global weighted-average LCOE = USD 0.034/kWh**; **+3% vs 2023** — **CONFIRMED** (document's "increased" direction is correct). Same source.
- Onshore wind **global weighted-average capacity factor = 34%** (2024; 27% in 2010) — **CONFIRMED**. Same source (Table S1).
- **5-year global TIC projection: onshore wind stabilising USD 850–1,000/kW; Asia ~USD 850/kW** — **CONFIRMED** (document's "Asia ~$850/kW" is correct; clarified it is a forward projection, not a 2024 actual). Same source.
- **China onshore-wind LCOE = USD 0.029/kWh (lowest globally); China = 70% of 2024 onshore installations** — **ADDED** (newly cited corroboration). Same source.
- **Turbine = 64–84% of total installed cost** — **FLAGGED / RE-ATTRIBUTED.** This range originates in IRENA's **2012** *Renewable Energy Technologies: Cost Analysis Series — Wind Power* (https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2012/RE_Technologies_Cost_Analysis-WIND_POWER.pdf), not the 2024 report. Retained as an order-of-magnitude historical share with the correct provenance.
- **TIC range "$727–2,110/kW"** — **[unverified]**. Could not be confirmed from the 2024 summary; likely a country-level data-table range from the full report. Removed from the headline table; treat as indicative only.

**Lazard — *LCOE+ v18.0*** (June 2025; US illustrative-project basis). Source: https://www.lazard.com/media/uounhon4/lazards-lcoeplus-june-2025.pdf
- Onshore wind **Total Capital Cost = $1,900–2,300/kW** — **CONFIRMED** (Key Assumptions, Renewable Energy cont'd). EPC cost $1,900/kW in the low-case sample calc.
- Onshore wind **Fixed O&M = $24.50–40.00/kW-yr; Variable O&M = $0** — **CONFIRMED** (document's "$24.50–40/kW-yr fixed; no variable" verified).
- Onshore wind **Facility life = 30 years; capacity factor 30–55%; unsubsidized LCOE = $37–86/MWh** — **CONFIRMED**.
- **"Up ~55% YoY"** — **CORRECTED** to **+49% over 2020–2025 (≈8% CAGR)** per Lazard's own historical-trend chart; the single-year 55% framing was not supported.

**NREL — *Cost of Wind Energy Review: 2024 Edition*** (NREL, Nov 2024). Source: https://docs.nrel.gov/docs/fy25osti/91775.pdf (also OSTI https://www.osti.gov/biblio/2479271)
- Reference land-based project: **25-year operating life, 5-yr MACRS depreciation, 2.5% inflation** — **CONFIRMED** (from NREL landing/abstract).
- **Turbine ~$1,100/kW class** and the precise land-based total CapEx $/kW — **[unverified]** from this environment: NREL's document hosts (docs.nrel.gov / atb.nrel.gov / research-hub) were not reachable for full-text extraction during this pass. The ~$1,100/kW US-turbine figure is retained as an order-of-magnitude reference consistent with NREL ATB land-based wind; verify against the PDF before quoting as exact.

**Sri Lanka onshore reference — Mannar Wind Farm (CEB1)**
- **103.5 MW; total cost $256.7M (~$2,480/kW all-in); 30× Vestas V126-3.45 MW; COD 2021; ADB $200M loan + $56.7M CEB** — **ADDED** as a verifiable in-country onshore reference (utility/grid-inclusive upper bound). Sources: https://www.power-technology.com/marketdata/mannar-wind-farm-ceb1-sri-lanka/ ; ADB project 49345-002 https://www.adb.org/projects/49345-002/main . (Replaces the prior unsourced "Bangladesh ~$1,900–2,100/kW" proxy.)

**Sri Lanka bonded-warehouse import-duty treatment**
- **Exemptions from selected duties and taxes on approved capital goods (plant, machinery, equipment, spares, sector-specific construction materials) during the construction period; administered by Sri Lanka Customs** — **CONFIRMED.** Sources: Sri Lanka Customs, Bonded Operation https://www.customs.gov.lk/services/bonded-operation/ ; KPMG, "Sri Lanka: Amended bonded warehouse facility regulations" https://kpmg.com/us/en/taxnewsflash/news/2025/10/sri-lanka-amended-bonded-warehouse-facility-regulations.html
- **2025 amendment (effective 15 Oct 2025) adds renewable-energy storage facilities (≥1 MWh) as an eligible sector** — **ADDED** (relevant if BESS is later brought inside the bonded scope). Same KPMG source.
- **SSCL 2.5% / VAT 18%** rates — consistent with Sri Lanka Inland Revenue (documented in the separate corporate-tax-regime reference); unchanged.

**Project-internal sources (not externally verifiable — preserved)**
- Tendered 50 MW Sri Lanka coastal-wind EPC summary (Chinese EPC + turbine, bonded-warehouse scheme).
- Project EIA (disclosed financial and economic capex build).
- CEB Standardized PPA template (tariff and grid-connection terms).
- NREL / IEA reference turbine (10 MW class) for energy-side identity and capacity factor.

## Changelog (deep-research update 2026-06-25)

**Confirmed (verified against primary sources, unchanged):**
- IRENA 2024 onshore wind: TIC **$1,041/kW**, LCOE **$0.034/kWh** (+3% YoY), CF **34%**, Asia 5-yr projection **~$850/kW**.
- Lazard v18.0 (Jun 2025) onshore wind: capex **$1,900–2,300/kW**, fixed O&M **$24.50–40.00/kW-yr**, no variable O&M, 30-yr life, LCOE **$37–86/MWh**.
- Lazard report vintage (June 2025, v18.0) and the unsubsidized LCOE range.
- Sri Lanka bonded-warehouse duty/VAT shelter on imported capital goods during construction (Sri Lanka Customs / KPMG).
- IRENA report basis is 2024 USD; clarified Lazard is a US illustrative basis.

**Corrected:**
- Lazard LCOE-trend wording: "up ~55% YoY" → **+49% over 2020–2025 (≈8% CAGR)**.
- IRENA Asia "$850/kW" clarified as a **forward 5-yr projection**, not a 2024 actual; global TIC band given as $850–1,000/kW.
- Turbine "64–84% of total installed cost" **re-attributed to IRENA's 2012** Wind Power cost study (not the 2024 report) and labelled as a historical/order-of-magnitude share.
- Replaced the unsourced "Bangladesh ~$1,900–2,100/kW" proxy with the verifiable **Mannar (CEB1) ~$2,480/kW** in-country reference.
- O&M anchor note: $22/kW-yr is conservative-low vs Lazard's $24.50–40/kW-yr band; flagged for upward sensitivity.
- IRENA *Renewable Power Generation Costs in 2024* release date corrected from "June 2025" to **22 July 2025** (the IRENA URL path itself reads `/2025/Jul/`); all IRENA figures unchanged.

**Added:**
- **External validation & sources** section with full URLs for every externally-verifiable claim.
- IRENA China onshore LCOE **$0.029/kWh** and **70% of 2024 global onshore installs**.
- Mannar Wind Farm reference row (103.5 MW, $256.7M, 30× Vestas V126-3.45MW, COD 2021, ADB-financed).
- Bonded-warehouse 2025 amendment extending eligibility to renewable-energy storage (≥1 MWh).
- NREL reference-project assumptions (25-yr life, 5-yr MACRS, 2.5% inflation).

**Flagged / unverified:**
- IRENA TIC range **"$727–2,110/kW"** — could not confirm from the 2024 summary; removed from the headline table, treat as indicative.
- NREL precise land-based total CapEx $/kW and **turbine ~$1,100/kW** — **[unverified]** from this environment (NREL document hosts unreachable); retained as order-of-magnitude with the canonical NREL URL for verification.
- Wood Mackenzie Oct-2025 LCOE-leadership line — not independently re-verified this pass; left out of the strengthened table pending a primary citation.
