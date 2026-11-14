# Blue Whale Financing, FX, Tenor-Tail, and Evidence-Status Review

Prepared 14 November 2026 | Document ID: `BW-FIN-COST-20261114-REV` | Version 1.0
Complementary to PR #1678 (`#1677`, Equipment-Cost Parity Benchmark & Logistics Buildup)

---

## 1 Executive summary and purpose

This review ingresses and evaluates the financing, foreign exchange (FX), debt tenor-tail, and evidence-status research from the 14 November 2026 research handoff (`Blue_Whale_Research_Handoff_2026-11-14.zip`, document `BW FIN COST 20261114`, v1.0).

The review establishes four essential calculation and governance controls for Blue Whale project evaluation:
1. **Evidence classification**: Categorizes all financial, tariff, permit, and cost assumptions into seven explicit evidence classes to distinguish primary checked facts from unverified historical claims, reconstructed screening models, conditional rights, and unresolved items.
2. **Correction of Envision commercial pricing premise**: Clarifies that the September 2026 Kalpitiya proposal is a technical proposal and controlled power-curve package containing no commercial price schedule. A single-machine commercial price remains unquoted; missing items must fail closed (`None`) and cannot be estimated by adjacent project blends.
3. **Debt tenor-tail gate**: Strictly enforces that senior debt maturity cannot exceed contracted revenue duration less the required lender tail (`max(dfi_tenor, local_tenor) <= ppa_years - lender_tail_years`), requiring a 12-year SPPA sensitivity alongside the 20-year reference.
4. **Dual-currency FX and DSCR screening**: Sizes committed senior debt under a dual-currency structure (USD DFI tranche translated at payment FX; LKR domestic tranche fixed in LKR at closing FX) across P50/P90 generation, historical FX CAGR paths, and forward shock sensitivities.

This work is analytical screening and review tooling (`analytics/finance/blue_whale_fx_tenor_screening.py`, `conf/blue_whale_fx_tenor_screening.yaml`, `scripts/run_blue_whale_fx_tenor_screening_v14.py`). It is complementary to PR #1678, does not modify frozen scenario YAMLs (`scenarios/blue_whale_*.yaml`), and confers no lender, Board, or commercial approval.

---

## 2 Evidence classification framework

To prevent informal assumptions from masquerading as verified inputs, all data points in the Blue Whale financing and cost review are classified into seven canonical tiers:

| Evidence Class | Definition | Application to Blue Whale |
|---|---|---|
| **Primary checked** | Official source directly accessible and verified at official publication endpoint. | Central Bank of Sri Lanka (CBSL) 2025 review / 2026 release; SOFR 3.90% on FRED (12 Nov 2026); PUCSL feed-in tariff schedule (24 Aug 2026). |
| **Repository observed** | Input inspected and verified byte-for-byte at recorded local repository commit. | Frozen scenario CAPEX `$8,899,980` in `scenarios/blue_whale_wind_lot5b_2026.yaml`; AEP transfer summary `40.575 GWh` in `docs/blue_whale/met_mast_transfer_summary.json`. |
| **Historical claim** | Asserted in earlier session or chat; not independently reproduced from primary source. | Historical loan sizing ($87.77M / $81.62M); claim of March 2026 12-year PPA policy letter; AWPR 11.01% dated observation. |
| **Reconstructed** | Newly implemented calculation or refreshed model; assumptions and boundaries stated. | Dual-currency screening model (`analytics/finance/blue_whale_fx_tenor_screening.py`); 70-iteration bisection debt sizing; 2D FX stress grid. |
| **Conditional** | Dependent on unsigned agreement, pending regulatory decision, or unverified eligibility. | 20-year SPPA duration; exemption from 10 MW contiguous-site limit; concessional DFI margin; tax holiday/depreciation ruling. |
| **Unresolved** | Missing source, incomplete scope, inconsistent data, or unpriced major package. | Single-unit EN206 commercial quote; marine delivery/jetty EPC price; BESS replacement and augmentation contract terms. |
| **Withheld** | Source identified in private corpus but excluded from public repository under confidentiality. | Private proposal text/binaries; vendor price formulas; sensitive supplier schedules in private RAG. |

---

## 3 Correction of Envision pricing premise

The earlier research premise asserted that an Envision commercial price schedule was available in the September 2026 Kalpitiya proposal package and had merely been omitted from the Blue Whale blend.

**Audit finding**:
- The Kalpitiya package consists of a technical proposal, foundation interface data, and a controlled power curve document.
- It contains **zero commercial price schedules** for turbine supply, tower, transport, or erection.
- No commercial single-machine OEM quote exists in that package.
- Estimating the missing single-machine price by energy-proportional scaling from an adjacent 50 MW / 56 MW wind farm (Mannar benchmark) or by applying an arbitrary rating exponent is invalid for procurement and contract negotiations (`TEST-01`).
- Under `CESSPIT` and `CASPER`, missing cost packages must remain unresolved (`None`) and fail closed:
  $$\text{complete\_total}(\{p_i\}) = \begin{cases} \sum p_i & \text{if all } p_i \neq \text{None} \\ \text{None} & \text{if any } p_i = \text{None} \end{cases}$$

---

## 4 PUCSL feed-in tariffs, PPA duration, and contiguous-location limits

### Published tariff rates (24 August 2026)
PUCSL published wind feed-in tariff components effective 25 August 2026 to 24 February 2027:
- **Fixed (capital) component**: LKR 20.80 / kWh
- **O&M component**: LKR 4.93 / kWh
- **Total initial tariff**: LKR 25.73 / kWh

### Statutory contiguous-location restriction
Section 11(3) of the Sri Lanka Electricity Act No. 36 of 2024 establishes a statutory proviso:
> "...the aggregate capacity of plants utilizing standardized purchase agreements from a contiguous location shall not exceed 10 MW."

While the 2025 amendment expanded enabling language for storage and ancillary services, it did not repeal the contiguous-location proviso. Consequently:
- Circumventing the 10 MW boundary by executing multiple separate SPPAs across contiguous parcels (e.g. fifteen 10 MW SPPAs for a 150 MW farm, or separate SPPAs for wind, PV, and BESS on Lot 5B) carries substantial regulatory and legal challenge risk.
- For Blue Whale (9.5 MW wind + 5 MW PV + 5 MW BESS), explicit regulatory determination is required for grid-export limiting and contiguous-site eligibility.

### PPA duration and lender tail
Although the PUCSL methodology uses a generic 20-year financial modeling horizon, commercial banks and DFIs require debt repayment to terminate safely before contracted revenue expires.
- **Tenor-tail invariant**:
  $$\max(T_{\text{DFI}}, T_{\text{local}}) \le T_{\text{PPA}} - T_{\text{tail}}$$
- Where $T_{\text{PPA}} = 12$ years (short-tenor policy scenario) and $T_{\text{tail}} = 2$ years, maximum allowable debt tenor is 10 years. A 15-year DFI tranche strictly fails this gate.

---

## 5 FX historical analysis and forward stress scenarios

### Historical exchange-rate observations
Central Bank of Sri Lanka (CBSL) published exchange rates (LKR per USD):

| Date | LKR / USD | Periodic Quote Change | LKR Value Depreciation | Evidence Status |
|---|---:|---:|---:|---|
| 2021-12-31 | 200.43 | — | — | Conversation transcription; primary series not refetched |
| 2022-12-31 | 363.11 | +81.17% | -44.80% | Conversation transcription; primary series not refetched |
| 2023-12-31 | 323.92 | -10.79% | +12.10% | Conversation transcription; primary series not refetched |
| 2024-12-31 | 292.58 | -9.68% | +10.71% | CBSL 2025 review and 2026 press release |
| 2025-12-31 | 309.99 | +5.95% | -5.62% | CBSL 2025 review and 2026 press release |
| 2026-11-13 | 332.50 | +7.26% | -6.77% | Indicative spot; secondary CBSL republication |

### Quote change vs. currency value depreciation
Distinction between quote appreciation ($q$) and rupee purchasing power loss ($d$):
$$q = \frac{E_{\text{end}}}{E_{\text{start}}} - 1, \quad d = 1 - \frac{E_{\text{start}}}{E_{\text{end}}}, \quad (1 + q)(1 - d) = 1$$
For 2022, the quote rose by +81.17%, while the rupee's external value fell by -44.80%.

### Annualized CAGR windows (actual days / 365.25)
$$\text{CAGR} = \left(\frac{E_{\text{end}}}{E_{\text{start}}}\right)^{\frac{365.25}{\Delta \text{days}}} - 1$$
- **5-year near-matched** (2021-11-24 [200.78] to 2026-11-13 [332.50]): **+10.684%** / yr
- **Post-crisis** (2022-12-31 [363.11] to 2026-11-13 [332.50]): **-2.251%** / yr
- **Recent recovery** (2024-12-31 [292.58] to 2026-11-13 [332.50]): **+7.090%** / yr

### Compounded forward projections
From closing FX of 332.50 LKR/USD, two-year construction to COD and subsequent operating years:
- **7.00% annual drift**: COD = 380.68; Year 10 = 699.86; Year 15 = 981.59 LKR/USD
- **10.68% annual drift**: COD = 407.31; Year 10 = 1,015.20; Year 15 = 1,686.16 LKR/USD

---

## 6 Dual-currency debt sizing and coverage mechanics

### Dual-currency loan mechanics
Committed debt $D_{\text{USD}}$ is allocated into two currency tranches:
1. **USD DFI tranche** ($\alpha D_{\text{USD}}$): Amortized over $T_{\text{DFI}}$ years at rate $r_{\text{DFI}}$ (SOFR 3.90% + 4.50% margin = 8.40%). Service is paid in USD and translated to LKR at operating-year scenario FX.
2. **LKR domestic tranche** ($(1 - \alpha) D_{\text{USD}} \cdot E_{\text{close}}$): Fixed in LKR at financial close FX ($E_{\text{close}} = 333.79$). Amortized over $T_{\text{local}}$ years at rate $r_{\text{local}}$ (AWPR 11.01% + 1.75% margin = 12.76%). Service is fixed in LKR throughout its 10-year life.

### Sizing criteria and constraints
Debt is sized via 70-iteration bisection against four simultaneous covenants:
1. **Minimum P50 DSCR**: $\min_{t} \text{DSCR}_{50}(t) \ge 1.30$
2. **Minimum P90 DSCR**: $\min_{t} \text{DSCR}_{90}(t) \ge 1.10$
3. **Average P50 DSCR over local tenor**: $\frac{1}{T_{\text{local}}} \sum_{t=1}^{T_{\text{local}}} \text{DSCR}_{50}(t) \ge 1.50$
4. **Maximum gearing cap**: $D_{\text{USD}} \le 0.70 \times \text{CAPEX}_{\text{USD}}$

### Benchmark sizing results (reconstructed reference cases)

| Metric | Selected 15-Year Case | Selected 10-Year Case |
|---|---:|---:|
| **Scope basis** | 15 turbines (reference illustration) | 15 turbines (reference illustration) |
| **Gross CAPEX** | $167,860,000 | $167,860,000 |
| **PPA / tail** | 20 years PPA / 0 tail | 12 years PPA / 2-year tail |
| **Tranche tenors** | DFI 15 yrs / Local 10 yrs | DFI 10 yrs / Local 10 yrs |
| **Sized senior debt** | **$80,770,762** | **$72,421,934** |
| **Gearing** | **48.12%** | **43.14%** |
| **Sponsor equity balance** | $87,089,238 | $95,438,066 |
| **P50 Min DSCR** | 1.3000 (Year 10 binding) | 1.3000 (Year 10 binding) |
| **P50 Debt-life average DSCR** | 1.9476 | 1.6798 |
| **P50 Local-tenor average DSCR**| 1.6423 | 1.6798 |
| **P90 Min DSCR** | 1.1119 (Year 10 binding) | 1.1092 (Year 10 binding) |
| **P90 Debt-life average DSCR** | 1.6693 | 1.4601 |

### Binding year shift under FX drift
Under moderate FX drift ($\le 8\%$), the local tranche repayment in Year 10 is the binding constraint on project DSCR. However, at **10.68% annual FX depreciation**, the compounded depreciation of the rupee ($E_{15} \approx 1,686$ LKR/USD) inflates the LKR cost of servicing the USD DFI tranche in Year 15 to such an extent that **Year 15 becomes the binding year** ($\text{DSCR}_{15} = 0.761 < 1.0$), even though the local tranche was fully retired five years earlier.

---

## 7 Complementarity with PR #1678

This pull request is complementary to Draft PR #1678 (`feat/blue-whale-equipment-parity-20261114`):

| Dimension | PR #1678 (#1677) | This PR (#1681) |
|---|---|---|
| **Domain** | Wind engineering, equipment parity, logistics | Finance, dual-currency debt sizing, FX & tenor screening |
| **Primary module** | `analytics/wind/blue_whale_equipment_parity.py` | `analytics/finance/blue_whale_fx_tenor_screening.py` |
| **Config file** | `conf/blue_whale_equipment_parity.yaml` | `conf/blue_whale_fx_tenor_screening.yaml` |
| **Hydra CLI** | `scripts/run_blue_whale_equipment_parity_v14.py` | `scripts/run_blue_whale_fx_tenor_screening_v14.py` |
| **Documentation** | `docs/blue_whale/EQUIPMENT_PARITY_AND_LOGISTICS_REVIEW_2026-11-14.md` | `docs/blue_whale/FINANCING_FX_AND_EVIDENCE_REVIEW_2026-11-14.md` |
| **Test suite** | `tests/wind/test_blue_whale_equipment_parity.py` | `tests/finance/test_blue_whale_fx_tenor_screening.py` |
| **Scenario YAMLs** | Untouched (`$8,899,980` frozen CAPEX preserved) | Untouched (`scenarios/blue_whale_*.yaml` preserved) |
| **Path overlap** | Disjoint | Disjoint (zero overlapping files) |

Both PRs share the governing principle: transparent public reproduction and screening without modifying frozen scenario baselines or publishing confidential vendor proposals.

---

## 8 Confidentiality and disclosure boundaries

In accordance with `DATA-01`, `GOV-02`, and project confidentiality rules:
- No raw commercial prices from confidential vendor offers or tender submissions are included in repository code or documentation.
- The identified private Kalpitiya proposal is cited by document date and technical finding only; its text, figures, and binaries are withheld.
- Derived screening numbers and benchmark comparisons are published as reproducible arithmetic without exposing confidential anchor values.
