# Dutch Bay — Envision 14-turbine / Wariyapola 220 kV evidence ingress

**R3 / restricted decision study — branch ingress only.** Work item #1939, tracker #1353. Original screening calculations completed 23 November 2026 from 49b9527c, numerically replayed at 071d7476, and published here as source-safe derived screening. The committed lendercase, EIA approval state and F-5 non-reliance restrictions are not changed. Earlier independent R3 reviews on draft PR #1942 requested remediation; this branch remains UNACCEPTED.

This package is the **public-repository-safe derived subset** of three earlier private working packages:

1. EIA R2 + Annex I–VI (344-page final EIA, 292-page annexes, 98 selective-OCR pages): technical obligations, source crosswalk and OCR quality.
2. P01 integrated DBPL study: 25-module reporting audit, 13 conditions precedent and 20 feasibility sections.
3. P02 Envision14/Wariyapola study: revised turbine geometry, NASA/met-mast-derived wind rose, PyWake array loss, grid advisory sensitivities, and rejection at the lender-AEP provenance gate.

Confidential original EIA, OCR text, Envision PMD-004447 confidential power/Ct curve, 2025 mast interval export, route-page images and original restricted PDFs remain **outside the public Git repository**. See DATA_HANDLING.md.

## Proposed controlling identity, not an approved lendercase

| Element | Proposed screen |
|---|---|
| Turbine | Envision EN206/10.5, 206m rotor and 130m hub |
| Derating | Assumed power curve clip at 9.5MW; OEM certified derated curve required |
| Dutch Bay | 14 countable turbines T1 and T3–T15; 147MW nameplate, 133MW assumed active limit |
| Blue Whale | Former T2; separately costed, excluded from Dutch Bay cashflow but included as external wake |
| Resource | 16-sector 130m 2015–2025 NASA/MERRA2 transfer from the partial 2025 Kalpitiya mast |
| Alternative resource | Legacy ERA5-fitted 2020–24, NOT a fresh download |
| Grid | EIA Annex III I conceptual 104.77km 220kV Kalpitiya collector–Wariyapola line |
| National line | Planned Norochcholai–Wariyapola 220kV; source plan indicates 2030; equivalence to EIA trace unproven |

A 147MW installed nameplate is not 133MW derated output or converter/POC rated MVA.

## Derived findings — screening, NOT bankable

- At an UNVALIDATED uniform model TI=0.10, 14 counted EN206 units with Blue Whale T2 active as external wake source: 616.043GWh gross, 18.522% wake loss and 462.923GWh net after the legacy non-wake stack.
- TI=0.06/0.14 gives 444.951/476.417GWh. The mast-sector indicative TI=0.070 gives 450.013GWh (rather than 462.923GWh at model TI=0.10); T2 absent at TI=0.10 gives 466.970GWh.
- Prior ERA5-fitted reference at TI=0.10 gives 370.332GWh net. The large resource discrepancy is unresolved.
- The assumed 2% haircut gives a CONDITIONAL 453.664GWh screen, NOT P50. Multiplication by a frozen Blue Whale 1-year uncertainty ratio (1 - 1.2816 × 0.1315568) gives 377.175GWh, NOT P90; the source budget has zero wake-model uncertainty. These are not probabilistic lender estimates.
- Grid: EIA conductor AC resistance 0.0702ohm/km and 104.77km route; two circuits/twin Zebra. Assumed X=0.27ohm/km/circuit and unverified 500–1500MVA upstream fault scenarios. At assumed 900MVA, SCR is 4.84 both circuits / 4.00 N–1.
- The full finance pipeline **refused** promotion because the screen lacks bankable AEP provenance. That guard must not be bypassed. No project IRR, equity IRR, DSCR, lender gearing or tariff assumption was overwritten.
- EIA source distinguishes the private 104.77km collector route from the publicly proposed national Norochcholai–Wariyapola scheme. Separate permits/engineering and a 2027 COD vs planned 2030 line date remain open.

## Published evidence

- evidence/module_assurance_matrix_25.csv: 25 substantive analytical modules with missing dedicated presentation or inactive scenarios.
- evidence/CP_feasibility_33_EIA_crosswalk.csv: thirteen conditions precedent and twenty feasibility sections, numbered physical EIA/annexure source pages, honest content coverage and missing proof.
- evidence/consolidated_input_21.csv: sourced data, maturity, promotion requirements and responsible discipline.
- report/reporting_activation.md: additional omitted report emitters and live inputs to activate them.
- results/: 16-sector rose, 7 wake cases, grid sensitivity, five additional wind adverse scenarios, and finance provenance refusal receipts.
- tools/: reproduction using runtime-provided private OEM curve; never commit the curve values or raw mast.
- report/: corrected DBPL P04 standalone source-safe annex and derived plots; the original P01 and P02 restricted reports are not published.

**Prior R3 domain, assurance and finance/E&S reviewers issued CHANGES_REQUESTED. New-head reviews pending. No regulatory or lender reliance. Do not merge without prior explicit approval from Aruna.**

## Agreed completion sequence
1. EN206 certified derating/Ct, turbine loading/IEC suitability, revised EIA geometry and T2 carve-out.
2. Longer mast/independent ERA5+NASA resource, credible MCP and bankable EYA with wake uncertainty.
3. NTNSP/NSO fault equivalent, actual 220kV POI, PSS/E/PSCAD, transmission approvals and COD gating.
4. Finance: current tariff, EN206 prices, jetty landed costs, DFI/local bank terms; then two-factor and FX/tenor screens.
5. Compare technologies and equipment on normalized assumptions; BESS/solar only with executable commercial designs.
6. Exact-head independent review pair; F-5 lifted only by separately authorized board/lender control.

## R3 remediation disclosure

Read evidence/R3_REMEDIATION_AND_RESIDUAL_HOLDS.md and evidence/COVERAGE_RUBRIC_AND_BASELINE.md before interpreting these values. The original EIA does not approve revised EN206 T2 carve-out; source rights to distribute derived analyses beyond authorized review remain unconfirmed. Neither the 7.32% historic IEA wake estimate nor the 18.52% new screen has been independently adopted. New five-case TI, rose rotation and TEC exclusion sensitivities are non-probabilistic. The 2 × 90 MVA transformer N-1 contingency is not included in the line SCR cases.

## Review-verified clarifications — new successor head

- Historic IEA-reference lendercase wake 7.32% is a **frozen calibration artifact**: original wake summary documents a live PyWake IEA-reference estimate of about **19.44% on the same layout**, very different from the frozen 7.28/7.32% figure. The new EN206/ERA5 estimate is **18.20%** and EN206/NASA **18.52%**. Source geometry/rose differences do NOT explain the entire 11.2 percentage-point frozen-versus-live discrepancy; #1589 remains unresolved.
- Default uniform TI 0.10 must not be treated as representative observed site TI. Mast sectors show SW circa 0.070, WSW circa 0.074, SSW circa 0.078. Compare ±22.5-degree rose rotations at TI 0.070 against the TI 0.070 **450.013GWh** baseline, not the TI 0.10 462.923GWh headline. A near-0.36% gross discrepancy under sector rotation may reflect discrete speed/direction integration; independent review is required.
- Proposed project EIA corridor **ownership is not established**. Historical lendercase calls the transmission line a separately CEB-funded project yet carries USD 7.6608m for a 220kV line and USD 5.1072m for a Puttalam substation bay, USD 12.768m combined. Dividing the USD 7.6608m provisional line allocation by 104.77km gives USD 73,120/km, **not an OEM/EPC cost or proof that the corridor can be constructed for that amount**. No Wariyapola cost or ownership switch is adopted.
- The NSO Updated Interim LTPSDP (2027-2029), section 4.9.2, **printed page 23 / PDF page index 29**, explicitly labels *Norochcholai–Wariyapola* 220kV as **planned completion 2030, subject to revision**: https://www.pucsl.gov.lk/wp-content/uploads/2026/09/3-Letter-from-NSO-10-08-2026-Submission-of-Updated-Interim-Report-of-LTPSDP.pdf . This is not evidence that the EIA's 104.77km line and the national project share the same physical route.
- All EIA coverage ratings have been re-adjudicated under the defined rubric: CP 2/7/4 and feasibility 4/11/5. No revised 14-machine permit, adopted ESMP or financial-close CP is verified.

## Site-specific P05 successor intake

This source-safe P05 publication candidate belongs to focused issue **#1958**, preregistered under task tracker **#1353** before this successor branch and draft PR. It was copied from earlier study #1939 / draft PR #1942 for review on the latest origin/main; old first-review vetoes and source provenance remain available for independent reconciliation.

This is distinct from synthetic methods issue **#1953 / draft PR #1955**, which carries no site-specific Envision yield, EIA, financing or Wariyapola evidence. No approval is inherited from that PR.

**DO NOT MERGE WITHOUT PRIOR EXPLICIT APPROVAL FROM ARUNA.** Independent R3 domain, assurance and finance/environmental review must bind to this exact successor head; F-5 and third-party source-rights holds persist. This is not a lender P50/P90 or an approved EIA, grid study, tariff, financing agreement or Board release.
