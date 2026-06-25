# Onshore Wind EPC Costs: Benchmarks & Scaling Methodology

This reference establishes a defensible cost basis for onshore wind EPC in Sri Lanka and the broader South-Asia market, and documents the bottom-up methodology used to scale a tendered 50 MW line-item cost base to the 60 MW and 150 MW project sizes evaluated in this repository's scenarios. It pairs a real, line-itemed tender benchmark with published industry benchmarks (IRENA, Lazard, NREL/IEA), and resolves both into the financial and economic capex cases consumed by the model.

For the downstream finance treatment of these capex figures (IRR / NPV / DSCR, gearing, the flat-LKR tariff constraint), see the model's scenario set and the project economics documented elsewhere in this repository.

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

This **~$890/kW pre-tax / ~$977/kW all-in** benchmark sits materially below the conventional ~$1,300/kW Sri Lanka anchor (§2): Chinese EPC-plus-turbine packages set the low end of the cost curve.

### 1.2 The turbine as the dominant line item

Turbine supply alone is **43.8% of the pre-tax EPC** ($389.80/kW). This concentration is consistent with the published benchmark that turbines represent roughly 64–84% of *total installed cost* on a global modeled basis (IRENA); the lower share here reflects the the northwest-coast site tender's heavier loading of in-country logistics, civil works and local services. Because the turbine dominates, it is the single largest swing variable in any scaled estimate — Chinese OEM pricing (~$390/kW) versus US/NREL turbine pricing (~$1,100/kW) is the difference between a sub-$1,000/kW and a >$1,700/kW project (see §4).

### 1.3 Logistics share — an island cost driver

Transportation (sea freight plus inland haulage to a remote site) is **$5.62M, or 12.6% of the EPC** — a real cost driver for an island, remote-site project that should not be under-modeled. Larger turbine classes (e.g. 10 MW units with longer blades and heavier nacelles) carry disproportionately higher logistics costs, so this category does not scale linearly with capacity (§3).

### 1.4 Overplanting and the export cap (10 × 5.6→5.0 MW)

The 5.6 → 5.0 MW derate is a **CEB grid-connection / PPA export cap, not a turbine limitation**. This is a classic overplanting configuration: 56 MW of turbines sit behind a hard 50 MW export ceiling.

- Output above 50 MW is curtailed, but the 6 MW of headroom holds the 50 MW cap firmer across more of the wind distribution → higher *effective* capacity factor / availability on the 50 MW revenue basis.
- This must be modeled as a **production cap, not a nameplate**: revenue is bounded at 50 MW, and any P50 AEP figure must be read post-curtailment against the 50 MW cap.
- On a 56 MW *rated* basis the same EPC implies $794.47/kW pre-tax / $872.13/kW all-in — useful only as a sanity cross-check; the operating (50 MW) basis is the correct denominator for revenue economics.

### 1.5 The bonded-warehouse import-duty shelter

Under the **bonded-warehouse scheme**, duty and VAT on imported equipment are deferred so that SSCL (2.5%) and VAT (18%) fall only on the local services / civil / installation base (≈$20.8M / $21.3M), **not** on the bonded turbine and BOP imports. The all-in tax burden is therefore far below the nominal 20.5% of subtotal it would otherwise imply (here ~$4.35M, ~9.8% of subtotal). This is a **capex-side import-tax shelter** and must be kept distinct from income-tax treatment (corporate tax regime documented separately).

## 2. South-Asia Onshore Wind Cost Benchmarks

The tendered the northwest-coast site figure is corroborated and bounded by published industry benchmarks. The important caveat throughout: IRENA / Lazard / Wood Mackenzie figures are **global or US modeled costs** (China-weighted), while most country-level evidence is **auction PPA tariffs** (≠ capex ≠ all-in LCOE). No clean primary South-Asia capex/MW figure survives independent verification, so the anchor below is constructed, not cited.

| Source / basis | Total installed cost | O&M | Notes |
|---|---|---|---|
| **IRENA — Renewable Power Generation Costs in 2024** | $1,041/kW global wtd-avg (range $727–2,110) | — | LCOE $34/MWh, CF 34%; **Asia 5-yr projection ~$850/kW**; turbines 64–84% of total |
| **Lazard LCOE+ v18.0 (Jun 2025, US basis)** | $1,900–2,300/kW | $24.50–40/kW-yr fixed; no variable | 30-yr life, LCOE $37–86/MWh (up ~55% YoY) |
| **Wood Mackenzie (Oct 2025)** | — | — | China/India/Vietnam onshore LCOE leadership $25–70/MWh |
| **Bangladesh (import-dependent proxy)** | ~$1,900–2,100/kW | — | — |
| **Sri Lanka anchor (constructed)** | **$1,300/kW** | **$22/kW-yr**, 2.5%/yr USD escalation | Above IRENA-global (imported turbines + 220 kV grid + remote NW-coast BoP); well below US/Bangladesh |

### 2.1 The Sri Lanka $1,300/kW anchor and its composition

The $1,300/kW anchor is set above IRENA's global average to reflect imported turbines, 220 kV grid interconnection, and remote northwest-coast balance-of-plant, while staying well below US/Bangladesh modeled costs. The indicative component split used:

| Component | Share |
|---|---|
| Turbine | ~69% |
| Balance of plant | ~16% |
| Grid | ~8% |
| Development / owner's costs | ~3.5% |
| Financing | ~2% |
| Contingency | ~1.5% |

Operating expenditure is anchored at **$22/kW-yr** (the SL-adjusted Lazard low end), escalated at **2.5%/yr in USD** so that LKR-denominated O&M carries both USD inflation and FX depreciation.

### 2.2 Reconciling the two anchors

The the northwest-coast site tender ($890–977/kW) and the SL anchor ($1,300/kW) are not in conflict — they bracket the realistic range. The tender is the **lean Chinese-EPC floor**; the $1,300/kW anchor is the **prudent feasibility/lender base** that absorbs grid, financing and contingency the tender either externalizes or omits. Both are used: the prudent anchor for base-case underwriting, the tendered figure as the optimistic / cost-discipline case.

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

The lean rebuild lands **−$66.4M / −31%** below the EIA's own number, placing DutchBay almost exactly at the the northwest-coast site tender $/kW (~$977). The spread is driven almost entirely by turbine/equipment pricing (Chinese-bid ~$390/kW vs the EIA's implied ~$700–900/kW).

### 4.2 Turbine sensitivity (the swing)

| Turbine basis | Implied project $/kW (150 MW) | Status |
|---|---|---|
| the tendered benchmark Chinese-bid (~$390/kW) | **$977/kW** | Primary lean case |
| EIA implied (~$700–900/kW equipment) | **$1,420/kW** | Prudent / feasibility base |
| NREL US turbine (~$1,100/kW) | ~$1,723/kW | Discarded — overshoots the EIA's own anchor |

A US/NREL 10 MW turbine is used only for energy-side identity and capacity factor (CF ~35.4%); its *cost* is not adopted, since it overshoots even the conservative EIA capex.

### 4.3 Kalpitiya 50 MW

On the same tendered-benchmark basis, EPC-only and excluding BESS: **$44.40M = $888/kW** pre-SL-tax (≈$975/kW with SSCL + VAT) — consistent with the tendered 50 MW benchmark, as expected for a comparable size and turbine class.

### 4.4 How these flow into the model

Both DutchBay cost cases are carried as capex-sensitivity variants of the canonical lender case — resource, tariff and debt assumptions held identical, only capex differing — so the marginal effect of capex is cleanly isolated. Against a flat-LKR tariff the lean $977/kW case only marginally improves returns over the canonical ~$1,000/kW base, while the prudent $1,420/kW case drives gearing and returns down sharply. The consistent finding across both is that the **flat-LKR tariff, not capex, is the binding economic constraint** — capex discipline narrows but does not close the gap. See this repository's scenario files and the EIA/PPA reference documents for the downstream finance treatment.

## Sources

- Tendered 50 MW Sri Lanka coastal-wind EPC summary (Chinese EPC + turbine, bonded-warehouse scheme).
- Project EIA (disclosed financial and economic capex build).
- CEB Standardized PPA template (tariff and grid-connection terms).
- IRENA, *Renewable Power Generation Costs in 2024*.
- Lazard, *LCOE+ v18.0* (June 2025).
- Wood Mackenzie onshore wind LCOE commentary (October 2025).
- NREL / IEA reference turbine (10 MW class) for energy-side identity and capacity factor.
- Sri Lankan tax law (SSCL 2.5%, VAT 18%) and bonded-warehouse import scheme.
