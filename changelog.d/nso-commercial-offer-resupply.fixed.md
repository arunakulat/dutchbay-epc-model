- **Corpus manifest repaired** — `MANIFEST.sha256` recorded a `registers/__pycache__/*.pyc`
  bytecode file, added by #1226. `__pycache__/` is gitignored, so the file was never in the tree
  and never can be: `sha256sum -c` failed on `main` with `138 OK, 1 FAILED`, exit 1. Removed; the
  manifest verifies at `138/138 OK`, exit 0. This is the fourth manifest defect in this programme
  to reach `main` unnoticed because **no test covers either corpus manifest** — a stale, incomplete
  or impossible entry passes CI silently.
- **The coupling that keeps re-breaking it** — the parent manifest pins the SHA-256 of the nested
  `NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256`, so every edit to the nested file
  invalidates the parent unless the same commit refreshes it. That produced a broken manifest twice
  on this branch, and the second failure was the worse kind: `FAILED` on a *present* file, which in
  an evidence corpus is the signal reserved for content having been altered. It is the direct
  argument for the test above, and it is now written up as a pre-commit checklist in `AGENTS.md`.
- **Envision commercial offers silently revised, 4 September 2026** — both budgetary offers were
  supplied again carrying the **same version and date** as the 3 September copies ("Version: 01",
  "Date of Submission: August 31, 2026"), but their text **differs substantively**. Verified by
  extracting and diffing against the copies held in the private repository:
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

  Both sets of hashes are recorded
  in `NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256`; neither issue automatically
  supersedes the other. The offer **documents** are not in this public repository; they are held
  privately and recorded here by hash. The revised **terms set out above are disclosed** here, on
  the project owner's decision of 4 September 2026: clause 6 of both offers requires Envision's
  prior, explicit and written authorization before communication to a third party, no such
  instrument is held, and this repository is public. This entry is a disclosure of those terms,
  not a manifest-only record, and is labelled as one so it does not misdescribe itself.
