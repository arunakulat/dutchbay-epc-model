# PR #1336 D1 assurance review — round 4 final

- Reviewer: independent contract, provenance and failure-mode assurance reviewer,
  `/root/pr1336_d1_assurance_final_20261009`
- Candidate: `33dcef961820bafc670eb215e142da24acb790f2`
- Tree: `68a108a0a99f697321574be4e0cb1e1ca5a71455`
- Base and merge base: `cdc4146c92320b15ae4ec6fe025224286b2c9732`
- Canonical subject manifest: 13 rows, 1047 bytes, SHA-256
  `ee8d127fdbbd1a31d2eaef1c428b36d657dacb215dea9eeeeaf5dc57c9ad5953`
- Disposition: `ACCEPT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

The reviewer independently reconstructed the subject manifest, matched the exact Git and GitHub
head, tree, base, merge base and clean topology, and read the complete D1 source, tests, records,
governance corpus, live issues and pinned OpenOA v3.2 comparator. The reviewer was distinct from
the writer, coordinator and domain reviewer and did not seek or inspect the concurrent final domain
conclusion.

All thirteen subject blobs were byte-identical to pre-refresh head
`ec632e4005acefd6b264a1fada44bd00d9869e73`. The complete refresh delta contained only the eight
PR #1341 security paths and was bidirectionally isolated from D1 imports and normative behavior.

## Independent evidence

The GWTF bootstrap passed all 74 active rules. Cache-disabled focused tests passed
`103 passed in 47.11s`; strict mypy passed both production modules; `git diff --check` passed. An
independent production-only oracle exercised purpose minima, cadence boundaries, permitted and
refused calendar routes, fifteen split-product counterexamples, portable and hostile timezone
keys, missing timezone data, lineage collisions, status-by-kind and mixed-status refusal, full
coverage, malformed inputs, public-facade identity, nested immutability, JSON serialization and all
canonical-finance/bankability/lender/Board fences.

The broader contract-suite rerun was stopped at the coordinator's request after 263 passing tests
so the reviewer could conclude; no complete result is claimed from that reviewer run. The
coordinator separately completed all 1,496 contract tests, and hosted exact-head CI later reached
terminal green. The reviewer's tracked worktree and index remained clean. A coordinator audit
found no ignored cache timestamp after the earlier disqualified reviewer's known mypy-cache write,
which is consistent with this assurance reviewer's no-mutation attestation.

## Reconciliation and residuals

The operational-layer absence is closed within D1's declaration scope. `D1-DOM-001` through
`D1-DOM-006`, `A-01`, `A-02`, `A2-01`, `A2-02`, `D1-DOM-006-R3`, `A3-01`, the D1/D2 boundary and
base-refresh continuity are closed for this exact subject. The false BESS-gap premise is not
applicable.

Issue #1332 owns deterministic ingestion and QA of actual bytes, row counts, timestamps, DST
conversion, gaps, duplicates, non-finite values, cadence drift and lineage recomputation. A fixed
31-day declaration remains only a ceiling, not proof of calendar-consistent observations. These
are named downstream duties and do not block the D1 declaration contract.

The disposition accepts only this exact D1 subject as one member of the R2 review pair. It grants
no merge, release, publication, issue closure, deployment, professional sign-off, canonical
finance, bankability, lender, Board or HOLD authority. Issue #1110 remains open and its Board/lender
circulation HOLD remains active.
