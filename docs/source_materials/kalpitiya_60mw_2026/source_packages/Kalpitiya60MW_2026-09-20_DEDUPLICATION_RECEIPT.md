# Kalpitiya 60 MW Envision wind package — deduplication receipt

Prepared for the re-supply received **20 September 2026 at 16:18 UTC**: two loose PDFs.

Handling of this package is stated once, at `KALPITIYA60MW-WIND-HANDLING-2026-09-21` in the
header of [`Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256`](Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256).
This receipt cites that identifier and does not restate it.

## Result: zero new payload

| Field | Receipt |
|---|---|
| Received | 20 September 2026, 16:18 UTC, two loose PDFs |
| Payload files | 2 |
| Unique payload SHA-256 values | 2 |
| **New payload values versus the package already held** | **0** |

Both files are byte-identical to documents already held. Nothing was ingressed a second time, and
nothing in the manifest changed as a result.

## Member-level mapping

| Supplied file | Bytes | SHA-256 | Canonical object |
|---|---|---|---|
| `EN206-10.5MW Power Curve and Thrust Coefficient of Envision_Sri Lanka Kalpitiya 60MW Project_V20260907.pdf` | 328,834 | `9d21b053b2636f1d384e7b4235775402bdd289ce29c063df85dd162e8417ce8c` | `raw/Envision_EN206-10.5_Power_Curve_and_Ct_PMD-004447_RevA_2026-09-07.pdf` |
| `Sri Lanka Kalpitiya 60MW Project_6 x EN206-10.5derated from 11MWProposal Solution  Technical Alignment_HH130_V20260907.pdf` | 591,780 | `845d3df5c0310b39e42ca4ff729f3eb8c11691aa76c77f7a5416c0dc6adc6d19` | `raw/Envision_Kalpitiya_60MW_Proposal_Solution_and_Technical_Alignment_2026-09.pdf` |

Canonical paths are relative to `corpus/kalpitiya_60mw_2026_envision_wind/` in the private
repository, as recorded in the manifest.

## Why the supplied filenames are recorded verbatim

A deduplication receipt that does not name what arrived cannot be checked by anyone later, so the
supplied filenames are reproduced above. They carry more configuration metadata than the canonical
names do — unit count, hub height and the de-rate — and that disclosure is covered by item 3 of
the handling note rather than being made silently.

They also carry something the documents themselves do not. **The proposal PDF has no document
number and no revision on its face**, so the token `V20260907` in the supplied filename is the only
version label attached to that document anywhere. It is not evidence of a revision — the bytes are
identical to the copy already held — but it is the first version label this document has had, and
it arrives from a filename rather than from the document.

That matters because of a pattern already on this project's record: on 4 September 2026 the same
issuer supplied two commercial offers carrying the *same* version and submission date as earlier
copies while differing substantively in their terms. Version and date do not identify a document
here. A hash does, which is the whole reason this manifest exists.

## What was and was not done

- **Ingress, conversion and evaluation** were completed on the earlier, byte-identical copies and
  are held privately. They were not repeated.
- **Deduplication** is this receipt.
- **The addition to this repository** is the manifest-only record in this directory.
