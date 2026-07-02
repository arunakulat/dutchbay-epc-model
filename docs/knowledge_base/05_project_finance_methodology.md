# Renewable Project-Finance Methodology (DFI / Lender Lens)

This document sets out the project-finance methodology used to underwrite and stress the Dutch Bay portfolio and comparable Sri Lankan wind/BESS assets. The lens is that of a development-finance-institution (DFI) credit and investment analyst — IFC / ADB / World Bank practice — disciplined by Benjamin Graham value principles and by quantitative model-risk rigor. It documents *method and public regime facts*: how debt is sized and covered, how renewable-resource uncertainty and currency mismatch are handled, the Sri Lankan corporate-tax regime relevant to a renewable IPP, and how grid curtailment and multi-technology portfolios are modelled.

The financial engine that implements this methodology, and its scenario results, are published elsewhere in this repository. Where a number is cited below it is a *model result* for a disclosed scenario, not a commercial commitment. For the cost basis that feeds capex into these calculations see `01_wind_epc_costs_and_scaling.md`; for the resource and energy-yield methodology see `02_wind_resource_and_aep.md`; for the offtake and tariff framework see `03_offtake_ppa_and_grid.md`.

External, publicly-verifiable benchmark and regime claims in this document were re-validated against primary sources on 2026-06-25; see **External validation & sources** near the end for the source list and any corrections.

---

## 1. Debt Sizing and the Covenant Package

### 1.1 CFADS — the single foundation

Everything downstream is built on **Cash Flow Available for Debt Service (CFADS)**:

```
CFADS = revenue − operating expenditure − tax − maintenance capex   (before financing)
```

CFADS is defined once, per period, and every coverage ratio, sculpt and reserve is derived from it. Treating CFADS as the single upstream quantity — rather than recomputing cash from several places — is what keeps a model internally consistent and auditable. This CFADS-first construction, with debt sized backwards from the forecast CFADS stream, is standard lender practice (Yescombe, *Principles of Project Finance*).

### 1.2 Debt sizing — the more restrictive of two constraints

Debt capacity at financial close is the **minimum** of:

- **Gearing cap** — debt ≤ X% of project cost (typically 70–80% for contracted renewables; lender term sheets commonly express a maximum gearing such as 75% debt / 25% equity).
- **DSCR-sized debt** — the maximum debt such that `CFADS / DebtService ≥ target DSCR` in every period. This is solved *backwards* from the forecast CFADS stream.

The binding constraint flips between projects. A strong-resource, fully-contracted asset is usually gearing-bound; a weaker or FX-stressed asset becomes DSCR-bound at a lower gearing. In the disclosed Dutch Bay base case the FX correction (Section 3) pushed the asset from gearing-bound (~0.70) to DSCR-bound (~0.63) — a direct illustration that gearing is a *cap*, not an *entitlement*.

### 1.3 Sculpting — match principal to cash

A **sculpted** repayment profile shapes each period's principal so the DSCR sits at (or near) target throughout the loan life, rather than paying a flat annuity that wastes coverage in the cash-rich early years. The core equations:

```
Target Debt Service[t] = CFADS[t] / target DSCR
Debt at COD            = NPV(interest rate, Target Debt Service stream)
```

Sculpting **maximises debt capacity** versus a level/annuity profile. A grace or interest-only period (commonly 1–2 years) defers principal while generation and CFADS ramp. A **dual-DSCR** discipline is standard: a *target* DSCR drives the sculpt, and a *minimum* DSCR sets the covenant floor; the sculpt holds the per-period DSCR flat at target, so the covenant-relevant volatility shows up not in the (flat) min-DSCR but in the **balloon** — a squeezed CFADS amortises less and leaves a larger bullet at maturity.

### 1.4 Coverage ratios — the covenant suite

| Ratio | Definition | Horizon | Role |
|---|---|---|---|
| **DSCR** | period CFADS ÷ period debt service | point-in-time | Target ≈ 1.30× for contracted infra; min ≈ 1.20×. Industry benchmarks put contracted-solar P50 DSCR at ~1.20–1.30× and contracted-wind at ~1.30–1.40×, with merchant/higher-risk projects materially higher (~1.75–2.00×). Vintage anchor: the NREL ATB 2024 financial cases assume P50 DSCR ~1.25× (contracted solar) / ~1.3–1.4× (contracted wind) at a ~2.5% real interest rate. |
| **LLCR** | PV(CFADS over loan life, net of DSRA) ÷ debt outstanding | forward, loan term | Repayment capacity over the loan; triggers cash sweeps. Typical min ≈ 1.10–1.15×. |
| **PLCR** | as LLCR but over *project* life | forward, project term | Always ≥ LLCR; measures the tail-value cushion. |

A subtlety routinely mis-modelled: in the LLCR the **DSRA balance is deducted from the debt in the denominator** (`LLCR = PV(CFADS)/(Debt − DSRA)`), it is *not* added to the CFADS numerator. The forward-looking (prospective) DSRA requires its own second loop, starting one period forward — a step frequently omitted.

### 1.5 DSRA and the lender protections that make a model a *credit*

- **DSRA (Debt Service Reserve Account):** a cash buffer, commonly the **next six months** of debt service, funded at close and topped up from the waterfall. It steps *down* as the debt amortises and the residual is released to equity at maturity (a release that, if omitted, materially understates the equity return).
- **Distribution lock-up:** no equity distributions when DSCR or LLCR falls below a lock-up threshold (commonly set at or just above the minimum-DSCR covenant, e.g. ~1.20×); the trapped cash is *carried forward and released when the covenant cures*, not destroyed.
- **Cash sweep:** excess cash prepays senior debt as DSCR approaches a mid threshold (~1.10–1.15×). At a 100% sweep, principal rises until debt service equals CFADS, i.e. DSCR → 1.00×.
- **Events of default** below the floor.

These convert a spreadsheet of cash flows into a *credit*: they define what the lender will tolerate, and when control shifts.

### 1.6 The circular reference is real

Debt size drives interest-during-construction (IDC), which is part of project cost, which drives debt size; arrangement fees (a % of debt) and the DSRA (sized on debt service) sit inside the construction funding and feed back; and tax depends on interest, which depends on loan size. This is a genuine multi-layer fixed-point problem and must be solved **iteratively to convergence** (change debt → recompute IDC/fees/DSRA/tax → repeat), not papered over with a live circular reference. Stacking the LLCR-target constraint on top can make a naive solver unstable; convergence via a controlled iteration is the disciplined route.

### 1.7 Bankability — P50 / P75 / P90 and sizing off the downside

Energy-yield uncertainty is expressed as **exceedance (P-) values** — the probability that actual AEP is exceeded — and is the framework codified in IEC 61400-15-2 for pre-construction energy-yield assessment (which outputs a P50 median and a σ_AEP from which all Pxx levels are derived):

- **P50** — median; the equity base case.
- **P75** — a common European-lender compromise.
- **P90** — exceeded nine years in ten; the conventional **debt-sizing** standard.
- **P99** — deep downside / covenant stress.

The **P50→P90 spread** (≈1.10–1.20× depending on climate variability and total assessment uncertainty) is the bankability headroom: lenders size on the conservative case, equity is rewarded on the gap. The general rule is *size debt off the downside resource, run equity off P50* — but see Section 2.1 for how this rule must be refined.

---

## 2. Contrarian Refinements — "Golden Nuggets" That Revise the Playbook

These are non-obvious, primary-source-grounded refinements. Each is stated as **method**, not as a project number.

### 2.1 The P50-bias mirage

Two facts complicate "just use P50, then P90":

1. **The P50 base case is often biased optimistic.** Operational studies have found systematic over-prediction of energy in the order of a few percent. The defensible habit is to *interrogate the gross-energy-and-losses build*, not to accept the headline P50.
2. **A near-zero *net* P50 bias can be a mirage.** The independent NREL-led multi-consultant benchmark (Todd et al., *Wind Energy*, 2022) found a mean net P50 bias of only **−1.2%** across 10 North American plants and 68 EYA submissions — but with a **4.8% standard deviation**, and that near-zero mean arises *only because consultants over-predict gross turbine energy and then over-predict downstream losses, so the two errors cancel*, while inter-consultant disagreement stays roughly flat through the loss stack (differences worth up to ~$10/MWh in LCOE). A small net bias does **not** mean the estimate is sound; the **choice of yield consultant is itself a material model risk**.

Two further structural points:
- **Uncertainty has a floor that does not decay.** Only interannual variability shrinks with √N; measurement and energy-model errors are systematic and persist. Total P50 uncertainty floors above a few percent regardless of record length.
- **The P50→P90 spread narrows with tenor.** P50 is the only horizon-invariant P-value; every other Pxx drifts toward P50 over a longer term. A **10-year P90 is materially less conservative than a 1-year P90.** The right sizing case therefore depends on *who* bears the risk and *over what horizon*: a lender that bears downside but not upside may legitimately size off a short-horizon, low P-value (e.g. a 1-year P90/P99) rather than a generous 25-year P90.
- **The uncertainty build is gameable.** The correlation assumed between uncertainty categories in the root-sum-square is non-standardised; assuming more correlation reports lower total uncertainty, a tighter P90, and more debt. Interrogate the build, not just the headline.

### 2.2 "Cheap" USD debt is an illusion

A hard-currency coupon that *looks* cheap against a local-currency loan usually is not, once FX is priced. The defensible identity:

```
effective all-in cost of USD debt = USD rate + cost of hedging the FX ≈ local-currency loan rate
```

Feasibility must be tested at the **effective (hedged)** cost, not the headline USD coupon. And FX risk has *no natural private owner* — the developer cannot move the rate and the offtaker's control is limited — so it is, in the literature's words, "largely unmanageable for the private sector." The long-tenor private-to-private hedge market is itself thin (the "missing risk market" problem). FX/country risk lands on equity, on the tariff, on the offtaker, or on a DFI hedge instrument; never assume the lender silently absorbs it. (See Section 3.)

### 2.3 Merchant-tail red flag (the finite-life twist)

For a going concern, a high terminal-value share of NPV is unremarkable. For a **finite-life PPA asset the logic inverts**: the value lives in the *contracted* cash flows, and the post-PPA merchant tail is deeply uncertain and routinely over-credited. Market evidence supports the caution — a large share of corporate PPAs run shorter than the asset life, and investors often recover only a minority of capital within the contracted period. Demand a conservative (or zero) merchant tail; treat tails justified on long OEM warranties as a contested practice; and recognise that lenders cap tail exposure with re-contracting covenants and cash sweeps. The margin of safety must live in the contracted period.

### 2.4 Monte-Carlo, copula and CVaR traps

- **A hand-edited correlation matrix is probably invalid.** A correlation matrix must be symmetric, unit-diagonal and **positive semi-definite**. Manual stress overrides and asynchronous estimates routinely produce non-PSD matrices that silently break Cholesky sampling. Repair with the **nearest-correlation-matrix (Higham)** projection, and check PSD before trusting any simulation.
- **The Gaussian copula understates joint tail risk** — it has **zero asymptotic tail dependence for any ρ < 1** (asymptotic independence), so the "everything goes wrong together" year (low capacity factor + weak FX + curtailment) is under-weighted; this is the well-documented reason the Gaussian copula is regarded as unsuitable for tail-sensitive risk work. Use a **t-copula** (symmetric tail dependence growing as the degrees-of-freedom fall) or a **Clayton copula** (lower-tail dependence) for joint-tail behaviour, and impose a target *rank* correlation on Latin-Hypercube draws via **Iman–Conover** rather than naive Cholesky-on-levels.
- **CVaR ≠ "average of the worst x%" for discrete data.** VaR is not coherent (it ignores the tail beyond the threshold); CVaR/Expected Shortfall is coherent (for both continuous and discrete distributions) and is the right tail metric, but for *discrete* simulation output the naive tail average is not exact — compute CVaR via the **Rockafellar–Uryasev (2000) minimisation formula**, `CVaR_α(X) = min_β { β + (1/(1−α))·E[(X−β)₊] }`, which is convex and (for linear constraints) reduces to an LP.
- **Sobol total-order minus first-order > 0 reveals interactions** (FX × tariff × capacity factor) that a one-way tornado is blind to. Use cheap Morris screening first, then Sobol.
- **Model-risk hygiene:** audits of real-world operational spreadsheets find errors in the great majority of them (Coopers & Lybrand and later studies report defects in ~90% of audited sheets; KPMG-type model reviews find material errors in a large share of financial models), so a formal independent model audit before financial close is standard lender practice. Pin a fixed random seed and a single RNG API, surface NPV at the hurdle alongside IRR (cash flows with multiple sign changes can have multiple or no IRRs — prefer MIRR/XIRR or a bracketed solve), and **execute every load-bearing number rather than hand-tracing it**.

### 2.5 Graham discipline, adapted to cash-yielding infrastructure

The transferable ideas are the **margin of safety** and the **conservative base case**, not the equity screens. In project finance the margin of safety *is* the DSCR cushion above 1.0×, the P90-vs-P50 headroom, the DSRA, and the contingency. Intrinsic value comes from the facts — a 20-year PPA's discounted contracted cash flows — not from sentiment. Prefer the model that survives the downside.

---

## 3. FX and Currency-Mismatch Handling

Currency mismatch — **local-currency revenue against hard-currency debt and hard-currency capex/O&M** — is the structural value driver and the dominant project-killer for an emerging-market IPP. IRENA's cost-of-capital work makes the macro point concrete: WACC assumptions range from ~3.8% in Europe to ~12% in Africa, the cost of capital sits ~200–300 bps above the underlying country risk, and in higher-risk markets financing cost — not capex — dominates LCOE. For a flat-LKR-tariff wind asset, currency is the single most important sensitivity.

### 3.1 LKR-primary numeraire

The asset earns a **flat LKR/kWh tariff with no escalation or FX indexation**. The model is therefore structurally **LKR-primary**: the LKR tariff drives revenue, which drives CFADS and tax; the USD figure is a *post-hoc division* by the spot rate. The numeraire is pinned to LKR by policy and a dedicated guard, because a USD-bid project should carry its native USD tariff (converted at the resolver) rather than pre-baking an assumed FX into an LKR tariff. (A full numeraire flip would touch the debt and tax engines and is deliberately *not* done; the structure is already LKR-primary in substance.)

### 3.2 A fixed-vintage FX reference

FX must be a **single, config-pinned, network-free** reference — not a scatter of hardcoded literals. The disciplined pattern mirrors the resource pipeline:

- **FIXED** (default): a config-pinned vintage, zero network, CI-safe.
- **LATEST**: fetches a live rate, then *freezes a new vintage* (no live dependency at run time).
- **VALIDATE**: reports drift versus live but never mutates the pin.

A lint guard forbids magic FX literals. The cautionary history: the model once carried five divergent hardcoded rates and understated the spot rate by ~11%; correcting it cut the headline equity return materially and moved the asset from gearing-bound to DSCR-bound. **Green tests are not the same as correct numbers — check the pin, not just self-consistency.**

### 3.3 Why the mismatch drives value

The mechanism is sound and is not a double-count: LKR revenue is FX-independent *in LKR*, but its USD-reported value falls as the LKR weakens; capex is USD-fixed; and USD-denominated O&M costs *more LKR* as the LKR depreciates, lowering CFADS. A weaker LKR genuinely hurts both USD returns and debt capacity. The **minimum DSCR in the FX-stressed downside** is the binding constraint — not the average DSCR in the base case — and the LKR-depreciation assumption should be stated explicitly and stress-tested both ways (post-stabilisation the currency may be steadier than a high standing assumption implies).

### 3.4 The de-risking toolkit (method-level)

The emerging-market answer to the mismatch is not a hard-currency-indexed PPA backed by a sovereign guarantee — those *shift* FX risk onto the state's balance sheet rather than resolve it, and are increasingly unsustainable. The forward-looking tools to screen for:

- **Local-currency PPA with partial indexation**, or a *capped* public contribution toward hedging cost (bounding the public liability) rather than a full FX guarantee.
- **Currency-hedge facilities** providing long-tenor (covering a 20–25-year PPA) cross-currency swaps and forwards, subject to per-deal ticket and tenor caps — the thin private hedge market is exactly the gap DFI facilities exist to fill.
- **Political-risk / breach-of-contract cover** (e.g. MIGA's breach-of-contract and Non-Honoring of Sovereign Obligations products, available up to ~20 years and used on PPAs with state offtakers) that explicitly addresses PPA repudiation — denial of recourse and non-payment of an award.
- **A Put-and-Call Option Agreement (PCOA)** as a termination-cover alternative deliberately structured *not* to be a sovereign guarantee — a direct government↔project-company obligation over termination payments recast as a purchase price, which can avoid breaching fiscal commitments and avoid sovereign-liability recognition.

Throughout, **additionality is the gating DFI question, and it is asserted more often than proven**: financial additionality may be shown at the deal level, but the concessional-subsidy element is rarely separately justified or verified ex post, and concessional capital is disproportionately captured by large repeat clients with existing commercial access. Probe *why the concession, and why this sponsor*.

---

## 4. Sri Lankan Corporate-Tax Regime for a Renewable IPP

The post-2022 IMF-EFF reforms removed the incentives a renewable IPP historically relied on. The regime is fast-moving — rates and holidays changed in 2022, 2023, 2024 and 2025 — so **re-verify against the latest amendment act before relying on any figure**. The figures below were re-confirmed against the Sri Lanka Inland Revenue Department (IRD) published tax chart for the **2025/26 year of assessment** on 2026-06-25.

| Item | Current treatment | Note |
|---|---|---|
| **Corporate income tax (CIT)** | **30%** | Up from 24% w.e.f. 1 Oct 2022; the standard rate in the IRD 2025/26 chart (45% special rate applies only to betting/gaming, liquor and tobacco). |
| **Renewable CIT concession** | **Removed** | The old 14% rate for renewable supply to the grid was abolished → 30% from 1 Oct 2022. |
| **≥100 MW solar/wind holiday** | **Removed for new projects** | The 7-year holiday was withdrawn w.e.f. 1 Apr 2023; grandfathered only for undertakings commenced before 31 Mar 2023. |
| **Discretionary holiday (SDP route)** | **≤10 years, discretionary** | Re-opened but curtailed (capped at 10 yr, no extensions, mandatory ex-ante cost-benefit). Not assumable as a base case. |
| **Dividend WHT** | **15% final** | Confirmed in the IRD 2025/26 chart; the relevant lever for distribution-timing optimisation. |
| **Interest WHT** | **10%** | Confirmed in the IRD 2025/26 chart ("interest or discount paid"). Raised from 5% w.e.f. 1 Apr 2025; applies to interest paid to lenders, including non-resident USD/DFI lenders; a double-tax treaty may reduce the ceiling. |
| **Depreciation (capital allowances)** | **Straight-line** per Second Schedule, Inland Revenue Act No. 24 of 2017; plant & machinery 5 yr (20%/yr), buildings/structures 20 yr (5%/yr) | Split plant/civil lives, not a single blended life. Confirm against the current Second Schedule. |
| **Tax-loss carry-forward (TLCF)** | **6 years** | Confirmed: business losses carry forward up to six years under the Inland Revenue Act. The 25-year carry-forward applies only to >US$1bn depreciable-asset projects — irrelevant to a 150 MW wind farm. |
| **SSCL** | **2.5%** on liable turnover | Confirmed in the IRD 2025/26 chart; registration threshold ~Rs.60m/12 months (or Rs.15m/quarter). Activity-weighted. |
| **VAT** | **18%** | Confirmed in the IRD 2025/26 chart, effective 1 Jan 2024 (up from 15%); VAT treatment of electricity supply by an IPP should be confirmed case by case. |

**Modelling implications.** A new renewable IPP should be modelled at **no statutory tax holiday**, with **split 5-year plant / 20-year civil straight-line depreciation**, a **6-year TLCF**, **30% CIT**, **10% interest WHT** (treaty-modulated), and a **15% dividend WHT** as the distribution-tax lever. The removal of the holiday is itself a value driver — it removes the shelter that older Sri Lankan renewable models assumed. An enhanced-capital-allowance multiplier (an Enhanced Depreciation Allowance does exist under the Act's Second Schedule), where it applies, must be carried as an explicit multiplier (not a mangled percentage) so the depreciation base is not silently understated.

---

## 5. Grid-Curtailment and Multi-Technology Modelling

### 5.1 Curtailment — a layered loss-stack, not a flat haircut

Curtailment belongs in the **loss taxonomy** alongside wake, availability and electrical losses, and ideally as a *computed, provenance-stamped* figure rather than a single flat percentage. A flat haircut (e.g. 2%) is a placeholder that, on a constrained transmission corridor, plausibly **understates** the real bankability risk — the same class of flattering assumption as a stale FX rate or an inflated capacity figure. The disciplined treatment:

- **Document the flat figure as an unvalidated placeholder** and widen/justify its Monte-Carlo and tornado band rather than treating it as known.
- **Make curtailment a first-class risk variable** with a red-flag-register caveat pending a real interconnection study.
- **When real feeder data lands** (impedances, loads, topology), compute an annual curtailment percentage from a static/representative-week quasi-static time-series power-flow and feed it into the *existing* loss stack as a computed value — default-off, behind an optional extra, and reconciled fail-loud against the config haircut. A synthetic feeder is a demo, not a bankable number; **data is the critical path, not code.**

Two approaches were explicitly rejected as the wrong tool class for a 20-year cash-flow model: promoting a secondary AEP engine to primary (the rigorous wake-model engine is more appropriate for bankable AEP), and dynamic sub-hourly co-simulation (huge complexity, zero finance-decision value — the financial model needs an *annual* P50/P90 energy figure and a curtailment haircut, which is what drives DSCR and IRR).

### 5.2 Multi-technology (wind + solar + storage) portfolios

A portfolio is modelled by **explicit per-technology blocks** rather than a single blended assumption, with the honesty discipline that revenue is billed on real combined nameplate × blended capacity factor — so the combined CFADS is genuinely combined, and any per-technology split is a *declared, labelled allocation* rather than independent per-technology finance.

- **Generation technologies (wind, solar):** each declares capacity, capacity factor, degradation and capex. A wind producer uses a rigorous wake model; a solar producer uses an established irradiance-to-AC chain. Combined CFADS can be split proportionally by AEP as an *indicative* allocation.
- **Per-technology sensitivity (tornado):** must use **coupled overrides** to stay honest — a per-technology capacity-factor shock must also re-blend the project-level capacity factor so the year-1 reconciliation holds exactly, and a per-technology capex shock must also move the total capex; otherwise the tooling sweeps keys the engine never reads and reports fake-zero sensitivities. On a wind-dominated hybrid, wind drives IRR and balloon volatility several times more than solar simply because it is the bulk of generation.
- **Storage / BESS:** a battery is **not** a capacity-factor × tariff generator and its finance is modelled separately (capacity/availability tolling or arbitrage revenue, round-trip-efficiency losses, augmentation capex). Storage blocks are detected and reported but must not be *swept* as if they were generators until their economics are modelled — sweeping an unmodelled block produces a phantom sensitivity. The clean design is an explicit per-technology `type` discriminator (wind | solar | bess | …), with "hybrid" *derived* from the blocks present rather than stored as a second source of truth.

---

## 6. What "Good" Looks Like — and the Red Flags

A bankable, conservatively-underwritten renewable IPP shows:

- Debt sized on the **downside resource** (a short-horizon low P-value), not P50.
- **Minimum DSCR ≥ ~1.20×** across *all* named downside cases (P90 resource, capex overrun, FX shock, delay, curtailment), with LLCR/PLCR above covenant.
- A **funded DSRA**, modelled **distribution lock-up and cash sweep**, and a DSRA that is *released* to equity at maturity.
- Tax handled on the **current** Sri Lankan regime — no holiday, split depreciation, 6-year TLCF, correct WHT.
- The **LKR-revenue / USD-debt mismatch stressed hard**, at the *effective hedged* cost of debt.
- A **conservative or zero merchant tail** beyond the PPA.
- Monte-Carlo **breach probability and worst-year DSCR surfaced to the credit committee**, with a PSD correlation matrix and a coherent tail metric.

The red flags are the mirror image: returns shown only at P50; a thin DSCR cushion in a single downside; under-stressed FX; an over-credited post-PPA tail; assumptions hardcoded rather than config-driven; and numbers asserted but never executed. The value verdict a DFI analyst ultimately gives is a single question with three parts: **is there a margin of safety for the lender (downside resource + DSCR cushion + DSRA + sweep), an adequate and conservative equity return — and is the DFI genuinely additional?**

---

## External validation & sources

Each externally-verifiable benchmark/regime claim below was checked on 2026-06-25 against the cited authoritative source. Project-specific scenario numbers are *model results* and are not externally validated.

**Debt sizing, DSCR/LLCR and sculpting**
- DSCR is sized backwards from CFADS against a target, with gearing expressed as a maximum (e.g. 75/25) and a minimum DSCR (e.g. 1.4×) in the term sheet — confirmed (Yescombe, *Principles of Project Finance*; debt-sizing references): https://www.yescombe.com/PPF2bookframe.htm and https://www.wallstreetprep.com/knowledge/debt-sizing-in-project-finance/
- DSCR benchmarks: contracted solar ~1.20–1.30×, contracted wind ~1.30–1.40×, merchant ~1.75–2.00× — confirmed: https://courses.renewablesvaluationinstitute.com/pages/academy/debt-sizing-with-target-dscr and https://greenbridgeinfra.com/resources/project-finance/project-finance-dscr (the document's "target ≈1.30× / min ≈1.20×" sits within this range; *strengthened* with the wind/solar/merchant split).
- NREL ATB 2024/2025 vintage anchor for the DSCR ranges (recorded 2026-07-02, #620): the ATB 2024 financial cases assume P50 DSCR ~1.25× (contracted solar) / ~1.3–1.4× (contracted wind) at a ~2.5% real interest rate — https://atb.nrel.gov/electricity/2024/financial_cases_&_methods

**P50/P75/P90 and IEC 61400-15-2**
- IEC 61400-15-2 frames pre-construction EYA as a P50 + σ_AEP distribution from which P75/P90/P95 follow, used for bank/investor risk management — confirmed: https://www.profec-ventus.com/services/uncertainty-assessments-of-wind-resource-and-energy-yield.html and the IEC 61400-15 standard family at https://github.com/IEC-61400/eya-def
- P50-bias mirage: NREL-led multi-consultant benchmark found mean net P50 bias **−1.2%** (σ 4.8%) because gross over-prediction and loss over-prediction cancel, with persistent inter-consultant disagreement and up to ~$10/MWh LCOE spread — confirmed (Todd et al., *Wind Energy*, 2022): https://onlinelibrary.wiley.com/doi/full/10.1002/we.2768 and https://research-hub.nrel.gov/en/publications/an-independent-analysis-of-bias-sources-and-variability-in-wind-p-2/ (*added* the specific −1.2% / 4.8% figures).

**FX / currency mismatch (emerging-market renewables)**
- Country/currency risk drives a large cost-of-capital premium; IRENA WACC ~3.8% (Europe) to ~12% (Africa), CoC ~200–300 bps above country risk, financing cost dominates LCOE in high-risk markets — confirmed: https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2023/May/IRENA_The_cost_of_financing_renewable_power_2023.pdf and https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2016/IRENA_Risk_Mitigation_and_Structured_Finance_2016.pdf (*added* the WACC range and 200–300 bps premium).
- The thin long-tenor private hedge market ("missing risk market") — confirmed in IRENA risk-mitigation/structured-finance work (same source).
- MIGA breach-of-contract and Non-Honoring of Sovereign Obligations cover (up to ~20 yr, used on state-offtaker PPAs) — confirmed: https://www.miga.org/products and https://www.miga.org/fragile-and-conflict-affected-situations-fcs (*strengthened* the political-risk bullet).

**Sri Lankan corporate-tax regime (primary source: IRD 2025/26 tax chart)**
- CIT 30%; dividend WHT 15%; interest WHT 10%; VAT 18% (from 1 Jan 2024); SSCL 2.5% — **all confirmed directly** from the Inland Revenue Department 2025/26 tax chart: https://www.ird.gov.lk/en/publications/SitePages/tax_chart_2526.aspx?menuid=1404
- TLCF 6 years; capital allowances / Enhanced Depreciation Allowance under the Second Schedule of Inland Revenue Act No. 24 of 2017 — confirmed (IRD Act guidance): https://www.ird.gov.lk/en/publications/acts_income%20tax_2017/guide%20to%20inland%20revenue%20act.pdf (exact 5-yr/20% plant and 20-yr/5% building lines should be checked against the current Second Schedule — see flag).
- VAT/SSCL effective dates and thresholds — confirmed: https://www.ird.gov.lk/en/Type%20of%20Taxes/SitePages/Social%20Security%20Contribution%20Levy%20(SSCL).aspx

**Monte-Carlo / copulas / CVaR**
- Gaussian copula has zero asymptotic tail dependence for ρ<1 (asymptotic independence); t-copula gives symmetric tail dependence, Clayton lower-tail — confirmed: https://www.columbia.edu/~mh2078/QRM/Copulas_MasterSlides.pdf and https://arxiv.org/pdf/1607.04736
- CVaR coherent for continuous and discrete distributions; computed via the Rockafellar–Uryasev (2000) minimisation/LP formula — confirmed: https://www.sciencedirect.com/science/article/abs/pii/S0378426602002716 and https://www2.mathematik.hu-berlin.de/~romisch/SP01/Uryasev.pdf (*added* the explicit formula and convexity/LP note).
- Spreadsheet/financial-model error prevalence (~90% of audited sheets contain errors; large share of models carry material defects) supporting pre-close model audit — confirmed (spreadsheet-error literature, incl. EuSpRIG/Coopers & Lybrand and KPMG-type survey references): https://arxiv.org/pdf/0805.4224 and https://www.qashqade.com/insights/the-worst-financial-services-excel-errors-of-all-time

**Flagged / not independently re-derivable**
- [unverified] The exact Sri Lanka Second-Schedule line items "plant & machinery 5 yr (20%/yr)" and "buildings 20 yr (5%/yr)": the framework, straight-line basis, 6-yr TLCF and existence of an Enhanced Depreciation Allowance are confirmed from IRD sources, but the precise per-class rates were not retrievable in the published chart and should be checked against the current Second Schedule before reliance.
- [unverified] The literal phrase that FX risk is "largely unmanageable for the private sector": the *substance* (FX/country risk has no natural private owner and is a dominant premium driver) is well-supported by IRENA, but the exact quotation is attributed to the underwriting literature and is retained as a paraphrase, not a sourced verbatim quote.
- Project-specific scenario figures (gearing 0.63/0.70, the ~11% FX correction, AEP/IRR results) are model outputs, out of scope for external validation, and are preserved unchanged.

## Changelog (deep-research update 2026-06-25)

**Confirmed (left as stated, citations added):**
- DSCR target ~1.30× / min ~1.20× for contracted infra; gearing 70–80%; CFADS-backwards debt sizing and sculpting (Yescombe / lender practice).
- P50/P75/P90/P99 exceedance framework and IEC 61400-15-2 as the EYA bankability standard.
- Gaussian-copula zero tail dependence; t/Clayton alternatives; CVaR coherence and the Rockafellar–Uryasev formula; spreadsheet-error prevalence justifying pre-close model audit.
- **Sri Lanka CIT 30%, dividend WHT 15%, interest WHT 10%, VAT 18%, SSCL 2.5% — all confirmed directly against the IRD 2025/26 tax chart (primary source).** 6-year TLCF confirmed.

**Corrected / refined:**
- DSCR row in §1.4 now states the empirical wind/solar/merchant DSCR split (solar ~1.20–1.30×, wind ~1.30–1.40×, merchant ~1.75–2.00×) rather than a single generic band.
- §1.5 lock-up threshold characterised more precisely (commonly at/just above the min-DSCR covenant).

**Added:**
- §2.1: the specific NREL/Todd-et-al-2022 figures (mean net P50 bias −1.2%, σ 4.8%, ~$10/MWh LCOE spread) as the primary anchor for the "P50-bias mirage."
- §2.4: explicit Rockafellar–Uryasev CVaR formula and the convexity/LP property; sourced spreadsheet-error prevalence.
- §3 intro and §3.4: IRENA cost-of-capital framing (3.8%→12% WACC range, ~200–300 bps over country risk, financing-cost-dominated LCOE), the "missing risk market" hedge-liquidity gap, and MIGA breach-of-contract / Non-Honoring-of-Sovereign-Obligations cover.
- §4: notes that each rate was re-confirmed against the IRD 2025/26 chart, and that an Enhanced Depreciation Allowance exists under the Second Schedule.
- New "External validation & sources" section with full URLs.

**Flagged [unverified]:**
- Exact Sri Lanka Second-Schedule depreciation line items (5 yr/20% plant, 20 yr/5% buildings) — framework confirmed, precise per-class rates to be checked against the current Second Schedule.
- The verbatim "largely unmanageable for the private sector" quotation — substance supported by IRENA, retained as paraphrase.
- All project-specific scenario numbers left unchanged (out of scope for external validation).
