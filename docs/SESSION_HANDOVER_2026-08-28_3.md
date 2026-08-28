# Session handover — 2026-08-28, successor 3

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-28_2.md`](SESSION_HANDOVER_2026-08-28_2.md).
The predecessor and its referenced chain remain authoritative for verified
cleanup, PR #1165 exact-head receipts, frozen programme populations and
historical candidate-artifact identities. This successor supersedes only the
mutable startup, repository, worktree, issue and resource cutoff. It adds the
executable bootstrap requested by the owner and updates the live cutoff after
protected PR #1184.

## 1. Bootstrap — run this first

Start the next Codex task from the `DutchBay_EPC_Model` project. First run this
read-only identity and ownership preflight from the protected primary checkout:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
actual_repo="$(git rev-parse --show-toplevel)"
test "$(cd "$actual_repo" && pwd -P)" = \
  "$(cd "$expected_repo" && pwd -P)"

export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
test -x "$DUTCHBAY_VENV/bin/python"
"$DUTCHBAY_VENV/bin/python" -VV

git status --short --branch
git worktree list
gh pr list --state open --limit 100 \
  --json number,title,isDraft,headRefName,headRefOid,mergeStateStatus,url
for issue_number in 1110 1140 1158 1159 1160 1161 1162 1183; do
  gh issue view "$issue_number" \
    --json number,state,title,updatedAt,url
done
gh codespace list --json name,state,repository,createdAt,lastUsedAt
for lock_path in /tmp/dutchbay-1110-codespace-create.lock \
  /tmp/dutchbay-1110-candidate-codespace.lock; do
  if [ -e "$lock_path" ]; then
    ls -ld "$lock_path"
  fi
done
bootstrap_pid="$$"
ps -axo pid=,ppid=,state=,command= | awk -v bootstrap_pid="$bootstrap_pid" '
  BEGIN {
    pattern = "dutch" "bay.*(code" "space|cloud|1110)|gh code" "space"
  }
  $1 != bootstrap_pid && $0 ~ pattern { print }
'
```

**Stop after the preflight and inspect its output.** If it exposes a dirty or
wrong checkout, an unexpected worktree, process, lock, Codespace, PR owner or
issue state, reconcile exact ownership before continuing. Do not reset, stash,
clean, delete or guess.

Only after the read-only preflight is understood, run the guarded
synchronization and governance bootstrap:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
actual_repo="$(git rev-parse --show-toplevel)"
test "$(cd "$actual_repo" && pwd -P)" = \
  "$(cd "$expected_repo" && pwd -P)"

export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
test -x "$DUTCHBAY_VENV/bin/python"
test "$(git branch --show-current)" = "main"
test -z "$(git status --porcelain)"

git fetch origin --prune
git merge-base --is-ancestor HEAD origin/main
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"

DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
git status --short --branch
```

The second block is deliberately fail-closed on repository identity, branch,
cleanliness, ancestry, fast-forward synchronization, governed environment,
active-checkout import binding and canonical-rules validation. After it passes,
create any writing task from current `origin/main` in its own `codex/*` branch
and worktree.

The SHA, counts and open-item states below are a dated receipt. The bootstrap,
live GitHub state, `AGENTS.md` and the canonical CSV take precedence if they
have moved.

## 2. Exact authoring cutoff

At this successor's authoring base, protected `main` and `origin/main` are
clean and identical at
`855abb59cd74845699771ce29d3b088d4671e1b6`, the squash merge for
[#1184](https://github.com/arunakulat/dutchbay-epc-model/pull/1184).
PR #1184 published successor 2 and its proof-based operational-cleanup record.
That record is not formal audit independence. Its required contexts and
aggregate CI completed green, including the visible advisory audit-image job.

The persistent governed environment is
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, verified as Python 3.12.13.
The canonical bootstrap derived **72 rules, all 72 active, version v3.0** at
this cutoff. Never copy the rule bodies or trust an older 70/72 count; derive
the live population from `go_with_the_flow_rules_v3_0_clean.csv`.

Before this documentation worktree was created, the only registered worktree
was the protected primary checkout. The two unrelated local branches
`backup/nso-dossier-unredacted-local` and
`claude/sri-lanka-250mw-analysis-1834a3` remain deliberately preserved because
they contain unique local history and have no task worktree.

## 3. Final branch and resource cleanup

Successor 2 already records proof-based retirement of the merged #1110 task
branches and worktrees. This final pass also removed remote branch
`claude/dutchbay-epc-review-dthkqy`. Immediately before deletion, the cleanup
operator observed and retained the following contemporaneous receipt:

- no open pull request used the branch;
- `git ls-remote` reported its remote head as protected merge commit
  `0d1c512ed6571111a43f6823be95271142234b55` from PR #1179;
- that commit was an ancestor of current `origin/main`; and
- the branch contained no unique unmerged tree.

The deleted ref itself can no longer independently reproduce its former head;
the SHA above is a dated pre-deletion observation, not a surviving branch.

Open-PR branches remain protected from cleanup. At this cutoff they are:

- #1176 — `dependabot/pip/numerics-1a7835728b`;
- #1178 — `dependabot/pip/scipy-stubs-1.18.1.0`; and
- draft #1181 — `claude/nso-oem-docs-batch2`.

No GitHub Codespace exists for this repository. The candidate/create locks are
absent, and no matching cloud-review helper is known to survive. Re-query those
facts before any future deletion or cloud execution.

This successor is delivered through
[#1185](https://github.com/arunakulat/dutchbay-epc-model/pull/1185) on branch
`codex/session-handover-bootstrap-2026-08-28`. After that protected PR is
terminal green and verified merged, remove the clean worktree and its local and
remote topic refs, prune metadata, and prove the primary checkout is clean and
synchronized. Do not remove an open-PR branch or either preserved unique local
branch.

## 4. Remaining governed queue

The operational workspace is clean; the audit programme is not complete.
These obligations remain issue-bound:

1. [#1158](https://github.com/arunakulat/dutchbay-epc-model/issues/1158) —
   independent P01 clean-room checkpoint recovery.
2. [#1159](https://github.com/arunakulat/dutchbay-epc-model/issues/1159) —
   independent P01 portable-manifest and evidence-integrity attestation.
3. [#1160](https://github.com/arunakulat/dutchbay-epc-model/issues/1160) —
   additive, hash-bound P01 completion decision after #1158 and #1159.
4. [#1161](https://github.com/arunakulat/dutchbay-epc-model/issues/1161) —
   independent P02 adjudication of all 111 findings in the governed sandbox.
5. [#1162](https://github.com/arunakulat/dutchbay-epc-model/issues/1162) —
   independent P03 review of all 42 claims and 74 retained objects after P02.
6. [#1183](https://github.com/arunakulat/dutchbay-epc-model/issues/1183) —
   owner decision whether the audit-image CI context becomes required or
   remains advisory.
7. [#1140](https://github.com/arunakulat/dutchbay-epc-model/issues/1140) —
   scheduled 2026-11-30 review of the gated canon-movers register.

Issues #1138 and #1139 are closed. The dependency order remains P01, P02 and
P03 before P04; P05 requires P01 and P02. A same-implementer rerun, code-review
agent or green CI result is not the independent, hash-bound decision those
gates require.

## 5. Release and evidence boundary

[#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110)
remains OPEN. The controlled pack may be structurally `PASS`, but
`completion_authorized=false` and release remains `HOLD`. Neither cleanup,
protected merges, reconstructed controls nor hosted infrastructure supplies:

- independent P01/P02/P03 decisions;
- authenticated F5-02 lender, legal, tax or authorized-dealer evidence;
- bankable wind-resource or real-feeder evidence;
- a canonical financial re-baseline; or
- Board/lender circulation authority.

Keep F5-01 and F5-02 separate. Preserve exact-head receipts, manifests,
confidentiality boundaries, private-source authority and genuinely independent
reviewer identity. Only the governed terminal release decision may lift
`HOLD`.

## 6. Next-session operating rule

Begin with section 1 of this document, then reconcile live owners before
starting a dolphin. Work sequentially in the dependency order above, save
durable checkpoints early, and ship each independently reversible change
through a current branch, focused verification, two-lens review, required and
aggregate CI, protected merge, tree-equivalence proof and safe retirement.
Never infer completion from this handover's dated snapshot.
