# Blue Whale Financing, FX, Tenor-Tail, and Evidence-Status Review

Prepared 14 November 2026 (Refreshed 15 November 2026) | Version 1.1
Complementary to PR #1678 (`#1677`, Equipment-Cost Parity Benchmark & Logistics Buildup)

> **HOLD (F-5, `#1110`, `v15.6.1`) & Scope Caveat:**
> This document and its companion screening utility (`analytics/finance/blue_whale_fx_tenor_screening.py`) produce **standalone screening indicators only** — **not** a lender verdict, bankability determination, or credit commitment. Lender interest rates (DFI 8.40%, local 12.76%) and DSCR thresholds (1.30x / 1.10x / 1.50x) are **illustrative screening assumptions, not executed lender terms (`#1629`)**.
>
> **Pending Engine Path:** The core v14 engine path is **pending** — FX feeding the USD OPEX share is **BW-5 (`L-12 D-2`)** work.
>
> **Addendum (BW-5, `#1578` L-12):** The core v14 engine's Python override gateways now carry an FX override to the USD OPEX share (the web API's `/run-pipeline` overrides do not yet): an FX drift stress or a Monte Carlo drift draw replaces that share's own FX path with the stressed model curve. This review is kept as written on its dates; where it calls that engine path pending, it describes the state then. The screening still does not call the engine.
>
> **Addendum (`#1578` U4, 17 November 2026):** The screening now runs for any scenario that declares a `financing_screening` block (contract `#1754`): `scripts/run_fx_tenor_screening_v14.py scenario=<path>`, through the site-neutral `analytics/finance/fx_tenor_screening.py`. Capex, tariff, O&M, FX at close, timeline, tax and the gearing cap come from the scenario itself, and the assumptions, cases, stress grid and FX observations below now live in `scenarios/dutchbay_basecase_2025Q4.yaml`'s block. A scenario without the block is reported as not applicable. The module and config named in this review remain as a single-site adapter whose output is byte-identical, and the block-driven run reproduces every figure below exactly. No figure in this review changes.
>
> **No Measured Wind Data / No P90:** There is **no measured DutchBay wind data and no measured P90**. All downside generation figures (`assumed_downside_gwh = 377.3 GWh`) are **assumed downside screening sensitivities**, not measured P90 estimates.

---

## 1 Executive summary and purpose

This review ingresses and evaluates the financing, foreign exchange (FX), debt tenor-tail, and evidence-status research from the owner's private research hand-off of 2026-11-14, aligned to the governed 14-turbine DutchBay basecase (`scenarios/dutchbay_basecase_2025Q4.yaml`, `#1587`).

The review establishes four essential calculation and governance controls for Blue Whale project evaluation:
1. **Evidence classification (`DATA-01`)**: Categorizes all financial, tariff, permit, and cost assumptions into seven explicit evidence classes to distinguish primary checked facts and governed repository scenarios from unverified assumptions, screening models, conditional rights, and unresolved items.
2. **Correction of Envision commercial pricing premise**: Clarifies that the September 2026 Kalpitiya proposal is a technical proposal and controlled power-curve package containing no commercial price schedule. A single-machine commercial price remains unquoted; missing items must fail closed (`None`) and cannot be estimated by adjacent project blends.
3. **Debt tenor-tail screening check**: Evaluates whether illustrative debt maturity stays within contracted revenue duration less an illustrative lender tail (`max(dfi_tenor, local_tenor) <= ppa_years - lender_tail_years`), motivating a 12-year SPPA sensitivity alongside the 20-year reference.
4. **Dual-currency FX and DSCR screening**: Computes illustrative senior debt sizing indicators under a dual-currency structure (USD DFI tranche translated at payment FX; LKR domestic tranche fixed in LKR at closing FX) across reference P50 and assumed-downside generation, historical FX CAGR paths, and forward shock sensitivities.

This work is standalone analytical screening and review tooling (`analytics/finance/blue_whale_fx_tenor_screening.py`, `conf/blue_whale_fx_tenor_screening.yaml`, `scripts/run_blue_whale_fx_tenor_screening_v14.py`). It reads governed basecase inputs (`capex_usd`, `opex_usd_equivalent_year1`, `tariff_fixed_lkr_per_kwh`, `fx_close_lkr_per_usd`, `fx_depreciation_decimal`, etc.) directly from `scenarios/dutchbay_basecase_2025Q4.yaml`, is complementary to PR #1678, does not modify frozen scenario YAMLs (`scenarios/blue_whale_*.yaml`), and confers no lender, Board, or commercial approval. The core v14 engine path for FX feeding the USD OPEX share remains pending (`BW-5 / L-12 D-2`).

---

## 2 Evidence classification framework

To prevent informal assumptions from masquerading as verified inputs, all data points in the Blue Whale financing and cost review are classified into seven canonical tiers:

| Evidence Class | Definition | Application to Blue Whale |
|---|---|---|
| **Primary checked** | Official source directly accessible and verified at official publication endpoint. | Central Bank of Sri Lanka (CBSL) 2025 review / 2026 release (2024–2025 year-end rates); SOFR 3.90% on FRED (12 Nov 2026); PUCSL feed-in tariff schedule (24 Aug 2026). |
| **Repository observed** | Input inspected and verified byte-for-byte at recorded local repository commit. | Governed basecase inputs in `scenarios/dutchbay_basecase_2025Q4.yaml` (`$150M` capex, `$3.0M/yr` O&M, `20.30 LKR/kWh` tariff, `300.0` FX-at-close, `5.89%/yr` drift); 14-turbine DutchBay scope (`#1587`); frozen scenario CAPEX `$8,899,980` in `scenarios/blue_whale_wind_lot5b_2026.yaml`; AEP transfer summary `40.575 GWh` in `docs/blue_whale/met_mast_transfer_summary.json`. |
| **Unverified assumption** | Prior-session or secondary figure not independently reproduced from a primary source; treated strictly as an assumption under `DATA-01`. | 2021–2023 year-end FX rates (`200.43`, `363.11`, `323.92`), 2026-11-13 indicative spot (`332.50`), sensitivity O&M (`$3.359M/yr` = `$2.8467M * 1.18` VAT), AWPR `11.01%` observation, illustrative lender margins/rates (`#1629`). |
| **Reconstructed** | Newly implemented calculation or refreshed screening model; assumptions and boundaries stated. | Standalone dual-currency screening model (`analytics/finance/blue_whale_fx_tenor_screening.py`); 70-iteration bisection screening indicator; 2D FX stress grid. |
| **Conditional** | Dependent on unsigned agreement, pending regulatory decision, or unverified eligibility. | 20-year SPPA duration; exemption from 10 MW contiguous-site limit; concessional DFI margin; tax holiday/depreciation ruling. |
| **Unresolved** | Missing source, incomplete scope, inconsistent data, or unpriced major package. | Measured DutchBay wind data and P90 (`assumed_downside_gwh` used as sensitivity only); single-unit EN206 commercial quote; marine delivery/jetty EPC price; BESS replacement and augmentation contract terms; core v14 engine FX-OPEX path (`BW-5 / L-12 D-2`). |
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

### Published tariff rates vs. governed basecase
- **Governed basecase (`scenarios/dutchbay_basecase_2025Q4.yaml`)**: Flat fixed tariff of **LKR 20.30 / kWh** (`tariff_om_lkr_per_kwh = 0.0`).
- **Sensitivity (PUCSL published wind feed-in tariff effective 25 August 2026 to 24 February 2027)**: Fixed (capital) component LKR 20.80 / kWh + O&M component LKR 4.93 / kWh = LKR 25.73 / kWh initial tariff.

### Statutory contiguous-location restriction
Section 11(3) of the Sri Lanka Electricity Act No. 36 of 2024 establishes a statutory proviso:
> "...the aggregate capacity of plants utilizing standardized purchase agreements from a contiguous location shall not exceed 10 MW."

While the 2025 amendment expanded enabling language for storage and ancillary services, it did not repeal the contiguous-location proviso. Consequently:
- Circumventing the 10 MW boundary by executing multiple separate SPPAs across contiguous parcels carries substantial regulatory and legal challenge risk.
- For Blue Whale (9.5 MW wind + 5 MW PV + 5 MW BESS), explicit regulatory determination is required for grid-export limiting and contiguous-site eligibility.

### PPA duration and illustrative lender-tail screening check
Although the PUCSL methodology uses a generic 20-year financial modeling horizon, commercial banks and DFIs typically require debt repayment to terminate before contracted revenue expires.
- **Tenor-tail screening invariant**:
  $$\max(T_{\text{DFI}}, T_{\text{local}}) \le T_{\text{PPA}} - T_{\text{tail}}$$
- Where $T_{\text{PPA}} = 12$ years (short-tenor policy sensitivity) and $T_{\text{tail}} = 2$ years, the illustrative screening ceiling for debt tenor is 10 years; a 15-year DFI tranche exceeds this screening threshold.

---

## 5 FX historical analysis and forward stress scenarios

### Exchange-rate observations
Central Bank of Sri Lanka (CBSL) and prior-session exchange-rate observations (LKR per USD):

| Date | LKR / USD | Periodic Quote Change | LKR Value Depreciation | Evidence Status (`DATA-01`) |
|---|---:|---:|---:|---|
| 2021-12-31 | 200.43 | — | — | **Unverified assumption** (prior-session figure; primary series not refetched) |
| 2022-12-31 | 363.11 | +81.17% | -44.80% | **Unverified assumption** (prior-session figure; primary series not refetched) |
| 2023-12-31 | 323.92 | -10.79% | +12.10% | **Unverified assumption** (prior-session figure; primary series not refetched) |
| 2024-12-31 | 292.58 | -9.68% | +10.71% | Primary checked (CBSL 2025 review and 2026 press release) |
| 2025-12-31 | 309.99 | +5.95% | -5.62% | Primary checked (CBSL 2025 review and 2026 press release) |
| 2026-11-13 | 332.50 | +7.26% | -6.77% | **Unverified assumption** (secondary CBSL republication; not primary-refetched) |

### Quote change vs. currency value depreciation
Distinction between quote appreciation ($q$) and rupee purchasing power loss ($d$):
$$q = \frac{E_{\text{end}}}{E_{\text{start}}} - 1, \quad d = 1 - \frac{E_{\text{start}}}{E_{\text{end}}}, \quad (1 + q)(1 - d) = 1$$
For 2022 (on the assumed 200.43 to 363.11 series), the quote rose by +81.17%, while the rupee's external value fell by -44.80%.

### Annualized CAGR windows (actual days / 365.25; assumption-dependent endpoints)
$$\text{CAGR} = \left(\frac{E_{\text{end}}}{E_{\text{start}}}\right)^{\frac{365.25}{\Delta \text{days}}} - 1$$
- **5-year near-matched** (2021-11-24 [200.78] to 2026-11-13 [332.50]): **+10.684%** / yr *(unverified assumption endpoints)*
- **Post-crisis** (2022-12-31 [363.11] to 2026-11-13 [332.50]): **-2.251%** / yr *(unverified assumption endpoints)*
- **Recent recovery** (2024-12-31 [292.58] to 2026-11-13 [332.50]): **+7.090%** / yr *(unverified assumption terminal rate)*

---

## 6 Dual-currency debt screening indicators (14-turbine DutchBay `#1587`)

> **F-5 HOLD Caveat (`#1110`, `v15.6.1`):** All figures below are **standalone screening indicators only**, not a lender verdict or bankability determination. DFI/local interest rates (`8.40%` / `12.76%`) and DSCR thresholds (`1.30x` / `1.10x` / `1.50x`) are **illustrative screening assumptions, not lender terms (`#1629`)**.

### Dual-currency loan mechanics
Committed debt $D_{\text{USD}}$ is allocated into two currency tranches:
1. **USD DFI tranche** ($\alpha D_{\text{USD}}$, $\alpha = 0.30$): Amortized over $T_{\text{DFI}}$ years at illustrative screening rate $r_{\text{DFI}} = 8.40\%$ (SOFR 3.90% + 4.50% margin assumption). Service is paid in USD and translated to LKR at operating-year scenario FX.
2. **LKR domestic tranche** ($(1 - \alpha) D_{\text{USD}} \cdot E_{\text{close}}$): Fixed in LKR at closing FX ($E_{\text{close}} = 300.0$ LKR/USD in the governed basecase; `333.79` LKR/USD in the handoff sensitivity). Amortized over $T_{\text{local}} = 10$ years at illustrative screening rate $r_{\text{local}} = 12.76\%$ (AWPR 11.01% + 1.75% margin assumption). Service is fixed in LKR throughout its 10-year life.

### Screening thresholds (illustrative, not lender covenants)
Debt capacity indicators are computed via 70-iteration bisection against four simultaneous screening thresholds:
1. **Reference P50 min DSCR**: $\min_{t} \text{DSCR}_{50}(t) \ge 1.30$
2. **Assumed-downside min DSCR** *(not a measured P90)*: $\min_{t} \text{DSCR}_{\text{downside}}(t) \ge 1.10$
3. **Reference P50 average DSCR over local tenor**: $\frac{1}{T_{\text{local}}} \sum_{t=1}^{T_{\text{local}}} \text{DSCR}_{50}(t) \ge 1.50$
4. **Maximum gearing cap**: $D_{\text{USD}} \le 0.70 \times \text{CAPEX}_{\text{USD}}$

### Screening indicator results (14-turbine DutchBay `#1587`; 15-turbine case dropped)

| Metric | Governed Basecase (15-Yr DFI) | Governed Basecase (10-Yr DFI) | Explicit Handoff Sensitivity (15-Yr DFI) |
|---|---:|---:|---:|
| **Case classification** | Governed basecase screening | Governed basecase screening | **Explicit sensitivity** |
| **Scope basis** | 14 turbines (`#1587`) | 14 turbines (`#1587`) | 14 turbines (`#1587`) |
| **Gross CAPEX** | $150,000,000 (`dutchbay_basecase_2025Q4.yaml`) | $150,000,000 (`dutchbay_basecase_2025Q4.yaml`) | $159,120,000 *(sensitivity)* |
| **Year-1 O&M** | $3,000,000 (`dutchbay_basecase_2025Q4.yaml`) | $3,000,000 (`dutchbay_basecase_2025Q4.yaml`) | $3,359,106 *(unverified assumption)* |
| **Tariff (LKR/kWh)** | 20.30 fixed (`dutchbay_basecase_2025Q4.yaml`) | 20.30 fixed (`dutchbay_basecase_2025Q4.yaml`) | 20.80 + 4.93 O&M *(sensitivity)* |
| **FX close / drift** | 300.0 / 5.89%/yr (`dutchbay_basecase_2025Q4.yaml`) | 300.0 / 5.89%/yr (`dutchbay_basecase_2025Q4.yaml`) | 333.79 / 7.00%/yr *(sensitivity)* |
| **PPA / tail** | 20 yrs PPA / 0 tail | 12 yrs PPA / 2-yr tail | 20 yrs PPA / 0 tail |
| **Tranche tenors** | DFI 15 yrs / Local 10 yrs | DFI 10 yrs / Local 10 yrs | DFI 15 yrs / Local 10 yrs |
| **Screening debt indicator** | **$69,961,840** | **$63,198,314** | **$74,370,107** |
| **Screening gearing** | **46.64%** | **42.13%** | **46.74%** |
| **Sponsor equity balance** | $80,038,160 | $86,801,686 | $84,749,893 |
| **P50 Min DSCR** | 1.3000 (Year 10 binding) | 1.3000 (Year 10 binding) | 1.3000 (Year 10 binding) |
| **P50 Local-tenor avg DSCR** | 1.6012 | 1.6315 | 1.6539 |
| **Assumed-downside Min DSCR** *(not measured P90)* | 1.1163 (Year 10 binding) | 1.1138 (Year 10 binding) | 1.1111 (Year 10 binding) |

### Binding year shift under FX drift
Under moderate FX drift ($\le 8\%$), the local tranche repayment in Year 10 is the binding screening constraint on project DSCR. Under **10.68% annual FX depreciation** (on the `$87.77M` fixed-debt stress grid), the compounded depreciation of the rupee inflates the LKR cost of servicing the USD DFI tranche in Year 15 to such an extent that **Year 15 becomes the binding screening year**, even though the local tranche was fully retired five years earlier.

---

## 7 Complementarity with PR #1678 and pending engine path

This pull request is complementary to Draft PR #1678 (`feat/blue-whale-equipment-parity-20261114`):

| Dimension | PR #1678 (`#1677`) | This PR (`#1681`) |
|---|---|---|
| **Domain** | Wind engineering, equipment parity, logistics | Finance, dual-currency debt screening, FX & tenor-tail |
| **Primary module** | `analytics/wind/blue_whale_equipment_parity.py` | `analytics/finance/blue_whale_fx_tenor_screening.py` |
| **Config file** | `conf/blue_whale_equipment_parity.yaml` | `conf/blue_whale_fx_tenor_screening.yaml` |
| **Hydra CLI** | `scripts/run_blue_whale_equipment_parity_v14.py` | `scripts/run_blue_whale_fx_tenor_screening_v14.py` |
| **Documentation** | `docs/blue_whale/EQUIPMENT_PARITY_AND_LOGISTICS_REVIEW_2026-11-14.md` | `docs/blue_whale/FINANCING_FX_AND_EVIDENCE_REVIEW_2026-11-14.md` |
| **Test suite** | `tests/wind/test_blue_whale_equipment_parity.py` | `tests/finance/test_blue_whale_fx_tenor_screening.py` |
| **Scenario YAMLs** | Untouched (`$8,899,980` frozen CAPEX preserved) | Untouched (`scenarios/blue_whale_*.yaml` preserved; reads `scenarios/dutchbay_basecase_2025Q4.yaml` read-only) |
| **Engine path** | Standalone engineering parity | Standalone screening; **core v14 engine path pending (`BW-5 / L-12 D-2` for FX feeding USD OPEX share)** |
| **Path overlap** | Disjoint | Disjoint (zero overlapping files) |

---

## 8 Confidentiality and disclosure boundaries

In accordance with `DATA-01`, `GOV-02`, and project confidentiality rules:
- No raw commercial prices from confidential vendor offers or tender submissions are included in repository code or documentation.
- The identified private Kalpitiya proposal is cited by document date and technical finding only; its text, figures, and binaries are withheld.
- Derived screening numbers and benchmark comparisons are published as reproducible arithmetic without exposing confidential anchor values.
