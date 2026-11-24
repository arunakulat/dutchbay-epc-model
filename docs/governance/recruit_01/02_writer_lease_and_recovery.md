# RECRUIT-01 module 2 — writer leases, recovery, and closure

**Status:** canonical operational sub-module of GWTF `RECRUIT-01`

## 1. Roles and the one-writer invariant

One delivery coordinator owns task orchestration and lease authority. At most one participant holds
an active writer lease for a given worktree and checkpoint. The lease-holder may be a delegated
implementation worker or the coordinator, but never both concurrently. Every other participant,
including all reviewers, remains read-only.

The coordinator does not acquire mutation authority merely by coordinating. Coordinator takeover is
a new lease after the previous lease is conclusively revoked; it is not concurrent reconciliation of
another writer's tree.

## 2. Required lease fields

Every writer lease has a stable lease ID and names:

- coordinator and lease-holder;
- repository, exact worktree path, branch, base SHA, and starting HEAD/tree;
- phase and one bounded deliverable;
- exact file allowlist and forbidden surfaces;
- target-file hashes when pre-existing files will be edited;
- required checks, independent oracles, checkpoint form, and persistence path;
- interruption, drift, scope, secret, destructive-action, and authority stop conditions; and
- the event that expires the lease.

A lease is valid only after immediate branch, status, ownership, target-hash, environment, and base
preflight. Any mismatch leaves the worker read-only.

## 3. Mandatory state machine

```text
READ_ONLY
  -> LEASED
  -> PREFLIGHTED
  -> PATCH_APPLIED
  -> CHECKPOINT_VERIFIED
  -> FROZEN
  -> UNDER_REVIEW
       -> REJECTED -> READ_ONLY -> fresh lease
       -> ACCEPTED
  -> PR_OPEN
  -> FINAL_HEAD_REBOUND
  -> EXACT_HEAD_CI_GREEN
  -> MERGED
  -> PROTECTED_MAIN_VERIFIED
  -> WORKTREE_AND_BRANCH_RETIRED
  -> CLOSED
```

A writer lease expires at `CHECKPOINT_VERIFIED`; further mutation requires a new lease. Reviewers are
dispatched only after `FROZEN`. Commentary and receipts must distinguish `PREPARING`,
`PATCH_APPLIED`, and `ON_DISK_CHECKPOINT_VERIFIED`.

## 4. One bounded patch

A lease authorizes one allowlisted patch followed by diff inspection and the narrowest meaningful
verification. Formatters or generators may run only when their possible output paths are declared.
Unexpected path creation or modification is drift: stop without cleaning, reverting, stashing, or
absorbing it.

The checkpoint receipt states HEAD, tree, base, dirty paths, changed paths, hashes, checks and exact
results, concurrent drift, staged/committed/pushed state, limitations, and active HOLDs. A claimed
checkpoint without on-disk proof is not a checkpoint.

### 4.1 Typed-code checkpoint qualification

Before qualifying a checkpoint that changes typed Python, stubs, or a type/import
contract, run successful targeted mypy against the affected surface with the
governed interpreter and applicable existing CI gate configuration. Include
affected dependants when the interface or import boundary changes; broaden the
scope when impact is uncertain. Run on final formatter-stable bytes, before
staging; repeat after relevant byte, configuration or environment drift. Bind
the command, interpreter and mypy version, configuration identity, target scope,
exit result, log digest and candidate hashes to the checkpoint receipt. Missing
or failing type evidence blocks qualification. A not-applicable disposition
requires an explicit scope rationale subject to independent challenge; not run
is not PASS. A persistence-only rescue is not qualified and grants no review
or merge authority. Preserve R21 full-suite pre-push and R23 local type
verification and every existing CI type gate; the #1270 local hook decision
is unchanged. No error suppression or gate weakening is a remedy for a failed
type check.

### 4.2 Operational checkpoint and incident routing

Use the R25 preflight with the exact coordinator-verified worktree, branch and
live base. Before staging, run canonical allowlisted hook readiness
(`scripts/gwtf_checkpoint_readiness.py`); any formatter mutation stops
qualification, preserves bytes and requires reconciliation and a fresh lease.
Run the required final-byte tests and typed-code checks under §4.1, compare
the staged blobs and modes with the tested candidate, then use ordinary
commit hooks. Reconcile committed blobs, parent, tree and clean worktree.
Use `scripts/gwtf_checkpoint_receipt.py` for the external evidence journal;
preserve its digest independently. A journal entry alone is not proof of
execution, approval, signer identity or notification delivery. Record execution
completion separately from reporting observation; persist observed process
identity, exit and evidence immediately. Poll active processes within the active
execution session where practical. If interrupted, record outstanding process
identity and last observed state for the next authorized session; do not claim
background chat delivery.

Use `scripts/gwtf_interruption_recovery.py` for read-only observation and
explicitly authorized byte preservation, and `scripts/gwtf_incident.py` for
fixed-schema incident classification. Reconcile owner, stop, base and source
rights independently before any new lease. Unknown outcomes, missing evidence,
out-of-scope drift and platform execution restrictions fail closed; never
bypass platform restrictions. These tools do not grant writer authority,
retry permission, independent acceptance, required CI or merge authority.
Incident v2 drift is measured against the expected Git-visible state immediately
before the observed operation (including the authorized candidate and index),
not against HEAD. Retain the baseline digest and execution-evidence digest;
without them completion/unchanged claims cannot qualify. Unknown reporting of
a completed operation requires reconciliation. Incident CLI exit 0 denotes
only an observed successful, non-reconciliation disposition; exit 2 records
a held or incomplete disposition, exit 1 refuses malformed evidence. A receipt
write never authorizes retry or confirms delivery. CLI inputs must be regular
external files, and failures use bounded diagnostics; original logs and
authorized scope evidence still require controlled custody.

Ignored paths and concurrent changes between observations are residual
limitations, not certified isolation. The stricter applicable rule always wins.

### 4.3 Coordinator CLI for the v2 checkpoint journal

Use the governed Python interpreter and external, access-controlled evidence
directory. After the R25 and lease checks, invoke
`python -B scripts/gwtf_checkpoint_workflow.py --journal "$J" start --worktree "$W" --lease "$L"`
with the exact applied-patch lease, including initial index digest, candidate
hashes and Git modes, and approved type plan. Retain the returned subject
digest and journal tip in independent custody. The CLI returns planned type
commands; it does not execute them.

Run canonical readiness, the required targeted mypy and regression checks
under the lease. For each actual observed result, prepare an external JSON
object containing check_id, subject_sha256, command (argument list), exit_code,
log_name (basename in journal directory), log_sha256 and, for a type check,
type_evidence (the corresponding plan record). Append using
`observe --expected-tip "$TIP" --observation "$OBS"` after the same journal
prefix. Independently retain each returned tip. Failed observations are not
PASS; stop and reconcile rather than replacing evidence. Do not expose secrets
in command arguments, logs or evidence files.

Only the authorized writer may explicitly stage the exact tested allowlist,
run the readiness utility's --verify-staged comparison and ordinary commit
hooks. Record the staged and commit observations with their actual logs.
Use `complete --expected-tip "$TIP" --exit-code 0` only on observed successful
completion, then retain that pre-checkpoint tip separately. Invoke
`record --worktree "$W" --lease "$L" --expected-tip "$TIP"`, retain the new tip,
and invoke `verify --worktree "$W" --lease "$L" --expected-tip "$TIP"` with that
new anchor. The latter re-compares actual Git objects. Inspect alone never
establishes checkpoint qualification. The report subcommand records observed
reporting separately and cannot confirm delivery. Every mutation after start
requires the independently retained previous tip; a mismatch stops execution.

The CLI never stages, commits, pushes or merges and does not authenticate
execution, ownership, source rights or reviewer identity. Coordinator review,
live-base and scope adequacy checks, full pre-push tests and formal independent
R3 and CI remain mandatory. Version 1 records are historical claims only.

### 4.4 Predecessor disposition and verification limits

The [#1270 owner decision of 26 October 2026](https://github.com/arunakulat/dutchbay-epc-model/issues/1270#issuecomment-6407805476)
retains the disabled automatic local mypy hook;
R10 names the configured hooks and R21/R23 and applicable CI gates retain
mandatory type verification. Local implementation is not issue closure;
independent exact-object review and required CI still apply. #1262 remains
separate and open: the hook installation-tail tests do not establish complete
setup-path reachability. Do not claim that readiness or the v2 journal closes
that gap. The scope of branch retirement remains §8 and CLEANUP-01; no new
authority to retire unrelated or recovery branches is conferred.

Policy fences preserve every active predecessor rule identity, reject duplicate
identities and allow additive rules. They check scoped normative
clauses, not a frozen total rule count. They detect specific hostile context
mutations, including hidden or negated routed paragraphs and altered CI step
commands or failure settings. The inherited FX scoped mypy step is advisory;
blocking strict and scripts gates remain mandatory. These fences do not prove
workflow reachability or arbitrary natural-language consistency. Independent semantic
review and actual behavioral oracles remain mandatory.

## 5. Interruption and collision recovery

Any interruption, target drift, patch-context failure, unexpected writer activity, worktree-owner
uncertainty, or out-of-allowlist change causes:

```text
PRESERVE_OBSERVED_STATE
  -> REVOKE_LEASE
  -> READ_ONLY
  -> RECONCILE_OWNERSHIP_AND_HASHES
  -> fresh explicit lease or stop
```

An earlier authorization never survives interruption. The returning worker must not merge,
reconcile, format, reset, stash, clean, or continue another writer's tree.

## 6. Responsive and dead-worker takeover

For a responsive worker, takeover requires an explicit stop and acknowledgement before another
writer mutates the tree.

For a crashed, disconnected, or otherwise non-responsive worker, use `DEAD_WORKER_TAKEOVER`:

1. send an explicit stop or interrupt request;
2. wait a bounded interval for acknowledgement;
3. independently prove that the worker/process is no longer active;
4. re-read worktree ownership, branch, HEAD/tree, index, untracked files, and target hashes;
5. persist the takeover reason and observed state; and
6. issue a fresh lease before mutation.

No acknowledgement and no termination proof means no takeover.

## 7. Persistence-only rescue

When owned, focused, uncommitted work is discovered at material loss risk, a
`PERSISTENCE_CHECKPOINT` lease may preserve the exact existing bytes before substantive review. It
allows ownership proof, hashing, exact-path staging, and a clearly labelled checkpoint commit. It
does not authorize semantic edits and is never implementation acceptance, independent review, CI
evidence, or merge authority. Unfamiliar or unowned work remains untouched until ownership is
established.

## 8. Closure

After merge, follow `CLEANUP-01`: verify protected-main ancestry and tree/delivered-blob identity,
inform the tasklist and capability tracker (`#1353`), close only the focused issue named by number
on the merged pull request's `Work item:` or closing line, and only when its deliverable is
complete, synchronize the clean primary checkout when no other session is using it, retire only the
dolphin's own branch and worktree (`git worktree remove`, `git worktree prune`, `git branch -D`,
`git push origin --delete`), and remove any temporary or worktree-local virtual environments while
NEVER touching the protected persistent environment at
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`, `ENV-01`). Cleanup never closes a
pull request: closing an unmerged one needs a cited owner decision, posted as a comment on it
before it is closed. The one exception is a `TRAIN-01` car, closed only after the train's
post-landing check proves its commit is on `origin/main`, with the pointer comment posted first.
A `Work item:` line that names a #1353 comment closes nothing, and cleanup
never closes tracker #1353. A branch is deleted only when its pull request's `merged_at` is set and
every ref still present (remote and local) equals the merged head, read from the GitHub API
immediately before deleting, as the steward skill's step 4 block checks.
Preserve unrelated, dirty, unfamiliar, backup, and concurrently owned state. The final PERSIST-01
handover records what was removed, what remains, and whether recovery is possible.
