- **Corpus manifest repaired** — `MANIFEST.sha256` recorded a `registers/__pycache__/*.pyc` bytecode
  file, added by #1226. `__pycache__/` is gitignored, so the file was never in the tree and never
  can be: `sha256sum -c` failed on `main` with `138 OK, 1 FAILED`, exit 1. Removed; the manifest
  verifies at `138/138 OK`, exit 0. This is the fourth manifest defect in this programme to reach
  `main` unnoticed because **no test covers either corpus manifest** — a stale, incomplete or
  impossible entry passes CI silently.
- **A structural coupling that keeps re-breaking it** — the parent manifest pins the SHA-256 of the
  nested `NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256`, so every edit to the nested file
  silently invalidates the parent unless both are updated in the same commit. That coupling has now
  produced a broken manifest twice in three commits on this branch alone. It is the direct argument
  for the test above.
- **Envision commercial offers silently revised, 4 September 2026** — both budgetary offers were
  supplied again carrying the **same version and submission date** as the 3 September copies, and
  their text **differs substantively in commercial terms**. Established by extracting both pairs
  with governed MarkItDown 0.1.7 (`R26`) and comparing, then confirming each finding by direct
  string search across all four documents rather than reading it off a diff. This repeats a pattern
  already on the record for this OEM, whose 5 August design calculation silently revised the
  29 July one while both were labelled V1.0.

  **The terms themselves are deliberately not reproduced in this public repository.** Clause 6 of
  both offers forbids the offer being communicated to any third party absent Envision's prior,
  explicit and written authorization; none is held. What changed, in what direction, and the full
  comparison are held in the private repository, whose analysis document is now pinned by SHA-256
  in the offers manifest so it cannot be revised without trace. Both sets of offer hashes are
  recorded there; neither issue automatically supersedes the other.
