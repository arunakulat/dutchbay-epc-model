# Battery Energy Storage (BESS): Technology, Pricing & Revenue Models

This reference consolidates the technology, cost, and revenue-model knowledge underpinning battery energy storage scenarios in the financial model. It complements the wind-focused references in this knowledge base — see `01_wind_epc_costs_and_scaling.md` for generation EPC costing — and is written to support a first-class `type: bess` parameterization alongside wind and solar.

The single most important framing point: **BESS is not a capacity-factor × tariff generator.** Storage has no annual energy production (AEP) and no capacity factor in the generation sense. The conventional revenue formula `capacity_mw × capacity_factor × tariff` does not apply. The cost side of BESS is well-bounded by public benchmarks; the revenue/dispatch side is the genuine modelling decision, and it is determined by which procurement structure (tender) a project is bidding into.

> **Deep-research status (2026-06-25):** The externally-verifiable cost, chemistry, efficiency and revenue-taxonomy claims below have been validated against BloombergNEF, NREL (ATB / cost-projection reports), Lazard, the IEA and Ember. Full citations and any corrections are listed in **§6 External validation & sources**. Headline result: the pricing benchmarks are confirmed but are the **BloombergNEF *2025* survey** (published December 2025), not a 2026 vintage — the section is relabelled accordingly.

---

## 1. Technology and Modelling Defaults

### 1.1 Chemistry: LFP dominance

Lithium iron phosphate (LFP) is the decisive default chemistry for stationary storage:

- LFP represents **>90% of 2025 global stationary additions** and is projected to remain the #1 chemistry **through 2035**. (Confirmed: BloombergNEF — LFP accounted for more than 90% of annual additions in the global stationary market in 2025.)
- NMC/NCA chemistries have collapsed from ~50% share in 2021 to a projected **~1% by 2029** for stationary applications. BNEF's Dec-2025 pack-price survey puts the average **LFP pack at ~$81/kWh versus NMC at ~$128/kWh**, the cost gap driving the substitution.
- Sodium-ion remains secondary to ~2035; flow chemistries (vanadium, iron) are niche, confined to long-duration applications.

The sensible default is an **LFP system of 2–8 hours duration**. (Source: BloombergNEF.)

### 1.2 Rating and sizing defaults (utility LFP, 2025-verified)

| Parameter | Default | Notes / source |
|---|---|---|
| Round-trip efficiency (RTE) | **85%** (model default, NREL ATB 2024, #588); **90% optimistic fresh-AC anchor** | Ember/Lazard cite up to 90–92% for new AC-coupled systems; **NREL is more conservative — 86% (Mongird et al. 2020) and 85% in the 2024 ATB (Cole & Karmakar 2023)**. The model default is now 85% for bankable/lifetime modelling; use 90% only for fresh, optimistic AC RTE. |
| Depth of discharge (DoD) | **90%** | Standard for LFP cycling |
| Annual degradation | **~2%/yr** | → ~65% usable capacity after 20 years (without augmentation). Consistent with NREL stationary-degradation work (LFP retains >80% capacity after ~3,000 full cycles at 100% DoD, 25 °C). |
| Design life | **20 yr / 6,000–12,000+ cycles** | NREL/industry: LFP ~6,000–10,000+ cycles; calendar life is the binding constraint for daily-cycling grid duty over 15–20 yr. |
| Cycling rate | **~290–350 cycles/yr** | Lazard 350/yr @90% DoD; Ember ~290/yr (~80%, daily) |
| Opex | **~2% of capex ≈ $2.5/kWh/yr** | Excludes augmentation |
| Modelling horizon | **20 years** | Aligns with DFI debt tenor |

Relevant standards: **UL 9540** (the system safety *certification*, 1st ed. 2016), **UL 9540A** (a thermal-runaway fire-propagation *test method* — not itself a certification, 1st ed. 2017; 6th ed. with large-scale fire testing published March 2026), and **IEC 62933** (the international series with equivalent requirements; IEC 62933-5-2 references UL 9540A as an example test method). Reference tools include NREL's System Advisor Model (SAM) and Annual Technology Baseline (ATB).

C-rate, parasitic loads, the augmentation schedule, and usable-versus-nameplate capacity are implied by the above but should be quantified per project rather than assumed.

---

## 2. 2025 Turnkey Pricing Benchmarks (BNEF Energy Storage System Cost Survey 2025)

> **Vintage note:** these are the **BloombergNEF *2025* survey** figures (released December 2025), confirmed across BNEF and Ember reporting. They were previously labelled "2026" in this document; the data is 2025-vintage and the heading is corrected. 2026 figures will require re-baselining against the next BNEF survey and ATB-2026.

### 2.1 Use the turnkey layer — do not conflate the three cost layers

BESS pricing is reported at three distinct layers that must not be confused:

| Layer | Indicative 2025 price | Meaning |
|---|---|---|
| Cell | ~$40/kWh (China LFP) | Bare cell only |
| Stationary pack | ~$70–81/kWh | Assembled pack (BNEF Dec-2025: LFP pack ~$81/kWh; all-segment average $108/kWh) |
| **Turnkey (global)** | **~$117/kWh** | Full system, installed — **use this layer for capex** |

The turnkey figure (**BNEF 2025 survey: US$117/kWh global average**) fell **~31% year-on-year** (from an adjusted ~US$169/kWh in 2024), with **2-hour systems around $124/kWh and 4-hour around $110/kWh**. (All four numbers confirmed against BNEF/Ember reporting.)

### 2.2 Regional turnkey spread and the Sri-Lanka proxy

Turnkey prices vary widely by region: **China ~$73/kWh ≪ Europe ~$177/kWh ≪ US ~$219/kWh** (BNEF 2025, confirmed).

For Sri Lanka, the most relevant public proxy is the **Ember ex-China / ex-US "all-in" figure of ~$125/kWh** (Ember, October 2025) — built up as roughly a **$75/kWh Chinese core plus ~$50/kWh of local installation and grid integration** — implying that dispatchable solar-plus-storage reaches a total electricity cost on the order of **~$76/MWh** in Ember's analysis. This is the recommended planning anchor for a Sri Lankan grid-scale system. (The $75 + $50 split and the ~$76/MWh headline are confirmed in the Ember report.)

For cross-reference, Lazard's LCOS v10.0 (June 2025) reports **US *unsubsidised* storage at $115–254/MWh for 4-hour** and **$129–277/MWh for 2-hour** systems (both confirmed exactly); its 50 MW / 4-hour hybrid case carries capital of $122–313/kWh excluding the inverter.

**NREL contrast (important methodology gap).** NREL's ATB/cost-projection work gives a **2024 base-year *installed* cost of ~$334/kWh (2024$, built up from 2022$ bottom-up cost data) for a 4-hour utility-scale system** in the US — roughly 3× the BNEF $117/kWh global turnkey average. The gap is real and is driven by (i) US-specific balance-of-system, labour and soft costs versus a global/China-weighted turnkey average, (ii) a 2024 base year (built up from a 2022 bottom-up breakdown) versus a 2025 survey across a steep down-year, and (iii) bottom-up "installed" scope versus reported "turnkey" pricing. **Carry both anchors:** BNEF/Ember for a globally competitive EPC bid, NREL ATB as the conservative US/bottom-up bound.

### 2.3 Augmentation is excluded — and must be added

**All headline turnkey and LCOS figures above exclude augmentation** (the periodic capacity top-ups needed to offset degradation). Over a 20-year DFI tenor this is material and must be modelled explicitly rather than absorbed into the headline $/kWh.

### 2.4 Cost trajectory (IEA / BNEF)

Storage costs are on a steep secular decline, which is what makes the proxies above time-sensitive:

- **IEA:** the global average battery cost fell from ~$511/kWh in 2019 to **just below ~$213/kWh in 2024 (≈ −58%)**, more than −90% since 2010, and **could fall a further ~40% by 2030** (IEA, *Batteries and Secure Energy Transitions*, 2024).
- **BNEF:** 2025 was a sharp down-year (turnkey −31% YoY); pack prices hit a record **~$108/kWh** in 2025, with **stationary storage now the lowest-price battery segment** for the first time.

### 2.5 Benchmark caveats (load-bearing)

- **2025 was a sharp down-year** driven by EV-cell oversupply; 4-hour LCOS fell only ~5% across 2020–2025, with most of the capex step concentrated in 2024→2025. **2026 figures are preliminary** and should be re-baselined against ATB-2026 and the next BNEF survey.
- **No Sri Lanka-specific capex/opex/LCOS** figure survives independent verification; the Ember ex-China/US proxy stands in, and any CEB-grid integration premium above the ~$50/kWh installation allowance is an open input. **[unverified — Sri-Lanka-specific cost]**
- **Indian "BESS" headline numbers are auction *tariffs*, not capex** — the lowest 2025 standalone tariff was ~₹1.48 lakh/MW/month (~$1,580/MW/mo), down ~36% on 2024's ~₹2.3 lakh/MW/mo, on competitive bidding and 30% viability-gap funding; **~75% of 2-hour allocated capacity has been flagged "at-risk"** for viability. Do not read these as cost benchmarks. (Confirmed: Mercom India / ESS-News 2025–26.)
- Lazard figures embed (or exclude) the US investment tax credit depending on the case shown; Ember's headline embeds its own financing assumptions. **Reproduce these from inputs — do not hardcode the output.**

### 2.6 Hybrid sizing (wind + solar + BESS)

Co-locating PV and BESS on an existing wind grid connection is LCOE-advantageous across **PV/wind ratios of 90–140% when BESS is present** (versus ~82.5% PV-only) — BESS extends the optimal degree of PV oversizing, with the upper bound rising as storage duration increases. (NTUA, *Renewable Energy* 240, 2025; MILP study, directional.) **[peer-reviewed, directional — not independently re-derived here]**

### 2.7 Sri Lanka market context

Grid-scale storage is now live in Sri Lanka: **WindForce PLC secured Letters of Award (16 Feb 2026) for 12 standalone BESS projects totalling 120 MW / 480 MWh**, developed **BOO over a 15-year term** through CEB international competitive bidding (LKR ~20.79bn total, 80:20 debt:equity). The ADB is backing the country's first grid-scale BESS, and further tenders are underway. These set real market reference points for bid sizing. (Confirmed: SaurEnergy / Daily FT / EconomyNext, Feb 2026.)

---

## 3. CEB BESS Revenue Models — Three Distinct Structures

Because BESS earns nothing from a `capacity_factor × tariff` formula, the revenue model must be selected from the procurement structure a project is bidding into.

**Global framing.** Worldwide, grid-scale storage earns from three universal streams — **capacity payments** (paid for *being available* during system stress, called or not), **energy arbitrage** (buy/charge low, sell/discharge high), and **ancillary services** (short-term frequency/reserve grid-stability products). The mix is market-specific and shifts quickly (NREL; Modo Energy). The three CEB structures below map cleanly onto this taxonomy: **Model A = a capacity payment**, **Model C = energy arbitrage / time-shift**, and Model B is a build (EPC) contract rather than an operating revenue stream at all. Ancillary-services revenue is not (yet) a distinct CEB product line.

The Ceylon Electricity Board (CEB) has run **three economically distinct** structures. They are not variants of one spec — they require different financial treatments, and a `type: bess` block must select among them per scenario.

### 3.1 Model A — Distributed capacity-charge (availability tolling)

This is the best-documented and most directly modellable revenue structure, and it is a **capacity-payment** stream in the global taxonomy.

**Structure.** A fleet of distributed units (in the reference tender, 16 × 10 MW / 40 MWh distributed across multiple 33 kV grid-connection points — 160 MW / 640 MWh aggregate, 0.25C / 4-hour, BOO 15-year). The developer is paid a **capacity charge for being available**, not for energy delivered.

**Payment formula.** Payment = **R × Cpc × (ADSC / MDSC)**, where:

- **R** is a flat charge in **LKR/MW/month**, fixed for the full 15 years, **with no escalation and denominated in LKR only**.
- **MDSC** is the maximum dischargeable storage capacity; **ADSC** is the actual available capacity — so the charge scales by availability against the contracted capacity.
- An availability penalty applies: if monthly availability (MA) falls below 97%, payment is multiplied by `(1 − 2 × (0.97 − MA))`.

**Key terms.**

- CEB dispatches the asset (national system control centre, 15-minute blocks); there is **no per-kWh energy revenue** to the developer — only one-way liquidated damages flowing to CEB.
- Minimum **97% availability** (LD of 2× the charge, capped at 20%/month); minimum **85% RTE** (LD of 150% of peak tariff on the energy losses, with no upside for over-performance).
- Cycling capped at **≤400 full cycles/year** (Rainflow counting).
- A **maximum-dischargeable-capacity degradation covenant of 97.5% → 62.5% over 15 years (~2.5%/yr)** scales the contracted capacity over time.

**Modelling.** The revenue reduces to `rev = R × MW × (ADSC/MDSC) × availability − LDs`. The bid variable **R** is the developer's lever; everything else is a contracted covenant.

### 3.2 Model B — Single-site EPC supply (a single large central site)

A separate CEB structure procures a **single large site** (in the reference case, 100 MW / 4-hour = 100 MW / 400 MWh at one location) as a **CEB-owned night-peak supply asset**.

Critically, this is procured as an **EPC contract for the batteries and ancillaries**, not as an operating concession. The developer would be the EPC contractor, and its economics are the **construction-margin** on the EPC contract (contract price minus supply/build cost) realised over the ~1–2-year construction period. There is **no 15-year operating phase to bill**, no tolling stream, and no CFADS in the operational sense.

**Modelling implication.** This pattern does **not** fit an operational discounted-cash-flow generation engine. Representing it honestly requires a separate construction-margin module, not a `revenue.model` on the operating cash-flow path. It is recorded here as a distinct structure precisely so it is not shoehorned into the operational engine — and the EPC-procurement pattern is expected to recur as the utility scales storage.

### 3.3 Model C — Solar-plus-BESS night-peak energy tariff

A third CEB scheme (Cabinet-approved June 2025) pays a **flat energy tariff of 45.80 LKR/kWh** for energy **exported in the 18:30–22:30 night-peak window** from a BESS **charged only by an existing solar PV plant**. Terms: 10-year duration, BESS AC rating not exceeding the PV AC rating, structured as an addendum to the existing PV power purchase agreement.

This is the genuine **time-shift / arbitrage** model — charge from co-located solar during the day, discharge into the evening peak — and is the relevant structure where a hybrid project bolts storage onto an existing or planned solar asset.

### 3.4 Summary comparison

| | A — Distributed capacity charge | B — Single-site EPC | C — Solar+BESS night-peak |
|---|---|---|---|
| What is paid for | Availability (capacity) | Construction delivery | Energy in peak window |
| Revenue basis | LKR/MW/month tolling | EPC contract margin | LKR/kWh energy tariff |
| Global-taxonomy analogue | Capacity payment | (none — a build contract) | Energy arbitrage / time-shift |
| Indicative spec | 10 MW / 40 MWh units, 0.25C/4h | 100 MW / 400 MWh, single site | BESS ≤ host PV AC |
| Term | 15-yr BOO | ~1–2-yr build | 10-yr PPA addendum |
| Ownership | Developer (BOO) | CEB-owned | Developer (PV-coupled) |
| Currency | LKR, flat, no escalation | LKR (build cost) | LKR/kWh |
| Fits operating CFADS engine? | **Yes** | **No** (construction margin) | Yes (energy model) |

All three Sri-Lankan structures are **LKR-denominated**, consistent with an LKR-primary modelling numéraire. The flat, non-escalating LKR charge in Model A carries the same real-erosion exposure discussed for wind tariffs elsewhere in this knowledge base — see `02_ppa_and_tariff_structures.md`.

---

## 4. Representing the Capacity-Charge Model in the Financial Engine

The distributed capacity-charge structure (Model A) is implemented in the cash-flow engine as an **additive** revenue line that leaves all wind and solar scenarios unchanged.

**Discovery and formula.** A resolver locates technologies declared with `type: bess` under the `generation.technologies` block. The annual capacity-charge revenue is computed as:

```
R × power_mw × 12 × availability_factor × dispatchable_ratio
```

held flat across the contracted years (`contract_years`). The resolver fails loud on a mis-keyed BESS block and returns nothing when no BESS technology is present.

**Wiring.** The BESS revenue is added to total revenue in both cash-flow builders, so that the per-year and full-schedule code paths agree. Output rows separately carry `generation_revenue_lkr` and `bess_revenue_lkr`. When no `type: bess` block exists, the BESS contribution is exactly 0.0, leaving every wind and solar scenario **byte-identical** to before the feature was added.

**Reference scenario.** A standalone 10 MW / 40 MWh capacity-charge scenario illustrates the structure: storage-only (energy tariff set to zero), capex around $5M (~$125/kWh), and an illustrative bid charge R, producing marginal project economics where **R is the bid lever** that determines viability.

**Modelling gotchas for a standalone BESS scenario.**

- The engine is generation-centric: a `capacity_factor` of exactly 0 is rejected by validation (treated as missing). A standalone storage scenario uses a nominal placeholder capacity factor with the energy tariff set to zero.
- The `type` field is **authoritative** — a BESS unit is excluded from the generation AEP/CFADS split and from the generation-driven sensitivity sweep, so it can never be double-counted (once as tariff energy and once as a capacity charge).
- Availability and dispatchable ratios **fail loud outside [0,1]**; `contract_years` must be a positive whole number; `energy_mwh` is cross-asserted equal to `power_mw × duration_h`; non-finite inputs are rejected.
- Because scenario overrides deep-merge (they cannot remove wind or solar technologies from a hybrid base), a standalone BESS needs its own scenario file rather than an override of a generation scenario.

**Status.** The capacity-charge (Model A) revenue is folded into the engine and hardened. **BESS is a first-class model citizen** — it is simply outside the generation AEP/CFADS calculation, because storage is not generation. The night-peak energy-tariff model (Model C) is scaffolded as a separate revenue mode, and the single-site EPC structure (Model B) is intentionally left to a future construction-margin module rather than forced onto the operational path.

---

## 5. Building a `type: bess` Block — Reference Schema

A storage technology is declared under `generation.technologies.<name>` with an explicit `type: bess`, carrying three groups of inputs:

- **Rating:** `power_mw`, `energy_mwh` or `duration_h`, `rte`, `dod`, `annual_degradation_pct`, cycles/yr, `calendar_life_years`.
- **Cost:** `capex_per_kwh_usd` (~125 turnkey, ex-China/US), an augmentation schedule, and opex (~2%/yr).
- **Revenue:** the model selector — `capacity_charge` (Model A, standalone tolling) or the night-peak energy tariff (Model C, PV-coupled) — chosen per scenario.

Until a revenue model is wired for a given structure, a `type: bess` block must either fail loud or remain reporting-only, never silently contribute zero revenue while appearing active. The single-site EPC structure (Model B) is explicitly out of scope for the operational engine and belongs in a dedicated construction-margin module.

---

## 6. External validation & sources

Authoritative sources retrieved or surfaced during the 2026-06-25 deep-research pass. Each line gives the claim, the source, the current figure, and any correction.

- **Turnkey BESS price ~$117/kWh, −31% YoY (2025).** *Confirmed.* BloombergNEF *Energy Storage System Cost Survey 2025* via Energy-Storage.News, "Battery storage system prices continue to fall sharply" — global average **US$117/kWh in 2025, −31%** from an adjusted US$169/kWh in 2024. https://www.energy-storage.news/battery-storage-system-prices-continue-to-fall-sharply-bnef-and-ember-reports-find/ ; BNEF: https://about.bnef.com/insights/clean-energy/battery-storage-costs-hit-record-lows-as-costs-of-other-clean-power-technologies-increased-bloombergnef/
- **2-hour ~$124/kWh, 4-hour ~$110/kWh.** *Confirmed.* Same BNEF 2025 survey. (Energy-Storage.News link above.)
- **Regional spread China ~$73 / Europe ~$177 / US ~$219 per kWh.** *Confirmed.* BNEF 2025 survey. (Energy-Storage.News link above.)
- **Ember ex-China/US all-in ~$125/kWh ($75 core + $50 install), ~$76/MWh dispatchable solar.** *Confirmed.* Ember (October 2025), reported via the same Energy-Storage.News article. https://www.energy-storage.news/battery-storage-system-prices-continue-to-fall-sharply-bnef-and-ember-reports-find/
- **BNEF pack price record ~$108/kWh (2025); stationary now lowest-price segment; LFP pack ~$81 vs NMC ~$128/kWh.** *Confirmed / added.* BNEF Dec-2025 pack-price survey. https://about.bnef.com/insights/clean-transport/lithium-ion-battery-pack-prices-fall-to-108-per-kilowatt-hour-despite-rising-metal-prices-bloombergnef/
- **LFP >90% of 2025 global stationary additions; remains #1 through 2035.** *Confirmed.* BloombergNEF. https://about.bnef.com/insights/clean-energy/energy-storage-enters-the-100-gigawatt-era-three-things-to-know/
- **Lazard LCOS v10.0 (June 2025) unsubsidised: 4-hr $115–254/MWh; 2-hr $129–277/MWh.** *Confirmed exactly.* Lazard via Energy-Storage.News; primary PDF: https://www.lazard.com/media/uounhon4/lazards-lcoeplus-june-2025.pdf ; commentary: https://www.energy-storage.news/lazard-says-us-energy-storage-cost-reduction-in-2025-offsets-prior-pandemic-driven-increases/
- **NREL ATB 2024 base-year 4-hr installed cost ~$334/kWh (2024$, built up from 2022$ bottom-up data); RTE 85%.** *Added (methodology contrast).* NREL *Cost Projections for Utility-Scale Battery Storage* — the $334/kWh starting point is expressed in 2024$ (CPI-converted) and is derived from a 2022$ bottom-up cost breakdown (Ramasamy et al. 2023); RTE per Cole & Karmakar 2023. https://docs.nrel.gov/docs/fy25osti/93281.pdf ; ATB page: https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage
- **RTE 85–86% conservative anchor (vs 90% optimistic).** *Flagged / clarified.* NREL Mongird et al. (2020) = 86% representative RTE; 2024 ATB = 85%. The doc's 90% (Ember/Lazard) is the optimistic fresh-AC figure; bankable modelling should use 85–86%. (NREL ATB link above; Mongird via NREL ATB 2022.)
- **LFP cycle life ~6,000–10,000+; >80% capacity after ~3,000 full cycles at 100% DoD.** *Confirmed (range widened from "10,000–12,000").* NREL stationary lithium-ion degradation work. https://atb.nrel.gov/electricity/2022/utility-scale_battery_storage
- **Battery cost trajectory: ~$213/kWh in 2024, −58% since 2019, −40% possible by 2030.** *Added.* IEA, *Batteries and Secure Energy Transitions* (2024). https://www.iea.org/reports/batteries-and-secure-energy-transitions/outlook-for-battery-demand-and-supply ; https://www.iea.org/commentaries/battery-storage-is-scaling-up-and-taking-on-a-larger-system-role
- **UL 9540 (certification) vs UL 9540A (test method, not a certification) vs IEC 62933.** *Confirmed.* UL Solutions: https://www.ul.com/services/ul-9540a-test-method ; UL 9540A 6th ed. (large-scale fire test, March 2026): https://www.ul.com/news/ul-solutions-enhances-battery-energy-storage-system-safety-test-methods-address-industry
- **Indian "BESS" headlines are tolling tariffs, not capex; lowest 2025 ~₹1.48 lakh/MW/mo (−36% YoY); ~75% of 2-hr capacity flagged at-risk.** *Confirmed.* Mercom India: https://www.mercomindia.com/lowest-energy-storage-auction-tariffs-in-2025 ; ESS-News: https://www.ess-news.com/2026/05/19/india-awards-10-4-gw-of-standalone-bess-capacity-in-2025-but-tariff-viability-remains-a-concern/
- **Sri Lanka grid-scale BESS live: WindForce 120 MW / 480 MWh, 12 projects, BOO 15-yr, CEB ICB (Feb 2026).** *Confirmed.* SaurEnergy: https://www.saurenergy.com/solar-energy-news/sri-lanka-awards-first-120-mw480-mwh-bess-tender-for-12-projects-11138309 ; Daily FT: https://www.ft.lk/business/WindForce-leads-Sri-Lanka-s-first-ever-and-largest-120-MW-480-MWh-standalone-BESS-initiative/34-788579 ; EconomyNext: https://economynext.com/sri-lankas-windforce-secures-120mw-battery-storage-projects-261208/
- **Universal revenue taxonomy: capacity payment / energy arbitrage / ancillary services.** *Added (general framing).* NREL grid-scale storage FAQ: https://docs.nrel.gov/docs/fy19osti/74426.pdf ; Modo Energy: https://modoenergy.com/research/en/how-does-battery-energy-storage-make-money
- **No Sri-Lanka-specific capex/opex/LCOS verified.** *Flagged [unverified].* Ember ex-China/US proxy retained as the planning anchor; CEB grid-integration premium above ~$50/kWh remains an open input.
- **NTUA hybrid PV/wind/BESS sizing (90–140% ratio).** *Not independently re-derived.* Peer-reviewed (*Renewable Energy* 240, 2025); cited as directional.

> Project-specific content — the three CEB tender structures (Models A/B/C), the LKR payment formulae and covenants, the `type: bess` engine wiring and schema, and the 45.80 LKR/kWh night-peak tariff — derives from the user's CEB tender corpus and internal model, not public benchmarks, and is preserved unchanged.

---

## Changelog (deep-research update 2026-06-25)

**Confirmed (unchanged):**
- BNEF 2025 turnkey **$117/kWh, −31% YoY**; 2-hr **$124** / 4-hr **$110**; China **$73** / Europe **$177** / US **$219**.
- Ember ex-China/US **~$125/kWh** ($75 core + $50 install) and the **~$76/MWh** dispatchable-solar headline.
- **LFP >90%** of 2025 global stationary additions (BNEF).
- **Lazard LCOS v10.0 (June 2025)** unsubsidised **$115–254/MWh (4h)** and **$129–277/MWh (2h)** — verbatim match.
- UL 9540 / 9540A / IEC 62933 framing (9540A is a test method, not a certification).
- Sri Lanka market context — **WindForce 120 MW / 480 MWh, BOO 15-yr, CEB ICB**.
- Indian numbers are tolling tariffs not capex; sharp competitive decline; large at-risk share.

**Corrected:**
- Section 2 heading and prose relabelled from **"2026"** to **"2025"** pricing — the underlying data is the **BNEF Energy Storage System Cost Survey 2025** (released December 2025). Added an explicit vintage note.
- Design-life cycle band widened from "10,000–12,000" to **"~6,000–12,000+ cycles"** to match NREL/industry LFP range (~6,000–10,000+).
- NREL ATB dollar-year tag corrected from "(2022$)" to **2024$** — per NREL's *Cost Projections for Utility-Scale Battery Storage*, the ~$334/kWh starting point is expressed in 2024$ (CPI-converted) and is *derived from* a 2022$ bottom-up cost breakdown (Ramasamy et al. 2023). The figure, source and ~3× gap-to-BNEF framing are unchanged — only the dollar-year tag was imprecise.

**Added:**
- **NREL ATB 2024 contrast:** 4-hr US bottom-up **installed ~$334/kWh (2024$, built up from 2022$ data)** with **RTE 85%** (Cole & Karmakar 2023) — explains the ~3× gap to BNEF's global turnkey average and gives a conservative bound.
- **IEA cost trajectory:** ~$213/kWh (2024), −58% since 2019, a further ~40% possible by 2030.
- **BNEF Dec-2025 pack datapoint:** $108/kWh all-segment, LFP $81 vs NMC $128, stationary now lowest-price segment.
- **Universal revenue taxonomy** (capacity / arbitrage / ancillary) tying the three CEB structures to the global framework (NREL/Modo).
- New **§6 External validation & sources** with full URLs, and this changelog.

**Flagged:**
- **RTE 90%** is the optimistic fresh-AC figure; NREL's **85–86%** is the conservative bankable/lifetime anchor — both now shown with guidance on when to use each. **[range-flagged]**
- **No Sri-Lanka-specific capex/opex/LCOS** survives independent verification — proxy retained, premium an open input. **[unverified]**
- NTUA hybrid-sizing study cited as **directional / not re-derived**.
