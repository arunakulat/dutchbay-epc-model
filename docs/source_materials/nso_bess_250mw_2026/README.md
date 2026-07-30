# NSO 250 MW / 1000 MWh standalone BESS source package

This directory preserves the controlling procurement documents and the available Envision
design material for National System Operator tender `TR/REP&PM/ICB/2026/001/C`.

## Handling classification

- The NSO tender documents are procurement source records.
- The Envision design calculation is marked **confidential and privileged** by Envision Energy.
  Its notice prohibits unauthorised review, use, disclosure, or distribution without written
  consent. Keep the GitHub repository private and restrict access to authorised project
  participants.
- Do not copy the Envision document into public releases, generated Sites assets, container
  images, or unauthenticated downloads.

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

`reviews/Envision_Offer_Gap_Review_2026-07-30.md` is a derived review, not a controlling tender
or OEM document. When it conflicts with a source PDF, the source PDF governs.

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
