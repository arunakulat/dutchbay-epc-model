# RECRUIT-01 module 3 — independent review and exact-object attestation

**Status:** canonical operational sub-module of GWTF `RECRUIT-01`

## 1. Independence

An implementation worker does not self-approve. Required reviewers must be distinct from the writer,
coordinator, and each other; one worker cannot supply both required dispositions. A repeated pass by
the same worker may correct or deepen its own record but does not become a second independent review.

A reviewer supplies findings, not subject bytes. Where a reviewer demonstrates a gap with code — a
test, a patch, a command — that snippet is a description of the gap, and the writer reimplements it
in its own terms rather than committing the reviewer's lines. A writer that adopts them verbatim
makes that reviewer a co-author of the subject, so that lane's disposition on those bytes is a pass
over its own work rather than an independent review. Reimplementing is what keeps the lane eligible
to review the result, which is the point: the reviewer who found the gap is usually best placed to
judge whether the writer's own version closes it. The finding stays credited to the reviewer; the
implementation is the writer's.

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

## 8. Merge trains (`TRAIN-01`)

A merge train lets two or three reviewed pull requests, the cars, share one full-suite run and still
land as separate commits on `main`. This section is how a car's disposition reaches the train head and
how the landing is verified. It adds a second carry-forward beside §7 and does not change §7.

**Carry-forward.** A car's disposition, bound to its frozen draft head, carries onto the train head
only when its lane records all three of §7's proofs, applied to the train:

1. **BLOB-HASH IDENTITY** for every file the lane judged, between the car's reviewed head and the
   train head.
2. **BIDIRECTIONAL IMPORT ISOLATION** between the car and everything else the train head changes,
   meaning the other cars and any advance of `main`. For non-code sources, also account for normative
   references and dependencies. Count shared runtime inputs as dependencies too: a scenario or
   configuration file, a test fixture, a `conftest.py`, `pyproject.toml`, `VERSION`, a module that
   `tests/conftest.py` loads, an installed library, or anything else that two cars' code or tests
   both read. A shared runtime input links the car to another part of the train head only when one
   side changes bytes in it that the other side's code or tests consume. Loading a file is not
   consuming the bytes changed in it. A module that every test imports through `tests/conftest.py`,
   in which one car changes a constant that the other car never reads, is not a link once the
   consumption artifact below shows that. Whether
   changed bytes are consumed is shown by that artifact, never by a judgement.
   Path-disjoint cars that share an input whose changed bytes are consumed are not isolated, and
   neither are cars whose consumption artifact is missing or incomplete.
3. The **complete diff from the car's reviewed head to the train head**, shown in full, not a summary.

**Consumption artifact.** For every runtime input that one side changes and the other side's code or
tests read, the lane records the artifact in both directions: whether the car consumes what the rest
of the train head changes, and whether the rest consumes what the car changes. A side is a car or an
advance of `main`. Anyone may produce the artifact, and the lane re-runs what it needs before relying
on it. It has three parts, and any hit or difference is a link:

- **The changed bytes:** the input's full diff, and the names, keys, lines or distribution versions
  that it changes.
- **A reference search:** every reference to those names, keys and distributions in the other
  side's changed files and test selection, each hit listed with its file and line. A hit is a link
  even when the test that holds it would pass either way.
- **A differential run:** a side's test selection run on two trees that differ only by the other
  side's changes. Each car's selection runs on `main` plus that car alone and on the train head, which
  differ only by the other cars; because every car records its own pair, the pairs cover both
  directions between cars. Where `main` has advanced past a car's reviewed base, the car's selection
  also runs on its reviewed head and on `main` plus the car, and the advance's selection runs on
  `main` and on `main` plus the car. Both runs of a pair must collect the same test IDs with the same
  outcomes. Where a side changes the lock or an installed library, each run uses an environment
  installed from its own tree's lock.

A side's test selection is the test files it adds or changes, and every test file whose own import
statements name a module it changes. An empty selection is recorded as empty, and the reference search then
carries the direction alone. §7's proof 2 for a single pull request's base advance is unchanged:
this narrower link test applies only to a train.

If any proof is absent, incomplete or fails, the car leaves the train and its disposition stays bound
to its own head. A judgement that another car cannot matter never substitutes for these artifacts.
The cars are never edited on the train branch. A fix belongs on the car's own branch, which is a
subject change, so §6 restarts both of the car's reviews.

**Landing check.** Run the pre-landing check twice: on the built train before it is opened ready, so a
mis-built train never spends a full-suite run, and again just before landing. Each time, record the
protected `main` SHA, which must be `origin/main` at that moment. The train head's commits must form a
chain of non-merge commits, one per car, whose first parent is that `main` SHA. **Each train commit
must be exactly its car's reviewed diff:** it changes the same paths that the car's reviewed head
changes from its merge base, with the same modes and blobs. Compare both old and new modes and blob IDs, change status, and
every path byte using unambiguous framing. Its message and author equal the car's
recorded merge message and author, where the author is the car pull request's author as a squash
merge of that pull request would record it, and its subject ends with that car's pull-request number.
Each car's reviewed head must still be its pull request's head, so a car list that pairs a number with
another car's head fails. The three proofs above compare trees, so they cannot say which commit carries
which car. Without this check, a train whose cars' messages were swapped, or whose commit for one car
also carries a stray file or part of another car, passes every tree comparison. It would then land
under the wrong message on a `main` whose history is never rewritten, and reverting one car would
revert another. If `main` moves before landing, the train is rebuilt from the new `main`, never
refreshed with a merge commit, and the three proofs and the pre-landing check are repeated on the new
train head. The train lands by rebase-merge, never squash. After it lands, verification passes only
if:

- the SHA the merge returned equals the freshly fetched `origin/main` tip, so a side-parent or
  stale reachable commit cannot substitute for the protected landing; reconcile before proceeding
  if protected main has advanced again;
- the landed commits contain no merge commit;
- each landed commit's tree, message and author equal those of the matching train commit;
- each landed commit's parent is the previous landed commit, and the first one's parent is the
  recorded `main` SHA; and
- the last landed commit's tree equals the train head's tree.

Any mismatch fails merge verification closed, exactly as a squash whose tree differs from the accepted
head does under §7. The commands that run these checks must fail closed on their own: each stops at its
first failed comparison and reports success only with an explicit line. A check that passes in silence
is not a check.

**What a train does not prove.** The full suite ran on the union of the cars. The intermediate commits
between cars on `main` were never run by the full suite on their own, which is why the cars must be
path-disjoint and import-isolated. The differential run narrows that gap without closing it: each
car's own test selection ran on `main` plus that car alone, but the rest of the suite did not. A train lifts no `HOLD`, and it confers no release, lender, Board,
professional, evidence, deployment or publication authority.
