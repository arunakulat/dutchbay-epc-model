- **The Kalpitiya 60 MW Envision wind package is now recorded** —
  `docs/source_materials/kalpitiya_60mw_2026/`. A proposal and energy yield study for a 63.0 MW
  wind farm, and the turbine performance document behind it, both received 20 September 2026 and
  dated 7 September. It is the first wind material in the source corpora; everything else under
  `docs/source_materials/` is the NSO 250 MW BESS programme.
- **The record is manifest-only, and the documents are not here.** They are held in the private
  repository `arunakulat/DutchBay_RAG`. One is marked Confidential on every page of a Released
  controlled document; the other carries an express bar on reproduction without written
  permission. No authorization instrument is held for either, this repository is public, and a
  push to it cannot be taken back. Route already set twice in this corpus, for the 21 August
  checklist dossier and the 3 September commercial offers.
- **Handling is stated once**, at `KALPITIYA60MW-WIND-HANDLING-2026-09-21` in the package
  manifest header, and cited — never restated — by the two READMEs and the deduplication receipt.
  Unlike the offers manifest, this one recites no figure from either document. What the filenames
  alone still disclose is written down rather than glossed over.
- **The 20 September re-supply carried zero new payload.** Two PDFs, both byte-identical to copies
  already held. The receipt records it, and records that the as-supplied filename is the only
  place a version token exists for the proposal — the document itself carries no number and no
  revision. This issuer has already supplied substantively revised documents under an unchanged
  version and date, so a hash is the only identifier that holds.
- **Recorded is not accepted.** Nothing here has entered a scenario, a model input, a baseline or
  a report, and it should not until the issuer answers in writing which power curve produced the
  energy yield appendix and what the wind data provenance and uncertainty basis are.
- **Two declarations, both forced by the guard rather than trusted.** The package manifest is
  registered in `NESTED_EXTERNAL` — its subject is held elsewhere, so its recorded paths are never
  resolved against this tree — and its handling anchor in `HANDLING_ANCHORS` with the three files
  that cite it. Since #1289 neither is optional: forgetting the first fails
  `test_every_nested_manifest_is_classified`, forgetting the second fails
  `test_every_handling_note_in_the_tree_is_registered`. Both were removed in turn and observed to
  fail before this landed.
