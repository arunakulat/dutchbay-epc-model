# NSO 250 MW checklist package — ingress evaluation

- Tender: `TR/REP&PM/ICB/2026/001/C`
- Package: the supplier checklist package (168,832,294 bytes)
- Received: 21 August 2026, via the project owner
- Contents: 72 files, **58 unique by SHA-256** (9 duplicate groups, 14 redundant copies)
- File dates: newest are the filled Volume 2 schedule and the tracking workbook at **17 August
  2026**; newest document *content* date is the 11 August 2026 grid-compliance list
- **Submission deadline extended to 2 September 2026** (project owner, 21 August 2026). All package
  material is therefore **inside** the bid window, and **9 working days remain** — this review is a
  pre-submission punch list, not a post-mortem
- Extraction: MarkItDown (GWTF R26) for 47 unique convertible files; `pdftoppm` + `tesseract`
  OCR for 7 image-only PDFs; native OOXML extraction for the one `.docx`

This is **derived analysis**, not a controlling tender or OEM document. Where this review
conflicts with a source file, the source file governs.

> **Redacted public version.** This repository is public. On the project owner's direction
> (22 August 2026) this copy carries the full engineering findings but redacts commercial
> identities that the repository is not authorised to publish: the bidder, the OEM's battery
> affiliate and its cell-manufacturing and supply entities, the independent test house that
> authored the cell bankability study, the third-party operators whose reference letters appear
> in the package, the overseas system operator, and all named individuals, certificate numbers
> and confidential report references. Verbatim quotation from confidential *supplier* documents
> has been replaced by paraphrase; quotations from the RFP, a public procurement document, are
> retained. Public **standard** designations (UL 9540A, UL 1973, IEC and IEEE numbers) are
> retained because removing them would destroy the engineering content. No finding, figure or
> conclusion has been softened or withdrawn. The unredacted copy is held privately.

---

## 1. What the package is

This is the **supplier evidence dossier** assembled against the NSO 250 MW / 1000 MWh standalone
BESS tender, organised into the ten checklist sections A–J plus the tracking workbook
`NSO_BESS_Supplier_Document_Checklist.xlsx`.

It substantially answers the "Outstanding OEM evidence" table in
`oem/envision/compliance_evidence/README.md`, which as of 6 August 2026 recorded that no
certificates, type-test reports, grid-forming models, PSCAD/EMTDC model, executable PSS(R)E model,
model guides, fire-safety package or capacity-maintenance plan had been supplied. **Most of those
artifacts are now present.** The material questions have moved from *absence of evidence* to
*consistency and sufficiency of the evidence supplied*.

### 1.1 Commercial structure — newly established by this package

The tender's full title is recovered verbatim from the EOI letters (item 58):

> "REQUEST FOR PROPOSALS FOR THE ESTABLISHMENT OF 250 MW / 1000 MWh STANDALONE BATTERY ENERGY
> STORAGE SYSTEM **FROM 10 MW / 40 MWh AC CAPACITY PROJECTS** ON BUILD, OWN AND OPERATE BASIS
> WITH 15 YEAR OPERATIONAL PERIOD"

This resolves a standing ambiguity in the corpus: the 250 MW / 1000 MWh programme is procured as
**25 modular 10 MW / 40 MWh AC-capacity projects**, which is why the OEM design calculations are
sized at 10 MW / 40 MWh and 11 MW / 44 MWh (the latter being the 10 MW + 10 % export-limit case
referenced at checklist item 42). Bids are unit-scale, not programme-scale.

The contracting chain is:

| Role | Entity |
|---|---|
| Bidder / project proponent | A Sri Lankan listed-group company |
| Equipment supplier (EOI signatory) | **an affiliated supply entity**, on the battery affiliate's letterhead |
| Track record, letters, design calcs, grid compliance | **Envision Energy Co., Ltd / Envision Energy International Ltd** |
| Cell manufacturer on certificates | **the affiliate's cell manufacturing entity** |

Item 59.2, *Notice on Optimization of BESS Business Operations*, is the explanatory instrument:
Envision Group has moved the BESS Business to be **managed by a group battery affiliate going forward**. The letter
asserts no impact on existing contract fulfilment, unchanged after-sales interfaces, and names a
transition contact.

---

## 2. Findings

Ordered by materiality to tender compliance and bankability.

### F-1 (Critical) — Grid-forming: the letter, the compliance list and the EMT model do not agree

The NSO round makes grid-forming mandatory. The package contains **three mutually inconsistent
characterisations of the same converter**:

| Source | Characterisation |
|---|---|
| Item 37 — *Letter Confirming Grid-Forming Capability of ENPCS2520* | Asserts **full grid-forming (voltage-sourced, voltage-controlled) operation under all operating conditions**, including during grid faults and transient disturbances |
| Item 61 — *Grid Compliance List* (11 Aug 2026) | Describes the PCS as providing **both GFM and GFL modes** with **seamless transition between them** (clauses 3.17.4, 3.17.4.4) |
| Item 49 — PSCAD/EMTDC model actually supplied | Manual titled for the **GFL** PCS variant (V4.1b1); model page block labelled `GFL-PCS`; described as operating in active/reactive power control mode responding to external PPC or local commands, and represented as a **current source** |

A converter that *transitions* between grid-following and grid-forming is not voltage-source
under all operating conditions, and a **current-source** EMT model cannot demonstrate
voltage-source behaviour under fault.

This matters more than a labelling quibble because the PSS(R)E GFM manual itself records that
platform limitations make an EMT tool such as PSCAD the better recommendation for transient
studies including fault ride-through.

So the RMS model is grid-forming but is expressly not the right tool for fault studies, while the
EMT model that *is* the right tool is the grid-following variant. **No supplied artifact
demonstrates grid-forming fault behaviour.** The PSS(R)E side does ship a Sri-Lanka-specific
dynamic record (`ENVSG_PPC_2520_260416_LKA.dyr`, model `ENGFM01` + `BNPPC_GFMV3`), so the RMS GFM
path is real; the EMT gap is specific.

This also reconciles against the repository's pre-existing redacted fixture
`tests/fixtures/grid/envision_enpcs01_gridcode.yaml`, which identifies the referenced PCS as
**grid-following** — a characterisation the new compliance list now partially corroborates
(dual-mode) and the standalone letter contradicts (always-GFM).

**Against the RFP text this is not a labelling inconsistency but a declared non-compliance.**
RFP Volume I §3(c) requires a "full grid-forming-capable inverter (voltage-sourced — voltage-
controlled operation) irrespective of other generation in the grid", and states that it

> "should **NOT change the control mode to current-controlled (grid-following) during normal
> operation or under any network fault conditions**."

The item 61 compliance list advertises "seamless GFL/GFM transition" as a *capability*, at clauses
3.17.4 and 3.17.4.4, and offers it as the basis for meeting converter operational robustness. That
is the precise behaviour the RFP prohibits. The EMT model supplied is the grid-following variant of
the same converter.

Volume I §3.1(p) further requires PSS(R)E **and** PSCAD/EMTDC models demonstrating V/P/Q response
and a ±50° phase step at **SCR 1, 3, 5 and 10 (X/R 5)**, with failure a stated ground for
**technical rejection**. The PSCAD half of that requirement is presently satisfied only by a
grid-following model, and no SCR sweep or phase-step result is in the package.

**Required to close:** a grid-forming PSCAD/EMTDC model (or written confirmation that the GFL model
was supplied in error and the GFM EMT model follows), V/F fault-response evidence, the SCR 1/3/5/10
and ±50° phase-step validation outstanding since 31 July, and a written retraction or
reconciliation of the "seamless GFL/GFM transition" language against §3(c).

### F-2 (Critical) — The 10 MW / 40 MWh design calculation was silently revised, and the revision is what makes year-15 RTE pass

The package's `54.1 Sri Lanka 10MW_40MWh.pdf` (SHA-256 `5c619a2c…`) is **not** the repository's
`Envision_10MW_40MWh_Design_Calculation_V1.0_2026-07-29.pdf` (SHA-256 `7281d964…`). It is a later
document dated **05/08/2026** that still carries **version "V1.0"** — no revision bump, no change
record. Diffed content:

| Item | 29 Jul 2026 | 05 Aug 2026 | Effect |
|---|---|---|---|
| Proposed DC container | ENS-**D10E**-20100-10100-00 | ENS-**D10G**-20100-10100-000 | hardware generation change |
| RTE incl. aux, BoL | 86.3 % | 86.8 % | +0.5 pp |
| RTE excl. aux, BoL | 89.0 % | 89.6 % | +0.6 pp |
| **RTE incl. aux, year 15** | **84.9 %** | **85.0 %** | **below floor → exactly at floor** |
| DC-DC RTE, BoL | 94.4 % | 94.8 % | +0.4 pp |
| MV cable efficiency assumption | 99.5 % | 99.6 % | assumption relaxed |
| 15-yr cumulative export | 210,566 MWh | 210,777 MWh | +211 MWh |
| Meter-tolerance clause | absent | **added** | see below |

The tender's round-trip efficiency floor is a **minimum AC-to-AC RTE of 85 %, assessed monthly**,
with liquidated damages of **150 % of the peak-time 33 kV GP tariff per unit** when it is missed.
The superseded version **breached it at year 15**; the revision lands **exactly on it**.

The sequence matters. The project owner's own gap review of 30 July 2026 flagged, as a top must-fix
item, "RtE incl-aux 84.9 % < 85 % floor yr15". The revision dated **5 August** closes exactly that
gap — by changing the container generation, relaxing one loss assumption by 0.1 pp, and adding a
0.5 % meter-tolerance clause. The correction is responsive rather than independent, and it produces
**zero headroom against a monthly-assessed LD**. Part of the improvement is a genuine hardware change
(D10E → D10G), but part is an assumption tweak (MV cable 99.5 → 99.6 %), and the same revision
inserts a new measurement-tolerance escape clause: where RTE is measured with an electricity
meter, a meter error of about 0.5 % is assumed and the RTE is deemed compliant within that margin.

Stacked on the pre-existing ±1–2 % variation and ±5 °C deviation caveat that both versions carry, a
guarantee that sits **exactly on** the floor with a **0.5 % declared meter tolerance** and a
**1–2 % declared modelling tolerance** is not enforceable at the floor. For a lender this is a
zero-headroom performance covenant.

The 11 MW / 44 MWh variant is byte-identical to the copy already in the corpus (SHA-256
`0cf77ec5…`) and is unaffected; it carries more headroom (BoL 86.9 %, year 15 85.0 %).

### F-3 (Critical) — The vendor's own third-party bankability study contradicts the "no augmentation" declaration at tropical temperature

the cell bankability report is a genuine **independent test house** *Technical
Advisory Report — Bankability Study for Battery Energy Storage Product*, prepared **for the battery affiliate**,
Issue D, Final, 28 January 2026. Section 3.2.3:

- At **25 °C**, 0.25P charge/discharge: ~**10,000 cycles** to 70 % capacity retention — the test house confirms
  this "aligns with its specific claim".
- At **45 °C**, 0.25P: ~**4,000 cycles** to 70 % capacity retention — a **60 % reduction**.
- The 20-year / 70 %-retention simulation the test house endorses is qualified to **25 °C, ≤50 % SOC, one cycle
  per day** (§3.2.5).

Against the tender duty:

- Design duty is **1.1 cycles/day × 365 × 15 years ≈ 6,022 EFC**. This is not merely a design
  assumption: the RFP contracts for **400 full cycles per year with a floor of 20 cycles per
  month**, i.e. **~6,000 cycles over the 15-year term** as a *minimum obligation*.
- RFP Volume I §3.1(k) separately requires demonstration of **4 hours at rated output at site
  ambient** — the 45 °C case that is missing.
- The GTP declares battery and PCS operating range to **45 °C** (rows A.25, B.17); the design
  calculations state site conditions to **+45 °C** but compute auxiliary losses at **35 °C**.
- Checklist items 55 and 56 declare "**No Augmentation needed during lifetime**" and "**No
  replacement needed during lifetime**".

At the 45 °C figure in the affiliate's own independently reviewed data, the cell reaches the 70 % threshold at roughly
**4,000 cycles — about 2,000 short of the ~6,000 cycles the ESA contracts for**. The
no-augmentation claim is therefore supportable only near 25 °C cell temperature.

Note this is a *different* test from the tender's degradation floor, which the design passes
comfortably: the RFP requires ≥ **68.0 % at year 15**, and the design curves show **76.7 %** SoH.
The exposure is not the declared degradation curve — it is whether that curve holds at tropical
cell temperature, and whether the throughput obligation can be met without augmentation if it does
not.

**Fair caveat, stated explicitly:** the system is liquid-cooled (GTP A.23), so cell temperature is
not ambient temperature, and the 45 °C figure is an *ambient-soak* cycle-life datapoint rather than
a prediction of this system's cell temperature in service. That is precisely the problem — the
package supplies **no thermal model, no cell-temperature substantiation at 45 °C ambient, and no
auxiliary-load figure above 35 °C**. The cooling-energy gap and the cycle-life gap compound: the
same missing 45 °C thermal case would determine both the auxiliary draw (which reduces RTE) and the
cell temperature (which sets cycle life). Note also the test house's own recommendation that the affiliate "continuously
monitors its battery charge and discharge test data and updates its simulation curve to achieve a
more accurate cycle life."

This is the single most consequential open item for a 15-year BOO structure, and it is evidenced by
the supplier's own independent report rather than by inference.

### F-4 (High) — The fire-safety chain stops at module level, and the report says so itself

- `2.1 (UL 9540A-2019)-CELL-…` — cell level.
- the module-level UL 9540A-2026 test report — module level, 54 pp,
  issued 25 June 2026.

The module-level report's own conclusion is that cell-to-cell thermal runaway and propagation
occurred during the test; runaway was contained by
the module design, but cell vent gas was determined to be flammable at cell level. The report then
states that a BESS meeting any of the criteria at ANSI/CAN/UL 9540A:2026 (sixth edition) clause
9.1.1(a)-(e) requires a **unit-level test**, and that any BESS not meeting clause 9.1.1 instead
requires the **installation-level large-scale fire test**.

Under either branch a further test is mandatory, and **neither is in the package**. Recorded test
results: peak HRR 46.28 kW, peak SRR 0.5457 m²/s, TSR 29.98 m², total hydrocarbons 432.6 L, module
weight loss 1.8 kg, no flaming observed.

Separately, the *Fire Protection System Specification* (V2.0, 21 May 2026) is titled for
**ENS-D10** in its header, while the offered configurations use **ENS-D06G** containers (11 MW /
44 MWh: 2 × ENS-D06G; revised 10 MW: 1 × ENS-D10G + 1 × ENS-D06G). Fire-protection coverage of the
**D06G** variant is not evidenced.

### F-5 (High) — Item 57 does not answer the requirement it is filed against

Checklist item 57 requires "End-of-life decommissioning and battery **recycling commitments** (Sri
Lanka environmental regulations)". The document supplied is a BESS dismantling technical description — a **mechanical disassembly
work instruction** (special tool list, cable disconnection,
grounding removal, pipeline removal, lifting procedure).

A keyword sweep of the full extract returns **zero** occurrences of recycling, disposal, waste,
take-back, second-life, or Sri Lanka environmental regulation. The single “environmental” hit refers to
removal of the environmental-control pipeline, i.e. the cooling circuit. Item 57's status cell is
**blank** in the tracking workbook, consistent with it not having been assessed.

### F-6 (High) — Item 38 is filed as grid-forming modelling evidence but is a black-start feature description

Checklist item 38 requires "Supporting documentary and **modelling evidence** of grid-forming
operation" and is marked **Received**. The file is named *BESS Plant Grid Forming Technical
Solution (for reference)*, but its own title page identifies it as a **BESS plant black-start technical
solution (V1.0)**.

Its content is a PPC/SCADA functional description — topology monitoring, anti-misoperation
interlocks, GNSS-synchronised zero-voltage ramp-up, off-grid operation, SOC balancing, load
management, resynchronisation. It is a credible black-start capability write-up and useful for grid
code clause 3.17.7, but it contains **no simulation results, no V/F characteristic, no fault
response and no SCR sweep**. It is not modelling evidence, and it is marked "for reference".

### F-7 (Medium) — The offered PCS model has no track record in the submitted reference list

The supplier-experience workbook lists 22 PCS reference projects using **ENPCS 2750, 3450, 3300 and
2500**. The model offered for Sri Lanka is **ENPCS2520**, which appears **nowhere** in the reference
list. The battery-side list is strong (24 projects across Europe, Asia, Africa and the Middle East,
including several utility-scale references above 600 MWh).

Two further defects in the same workbook: the "Client Name & Address (**Including Contact No**)"
column is **empty for every PCS and PPC row**, and no contact number is given anywhere, though the
RFP form requests it. The workbook is also self-labelled "(part)".

### F-8 (Medium) — Qualification evidence and supply commitment sit in different corporate names

Clause 2.7.3 qualification rests on Envision Energy's letter (18.7 GW / 52.6 GWh disclosed track
record; 33.5 GWh shipped; 20.65 GWh at COD; "full-stack" in-house battery + PCS + PPC). But:

- the **EOI** — the actual commitment to supply — is signed by **an affiliated supply
  entity** on the battery affiliate's letterhead (signed 31 July 2026);
- the **cell certificates** (IEC 62619 CB and UL 1973) name **the affiliate's cell manufacturing
  entity** as applicant, manufacturer and factory;
- the **independent bankability study** was commissioned by and prepared for **the battery affiliate**.

Whether the RFP accepts intra-group attribution of Envision's track record to the affiliated supply
entity is a qualification question for the bidder's counsel, not a technical one — but it should be
answered explicitly rather than left implicit in the group-reorganisation letter.

Related: checklist item 58 requires three signed EOI letters "**& MAL Also (on Company
letterhead)**". Three EOI letters are present (BESS; PCS & Transformers; SCADA/PPC & EMS). **No
Manufacturer's Authorization Letter is in the package**, though item 58 is marked Received.

### F-9 (Medium) — UL 1973 is component recognition, not system certification

The UL 1973 certificate is explicit: *"UL Recognized components are incomplete in certain
constructional features or restricted in performance capabilities and are intended for installation
in complete equipment submitted for investigation to the certification body"*, and *"does not provide authorization
to apply the UL Recognized Component Mark"*. It is cell-level (BBGA2 component category). The
system-level standard, **UL 9540**, is separately self-declared "**Partially comply / future**".
Cell-level recognition should not be presented as system certification.

### F-10 (Medium) — Fourteen standards remain uncertified, seven by policy rather than schedule

From the Standards Compliance List and the tracking workbook:

| Standard | Declared | Basis given |
|---|---|---|
| IEC 62620, IEC 62933-5-2 | not certified | "Will finish before 2026" (already elapsed) |
| IEC 62902 | not comply | ISO 7010 labelling offered instead |
| IEC 62485-5 | not comply | IEC 62619 / 61000-6-2/-6-4 / 62620 offered instead |
| IEC 62933-1 | comply, no certificate | "do not plan to certificate this standard" |
| IEC 62933-2-1 | not comply | framework standard; 62620 + 62933-5-2 offered instead |
| UL 9540 | partially comply, future | US-market standard; IEC 62619 offered instead |
| IEEE 1547-2018 | partially | only US-version products tested |
| IEEE 2800-2022 | **No** | "US region-specific… not required for other markets" |
| UL 1741-SB | **No** | US-only; EN 50549-2 / G99 offered instead |
| IEC TS 62786-3 | n/a | string-PCS standard; centralised PCS offered |
| SL Grid Connection Code confirmation (item 36) | Not Received | *no remark given* |

The "Will finish before 2026" remarks are **stale** — the date has passed — and should be re-dated.
The IEEE 2800 refusal is the substantive one: it is the transmission-level IBR interconnection
standard whose grid-forming provisions are the natural reference for this tender's mandatory
grid-forming requirement, and it is declined on market-scope grounds.

Item 36 (Sri Lanka Grid Connection Code confirmation) is marked **Not Received with no remark**, yet
item 61 — the *Grid Compliance List of Envision Energy BESS for Projects in Sri Lanka*, 11 August
2026, expressly against "CEB Grid Code — Grid Connection Code (July 2024)" — post-dates the
checklist and largely answers it. **The workbook status is stale, not the evidence.**

### F-11 (Medium) — The "Grid-Forming BESS Grid Compliance" study never uses the term

`61. Sri_Lanka_Grid-Forming_BESS_Grid_Compliance_ver01pdf.pdf` is a 31-page clause-by-clause
response to the CEB Grid Connection Code (July 2024). Verified independently with both MarkItDown
and `pdftotext -layout`, the body contains **zero** occurrences of "grid-forming", "grid forming",
"voltage source", "voltage-controlled", "short-circuit ratio" or "weak grid". "GFM" appears five
times, always as "GFM/GFL modes" or "seamless GFL/GFM transition" (see F-1). The grid-forming claim
lives in the filename, not the analysis.

Document-control defects in the same file: `Doc. No.: PMD - XXXXXXXX` **placeholder**, Rev. A, and
no signature — while checklist item 61 requires it "signed on company letterhead".

Substantively the response is qualified in the usual places: reactive capability "cannot meet"
noted at one clause, over-frequency detail "determined on a case by case" basis, POD/SSTI
capability offered as input provisions, and repeated deferral to "the Technical Specification of
PCS-2520 and PPC document" — **which is not in this package**. Project-specific RMS/EMT studies are
acknowledged as still required.

### F-12 (Low, but corrigible now) — The tracking workbook's Summary tab under-reports

`Summary!B4:B9` uses `COUNTIF('Supplier Doc Checklist'!$F$2:$F$65, …)`, but the checklist data runs
to **row 69**. Items **60, 61 and 62** (rows 66, 67, 69) fall outside the range.

| | Summary tab reports | Actual |
|---|---|---|
| Received | 38 | **41** |
| Not Received | 14 | 14 |
| Blank (55, 56, 57) | — | 3 |
| Total | 52 | **58 numbered rows** |

Separately, **items 50–53 do not exist in the workbook at all** — numbering jumps from 49 (PSCAD
model) straight to 54 (BoL energy vs contracted rating). Four checklist lines in the
Performance & Simulation Data section were removed or never transcribed. Given the section they sit
in, these are plausibly the SCR/phase-step validation and model-validation-report rows that the
6 August evidence register already flags as missing. **The checklist cannot be relied on as a
completeness measure until 50–53 are restored.**

### F-13 (Low) — Filled Volume 2 GTP quality

`J. Volume 2 Filled Documents/Technical Specifications` (both `.docx` and `.pdf`) is the completed
Section 6 GTP and confirms tender `TR/REP&PM/ICB/2026/001/C`. Substantive entries are sound —
ENPCS2520 at 2.52 MW / 690 V / 50 Hz, liquid cooling, 416S1P×6 configuration, 0.25C continuous,
100 % DoD, 7300 EFC @100 % DoD / 9125 @80 % / 14600 @50 %, ≤3 %/month self-discharge, IP65, droop
1–9 %, deadband 0.0–1.0 Hz in 0.05 Hz steps, PF ±0.95, EnOS PPC.

Defects:

- **A.5 "Model No." answered "8"**; **A.4 "Make" answered "BESS"** — neither is a designation.
- **A.6 "Total Area Required (Acres)" answered "350 m2"** — wrong unit, and implausible for the
  block.
- Block totals (A.15 12 MW / A.16 48 MWh, 8 modules, 8 inverters) reconcile to neither the
  10 MW / 40 MWh nor the 11 MW / 44 MWh design calculation; 8 × ENPCS2520 = 20.16 MW against a
  declared 12 MW battery rating.
- **B.40 "Grid Forming Capability" is answered with a bare "Yes"** — see F-1.
- Section E (grid-code compliance metering, clause A.05.22) is answered "**Meter is Bop scope**" on
  **all five rows**, and items 43/44 are likewise declined as BoP scope. Legitimate as a scope
  boundary, but it means **no party in this package owns grid-code compliance monitoring**.
- The GTP contains **no round-trip-efficiency row, no capacity-warranty row, no degradation row and
  no augmentation row** — the commercially load-bearing guarantees are outside the schedule and
  live only in the design calculations, with the caveats at F-2.
- Tendered standards lists in A.9 and B.37 differ from the Required columns in exactly the ways
  F-10 records — internally consistent, but visibly short of the requirement.

### F-14 (Informational) — Reference letters are credible but all grid-following applications

Four operator letters: a 60 MW / 120 MWh ecological-protection project (18 sets, from Dec 2022,
a state-owned EPC contractor); a wind +
storage project (120 MW / 240 MWh, 33 sets, from Apr 2023, an independent power producer); a 200 MW wind project; and an overseas 100 MW / 100 MWh contingency-reserve test record.

Both letters from the two named-grid projects report **98.2 % availability** to 1 March 2024, with a consistent fault
signature: **0 hours** cell-fault downtime, 36–43 h DC-system, **68–70 h PCS**, 1 h EMS. PCS is the
dominant availability risk in the operator record — which is notable given F-7 (the offered PCS
model is not among the referenced units).

None of the four references demonstrates **grid-forming** operation. The overseas test record is a
handwritten, part-rotated scanned test form; OCR recovers the structure (two ramp tests to ~100 MW,
"Result: Passed") but individual handwritten values are not reliably legible and should not be
quoted without a clean copy. It also carries named signatories — treat as personal data.

### F-15 (Informational) — Simulation package inventory

- **PSS(R)E**: `ENVSG01_20260327_PSSE_V35.dll` (GFM PCS), `ENPPC_260415_PSSE_V35.dll` (PPC),
  `ENVSG_PPC_2520_260416_LKA.dyr` — a **Sri-Lanka-specific** dynamic record instantiating `ENGFM01`
  (2520 kW base) and `BNPPC_GFMV3`, with a 47.5/51.5 Hz protection envelope, 46.9/52.1 Hz trip
  stages and an LVRT/HVRT current-injection table. Manual V1.4a, 11 Aug 2026, 9 pp.
- **PSCAD/EMTDC**: `PCS2520x4_UPPC_x64_260605aBB.pscx` (4 × ENPCS2520 at 690 V / 50 Hz on one
  10.1 MVA skid), `PCSControllerInterface.dll`, five `.obj` + one `.lib` interface objects, GFL PCS
  manual V4.1b1 and Univers PPC manual V1.1.5b. Requires PSCAD V5.0 + Intel Fortran XE 15+, 1–200 µs
  timestep, 50 µs recommended.
- The PSCAD manual describes the compiled DLL using **wind-turbine** source-code wording — a copy-paste artifact from Envision's WTG documentation. Cosmetic, but it is a document
  hygiene signal in a package where model provenance matters.
- The PSS(R)E UDM manual's §4 "Diagnostic Flags and Internal Variables" renders as
  `错误!未定义书签` (Word "undefined bookmark" error) — the section is broken in the released PDF.

### F-16 (Resolved) — The package is inside the bid window

The original submission deadline was 14 August 2026, against which the filled Volume 2 schedule and
the tracking workbook (both 17 August) appeared to post-date the bid. **The project owner confirmed
on 21 August 2026 that the deadline has been extended to 2 September 2026.**

Consequences:

- All package material is **inside** the bid window. There is no submission irregularity.
- The **5 August revision of the 10 MW design calculation is the offered document** (F-2), so the
  offered container is **ENS-D10G**, not ENS-D10E. Every other document in the bid should be
  consistent with that — including the fire-protection specification, whose header scopes
  **ENS-D10** while the offered configuration pairs **ENS-D10G with ENS-D06G** (F-4).
- Most importantly: **the findings in this review are still correctable.** Nine working days remain
  (21, 24–28, 31 August, 1–2 September). Section 5 is prioritised accordingly.

---

## 3. Evidence register movement

Against `oem/envision/compliance_evidence/README.md` as at 6 August 2026:

| Outstanding item (6 Aug) | Status after this package |
|---|---|
| True grid-forming V/F operation | **Partially closed / newly contradicted** — signed letter received, but F-1 |
| PSS(R)E RMS model | **Closed** — executable DLLs, LKA `.dyr`, manual V1.4a |
| PSCAD/EMTDC model | **Contradicted** — model received but is the **GFL** variant (F-1) |
| SCR and phase-step validation | **Still missing** — no SCR 1/3/5/10, no ±50° phase step |
| Standards compliance | **Partially closed** — 11 AC + 5 DC certificates received; 14 still uncertified (F-10) |
| 45 °C performance guarantee | **Still missing, and now materially aggravated** (F-3) |
| Capacity Maintenance Plan | **Partially closed** — BoL sizing + 15-yr curves received; augmentation/replacement asserted as "none needed"; recycling/decommissioning **not** answered (F-5) |
| Ride-through and controls | **Partially closed** — grid compliance list + `.dyr` envelope; project RMS/EMT studies still required |
| Single-line diagram and export limiter | **Partially closed** — layouts, transformer and RMU datasheets received; plant SLD is declined as BoP scope |
| Equipment design life | **Partially closed** — 20-yr non-battery letter received, self-certified ("No certification to prove this but we provided a statement"); 15-yr battery life points to the bankability study, which is where F-3 arises |
| Fire safety and protection | **Partially closed** — spec + two UL 9540A reports; next-level test required by the report itself (F-4); D06G coverage unevidenced |
| Power-quality evidence | **Partially closed** — IEEE 519 and IEC 61000 cover pages received; harmonic apportionment 0.25 issue unresolved |

**Net:** a large, genuine advance on artifact availability. The three items that block a bankable
position — **grid-forming EMT evidence (F-1)**, **RTE headroom at the floor (F-2)** and **45 °C
cycle life versus the no-augmentation claim (F-3)** — are unclosed, and two of them are now
*better evidenced against the supplier* than they were before this package arrived.

---

## 4. New technical reference data recovered

For the corpus record (lossless-ingestion, GWTF DATA-01):

- **Cell**: the affiliate's `HC-L755A`, LFP, **3.2 V / 755 Ah / 2416 Wh**; 10,000 cycles to 70 % @25 °C /
  ~4,000 @45 °C (0.25P); storage recovery 99 % @25 °C, 97 % @45 °C after 135 d @100 % SOC.
- **Pack/module**: `ENS-1P416S-L-10`; rack configuration 416S1P × 6.
- **DC containers**: `ENS-D06G-24120-10100-000` — 6,030 kWh per container, 6 racks parallel,
  24.121 MWh nameplate per AC twin-skid, 4 containers per twin-skid; `ENS-D10G-20100-10100-000`
  (supersedes `ENS-D10E-…`). DC range **1165–1500 V**; 10 racks per DC container.
- **PCS**: `ENPCS2520`, 2.52 MVA, 690 V, 50 Hz, IP65, ‑25…45 °C, ≤85 dB(A) @1 m, droop 1–9 %,
  deadband 0.0–1.0 Hz (0.05 Hz steps), PF ±0.95.
- **AC skid**: 4 × ENPCS2520 = **10.08 MW**; step-up **10,100 kVA**, 0.69/33 kV, three-winding,
  off-load tap changer, LI 170 kV / AC 70 kV, oil-temperature indication/alarm/trip.
- **Switchgear**: 36 kV / 630 A RMU, 33 kV rated, 170 kV LI / 70 kV PF withstand, gas tank IP65,
  enclosure IP3X.
- **Container envelope**: 6058 (L) × 2438 (W) × 3258 (H) mm, < 50,000 kg; MV station
  12192 × 2438 × 2896 mm, ~49,000 kg.
- **Envision disclosed track record** (letter): 18.7 GW / **52.6 GWh** contracted; **33.5 GWh**
  shipped; **20.65 GWh** at COD.
- **Auxiliary load**: 0.17 MW × 4 h at BoL for the 11 MW case, "cannot be guaranteed separately",
  computed at 35 °C.
- **Loss stack (11 MW case)**: calendar degradation FAT→SAT 97 %; usable DC ratio 98 %; LV DC cable
  99.9 %; PCS 98.5 %; LV/MV transformer 99.2 %; MV cable 99.6 %; MV/HV transformer and HV cable
  100 % (assumed, BoP).

---

## 5. Pre-submission punch list

**Deadline 2 September 2026. Nine working days: 21, 24–28, 31 August, 1–2 September.**

Triaged by what can actually be delivered in that window. The governing distinction is that some
gaps are **document work** (days), some are **simulation work** (a week, but only if an input
arrives first), and some are **physical testing** (months) that cannot be closed and must instead be
converted into contractual commitments.

### Tier 1 — critical path, request today (21 August)

These gate everything else because a simulation cannot start until its model exists.

1. **The grid-forming PSCAD/EMTDC model.** Ask whether the GFL model was supplied in error and the
   GFM EMT model exists. Envision demonstrably has a GFM PSS(R)E model with a Sri-Lanka dynamic
   record, so a GFM EMT model plausibly exists too. **If it does not exist, that is decisive and you
   need to know today, not on 1 September** (F-1).
2. **SCR 1/3/5/10 at X/R 5, plus the ±50° phase step**, with V/P/Q traces. This is a week of
   simulation work and it **cannot start without item 1**. Volume I §3.1(p) makes its absence a
   stated ground for technical rejection — this is the single highest-value item in the package.
3. **45 °C guaranteed case** — cell temperature under liquid cooling at 45 °C ambient, auxiliary
   load at 45 °C, resulting guaranteed RTE, and **4 hours at rated output at site ambient** as
   Volume I §3.1(k) explicitly requires. A design-calculation update, not a test (F-3).

### Tier 2 — document corrections, days not weeks, and several are currently self-harming

4. **Delete or reword "seamless GFL/GFM transition"** from the item 61 compliance list (clauses
   3.17.4, 3.17.4.4). As drafted it advertises the exact behaviour §3(c) prohibits. This is a
   wording change in a document that is **actively damaging the bid as written** (F-1).
5. **Sign and identify the item 61 compliance list** — it carries placeholder `Doc. No.: PMD -
   XXXXXXXX`, Rev. A, and no signature, while the checklist requires it signed on company
   letterhead (F-11).
6. **Supply the Technical Specification of PCS-2520 and the PPC document.** The compliance list
   defers to them repeatedly and neither is in the package — a large share of the grid-code
   response currently points at a document the evaluator does not have (F-11).
7. **Obtain the MAL** required by checklist item 58, which is marked Received but absent (F-8).
8. **Resolve entity attribution** — written confirmation that Envision's Clause 2.7.3 track record
   qualifies the affiliated supply entity, plus any parent guarantee. Legal input, but it is a letter
   (F-8).
9. **Replace item 57** with a genuine decommissioning and recycling commitment referencing Sri
   Lankan environmental regulation. The present filing is a disassembly manual (F-5).
10. **Replace or supplement item 38** with actual grid-forming modelling evidence; the present
    filing is a black-start feature description marked "for reference" (F-6).
11. **Explain ENPCS2520's absence from the reference list** — its relationship to the referenced
    ENPCS 2750/2500 family, and any commissioned ENPCS2520 units. **Complete the client-contact
    column**, which the RFP form requests and which is empty for every PCS and PPC row (F-7).
12. **Fix the filled Volume 2 GTP entries**: A.4 "Make" = "BESS", A.5 "Model No." = "8", A.6 acres
    answered "350 m2", and block totals that reconcile to neither design calculation. These are
    unforced errors in a scored technical schedule (F-13).
13. **Confirm fire-protection coverage for both offered containers.** The specification header
    scopes ENS-D10; the offered configuration pairs **ENS-D10G with ENS-D06G** (F-4, F-16).
14. **Re-date the two "Will finish before 2026" standards remarks** — the date has passed, and a
    stale commitment reads worse than an honest revised one (F-10).

### Tier 3 — cannot be closed by 2 September; convert to contractual commitments

Do not leave these as silent gaps. Each should appear in the bid as an explicit, dated undertaking,
which is a far stronger position than an evaluator discovering the gap unaided.

15. **UL 9540A unit-level or installation-level fire test.** Physical burn testing — months. Offer a
    dated test commitment and interim compliance basis. Note the module report **itself** states one
    of the two is required, so the evaluator can find this without help (F-4).
16. **IEC 62620 and IEC 62933-5-2 certification.** Offer realistic completion dates (F-10).
17. **The 45 °C cycle-life exposure.** Re-testing is not possible in the window, so cover it
    commercially: a **capacity/throughput warranty** and an **augmentation undertaking** triggered if
    measured capacity falls below the declared curve. This converts the strongest technical exposure
    in the package into a bankable term, and it is the right answer even with more time (F-3).
18. **IEEE 2800-2022, UL 1741-SB, IEEE 1547-2018.** Declined on market-scope grounds. Sustainable as
    a position, but state the equivalence argument (EN 50549-2, G99) **in the bid** rather than only
    in a supplier workbook remark (F-10).

### Tier 4 — in-house, no counterparty needed, hours of work

19. **Correct the tracking workbook** — fix `Summary!B4:B9` to `$F$2:$F$69` (it currently reports
    38 Received against a true 41); **restore missing items 50–53**; set statuses for items 55–57;
    update item 36 to reflect that item 61 post-dates and largely answers it (F-10, F-12).
20. **Re-baseline on the 5 August design calculation.** With the deadline extended, the 5 August
    revision is the offered document, so ENS-D10G is the offered container. Check every other bid
    document for consistency and ask Envision for a properly versioned re-issue with a change record
    (F-2, F-16).
21. **Negotiate RTE headroom.** Year-15 at exactly 85.0 % against a monthly-assessed floor with LD at
    150 % of the peak-time 33 kV GP tariff is a zero-margin covenant, and the supplier has attached a
    0.5 % meter-tolerance clause to it. Either obtain headroom above the floor or accept the
    tolerance clause **knowingly and priced**, rather than inheriting it silently (F-2).

---

## 6. Handling and publication status

The source binaries are **not committed to this repository**. They remain in the project owner's
private working set, with SHA-256 recorded in
[`../source_packages/NSO250MW_checklist_2026-08-21.MANIFEST.sha256`](../source_packages/NSO250MW_checklist_2026-08-21.MANIFEST.sha256).

The existing `PUBLICATION_AUTHORIZATION.md` covers four specifically enumerated files from the
6 August tranche. It does **not** extend to this package, which additionally contains material that
is **not Envision's to authorise**:

- the **independent test house's** bankability report — the test house's copyright, classified
  "**CLIENT'S DISCRETION**" where the client is **the battery affiliate**;
- third-party **customer reference letters** on operators' own letterheads (a state-owned EPC
  contractor, an independent power producer, and others);
- third-party **certification-body** certificates and test reports (certification bodies and the
  IECEE CB scheme);
- **proprietary compiled model binaries** (`.dll`, `.obj`, `.lib`, `.pscx`, `.dyr`) — Envision's
  compiled PCS/PPC control code. The repository's existing fixture note records that these
  binaries are deliberately not committed;
- an **overseas system-operator test record bearing named individuals' signatures** — personal data.

**Recommendation:** keep the binaries out of the **public** repository. If publication of any part
is desired, obtain authorisation **separately from the battery affiliate and from the test
house** for the bankability study, and treat the model binaries and the personal-data-bearing test record as publish-never
regardless of authorisation.

**A private repository resolves this.** Every blocker above concerns *distribution*, not storage:
holding a licensed report, a counterparty's letterhead correspondence or supplied model binaries in
the bidder's own private repository is ordinary use of material received for the purpose. Verified
21 August 2026 that the configured GitHub credential carries full `repo` scope with private-repo
read and write. If the package is moved to private hosting, the residual control is **access
breadth** — every collaborator added to that repository receives the whole dossier, including the affiliate's
bankability study and Envision's compiled control code, so the collaborator list should stay minimal and be
reviewed when the bid closes.

Size is not a constraint: 58 unique files totalling **83.9 MB**, largest 43.0 MB, below GitHub's
50 MB per-file warning threshold. Git content-addressing deduplicates the 9 duplicate groups
automatically, so the 173 MB unpacked package stores as ~84 MB without Git LFS.
