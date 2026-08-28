# Session handover — 2026-08-28, successor 2

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-28.md`](SESSION_HANDOVER_2026-08-28.md).
The predecessor remains authoritative for PR #1165's exact-head cloud-sandbox
receipts, programme populations and the independent-review boundaries. This
successor updates protected-main delivery, cleanup, branch, open-PR and
operational-hold state.

## 1. Protected delivery and synchronization

At this record's base, protected `main` and `origin/main` are identical at
`c6c6e50d45e4de9a8bfdccb5a83605d3af9e510b`.

- PR #1165, the #1110 cloud-sandbox runtime fix, remains protected-merged as
  `14e7091fa3a3a5a028b1f8968ca619380c32f2fc`.
- PR #1182, the predecessor PERSIST handover, is protected-merged as
  `c6c6e50d45e4de9a8bfdccb5a83605d3af9e510b`.
- The reviewed topic trees were compared with their protected squash-merge
  trees before retirement, as recorded by the predecessor and PR receipts.

The persistent governed environment passed from the primary checkout using
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` and Python 3.12.13. The
canonical CSV bootstrap derived 72 active v3.0 rules at this cutoff. That is a
dated receipt; permanent instructions continue to derive the live population
from `go_with_the_flow_rules_v3_0_clean.csv`.

## 2. Worktree and local-branch cleanup

Before this successor worktree was created, `git worktree list` contained only
the protected primary checkout at
`/Users/aruna/Downloads/dutchbay-epc-model`. The merged #1165 and #1182
worktrees had already been removed, and worktree metadata was pruned.

Five detached local task branches remained because squash merges do not make
their topic commits ancestors of `main`. Each branch was independently mapped
to its merged PR, its full topic tree was exactly equal to the protected merge
tree, the merge commit was an ancestor of current `origin/main`, the PR had no
unresolved review threads, and the corresponding remote branch was absent.
Only then were these local branches deleted:

| Deleted local branch | Protected PR | Protected merge |
|---|---:|---|
| `codex/1110-p01-portability` | #1153 | `63b67eb62789da9ad712e9d0569737ec79988c65` |
| `codex/1110-p02-findings-overlay` | #1154 | `961461a32d35f9a3c1e730688e13bd737e8c60de` |
| `codex/1110-handover7` | #1155 | `594fbac4da33e1836481b482c962a7f5a9539b2d` |
| `codex/1110-p03-primary-sources` | #1156 | `6d09486cb1d22ffb4fffb39601a3c00a55a7502c` |
| `codex/1110-handover8` | #1157 | `6f2af3258e884f3cee6630c279d480ef8d41d812` |

The obsolete local `verify-main` pointer was also deleted after proving it was
fully contained in current `main`. No source, evidence artifact, uncommitted
change or unique task commit was deleted.

Two unrelated local history/backup branches were deliberately preserved:
`backup/nso-dossier-unredacted-local` and
`claude/sri-lanka-250mw-analysis-1834a3`. They have no worktree and contain
unique local commits. This cleanup did not publish, rewrite or delete them.

## 3. Open pull requests remain owned

At the inventory cutoff, the unrelated open pull requests were #1176, #1178
and draft #1181. Their branches were not local cleanup targets and remain
intact. #1176 and #1178 were behind `main` with failing historical check
rollups; #1181 was a clean, green draft. Those mutable statuses must be
re-queried before any action. Draft or open-PR status is not merge authority.

No unmerged implementation or documentation change remained in a retired
worktree. Consequently, no replacement PR was necessary merely to preserve
worktree content.

## 4. Residual obligations are already issue-bound

The cleanup inspection found no worktree-only defect or obligation requiring a
new issue. The remaining controlled programme is already represented on
GitHub:

- #1110 — parent controlled-successor and release gate;
- #1158 and #1159 — independent P01 execution and evidence-integrity review;
- #1160 — additive hash-bound P01 decision, dependent on #1158 and #1159;
- #1161 — independent P02 adjudication of all 111 findings;
- #1162 — independent P03 review of all 42 claims and 74 retained objects; and
- #1183 — owner decision whether the audit-review image job becomes required
  or remains advisory.

These issues are not stale branch remnants. They require new independent work,
external evidence or an owner decision and therefore remain open.

## 5. Holds and external resources

Operational cleanup is clear at this cutoff:

- no GitHub Codespace exists for the repository;
- candidate and reusable Codespace lifecycle locks are absent;
- no candidate, SSH-readiness or cloud-review helper process survives;
- no auxiliary task worktree existed before this documentation dolphin; and
- the primary checkout is clean and synchronized.

The governed audit/release HOLD is different and remains controlling. The
controlled pack may be structurally `PASS`, but #1110 remains open,
`completion_authorized=false`, and release remains `HOLD`. Cleanup, merged
infrastructure and green CI do not supply independent P01/P02/P03 decisions,
authenticated F5-02 transaction evidence, bankable resource evidence or Board/
lender circulation authority.

## 6. Continuation

1. Preserve the open issue population and execute #1158 through #1162 only in
   their governed dependency order with genuinely independent reviewers.
2. Obtain the owner decision in #1183 before changing the repository ruleset.
3. Keep F5-01 and F5-02 separate; do not infer F5-02 terms or lift the release
   HOLD without authenticated lender/legal/tax/authorized-dealer evidence.
4. Re-query all open PRs, branches, worktrees, locks, Codespaces and processes
   before mutation; this record is a cutoff, not a permanent lock.
5. After this successor's protected PR is verified merged, remove only its
   clean temporary worktree and local/remote topic branch. Preserve the two
   unrelated local history/backup branches and every open-PR branch.
