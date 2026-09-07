# RECRUIT-01 module 3 — independent review and exact-object attestation

**Status:** canonical operational sub-module of GWTF `RECRUIT-01`

## 1. Independence

An implementation worker does not self-approve. Required reviewers must be distinct from the writer,
coordinator, and each other; one worker cannot supply both required dispositions. A repeated pass by
the same worker may correct or deepen its own record but does not become a second independent review.

Reviewers remain read-only: no file, index, ref, branch, worktree, PR, issue, release, or other
external-state mutation. Each reviewer returns an initial disposition independently before being
shown or anchored by the other reviewer's conclusion. The coordinator reconciles disagreement only
after both dispositions exist. One veto blocks acceptance.

A read-only pre-implementation design challenge is allowed for `R2`/`R3` work and may expose likely
failure modes before code exists. It is advisory and never substitutes for the fresh post-freeze
exact-object disposition.

## 2. Frozen subject manifest

Before review, the coordinator freezes and reports:

- candidate commit and tree;
- protected base and merge base;
- clean index/worktree state;
- exact changed paths;
- a deterministic subject manifest of sorted `path<TAB>git-blob-SHA` entries for every substantive
  implementation, test, configuration, schema, changelog, and substantive documentation object,
  including governance modules and implementation records;
- governing charter/rule identities and applicable predecessor findings; and
- writer receipts, limitations, HOLDs, and declared checks not run.

A disposition naming no exact object is not a disposition. Acceptance never transfers to changed
subject bytes.

## 3. Review method

A reviewer reads the relevant source and test bodies; passing counts alone are not evidence of
coverage. Each load-bearing review must include at least one independent positive/negative oracle,
hostile counterexample, predecessor-finding replay, invariant proof, or an explicit bounded reason
why source-level analysis is sufficient. Merely rerunning writer-authored tests is supplementary.

Applicable predecessor findings are dispositioned in a matrix with: finding ID, applicability,
probe/evidence, and `CLOSED`, `RECURS`, `DEFERRED`, or `NOT_APPLICABLE` result.

## 4. Structured disposition receipt

Every review record contains:

```text
reviewer_role
reviewer_identity
candidate_commit
candidate_tree
base_sha
merge_base_sha
subject_manifest_sha256
corpus_and_rule_identities
review_scope
checks_executed_and_exact_results
independent_oracles_or_counterexamples
predecessor_finding_matrix
findings_and_residual_limitations
hold_and_authority_effect
disposition
mutation_attestation
```

Narrative detail may follow. The structured fields must remain machine-readable enough for a
focused policy test or future required check.

## 5. Findings ledger

Every finding receives one explicit state:

- `BLOCKS_CURRENT_CANDIDATE`;
- `ACCEPTED_RESIDUAL_WITHIN_SCOPE`;
- `DEFERRED_TO_NAMED_DOLPHIN`;
- `TRACKED_IN_NAMED_ISSUE`;
- `NOT_APPLICABLE_WITH_REASON`; or
- `SUPERSEDED_BY_SUCCESSOR_FINDING`.

A deferred finding names an owner, destination, why it does not block now, the future acceptance
gate, and its `HOLD` effect. `NO BLOCKER` never silently discards a finding.

## 6. Review records without SHA recursion

The substantive disposition binds to the frozen subject manifest. The coordinator may then add only
allowlisted review records and delivery metadata in a documentation-only receipt commit. Both
reviewers must rebind to the final delivery head after proving:

- all reviewed subject blobs are byte-identical;
- only named receipt/delivery files changed;
- receipt content accurately represents their dispositions; and
- base movement, if any, is separately dispositioned.

Open the PR before final rebind so its evidence channel exists. Persist the final rebind outside
the Git tree it attests to, with the reviewer identity, exact commit/tree/base, subject-manifest
digest, evidence identifier/URL, and content SHA-256. PR reviews, evidence comments and check runs
are not inherently immutable: treat the record as append-only, preserve its exact content in a
durable receipt, and verify its identity and content again at merge. An edit, deletion or mismatch
invalidates the rebind until the reviewer issues a new one. A later PERSIST-01 successor may mirror
that evidence after merge. If any subject blob changes, both
substantive reviews restart; the documentation-only shortcut does not apply.

## 7. Base movement and merge continuity

The 2026-09-02 base fast-forward carve-out remains mandatory. When the base advances purely to
satisfy the up-to-date-branch requirement, acceptance may carry forward only if all three proofs
are recorded in the PR:

1. **BLOB-HASH IDENTITY** for every file the reviewer judged, including documentation and files
   outside the changed-path list. An empty diff is not proof of matching object hashes.
2. **BIDIRECTIONAL IMPORT ISOLATION**: no changed module references a reviewed module and no reviewed
   module references a changed module. For non-code sources, also account for normative references
   and dependencies; if isolation cannot be established, require fresh review.
3. The **complete diff between reviewed and updated head**, shown in full, not a summary.

If any proof is absent, incomplete or fails, the disposition LAPSES. A judgement that a delta
cannot matter never substitutes for these artifacts. The exception covers only a base update;
any change to the candidate's own subject bytes requires fresh substantive review. After all three
proofs, reviewers bind the carry-forward disposition to the updated commit/tree/base and the
coordinator reruns the affected gates. No earlier acceptance silently transfers.

A squash merge creates a new commit identity. It preserves acceptance only when the protected merge
tree exactly equals the accepted final-head tree, expected ancestry is proven, and every required CI
check passed on the exact PR head. Otherwise merge verification fails closed.

Green CI is delivery evidence, not independent semantic review. Neither CI nor review lifts a
release, lender, Board, professional, evidence, deployment, publication, or `HOLD` boundary.
