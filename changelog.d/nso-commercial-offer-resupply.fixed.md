- **Corpus manifest repaired** — `MANIFEST.sha256` recorded a `registers/__pycache__/*.pyc`
  bytecode file, added by #1226. `__pycache__/` is gitignored, so the file was never in the tree
  and `sha256sum -c` failed on `main` (138 OK, 1 FAILED). Removed; the manifest verifies again at
  138/138. This is the fourth manifest defect in this programme to reach `main` unnoticed because
  **no test covers either corpus manifest** — a stale, incomplete or impossible entry passes CI
  silently. Worth a test.
- **Envision commercial offers re-supplied, 4 September 2026** — the two budgetary offers were
  supplied again. They are the same logical documents as those recorded on 3 September (both
  Version 01, both dated 31 August 2026) but are **not byte-identical** to the recorded copies.
  Both hashes are added to `NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256` so the
  divergence is on the record; neither copy supersedes the other. Content remains **manifest only**
  on the established 3 September route: clause 6 of both offers forbids the offer being
  "broadcasted, published, or, more generally, communicated to any third party without prior,
  explicit and written authorization from Envision", no such instrument is held, and this
  repository is public. Offer validity is 30 days from 31 August 2026, so both lapse on
  30 September 2026.
