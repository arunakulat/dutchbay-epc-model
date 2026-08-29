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
| OEM supply tranche — **now committed in full** | [`NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256`](NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256) | 27 Aug 2026 | 25 (14 certificates + 11 binaries), plus 13 derived extracts | [`../reviews/NSO250MW_Addendum01_AnnexA_Clarifications_Ingress_Evaluation_2026-08-27.md`](../reviews/NSO250MW_Addendum01_AnnexA_Clarifications_Ingress_Evaluation_2026-08-27.md) |

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


## OEM supply tranche, 27 August 2026 — committed in full

The tranche delivered **50 unique files**. All of them are now tracked in this repository.

| Group | Count | Location |
|---|---|---|
| Envision-authored product, commercial and compliance documentation, plus the superseding design calculation | 25 | `../oem/envision/` |
| Certification-body certificates and test reports | 14 | `../oem/envision/compliance_evidence/certificates/` |
| Compiled model deliverables (`.dll`, `.obj`, `.lib`, `.pscx`, `.dyr`) | 11 | `../oem/envision/dynamic_models/` |

One further file, `Technical_Requirement_Lakdhanavi_v1.xlsx`, is neither Envision-authored nor a
tender document; it is held at `../third_party/` with its handling question recorded rather than
resolved. See that directory's README.

### This reverses the position stated above, on recorded authority

The two right-hand groups were previously **manifest only**, and the text of this file said the
compiled binaries were *publish-never regardless of authorisation*. That was the analyst position,
not the owner's. On 27 August 2026 the project owner directed, in writing and as project owner,
that the copyright and publish-never restrictions be overridden because the material forms part of
the bid submitted to NSO, and that all of it — expressly including personal data — be committed.

The reversal is recorded rather than quietly applied, so that anyone reading this file later can
see that the restriction existed, who lifted it, and on what stated basis.

**This repository is public.** Committing here is publication, not storage. The distinction drawn
earlier in this file — that a *private* repository is ordinary use of material the bidder received,
whereas publication is a separate question — is the distinction the owner's direction overrides.

### Personal data, established by inspection

Four individuals are named, all in professional capacity on the face of the certificates, none with
any contact detail:

| Name | Capacity | Document |
|---|---|---|
| David Piecuch | UL Mark Certification Program Manager | `27_CERT_UL_1973_2022_CELL_HC-L755A.pdf` |
| Thomas Wilson | UL Solutions CB certificate signatory | `17c_CERT_IEC_62619_2022_CELL_HC-L755A.pdf` |
| Jiajun Zhang | Project Engineer, "tested by" | `37_COVER_ENPCS2520_IEEE_519.pdf` |
| Allen Hu | Authorizer, "authorized by" | `37_COVER_ENPCS2520_IEEE_519.pdf` |

These are the certifying officers whose names appear on any copy of these certificates, including
copies obtained from the certification bodies directly. The earlier README entry warning of "named
individuals' signatures" referred to an **overseas system-operator contingency-reserve test record**
in the *21 August* dossier, which is a different document and is not in this tranche.

### Derived text extracts

Thirteen of the fourteen certificates have MarkItDown/OCR extracts at `../oem/envision/extracted/`.
Two gaps, stated rather than papered over:

* `36_COVER_ENPCS2520_IEC_60068-2-30_78.pdf` — no extract; conversion produced nothing.
* `21_CERT_IEC_63056_2020_EN_62477-1_2022_RACK.pdf` — extract is empty; the PDF is an image-only
  scan and was not OCR'd successfully.

Both source PDFs are committed, so the gap is in the discovery aid, not in the corpus.

### Compiled binaries — what can and cannot be read from them

`.dll`, `.obj` and `.lib` are compiled. `scripts/analysis/extract_oem_dynamic_models.py` recovers
symbol and path metadata from them and is explicit that **the control law itself is not recoverable
and no attempt is made to recover it**. The `.dyr` and `.pscx` are text and are read in full by the
same tool. Committing the binaries makes them archivable and hash-verifiable; it does not make them
executable in this repository's CI, which has neither PSS(R)E, PSCAD nor an Intel Fortran compiler.
