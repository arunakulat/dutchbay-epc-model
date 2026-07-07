# DutchBay 150 MW Wind Farm — Complete Feasibility & Recommendation Study

**Project:** DutchBay Wind Farm — 159.6 MW (15 × IEA-Reference-10 MW), Dutch Bay, Kalpitiya, Puttalam District, Sri Lanka
**Prepared:** 2026-07-07 · **Basis:** live pipeline run, DutchBay EPC model `v15.3.0`, origin/main `a50b0bfce8e8`
**Canonical scenario:** `scenarios/dutchbay_lendercase_2025Q4.yaml` (5th-generation canon)
**Status of this document:** lender/DFI-grade feasibility. Every headline number traces to a fresh run artifact (§Appendix D). Framing is honest: on its committed flat-LKR PPA the project is **value-destructive**, and this study says so plainly.
**Run basis (full-stack):** unlike a finance-only pass — which reads a committed AEP summary — this study fired **every feasibility-relevant module end-to-end**: the wind-resource chain (ERA5 → Weibull → wake → bankable AEP), GeoGIS, micro-siting, the finance engine, a 100k-trial Monte-Carlo, global (Sobol/PAWN) sensitivity, the capital-structure optimiser, and the grid screen. The long path **reproduces the committed baseline** (fresh AEP 464.36 GWh → canon KPIs), and the exhaustive run **surfaced and fixed two real bugs** (grid `boundary_clip` #929, `ride_through` #930).

---

## 0. Executive summary & recommendation

DutchBay is a **technically sound, financially unviable-as-structured** 159.6 MW onshore wind project. The wind resource is real and bankable-grade; the economics fail because the revenue line — a **flat, non-escalating, non-FX-indexed 20.3 LKR/kWh CEB tariff** — cannot service USD/blended debt and clear an equity return once the LKR is allowed to depreciate at its data-derived ~5.9%/yr.

**Headline economics (live, canonical lender case):**

| Metric | Value | Read |
|---|---|---|
| Project IRR (unlevered, real) | **1.46 %** | far below the ~9.9 % build-up WACC → value-destructive |
| Equity IRR (levered) | **−5.84 %** | negative; equity MOIC 0.52 (< 1) |
| Project NPV @ WACC | **−$79.3 M** | negative in every scenario run |
| Min DSCR (covenant / per-period) | **1.286 / 1.30** | 1 equity-lockup year; sculpt holds 1.30 per period |
| LLCR / PLCR | **1.27 / 1.31** | thin but positive coverage |
| DSCR-solved gearing | **0.41** | debt auto-sized down to hold the 1.30 floor |

**The one-line verdict:** *the turbines will spin and the debt can (just) be sculpted to a 1.30 DSCR, but at the administered flat-LKR tariff the project returns ~1.5 % against a ~9.9 % cost of capital — it destroys value on a merchant/standalone basis.* The only way it clears is the **blended-finance / concessional case** (cf. the project's own Final EIA, which reports an **18.07 % economic IRR** under a very different capital-and-benefit frame).

**Recommendation:** **Conditional NO-GO on the current commercial terms; conditional GO only under a restructured revenue or capital stack.** Do not reach financial close at a flat-nominal-LKR 20.3 LKR/kWh tariff. Pursue, as conditions precedent, at least one of: (i) tariff FX-indexation or escalation; (ii) a materially concessional / grant-blended senior tranche; (iii) a shorter-tenor or availability-backed PPA that lifts the achievable DSCR. §11 lists the full conditions-precedent set. Development readiness rolls up to **RED** (financing uncommitted) despite a **GREEN** environmental status.

---

## 1. Project & context

| Attribute | Value |
|---|---|
| Capacity | 159.6 MW (15 × IEA Reference 10 MW, 10.638 MW rated) |
| Site | Dutch Bay, Kalpitiya, Puttalam District, North Western Province |
| Turbine-array centroid | 8.27 °N, 79.75 °E |
| Grid POI | Puttalam 220 kV substation (33 kV collector → 220 kV) |
| COD | 2027 (2-yr construction, 1-yr PPA-to-FC) |
| Operating life | 20 years |
| Offtaker | Ceylon Electricity Board (CEB), credit B+ (S&P) |
| PPA | CEB standardized BOO, 20-yr, **flat 20.3 LKR/kWh, fixed, no escalation, no FX index** |
| Developer | DutchBay Wind Power Pvt Ltd |

The 220 kV evacuation line is a **separate CEB-funded project** (not in this project's capex or wheeling charge). The site sits in the same Kalpitiya wind corridor as the Envision Final EIA (Sep-2025) reference project, which is used here only as an **ex-post corroboration**, never as a driver.

---

## 2. Wind resource & siting assessment

This section is built from a **fresh ERA5 retrieval run this session** (single-point ARCO timeseries, reproducible fixed 2005–2024 window) plus the committed bankable-AEP loss chain that feeds the finance model.

### 2.1 Fresh long-term resource (ERA5 ARCO, 2005–2024, 175,320 h, 100 % coverage)

| Reference period | Mean hub WS (150 m) | Net AEP P50 | Capacity factor |
|---|---|---|---|
| 2020–2024 (recent 5-yr) | 7.294 m/s | **523.0 GWh** | 0.3742 |
| 2015–2024 (current decade) | 7.317 m/s | 527.5 GWh | 0.3773 |
| 2005–2024 (long-term 20-yr) | 7.460 m/s | 551.2 GWh | 0.3943 |
| P90 (20-yr basis) | — | **480.0 GWh** | — |

Interannual coefficient of variation: **2.69 %** (low — a stable resource). Coverage complete (175,320 / 175,320 hours). Single-cell retrieval → spatial representativeness recorded as **not assessed** (honest caveat; a neighbourhood GIS sample is the next step for micro-siting representativeness).

### 2.2 ⭐ Material finding — a statistically significant secular-stilling trend

The 20-year series carries a **downward wind-speed trend that is significant at the 5 % level**:

- **Mann-Kendall** τ = −0.453, **p = 0.0047** (significant)
- **Sen's slope** = −0.219 m/s per decade (95 % CI −0.335 … −0.087)
- **OLS** slope −0.210 m/s/decade, R² = 0.365
- Decade means: 2000s **7.575** → 2010s **7.485** → 2020s **7.294** m/s
- Classification: **secular trend / stilling** — a sustained decline with material explained variance.

**Bankability consequence:** a forward P50 should be weighted toward the **current-climate period**, not the full 20-yr mean. The assessment therefore recommends the **recent-5-yr basis: P50 523.0 GWh (CF 37.4 %)** as the central bankable figure, with the 20-yr 551.2 GWh as the upside. This is the honest, IEC-61400-15-1 / MEASNET-consistent treatment (long-term reference, regime-shift-adjusted).

### 2.3 Committed bankable AEP used by the finance model

The finance run uses a **more conservative, fully-loss-adjusted** bankable AEP (from the committed `bankable_aep` chain), not the raw ARCO figure:

- ERA5-fitted Weibull **A = 8.199, k = 2.665**, mean **7.29 m/s** (this equals the fresh recent-5-yr mean of 7.294 — direct corroboration), air density 1.15 kg/m³.
- Loss stack **14.48 %**: PyWake Bastankhah-Porté-Agel wake **7.28 %** (15-turbine layout; TurbOPark bound 8.93 %), availability 97 %, electrical 2 %, curtailment 2 %, other/environmental 1 %.
- IEC 61400-15-2 pre-construction **over-prediction haircut 2.0 %** (a conservative policy choice, not derived from this project's own EYA).
- **→ Net P50 464.3 GWh, CF 0.332; P90 404.4 GWh.**
- Ex-post cross-check: the Envision EN220/10.0 Final EIA reports **P50 464.5 GWh** — within **~0.04 %** of the model output (corroboration only).

**Reconciliation (fresh vs committed):** the fresh ARCO recent-5-yr figure (523.0 GWh, CF 0.374) is a resource-level net; the committed 464.3 GWh (CF 0.332) additionally carries the full IEC loss stack + the 2 % over-prediction haircut — i.e. the finance model runs **~11 % below** the raw resource, deliberately. The two are consistent (same 7.29 m/s wind climate); the model uses the conservative number.

### 2.4 Turbine & layout

IEA Wind Task 37 **10 MW reference** (198 m rotor, 345 W/m², low-specific-power for the 7.3 m/s site), hub 150 m, cut-in 3 / rated 11 / cut-out 25 m/s. Open reference curve (not OEM-certified) — a stand-in for a future low-wind 10 MW OEM machine. Layout: 15 turbines, linear north-south coastal, avg spacing 650 m (3.8 D); IEC spacing compliance is marginal (6 compliant / 3 marginal / 6 violating pairs) — a micro-siting optimisation item, and the reason wake is modelled granularly rather than assumed flat.

### 2.5 Wind rose (fresh ARCO directional distribution, 12 × 30° sectors)

| Sector | 0° N | 30° | 60° | 90° E | 120° | 150° | 180° S | 210° | 240° | 270° W | 300° | 330° |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Frequency | 4.3 % | 13.1 % | 13.2 % | 3.8 % | 1.1 % | 1.4 % | 4.4 % | **31.8 %** | **22.7 %** | 1.5 % | 1.0 % | 1.6 % |

**Prevailing sector 210° (SW).** The climate is **bimodal monsoon**: a dominant **SW band (210–240°) at ~54.5 %** (the SW monsoon) plus a secondary **NE band (30–60°) at ~26.3 %** (the NE monsoon return). Provenance: single-cell ERA5 (~0.25°), indicative of the prevailing sector, not mast-validated on-site — a met-mast directional campaign is a bankability item. This directional structure is what makes the committed **linear north-south layout efficient** — the turbine string sits broadside to the dominant SW flow, minimising in-line wake.

### 2.6 Micro-siting (TopFarm on PyWake — fresh candidate this run)

A boundary-, spacing- and exclusion-constrained AEP maximisation (DTU TopFarm on the PyWake Bastankhah-Porté-Agel model), seeded with the committed 15-turbine layout and driven by the fresh ARCO wind rose:

| | AEP (wake-included) | Note |
|---|---|---|
| Committed baseline (linear N-S, 650 m) | **551.0 GWh** | scored on the PyWake model at the ARCO Weibull |
| Optimised candidate | **558.5 GWh** | 3.0-D min spacing respected (594 m) |
| **Uplift** | **+7.47 GWh (+1.36 %)** | KPI-neutral candidate — informs layout, not the finance case |

**Read:** the committed layout is already well-matched to the SW-dominant rose; a re-sited candidate captures a **modest ~1.4 %** additional energy by further trimming wake. This is a candidate for the micro-siting workstream, not a change to the headline economics (which use the committed 464.3 GWh bankable AEP).

### 2.7 GeoGIS spatial screen (fresh GeoTIFF export)

A native-resolution ERA5 GIS export (3 × 3 cells at 0.25°, bilinear-downscaled to 0.05°) rendered WS150 / capacity-factor / AEP-per-turbine GeoTIFFs and a spatial-representativeness verdict over the ~80 km neighbourhood:

| Metric | Value | Tolerance |
|---|---|---|
| Site-cell mean WS150 | 7.294 m/s | — |
| Neighbourhood (9-cell) mean WS150 | 7.344 m/s | — |
| Site-cell deviation from neighbourhood | **−0.69 %** | ±8 % ✓ |
| Neighbourhood spatial spread | **28.3 %** | 15 % ✗ |
| **Representative verdict** | **False** | — |

**Read:** the site cell sits essentially *at* the local mean (−0.7 %, comfortably within tolerance), so the reanalysis is a sound central estimate — but the wider ~80 km neighbourhood is spatially **heterogeneous** (28 % spread, a coastal/inland resource gradient), which trips the representativeness flag. The honest conclusion: the P50 level is defensible, but the regional variability argues for an **on-site met-mast campaign** before financial close, not reliance on single-cell reanalysis. Artifacts: `artifacts/gis/` (ws150/CF/AEP GeoTIFFs, coarse + fine, each with a provenance sidecar) + DataLake manifest.

---

## 3. Technical basis

| Item | Value |
|---|---|
| Rated capacity | 159.6 MW (15 × 10.638 MW) |
| Rotor / hub | 198 m / 150 m |
| Power curve | IEA Reference 10 MW (IEC 61400-12-1:2022, open reference) |
| Air density correction | site 1.15 vs ref 1.225 kg/m³ |
| Degradation | 0.5 %/yr (industry-standard onshore aging) |
| Wake model | PyWake Bastankhah-Porté-Agel (granular, 7.28 %) |

---

## 4. Capex & opex

### 4.1 Capex — bottom-up WBS ($159.6 M base = $1,000/kW, AACE Class 3)

| WBS line | USD | Share |
|---|---|---|
| Turbines (WTG supply, CIF + inland) | 110,124,000 | 69.0 % |
| Foundations | 7,660,800 | 4.8 % |
| Grid connection (220 kV line) | 7,660,800 | 4.8 % |
| Turbine erection | 5,107,200 | 3.2 % |
| Array collection (33 kV) | 5,107,200 | 3.2 % |
| Substation bay | 5,107,200 | 3.2 % |
| Development / owner's / land | 5,586,000 | 3.5 % |
| Site preparation | 3,064,320 | 1.9 % |
| Financing fees | 3,192,000 | 2.0 % |
| Contingency (~1.5 %) | 2,394,000 | 1.5 % |
| Project management | 2,553,600 | 1.6 % |
| Site development | 2,042,880 | 1.3 % |
| **Base capex total** | **159,600,000** | **100 %** |

$/kW benchmark: $1,000/kW sits between the SINOHYDRO Mannar EPC quote (~$889/kW) and the Envision Dutch Bay EIA (~$1,420/kW), and near the IRENA-2024 global onshore benchmark ($1,041/kW).

**Import-levy uplift (prudent posture, #738):** PAL 5 % + import-SSCL 2.5 % **paid** on the 0.69 imported share = **+$8.2593 M** duties (customs import duty on wind gensets is FREE, HS 8502.31). Capex VAT is relieved via the BOI §17 / bonded route. **→ Gross financed capex $167.86 M ($1,051.75/kW).** Duties capitalise into the depreciable base and flow to IDC, gearing and NPV.

### 4.2 Opex ($3.0 M/yr = $20/kW-yr)

O&M contract $2.0 M · insurance $0.5 M · land lease $0.3 M · admin/SPV $0.2 M. Unrecoverable 18 % input VAT on O&M is paid (IPP supply is VAT-exempt → no input credit). Opex held flat-nominal (no USD escalation applied; LKR cost erosion enters via the FX curve).

---

## 5. Financing structure

| Parameter | Value |
|---|---|
| Debt sizing | **dual-DSCR** auto-sculpt to a 1.30 target, capped at 70 % gearing |
| Realised gearing | **0.41** (auto-solved down to hold the covenant) |
| Max senior debt | $68.82 M |
| Tenor / grace | 15 yr / 2-yr interest-only |
| Tranche mix | LKR-local 45 % · USD-DFI 10 % · USD-commercial 45 % |
| Tranche rates | LKR **13.39 %** (UIP-implied: USD 7.5 % + 5.89 % drift) · DFI 6.5 % · USD-comm 7.5 % (blended kd ~7.63 %) |
| Credit-support fees | DFI guarantee 75 bps + PRI 100 bps per yr on outstanding senior debt (sized **inside** the sculpt) |
| DSRA | 6 months |
| Balloon | ~48.9 % at maturity, **cash-sweep** resolution (breaches the modelled 10 % refinance-risk covenant — a structuring flag) |
| IDC | $10.75 M |

The LKR tranche at the **UIP-implied 13.39 %** (not a concessional 8 %) is the honest market-rate assumption pending a real term sheet; it is the single biggest lever pushing the equity return negative. The ~49 % balloon under a cash-sweep is a genuine structuring weakness to resolve before close.

### 5.1 Capital-structure optimisation — financing cannot rescue the tariff

A capital-structure optimiser swept **36 debt-mix / gearing candidates** to maximise equity IRR. **All 36 are negative.** The best (DFI 40 % / USD-commercial 60 % / no LKR) lifts equity IRR from the committed **−5.84 % to −3.71 %** (min-DSCR 1.30, LLCR 1.16); the worst (LKR-heavy) is −6.30 %. So the *optimal* financing structure gains only ~2 pp and **still cannot make equity positive** — a quantitative proof, from the finance side, that the binding constraint is the flat-LKR tariff, not the capital structure. It corroborates the Sobol result (§7.5): the tariff, not the debt mix, is what moves the return.

---

## 6. Returns

### 6.1 Headline KPIs (live canonical run — reproduces the 5th-gen canon byte-identically)

| KPI | Value |
|---|---|
| Project IRR (unlevered, real) | **0.014551597740253388** (1.46 %) |
| Equity IRR (levered) | **−0.05841298678542661** (−5.84 %) |
| Project NPV @ WACC | **−$79,273,039** |
| Equity NPV @ ke | −$81,592,659 |
| Min DSCR (covenant fold / per-period) | **1.285740985294611** / 1.30 |
| Avg / max DSCR | 1.39 / 2.57 |
| LLCR / PLCR | 1.268 / 1.307 |
| Equity MOIC | 0.523 (< 1 — sponsors do not recover their outlay) |
| WACC (build-up) / project discount | ~9.94 % / 10.02 % |
| Total CFADS (20-yr) | $191.1 M |
| Total equity distributed | $51.78 M |

### 6.2 The equity bridge (why leverage makes it worse, not better)

Unlevered project IRR 1.46 % → levered equity IRR −5.84 %. Because the **asset return (1.46 %) is far below the blended cost of debt (~7.6 %)**, leverage is **dilutive**, not accretive: every borrowed dollar earns less than it costs, and the FX-inflating USD/blended debt service on flat-LKR revenue amplifies the loss. Add the SL 15 % dividend WHT, the UIP LKR rate, credit-support fees and import levies, and the equity return sinks below −5 %. The re-baseline chain (documented in Appendix A) shows each step.

---

## 7. Sensitivity & risk

### 7.1 Scenario suite (8 live runs) — no scenario clears a positive NPV

| Scenario | Project IRR | Equity IRR | Min DSCR | Project NPV | LLCR |
|---|---|---|---|---|---|
| Optimistic | 9.25 % | **+6.98 %** | 1.30 | −$6.76 M | 1.36 |
| Base case | 5.88 % | +3.01 % | 0.78 | −$37.79 M | 1.07 |
| Equity case | 5.88 % | +2.88 % | 1.40 | −$37.79 M | 1.87 |
| Pessimistic | 3.89 % | −4.95 % | 0.51 | −$57.11 M | 0.92 |
| Capex lean (SINOHYDRO) | 2.92 % | −4.40 % | 1.30 | −$61.74 M | 1.29 |
| **Lender (canonical)** | **1.46 %** | **−5.84 %** | **1.29** | **−$79.27 M** | **1.27** |
| Hybrid wind+solar | 1.86 % | −2.85 % | 1.30 | −$92.67 M | 1.49 |
| Capex prudent (EIA) | −0.59 % | −8.09 % | 1.30 | −$131.90 M | 1.36 |
| Solar-only | −3.44 % | −7.65 % | 1.57 | −$105.54 M | 1.57 |

**Every scenario has a negative project NPV.** The best case (optimistic) reaches +6.98 % equity IRR but still a −$6.76 M NPV — i.e. even the upside does not clear the 12 % equity hurdle. The result is robust to the technology and cost frame; the binding constraint is the tariff, not the capex.

### 7.2 Monte-Carlo distribution (live run)

An LHS Monte Carlo over six correlated drivers (capacity factor, tariff, opex, capex, FX, incremental curtailment; **Iman-Conover** rank correlation — capex↔opex +0.35, CF↔curtailment +0.20, FX left uncorrelated because the flat-LKR PPA breaks the revenue-FX link). Run at **2,500 trials** (100 % success), cross-validated against a full **100,000-trial** run — the two agree to ~0.1 pp, so the distribution is converged:

| Metric | P10 | P50 | P90 | Mean |
|---|---|---|---|---|
| Equity IRR | −11.3 % | **−7.3 %** | −2.8 % | −7.1 % |
| Project IRR | −2.0 % | +0.6 % | +3.4 % | +0.6 % |
| Project NPV | −$114.3 M | **−$85.9 M** | −$56.3 M | −$85.7 M |
| Min DSCR | 1.247 | 1.278 | 1.300 | 1.276 |
| LLCR | 1.259 | 1.271 | 1.286 | 1.272 |

**The negative-equity verdict is robust, not a point estimate:** equity IRR is **negative across the entire distribution through ~P90** (whole-sample max only +6.7 %), and **project NPV is negative in 100 % of trials**. Meanwhile **min-DSCR stays ≥ 1.21 throughout** — the *debt* is safe across the distribution; it is the *equity* that is underwater. (VaR/CVaR + covenant-breach detail in `artifacts/capital_risk_report.html`; NPV-distribution chart below.)

### 7.3 Downside production

P90 (1-yr) net AEP **404.4 GWh** vs P50 464.3 GWh (P90/P50 ≈ 0.871). The dual-DSCR sizer binds on the P50; the P99 downside factor (0.80 of P50 ≈ P90 territory) is what constrains debt capacity.

### 7.4 AEP sensitivity (fresh tornado)

A fresh AEP tornado on the committed resource basis (net-modelled base **473.84 GWh**, before the 2 % haircut → 464.3 bankable):

| Driver | Swing | AEP range (GWh) |
|---|---|---|
| **Wind-speed bias ±5 %** | **±20.5 %** | 424.6 – 521.5 |
| Power curve (IEA vs DTU 10 MW) | −16.0 % | 398.3 |
| Shear exponent ±0.04 | ±6.6 % | 458.1 – 489.6 |
| Losses ±20 % | ±6.4 % | 458.8 – 489.2 |

**Wind-speed uncertainty dominates — roughly 3× the next driver.** Combined with the significant secular-stilling trend (§2.2), this is exactly why the pre-construction P50 haircut and the P90 debt-sizing are the load-bearing conservatism in the model, and why an on-site measurement campaign (§2.7) is the highest-value pre-close derisking step.

### 7.5 Global sensitivity (Sobol / PAWN / Morris)

A variance-based global sensitivity analysis (SALib), over the same six drivers, for **equity IRR**:

| Driver | Sobol total-order (ST) |
|---|---|
| **Tariff (LKR/kWh)** | **0.47** |
| Capex | 0.19 |
| FX (LKR/USD) | 0.12 |
| Capacity factor | 0.12 |
| Curtailment | 0.06 |
| Opex | 0.04 |

**The flat-LKR tariff is quantitatively the #1 equity-IRR driver (ST 0.47 — larger than the next two combined).** This is the finance-side counterpart to the AEP tornado (§7.4, where wind-speed dominates *energy*): once the energy is financed, the *administered tariff* dominates the *return*. It is the analytical confirmation of the whole thesis — the binding lever is the revenue line, and it is fixed. (Morris μ\* ranks capex first on a one-at-a-time basis; Sobol total-order, which captures interactions, puts tariff first.)

---

## 8. Grid & interconnection (advisory screen — fired end-to-end)

The in-house grid-strength screen (`analytics.grid` #870 stack; **pandapower 3.3.0 / andes 2.0.0 / opendssdirect 0.9.4** all resolved) was **run this pass** with `grid.study_enabled=true`, and is **KPI-neutral** — the finance KPIs are byte-identical to canon with it on. Results:

- **SCR@POC ≈ 0.94 ("weak")** by pandapower IEC-60909 (fault level 150.1 MVA at the 33 kV POC vs 159.6 MVA plant) → **GFL at risk; grid-forming (GFM) likely required** (consistent with the NSO round mandating GFM). ⚠️ **Screening estimate, `bankable:false`** — the 150 MVA is driven by a *placeholder* 6 Ω connection reactance, not a CEB/NSCC-issued fault level. A bankable connection study (PSS®E / PowerFactory vs the utility base case) is a condition precedent.
- **RMS ride-through screen** ran all three cases (LVRT / HVRT / frequency); verdicts are the honest `None` because the ANDES dynamic solve is opt-in (the default is RMS-envelope only). The IEEE-519 harmonic screen ran. (The `poc_envelope` / `freq_response` sub-screens report not-applicable for a single-tech wind scenario — expected, not a failure.)
- **Provenance / verification discipline:** running the full stack surfaced — and this session fixed — **two real grid/GIS bugs**: a rasterio `boundary_clip` segfault under GDAL 3.10.3 (fixed, merged **#929**) and a `ride_through` kwarg `TypeError` that had silently degraded the screen on every run (fixed, PR **#930**). Both are exactly the defects a "run every module" pass is meant to catch.

---

## 9. The honest economics

- **Why equity IRR is negative:** a flat-nominal-LKR tariff with no escalation and no FX index, against a cost base that is ~69 % USD-denominated (turbines) and debt that is ~55 % USD/blended, financed while the LKR depreciates ~5.9 %/yr. Revenue is fixed in a currency that loses ~6 %/yr of USD value; costs and debt service are not. The scissors close on the equity.
- **The "cheap USD debt" illusion:** the USD-DFI 6.5 % / USD-commercial 7.5 % tranches *look* cheaper than the 13.39 % LKR tranche, but on flat-LKR revenue their effective LKR cost rises with depreciation — which is exactly why the UIP-implied LKR rate (13.39 %) is the correct comparator and why leverage is dilutive here.
- **The counter-case:** the project's Final EIA reports an **18.07 % economic IRR (EIRR)**. That is not a contradiction — it is a *different frame*: EIRR counts economy-wide benefits (avoided fossil generation, capacity value) under a concessional/blended capital stack, whereas this study's financial eqIRR is the sponsor's after-tax cash return at the administered flat-LKR tariff. **The project is economically attractive to Sri Lanka and financially value-destructive to a merchant sponsor** — the classic case for blended finance / concessional capital or a restructured tariff.
- **Merchant-tail caveat:** there is no merchant upside to rescue the tail — the PPA is flat for 20 years, so the downside (FX, curtailment, resource stilling) is one-sided.

---

## 10. ESG / EIA context & development readiness

**Environmental & social:** Final EIA approved (Envision, Sep-2025); E&S management plan in place → **GREEN**. Marine/coastal setting (Dutch Bay); IFC-PS / EP4-aligned. No standalone EP4 Climate Change Risk Assessment yet commissioned (honest gap; the resource-stilling finding in §2.2 is a physical-climate risk that a CCRA should formalise).

**Development-readiness register (roll-up: RED):**

| Workstream | Status | Note |
|---|---|---|
| Environmental & social | 🟢 Green | Final EIA approved |
| Land | 🟡 Amber | Site identified; lease in progress |
| Permits | 🟡 Amber | Generation licence + approvals under application |
| Grid connection | 🟡 Amber | 220 kV line separate CEB-funded project |
| PPA | 🟡 Amber | CEB standardized template; tariff not executed |
| EPC | 🟡 Amber | SINOHYDRO bottom-up quote; contract not awarded |
| **Financing** | 🔴 **Red** | equity IRR negative at flat-LKR tariff; debt+equity uncommitted |

---

## 11. Recommendation with conditions precedent

**Conditional NO-GO at the current flat-LKR 20.3 LKR/kWh tariff.** The project is value-destructive on a merchant/standalone basis in every scenario run. Do not reach financial close as structured.

**Path to a conditional GO** — pursue at least one, ideally a combination, of:

1. **Revenue restructuring (highest impact):** tariff FX-indexation or CPI escalation, or a USD-denominated / USD-linked PPA. This attacks the root cause (flat-LKR vs USD costs).
2. **Concessional / blended capital:** a materially concessional senior or first-loss/grant tranche that lowers the blended cost of debt below the asset return — the frame under which the EIA's 18.07 % EIRR is bankable.
3. **Debt-structure fixes:** resolve the ~49 % balloon (longer tenor, amortising structure, or committed refinance) and secure a real LKR term sheet (the 13.39 % UIP rate is an assumption, not a quote).
4. **Grid & resource DD:** a bankable PSS®E/PowerFactory grid-connection study (replacing the screening estimate) and a met-mast-validated resource campaign that formalises the secular-stilling haircut.
5. **Commercial DD:** execute the PPA (tariff currently `assumption`-tier), award the EPC, and close the land/permit items.

Until at least the revenue or the capital stack is restructured, the honest position is that DutchBay is an **economically valuable, financially unbankable** project — a candidate for concessional/blended finance, not commercial project finance.

---

## Appendix A — Assumptions & evidence register (provenance tiers)

| Assumption | Value | Source | Tier |
|---|---|---|---|
| Tariff | 20.3 LKR/kWh flat | CEB standardized PPA (not executed) | **assumption** |
| Debt terms | 15-yr, blended kd ~7.63 %, DSCR-sculpted | indicative (no term sheet) | **assumption** |
| Capex | $1,000/kW bottom-up WBS | NREL SAM/LandBOSSE; IRENA-2024 anchor; AACE Class 3 | benchmark |
| Opex | $20/kW-yr | IRENA RPGC 2024 / NREL ATB 2024-25 | benchmark |
| Capacity factor | 0.332 net P50 | ERA5→PyWake→power-curve→AEP, −2 % haircut | derived |
| FX | 333.79 LKR/USD, 5.89 % depr | CBSL anchor / FRED / BIS; 2026-Q2 pinned | measured |
| Tax | CIT 30 %, div WHT 15 %, no holiday | SL IRA, IMF-reformed 2024-26 | benchmark |
| Degradation | 0.5 %/yr | industry-standard onshore | benchmark |
| Discount rate | ~9.9 % build-up WACC | modelled capital structure | derived |
| Climate risk | analyst screen | no formal EP4 CCRA yet | assumption |

**Re-baseline chain to the current canon (honest audit trail):** FX 300→333.79 · ERA5-fitted Weibull (AEP 483.6→473.8) · project-discount construction-lag fix · degradation 0→0.5 %/yr · FX-drift 3 %→5.89 % · 2 % AEP over-prediction haircut (473.8→464.3) · non-statutory levy removal · SL dividend WHT + IDC capitalisation · UIP LKR debt rate 8 %→13.39 % · credit-support fees (guarantee 75 bps + PRI 100 bps) · import levies + indirect tax (SSCL-on-revenue reversed; PAL+import-SSCL paid). Net: projIRR → 1.46 %, eqIRR → −5.84 %, NPV → −$79.3 M, gearing → 0.41.

## Appendix B — Full scenario KPI table

See §7.1 (8 live scenarios). Source: `_out/feas924/suite/<scenario>/…/kpis.json`, all engine `v15.3.0` / SHA `a50b0bfce8e8`.

## Appendix C — Monte-Carlo method

100k-trial LHS (seed 42); drivers {capacity_factor, tariff, opex, capex, fx, curtailment} with uniform supports base·(1 ± 2·rel_std); Iman-Conover correlation (capex↔opex +0.35, CF↔curtailment +0.20). VaR/CVaR at 95 %; covenant floors DSCR 1.20 / LLCR 1.25. Lender-grade capital-risk report rendered at 2000 bounded trials (≥ the 1000-trial floor). Artifacts: `capital_risk_report.html`, `npv_distribution_equity_npv.png`.

## Appendix D — Reproduce recipe & provenance

```
Repo:    ~/Downloads/dutchbay-epc-model  @ origin/main a50b0bfce8e88f4927ffee0a697cd1c9a76d32e1
Engine:  v15.3.0   Python 3.11 (.venv)
Canon:   .venv/bin/python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
         → project_irr 0.014551597740253388 · equity_irr -0.05841298678542661 · min_dscr 1.285740985294611  (byte-identical to the 5th-gen canon)
Wind:    ERA5_REQUEST_CONFIG=artifacts/era5_request_dutchbay.yaml .venv/bin/python -m wind_resource.era5_retrieval
         → ARCO single-point 2005-2024, P50 523.0 (recent-5yr) / 551.2 (20-yr) GWh; wind_rose (prevailing 210° SW); secular-stilling MK p=0.0047
Tornado: analytics.wind.aep_tornado.tornado_from_config(lender)         → wind-speed ±20.5% dominant driver
Micrsit: wind_resource.layout_optimizer.optimize_layout (TopFarm/PyWake) → +1.36% AEP uplift candidate (baseline 551.0 → 558.5 GWh)
GIS:     GIS_EXPORT_CONFIG=wind_resource/config/gis_export_dutchbay.yaml -m analytics.gis.gis_export
         → WS150/CF/AEP GeoTIFFs (coarse 0.25° + fine 0.05°) + spatial-representativeness (False; 28.3% neighbourhood spread)
Suite:   run_full_pipeline_v14.py config=scenarios/dutchbay_{basecase,equitycase,optimistic,pessimistic,capex_*,hybrid_windsolar,solar_only}_2025Q4.yaml
Emitters: +emit_capital_risk_report / +emit_tech_comparison / +emit_interaction_grid / emit_executive_workbook  (all four fired)
FreshAEP: analytics.wind.aep_summary_builder.build_aep_summary_from_config(lender) → net P50 464.36 GWh / CF 0.3322  (= committed 464.3 → BASELINE reproduced the long way)
MC:      analytics.mc.engine.run_monte_carlo_analysis(lender, n_trials=2500, seed=42)  [+ a full 100k cross-check]
         → equity_irr P10/P50/P90 -11.3/-7.3/-2.8%; project_npv negative in 100% of trials; min_dscr ≥1.21 (2500 ≈ 100k, converged)
Sobol:   analytics/cli/cli_sensitivity_hydra.py (SALib Sobol+PAWN+Morris) → equity-IRR ST: tariff 0.47 (dominant) > capex 0.19 > fx 0.12
Optimiz: analytics/cli/cli_capital_structure_optimize_hydra.py → 36 debt-mix candidates, ALL negative; best -3.71% (DFI40/USD60)
Grid:    run_full_pipeline_v14.py config=<lender with grid.study_enabled:true> +emit_grid_screen=true
         → SCR@POC 0.94 (weak, pandapower IEC-60909); ride-through 3 cases (advisory); KPI byte-identical (neutral)
```

> **Full-stack note.** The finance engine drives production off `project.capacity_factor` and reads a *committed* `resource.aep_summary_path`; it does NOT re-run the wind stack. This study fired the wind/GIS/micro-siting stack **separately** and confirmed it reproduces the committed AEP (464.36 vs 464.3 GWh) — so the baseline holds computed the long way. Two data/terrain GIS layers remain **honestly blocked** (need external Global-Wind-Atlas / Copernicus-DEM / ESA-WorldCover rasters, absent locally); they are flagged, not fabricated.

**Verification discipline:** the canonical lender run reproduced the 5th-generation canon **byte-identically** (project_irr / equity_irr / min_dscr to 1e-9); the grid screen is advisory and KPI-neutral (byte-identical whether on or off); every figure in this study traces to a live artifact in `artifacts/`. Where an input is `assumption`-tier (tariff, debt terms), it is labelled as such — this is a development-stage feasibility, not a financed model.

---
*Prepared on the live DutchBay EPC model, 2026-07-07. Honest-economics basis: the project is technically viable and economically valuable to Sri Lanka, but financially value-destructive to a merchant sponsor at the committed flat-LKR tariff. Bankability requires a restructured revenue or concessional capital stack.*
