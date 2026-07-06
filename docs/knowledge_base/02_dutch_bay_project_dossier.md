# Dutch Bay 150 MW Wind + BESS: Engineering, Economics & PPA

## Overview

The Dutch Bay Wind Farm is a 150 MW onshore wind project with co-located battery storage, sited at Dutch Bay on the Kalpitiya peninsula, Puttalam District, Sri Lanka. The proponent is Envision Energy (turbine OEM acting as developer), with environmental consultancy by the Lanka Hydraulic Institute. The project sells its full output to the Ceylon Electricity Board (CEB) under the standardized Build-Own-Operate (BOO) Power Purchase Agreement regime introduced for large renewables.

This dossier consolidates the disclosed engineering configuration, energy-yield assessment, and Extended Cost-Benefit Analysis (ECBA) from the project's Final Environmental Impact Assessment (EIA, September 2025), together with the commercial structure defined by the CEB Standardized PPA template. Cost-engineering benchmarks and bottom-up capex scaling are documented separately in `01_wind_epc_costs_and_scaling.md`; the Sri Lankan tax treatment is covered in `04_sri_lanka_tax_and_regulatory.md`.

> **Note on verifiability.** The project-specific figures below (configuration, EIA energy yield, ECBA economics, SPPA clause values) are drawn from the project's own disclosure documents and are not independently verifiable from public reference sources. The *frameworks and benchmarks* surrounding them — reference-turbine specifications, typical onshore capacity factors, the deemed-energy/take-or-pay concept, and the economic-vs-financial / blended-finance rationale — have been validated against authoritative public sources and are cited inline; see **External validation & sources** near the end.

**Primary sources**
- Final EIA, *Proposed Envision Dutch Bay 150 MW Wind Farm Project* (September 2025), 344 pp — engineering, energy yield, Chapter 7 ECBA and Annexure III-M cost tables.
- CEB / Ministry of Energy **Standardized Power Purchase Agreement** (BOO basis, June 2025 draft template) for renewables ≥ 50 MW — Gazette 2246/24 (24 Sep 2021); Cabinet decision 17 Mar 2025.

---

## 1. Engineering Configuration

The final design comprises **15 × Envision EN220/10.0 wind turbine generators**, each rated 10.0 MW, for a nameplate capacity of **150 MW**.

| Parameter | Value |
|---|---|
| Turbine model | Envision EN220/10.0 |
| Unit rating | 10.0 MW |
| Number of WTGs | 15 |
| Total capacity | 150 MW |
| Hub height | 140 m |
| Rotor diameter | 220 m |
| Design standard | IEC 61400-1 |
| Salinity / corrosion class | IEC 60815 "very heavy" (marine-grade) |
| Build period | 2 years (≈ 40% / 60% phasing) |

An earlier feasibility-stage layout of 12 × 12.5 MW (EN-233/12.5) turbines was superseded by the larger-count, smaller-unit 15 × 10 MW final configuration.

**Reference-turbine context (10 MW class).** The financial model represents the array with the public **IEA Wind Task 37 10 MW offshore reference turbine (IEA-10.0-198-RWT)** — rated 10.0 MW, 198 m rotor (199.38 m exact), 119 m hub, IEC Class IA, direct-drive — a standardized, peer-reviewed reference design ([NREL/IEA Wind Task 37, 2019](https://docs.nrel.gov/docs/fy19osti/73492.pdf); [model repository](https://github.com/IEAWindSystems/IEA-10.0-198-RWT)). (The IEA-10.0-198-RWT is the Task 37 *offshore* reference turbine; the Task 37 *land-based* reference is the smaller IEA-3.4-130-RWT. The physical specs cited here — 10 MW / 198 m rotor / 119 m hub / Class IA / direct-drive — are the offshore machine's.) The comparable academic reference is the **DTU 10 MW (178 m rotor, 119 m hub, Class 1A)**. The commercial **Envision EN220/10.0** sits at the same 10 MW rating but with a substantially **larger rotor (220 m) and higher hub (140 m)** than either reference — i.e. a markedly lower specific power (≈ 263 W/m² for the EN220 versus ≈ 325 W/m² for the IEA-10.0-198). Lower specific power is the modern design lever that lifts capacity factor at a given wind class, and it is the engineering basis for the EN220's higher disclosed CF; the reference-turbine specifics are what the model's "15 × IEA-10 MW" placeholder stands in for.

### Battery Energy Storage System (BESS)

An **11 MW / 23.8 MWh BESS** is co-located at the site for frequency regulation, voltage support, and peak-shaving, with its own SCADA. The storage is integrated at the project's new **220 kV / 150 MVA collector / booster substation**.

### On-site grid interface

The project's grid scope is limited to the on-site collector and 220 kV booster substation. The marine coastal setting (IEC 60815 "very heavy" salinity) drives marine-grade corrosion protection across foundations, towers, and electrical equipment — a meaningful durability and cost consideration.

---

## 2. Energy Yield

The disclosed wind resource is approximately **8.3–8.45 m/s at 130 m**, with wake losses in the 3–17% range. Net annual energy production (AEP) and capacity factor (CF) from the EIA:

| Exceedance | Net AEP (GWh/yr) | Capacity factor | Full-load hours |
|---|---|---|---|
| **P50** | **464.5** | **35.4%** | ~3,098 |
| P75 | 427.5 | 32.6% | — |
| P90 | 385.8 | 29.4% | — |

The disclosed **P50 capacity factor of 35.4% is consistent with — and modestly above — the IRENA global weighted-average onshore CF of 34% in 2024** (up from 27% in 2010, driven by larger rotors and higher hub heights) ([IRENA, *Renewable Power Generation Costs in 2024*](https://www.irena.org/Publications/2025/Jun/Renewable-Power-Generation-Costs-in-2024)). A 35.4% CF is credible for a strong, steady **south-west monsoon coastal site** equipped with a low-specific-power 220 m-rotor machine, while remaining well short of the optimistic >40% values seen only at the very best onshore sites — i.e. it is a plausible base case rather than an aggressive one.

The project represents roughly 2.7% of national electricity demand. For bankable financial structuring, the P50 figure is the appropriate base case, while debt sizing should reference the P90 yield. The financial model carries an AEP of ~473.8 GWh, approximately 2% above the EIA P50 — a recalibration toward 464.5 GWh (base) and 385.8 GWh (debt-sizing) is the conservative treatment. See `03_energy_yield_and_resource_methodology.md` for the P50/P90 framework and `05_pf_analyst_playbook.md` for the P50-bias discussion.

### 2.1 Wake parametrization and coastal turbulence-intensity sensitivity (#832)

The bankable engine models array wake loss over the real 15-turbine layout with PyWake's **Bastankhah–Porté-Agel 2014 Gaussian** deficit, whose wake-growth rate is set by the site **ambient turbulence intensity (TI)** through the Niayifar & Porté-Agel (2016) closure **`k* = 0.38·TI + 0.004`** (`wind_resource/bankable_aep.py::gaussian_k_star`). Lower TI, characteristic of a **low-roughness coastal/water fetch** (`z₀ ≈ 0.01–0.1 m`, versus `0.1–1 m` onshore), produces a smaller `k*` and hence slower cross-wind wake spreading.

> **Do NOT hardcode the "coastal 0.04" figure.** The often-quoted coastal wake-decay ≈ 0.04 (vs onshore 0.075) is a **Jensen/Park-model** constant and does **not** map onto the Gaussian `k*`. The correct, physically consistent lever is the **site TI**, not a transplanted Jensen decay constant.

**Sensitivity (screening, recomputed — not assumed).** Sweeping ambient TI over the committed 15-turbine single-row layout and SW-dominant wind rose (IEA 10 MW reference curve, Weibull a=8.199, k=2.665) gives the modelled array wake loss below. Numbers come from actual PyWake recomputation via `wind_resource.bankable_aep.wake_loss_ti_sensitivity`, against the **live-path baseline TI = 0.10** (which yields ≈ 8.19% here; note this differs from the frozen headline 7.28%, computed offline with the committed inputs — the sensitivity slope, not the absolute level, is the deliverable):

| Ambient TI | `k* = 0.38·TI + 0.004` | Modelled array wake loss | Δ vs TI=0.10 |
|---|---|---|---|
| 0.06 | 0.0268 | 8.68% | **+0.49 pp** |
| 0.08 | 0.0344 | 8.43% | +0.24 pp |
| **0.10** (baseline) | **0.0420** | **8.19%** | 0.00 pp |
| 0.12 | 0.0496 | 7.94% | −0.25 pp |
| 0.14 | 0.0572 | 7.68% | −0.51 pp |

Mean slope ≈ **−0.13 pp of array wake loss per +0.01 TI** (equivalently, **+0.13 pp per −0.01 TI**) over this range. The direction is the honest, counter-intuitive result the issue warns about: for this **densely-packed single row**, a *lower* coastal TI *raises* modelled wake loss (slower recovery-width growth keeps downwind turbines deeper in the deficit) — so "coastal ⇒ lower wake loss" is **not** a safe assumption and must not be baked in blind. The sign and magnitude are layout- and spacing-dependent; a wider or 2-D array would trade off differently.

**Data dependency and gating.** The coastal-appropriate TI is a **documented assumption** until validated by **site mast / lidar** turbulence measurement; absent that, adopting a non-default TI is provenance-tagged and does **not** change any committed number. The parametrization ships **default-OFF**: an unset `resource.wake.turbulence_intensity` reproduces the current `k*` (TI = 0.10) exactly, and the frozen headline wake loss (7.28%) is untouched. Enabling a coastal TI (which moves modelled AEP) is a separate, **oracle-gated (`kpi_oracle.py`) and adversarially-reviewed** config edit — never folded into a feature/GIS change (issue #832, epic #827; `seq:3-correctness`).

---

## 3. Project Economics (EIA Extended Cost-Benefit Analysis)

The EIA's Chapter 7 ECBA, supported by the Annexure III-M detail tables, distinguishes **financial** capital cost (the cash the project actually spends) from **economic** capital cost (shadow-priced for the national cost-benefit analysis). These are not interchangeable: the financial figure drives equity returns; the economic figure exists only for the societal CBA.

### Capital cost

| Basis | Capex (US$ M) | $/kW | Notes |
|---|---|---|---|
| **Financial** | **212.97** | **~1,420** | Anchor for the financial model |
| Economic | 200.90 | ~1,339 | Financial − transfer payments, × national Standard Conversion Factor 0.95 (CBA only) |

Financial capex breakdown (Annexure III-M, Table 1):

| Component | US$ M | Share |
|---|---|---|
| Equipment + installation | 162.77 | 76% |
| Civil works | 22.41 | — |
| Other (development & owner&#39;s costs) | 17.65 | — |
| Contingency (5%) | 10.14 | — |

The disclosed financial capex of **~US$1,420/kW** sits above IRENA's 2024 global weighted-average onshore total installed cost of **US$1,041/kW** ([IRENA 2024](https://www.irena.org/Publications/2025/Jun/Renewable-Power-Generation-Costs-in-2024)), which is expected: the global average reflects mature, scale-advantaged markets, whereas an island-grid project with marine-grade corrosion protection, a dedicated 220 kV booster substation, BESS, and importation logistics carries a structural premium. It remains below typical US onshore benchmarks. Import duty is only ~US$ 1.0 M, confirming that equipment enters essentially duty-free under the renewable-energy concession / bonded-warehouse scheme — consistent with the EPC cost structure discussed in `01_wind_epc_costs_and_scaling.md`.

### Operations & maintenance

O&M is budgeted at **3.5%/yr of capex** (3% in years 1–10, 4% in years 11–20), equivalent to roughly **1.55 US¢/kWh**, escalating ~0.25% real. Undiscounted lifecycle (20-year) O&M is approximately US$ 136.8 M.

### Economic returns

At a 14% discount rate (against an estimated WACC of 12.10%), the base (P50) case yields:

| Metric | Base (P50) |
|---|---|
| Economic IRR (EIRR) | **18.07%** |
| Economic NPV (ENPV) | **+US$ 48.96 M** |
| Benefit-Cost Ratio (BCR) | **1.21** |

ENPV is built from discounted economic benefits of US$ 282.93 M against discounted economic costs of US$ 233.98 M (Table 10, @14%). The result is robust under stress: CapEx +10% → EIRR 16.33%; Benefits −10% → 15.74%; both simultaneously → 14.15% / BCR 1.01; P75 yield → 16.35%; P90 yield → 14.34% / BCR 1.02. The economic case includes ~0.3 MtCO₂/yr of avoided emissions, ~Rs 8 bn/yr of fuel savings, energy-security value, and employment.

### The economic-vs-financial wedge (the blended-finance signature)

The decisive insight of the dossier is the gap between the EIA's **economic** return and the project's **financial** equity return:

| Lens | IRR | NPV |
|---|---|---|
| Economic (EIA ECBA, societal, externalities-in) | **EIRR 18.07%** | ENPV +US$ 48.96 M |
| Financial (model, equity, flat-LKR tariff) | **Project IRR ~2.75% / equity IRR −0.46%** | −US$ 53.3 M |

The ~15-point spread between the 18.07% economic return and the near-zero financial return is the value that the regulated, flat-nominal-LKR tariff does not pass through to private equity — compounded by FX and inflation erosion over the 20-year term. In other words, the project is highly valuable to the nation but value-destructive for equity at the standardized tariff. This is the textbook signature of a project that requires **concessional / blended finance**, or an indexed / higher tariff, to be privately bankable.

This wedge is precisely the condition that the development-finance community defines as the mandate for **blended concessional finance**: a project with strong development impact and a high *economic* return that is nonetheless not commercially viable at market terms, where a measured tranche of concessional capital can crowd in private investment without crowding it out. The IFC-chaired **DFI Working Group on Blended Concessional Finance** codifies this in five enhanced principles — (1) rationale for blended concessional finance, (2) crowding-in and minimum concessionality, (3) commercial sustainability, (4) reinforcing markets, and (5) promoting high standards ([IFC, *Blended Concessional Finance Principles*](https://www.ifc.org/wps/wcm/connect/corp_ext_content/ifc_external_corporate_site/solutions/products+and+services/blended-finance/blended-finance-principles); [IFC, *Using Blended Concessional Finance to Invest in Challenging Markets*, 2021](https://www.ifc.org/content/dam/ifc/doc/mgrt/ifc-blendedfinance-fin-092021.pdf)). The World Bank likewise frames the gap directly: where the socio-economic NPV is strongly positive but the financial NPV to equity is negative, the project is societally desirable yet not privately bankable without risk-mitigation or concessional support — the standard rationale for combining MDB/DFI concessional capital with commercial finance ([World Bank, *Sustainable Infrastructure Finance*](https://www.worldbank.org/en/topic/sustainableinfrastructurefinance/overview)). The gap widens further if the EIA's 12.10% WACC (rather than the model's ~8.10% hurdle) is taken as the true cost of capital. See `05_pf_analyst_playbook.md` for the blended-finance framing and DFI lens.

---

## 4. CEB Standardized PPA — Commercial Terms

Revenue is governed by the CEB / Ministry of Energy **Standardized Power Purchase Agreement** (BOO, June 2025 draft template) for renewables ≥ 50 MW. The template fixes the contractual *structure* with certainty; tariff and capacity values are filled per project. The terms below are the wind-applicable structure.

| Term | Provision |
|---|---|
| Basis / term | BOO; **20 years from Commercial Operation Date** (COD). Force majeure extends; COD delay shortens. |
| Tariff | **Flat LKR/kWh**, paid monthly in arrears in **LKR**. **No escalation, no FX indexation.** |
| Curtailment | **Compensated as deemed energy** — CEB/grid dispatch-down is paid at the full metered rate. |
| Availability | **95% guaranteed annual availability**; liquidated damages only below 94% (1% deadband). |
| Carbon credits | Accrue to the **Government of Sri Lanka** — no carbon revenue to the project. |
| Interconnection | SPV builds the on-site interface turnkey and hands it to CEB (CEB operates thereafter). |
| Payment security | **Escrow account** plus a CEB **standby Letter of Credit** sized at ~3 months of guaranteed output. |

### Tariff structure and currency risk

The tariff is a **flat nominal LKR/kWh** with no escalation and no FX indexation, settled monthly in LKR. This makes Dutch Bay a flat-nominal-rupee asset whose USD-equivalent revenue erodes as the rupee depreciates and as domestic inflation runs over the 20-year horizon. This single structural feature — not any one contractual clause — is the primary driver of the weak financial equity return. (The model's financial schedule is the contract's own Schedule 22, the "Project Company Financial Model.") The nearest priced data point under the same standardized regime is a comparable Kalpitiya wind PPA at a flat 21 LKR/kWh — see `04_sri_lanka_tax_and_regulatory.md`.

### Curtailment as deemed energy

Curtailment is compensated. Under Schedule 9.1, curtailed monthly output is computed from met-mast potential less WTG-fault losses less delivered energy, and **both delivered and curtailed energy are paid at the full metered rate**. The consequence for revenue modeling is important: **grid/CEB dispatch-down curtailment should not be haircut** — it is paid as deemed energy. Only WTG-fault unavailability and sub-cut-in wind go unpaid. The exception is ecological / avifauna adaptive curtailment (bird-bat shutdowns), which is proponent- or regulator-initiated rather than CEB-dispatched and is therefore likely an **uncompensated** AEP haircut.

This "deemed energy" / take-or-pay mechanism is a **standard bankability feature** of renewable PPAs, not a Sri Lanka-specific concession. Where the offtaker cannot physically take output and the plant is curtailed for reasons within the offtaker's control (e.g. grid dispatch-down or "economic curtailment"), bankable PPAs compute the energy that *would have been* produced and pay for it on a deemed-delivered basis, converting an availability-based revenue line into a take-or-pay obligation that lenders can size debt against ([World Bank PPP, *Power Purchase Agreements* guidance](https://ppp.worldbank.org/sector/energy/energy-power-agreements/power-purchase-agreements); [Stoel Rives, *Law of Solar — Utility-Scale PPAs*](https://www.stoel.com/insights/reports/the-law-of-solar/power-purchase-agreements-utility-scale-projects)). The same deemed-generation / allocation-of-curtailment-risk question was a central negotiated item in IFC's flagship Rewa Ultra-Mega Solar transaction in India ([World Bank, *Rewa Solar — Removing Barriers to Scale*](https://documents1.worldbank.org/curated/en/627561582530270545/pdf/Rewa-Solar-India-Removing-Barriers-to-Scale.pdf)). The convention that the generator bears WTG-fault/availability risk but is made whole for offtaker- or grid-driven curtailment is the standard allocation; the Dutch Bay SPPA follows it.

### Availability and liquidated damages

A 95% guaranteed annual plant availability applies, with liquidated damages triggered only if availability falls below 94% (a 1% deadband, force-majeure losses excluded). The LD penalty rate is set at 1.2× the tariff and is **capped at the energy charge for 10% of annual guaranteed output** per year, bounding the downside.

### Counterparty / payment-security structure

Payment risk is mitigated by an escrow arrangement and a CEB standby Letter of Credit, but the **L/C covers only about three months** of guaranteed output. CEB counterparty payment risk therefore remains the live residual revenue risk even with the PPA in place. Late-payment interest accrues at the Sri Lankan prime rate + 1.5%; disputes escalate to expert determination and then arbitration above a defined threshold. The WTG model must have an aggregate ≥ 100 MW in successful operation for ≥ 2 years (which the Envision-class turbine satisfies).

---

## 5. Transmission Evacuation — A Separate Utility Project

A common misconception is that the long high-voltage evacuation line is part of project capex. It is not. The ≈**104.77 km, 220 kV double-circuit (Twin Zebra) line** running from the Kalpitiya collector to the CEB Wariyapola switching station (plus two new bays) appears in the EIA only as an **associated facility** for environmental coverage. It is developed and funded **separately by CEB** — effectively a shared regional evacuation backbone for the wider Kalpitiya wind cluster.

The practical consequences:

- The US$ 212.97 M financial capex covers the **wind farm + BESS + on-site 220 kV collector/booster substation only** — the long line is not loaded onto it.
- Under the SPPA, **Dutch Bay pays no transmission / wheeling / use-of-system charge**; CEB takes delivery at the interconnection point and bears the grid. The energy charge is the sole cash flow. The grid side is therefore both **capex-light and opex-free** for the project.
- The residual risk is schedule-linked: **COD depends on CEB completing the line on time** (Sri Lankan grid builds frequently lag generation). This is partly mitigated by the SPPA's CEB-delay charge and the deemed-energy curtailment compensation described in Section 4.

---

## Summary of Key Figures

| Item | Value | Source |
|---|---|---|
| Configuration | 15 × Envision EN220/10.0 (10 MW) = 150 MW | EIA |
| Hub / rotor | 140 m / 220 m | EIA |
| BESS | 11 MW / 23.8 MWh | EIA |
| Substation | 220 kV / 150 MVA collector-booster | EIA |
| Build period | 2 years | EIA |
| P50 AEP / CF | 464.5 GWh / 35.4% | EIA |
| P75 / P90 AEP | 427.5 / 385.8 GWh | EIA |
| Financial capex | US$ 212.97 M (~$1,420/kW) | EIA Annexure III-M |
| Economic capex | US$ 200.90 M (~$1,339/kW) | EIA ECBA |
| O&M | 3.5%/yr (~1.55 US¢/kWh) | EIA / Cabinet Memo |
| EIRR / ENPV / BCR | 18.07% / +US$ 48.96 M / 1.21 @ 14% | EIA ECBA |
| Estimated WACC | 12.10% | EIA |
| PPA term / basis | 20 yr from COD / BOO | CEB SPPA |
| Tariff | Flat LKR/kWh, no escalation, no FX indexation | CEB SPPA |
| Availability guarantee | 95% (LD below 94%) | CEB SPPA |
| Payment security | Escrow + ~3-month standby L/C | CEB SPPA |
| Evacuation line | Separate CEB project; no wheeling charge | EIA / CEB SPPA |

---

## External validation & sources

The project-specific EIA/SPPA figures above are not publicly verifiable and are left intact. The following **frameworks and benchmarks** were checked against authoritative sources during the 2026-06-25 deep-research pass.

| Claim in dossier | Verdict | Authoritative source & current figure | Note |
|---|---|---|---|
| 10 MW-class reference turbine specs (the model's "IEA-10 MW") | **Confirmed / clarified** | NREL / IEA Wind Task 37 — **IEA-10.0-198-RWT** (the Task 37 *offshore* reference turbine): rated **10.0 MW, rotor 198 m (199.38 m exact), hub 119 m, IEC Class IA, direct-drive**. [NREL/IEA Task 37 report (2019)](https://docs.nrel.gov/docs/fy19osti/73492.pdf) · [model repo](https://github.com/IEAWindSystems/IEA-10.0-198-RWT) | The IEA-10.0-198-RWT is the Task 37 **offshore** reference (not the land-based one — that is the smaller IEA-3.4-130-RWT). Its 198 m rotor / 119 m hub are *not* the Envision EN220's 220 m / 140 m. The Envision is a commercial machine of the same rating with a larger, lower-specific-power rotor (≈263 vs ≈325 W/m²). Corrected the onshore/offshore label and added the distinction. |
| Comparable academic 10 MW reference | **Confirmed** | DTU 10 MW RWT: **10 MW, rotor 178 m, hub 119 m, IEC Class 1A**, direct-drive. [NREL turbine-models archive](https://nrel.github.io/turbine-models/DTU_10MW_178_RWT_v1.html) | Added as a second standard reference point. |
| P50 CF 35.4% is plausible for a strong coastal site | **Confirmed** | IRENA *Renewable Power Generation Costs in 2024*: onshore global weighted-average CF **34% in 2024** (27% in 2010). [IRENA 2024](https://www.irena.org/Publications/2025/Jun/Renewable-Power-Generation-Costs-in-2024) | 35.4% is modestly above the global average — credible for a low-specific-power machine on a monsoon coastal site; not aggressive. |
| Financial capex ~$1,420/kW vs benchmark | **Confirmed (premium explained)** | IRENA 2024: onshore global weighted-average **total installed cost US$1,041/kW**; onshore **LCOE US$0.034/kWh** (lowest of any new generation; −53% vs cheapest fossil). [IRENA 2024](https://www.irena.org/Publications/2025/Jun/Renewable-Power-Generation-Costs-in-2024) | Dutch Bay's premium over the global average is consistent with island-grid logistics, marine corrosion protection, dedicated substation and BESS. |
| Deemed energy / take-or-pay curtailment compensation is standard | **Confirmed** | World Bank PPP guidance on PPAs; IFC Rewa Ultra-Mega Solar (deemed generation a central negotiated item); legal commentary on "economic curtailment" paid at contract price. [WB PPP PPAs](https://ppp.worldbank.org/sector/energy/energy-power-agreements/power-purchase-agreements) · [Rewa Solar (WB)](https://documents1.worldbank.org/curated/en/627561582530270545/pdf/Rewa-Solar-India-Removing-Barriers-to-Scale.pdf) · [Stoel Rives, Law of Solar](https://www.stoel.com/insights/reports/the-law-of-solar/power-purchase-agreements-utility-scale-projects) | Confirms the dossier's "don't haircut grid curtailment" treatment is the standard bankability allocation. |
| Economic return ≫ financial return → blended-finance case | **Confirmed** | IFC-chaired DFI Working Group, five blended-concessional-finance principles: (1) rationale for blended concessional finance, (2) crowding-in and minimum concessionality, (3) commercial sustainability, (4) reinforcing markets, (5) promoting high standards; World Bank framing of positive socio-economic NPV with negative private NPV. [IFC principles](https://www.ifc.org/wps/wcm/connect/corp_ext_content/ifc_external_corporate_site/solutions/products+and+services/blended-finance/blended-finance-principles) · [IFC 2021 report](https://www.ifc.org/content/dam/ifc/doc/mgrt/ifc-blendedfinance-fin-092021.pdf) · [WB Sustainable Infrastructure Finance](https://www.worldbank.org/en/topic/sustainableinfrastructurefinance/overview) | Strengthens the dossier's central thesis with the precise DFI doctrine. |

---

## Changelog (deep-research update 2026-06-25)

**Confirmed**
- The 10 MW reference-turbine class the model uses corresponds to the public IEA Wind Task 37 **IEA-10.0-198-RWT** (10 MW / 198 m rotor / 119 m hub / Class IA, the Task 37 *offshore* reference) and the academic **DTU 10 MW** (178 m / 119 m / Class 1A) — both verified against NREL/IEA Task 37 sources.
- P50 capacity factor of 35.4% is consistent with (modestly above) IRENA's 34% global weighted-average onshore CF for 2024.
- Deemed-energy / take-or-pay curtailment compensation is a standard, bankability-driven PPA feature (World Bank PPP guidance; IFC Rewa Solar) — validating the "do not haircut grid curtailment" modeling treatment.
- The economic-return-exceeds-financial-return wedge as the trigger for blended concessional finance is exactly the IFC/DFI Working Group doctrine and the World Bank's positive-socio-economic-NPV / negative-financial-NPV framing.

**Corrected / clarified**
- Corrected the turbine label: the **IEA-10.0-198-RWT is the IEA Wind Task 37 *offshore* reference turbine**, not the land-based one (the Task 37 land-based reference is the smaller IEA-3.4-130-RWT). The physical specs (10 MW / 198 m rotor / 119 m hub / Class IA / direct-drive) are unchanged and correct.
- Made explicit that the **IEA/DTU 10 MW references (198 m / 178 m rotors, 119 m hubs) are distinct from the commercial Envision EN220/10.0 (220 m rotor, 140 m hub)**; the Envision is the same rating but a larger, lower-specific-power rotor, which is the engineering basis for its higher CF. Added a "Reference-turbine context" paragraph to Section 1.
- Corrected the IFC blended-concessional-finance principles to the actual five: (1) rationale for blended concessional finance, (2) crowding-in and minimum concessionality, (3) commercial sustainability, (4) reinforcing markets, (5) promoting high standards. The earlier list double-counted "crowding-in" and "minimum concessionality" as two principles and omitted "promoting high standards."
- Contextualised the ~$1,420/kW financial capex against IRENA's $1,041/kW global average, explaining the island-grid/marine premium (no figure changed).

**Added**
- Inline IRENA 2024 capacity-factor and cost benchmarks in Section 2 and Section 3.
- A bankability-standard framing for deemed-energy curtailment in Section 4 (World Bank / IFC / legal sources).
- The IFC five-principle blended-concessional-finance doctrine and World Bank framing in Section 3's economic-vs-financial wedge.
- A new **External validation & sources** table mapping each validated claim to its authoritative URL and current figure.
- A verifiability note in the Overview clarifying which content is project-specific (unverifiable) vs benchmark (validated).

**Flagged**
- No external claim required an "[unverified]" tag; all benchmark/framework claims were corroborated by at least one authoritative primary source. The IRENA *Renewable Power Generation Costs in 2024* landing page and several primary PDFs returned HTTP 403 to direct fetch; figures were confirmed via IRENA's own reporting and reputable secondary coverage of the same report (LCOE US$0.034/kWh; installed cost US$1,041/kW; onshore CF 34% in 2024 vs 27% in 2010).
