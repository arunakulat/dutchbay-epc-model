- **Corpus manifest repaired** — `MANIFEST.sha256` recorded a `registers/__pycache__/*.pyc`
  bytecode file, added by #1226. `__pycache__/` is gitignored, so the file was never in the tree
  and never can be: `sha256sum -c` failed on `main` with `138 OK, 1 FAILED`, exit 1. Removed; the
  manifest verifies at `138/138 OK`, exit 0. This is the fourth manifest defect in this programme
  to reach `main` unnoticed because **no test covers either corpus manifest** — a stale, incomplete
  or impossible entry passes CI silently.
- **The coupling behind it** — the parent manifest pins the SHA-256 of the nested
  `NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256`, so an edit to the nested file
  invalidates the parent unless the same commit refreshes it. One committed tree on this branch
  failed that way, and it failed in the worse manner: `FAILED` on a *present* file, which in an
  evidence corpus is the signal reserved for content having been altered, rather than the absent
  file the base defect described. It is the direct argument for the test above, and it is now
  written up as a pre-commit checklist in `AGENTS.md`.
- **Envision commercial offers silently revised, 4 September 2026** — both budgetary offers were
  supplied again carrying the **same version and date** as the 3 September copies ("Version: 01",
  "Date of Submission: August 31, 2026"), but their text **differs substantively**. Verified by
  extracting both pairs with governed MarkItDown 0.1.7 and confirming each finding by direct
  string search across all four documents, not by reading a diff.
  - the **10 MW offer's BESS warranty was cut from 5 years to 2 years**, while the 11 MW offer's
    stayed at 5 years. The edit did not reach the 10 MW executive summary, which still promises
    "5 years' BESS Warranty", so that document is now internally inconsistent;
  - the scope note *"PCS and AC equipment are not included in supply scope"* was **removed from
    both** offers, resolving a contradiction against their own price tables, which charge
    separately for "PCS & MV Transformers";
  - **both headline prices are unchanged**, so on the 10 MW offer the price held while the
    warranty was reduced;
  - this repeats a pattern already on the record for this OEM, whose 5 August design calculation
    silently revised the 29 July one while both were labelled V1.0.
- **Handling of that finding, now stated once** — the offer documents are not in this public
  repository and never have been; both sets of hashes are recorded and the comparison establishing
  the revisions is pinned by SHA-256, so the analysis cannot be revised without trace. Neither
  issue automatically supersedes the other. Everything else about how the package is handled —
  what this repository does and does not disclose about the offers, on whose decision, and why
  that route was chosen — is stated in exactly one place: the header of
  `docs/source_materials/nso_bess_250mw_2026/source_packages/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256`,
  under the identifier `NSO250MW-OFFERS-HANDLING-2026-09-04`. It had been written out in five
  places; the five copies disagreed with each other, and every blocking finding of two RECRUIT-01
  reviews of this change was one of those disagreements. The READMEs and this fragment now cite
  the identifier instead of restating it.
