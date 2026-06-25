# Dutch Bay 150 MW Wind + BESS: Engineering, Economics & PPA

## Overview

The Dutch Bay Wind Farm is a 150 MW onshore wind project with co-located battery storage, sited at Dutch Bay on the Kalpitiya peninsula, Puttalam District, Sri Lanka. The proponent is Envision Energy (turbine OEM acting as developer), with environmental consultancy by the Lanka Hydraulic Institute. The project sells its full output to the Ceylon Electricity Board (CEB) under the standardized Build-Own-Operate (BOO) Power Purchase Agreement regime introduced for large renewables.

This dossier consolidates the disclosed engineering configuration, energy-yield assessment, and Extended Cost-Benefit Analysis (ECBA) from the project's Final Environmental Impact Assessment (EIA, September 2025), together with the commercial structure defined by the CEB Standardized PPA template. Cost-engineering benchmarks and bottom-up capex scaling are documented separately in `01_wind_epc_costs_and_scaling.md`; the Sri Lankan tax treatment is covered in `04_sri_lanka_tax_and_regulatory.md`.

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

The project represents roughly 2.7% of national electricity demand. For bankable financial structuring, the P50 figure is the appropriate base case, while debt sizing should reference the P90 yield. The financial model carries an AEP of ~473.8 GWh, approximately 2% above the EIA P50 — a recalibration toward 464.5 GWh (base) and 385.8 GWh (debt-sizing) is the conservative treatment. See `03_energy_yield_and_resource_methodology.md` for the P50/P90 framework and `05_pf_analyst_playbook.md` for the P50-bias discussion.

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

Import duty is only ~US$ 1.0 M, confirming that equipment enters essentially duty-free under the renewable-energy concession / bonded-warehouse scheme — consistent with the EPC cost structure discussed in `01_wind_epc_costs_and_scaling.md`.

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
| Financial (model, equity, flat-LKR tariff) | **Project IRR ~5.05% / equity IRR −2.47%** | −US$ 35.5 M |

The ~13-point spread between the 18.07% economic return and the near-zero financial return is the value that the regulated, flat-nominal-LKR tariff does not pass through to private equity — compounded by FX and inflation erosion over the 20-year term. In other words, the project is highly valuable to the nation but value-destructive for equity at the standardized tariff. This is the textbook signature of a project that requires **concessional / blended finance**, or an indexed / higher tariff, to be privately bankable. The gap widens further if the EIA's 12.10% WACC (rather than the model's ~8.18% hurdle) is taken as the true cost of capital. See `05_pf_analyst_playbook.md` for the blended-finance framing and DFI lens.

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
