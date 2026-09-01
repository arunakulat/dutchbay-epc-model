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
  -> FINAL_HEAD_REBOUND
  -> PR_OPEN
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

After merge, verify protected-main ancestry and tree/delivered-blob identity, synchronize the clean
primary checkout, and retire only the dolphin's own branch and worktree. Preserve unrelated, dirty,
unfamiliar, backup, and concurrently owned state. The final PERSIST-01 handover records what was
removed, what remains, and whether recovery is possible.
