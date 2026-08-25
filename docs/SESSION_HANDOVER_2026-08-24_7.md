# Session handover — 2026-08-24, successor 7

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-24_6.md`](SESSION_HANDOVER_2026-08-24_6.md).
Successor 6 remains authoritative for its P01 design, clean-room populations and historical
validation receipts except where this record replaces its now-stale delivery state.

## 1. Live repository, environment and coordination state

**Protected main at this authored cutoff:**
`961461a32d35f9a3c1e730688e13bd737e8c60de`.

**Active worktree for this handover dolphin:**
`/Users/aruna/Downloads/dutchbay-wt-1110-handover7`.

**Active branch:** `codex/1110-handover7`.

**Branch base:** exact `origin/main` at
`961461a32d35f9a3c1e730688e13bd737e8c60de`.

The governed environment remains
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, verified as Python 3.12.13.
Post-P02 shared-environment verification passed across protected `main` and the clean P02
candidate worktree with imports resolving from each active checkout. No checkout-local or
temporary Python environment was created.

This Codex task is rooted at `/Users/aruna/Downloads`, not the repository. The built-in
post-PR monitor is therefore blind under ENV-01. Git and GitHub operations must continue to
use explicit repository context, and the active worktree must remain first on `PYTHONPATH`.

The last successful full Codex-task inventory in this session found only this task active;
other relevant DutchBay tasks were idle or unloaded. Three later app-inventory refreshes
timed out without returning a new snapshot. Treat that timeout as a coordination coverage
boundary, not evidence that no task exists. At the P02 commit, PR and merge boundaries,
independent local checks found:

- no DutchBay editor, test, Hydra, pre-commit, Git mutation or overlay-builder process;
- no Git lock file;
- no movement of `origin/main` before the protected merge;
- no path overlap between P02 and any open pull request;
- only dependency pull requests #1128 and #1064-#1068 remained open; and
- no second repository worktree with overlapping unpublished files.

Re-run the mutable task, process, worktree, lock, PR and changed-path checks before every
future commit, push, PR update and merge. If the app inventory remains unavailable, disclose
the coverage boundary and do not replace it with an unsupported all-clear.

## 2. Programme status remains OPEN/HOLD

GitHub issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) is OPEN.
The controlled pack remains structurally `PASS` and release `HOLD`. No independent
`RELEASED` decision exists.

The published programme ledger still has:

- 23 pending programme gates;
- 56 pending architecture examinations and zero hash-bound examination results;
- 111 HOLD-blocking finding rows;
- 34 reproduction controls: 18 completed, 11 required-not-run and five unavailable;
- 42 primary-source records;
- F5-02 blocked on authenticated external transaction evidence; and
- Board/lender synthesis and circulation prohibited until the dependency chain and final
  independent release decision are complete.

F5-01 and F5-02 remain completely separate evidence, decision, implementation, test,
reconciliation, PR and rollback surfaces. Synthetic lender terms, synthetic ERA5/mast/MCP
profiles, QSTS software-path success and compile-only artifacts remain modelling or workflow
evidence only; none supplies bankable resource, utility-accepted feeder or lender evidence.

## 3. P01 protected delivery is complete; P01 review is not

PR [#1153](https://github.com/arunakulat/dutchbay-epc-model/pull/1153) was squash-merged as
`63b67eb62789da9ad712e9d0569737ec79988c65` from exact reviewed head
`959d63cd7ae9c8a2dd1fedc8d72d4fa95a7d03e5`.

The reviewed and merged trees were byte-identical at
`272e608c729a6b836d45df16f7903c142d90bd0a`. Exact-head CI recorded 17 successes,
three governed qualification skips and no live failure or pending check. Post-merge focused
recovery/pack testing recorded 53 passed, and the controlled validator returned `PASS/HOLD`.

P01 remains `pending_independent_review`. The implementer clean-room self-check cannot
satisfy the independent evidence-integrity reviewer requirement. Recovery proves governed
byte identity and portability; it does not authenticate third-party authorship, establish
semantic correctness, or authorize circulation.

Durable issue receipt:
[P01 comment](https://github.com/arunakulat/dutchbay-epc-model/issues/1110#issuecomment-5396117160).

## 4. P02 protected delivery is complete; P02 adjudication is not

PR [#1154](https://github.com/arunakulat/dutchbay-epc-model/pull/1154) was squash-merged as
`961461a32d35f9a3c1e730688e13bd737e8c60de` from exact reviewed head
`dd68480f706da6490bdc2fc769ed91e58eb43b7d` and base
`63b67eb62789da9ad712e9d0569737ec79988c65`.

The reviewed candidate and merged trees are byte-identical at
`af2c8741552b78be085d558ce927fe030ea12c22`. The branch contained one commit and 11
controlled files. Protected delivery recorded:

- all six Python 3.12 shards successful;
- Coverage Gate and aggregate Test Summary successful;
- required `fastlane`, `smoke` and `Test Summary` checks successful;
- current VERIFY-01, Code Quality, Security, CodeQL and regression smoke successful;
- 17 current successes and three governed qualification skips;
- an initial VERIFY-01 failure caused solely by the absent receipt table, superseded by a
  successful PR-body-edit rerun containing 12 non-silent receipt rows; and
- `MERGEABLE/CLEAN` state, exact branch currency and no open-PR path overlap immediately
  before merge.

The additive P02 overlay preserves all 111 audited finding IDs and the source register at
SHA-256
`71d16a15357a6073456b241d713ba775e2945990b22fa72045d5f312e183b4b8`.
Its controlled artifact identities are:

| Artifact | SHA-256 |
|---|---|
| current-state plan | `b90597560e9cc7985ab9a29b91ccf79efe8312e57de641a0e3616bf8e2156dd8` |
| current-state overlay | `5de2351ddd90dcf778400321def207822a4ce37006c40ebca03fdafd32666808` |
| repository-history implementer self-check | `8a8c481a3beb60ed54ef0f865f134bb9c82766e66e5e820db398fd19b684dc0a` |
| 74-entry publication manifest | `aa0aff11fb27391d04b32f1929864963c6a792d07c08ee965cf538be02fcf220` |

The current-state population is exactly:

- five `implementation_delivered_review_pending` rows: P2-F5-01,
  P2-MC-SENS-01, P2-MC-SENS-02, P3-EQ-04 and P3-MCFX-03;
- one `external_evidence_blocked` row: P2-F5-02;
- four baseline-closed rows not reassessed;
- 16 deferred rows not examined;
- 65 open rows not examined; and
- 20 requires-correction rows not examined.

All 111 rows remain HOLD-blocking and independently reviewed count remains zero. The full
F5-01 delivery sequence is recorded without treating partial D1 evidence as full closure.
F5-02 recognizes only its fail-closed intake control; synthetic lender terms and synthetic
wind placeholders are expressly excluded. The user-accepted `v15.4.0` tag exception is
recorded as unsigned and is not represented as a cryptographic signature.

Post-merge verification from protected `main` returned:

- shared Python 3.12 worktree proof: `PASS`;
- controlled-pack validator: structural `PASS`, release `HOLD`, 74 manifest entries;
- focused P02 and audit-pack suite: 51 passed, one known Hypothesis collection warning;
- protected `main == origin/main == 961461a32d35f9a3c1e730688e13bd737e8c60de`;
  and
- merged tree exactly equal to the reviewed candidate tree.

Durable issue receipt:
[P02 comment](https://github.com/arunakulat/dutchbay-epc-model/issues/1110#issuecomment-5397012154).

## 5. Current worktree disposition

The clean P02 worktree remains temporarily retained at
`/Users/aruna/Downloads/dutchbay-wt-1110-p02-findings-overlay` on local branch
`codex/1110-p02-findings-overlay`; its remote branch is gone after merge. It contains no
unpublished bytes. It may be removed after this handover is protected-delivered and no
other task claims ownership. Do not use destructive reset or clean commands.

The historical P01 worktree was already retired after its protected delivery. Protected
`main` is clean. The non-task local branches `backup/nso-dossier-unredacted-local`,
`claude/sri-lanka-250mw-analysis-1834a3` and `verify-main` are user history and must not be
modified or removed by audit remediation.

## 6. Next dolphin — P03 primary-source control candidate

P03 is the next dependency-free programme gate. Its existing controlled sources are:

- `registers/primary_source_register.v2.json` — 42 registered claim-level records; and
- `source-controls/SOURCE_ARCHIVE_MANIFEST.v2.sha256` — retained source-object manifest.

P03 completion requires an independent source-verification reviewer. The next implementer
dolphin therefore must not mark P03 complete. Its bounded purpose is to publish a
deterministic, fail-closed P03 verification/sampling plan and same-implementer preflight that
an independent reviewer can execute against exact hashes and source locations.

Minimum acceptance boundary for the P03 candidate:

1. preserve the exact 42-record source register and all predecessor hashes without
   rewriting source evidence status;
2. prove every registered path, URL/location, access date, digest, evidence class,
   publication limitation and finding link is structurally present or explicitly
   unsupported/HOLD-blocking;
3. distinguish authenticated primary sources from supplier, agent, analyst-generated,
   synthetic and precedent material;
4. bind retained source objects to a non-self-attesting manifest/root control;
5. generate a deterministic population-exact independent-review plan with sampling or
   full-population requirements justified by claim severity and evidence class;
6. include a negative control that rejects unsupported escalation to verified-primary
   status;
7. keep independent reviewer identity null, completion unauthorized and release `HOLD`;
8. rebuild the publication manifest and pack validator without absolute local paths;
9. run focused adversarial tests plus proportionate GWTF, CASPER, CESSPIT, CCCDIR,
   compatibility, provenance and regression checks; and
10. deliver through a new isolated worktree and exact-head protected PR.

The implementer may publish a candidate control surface and full-population preflight, but
only a genuinely independent reviewer may supply the hash-bound P03 completion decision.

## 7. Exact continuation sequence

1. Protect-deliver this two-file successor-7 handover dolphin and prove reviewed-tree to
   merged-tree identity. Keep issue #1110 OPEN and release `HOLD`.
2. Re-run app-task inventory. If it still times out, disclose that boundary and repeat the
   Git/process/worktree/lock/open-PR conflict audit before creating the P03 worktree.
3. Retire the clean P02 worktree only after protected handover delivery and a final
   ownership check; preserve its merged commit and issue/PR receipts.
4. Inspect the exact P03 register, source manifest, retained source objects, tests and pack
   validator from the latest `origin/main`. Freeze paths, counts and hashes before design.
5. Create a distinct P03 branch/worktree and implement only the candidate verification and
   independent-review-plan surface. Do not combine P03 with P04/P05, F5-01, F5-02 or final
   synthesis work.
6. Publish P03 through protected exact-head CI, then keep its programme gate pending until
   a genuinely independent source-verification decision is hash-bound.
7. Continue P04/P05/P07/P08 only in dependency order. F5-02 P06/L03 remains blocked on
   authenticated external transaction evidence; L04 retains the on-site mast/MCP gap.
8. Regenerate the Board/lender synthesis last. Only R07 may record `RELEASED`, and R08 is
   the sole closure-action gate after P09 consolidation.
