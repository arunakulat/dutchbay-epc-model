# Session handover — 2026-08-29, successor 19

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-29_2.md`](SESSION_HANDOVER_2026-08-29_2.md). Successor 18
remains authoritative for the complete Dolphin 3A `ProjectCase` v1 contract surface, its
D3A-DOM/R/ASR review chain, both independent acceptance dispositions, every verification
receipt, and the web and evolution boundary. Its predecessor chain remains authoritative for
Dolphin 0 through Dolphin 2.

This record carries only the protected delivery of PR
[#1191](https://github.com/arunakulat/dutchbay-epc-model/pull/1191), the post-merge
synchronization, and the predecessor statements that the merge superseded. It changes no audit,
statutory, engineering, lender, Board, report-grade or release authority, checks no `#1110`
control, and lifts no `HOLD`.

## 1. Bootstrap — run this first

The Dolphin 3A topic is delivered, so there is no topic worktree to resume. Start the next task
from the `DutchBay_EPC_Model` project and run this read-only preflight from the protected
primary checkout:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
test "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)" = "$(cd "$expected_repo" && pwd -P)"

export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
test -x "$DUTCHBAY_VENV/bin/python"
"$DUTCHBAY_VENV/bin/python" -VV

git status --short --branch
git worktree list
git branch --list
gh pr list --state open --limit 100 \
  --json number,title,isDraft,headRefName,headRefOid,mergeStateStatus,url
gh issue view 1110 --json number,state,title,updatedAt,url
```

**Stop and read that output.** A dirty tree, an unexpected worktree or branch, or an unfamiliar
PR owner is reconciled before anything else. Do not reset, stash, clean, delete or guess.

Only then run the guarded synchronization and governance bootstrap:

```bash
set -eu
expected_repo="/Users/aruna/Downloads/dutchbay-epc-model"
cd "$expected_repo"
test "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)" = "$(cd "$expected_repo" && pwd -P)"

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

That block is fail-closed on repository identity, branch, cleanliness, ancestry, fast-forward
synchronization, governed environment, active-checkout import binding and canonical-rules
validation. Create any writing task afterwards from current `origin/main` in its own `codex/*`
branch and worktree.

On an ephemeral CI or container host where `DUTCHBAY_VENV` cannot be set to the persistent
macOS environment, the checkout-local portable `.venv` fallback permitted by `ENV-01` and
`THREAD-01` applies, and `./check_venv.sh --no-bootstrap` reports
`selection_source: portable_fallback`. That fallback never replaces the persistent local
environment for local Codex work.

The SHAs, counts and states below are a dated receipt. The bootstrap output, live GitHub state,
`AGENTS.md` and the canonical CSV take precedence wherever they have moved.

## 2. Protected delivery of PR #1191

PR #1191 is **merged**, not open. It was merged by `arunakulat` at `2026-08-29T14:51:36Z` as
protected squash merge `cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce`, currently the head of both
`main` and `origin/main`.

| Item | Exact value |
|---|---|
| Protected merge | `cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce` |
| Merged PR head | `8ae0c093c04431b00c99a3dd8380b1d481a256d2` |
| Base at merge | `782c9588ef2685fcf0608d48f7745493aaa15b78` |
| Surface | 8 files, 8810 insertions, 0 deletions, 19 topic commits |
| State | `closed`, `merged=true`, `draft=false` |

The base is the merge commit's sole parent and an ancestor of current `main`. Because the merge
was a squash, the merged PR head `8ae0c093…` is **not** an ancestor of `main`; branch
containment alone will therefore never prove the topic retired.

The delivered surface is exactly:

- `analytics/feasibility_report_contract/__init__.py` and `.../project_case.py`;
- `tests/contracts/test_project_case_contract.py`;
- `changelog.d/project-case-v1.added.md`; and
- `docs/DOLPHIN_3A_ASSURANCE_REVIEW_RECORD.md`,
  `docs/DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md`,
  `docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md`,
  `docs/SESSION_HANDOVER_2026-08-29_2.md`.

No diff landed under `analytics/contracts_v14.py`, `finance/`, `app/`, `api/` or `VERSION`.
`VERSION` remains `15.4.0`. Remote branch `codex/d3-project-case-contract` is absent from
`origin` at this cutoff.

## 3. Synchronization receipt

This cutoff was taken from an ephemeral container checkout at `/home/user/dutchbay-epc-model`,
not from the durable macOS checkout. Within that checkout:

- `git fetch origin` advanced `origin/main` from `1e0d1dcf8140702764956aa1dcaf16e4d321710f` to
  `cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce` and registered the two open dependabot branches;
- local `main` was fast-forwarded from `1e0d1dcf8140702764956aa1dcaf16e4d321710f` to
  `cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce` with `git fetch origin main:main`. `main` was
  checked out in no worktree, so this moved a ref only: no protected working tree was mutated
  and no commit was authored on `main`, consistent with `GOV-02`; and
- the merged D3A surface was confirmed present in the working tree, and
  `git worktree list` contained only this single checkout.

**The owner's durable checkout `/Users/aruna/Downloads/dutchbay-epc-model` was not reachable
from this session and is not covered by this receipt.** It must still be fast-forwarded on the
macOS host using the guarded block in section 1. Treat the local synchronization obligation as
open until that block passes there.

## 4. Predecessor statements superseded by the merge

Successor 18 was written before the merge. These of its statements are now superseded; its
remaining sections are unaffected.

1. **Section 1, "PR `#1191` remains open, draft, mergeable, and clean."** Superseded. The PR is
   closed, merged and not a draft, per section 2 above.
2. **Section 1 bootstrap.** It resumes from worktree
   `/Users/aruna/Downloads/dutchbay-wt-d3-project-case-contract` on branch
   `codex/d3-project-case-contract`. That topic is delivered and its remote branch is gone, so
   the next session must not resume there. Use section 1 of this record instead.
3. **Sections 1 and 7, accepted head `77db342342e5ef62c922ac328d73a0b2e3e407d3`.** That was the
   pre-append candidate head. The authorized documentation append created a new head and both
   reviewers rebound to it: the PR body records **DOMAIN ACCEPTED** and **ASSURANCE ACCEPTED**
   at final head `8ae0c093c04431b00c99a3dd8380b1d481a256d2`, and that is the head that merged.
   Successor 18 anticipated this rebind. The final head supersedes the capture-time head; it
   does not weaken either acceptance.
4. **Section 7, delivery steps 6 and 7.** Step 6 (make `#1191` ready and merge) is discharged.
   Step 7 (synchronize protected main after merge) is discharged for this session's checkout
   only and remains open for the durable macOS checkout, per section 3.

Retiring the delivered worktree and its local branch stays subject to the proof-based
discipline recorded in
[`docs/SESSION_HANDOVER_2026-08-28_2.md`](SESSION_HANDOVER_2026-08-28_2.md) section 2: prove
the topic tree equals the protected merge tree, prove the merge commit is an ancestor of
current `origin/main`, confirm no unresolved review thread and an absent remote branch, and
only then delete. Nothing in this record authorizes deleting a branch that still holds unique
unmerged work.

## 5. Repaired bootstrap pointer

`AGENTS.md` named `docs/SESSION_HANDOVER_2026-08-28_3.md` as the newest record while five newer
records existed: `2026-08-28_4`, `2026-08-28_5`, `2026-08-28_6`, `2026-08-29` and
`2026-08-29_2`. The pointer last moved with PR #1185; the later record-adding PRs did not
advance it. A session that trusted the pointer would have executed a bootstrap five records
stale. This record repoints `AGENTS.md` at successor 19.

No repository test asserts that pointer, so the drift was silent rather than a CI failure. A
guard that binds the `AGENTS.md` pointer to the newest record in the handover chain would make
the next drift fail loudly; it would have to follow each record's stated predecessor link
rather than filename order, because `_10` sorts before `_2`. That guard is deliberately out of
this dolphin's scope and is not added here.

## 6. Environment and ruleset receipt at this cutoff

Taken on an ephemeral container host with `DUTCHBAY_VENV` unset, so `check_venv.sh
--no-bootstrap` selected the permitted portable fallback and returned `status: PASS`,
`selection_source: portable_fallback`, `venv_path: /home/user/dutchbay-epc-model/.venv`,
`python_version: 3.12.3`, `import_path` under the active checkout,
`foreign_checkout_paths: []` and `editable_project_install: false`.

**This is not a receipt for the persistent governed environment**
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, which this session could not reach.
Successor 18's Python 3.12.13 receipt for that environment stands until it is re-verified
locally by the section 1 bootstrap.

The canonical bootstrap derived **72 rules, all 72 active, version v3.0** at this cutoff. That
is a dated count; always derive the live population from
`go_with_the_flow_rules_v3_0_clean.csv`.

## 7. Unchanged authority, holds and open items

- Issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) remains `OPEN`
  with **0 of 23 controls checked** and its Board/lender release `HOLD` language unchanged. It
  was last updated `2026-08-28T09:07:07Z`; neither #1191 nor this record touched it.
- `VERSION` remains `15.4.0`. No KPI, finance, evaluation, contract or committed-behavior
  change was made by this documentation dolphin.
- The D3A domain and assurance acceptances establish narrow contract sufficiency only. They are
  not professional or statutory engineering assurance, external audit, lender or Board
  acceptance, achieved-grade authority, package approval, release or deployment authorization,
  or authority to lift any `HOLD`.
- Open pull requests at this cutoff are #1176 (dependabot numerics group) and #1178
  (dependabot `scipy-stubs` 1.18.1.0). Both are non-draft and both are based on
  `f8bc6b2857a3a681515511397ffb88c011d34341`, so both are behind current `main`. These statuses
  are mutable and must be re-queried before any action.

## 8. Continuation

1. Fast-forward the durable macOS checkout with the guarded block in section 1, then confirm
   `main` equals `origin/main` there. Until then, section 3's synchronization is partial.
2. Retire the delivered Dolphin 3A worktree and local branch only under the proof-based
   discipline in section 4. Squash-merge means containment alone is not proof.
3. Keep the next Dolphin 3 increment inside successor 18's section 4 exclusions. Nothing here
   authorizes wiring the v14 engine, ProjectCase-to-v14 mapping, a web or API adapter,
   persistence, or feasibility-package assembly.
4. Re-query open PRs, branches, worktrees and issue states before any mutation. This record is
   a cutoff, not a lock.
5. Leave every `#1110` control unchecked and the release `HOLD` in force absent genuinely
   independent evidence and an explicit recorded disposition.
