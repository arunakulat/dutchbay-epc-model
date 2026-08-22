# Source packages held outside the repository

Some received tender packages are recorded here by **manifest only**. The binaries stay in the
project owner's private working set and are not committed, because they contain material this
repository is not authorised to publish, or should not publish at all.

Each entry records what arrived, when, from whom, and the SHA-256 of every file, so a future
session can verify that a re-supplied copy is the same artifact without the artifact being public.

## Packages

| Package | Manifest | Received | Files | Analysis |
|---|---|---|---|---|
| NSO 250 MW checklist dossier | [`NSO250MW_checklist_2026-08-21.MANIFEST.sha256`](NSO250MW_checklist_2026-08-21.MANIFEST.sha256) | 21 Aug 2026 | 72 (58 unique) | [`../reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md`](../reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md) |

## Why the NSO 250 MW checklist package is manifest-only

`PUBLICATION_AUTHORIZATION.md` covers four specifically enumerated files from the 6 August 2026
tranche. It does not extend to this package. Beyond that, the package contains material that is
**not Envision's to authorise**, and material that should not be published under any authorisation:

| Content | Reason |
|---|---|
| Independent test-house cell bankability study | Test-house copyright; classified "CLIENT'S DISCRETION" where the client is **the battery affiliate**, not Envision |
| Customer reference letters | Third-party operators' own letterheads (state-owned and independent operators) |
| Certification-body certificates and test reports | Certification-body and IECEE CB scheme copyright |
| Compiled model binaries — `.dll`, `.obj`, `.lib`, `.pscx`, `.dyr` | Envision's compiled PCS/PPC control code. `tests/fixtures/grid/envision_enpcs01_gridcode.yaml` already records that these binaries are deliberately not committed. **Publish never.** |
| Overseas system-operator contingency-reserve test record | Bears named individuals' signatures — personal data. **Publish never.** |

If publication of any part is later desired, authorisation must be obtained **separately from the battery affiliate
and from the test house** for the bankability study, and the last two rows remain out of scope
regardless.

**Private hosting is a different question.** The table above concerns *publication*. Holding the
same material in a **private** repository is storage, not distribution, and is ordinary use of
material the bidder received for the purpose — so a private repository is an available home for the
full package including the binaries. The residual control there is access breadth: every
collaborator receives the whole dossier. Keep that list minimal and review it when the bid closes.

## Local location

The unpacked package, the MarkItDown/OCR extracts and the conversion logs are held at:

```
~/Downloads/SriLanka_250MW_NSO_ingress/
  raw/        received package, byte-for-byte as supplied
  extracted/  MarkItDown + tesseract OCR text extracts (derived discovery aids)
  logs/       conversion script, OCR script, checksum listing, comparison extract
  MANIFEST.sha256
```

Extracts never supersede the received original.
