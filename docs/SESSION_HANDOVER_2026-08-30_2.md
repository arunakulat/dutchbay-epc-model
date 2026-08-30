# Session handover — 2026-08-30, successor 21

Durable `PERSIST-01` successor to [`docs/SESSION_HANDOVER_2026-08-30.md`](SESSION_HANDOVER_2026-08-30.md)
(successor 20). The predecessor chain remains authoritative for Dolphin 0 through Dolphin 3A and for
the `#1191` merge receipt.

This record closes a **local governed session** on the Mac. It discharges three of the five open
items successor 20 carried forward, recovers the Dolphin 3B-0 implementation from an uncommitted
worktree, and retires the Dolphin 3A worktree and branch on a full five-condition proof. It changes
no audit, statutory, engineering, lender, Board, report-grade or release authority, checks no `#1110`
control, and lifts no `HOLD`.

## 1. Bootstrap receipt

Successor 20 section 1 required a guarded synchronization before further work. **It was already
satisfied on arrival** — the durable checkout was not six commits behind, because `#1197` (the
successor-20 record itself) had landed and `main` had been fast-forwarded. Verified, not assumed:

| Check | Command | Result |
|---|---|---|
| Checkout synchronized | `git rev-parse HEAD origin/main` | both `fa1418122368011c23643cc77ee5821c60e540f3` |
| Working tree | `git status --short --branch` | clean, `## main...origin/main` |
| Governed environment | `./check_venv.sh --no-bootstrap` | `status: PASS`, `selection_source: DUTCHBAY_VENV`, prefix `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, Python `3.12.13` |
| Canonical ruleset | `dutchbay_bootstrap_rules.py` | `73 rules; versions: v3.0; latest = v3.0`, `active=73` |
| Ruleset digest | `shasum -a 256 go_with_the_flow_rules_v3_0_clean.csv` | `707ee9ba28a48536f3d145931afa87f2a053f234d6268c8cbebd5b385ead79d9` |

The 73-rule population and the `707ee9ba…` digest both match successor 20's post-`MERGE-01` figures
exactly. Successor 20's environment caveat is discharged: this session reached the persistent
governed `.venv`, so the Python `3.12.13` receipt for it is current rather than inherited.

## 2. Dolphin 3B-0 recovered, committed, pushed and opened

Successor 20 open item 2 recorded the D3B implementation tree as uncommitted and unpushed — a live
`PERSIST-01` exposure. It has been discharged.

The frozen five-file tree was inventoried before anything was fetched, staged or merged, per the
charter section 9 restart rule. One of the five, `docs/DOLPHIN_3B_EXECUTION_CHARTER.md`, was an
untracked copy **byte-identical** to the file `#1196` had already merged — SHA-256
`4a8af1a2e7434b5b7701a85c0aedb6b0a4f16ee215453342984e741dc1446b76` on both the working copy and
`origin/main:docs/DOLPHIN_3B_EXECUTION_CHARTER.md`. It was therefore removed rather than committed,
after that identity was proven against the remote object directly. The other four are the delivery.

The branch carried **no commits of its own** — the entire slice existed only in the working tree.
It was committed as one checkpoint, then rebased onto current `origin/main` (it had been six
behind), giving head `5dabf43384dd16de37820e8709baa1cea8660675`, one commit ahead and conflict-free.

Opened as [`#1198`](https://github.com/arunakulat/dutchbay-epc-model/pull/1198). Delivery is
3,989 insertions across four files: `analytics/feasibility_report_contract/assessment_scope.py`
(1,827 lines), `tests/contracts/test_assessment_scope_contract.py` (2,024 lines, 64 test functions),
the package `__init__.py` re-export block, and a changelog fragment.

### 2.1 Gate receipts

All run at head `5dabf43` from the D3B worktree under the governed environment.

| Gate | Command | Result |
|---|---|---|
| Focused hostile tests | `pytest tests/contracts/test_assessment_scope_contract.py -q` | `136 passed, 1 warning in 16.53s` |
| Contract regression (D2 + D3A + D3B) | `pytest tests/contracts/ -q` | `792 passed, 1 warning in 20.75s` |
| Lint | `ruff check <paths>` | `All checks passed!` |
| Format | `ruff format --check <paths>` | `3 files already formatted` |
| Black | `black --check <paths>` | `3 files would be left unchanged.` |
| isort | `isort --check-only <paths>` | clean, exit 0 |
| Types | `mypy --no-incremental analytics/feasibility_report_contract/` | `Success: no issues found in 6 source files` |
| Byte-compile | `compileall -q <paths>` | clean, exit 0 |
| Public-export identity | fresh-process `__all__` probe | 121 exports, sorted and unique, `missing attrs: NONE` |
| Draft 2020-12 schema modes | — | **not run** — charter section 8 lists it; not executed this session |
| **Exact-head CI** | `gh pr view 1198 --json statusCheckRollup,mergeStateStatus,mergeable` | **21 checks, NON-SUCCESS: NONE**, `mergeStateStatus: CLEAN`, `mergeable: MERGEABLE`, head `5dabf43` |

`#1198` is therefore green in the merge boundary's own sense: every required check reporting success
on the exact current head, nothing failed, pending or unreported, no conflict.

The focused suite collecting **exactly 136 cases** independently corroborates successor 20's "136
focused tests": the recovered tree is the tree that record describes.

### 2.2 Excluded-surface check, with its negative control

`assessment_scope.py` imports no evaluator, finance, app or api module. Its only textual reference to
the gateway is line 614, `Literal["analytics.evaluation_v14.evaluate_with_overrides"]` — a declared
identifier **string**, not an import.

The cold-import probe does show `analytics.evaluation_v14` and `analytics.pipeline_v14_enhanced` in
`sys.modules`. That is not a D3B regression, and the negative control proves it: a fresh process
running `import analytics` **with no D3B module involved at all** loads the same two, among 37
`analytics.*` submodules. This is the inherited process-level limitation the charter's section 6
already declines to claim it removed, and which successor 20 section 5 verified independently.

### 2.3 What was NOT recovered — declared, not omitted

Charter section 8 requires both reviewers to inspect the frozen uncommitted tree and return a bounded
no-blocker **before** it is committed, then rebind their disposition to the committed SHA. Successor
20 records "four candidate rounds and a three-round veto chain".

**No durable D3B review record exists.** A repository-wide search found no D3B review artefact —
contrast `DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md`, `DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md`,
`DOLPHIN_3A_INDEPENDENT_REVIEW_RECORD.md`, `DOLPHIN_3A_ASSURANCE_REVIEW_RECORD.md` and
`DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md`, each of which is committed. That chain lived only in
the prior session's context and **is lost**.

`#1198` therefore carries **no independent domain or assurance disposition**, and the charter's
commit-ordering precondition was not met — the tree was committed to stop the loss, not because a
no-blocker had been returned. Under the charter D3B-0 remains an implementation candidate. This is
stated here and in the PR body rather than left silent, per `VERIFY-01`.

This is the second time this exposure has cost something. The first cost was the risk; this is the
realised loss. Reviews are work product and belong in `docs/`, at the moment they land.

## 3. Dolphin 3A retired

Successor 20 open item 3. Its section 7 conditions were re-proved locally before anything was
deleted, and all passed — the topic tree hash matches the value that record established from the
remote side:

| Condition | Result |
|---|---|
| Topic tree equals the protected merge tree | **identical** — both `66a42075c53813008b2ee779413a9c7a71040474` |
| `cbc0e4c` is an ancestor of `origin/main` | yes |
| Remote branch `codex/d3-project-case-contract` absent | yes |
| Worktree clean (including untracked) | yes |
| Unique work on the topic head | none — `git diff cbc0e4c codex/d3-project-case-contract` empty |

Worktree `/Users/aruna/Downloads/dutchbay-wt-d3-project-case-contract` removed, `git worktree prune`
run, branch deleted with `-D` (correct for a squash merge, as successor 20 explains). The tip was
`8ae0c093c04431b00c99a3dd8380b1d481a256d2`, still recoverable via `refs/pull/1191/head`.

Live worktrees are now the main checkout, this session's `claude/update-continue-9a1759`, and
`dutchbay-wt-d3b-v14-binding-facade`.

## 4. `MERGE-01` in force; the dependabot pair is out of its scope

`MERGE-01` (row 73, added 2026-08-30 via `#1193`) is the governing merge rule: merge on green, no
per-PR go-ahead. It is **delivery authority only** — it lifts no `HOLD` and confers no grade,
release, audit, lender or Board authority.

It explicitly does **not** apply to a branch that is red, behind or conflicted. Both open dependabot
PRs are exactly that, and were left alone:

| PR | State | Non-success required checks |
|---|---|---|
| `#1176` numerics group | `MERGEABLE` but `BEHIND` | fastlane, smoke, health-image, Code Quality, Security Scan, Test shard 1 |
| `#1178` scipy-stubs | `MERGEABLE` but `BEHIND` | Code Quality Checks, Test Summary |

Both need updating onto current `main` and driving back to green under R23/R25 before `MERGE-01`
engages. Mutable — re-query before acting.

## 5. Environment note — external memory writes were blocked

This session could not write to the operator's memory tree at
`/Users/aruna/.claude/projects/…/memory/`; every read and write there was refused by the harness
permission classifier as outside the repository. No workaround was attempted.

**Consequence to repair in an interactive session:** the operator's global memory file
`dutchbay_gwtf_ruleset_and_framework_acronyms.md` still carries a "STANDING FREEZE: nothing merges to
`origin/main` without an explicit go-ahead" directive dated 2026-08-26, and still pins the ruleset at
**70 rules**. Both are stale. The freeze was withdrawn by the owner on 29 August 2026 and replaced by
`MERGE-01`; the population is 73. That file is `@import`-pinned into the global `CLAUDE.md` and loads
in full every session, so until it is corrected **every future session starts by loading a dead
merge freeze that contradicts row 73 of the canonical ruleset** — a live drift between the operator's
pinned memory and the ruleset it exists to protect.

## 6. Open items carried forward

1. **`#1198` is green but carries no D3B disposition.** Sections 2.1 and 2.3. Its exact-head CI is
   clean, so `MERGE-01`'s delivery authorization is engaged on the letter of the rule. What is
   missing is the charter's independent domain and assurance review, which is **not** a required
   status check and so forms no part of "green". `MERGE-01` declines to substitute for a mandatory
   review, and equally declines to let one act as an unwritten gate a green PR is silently held
   against — it directs that such a review be promoted into the required-check set instead. Those
   two halves do not resolve themselves here, so the PR was **not** merged on the agent's own
   judgement. Three exits are open: supply the missing review, promote it to a required check, or
   accept `#1198` on CI green alone. Supplying it is the cheapest and is being carried as its own
   dolphin on a separate branch; the owner's remaining choice is whether that review suffices.
2. **Repair the operator's global memory file.** Section 5. Needs an interactive session.
3. **The D3C charter still awaits an independent disposition.** Unchanged from successor 20 item 4.
   No domain or assurance review exists; it is a proposal only.
4. **Re-ingress for the D3C recruit.** Unchanged from successor 20 item 5. The corpus now holds both
   charters, a 73-rule ruleset and this record.
5. **The dependabot pair.** Section 4.
6. **D3B-1** — the single preflighted `evaluate_with_overrides` call — has not started. It is a
   separate commit boundary under charter section 6.

## 7. Unchanged authority and holds

- Issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) remains `OPEN` with
  **0 of 23 controls checked** and its Board/lender release `HOLD` language unchanged. Nothing in
  this session touched it.
- `VERSION` remains `15.4.0`. No KPI, finance, evaluation or committed-behaviour change: the model
  canon is untouched, and `#1198` adds a contract surface that executes nothing.
- Neither charter carries a disposition. They establish no contract sufficiency, domain sufficiency,
  achieved grade, package approval, release or deployment authority.
