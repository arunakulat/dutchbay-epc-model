# NSO 250 MW / 1000 MWh standalone BESS source package

This directory preserves the controlling procurement documents and the available Envision
design material for National System Operator tender `TR/REP&PM/ICB/2026/001/C`.

## Handling classification

- The NSO tender documents are procurement source records.
- The Envision design calculation is marked **confidential and privileged** by Envision Energy.
  That original marking is retained in the file for provenance.
- On 31 July 2026, the project owner confirmed that Envision authorised publication of the
  Envision content in a public GitHub space, including the design calculation and derived gap
  statement in this corpus. This records permission for the repository publication; it does not
  imply a transfer of copyright or a broader licence beyond the permission received.

## Controlling documents

| Document | Repository path | Role |
|---|---|---|
| Paper advertisement | `rfp/NSO_250MW_BESS_Paper_Advertisement_Final.pdf` | Procurement notice and submission deadline |
| RFP Volume I | `rfp/NSO_250MW_BESS_RFP_Volume_I_Final.pdf` | Instructions, qualification and technical requirements |
| RFP Volume II | `rfp/NSO_250MW_BESS_RFP_Volume_II_Final.pdf` | Proposal letters, compliance schedules and forms |
| RFP Volume III | `rfp/NSO_250MW_BESS_RFP_Volume_III_ESA_Final.pdf` | Model Energy Storage Agreement |
| Envision design calculation | `oem/envision/Envision_10MW_40MWh_Design_Calculation_V1.0_2026-07-29.pdf` | Available OEM design and performance calculation |

The files are stored byte-for-byte from the supplied originals. SHA-256 checksums are recorded
in `MANIFEST.sha256`.

## Reviews and derived material

| Document | Repository path | Role |
|---|---|---|
| Initial Envision offer gap review | `reviews/Envision_Offer_Gap_Review_2026-07-30.md` | Preliminary issue identification against the tender package |
| Detailed Envision gap statement | `reviews/Envision_NSO_250MW_BESS_Detailed_Gap_Statement_2026-07-31.pdf` | Tender-response improvement requirements, design-calculation critique, evidence matrix, OEM dossier and closure plan |

Both reviews are derived analysis, not controlling tender or OEM documents. When either review
conflicts with a source PDF, the source PDF governs. The detailed gap statement derives from and
reproduces information in the Envision design calculation and retains confidentiality markings
for provenance. Public repository publication is authorised as recorded in the handling
classification above.

## OEM compliance evidence status

The design calculation is the only separate OEM document found in the supplied local folders.
The repository already contains a redacted, non-executable grid-code parameter fixture at
`tests/fixtures/grid/envision_enpcs01_gridcode.yaml`; that fixture identifies the referenced PCS
as grid-following and explicitly says the proprietary model binaries are not committed.

No certificates, type-test reports, certified grid-forming models, PSCAD/EMTDC model, executable
PSS(R)E model, single-line diagram, fire-safety package, or capacity-maintenance plan were found.
The evidence register in `oem/envision/compliance_evidence/README.md` tracks those outstanding
items without representing them as received.

## Integrity and update procedure

1. Preserve received documents without editing or re-exporting them.
2. Add a new version alongside the prior version rather than overwriting evidence.
3. Record the source, received date, document date/version, confidentiality and SHA-256 checksum.
4. Update the compliance-evidence register only when the underlying artifact is committed.
5. Do not treat in-house analytical screens as substitutes for OEM or utility-certified evidence.
