- **Advisory issue of the NSO 250 MW gap register** —
  `docs/source_materials/nso_bess_250mw_2026/registers/render_advisory_issue_2026-08-27.py` renders
  a second, bidder-neutral issue of the same register for release to a bidder other than the one it
  was raised for. It imports the register unchanged and applies exactly three changes: the raising
  label becomes the advisory group; two statements true only of the original recipient are
  de-attributed (gap A6's "the bidder asked ... at clarification 64", and the closure pathway's
  "the bidder holds both models"); and an *Issue and reliance* section is added. The two documents
  are rendered from one source and cannot drift. The script **fails loudly** if either de-attributed
  passage moves, rather than silently emitting a document that misattributes a clarification
  question — a guard that has already fired in anger. The rendered issue is committed beside the
  internal dossier.
- **Session archive** — `reviews/NSO250MW_Session_Archive_2026-08-29.md` records the state at close,
  the findings that matter before the 4 September deadline, the recorded publication reversal, and
  three stated limitations: two OCR extract gaps, five sandbox-only watchdog test failures that CI
  cannot warn about, and the fact that **neither corpus manifest is covered by a test** — a stale or
  incomplete manifest passes CI silently, and two such defects were found and repaired by hand.
  Corpus manifest: 108 -> 111 entries, all verifying.
