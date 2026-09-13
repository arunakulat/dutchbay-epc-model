Reconciled `R18` and `R21` with the convention `main` actually follows, and retracted a false
enforcement claim in `REFACTOR-03`. Remediates audit pointer `RS-F4`, which names both rows as
enforcement-drift.

`R18` now sanctions the eleven-type Conventional Commits set (as enumerated by commitlint
`config-conventional`), records `deploy` as unsanctioned, makes scope *expected* with an explicit
carve-out for cross-cutting changes and `REFACTOR-03` Dolphin Strategy commits, and restates its
test-status clause as a `VERIFY-01` receipt.

**No cell this rule touches carries a frozen figure.** `R18` drifted because it pinned one example
commit; a pinned percentage decays identically. Two review rounds were needed to get this right: the
first draft froze five fresh measurements into normative text, one of them overstated ~15x and
self-contradicting; the second removed three of four and left a stale commit count in the description.

Conformance is **computed** by `tests/lint/test_commit_message_conformance.py`, measured against
`origin/main` rather than the current branch, so its verdict describes shared history and not whichever
branch a runner stands on. Its binding to `R18`'s type list is a set comparison in both directions —
substring presence bound nothing, since `ci` matches inside "explicit" — and that binding runs
everywhere including CI, because it reads the CSV rather than git history. Only the measurement itself
needs full history and skips without it.

**No scope floor is gated.** An earlier draft asserted one, which was a category error: `R18` makes
scope *expected*, not required, and explicitly sanctions unscoped commits. That floor was also authored
at exactly the observed value, 170/200 with zero headroom, and would have failed on the next sanctioned
unscoped commit — on a check that `R21` makes mandatory before every push.

`R21` step (5) now requires the narrowest meaningful check before each commit and the full suite before
pushing. No test-count figure is pinned; the one first drafted had been lifted from a stale workflow
comment and was wrong by ~1.7x.

`REFACTOR-03` enforcement claimed a pre-commit hook that warns on `refactor:` commits touching more than
one file. No such hook exists or ever did. Left unamended, the CSV would have asserted both that this
repository has no commit-message linter and that it has one.

Rule count unchanged at 74; no row added, removed or reordered. 19 negative controls, each verified to
fire from its own assertion.
