# Session handover — 2026-08-24, successor 8

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-24_7.md`](SESSION_HANDOVER_2026-08-24_7.md).
Successor 7 remains authoritative for the P01/P02 candidate designs, exact delivery
receipts and historical populations except where this record replaces its now-stale P03
and continuation state.

## 1. Live repository, environment and coordination state

**Protected main at this authored cutoff:**
`6d09486cb1d22ffb4fffb39601a3c00a55a7502c`.

**Active worktree for this handover dolphin:**
`/Users/aruna/Downloads/dutchbay-wt-1110-handover8`.

**Active branch:** `codex/1110-handover8`.

**Branch base:** exact `origin/main` at
`6d09486cb1d22ffb4fffb39601a3c00a55a7502c`.

The governed environment remains
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, verified as Python 3.12.13.
No checkout-local, temporary, Python 3.11 or system replacement environment was created.
Repository work continues from the applicable isolated worktree with that worktree first
on `PYTHONPATH`.

This Codex task is rooted at `/Users/aruna/Downloads`, not the repository. The built-in
post-PR monitor is therefore blind under ENV-01. Git and GitHub operations must continue to
use explicit repository context. Reopen a task rooted at
`/Users/aruna/Downloads/dutchbay-epc-model` for automatic PR/CI context.

The last successful full Codex-task inventory earlier in this same session found only this
task active; other relevant DutchBay tasks were idle or unloaded. Every later inventory
refresh—including both pre-P03 and post-P03 attempts—timed out without returning a new
snapshot. This is a continuing coordination coverage boundary, not evidence that no other
task exists. Before every mutation boundary, repository-visible checks independently found:

- no Git lock;
- no matching editor, test, Hydra, pre-commit or Git mutation process;
- no movement of `origin/main` before either protected merge;
- no open-PR path overlap;
- only dependency PRs #1128 and #1064–#1068, touching only `requirements.txt` and/or
  `constraints.txt`; and
- one isolated writing worktree per current dolphin.

At this cutoff the repository worktrees are:

- clean protected main at `6d09486c`;
- this handover-8 worktree at the same base; and
- the clean, already-merged P03 candidate worktree at reviewed head `5e2973fd`, whose
  upstream branch is gone and whose tree is byte-identical to the protected squash merge.

Re-run the mutable task/process/worktree/lock/PR checks before commit, push, PR update and
merge. If app task inventory remains unavailable, disclose the limitation; never replace
it with an unsupported all-clear.

## 2. Programme status remains OPEN/HOLD

GitHub issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) is OPEN.
The controlled pack is structurally `PASS` and release `HOLD`. No independent `RELEASED`
decision exists.

The published programme ledger remains immutable at its v1 pre-execution state:

- 23 pending programme gates;
- 56 pending architecture examinations and zero hash-bound examination results;
- 111 HOLD-blocking finding rows;
- 34 reproduction controls: 18 completed, 11 required-not-run and five unavailable;
- 42 primary-source claim records;
- F5-02 blocked on authenticated external transaction evidence; and
- Board/lender synthesis and circulation prohibited until the dependency chain and final
  independent release decision are complete.

The publication pack now contains 77 manifest entries. P01, P02 and P03 each have a
protected-delivered candidate control surface and same-implementer preflight. None has the
independent decision required to complete its programme gate.

F5-01 and F5-02 remain completely separate evidence, decision, implementation, test,
reconciliation, PR and rollback surfaces. Synthetic lender terms, synthetic ERA5/mast/MCP
profiles, QSTS software-path success and compile-only outputs remain modelling/workflow
evidence only. None supplies authenticated lender, utility-accepted feeder or bankable wind
resource evidence.

## 3. P01 and P02 delivery state is unchanged

P01 candidate portability/recovery delivery remains protected-complete through PR #1153,
squash merge `63b67eb62789da9ad712e9d0569737ec79988c65`. Its independent evidence-integrity
review remains pending.

P02 candidate findings-current-state delivery remains protected-complete through PR #1154,
squash merge `961461a32d35f9a3c1e730688e13bd737e8c60de`. All 111 rows remain HOLD-blocking;
independently reviewed count remains zero. Five rows have positively evidenced
implementation delivery pending review, P2-F5-02 remains separately external-evidence
blocked, and the other 105 rows remain explicitly not reassessed or examined.

Successor 7 carries the full P01/P02 artifact identities, CI receipts, issue comments,
F5 separation and unsigned-`v15.4.0` exception wording. Do not reinterpret candidate
delivery as programme-gate completion.

## 4. P03 protected delivery is complete; P03 independent review is not

PR [#1156](https://github.com/arunakulat/dutchbay-epc-model/pull/1156) was squash-merged as
`6d09486cb1d22ffb4fffb39601a3c00a55a7502c` from exact reviewed head
`5e2973fd71656e05c313de186bdcb369db79d4e4` and base
`594fbac4da33e1836481b482c962a7f5a9539b2d`.

The reviewed candidate and merged trees are byte-identical at
`d473f97374585fa42dc5b4c560cb85e3da136efd`. Protected delivery recorded:

- all six Python 3.12 shards successful;
- Coverage Gate and aggregate Test Summary successful;
- required `fastlane`, `smoke` and `Test Summary` successful;
- VERIFY-01, Code Quality, Security, CodeQL and regression smoke successful;
- 17 successes, three governed qualification skips and no failure or pending check;
- `MERGEABLE/CLEAN`, exact base currency and no open-PR path overlap immediately before
  merge; and
- the remote topic branch deleted after merge.

P03 publishes a deterministic population-exact review plan over all 42 primary-source
records and all 74 retained source-manifest objects. It reconciles 92 artifact references
across 64 unique paths: 62 claim-referenced manifest objects, 12 retained-unreferenced
objects and two separately governed artifact routes.

The same-implementer source preflight verified all 74 objects, 70 unique digests,
50,938,825 retained bytes, the parent IEC catalogue query log and both governed exception
routes. Two exact-head CLI runs were byte-identical, matched the committed receipt and
created no logs or output directories. This establishes byte identity and structural
linkage only.

Controlled P03 artifact identities are:

| Artifact | SHA-256 |
|---|---|
| population-exact review plan | `01d324d31918100e0db4a05671b84f9f7792ed165f97258a985eee5566d6c661` |
| path-free implementer self-check | `63abf3fceba3cfc56c5c2c3369dad3ad2d828d0ce2618796736ee957d5421082` |
| 77-entry publication manifest | `dd045ded560b65e5fdf5eff11d5ee61ddc7595f8e2f0ba284877a5790e04bb17` |
| P03 builder | `d086c355e50311af6c117150cad4acae6a3e10d5fcce8fff9afbe475a254b1bc` |
| Hydra verifier CLI | `0c0cb840bfeb2d5e0f0752d181ca4f5ac5b0ac661c2e77c6e50e2cf656772000` |

Post-merge verification from protected main returned:

- reviewed tree exactly equal to merged tree;
- governed environment/import-origin proof: `PASS`;
- controlled-pack validator: structural `PASS`, release `HOLD`, 77 entries;
- focused P03 and pack suite: 53 passed, one known Hypothesis collection warning; and
- protected `main == origin/main == 6d09486cb1d22ffb4fffb39601a3c00a55a7502c`.

Durable issue receipt:
[P03 comment](https://github.com/arunakulat/dutchbay-epc-model/issues/1110#issuecomment-5397906019).

P03 still records `independence_satisfied=false`, zero semantic reviews, zero
publication-rights reviews and `completion_authorized=false`. The source-root selector is
environment-only and no local path is published. Successful retention hashing does not
establish semantic support, publication rights, transaction evidence, bankability or
release approval.

## 5. Current worktree and branch disposition

The P03 candidate worktree remains temporarily retained at
`/Users/aruna/Downloads/dutchbay-wt-1110-p03-primary-sources` on local branch
`codex/1110-p03-primary-sources`. It is clean, its remote upstream is gone, and it contains
no unpublished bytes. Its reviewed tree is preserved by PR #1156 and squash merge
`6d09486c`. It may be removed after this successor-8 handover is protected-delivered and a
final ownership check finds no task using it. Do not reset or clean it destructively.

The local merged candidate branches for P01, P02, P03 and handover 7 remain recoverable
history. Do not remove them merely because their remote branches are gone. The non-task
local branches `backup/nso-dossier-unredacted-local`,
`claude/sri-lanka-250mw-analysis-1834a3` and `verify-main` are user history and must not be
modified or removed by audit remediation.

## 6. Corrected dependency analysis and controlled to-do list

The earlier shorthand “continue P04/P05” is incomplete. The immutable programme plan is
the authority:

- P04 reproduction execution depends on P01, P02 and P03;
- P05 architecture execution depends on P01 and P02; and
- P01, P02 and P03 remain pending because their required independent reviewers have not
  supplied hash-bound completion decisions.

Therefore S02 evidence execution is not currently dependency-ready. Protected candidate
delivery is not a substitute for independent gate completion, and a same-implementer rerun
must not be relabelled independent.

The next controlled work is:

1. **P01 independent evidence-integrity review.** Review the recovery descriptor,
   clean-room materialization, immutable source/outer/inner manifests, Git-bundle boundary,
   negative controls and exact tested snapshot. Produce an additive, reviewer-identified,
   hash-bound decision; do not rewrite the candidate descriptor or self-check.
2. **P02 independent model-risk/adjudication review.** Review the exact 111-row overlay,
   five implementation-delivered mappings, separate F5-02 blocked row, 105
   not-reassessed/not-examined rows, F5 separation, unsigned tag exception and repository
   history receipt. A completion artifact must account for all 111 IDs without silently
   closing findings or importing current evidence into audited fields.
3. **P03 independent source-verification review.** Execute the population-exact plan over
   all 42 claims and all 74 retained objects. Review source location, claim/support
   semantics, limitations and publication rights for every claim. Preserve PSR-0009 as
   analyst judgment, PSR-0005's unavailable transaction-evidence boundary and PSR-0012's
   internal evidence-status limitation. Record reviewer identity, independence statement,
   decision time and result-artifact hash in a new additive result surface.
4. **Only after P01/P02/P03 complete, start P04.** Preserve the frozen 34-control
   denominator: 18 completed, 11 required-not-run and five unavailable. Execute each
   outstanding control with a versioned method and independent oracle, or record a governed
   unavailable/deferred result with owner, rationale and release effect. Never mark a row
   completed without a result hash and independent review.
5. **Only after P01/P02 complete, start P05.** Execute all 56 architecture rows exactly
   once using their planned negative controls; each final disposition needs a hash-bound
   result and independent software-architecture review. Preserve the frozen plan and
   historical 72-pointer source.

P01/P02/P03 reviews are distinct evidence surfaces and may be coordinated in parallel only
with genuinely independent reviewers and isolated worktrees. Their results must remain
additive; the existing plans, source registers and implementer receipts are immutable
inputs. If independent reviewer authority or retained evidence access is unavailable, stop
and report that blocker rather than manufacturing independence.

## 7. Exact continuation sequence

1. Protect-deliver this successor-8 handover and prove reviewed-tree to merged-tree
   identity. Keep issue #1110 OPEN and release `HOLD`.
2. Re-run app task inventory. If it still times out, disclose the boundary and repeat
   Git/process/worktree/lock/open-PR checks before retiring the clean P03 worktree.
3. Remove the clean P03 worktree only after protected handover delivery and a final
   ownership check; preserve its branch, PR, merge and issue receipts.
4. Obtain or assign genuinely independent P01/P02/P03 reviewers with access to the exact
   controlled inputs. Do not use the original implementer or a same-context rerun as the
   independent decision.
5. Persist each result immediately as an additive reviewer-identified, result-hashed
   artifact; run its negative controls and the pack validator; leave the gate pending on
   any missing population, semantic, rights, hash or independence field.
6. Recompute programme dependency readiness from those exact result artifacts. Start P04
   only after P01/P02/P03 pass; start P05 only after P01/P02 pass.
7. Keep P06/L03 blocked on authenticated F5-02 transaction evidence and L04 explicit about
   the on-site mast/MCP gap. Synthetic placeholders remain modelling-only.
8. Regenerate the Board/lender synthesis last. Only R07 may record `RELEASED`, and R08 is
   the sole closure-action gate after P09 consolidation.
