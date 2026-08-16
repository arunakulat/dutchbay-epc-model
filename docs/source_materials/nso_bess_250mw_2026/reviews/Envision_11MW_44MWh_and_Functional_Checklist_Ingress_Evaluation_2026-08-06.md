# Envision 11 MW / 44 MWh design and functional checklist ingress evaluation

- Date of evaluation: 6 August 2026
- Tender context: NSO `TR/REP&PM/ICB/2026/001/C`
- Evaluation status: documentary gap assessment, not a compliance certificate

## 1. Sources and evidence status

| Source | Source date | SHA-256 | Evidentiary role |
|---|---:|---|---|
| `oem/envision/Envision_Sri_Lanka_11MW_44MWh_Design_Calculation_V1.0_2026-08-05.pdf` | 5 August 2026, V1.0 | `0cf77ec5d7615c611e0a5cbbf7ab8c3f8a6a722e5b31e42a25fad27f88841e86` | Envision design and performance calculation for a named 11 MW / 44 MWh Sri Lanka project; tender number is not stated in the document |
| `oem/envision/compliance_evidence/Envision_Functional_Requirements_Checklist_2026-07-21.xlsx` | Workbook metadata: created and modified 21 July 2026 | `8236806c21f651fdf78591f9665cd68632e2f195e810f10d7d2f946325e0bd49` | Supplier compliance declaration against selected Annex A and Annex B clauses; not the official annex and not supported by embedded evidence links |

Both files were supplied for ingress on 6 August 2026. The PDF is marked confidential and
privileged. The workbook has no title page, tender identifier, author, signatory, revision,
approval state or source-document hash. Its embedded workbook path is
`C:\Users\Ziyin.you1\Desktop\`; this is provenance metadata only and does not establish the
author or approver.

The files are therefore retained as received OEM material. Neither is treated as a controlling
NSO tender document. The checklist does not cure the absence of the official 250 MW Annex A,
Annex B tender copy, addenda or clarification register.

## 2. Ingression and QA method

- PDF converted with repository MarkItDown 0.1.6 before interpretation.
- The PDF contains a usable embedded text layer; separate image OCR was not necessary.
- All 10 PDF pages were rendered at 150 dpi and visually checked against the extract.
- `qpdf --check` reported no syntax or stream-encoding errors.
- Workbook converted with MarkItDown 0.1.6 and independently imported with the bundled
  spreadsheet runtime.
- The workbook contains one worksheet, `Compliance Checklist`, with 59 populated rows in
  `A1:F59` and a residual styled blank cell at `A60`.
- The workbook has no formulas and the error scan found no formula-error values.
- The complete `A1:F60` sheet was rendered and visually checked. The header row is frozen;
  compliance cells contain `Yes,No,Partial` validation lists.
- The workbook's auto-filter covers only `A1:F46`, so it excludes the Annex B block in rows
  47-59. This is a source usability limitation; the received workbook has not been altered.

Searchable MarkItDown extracts are stored beside the sources. The received PDF and workbook
remain the authoritative bytes for what Envision supplied.

## 3. Relationship to the earlier Envision design

The 5 August document is a new configuration and is not a renamed duplicate of the 29 July
10 MW / 40 MWh design calculation. It must coexist with the earlier source until Envision or
the bidder formally identifies which configuration controls the proposal.

| Parameter | 29 July design | 5 August design | Evaluation |
|---|---:|---:|---|
| Named project | 10 MW / 40 MWh | 11 MW / 44 MWh | New nominal project basis |
| Proposed solution | 1 x ENS-D10E-20100-10100-00 plus 1 x ENS-D06G-24120-10100-000 | 2 x ENS-D06G-24120-10100-000 | Material topology change |
| Rated apparent power | 15.1 MVA | 20.1 MVA | +5.0 MVA |
| Required active power at POC | 10 MW | 11 MW | +1 MW |
| Usable active power at POC | 14 MW | 18.7 MW | +4.7 MW |
| Installed capacity | 44.2 MWh | 48.2 MWh | +4.0 MWh |
| Usable capacity at POC, BoL | 40.2 MWh | 43.9 MWh | +3.7 MWh, but 0.1 MWh below the new 44 MWh label |
| BoL duration at required power | 4.02 h | 3.9909 h | New document does not demonstrate a full 44 MWh at 11 MW from the rounded offered value |
| Year-15 usable capacity including auxiliaries | 30.8 MWh | 33.6 MWh | Both report 76.7% SoH |
| BoL RTE including auxiliaries | 86.3% | 86.9% | +0.6 percentage points |
| Year-15 RTE including auxiliaries | 84.9% | 85.0% | Reaches the tender threshold only at displayed precision; no margin |
| BoL/year-15 RTE excluding auxiliaries | 89.0% / 88.4% | 89.9% / 88.8% | Higher new declared curve |
| BoL/year-15 DC-DC RTE | 94.4% / 93.7% | 94.8% / 93.6% | New curve starts higher and ends slightly lower |
| Auxiliary assumption | 0.16 MW x 4.02 h | 0.17 MW x 4 h | 0.6432 MWh versus 0.68 MWh |
| MV cable efficiency | 99.5% | 99.6% | +0.1 percentage points |
| PCC reactive capability | +/-3.29 Mvar at 10 MW | +/-3.62 Mvar at 11 MW | Both correspond to approximately 0.95 power factor |
| Cumulative 15-year export | 210,566 MWh | 229,924 MWh | +19,358 MWh |

The 11 MW / 44 MWh label may represent an oversized tender configuration, but the document
does not state the NSO tender number or explicitly explain the relationship to the tender's
10 MW / 40 MWh unit. That relationship remains an inference and requires confirmation.

## 4. Complete 5 August design data

### 4.1 Project and topology

| Field | Received value |
|---|---|
| Project name | Sri Lanka 11 MW / 44 MWh BESS project |
| Environmental conditions | -30 degrees C to +45 degrees C |
| Auxiliary-loss calculation temperature | 35 degrees C |
| POC voltage | 33 kV |
| Nominal POC power | 11 MW |
| Offered usable energy at BoL | 43.9 MWh |
| Cycles per day | 1.1 |
| Proposed solution | 2 x `ENS-D06G-24120-10100-000` |
| Overall rated power | 20.1 MVA |
| Usable active power at POC | 18.7 MW |
| Installed capacity | 48.2 MWh |
| DC container configuration | 6,030 kWh; 6 racks connected in parallel per container |
| Nameplate capacity per solution set | 24.121 MWh; 4 containers per AC twin-skid |
| Step-up transformer | 10.1 MVA, 0.69/33 kV, three winding |
| PCS | 2.52 MVA each |
| AC unit | 10.08 MW; 4 PCS and 1 transformer |

Two stated 10.1 MVA transformers sum to 20.2 MVA while the overall solution table reports
20.1 MVA. Two stated 24.121 MWh sets sum to 48.242 MWh while the overall table reports
48.2 MWh. The energy difference is consistent with one-decimal rounding; the apparent-power
difference should still be reconciled in the final equipment schedule.

### 4.2 Annual performance curve, transcribed losslessly

| Year | Usable MWh at 33 kV incl. aux | Usable MWh at 33 kV excl. aux | SoH incl. aux | SoH excl. aux | RTE incl. aux | RTE excl. aux | DC usable discharge MWh | DC-DC RTE | Export in previous year MWh | Cumulative export MWh |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BoL | 43.9 | 44.6 | 100% | 100% | 86.9% | 89.9% | 45.8 | 94.8% | - | - |
| 1 | 43.1 | 43.9 | 98.2% | 98.3% | 86.6% | 89.8% | 45.0 | 94.7% | 17,465 | 17,465 |
| 2 | 42.0 | 42.8 | 95.7% | 95.9% | 86.4% | 89.7% | 43.9 | 94.6% | 17,102 | 34,568 |
| 3 | 41.1 | 41.9 | 93.7% | 93.8% | 86.2% | 89.6% | 43.0 | 94.5% | 16,703 | 51,271 |
| 4 | 40.3 | 41.1 | 91.8% | 92.0% | 86.1% | 89.5% | 42.1 | 94.4% | 16,354 | 67,626 |
| 5 | 39.5 | 40.3 | 90.0% | 90.3% | 86.0% | 89.5% | 41.3 | 94.3% | 16,036 | 83,662 |
| 6 | 38.8 | 39.6 | 88.4% | 88.7% | 85.8% | 89.4% | 40.6 | 94.2% | 15,740 | 99,403 |
| 7 | 38.1 | 38.9 | 86.9% | 87.2% | 85.7% | 89.3% | 39.9 | 94.1% | 15,462 | 114,865 |
| 8 | 37.5 | 38.3 | 85.4% | 85.7% | 85.6% | 89.2% | 39.2 | 94.1% | 15,198 | 130,064 |
| 9 | 36.9 | 37.6 | 84.0% | 84.3% | 85.5% | 89.2% | 38.6 | 94.0% | 14,946 | 145,010 |
| 10 | 36.3 | 37.1 | 82.7% | 83.0% | 85.4% | 89.1% | 38.0 | 93.9% | 14,705 | 159,716 |
| 11 | 35.7 | 36.5 | 81.4% | 81.7% | 85.3% | 89.1% | 37.4 | 93.9% | 14,473 | 174,190 |
| 12 | 35.2 | 35.9 | 80.2% | 80.5% | 85.2% | 89.0% | 36.9 | 93.8% | 14,250 | 188,440 |
| 13 | 34.6 | 35.4 | 79.0% | 79.3% | 85.1% | 88.9% | 36.3 | 93.8% | 14,034 | 202,475 |
| 14 | 34.1 | 34.9 | 77.8% | 78.2% | 85.0% | 88.9% | 35.8 | 93.7% | 13,825 | 216,300 |
| 15 | 33.6 | 34.4 | 76.7% | 77.0% | 85.0% | 88.8% | 35.3 | 93.6% | 13,623 | 229,924 |

The source cumulative-export column sometimes differs by 1 MWh from adding the displayed,
rounded annual-export values. The source figures are retained rather than recalculated.

The source states that performance may vary by 1-2% with actual site conditions, including
ambient-temperature variation of +/-5 degrees C and external PT/CT metering accuracy. It also
states that an electricity-meter error of about 0.5% should cause the RTE to be deemed compliant
within that margin. This is an OEM qualification, not evidence that NSO has accepted such a
compliance tolerance.

### 4.3 Loss and impedance assumptions

| Item | Value | Scope/remark |
|---|---:|---|
| Calendar degradation | 97% | Cell manufacture to SAT; assumes six months FAT-to-SAT |
| Usable DC capacity ratio | 98% | Cell efficiency and depth-of-discharge limits |
| LV DC cable efficiency | 99.9% | Aluminium, 30 m, BoP supply |
| PCS efficiency | 98.5% | At rated power, Envision supply |
| LV/MV transformer efficiency | 99.2% | EU Ecodesign, Envision supply |
| MV/HV transformer efficiency | 100% | Assumed, BoP supply |
| MV cable efficiency | 99.6% | Assumed, BoP supply |
| HV cable efficiency | 100% | Assumed, BoP supply |
| Auxiliary consumption at BoL | 0.17 MW x 4 h | Cannot be guaranteed separately |
| LV/MV transformer impedance | 9% | EU Ecodesign |
| MV/HV transformer impedance | 16% | Assumed, BoP supply |

### 4.4 PCC and PCS requirements

| Mode | P at PCC MW | S at PCC MVA | Q at PCC Mvar | PF at PCC | P at PCS MW | S at PCS MVA | Q at PCS Mvar | PF at PCS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Discharge, overexcitation | 11 | 11.58 | 3.62 | 0.95 | 11.37 | 12.37 | 4.87 | 0.92 |
| Discharge, underexcitation | 11 | 11.58 | -3.62 | -0.95 | 11.36 | 11.61 | -2.37 | -0.98 |
| Charge, overexcitation | -11 | 11.58 | 3.62 | 0.95 | -10.64 | 11.68 | 4.82 | 0.91 |
| Charge, underexcitation | -11 | 11.58 | -3.62 | -0.95 | -10.64 | 10.91 | -2.42 | -0.98 |

The source says these power-flow values are valid only when PCS terminal voltage is within
0.9-1.1 p.u.

## 5. Functional checklist evaluation

The workbook contains 56 substantive compliance rows:

| Section | Yes | No | Partial | Total |
|---|---:|---:|---:|---:|
| Annex A-labelled rows | 37 | 6 | 1 | 44 |
| Annex B-labelled rows | 11 | 1 | 0 | 12 |
| Total | 48 | 7 | 1 | 56 |

These are supplier declarations, not verified compliance results. The workbook contains no
evidence-reference column and no attached certificates, models or test reports.

### 5.1 Declared failures and partial compliance

| Clause | Requirement | Limit | Declaration | Supplier remark/evaluation |
|---|---|---|---|---|
| A.05.03 | Synthetic inertia time constant | >=20 s | No | Supplier states <=12 s |
| A.05.04 | Frequency ride-through configurable bands | At least 4 bands, 45-55 Hz | No | No supporting remark |
| A.05.04 | 52-53 Hz operation | 1 minute | No | Supplier states 1 minute cannot be met |
| A.05.04 | 45-47 Hz operation | 10 seconds | No | Supplier states 10 seconds cannot be met |
| A.05.07 | AVR response to 5% voltage step | <50 ms, overshoot <=30% | Partial | Supplier says test requirements are unclear |
| A.05.09 | Continuous operation through repeated disturbances | Up to 6 disturbances in 5 minutes | No | Supplier test report contains only 2 faults; report not supplied |
| A.05.10 | Active-power recovery after fault clearance | >=95% within 100 ms | No | Supplier states recovery exceeds 100 ms |
| Annex B 3.17.2.5 II | Harmonic apportionment factor | Default 0.25 unless connection agreement states otherwise | No | No supporting remark |

### 5.2 Material qualifications hidden behind `Yes`

- A.05.02 declares the 120% for two minutes and 150% for ten seconds overload requirements
  compliant only below 35 degrees C. That qualification conflicts with the PDF's named +45
  degrees C environmental envelope and does not demonstrate hot-site overload performance.
- Annex B 3.6.3 and 3.6.4 declare waveform-distortion and flicker compliance but expressly say
  that certificates cannot be provided.
- A.05 declares grid-forming capability `Yes`, but supplies no signed control description,
  model, test report or traceable evidence.
- A.05.23 declares PSS/E v35.x, PSCAD v5.x and PowerFactory model availability `Yes`, but no
  model artifacts, guides, parameter sets or validation reports accompanied the workbook.
- A.05.24 declares a grid-connection test scope including harmonics, FRT, frequency, reactive
  power, voltage, EMI and noise `Yes`, while the same sheet admits that the available test report
  contains only two faults. The underlying report was not supplied.

### 5.3 Checklist requirements captured for future reconciliation

The raw searchable extract retains all 56 rows. Material requirements newly exposed by the
checklist include:

- 33 kV PPC control and monitoring point.
- 10-40 degrees C continuous operation and 95% 24-hour relative humidity.
- Three NSO user-access levels.
- 33/36/30 kV nominal/maximum/minimum voltage and 50/50.5/49.5 Hz continuous frequency.
- 2.5 Hz/s RoCoF over 500 ms and 4.0 Hz/s withstand over 250 ms.
- 170 kV peak basic-insulation level and 70 kV peak switching/power-frequency withstand.
- 110% continuous, 120% for two minutes and 150% for ten seconds PCS current capability.
- Frequency droop configurable from 1-9%, default 4%; synthetic inertia >=20 s and activation
  <=5 ms; primary response <0.2 s within 2% deviation.
- Voltage droop configurable from 1-6%; at least 10 voltage bands from 0-1.3 p.u.; zero-voltage
  operation for 0.2 s; >1.30 p.u. operation for 0.02 s.
- Fault reactive current of 2% per 1% voltage drop, configurable 1-6%; 20-40 ms activation and
  full delivery within 70 ms.
- Four-quadrant reactive capability of +/-0.3 p.u.; voltage, droop, reactive-power and
  power-factor control modes.
- Setpoint commencement <50 ms, achievement <300 ms, overshoot <=10% and settling <400 ms
  to 1%.
- Oscillation damping over 0.2-2.5 Hz for 10-30% Pn variation; AGC range -100% to +100% Pn.
- Minimum SCR 1.2 for grid-following and 1.0 for grid-forming.
- Safe state with no automatic restart after communication loss.
- IEC 60870-5-104/101 communications.
- PSS/E v35.x, PSCAD v5.x and PowerFactory model formats.
- Annex B references to IEC 61000-3-6, IEC 61000-3-7, IEEE 519-1992, LFSM-U at 49.8 Hz,
  LFSM-O at 50.1 Hz, 2-5 s LFSM step response and 20-30 s settling.

Because the workbook is not the official annex and has no document-control fields, each of
these values must be reconciled against the issued Annex A/B before it is represented as a
binding tender requirement.

## 6. Compliance and model implications

### 6.1 Critical proposal gaps

1. **Energy at the named rating:** 43.9 MWh is 0.1 MWh, or about 0.23%, below 44 MWh and
   corresponds to about 3.9909 hours at 11 MW. The final guarantee must state the required
   metering point, auxiliary treatment, temperature and tolerances.
2. **RTE headroom:** the displayed auxiliary-inclusive RTE is exactly 85.0% in years 14 and
   15. A rounded threshold value, combined with the source's 1-2% site variation, is not robust
   evidence of monthly 85% compliance.
3. **Temperature basis:** the design names -30 to +45 degrees C, but auxiliaries are calculated
   at 35 degrees C, the workbook declares continuous operation only to 40 degrees C, and the
   120%/150% overload statements are qualified to below 35 degrees C.
4. **Grid-forming evidence:** `Yes` in a checklist does not demonstrate true voltage-source,
   voltage-controlled operation without fallback under normal and fault conditions.
5. **Known functional shortfalls:** the supplier itself declares failures in synthetic inertia,
   frequency ride-through, repeated-disturbance operation, active-power recovery and harmonic
   apportionment, plus partial AVR-step response.
6. **Missing evidence dossier:** declared model and testing capability is not accompanied by
   the executable models, model guides, certificates, type tests or validation reports.

### 6.2 What this ingress changes

- The earlier 84.9% year-15 RTE issue is improved numerically to a displayed 85.0%, but not
  closed because the new curve has no margin and remains qualified.
- The earlier absence of any GFM statement is improved to a supplier declaration of `Yes`, but
  not closed as evidence.
- The checklist exposes detailed claimed Annex A/B parameters and explicit supplier failures.
  It is valuable gap evidence but not a controlling annex.
- The new PDF explicitly names a +45 degrees C project envelope, but its underlying loss and
  overload bases do not demonstrate performance across that envelope.
- No parameter in these documents is wired into the executable DutchBay financial or grid
  model by this corpus-only ingress.

## 7. Required closure package

Before any final technical-compliance claim, obtain:

1. The official issued Annex A and Annex B, all addenda and the clarification register.
2. A signed, revision-controlled compliance matrix naming the tender and exact 11 MW / 44 MWh
   configuration, with one evidence reference for every row.
3. A guaranteed 11 MW and 44 MWh at the contractual metering point, including auxiliaries and
   at the required ambient temperature, with an unrounded RTE guarantee and contractual test
   tolerance.
4. A reconciliation of 20.1/20.2 MVA and the final equipment count, SLD and power-limiting
   method for the tender's nominal 10 MW unit.
5. True-GFM control description plus executable PSS/E and PSCAD models, model guides,
   parameter sets and validation at the required SCR and disturbance cases.
6. A compliance recovery plan for the declared `No` and `Partial` items, including supplier
   ownership, design change, retest date and acceptance criterion.
7. Temperature-qualified overload, frequency-withstand, repeated-disturbance and active-power
   recovery reports.
8. Power-quality certificates/reports and a resolved harmonic-apportionment position.

## 8. Conclusion

The new material is decision-useful because it replaces ambiguity with explicit design data and
supplier-declared functional gaps. It does not establish a compliant offer. The 11 MW / 44 MWh
calculation is a distinct candidate configuration, while the workbook is an unsigned working
compliance declaration. Both should remain indexed as OEM evidence, with the official annexes,
configuration-specific guarantees and traceable model/test dossier still outstanding.
