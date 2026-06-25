# Battery Energy Storage (BESS): Technology, Pricing & Revenue Models

This reference consolidates the technology, cost, and revenue-model knowledge underpinning battery energy storage scenarios in the financial model. It complements the wind-focused references in this knowledge base — see `01_wind_epc_costs_and_scaling.md` for generation EPC costing — and is written to support a first-class `type: bess` parameterization alongside wind and solar.

The single most important framing point: **BESS is not a capacity-factor × tariff generator.** Storage has no annual energy production (AEP) and no capacity factor in the generation sense. The conventional revenue formula `capacity_mw × capacity_factor × tariff` does not apply. The cost side of BESS is well-bounded by public benchmarks; the revenue/dispatch side is the genuine modelling decision, and it is determined by which procurement structure (tender) a project is bidding into.

---

## 1. Technology and Modelling Defaults

### 1.1 Chemistry: LFP dominance

Lithium iron phosphate (LFP) is the decisive default chemistry for stationary storage:

- LFP represents **>90% of 2025 global stationary additions** and is projected to remain the #1 chemistry **through 2035**.
- NMC/NCA chemistries have collapsed from ~50% share in 2021 to a projected **~1% by 2029** for stationary applications.
- Sodium-ion remains secondary to ~2035; flow chemistries (vanadium, iron) are niche, confined to long-duration applications.

The sensible default is an **LFP system of 2–8 hours duration**. (Source: BloombergNEF.)

### 1.2 Rating and sizing defaults (utility LFP, 2025-verified)

| Parameter | Default | Notes / source |
|---|---|---|
| Round-trip efficiency (RTE) | **90%** | Ember; Lazard cites up to 92% |
| Depth of discharge (DoD) | **90%** | Standard for LFP cycling |
| Annual degradation | **~2%/yr** | → ~65% usable capacity after 20 years (without augmentation) |
| Design life | **20 yr / 10,000–12,000+ cycles** | Calendar and cycle life |
| Cycling rate | **~290–350 cycles/yr** | Lazard 350/yr @90% DoD; Ember ~290/yr (~80%, daily) |
| Opex | **~2% of capex ≈ $2.5/kWh/yr** | Excludes augmentation |
| Modelling horizon | **20 years** | Aligns with DFI debt tenor |

Relevant standards: **UL 9540** (system certification), **UL 9540A** (a fire-propagation test method, not itself a certification), and **IEC 62933**. Reference tools include NREL's System Advisor Model (SAM) and Annual Technology Baseline (ATB).

C-rate, parasitic loads, the augmentation schedule, and usable-versus-nameplate capacity are implied by the above but should be quantified per project rather than assumed.

---

## 2. 2026 Turnkey Pricing Benchmarks

### 2.1 Use the turnkey layer — do not conflate the three cost layers

BESS pricing is reported at three distinct layers that must not be confused:

| Layer | Indicative 2025 price | Meaning |
|---|---|---|
| Cell | ~$40/kWh (China LFP) | Bare cell only |
| Stationary pack | ~$70/kWh | Assembled pack |
| **Turnkey (global)** | **~$117/kWh** | Full system, installed — **use this layer for capex** |

The turnkey figure (BNEF 2025) fell ~31% year-on-year, with 2-hour systems around $124/kWh and 4-hour around $110/kWh.

### 2.2 Regional turnkey spread and the Sri-Lanka proxy

Turnkey prices vary widely by region: **China ~$73/kWh ≪ Europe ~$177/kWh ≪ US ~$219/kWh**.

For Sri Lanka, the most relevant public proxy is the **Ember ex-China / ex-US "all-in" figure of ~$125/kWh** — built up as roughly a **$75/kWh Chinese core plus ~$50/kWh of local installation and grid integration** — implying a levelised cost of storage (LCOS) on the order of **~$65/MWh**. This is the recommended planning anchor for a Sri Lankan grid-scale system.

For cross-reference, Lazard's LCOS v10.0 (June 2025) reports US unsubsidised storage at **$115–254/MWh for 4-hour** and **$129–277/MWh for 2-hour** systems; its 50 MW / 4-hour hybrid case carries capital of $122–313/kWh excluding the inverter.

### 2.3 Augmentation is excluded — and must be added

**All headline turnkey and LCOS figures above exclude augmentation** (the periodic capacity top-ups needed to offset degradation). Over a 20-year DFI tenor this is material and must be modelled explicitly rather than absorbed into the headline $/kWh.

### 2.4 Benchmark caveats (load-bearing)

- **2025 was a sharp down-year** driven by EV-cell oversupply; 4-hour LCOS fell only ~5% across 2020–2025, with most of the capex step concentrated in 2024→2025. **2026 figures are preliminary** and should be re-baselined against ATB-2026 and the next BNEF survey.
- **No Sri Lanka-specific capex/opex/LCOS** figure survives independent verification; the Ember ex-China/US proxy stands in, and any CEB-grid integration premium above the ~$50/kWh installation allowance is an open input.
- **Indian "BESS" headline numbers are auction tariffs, not capex** — they fell ~71% over 2022–2025 on competitive bidding and viability-gap funding, and a large share of contracted capacity may be sub-viable. Do not read them as cost benchmarks.
- Lazard figures embed the US investment tax credit; Ember's $65/MWh embeds its own financing assumptions. **Reproduce these from inputs — do not hardcode the output.**

### 2.5 Hybrid sizing (wind + solar + BESS)

Co-locating PV and BESS on an existing wind grid connection is LCOE-advantageous across **PV/wind ratios of 90–140% when BESS is present** (versus ~82.5% PV-only) — BESS extends the optimal degree of PV oversizing, with the upper bound rising as storage duration increases. (NTUA, *Renewable Energy* 240, 2025; MILP study, directional.)

### 2.6 Sri Lanka market context

Grid-scale storage is now live in Sri Lanka: a domestic developer secured a 120 MW grid-scale BESS award (early 2026), the ADB is backing the country's first grid-scale BESS, and a 640 MWh tender is underway. These set real market reference points for bid sizing.

---

## 3. CEB BESS Revenue Models — Three Distinct Structures

Because BESS earns nothing from a `capacity_factor × tariff` formula, the revenue model must be selected from the procurement structure a project is bidding into. The Ceylon Electricity Board (CEB) has run **three economically distinct** structures. They are not variants of one spec — they require different financial treatments, and a `type: bess` block must select among them per scenario.

### 3.1 Model A — Distributed capacity-charge (availability tolling)

This is the best-documented and most directly modellable revenue structure.

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
