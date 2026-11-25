# GWTF R25 Compliance Scripts

## Feature-writer preflight

Run the read-only identity preflight from the exact authorized linked worktree root
with the coordinator-verified worktree, branch and full protected base SHA:

```bash
bash scripts/gwtf-preflight.sh "$EXPECTED_WORKTREE" "$EXPECTED_BRANCH" "$EXPECTED_BASE_SHA"
```

No interactive override is available. Protected and detached branches, mismatched
identity, unavailable or stale live base and non-ancestor bases fail closed.
Missing upstream is explicitly UNKNOWN, not zero unpushed commits. An upstream
comparison does not establish a remote feature branch's identity.

The preflight is not writer ownership proof, a lease, scope authorization, test
qualification, CI acceptance, push or merge authority. The primary protected
checkout must be synchronized separately under CLEANUP-01, not with this feature
writer entrypoint.

The retired root-level `fix_precommit.sh` only emits a diagnostic and exits
nonzero. Use canonical configured hooks on the fresh lease's exact allowlist;
preserve and reconcile any formatter mutation before testing or staging.

## Daily audit

Run at the end of each work session:

```bash
bash scripts/gwtf-daily-audit.sh
```
