# NSO 250 MW — Addendum 01, Annex A and the clarification register: ingress evaluation

- Tender: `TR/REP&PM/ICB/2026/001/C`
- Sources ingressed: **3 files, 53 pages** — Addendum No. 01 (10 pp), Annex A Functional & Performance
  Requirement (27 pp), Clarifications for the RFP (16 pp: 15 content + 1 blank)
- Received: 27 August 2026, via the project owner
- Extraction: governed MarkItDown 0.1.7 (GWTF R26) for the two digital-text PDFs; the clarification
  register is an **image-only scan** and went through the OCR branch — see §0
- **These are controlling procurement documents.** Unlike every prior ingress in this corpus, they are
  not OEM or supplier material: they are issued by the Employer and they **qualify and override the
  RFP volumes**. Where this review conflicts with them, they govern.

This is **derived analysis**. It corrects three findings in the 21 August 2026 dossier evaluation.
Those corrections are stated plainly in §2 rather than folded silently into new text.

---

## 0. Source QA and extraction route

| Document | Pages | Text layer | Route | Result |
|---|---|---|---|---|
| Addendum No. 01 | 10 | Yes (Word 2016, created 07/08/2026 19:13 +05:30) | MarkItDown | Clean, 21 KB |
| Annex A Functional & Performance Requirement | 27 | Yes (Word for M365, created 26/06/2026 08:11 +05:30) | MarkItDown | Clean, 51 KB |
| Clarifications for the RFP | 16 | **None — 0 characters** | MarkItDown → **empty**, then OCR | See below |

The clarification register is a 300 dpi Canon scan (`Adobe PSL 1.3e for Canon`, created 21/08/2026
19:55 +05:30), one full-page image per page. MarkItDown correctly returned an empty document.
`tesseract` 5.3.4 recovered text but **scrambled the two-column Q&A table**, interleaving question and
answer (e.g. "Please refer to item 23 of Addendum 01" became "PISase fblet to em 25 er adden Ol").
R26 requires verifying an OCR result before drawing claims on it, so all 15 content pages were
rendered and read directly; the resulting verified transcript is at
[`../rfp/extracted/NSO_250MW_BESS_RFP_Clarifications_2026-08-21.verified-transcript.md`](../rfp/extracted/NSO_250MW_BESS_RFP_Clarifications_2026-08-21.verified-transcript.md).
The raw tesseract output is retained beside it as a provenance record of the mechanical baseline.
**No finding in this review rests on the unverified tesseract text.**

A note on page count: the upload notice for the clarification PDF reported 138 pages. Both PyMuPDF
and pdfplumber report **16**, and the document's own footer runs "Page 1 of 15". 16 is correct.

Each content page of the clarification register bears an **unnamed initialling mark**. No individual
is named. The three documents are procurement records issued to all bidders, in the same class as the
RFP volumes already committed here, so they are committed in full.

---

## 1. What these documents change

The 21 August evaluation closed by recording that "the official 250 MW Annexes A–D, addenda and
clarification register remain required where they control or qualify the RFP volumes." Two of the
three have now arrived. Between them they **move the bid deadline, reverse one punch-list
instruction, remove one critical-path item, and harden the RTE and liquidated-damages exposure
considerably.**

### 1.1 The schedule — and two windows that have already closed

Addendum 01 item 01 replaces the Project Milestone Schedule in Volume I clause 1.4:

| Milestone | Date |
|---|---|
| Requests for Clarifications | **25 August 2026** |
| **Closing date of submission of Proposals** | **4 September 2026 by 10.00 hrs** |
| Bid evaluation and submission to CANC | 5 October 2026 |
| CANC decision and appeal process | 16 October 2026 |
| Cabinet approval | 28 October 2026 |
| PUCSL approval | 4 November 2026 |
| Issue of Letter of Award | 6 November 2026 |
| Acceptance of LOA | 13 November 2026 (within 7 days) |
| Signing of ESA | 14 December 2026 (within 1 month of acceptance) |
| **Submission of models and results on Dynamic Model Tests** | **14 January 2027** (within 1 month of ESA signing) |
| Submission of Environmental Clearance | 14 January 2027 |
| Financial Closure | 15 March 2027 (within 3 months of ESA signing) |
| Commissioning, Testing & COD | 16 August 2027 (within 8 months of ESA signing) |

**The corpus recorded the deadline as 2 September 2026. It is 4 September 2026** — two days later than
assumed, on the authority of the Addendum itself rather than a verbal report.

Two windows have nonetheless **already closed**:

1. **Requests for clarifications closed 25 August 2026.** The Tier-1 actions in the 21 August punch
   list that were addressed to *NSO* can no longer be asked. Only requests to the *supplier* remain
   open. This is the single largest procedural change to that punch list.
2. **The Grid Interconnection Confirmation Letter must be requested from the relevant Provincial
   Director of EDL "at least 21 days before the Closing date"** (Addendum item 07) — i.e. by
   **14 August 2026** — and "EDL shall not be liable for any delays in issuance of the same." If the
   Bidder is taking **Option 2** for the Grid Point, that letter is **mandatory**, forms part of the
   Bid (item 02, and clarification 11), and its absence is a **Major Deviation** under Volume I
   clause 6.3.1 (item 08). If it has not already been requested, this is the most urgent item in this
   review, and it is a disqualification risk rather than a scoring one.

Also newly disqualifying: **failure to submit Certification of Registration under the Public Contract
Act No. 3 of 1987 (PCA3)** is added to Volume I clause 6.3 as a ground for exclusion (item 10).

---

## 2. Corrections to the 21 August 2026 evaluation

### C-1 (Critical correction) — Annex A **requires** the dual-mode GFL/GFM behaviour that the 21 August review told the bidder to delete

The 21 August evaluation, finding F-1 and punch-list item 4, recorded that the item 61 compliance
list's "GFM/GFL modes" and "seamless GFL/GFM transition" language "advertises the exact behaviour
§3(c) prohibits", called that document "actively damaging the bid as written", and instructed:
"**Delete or reword 'seamless GFL/GFM transition'**".

Annex A, the official Functional & Performance Requirement, says at **A.05.17**:

> "(i) The BESS shall **support both grid-following and grid-forming control modes, enabling online
> switching between the two.**
> (j) The **grid-following mode shall operate stably under a minimum short-circuit ratio (SCR) of
> 1.2**, while the **grid-forming mode shall operate stably under a minimum SCR of 1.0**."

Dual-mode capability with online switching is therefore a **mandatory requirement of the controlling
annex**, not a prohibited deviation. Acting on punch-list item 4 would have deleted the bid's
evidence of compliance with A.05.17(i).

**That instruction is withdrawn. Do not delete the dual-mode language.**

The underlying tension is real but it is between two Employer documents, not inside the supplier's:

| Source | Says |
|---|---|
| Volume I §3(c) | Full grid-forming (voltage-sourced, voltage-controlled) inverter; "should NOT change the control mode to current-controlled (grid-following) during normal operation or under any network fault conditions" |
| Annex A A.05.17(i) | "shall support both grid-following and grid-forming control modes, **enabling online switching between the two**" |
| Clarification 12 | "Grid forming is listed as a mandatory requirement… clarify whether these standalone projects can practically have grid-forming capability" → **"Yes"** |

The reconciliation that survives all three is: the plant must be **capable** of both modes and of
switching between them, must **operate** in grid-forming mode, and must not **drop** to
current-controlled operation during normal operation or faults. A bid should state exactly that.
What remains genuinely unhelpful in the item 61 compliance list is offering seamless transition as
the *basis for meeting converter operational robustness* — that is, as the fault response. The
capability statement stays; the fault-response framing should be re-pointed at A.05.17(j)'s
requirement that **grid-forming mode be stable down to SCR 1.0**.

Note also that A.05.01(a) gives Annex A precedence over the **Grid Connection Code** where they
differ. It does not, on its face, resolve Annex A against Volume I. Since the clarification window has
closed, this now has to be handled by stating the reconciliation in the bid rather than by asking.

The corpus's own screening evidence is unaffected and is corroborated: `grid_screening_scope.md` and
`grid_screening_emit.py` already record a **GFL floor of SCR 1.2** for these rounds. Annex A confirms
that figure exactly and adds the **GFM floor of SCR 1.0**.

### C-2 (Critical correction) — the SCR 1/3/5/10 sweep is **not** a bid-stage requirement if both models are supplied

The 21 August punch list put the SCR sweep at Tier 1 item 2 — "a week of simulation work… the single
highest-value item in the package" — on the basis that Volume I §3.1(p) makes its absence a ground for
technical rejection.

Annex A **A.05.23(d)** states the bid-stage minimum as an **alternative**:

> "As a minimum requirement, bidders must fulfil one of the following:
> I. Submit **initial non-site-specific simulation models** of the BESS in **both PSS®E and
> PSCAD™/EMTDC™** formats along with the tender for evaluation; **or**
> II. provide **test results** with the tender, demonstrating the BESS response in terms of voltage
> (V), active power (P), and reactive power (Q) during deep and shallow faults, and for a +50-degree
> phase angle step change at the POC, under SCR levels of 1, 3, 5, and 10, with an X/R ratio of 5.
> **Failure to meet at least one of the above requirements may result in the rejection of the
> bidder's technical proposal.**"

Addendum 01 item 14 adds precisely this to the Volume II Section 5 Compliance Schedule as new item 12,
in the same "models **or** test results" form.

The bidder **already holds both models** (PSS®E V35 DLLs with the Sri-Lanka `.dyr`, and the PSCAD
`.pscx` with its interface objects). Route I is therefore satisfiable now, without a week of
simulation. Annex A A.05.23(c) requires PSS®E 35.x and PSCAD 5.x with Intel Fortran — both match the
supplied model manuals.

**The critical path is not what the 21 August review thought it was.** Two consequences:

- The SCR sweep leaves the bid-stage critical path. It does **not** disappear: A.05.23(e) requires
  the grid-forming demonstration in **both** PSS®E and PSCAD, and Addendum items 06 and 12 move the
  Dynamic Model Tests to **within one month of ESA execution** (14 January 2027) with **forfeiture of
  the Performance Security** if the results are not delivered "in a form and level of detail
  acceptable to the NSO". The grid-forming EMT gap therefore converts from a bid-rejection risk into
  a **security-backed post-award execution risk on a one-month clock**.
- The word "**non-site-specific**" in route I matters: the generic model is explicitly acceptable at
  bid stage, which is what the bidder has.

Clarification 35 confirms the model set: of the three tools named in A.05.23(b), "**It is compulsory
to provide PSSE and PSCAD models**" — so the PowerFactory RMS/EMT models mentioned in A.05.23(b) are
**not** compulsory. (Envision has previously delivered DIgSILENT/PowerFactory models, so this is
available if useful, but it is not required.)

### C-3 (Correction, favourable) — item 61's "grid-forming" filename is less damning than recorded, but the placeholder defects stand

F-11 recorded that the *Sri Lanka Grid-Forming BESS Grid Compliance* study "never uses the term" and
that "the grid-forming claim lives in the filename, not the analysis". That reading stands as a
description of the document. What changes is its consequence: since Annex A requires dual-mode
capability and the grid-code response is a clause-by-clause answer to the **CEB Grid Connection
Code** — which A.05.01(a) says Annex A overrides where they differ — the absence of grid-forming
language in a Grid-Connection-Code response is less anomalous than it appeared. The document-control
defects in F-11 are unaffected: `Doc. No.: PMD - XXXXXXXX` placeholder, Rev. A, unsigned, and repeated
deferral to a PCS-2520 technical specification that is not in the package.

---

## 3. New findings

### N-1 (Critical) — the RTE guarantee is now materially worse than "zero headroom"

F-2 recorded that the 5 August revision moved year-15 RTE incl. aux from 84.9 % to **exactly 85.0 %**,
and attached a **0.5 % meter-tolerance clause**. Four clarifications independently harden every
element of that position:

| Clarification | Effect on the RTE guarantee |
|---|---|
| **40** — "may there be errors in the final performance test… e.g. an error within 1% considered as meeting the standard?" → **"No"** | The measurement-tolerance concept is **refused outright**. Envision's 0.5 % meter-tolerance clause has no contractual counterpart — it is a supplier-side statement against an Employer that has declined the principle |
| **51** — auxiliary and HVAC loads directly associated with BESS operation "**shall be accounted for in the RTE calculation**" | The **aux-inclusive basis is confirmed as the contractual basis.** The 30 July review's hope that the metered basis might be aux-exclusive (88.4 %) is closed off. The one relief: general site loads — CCTV, security, lighting — are **excluded** |
| **31** — energy lost to frequency/voltage regulation in standby, unscheduled by the grid, counted in RTE → **"Yes"** | Adds an **uncompensated loss term** the design calculation does not model at all |
| **55(b)** — energy exchanged providing frequency response, synthetic inertia, oscillation damping and AGC is **not** excluded from the RTE calculation **or** from the 400 Full Equivalent Cycle allowance | Adds a **second** uncompensated loss term, and simultaneously consumes cycle allowance |
| **5** — RTE assessed monthly; a shortfall "**shall not be carried forward or reconciled**" against later months or year-end | No annual averaging. Every month stands alone |

The design calculation's 85.0 % at year 15 is computed on a loss stack that includes auxiliaries at
**35 °C** and excludes both standby-regulation and grid-support energy. Clarifications 31 and 55(b)
put those two terms **inside** the measured quantity. A guarantee sitting exactly on the floor, on a
basis that now carries two loss terms it never modelled, assessed monthly with no reconciliation and
no tolerance, is not a thin margin — it is a **structurally short position**.

Compounding: **clarification 55(a)** states that power or energy reserved for those same ancillary
services is **not** treated as available for Capacity Availability or Contracted Storage Capacity. The
plant is charged for the energy, denied the availability credit, and consumes the cycle allowance.

### N-2 (Critical) — no aggregate cap on liquidated damages, and the capacity charge can go to zero

Clarification **54** is the most consequential commercial answer in the register:

- "**There is no aggregate cap on liquidated damages either per Contract Year or over the full 15-year
  Term.**" The only cap is **monthly**, per Clause 2 of Appendix A of Volume III.
- RTE liquidated damages sit inside that monthly cap.
- But "**capacity charge deductions for failure to achieve the required 97 % availability are not
  liquidated damages and therefore do not fall within the monthly LD cap**" — and "if the BESS fails
  to meet the 97 % availability requirement, the capacity charge payable for that month **may be
  reduced, potentially down to LKR 0**".

So the revenue line has **no floor** in a bad month, and the damages line has **no ceiling** over the
term. Read with clarification **52** — no termination compensation or buy-out formula for NSO default,
political force majeure attributable to the Government of Sri Lanka, or prolonged natural force
majeure, beyond what the ESA expressly provides — and clarification **30** confirming the ESA template
is final and unamendable after the LOA (Volume I §7.1), the downside is **unbounded, unhedgeable at
contract stage, and not negotiable after award**.

For the financial model this is a direct input: **an availability-linked revenue floor of zero and an
uncapped multi-year LD tail** should be modelled explicitly, not approximated by a capped-LD
assumption.

### N-3 (High) — the 11 MW declared capacity is now formally available, and it is the better RTE position

Clarification **2** confirms the Contracted Capacity is the **Declared Capacity offered by the
successful Bidder in Section 1 of Volume II**, amended into the Contract at execution, expressly
"i.e., up to 11 MW" in the question and not contradicted in the answer. Clarification **66** confirms
Contract Year 1 uses the capacity **declared at bidding stage**, which "is required to be achieved and
demonstrated during commissioning".

This matters because the corpus records the **11 MW / 44 MWh** variant as carrying more RTE headroom
than the 10 MW case (BoL 86.9 %, year 15 85.0 %) and it is byte-identical to the copy already held.
Against N-1's hardened RTE basis, headroom is the scarce commodity.

**Two checks before relying on it**, neither of which this review can close from the documents in the
corpus:

1. **Reactive capability.** Clarification **24** settles that the requirement is "**±0.3 times the
   rated active power**", not a flat ±3 Mvar. At a declared 11 MW that is **±3.3 Mvar**. The 10 MW
   design calculation states ±3.29 Mvar at the PCC. If the 11 MW variant carries the same ±3.29 Mvar
   figure it is **marginally short** of ±3.3 Mvar. The 11 MW design calculation's reactive figure must
   be read directly and confirmed — this review has not verified it.
2. **Declared capacity is a commissioning obligation** (clarification 66), and the year-15 ADSC
   arithmetic in clarification 53 is worked at 10 MW / 40 MWh. Declaring 11 MW raises every
   capacity-linked obligation in proportion.

### N-4 (High) — two technical proposals are now permitted: the available hedge

Addendum 01 **item 23** repeals the Volume I clause 2.7.1 note that barred variant proposals
("Submission of multiple technical options, variant proposals, optional configurations, or
alternative technical arrangements under the same Proposal shall not be permitted… shall be deemed
non-responsive") and replaces it with:

> "The Project Proponent **may submit a maximum two (02) Technical Proposals** under the Financial
> Proposal submitted for this RFP."

Clarification **73(a)** confirms: "a bidder may submit proposals based on up to **two alternative
manufacturers/complete solutions**", each "a complete and technically integrated BESS solution",
treated as "separate and complete solutions", with **no interchange** of major equipment between them
during detailed design, construction or implementation.

This is the principal new degree of freedom in the bid, and it maps directly onto the two unresolved
technical exposures: the **grid-forming EMT gap** (F-1/C-1) and the **offered PCS having no track
record** (F-7). A second complete solution is the only remaining hedge, because clarification
**73(b)** answers "**No**" to changing a nominated supplier after award. Whatever is submitted is what
must be built.

### N-5 (High) — qualification attribution and pending certifications are substantially relieved

Both open items from F-8 and F-9/F-10 move favourably:

- **Clarification 58(e):** "The qualification should be satisfied based on the **manufacturer/component
  supplier's experience, and therefore need not be experience of the Project Proponent itself**."
  This addresses the core of F-8 — clause 2.7.3 track record does not have to sit in the Proponent.
- **Clarification 58(c):** a **manufacturer-issued declaration on official letterhead** is acceptable
  evidence provided it identifies product, installed quantity/capacity, project(s), location,
  commissioning date and manufacturer; NSO may request supporting evidence.
- **Clarification 58(a)/(b):** thresholds are **cumulative global installed volume**, and must be
  **installed/commissioned** volume, not shipped or contracted. Envision's letter discloses 52.6 GWh
  contracted, 33.5 GWh shipped, **20.65 GWh at COD** — the last figure is the one that qualifies.
- **Clarification 58(d):** an OEM's standard EOI/letter format is acceptable if it carries all
  RFP-required information and is signed by an authorised representative.
- **Clarification 62:** where the proposed package is newly introduced and certifications are still in
  progress, the bidder may submit **currently available valid certifications for the applicable cells,
  racks, major components and/or established product family**, plus documentary evidence of the
  **relationship and technical equivalence** to the proposed package. This is a direct route for the
  14 uncertified standards in F-10 and for the cell-level-vs-system-level problem in F-9 — but it is
  an *equivalence-evidence* route, not a waiver, and the equivalence evidence has to be written.

**What is not relieved:** clarification 58(e) resolves attribution to *a* manufacturer. It does not
resolve *which* group entity — Envision Energy holds the track record while the EOI is signed by an
affiliated supply entity on the battery affiliate's letterhead and the cell certificates name the
affiliate's cell-manufacturing entity. The MAL absent from checklist item 58 also remains absent.

### N-6 (High) — new hard performance parameters in Annex A, several not evidenced in the package

Annex A sets numeric requirements that the 21 August evidence register did not track because Annex A
was not held. Each needs checking against the ENPCS2520 / ENS-D10G package:

| Annex A clause | Requirement | Package position |
|---|---|---|
| A.05.02(a) | PCS AC-side current **110 % continuous**, **120 % for ≥2 min**, "preferably" **150 %** short-term | Clarifications 59 and 64 both refuse relief ("comply with A.05.02"), including an explicit request to cut 120 % from 2 min to 1 min. **110 % continuous implies a ~10 % PCS oversize on top of the reactive requirement.** Not evidenced in the GTP |
| A.05.02(b) | Droop settable **1–9 %**; default **4 %** if NSO specifies none | GTP declares droop 1–9 % — **complies** |
| A.05.02(c)/(d) | Synthetic inertia; **maximum inertia time constant no less than 20 s**, **activation ≤5 ms**, flexibly adjustable | Not evidenced. The PSS®E `ENGFM01` record may carry it; unverified |
| A.05.02(e) | Primary frequency regulation response **<0.2 s**, active power adjustment deviation **≤2 %** | Not evidenced |
| A.05.17(d) | Autonomous damping of **0.2–2.5 Hz** oscillations, active power variation limited to **10–30 % Pn** | Item 61 offers POD as "input provisions" only |
| A.05.17(h) | AGC regulation range **−100 % to +100 % Pn**, steady-state active deviation **≤2 % Pn**; AVC steady-state reactive deviation **≤2 % Pn** | Not evidenced |
| A.05.17(j) | GFL stable at **SCR ≥1.2**; **GFM stable at SCR ≥1.0** | The supplied EMT model is the GFL variant — the GFM SCR 1.0 case is exactly what cannot be demonstrated with it |
| A.05.13 / clarification 24 | Reactive **±0.3 × rated active power** | See N-3 |
| A.05.18 | Fault-current contribution bounded by NSO-specified breaker capability; withstand per A.04 | Max three-phase fault current at POC **25 kA**; breaker failure clearing time **550 ms**. PCS fault contribution/withstand still unevidenced (open since 30 July) |
| A.05.04 | Steady-state frequency **47–52 Hz**, extremes **45–55 Hz**; under-frequency window extends to 45 Hz; 47.0 > f ≥ 45.0 → **10 s** | Clarification 29 confirms **A.05.04 governs**, overriding the 49.5–50.5 / 53 / 47 Hz figures in Annex A clause 04. The supplied `.dyr` protection envelope is 47.5/51.5 Hz continuous with 46.9/52.1 Hz trip stages — **narrower than the 47–52 Hz steady-state requirement at both ends**, and needs reconciliation |

That last row is a concrete, checkable mismatch between the Sri-Lanka dynamic record already supplied
and the frequency requirement Annex A imposes.

### N-7 (Medium) — black start is not mandatory, which further devalues checklist item 38

Clarification **37**: "Is the black start function mandatory in this project?" → "**No**."

F-6 recorded that checklist item 38, filed as grid-forming *modelling evidence*, is actually a
black-start technical solution marked "for reference". It is now established that the document is
**not responsive to item 38 and is not required by the tender at all**. Item 38 needs genuine
grid-forming modelling evidence; the black-start document should be re-filed or dropped.

### N-8 (Medium) — the clarification register contradicts itself on shared interconnection

**Clarification 20:** two projects at the selected GSS on a single land plot → "**Yes.** A common grid
interconnection line may be used, subject to… approvals from the EDL."

**Clarification 75:** two 10 MW/40 MWh projects sharing a common grid interconnection line → "Due to
network constraints, **only one BESS project can be connected to a single 33 kV feeder.** …it is
technically not feasible to accommodate both projects through the same feeder."

These point opposite ways on the same question. They reconcile only if a common *line* can terminate
in two separate *feeder bays* at the GSS — which clarification 46's premise (six GSS can each
accommodate two 10 MW/40 MWh systems) makes plausible but which neither answer states. Since the
clarification window has closed, a two-project bid at one GSS should be costed on the **conservative**
reading — separate feeders, per clarification 75 — and the assumption stated in the bid.

Two further internal inconsistencies are recorded in the transcript: **clarification 65** gives the
Capacity Charge Rate unit as `LKR/MW/month` and then writes the applicable-rate formula in
`LKR/MWh/month` in the same answer; and **clarification 9** offers 2 months from the **LOA** for CEA
approval while Addendum item 01 schedules Environmental Clearance at 1 month from **ESA signing**.

### N-9 (Medium) — commercial and scope changes worth pricing

| Source | Change |
|---|---|
| Addendum 07 | Clause 3.2 wholly replaced. **Two Grid Point options**: Option 1 at the 33 kV feeder bay of the GSS; Option 2 at the nearest feasible 33 kV point. Choice is made by the **provincial Director of EDL**, and must be confirmed in writing (Section 15, Vol II) |
| Addendum 07 | At the Metering Point, **the project proponent fixes the metering equipment** and title passes to **NSO** (previously EDL fixed it and title passed to EDL) |
| Addendum 13 | Volume II Section 4 capacity-charge table now carries explicit **SSCL (if applicable)**, **VAT – 18 %** and **Total** rows; Addendum 11 removes "(excluding VAT)" from clause 2.8 |
| Addendum 09 | SCADA gateway must support **four SCADA master servers** (two at NSCC, two at Backup NSCC), any combination, "without interrupting existing communication links or requiring additional hardware, software, configuration changes, or licenses" |
| Addendum 18 | Land must be **within 5 km of the designated GSS** |
| Addendum 03 | Proposal Security validity **180 days from closing → valid until 3 March 2027** |
| Addendum 04 | Cost breakdown to be submitted in **Microsoft Excel** form |
| Addendum 16 | Proposal Security demand to be signed by the **CEO** of NSO or authorised officer; clarification 41 confirms the security is addressed to the **CEO of NSO** |
| Addendum 19/20/21/22 | Section 13 diagram, Section 15 EDL confirmation letter, Section 16 NSCC communication arrangement and a **revised Model ESA and Tripartite Agreement** are supplied as Attachments 1–4 |
| Clarification 14 | If the developer draws the 33 kV line to the GSS, **cost of construction, finding land and wayleaves are all the developer's** |
| Clarification 43 | EDL identifies and marks wayleaves and issues request letters; **the developer obtains approvals and pays, at its own cost** |
| Clarification 48 | Bonded Warehouse applies **only to BESS facility equipment** — transmission-line materials are **not eligible** |
| Clarification 63 | A **separate firewall** is required at the BESS facility |
| Clarification 21 | Grid-code compliance monitoring: NSO does **not** specify make/model; the **Developer** maintains and calibrates; data **is** used for billing and verification |
| Clarification 4(b) | Grid compliance monitoring standard: **IEC 61000-4-30 Class A** |
| Clarification 23 | The **developer** measures background voltage distortion at the connection point during harmonic measurement — this is the route to closing the long-open harmonic apportionment (0.25 factor) question |
| Clarification 69/70 | LKR 600 m financial resources **per project**, cumulative (2 projects → LKR 1,200 m); each proposal a **complete and separate submission**; clarification 46 — a **separate RFP purchase per proposal** |
| Clarification 60 | A technical/manufacturing partner that is a **formal JV member** must meet **25 % of the LKR 600 m** regardless of role; to avoid that it must be structured as a **subcontractor/supplier**, not a JV member. FIN-1 to FIN-4 completed by each formal member |
| Clarification 44/45 | Agreement to Lease need only be **attested by a Notary Public** (registration not mandatory); bidding on a JV Letter of Intent is acceptable, and Bid Security may be in the **Lead Partner's** name |
| Clarification 76 | **80 perches within the Horana Export Processing Zone** confirmed available by BOI for a Horana GSS project |

### N-10 (Informational) — the year-15 dispatch arithmetic, from the Employer

Clarification **53** supplies NSO's own worked example, which the corpus should adopt as the reference
case rather than deriving its own:

- Contracted Power Capacity (CPC) = **10 MW**
- Contracted Storage Capacity (CSC) = **40 MWh**
- Minimum Dispatchable Storage Capacity in Year 15 = **68 % × 40 MWh = 27.2 MWh**
- Therefore Year-15 ADSC = **2.72 hours at 10 MW, not four hours**
- A 15-minute dispatch at 10 MW requires **2.5 MWh**

"The resulting ADSC, rather than a fixed four-hour discharge duration, shall constitute the applicable
energy limit for Dispatch Instructions." This confirms the 68 % year-15 floor used throughout the
corpus and establishes that dispatch obligations scale down with degradation.

Clarification **26** defines "Number of Remaining Round Trip Cycles per Year at Boundary" as the
remaining equivalent full round-trip cycles measured at the **Point of Interconnection**, after
accounting for cycles used in the relevant Contract Year.

---

## 4. Effect on the 21 August evidence register

| Item | Status at 21 Aug | Status now |
|---|---|---|
| True grid-forming V/F operation | Partially closed / newly contradicted | **Requirement re-read.** Dual-mode capability is *mandatory* (A.05.17(i)); the supplier's dual-mode language is compliant, not self-harming. The gap is the **GFM fault demonstration at SCR 1.0**, not the wording |
| PSCAD/EMTDC model | Contradicted (GFL variant) | **Bid-stage risk substantially reduced** — A.05.23(d)(I) accepts non-site-specific models in both formats. **Post-award risk raised** — GFM demonstration due within 1 month of ESA, Performance Security forfeitable |
| SCR and phase-step validation | Still missing; Tier 1 critical path | **Not required at bid stage** where both models are supplied (A.05.23(d), Addendum 14). Required post-award under A.05.23(e) |
| 45 °C performance | Still missing, materially aggravated | **Unchanged and still the deepest exposure.** Nothing in these documents relieves it; clarification 55(b) makes it worse by charging ancillary-service energy against the 400 FEC allowance |
| RTE headroom | Zero headroom at the floor | **Worse than zero** — see N-1. Meter tolerance refused (40), aux confirmed inside (51), two unmodelled loss terms added (31, 55(b)), no annual reconciliation (5) |
| Standards compliance | 14 uncertified | **Route opened** — product-family equivalence evidence accepted at bid stage (62), with certifications for the exact package before ESA signing |
| Qualification attribution | New, open | **Largely relieved** (58(e)) — manufacturer's experience suffices. Intra-group entity question and the missing MAL remain |
| Capacity Maintenance Plan | Partially closed | Unchanged. Recycling/decommissioning still unanswered (F-5) |
| Ride-through and controls | Partially closed | **New hard numbers to meet** — N-6. `.dyr` protection envelope narrower than A.05.04 at both ends |
| Single-line diagram and export limiter | Partially closed; BoP-scope declined | **Employer has now allocated the scope** — Addendum 07 (two Grid Point options), clarifications 21, 43, 63, 67. "No party owns grid-code compliance monitoring" is resolved: the **Developer** does (21) |
| Fire safety | Partially closed; next-level test required | Unchanged. Clarification 62's equivalence route may help the D06G coverage gap (F-4) but does not answer the UL 9540A unit/installation-level test |
| Power-quality evidence | Harmonic apportionment unresolved | **Method supplied** (23) — developer measures background distortion at the connection point |

---

## 5. Revised pre-submission position

**Closing: 4 September 2026, 10.00 hrs. Clarification window closed 25 August.** Working days
remaining from 27 August: 27, 28, 31 August, 1, 2, 3 September, plus the morning of 4 September.

The triage changes shape because NSO can no longer be asked anything. Every remaining action is
either **in-house** or **addressed to the supplier**.

### Tier 1 — disqualification risks, today

1. **Grid Interconnection Confirmation Letter.** If Option 2 is being taken, this is **mandatory**,
   forms part of the Bid, and is a **Major Deviation** if absent (Addendum 02, 08; clarification 11).
   It should have been requested from the Provincial Director of EDL by **14 August**. Establish
   immediately whether it has been requested and whether it will arrive; if Option 1 is being taken,
   record that decision explicitly in the bid.
2. **PCA3 registration certificate** (Addendum 10) — newly a ground for disqualification.
3. **Confirm the submission arithmetic**: separate RFP purchase per proposal (46), complete and
   separate submission each (70), LKR 600 m financial resources per project cumulatively (69), Bid
   Security to the CEO of NSO (41), Proposal Security validity to 3 March 2027 (Addendum 03).
4. **Re-check JV structure against clarification 60** — any technical partner sitting as a formal JV
   member drags a 25 % share of LKR 600 m. If that was not the intent, restructure it as a
   subcontractor/supplier before submission.

### Tier 2 — decide the technical proposal strategy

5. **Use the two-proposal allowance (Addendum 23, clarification 73(a)).** This is the only remaining
   hedge against the grid-forming EMT gap and the ENPCS2520 track-record gap, and supplier change
   after award is refused (73(b)). Decide whether solution B is the 11 MW / 44 MWh variant, a
   different PCS, or a different OEM — noting no interchange between solutions is permitted.
6. **Decide the declared capacity.** 11 MW carries more RTE headroom, which N-1 makes valuable —
   but first read the 11 MW design calculation's reactive figure against the **±3.3 Mvar** that
   clarification 24 implies at 11 MW (N-3).
7. **Submit both PSS®E and PSCAD models with the bid** under A.05.23(d)(I), with a covering note that
   they are the non-site-specific models the clause contemplates. This is the cheapest available way
   to clear a stated rejection ground.

### Tier 3 — supplier requests, this week

8. **The grid-forming EMT model**, restated: no longer needed to avoid bid rejection, but needed by
   **14 January 2027** with the Performance Security at risk. Ask now, with that date named.
9. **45 °C case** — cell temperature under liquid cooling at 45 °C ambient, auxiliary load at 45 °C,
   resulting guaranteed RTE, and 4 hours at rated output at site ambient (A.05.23 and Volume I
   §3.1(k)). Unchanged from 21 August and still the deepest exposure.
10. **A re-stated RTE guarantee** on the basis clarifications 51, 31 and 55(b) actually establish —
    aux-inclusive, including standby-regulation and ancillary-service energy — and **without** the
    0.5 % meter-tolerance clause, which clarification 40 has refused. If the supplier cannot hold
    85.0 % on that basis, that needs to be known before submission, not after.
11. **Annex A parameter conformance** (N-6): inertia constant and activation time, 110 %/120 %/150 %
    current ratings and the ambient at which they hold, primary frequency response, AGC/AVC deviations,
    POD band and limits, and reconciliation of the `.dyr` 47.5/51.5 Hz envelope against A.05.04's
    47–52 Hz.
12. **Product-family equivalence evidence** under clarification 62, for every standard in F-10 still
    uncertified, plus the UL 1973 component-vs-system point in F-9.
13. Still outstanding from 21 August and unaffected by these documents: the **MAL** (F-8), a genuine
    **recycling/decommissioning commitment** for item 57 (F-5), **replacement of item 38** with real
    grid-forming modelling evidence (F-6, and see N-7), **ENPCS2520 track record and client contacts**
    (F-7), the **GTP data-entry errors** (F-13), **D06G fire-protection coverage** (F-4), and the
    **workbook corrections** (F-12).

### Tier 4 — model and price these, in-house

14. **Rebuild the revenue model** around N-2: **no aggregate LD cap** over the term, a **monthly** LD
    cap only, and a capacity charge that can fall to **LKR 0** in a month where availability misses
    97 %, outside that cap. Add the no-termination-compensation position from clarification 52.
15. **Re-run the RTE case** with the two loss terms clarifications 31 and 55(b) add, and no tolerance.
16. **Price the two-project case conservatively** on separate 33 kV feeders (clarification 75), not on
    the shared line clarification 20 appears to allow (N-8).
17. **Re-baseline** every bid document on the 4 September closing date and on Addendum 01's replaced
    clause 3.2, Section 4 table and Section 11 options.

---

## 6. Handling and publication

These three documents are **NSO procurement records**, issued by the Employer to bidders, of the same
class as the RFP volumes already committed to this repository. They contain no Envision confidential
marking, no third-party copyright, no compiled binaries and no named individuals. They are committed
in full, with the extracts, and recorded in `MANIFEST.sha256`.

The only handling note is the **unnamed initialling mark** on each page of the clarification register.
No individual is identified by it and it is not treated as personal data.

`PUBLICATION_AUTHORIZATION.md` is unaffected — it governs Envision material, and nothing here derives
from Envision material.
