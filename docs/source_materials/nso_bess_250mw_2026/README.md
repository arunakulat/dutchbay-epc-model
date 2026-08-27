# NSO 250 MW / 1000 MWh standalone BESS source package

This directory preserves the controlling procurement documents and the available Envision
design material for National System Operator tender `TR/REP&PM/ICB/2026/001/C`.

The tender establishes **250 MW / 1000 MWh of standalone BESS from 10 MW / 40 MWh AC-capacity
projects** on a build-own-operate basis with a 15-year operational period. The submission deadline
is **4 September 2026 at 10.00 hrs**, set by the revised Project Milestone Schedule in **Addendum
No. 01 item 01** (ingressed 27 August 2026), which supersedes the verbally reported "2 September"
recorded on 21 August. The **window for requests for clarification closed on 25 August 2026**, so
open items may now be pursued only with the supplier or in-house, not with NSO. The programme is
therefore procured as roughly 25 unit-scale projects, which is why the OEM design calculations are
sized at 10 MW / 40 MWh and 11 MW / 44 MWh (the latter being the 10 MW + 10 % export-limit case).
The bidder is a Sri Lankan listed-group company; the equipment supply commitment is given by
**an affiliated supply entity** on the battery affiliate's letterhead, following the transfer of
Envision's BESS business to a group battery affiliate.

## Handling classification

- The NSO tender documents are procurement source records.
- The Envision design calculation is marked **confidential and privileged** by Envision Energy.
  That original marking is retained in the file for provenance.
- On 31 July 2026, the project owner confirmed that Envision authorised publication of the
  Envision content in a public GitHub space, including the design calculation and derived gap
  statement in this corpus. This records permission for the repository publication; it does not
  imply a transfer of copyright or a broader licence beyond the permission received.
- The 5 August 2026 11 MW / 44 MWh design calculation is also marked confidential and
  privileged. The functional-requirements workbook contains supplier compliance declarations.
  Both were ingressed on 6 August 2026.
- On 16 August 2026, the project owner recorded that verbal confirmation had been received from
  Envision covering the two new source files, their extracts and the 6 August evaluation, and
  directed public GitHub publication on the project owner's authority. The scope and limitations
  are recorded in `PUBLICATION_AUTHORIZATION.md`.
- The NSO 250 MW checklist dossier received on 21 August 2026 is **not** covered by that
  authorization, and parts of it are **not Envision's to authorise** — it contains a the independent test house
  report classified at the battery affiliate's discretion, third-party operator letterheads, certification-body
  copyright, compiled model binaries and a test record bearing named individuals' signatures.
  Its binaries are therefore **held outside this repository**, recorded by manifest only. See
  `source_packages/README.md`.

## Package documents and roles

| Document | Repository path | Role |
|---|---|---|
| Paper advertisement | `rfp/NSO_250MW_BESS_Paper_Advertisement_Final.pdf` | Procurement notice and submission deadline |
| RFP Volume I | `rfp/NSO_250MW_BESS_RFP_Volume_I_Final.pdf` | Instructions, qualification and technical requirements |
| RFP Volume II | `rfp/NSO_250MW_BESS_RFP_Volume_II_Final.pdf` | Proposal letters, compliance schedules and forms |
| RFP Volume III | `rfp/NSO_250MW_BESS_RFP_Volume_III_ESA_Final.pdf` | Model Energy Storage Agreement |
| **Addendum No. 01, 7 Aug 2026** | `rfp/NSO_250MW_BESS_Addendum_01_2026-08-07.pdf` | **Controlling amendment** — revises the milestone schedule and closing date, replaces Vol I clause 3.2 (Termination/Metering/Grid Point, two Grid Point options), adds the Grid Interconnection Confirmation Letter and PCA3 as disqualifying items, permits **two technical proposals**, and adds Attachments 1–4 including a revised Model ESA and Tripartite Agreement |
| **Annex A — Functional & Performance Requirement** | `rfp/NSO_250MW_BESS_Annex_A_Functional_Performance_Requirement.pdf` | **Controlling technical annex** — grid-forming and grid-following requirements, SCR floors, inertia, AGC/AVC, protection envelope, simulation-model and commissioning-test obligations |
| **Clarifications for the RFP, 21 Aug 2026** | `rfp/NSO_250MW_BESS_RFP_Clarifications_2026-08-21.pdf` | **Controlling clarification register** — 76 numbered items answering bidder questions on RTE basis, liquidated damages, declared capacity, qualification attribution, certification and scope. Image-only scan; see the verified transcript in `rfp/extracted/` |
| Envision 10 MW / 40 MWh design calculation | `oem/envision/Envision_10MW_40MWh_Design_Calculation_V1.0_2026-07-29.pdf` | Earlier OEM design and performance calculation |
| Envision 11 MW / 44 MWh design calculation | `oem/envision/Envision_Sri_Lanka_11MW_44MWh_Design_Calculation_V1.0_2026-08-05.pdf` | Later, distinct candidate configuration; document does not state the tender number |
| Envision functional-requirements checklist | `oem/envision/compliance_evidence/Envision_Functional_Requirements_Checklist_2026-07-21.xlsx` | Supplier declaration against selected Annex A/B clauses; not the official annex and not evidence-complete |
| NSO 250 MW checklist dossier, 21 Aug 2026 | `source_packages/NSO250MW_checklist_2026-08-21.MANIFEST.sha256` | Manifest only — 72 files / 58 unique across checklist sections A-J. Certificates, grid-forming letters, PSS(R)E and PSCAD models, fire-safety package, independent bankability study, filled Volume 2 GTP, grid-compliance list. Binaries held outside the repository |

The files are stored byte-for-byte from the supplied originals. SHA-256 checksums are recorded
in `MANIFEST.sha256`.

The RFP files, **Addendum No. 01, Annex A and the clarification register** are the controlling
procurement sources in this package. OEM documents and supplier declarations are proposal evidence
only. Where a controlling document and an OEM document conflict, the controlling document governs;
where Addendum 01 amends an RFP volume, the Addendum governs. **Annexes B, C and D and any
subsequent addenda remain outstanding** — Annex B (Grid Connection Code requirements) and Annex D
(measurement indicators) are both referenced by clauses evaluated in this corpus.

## Reviews and derived material

| Document | Repository path | Role |
|---|---|---|
| Initial Envision offer gap review | `reviews/Envision_Offer_Gap_Review_2026-07-30.md` | Preliminary issue identification against the tender package |
| Detailed Envision gap statement | `reviews/Envision_NSO_250MW_BESS_Detailed_Gap_Statement_2026-07-31.pdf` | Tender-response improvement requirements, design-calculation critique, evidence matrix, OEM dossier and closure plan |
| 11 MW / 44 MWh and checklist ingress evaluation | `reviews/Envision_11MW_44MWh_and_Functional_Checklist_Ingress_Evaluation_2026-08-06.md` | Source QA, complete normalized performance curve, checklist status analysis, comparison and closure requirements |
| NSO 250 MW checklist dossier ingress evaluation | `reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md` | Full evaluation of the 21 August dossier: 15 findings, evidence-register movement, recovered technical reference data, recommended actions and handling classification |
| **Addendum 01 / Annex A / clarifications ingress evaluation** | `reviews/NSO250MW_Addendum01_AnnexA_Clarifications_Ingress_Evaluation_2026-08-27.md` | Evaluation of the three controlling documents: **three corrections** to the 21 August review (the dual-mode grid-forming instruction is withdrawn; the SCR sweep is not a bid-stage requirement; the closing date is 4 September), ten new findings, revised evidence register and revised pre-submission punch list |

These reviews are derived analysis, not controlling tender or OEM documents. When a review
conflicts with a source file, the source file governs. The detailed gap statement and the 6 August
evaluation derive from Envision material and retain the source classification for provenance.
Public publication of the earlier and newly ingressed material is authorised as recorded above
and in `PUBLICATION_AUTHORIZATION.md`.

Searchable MarkItDown extracts of the two 6 August ingress sources are under
`oem/envision/extracted/`. They are derived discovery aids and never supersede the received
PDF or workbook.

## OEM compliance evidence status

The package now contains two distinct Envision design calculations and one functional-
requirements checklist. The checklist declares 48 `Yes`, 7 `No` and 1 `Partial` results across
56 selected Annex A/B rows. It has no tender identifier, signatory, revision, evidence-reference
column or attached evidence dossier, so its declarations are not treated as verified compliance.

The repository already contains a redacted, non-executable grid-code parameter fixture at
`tests/fixtures/grid/envision_enpcs01_gridcode.yaml`; that fixture identifies the referenced PCS
as grid-following and explicitly says the proprietary model binaries are not committed.

No certificates, type-test reports, certified grid-forming models, PSCAD/EMTDC model, executable
PSS(R)E model, model guides, single-line diagram, fire-safety package, capacity-maintenance plan
or the test report mentioned in the checklist were supplied. The evidence register in
`oem/envision/compliance_evidence/README.md` tracks declarations separately from underlying
artifacts and does not represent an unsupported checkbox as received evidence.

## Integrity and update procedure

1. Preserve received documents without editing or re-exporting them.
2. Add a new version alongside the prior version rather than overwriting evidence.
3. Record the source, received date, document date/version, confidentiality and SHA-256 checksum.
4. Update the compliance-evidence register only when the underlying artifact is committed.
5. Do not treat in-house analytical screens as substitutes for OEM or utility-certified evidence.
