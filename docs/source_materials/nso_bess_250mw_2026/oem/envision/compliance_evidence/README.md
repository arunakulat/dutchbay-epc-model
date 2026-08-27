# Envision OEM compliance evidence register

- Tender: `TR/REP&PM/ICB/2026/001/C` — 250 MW / 1000 MWh assembled from **10 MW / 40 MWh AC-capacity
  projects**, BOO, 15-year operational period (full title recovered from the 31 July 2026 EOI letters)
- Configurations: 10 MW / 40 MWh and later 11 MW / 44 MWh Envision design variants
- OEM: Envision Energy; BESS business now managed by **the battery affiliate** (group reorganisation letter, item 59.2)
- Bidder: a Sri Lankan listed-group company; EOI supply commitment given by **an affiliated
  supply entity** on the battery affiliate's letterhead; cell certificates name the affiliate's
  cell manufacturing entity
- Last updated: **27 August 2026**, after ingress of **Addendum No. 01, Annex A and the 76-item
  clarification register**
  (see [`../../../reviews/NSO250MW_Addendum01_AnnexA_Clarifications_Ingress_Evaluation_2026-08-27.md`](../../../reviews/NSO250MW_Addendum01_AnnexA_Clarifications_Ingress_Evaluation_2026-08-27.md));
  previously 21 August 2026 after the checklist dossier
  (see [`../../../reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md`](../../../reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md))
- **Closing date: 4 September 2026, 10.00 hrs** (Addendum 01 item 01). Requests for clarification
  closed 25 August 2026

This register distinguishes evidence actually received from evidence required by the tender.
An item is not complete until its source artifact is committed beside this register and its
checksum is added to the package manifest.

## Evidence received

| Evidence | Status | Location | Limitation |
|---|---|---|---|
| Design calculation V1.0, 29 July 2026 | Received | `../Envision_10MW_40MWh_Design_Calculation_V1.0_2026-07-29.pdf` | Design calculation only; not a complete compliance package |
| Design calculation V1.0, 5 August 2026 | Received | `../Envision_Sri_Lanka_11MW_44MWh_Design_Calculation_V1.0_2026-08-05.pdf` | Distinct 11 MW / 44 MWh candidate; no tender number; 43.9 MWh offered at BoL; auxiliary assumptions remain at 35 degrees C |
| Functional-requirements checklist, metadata date 21 July 2026 | Received | `Envision_Functional_Requirements_Checklist_2026-07-21.xlsx` | Unsigned working declaration; 48 Yes, 7 No and 1 Partial; no evidence references or attached model/test/certificate dossier; not the official Annex A/B |
| Redacted ENPCS01 grid-code parameters | Received previously | `../../../../../../tests/fixtures/grid/envision_enpcs01_gridcode.yaml` | Reference constants only; grid-following topology; proprietary binaries absent |
| **NSO 250 MW checklist dossier, 21 August 2026** | **Received; held outside the repository** | manifest at `../../../source_packages/NSO250MW_checklist_2026-08-21.MANIFEST.sha256` | 72 files / 58 unique across checklist sections A-J. Binaries not committed: contains the independent test house and certification-body copyright, third-party letterheads, compiled model binaries and personal data. See `../../../source_packages/README.md` |
| Superseding 10 MW / 40 MWh design calculation, 5 August 2026 | Received (in the above package) | manifest entry `5c619a2c...` | **Silently revises the 29 July document while still labelled V1.0.** Container changed ENS-D10E to ENS-D10G; year-15 RTE incl. aux moved 84.9 % to 85.0 %, i.e. from below the floor to exactly on it; adds a 0.5 % meter-tolerance clause. Treat the 29 July file as superseded but retain both |
| Grid-forming and parallel-operation letters | Received (in the above package) | manifest entries, checklist items 37 and 39 | Signed Envision letters. Item 37 asserts full grid-forming voltage-source operation at all times; **contradicted** by the dual-mode language in the item 61 compliance list and by the grid-following EMT model actually supplied |
| PSS(R)E GFM model, Sri-Lanka dynamic record | Received (in the above package) | checklist item 48 | Executable DLLs, `ENVSG_PPC_2520_260416_LKA.dyr` (`ENGFM01` + `BNPPC_GFMV3`), manual V1.4a. Manual itself states EMT is the better tool for fault ride-through |
| PSCAD/EMTDC model | Received (in the above package) | checklist item 49 | **Grid-following variant.** Manual titled "GFL PCS"; model block labelled `GFL-PCS`; "represented with current source". Cannot demonstrate voltage-source fault behaviour |
| Standards certificates | **Received and committed** | `certificates/` — 14 files | Cell certificates are in **the affiliate's cell manufacturing entity** name. UL 1973 is **component recognition**, not system certification. Committed 27 Aug 2026 on the project owner's explicit authority, reversing the earlier manifest-only handling; see `../../../source_packages/README.md` |
| PSS(R)E and PSCAD model deliverables | **Received and committed** | `../dynamic_models/` — 11 files | `.dll`/`.obj`/`.lib` are compiled and their control law is not recoverable; `.dyr` and `.pscx` are text and are read by `scripts/analysis/extract_oem_dynamic_models.py`. Committed 27 Aug 2026 on the same authority, reversing the earlier publish-never handling |
| Fire-safety package | Received (in the above package) | checklist item 45 | Fire Protection System Specification V2.0 (header scopes **ENS-D10**, not the offered **ENS-D06G**); UL 9540A cell-level (2019) and module-level (2026) reports |
| the independent test house cell bankability study | Received (in the above package) | checklist item 47 | Genuine third-party study, Issue D Final, 28 Jan 2026, prepared **for the battery affiliate**. Contains the 45 degree C cycle-life finding at the heart of the augmentation question |
| Filled Volume 2 GTP | Received (in the above package) | checklist item 62 | Section 6 technical schedule, confirms the tender number. Unsigned; several rows mis-entered; no RTE, warranty, degradation or augmentation row |
| Grid Compliance List, 11 August 2026 | Received (in the above package) | checklist item 61 | 31-page clause-by-clause response to CEB Grid Connection Code (July 2024). Placeholder `Doc. No.: PMD - XXXXXXXX`, Rev. A, unsigned. Body never uses the term "grid-forming" |
| Supplier document checklist workbook | Received (in the above package) | `NSO_BESS_Supplier_Document_Checklist.xlsx` | Tracking sheet, 58 numbered rows: 41 Received, 14 Not Received, 3 blank. **Summary tab under-reports (38/52) because its COUNTIF range stops at row 65; items 50-53 are absent entirely** |

## Outstanding OEM evidence

Restated 21 August 2026 after the the bidder dossier. "Partially closed" means an artifact arrived but
does not discharge the requirement.

| Requirement | Status | Evidence still needed |
|---|---|---|
| **True grid-forming V/F operation** | **Requirement re-read 27 Aug; gap narrowed and relocated** | Annex A **A.05.17(i) requires** the BESS to "support both grid-following and grid-forming control modes, enabling online switching between the two", and **A.05.17(j)** requires GFL stable at **SCR >= 1.2** and **GFM stable at SCR >= 1.0**. The supplier's dual-mode language is therefore **compliant with the controlling annex**, not a deviation — the earlier instruction to delete it is withdrawn. Volume I §3(c) still prohibits *dropping* to current-controlled operation in normal or fault conditions, so the bid must state capability-for-both / operates-in-GFM / does-not-drop. The real gap is the **GFM fault demonstration at SCR 1.0**, which the supplied GFL EMT model cannot provide |
| PSS(R)E RMS model | **Closed** | Executable DLLs, Sri-Lanka `.dyr` and manual V1.4a received. Model validation report still desirable |
| PSCAD/EMTDC model | **Bid-stage risk reduced; post-award risk raised** | Annex A **A.05.23(d)** accepts, as the bid-stage minimum, initial **non-site-specific** models in **both** PSS(R)E and PSCAD formats **or** the SCR test results — and both models are held, so the stated rejection ground is clearable now. **A.05.23(e)** still requires the grid-forming demonstration in both tools, and Addendum items 06 and 12 move the Dynamic Model Tests to **within one month of ESA execution (14 Jan 2027)** with the **Performance Security forfeitable** if not delivered acceptably. The GFM EMT model is now a dated, security-backed obligation |
| SCR and phase-step validation | **Not required at bid stage; required post-award** | A.05.23(d) makes it the *alternative* to submitting both models (Addendum item 14 adds the same either/or to the Volume II Section 5 Compliance Schedule as item 12). Still required under A.05.23(e) for the post-award Dynamic Model Tests: V/P/Q at SCR 1, 3, 5, 10 with X/R 5 and a +50 degree phase step. The tracking workbook remains missing items 50-53 in exactly this section |
| Standards compliance | **Partially closed** | 16 certificates/reports received. Still uncertified: IEC 62620, 62902, 62485-5, 62933-1, 62933-2-1, 62933-5-2, UL 9540, IEEE 1547-2018, IEEE 2800-2022, UL 1741-SB, IEC TS 62786-3. **IEEE 2800-2022 declined outright** on market-scope grounds although it is the transmission-level IBR standard for this tender's grid-forming requirement. Two remarks still say "Will finish before 2026" and need re-dating |
| **45 degree C performance** | **Still missing; aggravated again** | the independent test house confirms ~10,000 cycles to 70 % retention at 25 degrees C but only **~4,000 at 45 degrees C**, against a 15-year duty of ~6,022 EFC at 1.1 cycles/day. **Clarification 55(b)** now confirms that energy exchanged providing frequency response, synthetic inertia, oscillation damping and AGC is **not excluded from the 400 Full Equivalent Cycle allowance**, so ancillary-service duty consumes the same cycle budget. Need cell temperature under liquid cooling at 45 degrees C ambient, auxiliary load at 45 degrees C, resulting guaranteed RTE, 4 hours at rated output at site ambient, and cycle life at the resulting cell temperature |
| Capacity Maintenance Plan | **Partially closed** | BoL sizing and 15-year curves received; augmentation and replacement declared as "none needed" (checklist items 55 and 56, both status-blank). Still needed: substantiation of the no-augmentation claim against the 45 degree C cycle-life finding, and a genuine **decommissioning and recycling commitment** referencing Sri Lankan environmental regulation. The document filed at item 57 is a mechanical disassembly work instruction with no recycling content |
| Ride-through and controls | **Partially closed** | Grid compliance list and the `.dyr` protection envelope (47.5/51.5 Hz continuous, 46.9/52.1 Hz trip stages, LVRT/HVRT current-injection table) received. Project-specific RMS and EMT studies still required, and the compliance list defers repeatedly to a "Technical Specification of PCS-2520 and PPC document" that is **not in the package** |
| Single-line diagram and export limiter | **Partially closed** | Container layouts, 10,100 kVA transformer and 36 kV RMU datasheets received. Plant-level SLD, dynamic model data and metering are declined as BoP scope (items 43, 44, Section E), so **no party in the package owns grid-code compliance monitoring** |
| Equipment design life | **Partially closed** | 20-year non-battery letter received but self-certified; the checklist itself records "No certification to prove this but we provided a statement". 15-year battery life points to the bankability study, which is where the 45 degree C issue arises |
| Fire safety and protection | **Partially closed** | Specification plus UL 9540A cell- and module-level reports received. The module report states that **either a Unit level test or an Installation Level Large Scale Fire Test shall be conducted** — neither is supplied. Fire-protection coverage of the offered **ENS-D06G** container is unevidenced (the specification header scopes ENS-D10). PCS fault-contribution and withstand evidence still missing |
| Power-quality evidence | **Partially closed** | IEEE 519 and IEC 61000 certificate cover pages received. Harmonic apportionment factor 0.25 issue unresolved |
| **Qualification attribution** | **Largely relieved 27 Aug** | **Clarification 58(e)**: "The qualification should be satisfied based on the **manufacturer/component supplier's experience, and therefore need not be experience of the Project Proponent itself**." **58(c)** accepts a manufacturer declaration on official letterhead identifying product, installed quantity/capacity, project, location, commissioning date and manufacturer. **58(a)/(b)** set the threshold as **cumulative global installed/commissioned** volume — so the qualifying figure is the **20.65 GWh at COD**, not the 52.6 GWh contracted or 33.5 GWh shipped. Residual: which *group entity* holds it, given the EOI is signed by the affiliated supply entity and the certificates name the cell-manufacturing entity |
| **Manufacturer's Authorization Letter** | **New, open** | Checklist item 58 requires three signed EOI letters "& MAL Also (on Company letterhead)". Three EOI letters are present; **no MAL is in the package**, though item 58 is marked Received |
| **Standards compliance route** | **Route opened 27 Aug** | **Clarification 62**: where the proposed package is newly introduced and certifications are in progress, the bidder may submit **currently available valid certifications for the applicable cells, racks, major components and/or established product family**, plus **documentary evidence of the relationship and technical equivalence** to the proposed package, with certifications for the exact package before ESA signing. This is an evidence route for the 14 uncertified standards and for the UL 1973 component-vs-system point — **not a waiver**; the equivalence evidence must be written |
| **Annex A numeric parameters** | **New, open** | Not previously tracked because Annex A was not held. Unevidenced in the package: inertia time constant (**>= 20 s**) and activation (**<= 5 ms**) per A.05.02(d); PCS AC-side **110 % continuous / 120 % for >= 2 min / 150 % preferred** per A.05.02(a) (clarifications 59 and 64 both refuse relief); primary frequency response **< 0.2 s**, deviation **<= 2 %** per A.05.02(e); AGC **-100 % to +100 % Pn**, deviation **<= 2 % Pn**, AVC reactive **<= 2 % Pn** per A.05.17(h); POD over **0.2-2.5 Hz** limited to **10-30 % Pn** per A.05.17(d). Also: the supplied `.dyr` protection envelope (47.5/51.5 Hz continuous) is **narrower at both ends** than A.05.04's 47-52 Hz steady-state range, which clarification 29 confirms governs |
| **Reactive capability at declared capacity** | **New, open** | **Clarification 24** settles the requirement as **+/-0.3 x rated active power**, not a flat +/-3 Mvar. At a declared **11 MW** that is **+/-3.3 Mvar**; the 10 MW design calculation states +/-3.29 Mvar at the PCC. The 11 MW design calculation's reactive figure must be read directly before an 11 MW capacity is declared |
| **Offered PCS track record** | **New, open** | The 22 reference projects list ENPCS 2750, 3450, 3300 and 2500. The offered **ENPCS2520 appears in none of them.** Client-contact columns are empty for every PCS and PPC row |

## Important boundary

The repository's Python grid screens, generic RMS ride-through simulations, financial BESS
degradation model and redacted fixture are design-stage analytical aids. They are not substitutes
for the OEM-certified models, certificates, test reports or site-specific engineering package
required by the tender.

A supplier declaration is not evidence. Several checklist rows in the 21 August dossier are marked
"Received" against documents that do not answer the requirement they are filed under — item 38
(grid-forming modelling evidence) is a black-start feature description, item 57 (recycling
commitments) is a mechanical disassembly manual, and item 58 is missing its MAL component. The
register above tracks the requirement, not the checkbox.

The full lossless checklist extract and the source-by-source evaluation are respectively in
`../extracted/Envision_Functional_Requirements_Checklist_2026-07-21.markitdown.md` and
`../../../reviews/Envision_11MW_44MWh_and_Functional_Checklist_Ingress_Evaluation_2026-08-06.md`.

The 21 August 2026 dossier evaluation, covering all 58 unique files in that package, is in
`../../../reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md`. Its source binaries
are held outside this repository; see `../../../source_packages/README.md` for the handling
classification and the local location.
