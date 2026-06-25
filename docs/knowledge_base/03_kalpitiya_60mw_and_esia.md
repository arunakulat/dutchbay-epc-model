# Kalpitiya 60 MW Wind & the Lender-Grade ESIA

This document covers the standalone 60 MW Kandakkuliya / Kalpitiya wind project on Sri Lanka's north-west coast, the contractual and currency structure created by its signed flat-rate PPA, and the lender-grade Environmental and Social Impact Assessment (ESIA) framework mandated by its Terms of Reference. It is written as a reference for analysts wiring the project's environmental and social (E&S) risk register into a project-finance model. For the EPC cost basis used in the economics, see `01_wind_epc_costs_and_scaling.md`; for the PPA-erosion and currency mechanics referenced throughout, the standardized-PPA analysis in the sibling CEB-PPA document applies.

---

## 1. Project Overview and Commercial Structure

### 1.1 The asset

The project is a **60 MW onshore wind power plant at Kandakkuliya, Kalpitiya**, on Sri Lanka's north-west coast. It is a **separate, standalone development** — not a sub-block or variant of any larger Dutch Bay / Kalpitiya scenario in the model portfolio, and on a distinct site. The turbine count, model, and hub height are not fixed at the TOR stage; the layout is for the ESIA consultant and the developer's engineering team to describe. An Initial Environmental Examination (IEE) already exists for the site; lenders require this to be upgraded to a full ESIA for financial close, so the consultant is instructed to review — but not simply rely on — the existing IEE.

### 1.2 The signed PPA: flat 21 LKR/kWh, 20 years

The project carries a **signed Power Purchase Agreement at a flat 21 LKR/kWh over a 20-year term**, read as flat nominal LKR with no escalation. The commercial consequence is significant: **merchant price risk is off the table** between PPA execution and financial close. What gates Development Finance Institution (DFI) debt is no longer price discovery but the **ESIA and its Environmental and Social Action Plan (ESAP)**, which function as financing conditions precedent.

At a reference rate of roughly 333.79 LKR/USD, the tariff is approximately **6.29 US¢/kWh today**. Indicative gross production and revenue, on a modelled capacity-factor proxy of 0.339:

| Quantity | Value |
|---|---|
| Tariff (nominal) | 21 LKR/kWh (~6.29 US¢/kWh at ~334 LKR/USD) |
| Term | 20 years, flat nominal |
| Indicative net generation | ~178 GWh/yr (60 MW × CF 0.339 × 8,760 h) |
| Indicative gross revenue | ~LKR 3.74 bn/yr (~US$11.2 M/yr), pre-curtailment |
| Per-kW revenue | ~US$187/kW-yr, pre-curtailment |

These figures are indicative model outputs, not contractual quantities, and they are stated **pre-curtailment** — the E&S curtailment regime in §3 reduces them.

### 1.3 The core value risk: flat-nominal-LKR erosion

The defining financial risk of this asset is that **a flat nominal LKR tariff erodes hard in USD and real terms over a 20-year life.** Under a representative ~6%/yr LKR depreciation path, the 6.29¢ headline tariff falls to roughly **3.5¢ by year 10 and ~2.0¢ by year 20.** Any equity or debt service denominated or benchmarked in USD therefore sees its coverage decay year over year — the classic "cheap USD debt is an illusion" trap for an LKR-revenue asset.

The structural conclusion is that this is **fundamentally an LKR-denominated asset and should be evaluated and financed LKR-primary.** Doing so removes the headline FX mismatch but surfaces the second half of the tension: high (and declining) nominal LKR interest rates produce **front-loaded debt-service stress and tighter early-year DSCRs.** This **currency-versus-rate mismatch** — you can hedge the currency by going LKR-primary, but then you import the rate level — is the central modelling problem. A fixed-vintage FX stress path (rather than a single spot conversion) is the appropriate tool for quantifying it.

### 1.4 Curtailment now bites contracted revenue

Sri Lankan standardized PPAs are typically **take-and-pay (energy-only)**. Unless the executed PPA contains a **deemed-energy / curtailment-compensation clause**, any energy not delivered is simply unpaid. That matters here because the ESIA regime in §3 mandates biodiversity- and amenity-driven shutdowns, and the grid operator may impose export caps — and in a take-and-pay structure **all of those become uncompensated lost revenue rather than a met-but-curtailed payment.** Whether the PPA carries deemed-generation or curtailment-compensation provisions is the single most material open question for converting modelled AEP into bankable revenue.

---

## 2. The Lender-Grade ESIA Framework

The TOR is a genuinely lender-grade document: it scopes the ESIA to the **most-stringent-of** national law and the international DFI / Equator standard stack, and it makes the resulting action plan a condition of financing.

### 2.1 The standards stack

The ESIA must satisfy, taking the most stringent requirement where they differ:

| Layer | Standard |
|---|---|
| National | Sri Lankan environmental law and permitting (incl. existing IEE) |
| IFC | **Performance Standards 2012, PS1–PS8** |
| Equator | **Equator Principles (EP4)** |
| WBG EHS | General + Wind + Transmission & Distribution Environmental, Health & Safety Guidelines |
| Multilateral safeguards | **ADB Safeguard Policy Statement (SPS)**, **World Bank Environmental & Social Framework (ESF)**, **AIIB ESF** |
| Biodiversity references | IUCN / National Red List, BirdLife IBA/KBA designations |

This is the standard DFI/Equator-bank bankability lens. Its presence confirms the project is being taken to **IFC / ADB / AIIB / Equator-bank standard** from the outset.

### 2.2 ESAP as a condition precedent

The key deliverable is the **Environmental and Social Action Plan (ESAP)**, structured as a **financing condition precedent.** In practice this means the lender's commitment is contingent on an agreed, costed, time-bound set of E&S actions — the ESAP is where residual gaps against the standards stack are converted into obligations the borrower must close, and several of those obligations (offsets, monitoring programmes, curtailment protocols) carry directly into the financial model as opex or capex lines.

### 2.3 Procurement signal

The consultant selection is **QCBS, quality-first**, with price weighted at only ~10% of the award. The remaining weight sits on demonstrated ESIA/IFC-PS understanding, wind/avifauna/bat survey experience, methodology, team, and regional track record. The weighting itself is a signal: the developer is buying defensible, lender-acceptable E&S work, not the cheapest study.

---

## 3. Principal E&S Risk Register Feeding the Financial Model

For the financial model, the ESIA is less a capex input than a **source of AEP haircuts, a capacity-risk flag, and a COD-delay driver.** Four risks should be carried explicitly.

### 3.1 Biodiversity curtailment — the headline AEP haircut

Kalpitiya sits on the **Central Asian Flyway and within IBA-grade bird habitat**, which places it at the upper end of avian sensitivity. The TOR mandates, as live operational requirements rather than aspirations:

- **SCADA-linked shutdown-on-demand** for birds;
- **seasonal (migratory) curtailment** windows;
- **low-wind-speed bat curtailment** (raising the cut-in wind speed during high-risk bat-activity periods);
- **shadow-flicker shutdown programming** for nearby receptors.

Each of these removes energy. The model should carry an explicit **biodiversity-curtailment line** in the loss stack. Indicative literature ranges for planning purposes:

| Driver | Indicative AEP loss |
|---|---|
| Bat low-wind cut-in curtailment | ~1–3% |
| Bird seasonal / on-demand shutdown | ~0.5–5% |

Given the flyway/IBA setting, the bird component should be modelled toward the upper end. Critically, these biodiversity haircuts **compound with any grid-export curtailment** imposed by the system operator — they are additive losses on top of, not a substitute for, transmission-side constraints.

### 3.2 IFC PS6 Critical Habitat — a capacity risk

A formal **Critical Habitat Assessment (CHA)** under IFC PS6 is required. Given the IBA/KBA status, migratory corridor, and proximity to lagoon, dune, and potentially Ramsar-adjacent systems, a critical-habitat trigger is plausible. If triggered, the PS6 mitigation hierarchy can force:

- **removal or relocation of high-risk turbines** — directly fewer MW and lower AEP; and
- **biodiversity offsets / net-gain obligations** — additional opex and/or capex.

This is a genuine **capacity risk**, not merely a cost risk, and should be modelled as a downside scenario (e.g. loss of one to two turbines plus an offset cost line), distinct from the operational curtailment in §3.1.

### 3.3 Schedule — multi-season surveys as a COD-delay driver

A full ESIA requires a baseline study window plus, decisively, **bird and bat surveys spanning both migratory and non-migratory seasons.** That seasonal coverage requirement is the binding constraint on the timeline: it realistically adds on the order of **6–12 months to financial close**, with the ESIA study itself a development-cost line of roughly the magnitude expected for a South Asian wind ESIA of this scope. Delayed COD directly compresses IRR, so the survey calendar should be reflected as a schedule input, not buried in a generic contingency.

### 3.4 Cumulative impacts and grid clustering

The TOR's Cumulative Impact Assessment (CIA) explicitly covers the **wider Kalpitiya / north-west coastal wind development area**, existing operators, and "coordinated mitigation with grid and transmission operators." The corridor is saturating, which raises two coupled risks:

- **ecological cumulative impact** (concentrated avian/bat mortality and habitat pressure across multiple farms); and
- **corridor-wide grid-export curtailment** as cumulative wind capacity outpaces transmission and dispatch headroom.

A flat low-single-digit grid-curtailment haircut likely understates this clustering risk. Where feeder-level data exists, grid curtailment should be modelled from the network constraint rather than assumed as a flat percentage.

---

## 4. The Reusable ESIA Skeleton Approach

A lender-grade ESIA for a project like this can be drafted efficiently by separating what can be transferred from a prior regional study from what must be collected fresh in the field. The governing principle is a **strict reuse rule**:

> A prior regional EIA is a **template, methodology, and regional-context donor — never a data donor.**

### 4.1 What transfers (high reuse)

These elements are method and context, not site facts, and can legitimately be adapted from a well-built regional precedent:

- overall **report structure** and chapter architecture;
- the **IFC-PS / Equator / legal framework** register and crosswalk method;
- **impact-significance matrices** (e.g. Leopold-style significance scoring);
- **regional context** — Kalpitiya climate and oceanography, the Central Asian Flyway setting, north-west coastal ecology at the landscape scale;
- **same-OEM engineering** description patterns where the turbine supplier is shared;
- **management-plan skeletons** (ESMP / ESMMP, stakeholder engagement, grievance mechanism templates); and
- the **Ecosystem / Critical-habitat assessment (ECBA) method** framework.

### 4.2 What must be collected fresh (non-negotiable)

Copying any of the following from another project would fail lender due diligence:

- **all site field baselines** — avifauna and bat counts, habitat maps, fisheries and social baselines, water, noise, and air quality, site coordinates;
- a project-specific **PS-crosswalk, CHA, Cultural Resource Management, Stakeholder Engagement Plan, Labour Management Procedure, Livelihood Restoration Plan, and ESAP** where the donor study was a national EIA that did not contain them; and
- the project's **own transmission line** assessment, where any shared backbone line is a separate, associated-facility asset rather than part of this project's scope.

### 4.3 Field-survey programme

The fresh-data core of the programme is the **multi-season biodiversity survey**: avifauna and bat monitoring across both the migratory and non-migratory seasons, supported by habitat mapping and a critical-habitat screening, plus the standard physical-baseline campaigns (noise, air, water, soils) and the socio-economic and fisheries baseline. This survey calendar is what sets the ESIA timeline (§3.3) and ultimately the achievable COD.

---

## 5. Summary

The Kalpitiya 60 MW project is a **contracted wind asset** — signed 20-year flat-LKR PPA, merchant risk removed — whose principal residual risks are **financial-structural** (nominal-LKR erosion and the currency-versus-rate financing mismatch) and **environmental-social** (biodiversity curtailment, PS6 critical-habitat capacity risk, multi-season-survey COD delay, and corridor cumulative/grid effects). Its TOR sets a genuine IFC/ADB/AIIB/Equator-grade bankability bar, with the ESAP as a financing condition precedent. For the financial model, the ESIA contributes a **risk register, an AEP loss stack, and a schedule constraint** — and the economics should be run **LKR-primary**, with biodiversity curtailment in the loss stack and an economic-versus-financial gap that signals a blended-finance structure.
