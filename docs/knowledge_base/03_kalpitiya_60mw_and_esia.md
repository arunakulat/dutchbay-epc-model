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

| Layer | Standard | Current status (verified 2026-06-25) |
|---|---|---|
| National | Sri Lankan environmental law and permitting (incl. existing IEE) | — |
| IFC | **Performance Standards 2012, PS1–PS8** | 2012 edition still current; PS6 governs biodiversity / critical habitat |
| Equator | **Equator Principles (EP4)** | EP4 in force since 1 Oct 2020 (current version) |
| WBG EHS | General + Wind + Transmission & Distribution Environmental, Health & Safety Guidelines | General EHS Guidelines 2007; Wind Energy EHS Guidelines 2015 |
| Multilateral safeguards | **ADB Safeguard Policy Statement (SPS 2009)**, **World Bank Environmental & Social Framework (ESF)**, **AIIB ESF** | **ADB: SPS 2009 superseded by ADB ESF effective 1 Jan 2026** (SPS still applies to concept notes approved before that date); **WB ESF applies to IPF from 1 Oct 2018**; **AIIB ESF current version June 2024** |
| Biodiversity references | IUCN / National Red List, BirdLife IBA/KBA designations | — |

This is the standard DFI/Equator-bank bankability lens. Its presence confirms the project is being taken to **IFC / ADB / AIIB / Equator-bank standard** from the outset.

> **Framework-currency note (deep-research 2026-06-25).** Two of the multilateral citations have moved since the TOR was drafted and should be tracked as live:
> - **ADB** approved a new **Environmental and Social Framework (ESF) on 22 November 2024, effective 1 January 2026**, which supersedes the 2009 SPS for projects with a concept note approved on/after that date (the 2009 SPS continues to apply to earlier concept notes). Whichever instrument binds depends on ADB's pipeline timing for this transaction — for a financing reaching the market in 2026, the **ADB ESF (2026)** is the more probable reference, not the legacy SPS.
> - **AIIB**'s ESF current edition is the one **amended through 26 June 2024** (it replaced the November 2022 edition; the May 2021 and February 2019 editions are historic). The applicable version depends on when the project enters AIIB's pipeline.
>
> EP4, the WB ESF, and IFC PS 2012 (incl. PS6) remain the current editions and are confirmed unchanged.

### 2.2 ESAP as a condition precedent

The key deliverable is the **Environmental and Social Action Plan (ESAP)**, structured as a **financing condition precedent.** In practice this means the lender's commitment is contingent on an agreed, costed, time-bound set of E&S actions — the ESAP is where residual gaps against the standards stack are converted into obligations the borrower must close, and several of those obligations (offsets, monitoring programmes, curtailment protocols) carry directly into the financial model as opex or capex lines.

### 2.3 Procurement signal

The consultant selection is **QCBS, quality-first**, with price weighted at only ~10% of the award. The remaining weight sits on demonstrated ESIA/IFC-PS understanding, wind/avifauna/bat survey experience, methodology, team, and regional track record. The weighting itself is a signal: the developer is buying defensible, lender-acceptable E&S work, not the cheapest study.

---

## 3. Principal E&S Risk Register Feeding the Financial Model

For the financial model, the ESIA is less a capex input than a **source of AEP haircuts, a capacity-risk flag, and a COD-delay driver.** Four risks should be carried explicitly.

### 3.1 Biodiversity curtailment — the headline AEP haircut

Kalpitiya sits on the **Central Asian Flyway and within IBA-grade bird habitat**, which places it at the upper end of avian sensitivity. The Central Asian Flyway is a CMS-recognised flyway covering ~30 countries from the Arctic/Siberian breeding grounds to South Asian wintering grounds, supporting on the order of 600 migratory species; **Sri Lanka is the southern terminus of the route**, which is precisely why its north-west coastal wetlands carry such high avian sensitivity. The TOR mandates, as live operational requirements rather than aspirations:

- **SCADA-linked shutdown-on-demand** for birds;
- **seasonal (migratory) curtailment** windows;
- **low-wind-speed bat curtailment** (raising the cut-in wind speed during high-risk bat-activity periods);
- **shadow-flicker shutdown programming** for nearby receptors.

Each of these removes energy. The model should carry an explicit **biodiversity-curtailment line** in the loss stack. Indicative ranges for planning purposes, now anchored to the peer-reviewed evidence base:

| Driver | Indicative AEP loss | Evidence anchor |
|---|---|---|
| Bat low-wind cut-in curtailment | ~0.3–3% (well-designed cut-in ~5.0 m/s ≈ <1%; more aggressive/seasonal-blanket regimes can exceed it) | Arnett et al. 2011: cut-in 5.0 m/s ≈ 0.3% AEP loss / 6.5 m/s ≈ 1%, with 44–93% fatality reduction; Whitby et al. 2024 (decade review): 5.0 m/s ≈ 62% average fatality reduction. US grid-scale studies show AEP loss can range from <1% to >10% under aggressive scenarios. |
| Bird seasonal / on-demand shutdown | ~0.5–5% | Radar-assisted shutdown-on-demand at a Portuguese migratory-flyway site cut soaring-bird mortality effectively to zero with annual downtime falling to ~15 hours once the monitoring team had direct SCADA control — i.e. well-implemented SDOD can hold the AEP cost low, but a flyway-grade site biases the planning range upward. |

> **Refinement (deep-research 2026-06-25).** The previous "bat ~1–3%" figure is broadly defensible but should be read against the seminal evidence: the canonical Arnett et al. (2011) study found a **5.0 m/s cut-in costs ~0.3% of annual output** (≤1% at 6.5 m/s) while cutting bat fatalities 44–93%, so a *well-designed* bat-curtailment regime sits at the **low** end of the range. The upper end (≥3%, and in extreme blanket scenarios much higher) applies when cut-in speeds are raised aggressively or applied over long seasonal windows. Model the actual cut-in speed and seasonal window, not a flat band.

Given the flyway/IBA setting, the bird component should be modelled toward the upper end. Critically, these biodiversity haircuts **compound with any grid-export curtailment** imposed by the system operator — they are additive losses on top of, not a substitute for, transmission-side constraints.

### 3.2 IFC PS6 Critical Habitat — a capacity risk

A formal **Critical Habitat Assessment (CHA)** under IFC PS6 is required. PS6 (2012) defines Critical Habitat against **five criteria**: (1) habitat of significant importance to Critically Endangered and/or Endangered species; (2) habitat of significant importance to endemic and/or restricted-range species; (3) habitat supporting significant global concentrations of **migratory and/or congregatory species**; (4) highly threatened and/or unique ecosystems; and (5) areas associated with key evolutionary processes. Criterion (3) is the directly relevant trigger for a Central Asian Flyway coastal site. Given the IBA/KBA status, migratory corridor, and proximity to lagoon, dune, and potentially Ramsar-adjacent systems, a critical-habitat trigger is plausible. If triggered, the PS6 mitigation hierarchy requires a **net gain** of the biodiversity values for which critical habitat was designated, and can force:

- **removal or relocation of high-risk turbines** — directly fewer MW and lower AEP; and
- **biodiversity offsets / net-gain obligations** — additional opex and/or capex.

This is a genuine **capacity risk**, not merely a cost risk, and should be modelled as a downside scenario (e.g. loss of one to two turbines plus an offset cost line), distinct from the operational curtailment in §3.1.

### 3.3 Schedule — multi-season surveys as a COD-delay driver

A full ESIA requires a baseline study window plus, decisively, **bird and bat surveys spanning both migratory and non-migratory seasons.** That seasonal coverage requirement is the binding constraint on the timeline. Lender-grade wind ESIAs in practice run year-round (multi-season) biodiversity baselines — published DFI-financed ESIAs document campaigns spanning all four seasons across roughly 11 months to two survey years — so the survey calendar realistically adds on the order of **6–12 months to financial close**, with the ESIA study itself a development-cost line of roughly the magnitude expected for a South Asian wind ESIA of this scope. Delayed COD directly compresses IRR, so the survey calendar should be reflected as a schedule input, not buried in a generic contingency. [The specific dollar magnitude of the ESIA study budget for this project remains a project-specific input — unverified against a public benchmark.]

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

---

## External validation & sources

Each externally-verifiable claim below was checked against an authoritative source during a deep-research pass on 2026-06-25. Project-specific (non-public) content — the 21 LKR/kWh signed PPA, the 0.339 CF proxy, the QCBS ~10% price weight, the TOR's specific mandates — is not externally verifiable and is left as stated.

**Standards stack — frameworks**

- **IFC Performance Standards (2012), PS1–PS8 — confirmed current.** The 2012 edition remains in force; PS6 is the biodiversity standard. IFC PS6 page: https://www.ifc.org/en/insights-reports/2012/ifc-performance-standard-6 ; PS6 full text: https://www.ifc.org/content/dam/ifc/doc/2010/2012-ifc-performance-standard-6-en.pdf
- **IFC PS6 Critical Habitat — five criteria added (confirmed).** Critical Habitat = areas of high biodiversity value under five criteria (CR/EN species; endemic/restricted-range; significant concentrations of migratory/congregatory species; highly threatened/unique ecosystems; key evolutionary processes); designation triggers a **net-gain** requirement after the mitigation hierarchy. Source (PS6 text + IAIA criteria paper): https://documents1.worldbank.org/curated/en/898321491456820716/pdf/113846-WP-ENGLISH-PS6-Biodiversity-conservation-2012-PUBLIC.pdf ; https://conferences.iaia.org/2013/pdf/Final%20papers%20review%20process%2013/Critical%20Habitat%20Assessment%20using%20IFC%20PS6%20Criteria.pdf
- **Equator Principles EP4 — confirmed current; effective date added.** EP4 is the current version, in effect for all EPFIs since **1 October 2020** (extended from 1 July 2020 due to COVID-19); applies to project finance ≥US$10 M capital cost. EP4 text: https://equator-principles.com/app/uploads/The-Equator-Principles_EP4_July2020.pdf ; scope: https://equator-principles.com/about-the-equator-principles/
- **ADB Safeguard Policy Statement (2009) — CORRECTED / flagged.** SPS 2009 is being superseded: the **ADB Environmental and Social Framework (ESF), approved 22 November 2024, takes effect 1 January 2026**, superseding the SPS for projects with a concept note approved on/after that date; SPS 2009 continues to apply to earlier concept notes. ADB page: https://www.adb.org/who-we-are/environmental-social-requirements/safeguard-policy-statement ; SPS 2009 text: https://www.adb.org/sites/default/files/institutional-document/32056/safeguard-policy-statement-june2009.pdf
- **World Bank Environmental & Social Framework (ESF) — confirmed; scope added.** ESF (10 Environmental and Social Standards, ESS1–ESS10) approved 4 August 2016; applies to all Investment Project Financing initiated on/after **1 October 2018**. WB ESF: https://www.worldbank.org/en/projects-operations/environmental-and-social-framework ; ESS overview: https://www.worldbank.org/en/projects-operations/environmental-and-social-framework/brief/environmental-and-social-standards
- **AIIB Environmental & Social Framework — CORRECTED.** The current AIIB ESF is the edition **as amended through 26 June 2024** (replaced the November 2022 edition; May 2021 and February 2019 editions are historic). AIIB ESF page: https://www.aiib.org/en/policies-strategies/framework-agreements/environmental-social-framework.html ; June 2024 text: https://www.aiib.org/en/policies-strategies/_download/environment-framework/AIIB-Environmental-and-Social-Framework_ESF-June-2024.pdf

**Biodiversity / avifauna / bat evidence**

- **Central Asian Flyway — confirmed; detail added.** CMS-recognised flyway over ~30 countries from Siberian breeding grounds to South Asian wintering grounds; ~605 migratory species; Sri Lanka is the southern terminus. CMS: https://www.cms.int/legalinstrument/central-asian-flyway ; CAF Situation Analysis 2023: https://www.cms.int/sites/default/files/document/cms_cop14_inf.28.4.2_central-asian-flyway-situation-analysis-2023_e.pdf
- **BirdLife Important Bird Area criteria — confirmed.** Global A-criteria: A1 (globally threatened species — IUCN CR/EN/VU), A2 (restricted-range), A3 (biome-restricted), A4 (congregations ≥1% of global/biogeographic population). BirdLife DataZone: https://datazone.birdlife.org/site/ibacritglob
- **Bat low-wind-speed curtailment — refined with primary evidence.** Arnett et al. (2011, *Front. Ecol. Environ.*): raising cut-in from 3.5 to 5.0/6.5 m/s reduced bat fatalities **44–93%** with annual energy loss of **~0.3% (5.0 m/s) to ≤1% (6.5 m/s)**. https://esajournals.onlinelibrary.wiley.com/doi/abs/10.1890/100103 . Whitby et al. (2024, decade review): a 5.0 m/s cut-in reduces total bat fatalities by **~62% on average (95% CI 54–69%)**; ~33% reduction per +1.0 m/s. https://besjournals.onlinelibrary.wiley.com/doi/full/10.1002/2688-8319.12371 . US grid-scale modelling shows aggressive/seasonal-blanket curtailment can drive AEP loss from <1% to >10%. https://pmc.ncbi.nlm.nih.gov/articles/PMC8598023/
- **Bird shutdown-on-demand (SCADA) effectiveness — confirmed; evidence added.** Radar-assisted shutdown-on-demand at a Portuguese migratory-flyway wind farm achieved zero soaring-bird collision mortality across five autumns, with annual shutdown time falling from ~105 h to ~15 h once the monitoring team had direct SCADA control — i.e. SDOD is highly effective and its AEP cost is low when well implemented. https://link.springer.com/chapter/10.1007/978-3-319-51272-3_7 ; https://www.thebiodiversityconsultancy.com/insights/article/shutdown-on-demand-reducing-bird-fatalities-at-wind-farms-1/

**ESIA cost / duration benchmark**

- **Multi-season biodiversity baseline — confirmed as GIIP; duration anchored.** Lender-grade / DFI-financed wind ESIAs run year-round multi-season biodiversity baselines (documented campaigns of ~11 months to two survey years across all four seasons), consistent with the document's 6–12-month COD-delay estimate. EPFIs require a bankable ESIA meeting EP4 + IFC PS. Examples: https://www.dfc.gov/sites/default/files/esia/2023/amunet/WindFarm/Environmental_Social_Impact_Assessment.pdf ; https://www.itpenergised.com/obtaining-project-finance-the-bankable-environmental-and-social-impact-assessment-esia/ . The **specific dollar magnitude** of the ESIA study budget is **[unverified]** against a public benchmark and remains a project-specific estimate.

**Sri Lanka context**

- **Kalpitiya / NW-coast avian importance — partially confirmed.** Sri Lanka's NW coast (Mannar/Kalpitiya wetland complex) is a major Central Asian Flyway wintering/stopover region; reporting describes Sri Lanka receiving ~15 million migratory birds annually and the area being at the heart of a live wind-power-vs-bird-migration dispute. A site-specific IBA citation for the exact Kandakkuliya turbine footprint was **[not independently verified]** in this pass. Mongabay 2025: https://news.mongabay.com/2025/08/respite-for-now-for-bird-migration-hotspot-at-heart-of-sri-lankas-wind-power-dispute/

**Unverifiable / project-specific (left as stated):** signed 21 LKR/kWh × 20-yr PPA; 333.79 LKR/USD reference; CF 0.339; ~US$11.2 M/yr indicative revenue; QCBS ~10% price weight; the TOR's specific curtailment/CHA/CIA mandates; the ~6%/yr LKR depreciation path (a modelling assumption, not a published forecast).

## Changelog (deep-research update 2026-06-25)

**Confirmed (unchanged, now cited):**
- IFC Performance Standards 2012 (PS1–PS8) remain the current edition; PS6 governs biodiversity/critical habitat.
- Equator Principles EP4 is the current version (effective 1 Oct 2020).
- World Bank ESF (10 ESS) applies to IPF from 1 Oct 2018.
- Central Asian Flyway (CMS, ~30 countries, ~605 species; Sri Lanka as southern terminus) and BirdLife IBA A1/A4 criteria.
- Shutdown-on-demand and multi-season biodiversity baselines as Good International Industry Practice; 6–12-month COD-delay estimate.

**Corrected:**
- **ADB SPS (2009)** — flagged as being superseded by the **ADB ESF (approved 22 Nov 2024, effective 1 Jan 2026)**; SPS now applies only to concept notes approved before the effective date. Added a framework-currency note in §2.1.
- **AIIB ESF** — corrected the implicit "2021" reference to the **current June 2024 edition** (replaced Nov 2022; May 2021 and Feb 2019 are historic).

**Added:**
- IFC PS6's **five critical-habitat criteria** and the **net-gain** requirement, with Criterion 3 (migratory/congregatory concentrations) flagged as the relevant trigger (§3.2).
- Primary-evidence anchors for the curtailment loss table: Arnett et al. (2011) and Whitby et al. (2024) for bats; the Portuguese radar-SDOD case for birds (§3.1).
- A framework-currency note tracking the ADB and AIIB version changes (§2.1).
- An "External validation & sources" section with full URLs.

**Refined / flagged:**
- The bat-curtailment AEP range was widened/clarified from "~1–3%" to **"~0.3–3%"** with the evidence that a well-designed ~5.0 m/s cut-in costs ~0.3% AEP (≤1% at 6.5 m/s) while cutting fatalities 44–93%, and that aggressive/blanket regimes can exceed 3% (up to >10% in extreme US scenarios). Recommend modelling the actual cut-in speed and seasonal window rather than a flat band.
- The ESIA study **dollar magnitude** is marked **[unverified]** (no public benchmark retrieved); the **multi-season duration** is corroborated.
- A site-specific IBA designation for the exact Kandakkuliya footprint is marked **[not independently verified]**; the broader NW-coast/Kalpitiya CAF importance is corroborated.
