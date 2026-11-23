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

- At TI=0.10, 14 counted EN206 units with Blue Whale T2 active as external wake source: 616.043GWh gross, 18.522% wake loss and 462.923GWh net after the legacy non-wake stack.
- TI=0.06/0.14 gives 444.951/476.417GWh; T2 absent at TI=0.10 gives 466.970GWh.
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
