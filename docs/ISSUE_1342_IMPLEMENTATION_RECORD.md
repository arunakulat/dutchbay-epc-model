# Issue #1342 handover-resolver performance implementation record

## Scope and authority

This record covers the bounded governance-runtime repair in issue #1342 on base
`160f25d5d625436caa4c8c6ae47fab518c0eb87f`. The change affects only the session-handover
resolver, its hostile test suite, this record, and one changelog fragment. It changes no finance
formula, model input, KPI, evidence status, release decision, professional conclusion, or `HOLD`.

## Diagnosis and implementation

The canonical tree contains 44 current handover-family records. The prior resolver ran one
`git log --follow` for every record and then ran a whole-tree
`git diff-tree -M1% -C1% --find-copies-harder` subprocess for every commit returned by every
lineage. Overlapping lineages therefore repeated both history traversal and expensive whole-tree
copy detection. On the exact base and governed cloud Python 3.12 environment, the pre-change
canonical command completed successfully in 207.646 seconds.

The repair preserves the existing whole-tree rename/copy classification, NUL framing, family-entry
rules, topology checks, timestamp checks, index/worktree parity, and fail-loud errors while batching
the work:

1. one multi-path `git log --full-history` returns metadata for commits touching all current record
   paths;
2. one `git diff-tree --stdin` applies the existing whole-tree rename/copy options to those commits;
3. lineage tracing reuses those immutable deltas for every record; and
4. a rename to a predecessor path outside the first batch triggers a bounded follow-up batch, so
   entry from outside the family and delete/re-add ambiguity semantics are retained.

An ordinary merge omitted by `diff-tree` without `-m` is represented as the same empty change set
returned by the former per-commit invocation.

## Evidence

- Pre-change canonical resolver: exit 0, 207.646 seconds.
- Post-change canonical resolver: exit 0, 23.237 seconds (8.9 times faster and below the repository's
  60-second intervention threshold).
- Both runs emitted the same five records, fields, order, and values, headed by
  `docs/SESSION_HANDOVER_2026-10-12_THREAD_TODO.md` at commit
  `160f25d5d625436caa4c8c6ae47fab518c0eb87f`.
- `tests/lint/test_codex_project_guidance.py`: 16 passed. Existing hostile cases cover correction of
  an old record, staged/untracked/deleted/ignored records, delete/re-add ambiguity, rename into and
  within the family, copies, hostile filenames, newest timestamp ties, backdated descendants,
  incomparable introductions, and shallow history.
- The new deterministic regression creates eight separately introduced records and proves the
  successful resolver uses one shared history query and one `diff-tree --stdin` traversal. The
  previous per-record implementation violates both bounds, so the check is a non-wall-clock
  negative control rather than a timing assertion vulnerable to shared-runner noise.

## Limitations

The measured timing is an environment observation, not a permanent wall-clock guarantee. Git copy
detection still depends on repository history and storage performance. Repositories with many
successive renames to previously unqueried predecessor paths require additional bounded batches;
the test suite retains the semantic controls for those paths. This engineering repair grants no
release, audit, lender, Board, professional, publication, issue-closure, or `HOLD` authority.
