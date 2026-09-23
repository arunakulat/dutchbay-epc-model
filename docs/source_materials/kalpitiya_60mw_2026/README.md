# Kalpitiya 60 MW — Envision wind proposal source package

This corpus area records the Envision Energy material received in September 2026 for a
**63.0 MW nameplate wind farm at Kalpitiya**: a proposal and energy yield study, and the turbine
performance document that underpins it.

It is the **first wind material** in the project's source corpora. Everything previously recorded
under `docs/source_materials/` is the NSO 250 MW standalone BESS programme.

## This area is manifest-only

No document from this package is committed here, and no extract of one. What this directory holds
is a **record**: the SHA-256 of every file in the package, so a future session can prove that a
re-supplied copy is the same artifact without the artifact ever being public, and so the
evaluation that exists elsewhere can be tied to the exact bytes it was written against.

The documents, their extracts, the derived data, the registers and the two evaluations are held in
the **private** repository `arunakulat/DutchBay_RAG`.

**How this package is handled is stated once** — where the documents live, what this repository
does and does not disclose about them, why that route was selected, and what the filenames alone
still give away — in the header of
[`source_packages/Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256`](source_packages/Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256),
under the identifier `KALPITIYA60MW-WIND-HANDLING-2026-09-21`. Read it there. It is deliberately
not repeated here: the equivalent statement for the NSO commercial offers stood written out in
five places on 4 September 2026 and the five copies disagreed with one another, which was a
blocking finding of the `RECRUIT-01` review of that change.

## Contents

| File | Holds |
|---|---|
| [`source_packages/README.md`](source_packages/README.md) | The packages table for this area |
| [`source_packages/Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256`](source_packages/Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256) | The handling note, and the SHA-256 of all 16 files held privately |
| [`source_packages/Kalpitiya60MW_2026-09-20_DEDUPLICATION_RECEIPT.md`](source_packages/Kalpitiya60MW_2026-09-20_DEDUPLICATION_RECEIPT.md) | The 20 September re-supply: two files, zero new payload |
| `MANIFEST.sha256` | This area's own integrity record, pinning each of the above |

## Status: recorded, not accepted

Nothing in this package has been promoted into a scenario, a model input, a baseline or a report,
and it should not be. The evaluation held privately leaves two questions that need a written
answer from the issuer first:

1. **Which power curve produced the energy yield appendix.** The appendix and the machine the
   proposal offers are not labelled consistently, and the difference is not cosmetic.
2. **What the wind data provenance and uncertainty basis are.** The study's own data source table
   lists no wind data, and it gives a P50 with no distribution around it, so it cannot enter a
   framework that sizes debt off P90.

The figures behind both are in the private evaluation, not here. This is a record of receipt, and
receipt is not acceptance.

## Integrity

`MANIFEST.sha256` records every file in this area. Verify with `sha256sum -c MANIFEST.sha256` from
this directory. `tests/lint/test_nso_corpus_manifest_integrity.py` runs that check in **both**
directions on every pull request, in the `fastlane` job — a file tracked here but absent from the
manifest fails just as loudly as a recorded file that has changed.
