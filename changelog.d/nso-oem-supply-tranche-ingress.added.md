Ingressed the OEM supply tranche received 27 August 2026 for NSO tender
`TR/REP&PM/ICB/2026/001/C`: **50 unique files** from 53 uploaded in the tranche, after de-duplication.

De-duplication by SHA-256 did real work. Six uploads were byte-identical repeats within the tranche
(the ENPCS 2520 specification, the electrical primary diagram and the Standards Compliance List were
each supplied twice). One file, the 11 MW / 44 MWh design calculation, is byte-identical to a copy
already committed and was not re-committed. Twenty-one files match hashes recorded in the
21 August dossier manifest — material previously held by manifest only is now actually in hand,
including the **superseding 5 August 10 MW / 40 MWh design calculation**, whose hash `5c619a2c…`
matches exactly what the 21 August evaluation recorded for a document it could identify but never
held.

Extraction followed GWTF R26. Thirty-seven files carried complete text layers and went through
governed MarkItDown 0.1.7; one certificate cover page was image-only and went through the OCR
branch; one file was a 39-byte plain-text note carried verbatim. One extract initially came back
empty and was re-run rather than accepted — it was a timeout artifact, not an image-only source.

Committed: 25 Envision-authored product, commercial and compliance documents plus the superseding
design calculation, with extracts. Withheld by manifest: 14 certification-body certificates and test
reports (certification-body and IECEE CB scheme copyright, per the 21 August policy) and 11 compiled
model binaries (publish never). One non-Envision third-party file is held separately with its
handling question recorded rather than resolved.

**No analysis or evaluation has been performed.** The gap register and the corpus reviews are
untouched, and this tranche has not been assessed against the tender.
