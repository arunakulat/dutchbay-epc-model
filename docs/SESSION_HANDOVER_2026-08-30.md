# Session handover — 2026-08-30, successor 20

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-29_3.md`](SESSION_HANDOVER_2026-08-29_3.md). Successor 19 remains
authoritative for the PR `#1191` merge receipt and the Dolphin 3A retirement conditions; its
predecessor chain remains authoritative for Dolphin 0 through Dolphin 3A.

This record closes a **remote cloud session** and hands the work back to the governed local Mac
environment. It carries six protected merges, one new GWTF rule, the Dolphin 3B/3C naming
reconciliation, and the ingress of the D3B execution charter. It changes no audit, statutory,
engineering, lender, Board, report-grade or release authority, checks no `#1110` control, and lifts
no `HOLD`.

## 1. Bootstrap — run this first

**This session ran in an ephemeral cloud container with no route to the Mac.** The durable checkout
is therefore behind by six commits and must be synchronized before any further work. Start the next
task from the `DutchBay_EPC_Model` project and run this read-only preflight:

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

**Stop and read that output.** A dirty tree, an unexpected worktree or branch, or an unfamiliar PR
owner is reconciled before anything else. Do not reset, stash, clean, delete or guess.

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
git log --oneline -6
```

Expected end state: `main` equals `origin/main` at
`90b11a65dd045d71453a9a0a75b4644e669daf59`, and the canonical bootstrap reports **73 rules, all 73
active, version v3.0**. That is a dated receipt; always derive the live population from
`go_with_the_flow_rules_v3_0_clean.csv`.

## 2. Protected deliveries in this session

Six protected squash merges, each green on its exact head before merge:

| Merge | PR | Change |
|---|---|---|
| `978fed8` | `#1192` | PERSIST successor 19; repaired the `AGENTS.md` pointer, five records stale |
| `46515dc` | `#1193` | **`MERGE-01`** added to the canonical ruleset |
| `5b51ff9` | `#1194` | Result-facade charter (then named D3B) |
| `ead6a54` | `#1195` | Five design questions resolved; charter rebranded to **D3C** |
| `90b11a6` | `#1196` | **D3B execution charter ingressed** into the corpus |

`VERSION` remains `15.4.0`. No production, test, KPI, finance or evaluation change was made in this
session; every merge was documentation or governance.

## 3. `MERGE-01` — new standing authorization

The owner granted standing authorization to merge a pull request as soon as its required CI is
green, replacing the previous per-PR go-ahead. `MERGE-01` records it in the canonical ruleset
(Git Workflow, v3.0, active), taking the population from 72 to 73 and the CSV SHA-256 from
`3832a07d8adecb5692b871ac67b4b1d056f8d33b1c4a18669eb8d3e1767aa44f` to
`707ee9ba28a48536f3d145931afa87f2a053f234d6268c8cbebd5b385ead79d9`.

**Green** means what the merge boundary already means by green: every REQUIRED check reporting
success on the exact current head, with nothing failed, pending or unreported and no conflict. It
is **delivery authority only** — it lifts no `HOLD` and confers no grade, release, audit, lender or
Board authority. `AGENTS.md` carries the same wording so the gateway cannot contradict the ruleset.

Any handover or charter written before 2026-08-30 that pins **72 rules** or the `3832a07d…` digest
is a dated pre-`MERGE-01` receipt, not a discrepancy.

## 4. Dolphin 3B / 3C naming reconciliation

Two workstreams independently chartered **opposite halves of the same seam** and both called theirs
D3B. They are complementary in substance; only the label collided. The Codex programme's naming
stands, because it is anchored to an implementation with 136 focused tests, four candidate rounds, a
three-round independent veto chain and a trained D3C recruit:

| Increment | Direction | Charter |
|---|---|---|
| **D3B-0** | `ProjectCase` → assessment intent and authored-scenario binding | `DOLPHIN_3B_EXECUTION_CHARTER.md` |
| **D3B-1** | one preflighted `evaluate_with_overrides` call | same |
| **D3C** | v14 result → Dolphin 2 package records | `DOLPHIN_3C_RESULT_FACADE_CHARTER.md` |

The result-facade charter was renamed accordingly and its boundaries corrected: it excludes anything
that calls the engine, and the `return_full_result=True` requirement moved to **D3B-1**, which owns
the gateway call, since D3C may not rerun the engine.

Its section 9 now records five resolved design questions with the evidence that settles each. Four
were mis-posed, and in two cases every option originally offered was wrong. Section 9.6 leaves two
items genuinely open, and both are **domain data rather than design choice**: the per-field precision
table, and the field-to-unit table for `float` fields whose names are silent about units.

## 5. D3B execution charter ingress and verification

Three supplied archives were a markdown snapshot of the local `docs/` tree: 183 of 184 files
byte-identical, zero differing, one new. That one file, the D3B execution charter, is now ingressed
verbatim at SHA-256
`4a8af1a2e7434b5b7701a85c0aedb6b0a4f16ee215453342984e741dc1446b76`.

Its verifiable claims were checked against this repository rather than taken on trust, and all hold:

- the pinned ruleset SHA `3832a07d…44f` matches the CSV at `cbc0e4c` **exactly**;
- its CASPER, CESSPIT and CCCDIR expansions match `FRAMEWORK-01`, `FRAMEWORK-02` and
  `FRAMEWORK-03` **verbatim**;
- `analytics.run_manifest.config_sha256`, its stated delegation target, exists and is public;
- the stated direction `evaluation_v14 → contracts_v14 → feasibility_report_contract` holds, and the
  contract package imports no evaluator, finance, app or api module; and
- its candid section 6 admission verifies — importing `analytics` eagerly loads 36 submodules
  including `analytics.evaluation_v14` and `analytics.pipeline_v14_enhanced`, exactly the inherited
  process-level limitation it declines to claim it has removed.

Disclosing a limitation that would have been easy to omit is the behaviour `VERIFY-01` asks for.

## 6. Open items carried forward

1. **Synchronize the durable checkout.** Section 1. Until it passes there, the Mac is six commits
   behind and `AGENTS.md` points at a record it does not have.
2. **The D3B implementation tree is uncommitted and unpushed.** `git ls-remote` shows no
   `codex/d3b-v14-binding-facade` on `origin`; 136 focused tests, four candidate rounds and a
   three-round veto chain exist only in that local worktree. The freeze-then-review-then-commit
   order explains it, but `PERSIST-01` exists for exactly this exposure — a crash costs four review
   rounds.
3. **Retire the delivered Dolphin 3A worktree and branch** under the proof in section 7. Not yet
   done.
4. **The D3C charter awaits an independent disposition.** No domain or assurance review exists. It
   is a proposal only.
5. **Re-ingress for the D3C recruit.** The corpus now contains both charters and a 73-rule ruleset;
   a recruit trained before 2026-08-30 has a stale vocabulary and rule population.

## 7. Dolphin 3A retirement proof

All four conditions were independently established from the remote side. The topic head
`8ae0c093c04431b00c99a3dd8380b1d481a256d2` was recovered via `refs/pull/1191/head`, so the tree
comparison used the real object rather than an assumption:

| Condition | Result |
|---|---|
| Topic tree equals the protected merge tree | **identical** — both `66a42075c53813008b2ee779413a9c7a71040474` |
| Merge `cbc0e4c` is an ancestor of `origin/main` | yes |
| Unique work on the topic head | none — `git diff cbc0e4c pr/1191` is empty |
| Unresolved review threads on `#1191` | 0 threads |
| Remote branch `codex/d3-project-case-contract` | absent |

Re-prove locally before deleting anything, then delete only on a full pass:

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-epc-model
D3A_MERGE=cbc0e4c2f2de17bfe0b4ba650fb08f7b1623b9ce
D3A_BRANCH=codex/d3-project-case-contract
D3A_WORKTREE=/Users/aruna/Downloads/dutchbay-wt-d3-project-case-contract

test "$(git rev-parse "$D3A_BRANCH^{tree}")" = "$(git rev-parse "$D3A_MERGE^{tree}")"
git merge-base --is-ancestor "$D3A_MERGE" origin/main
test -z "$(git ls-remote --heads origin "$D3A_BRANCH")"
test -z "$(git -C "$D3A_WORKTREE" status --porcelain)"

git worktree remove "$D3A_WORKTREE" && git worktree prune
git branch -D "$D3A_BRANCH"
```

`-D` rather than `-d` is correct and safe here: `#1191` was **squash**-merged, so the topic commits
are not ancestors of `main` and `-d` refuses even though the tree proof holds. That refusal is the
squash artifact, not a warning that work would be lost. Never delete on a partial pass.

## 8. Unchanged authority and holds

- Issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) remains `OPEN` with
  **0 of 23 controls checked** and its Board/lender release `HOLD` language unchanged. Nothing in
  this session touched it.
- `VERSION` remains `15.4.0`. No KPI, finance, evaluation or committed-behaviour change.
- Neither charter carries a disposition. They establish no contract sufficiency, domain
  sufficiency, achieved grade, package approval, release or deployment authority.
- Open pull requests at this cutoff are the two dependabot bumps, `#1176` and `#1178`, both behind
  current `main`. Mutable — re-query before acting.

## 9. Environment note for the next session

This session ran on an ephemeral container with `DUTCHBAY_VENV` unset, so `check_venv.sh` selected
the portable `.venv` fallback permitted by `ENV-01` and `THREAD-01` for that host class, reporting
Python `3.12.3` under `selection_source: portable_fallback`. **That is not a receipt for the
persistent governed environment** `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, which no remote
session can reach. Successor 18's Python 3.12.13 receipt for that environment stands until the
section 1 bootstrap re-verifies it locally.

A remote session has no route to the Mac filesystem at all: `/Users` does not exist there, no host
mount is present, and no filesystem connector exists to enable. Work needing the durable checkout,
the governed `.venv`, or the D3B worktree belongs in a local session.
