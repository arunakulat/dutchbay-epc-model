# Reconciliation & Knowledge-Update Report
*Deep-research validation pass — 2026-06-25*

This report summarises how the deep-research validation updated five renewable-energy knowledge-base documents. Per document: the most material confirmations, corrections, and new authoritative figures/citations, followed by what remains open or unverified.

---

## 01_wind_epc_costs_and_scaling.md
*Validated against IRENA RPGC 2024, Lazard LCOE+ v18.0, NREL Cost of Wind Energy Review 2024, ADB/CEB Mannar, SL Customs/KPMG.*

- **Confirmed:** IRENA 2024 onshore wind TIC **$1,041/kW**, LCOE **$0.034/kWh** (+3% YoY), CF 34%; Lazard v18.0 onshore capex **$1,900–2,300/kW**, fixed O&M $24.50–40/kW-yr (no variable O&M), 30-yr life, LCOE $37–86/MWh; SL bonded-warehouse duty/VAT shelter confirmed.
- **Corrected:** Lazard "up ~55% YoY" → **+49% over 2020–2025 (~8% CAGR)**; IRENA $850/kW relabelled as a *forward projection* (band $850–1,000/kW); "turbine 64–84% of TIC" re-attributed to IRENA's **2012** study (not 2024); unsourced "Bangladesh ~$1,900–2,100/kW" proxy replaced with verifiable **Mannar CEB1 ~$2,480/kW** in-country reference.
- **New figures/citations:** IRENA China LCOE $0.029/kWh (70% of 2024 installs); Mannar row (103.5MW / $256.7M / 30× Vestas V126 / COD 2021 / ADB-financed); 2025 bonded-warehouse amendment extending eligibility to renewable storage ≥1MWh; full "External validation & sources" section with URLs.

**Open / unverified:**
- IRENA "$727–2,110/kW" range removed from headline table (not substantiated).
- NREL precise land-based CapEx $/kW and turbine ~$1,100/kW — retained as order-of-magnitude; NREL hosts unreachable from sandbox (cited report NREL/TP-7A40-91775 / OSTI 2479271 is real).
- IRENA RPGC 2024 vintage labelled "June 2025" throughout — actual release **22 July 2025** (figures themselves correct; date should be fixed).
- Wood Mackenzie Oct-2025 line not re-verified this pass.

---

## 02_dutch_bay_project_dossier.md
*External frameworks/benchmarks validated via IRENA, NREL/IEA Wind Task 37, World Bank, IFC; project-specific EIA/SPPA figures left intact.*

- **Confirmed:** Model's "IEA-10 MW" reference = IEA Wind Task 37 **IEA-10.0-198-RWT** (10MW / 198m rotor / 119m hub / Class IA), DTU 10MW as academic peer; P50 CF 35.4% consistent with/modestly above IRENA's 34% global onshore CF; deemed-energy/take-or-pay curtailment compensation is standard bankability (WB PPP, IFC Rewa Solar); economic≫financial wedge = textbook IFC/DFI blended-finance trigger.
- **Clarified:** IEA/DTU 10MW references (198m/178m rotors) made explicitly **distinct from the commercial Envision EN220/10.0** (220m rotor, 140m hub) — larger/lower-specific-power rotor explains the higher CF. ~$1,420/kW capex contextualised against IRENA $1,041/kW global with island-grid/marine premium.
- **New citations:** inline IRENA 2024 CF/cost cites; WB/IFC/legal bankability framing for deemed-energy; IFC blended-finance doctrine; new "External validation & sources" table and verifiability note.

**Open / unverified:**
- **Correction needed — turbine classification:** the IEA-10.0-198-RWT is the IEA Wind Task 37 **offshore** reference turbine, not "land-based." (The Task 37 land-based machine is the IEA-3.4-130-RWT.) Physical specs cited are correct; the onshore/land-based label is wrong and should read "offshore."
- **Correction needed — IFC blended-finance principles mislabelled:** "crowding-in" and "minimum concessionality" are a **single** combined principle, and the fifth principle, **"Promoting High Standards,"** is omitted. Correct five: (1) Rationale for Blended Concessional Finance, (2) Crowding-in and Minimum Concessionality, (3) Commercial Sustainability, (4) Reinforcing Markets, (5) Promoting High Standards.
- Several IRENA/WB PDFs returned HTTP 403 to direct fetch; figures confirmed via IRENA publication page + reputable secondary coverage.

---

## 03_kalpitiya_60mw_and_esia.md
*Framework, biodiversity, and benchmark claims validated; project-specific PPA/CF/revenue/TOR preserved. (Verify: clean.)*

- **Confirmed (now cited with URLs):** IFC PS 2012 (PS1–PS8) current; EP4 effective 1 Oct 2020; WB ESF (10 ESS) applies to IPF from 1 Oct 2018; Central Asian Flyway (CMS, ~30 countries, ~605 species, SL as southern terminus); BirdLife IBA A1/A4; SDOD + multi-season baselines as GIIP; 6–12 month COD-delay estimate.
- **Corrected:** **ADB SPS 2009 → new ADB ESF** (approved 22 Nov 2024, effective **1 Jan 2026**; SPS now applies only to pre-effective-date concept notes) — the single most material change for a 2026 financing. **AIIB ESF current edition = June 2024** (not 2021/2022).
- **New figures/citations:** IFC PS6's five critical-habitat criteria + net-gain (Criterion 3 = migratory/congregatory concentrations = the trigger); curtailment evidence anchors — Arnett et al. 2011, Whitby et al. 2024 (bats), Portuguese radar shutdown-on-demand case (birds).

**Open / unverified:**
- Bat-curtailment AEP range refined from "~1–3%" to **"~0.3–3%"** (well-designed 5.0 m/s cut-in ≈ 0.3% AEP, ≤1% at 6.5 m/s, cutting fatalities 44–93%; blanket regimes can exceed 3%, up to >10% in extreme US cases) — recommend modelling actual cut-in speed/window.
- ESIA study dollar magnitude marked **[unverified]** (no public benchmark retrieved).
- Site-specific IBA designation for the exact Kandakkuliya footprint **[not independently verified]**; broader Kalpitiya/NW-coast CAF importance corroborated.

---

## 04_bess_technology_pricing_revenue.md
*Validated against BloombergNEF, NREL ATB, Lazard, IEA, Ember, UL/IEC and SL market sources.*

- **Confirmed:** BNEF 2025 turnkey **$117/kWh (−31% YoY)** (2h $124 / 4h $110; China $73 / Europe $177 / US $219); Ember ex-China/US **~$125/kWh** ($75 core + $50 install), ~$76/MWh dispatchable-solar headline; LFP >90% of 2025 global stationary additions; Lazard LCOS v10.0 (Jun 2025) unsubsidised $115–254/MWh (4h) and $129–277/MWh (2h); UL 9540/9540A/IEC 62933 framing; SL WindForce 120MW/480MWh BOO-15yr CEB award (Feb 2026); India tolling tariffs (LKR/MW/mo, −36% YoY, ~75% of 2-hr capacity flagged at-risk).
- **Corrected:** heading/prose said "2026 pricing" but underlying data is the **BNEF Energy Storage System Cost Survey 2025 (published Dec 2025)** — relabelled and dated.
- **New figures/citations:** NREL ATB 2024 4-hr US installed cost **~$334/kWh**, RTE 85% (methodology gap vs BNEF global-turnkey); IEA trajectory (~$213/kWh in 2024, −58% since 2019, ~40% further possible by 2030); BNEF Dec-2025 pack price ($108/kWh all-segment; LFP pack $81 / NMC $128; stationary now lowest-price segment); NREL Mongird 86% RTE; universal capacity/arbitrage/ancillary revenue taxonomy (NREL/Modo); full sources section.

**Open / unverified:**
- **RTE:** doc's 90% (Ember/Lazard) is optimistic vs NREL's conservative **85–86%** anchor — flagged, range given.
- No **Sri-Lanka-specific capex/LCOS** survives independent verification (proxy retained).
- **Minor:** NREL ATB ~$334/kWh tagged "(2022$)" — should read **2024$** (built up from 2022$ bottom-up data); figure, source, and ~3× gap framing all correct.

---

## 05_project_finance_methodology.md
*Validated against primary PF sources + IRD 2025/26 tax chart. (Verify: clean.)*

- **Confirmed (citations added):** DSCR ~1.30× / min ~1.20× and 70–80% gearing with CFADS-backwards sizing/sculpting (Yescombe + lender practice); P50/P75/P90 + **IEC 61400-15-2** as EYA bankability standard; Gaussian-copula zero tail dependence vs t/Clayton; CVaR coherence + Rockafellar–Uryasev formula; spreadsheet-error prevalence justifying pre-close audit.
- **Confirmed directly vs IRD 2025/26 chart (primary):** CIT 30%, dividend WHT 15%, interest WHT 10%, VAT 18% (from 1 Jan 2024), SSCL 2.5%, 6-year TLCF.
- **Corrected/refined:** DSCR table now gives empirical split (**solar 1.20–1.30× / wind 1.30–1.40× / merchant 1.75–2.00×**) instead of one generic band; lock-up threshold characterised more precisely.
- **New figures/citations:** NREL/Todd-et-al-2022 P50-bias (mean −1.2%, σ 4.8%, ~$10/MWh LCOE spread); explicit Rockafellar–Uryasev CVaR formula + LP/convexity note; IRENA cost-of-capital framing (WACC 3.8%→12%, ~200–300 bps over country risk); MIGA breach-of-contract / Non-Honoring-of-Sovereign-Obligations cover.

**Open / unverified:**
- Exact SL Second-Schedule depreciation line items (5 yr/20% plant, 20 yr/5% buildings) **[unverified]** — framework, straight-line basis, TLCF, and Enhanced Depreciation Allowance confirmed, but precise per-class rates not in the published chart; check against current Second Schedule.
- Verbatim "largely unmanageable for the private sector" retained as IRENA-supported paraphrase.

---

## Cross-cutting themes
- **Two substantive corrections still to apply** (both in doc 02): the IEA-10.0-198-RWT *offshore* (not land-based) label, and the *five* IFC blended-finance principles. All other documents are figure-clean.
- **Recurring vintage imprecision:** IRENA RPGC 2024 mis-dated "June 2025" (actual 22 July 2025) in doc 01; "2026 pricing" → BNEF 2025 survey in doc 04; NREL ATB dollar-year tag in doc 04. Figures correct in every case — labels only.
- **Persistent unverifiable cluster:** NREL-hosted CapEx/turbine specifics (sandbox host unreachable) and all Sri-Lanka-specific capex/LCOS benchmarks — proxies retained, flagged, never fabricated.
- **Most consequential single update:** doc 03's **ADB SPS → ESF** regime shift (effective 1 Jan 2026), which a 2026 Kalpitiya financing must track.
