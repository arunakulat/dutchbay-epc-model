# PR #1336 D1 assurance review — round 3

- Reviewer: independent Python contract, provenance, failure-mode and delivery assurance reviewer,
  `/root/pr1336_assurance_review_refresh`
- Candidate: `f818a084d2ea0367aac18ca720577fb19327a826`
- Tree: `56a83dc1e06140e8f28c8f4d9e25d500172241e1`
- Base and merge base: `3b352034f74254af8b8baeb4d8cf9181ad252cb2`
- Subject-manifest SHA-256:
  `2136a8a0b47285b6238a6c722acceb1bebf67cc72d1fff6dc730f747243a702f`
- Disposition: `REJECT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

The reviewer reconstructed the eleven-blob manifest, matched GitHub/local/base identities, read all
subject files and governance sources, and remained blind to the current domain conclusion.

Independent checks passed 92 focused tests, strict mypy and `git diff --check`; AST-proved
standard-library-only production imports; exercised a 14-case zone matrix, 15 lineage negatives,
four facade surfaces, 12 numeric cadence boundaries and five reliance fences; and confirmed frozen,
JSON-serializable behavior. Observation-status and derived-lineage semantics, mixed-status
prohibition, cadence, single-product completeness and public exports were otherwise sound.

## `A3-01` — `BLOCKS_CURRENT_CANDIDATE`

`ZoneInfo(key)` established only that the current host could open some TZif object. It accepted
`localtime` and `posixrules`; the first can resolve to different rules on different hosts. The
`posix/*` and `right/*` implementation namespaces could similarly expose non-portable TZPATH
objects. This contradicted the candidate's claim to bind a reproducible named IANA zone.

The bounded correction is to reject host-relative and implementation-special keys and require a
portable region-style IANA key (or explicit `UTC`) before runtime availability validation. Positive
region controls and negative special-key controls are required, with predictable
`OperationalEvidenceError` behavior if no timezone database is available.

## Reconciliation and residuals

`A-01`, `A-02`, `D1-DOM-001` through `D1-DOM-004`, `A2-02` and `D1-DOM-006` were closed from this
assurance lane. `A2-01` / `D1-DOM-005` recurred through the special-key defect. Byte verification,
tzdb-version receipts and causal-lineage execution remain assigned to #1332.

Exact-head Security Scan was independently red during review because the mandatory security step
failed; that was a separate delivery blocker and not a semantic oracle.

This rejection granted no merge, release, issue-closure, lender, Board, professional, publication,
canonical-finance, bankability, deployment or HOLD authority. Issue #1110 remained open.
