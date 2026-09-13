Reconciled `R18` and `R21` with the convention `main` actually follows, and retracted a false
enforcement claim in `REFACTOR-03`. Remediates audit pointer `RS-F4`, which names both rows as
enforcement-drift.

`R18` now sanctions the eleven-type Conventional Commits set (as enumerated by commitlint
`config-conventional`), records `deploy` as unsanctioned so it is not re-litigated, makes scope
*expected* with an explicit carve-out for cross-cutting changes and `REFACTOR-03` Dolphin Strategy
commits, and restates its test-status clause as a `VERIFY-01` receipt.

**Its enforcement cell deliberately carries no frozen conformance figure.** `R18` drifted because it
pinned one example commit; a pinned percentage decays identically. An earlier draft of this change
froze five fresh measurements into normative text — and independent review found one of them (a
"504 consecutive commits" claim) overstated ~15x *and* self-contradicting, because the counted run
included the very `deploy(fly):` commits the same cell declared unsanctioned. Conformance is now
**computed** by `tests/lint/test_commit_message_conformance.py`, which measures from git history at
test time against ratchet floors and skips on a shallow checkout.

As at 2026-09-13, for the record rather than for the rule: 99.25% of the last 400 commits use a
sanctioned type and 90.75% carry a scope.

`R21` step (5) now requires the narrowest meaningful check before each commit and the full suite
before pushing; the previous literal wording is impractical per-commit, and `AGENTS.md` already
instructs the graduated form. No test-count figure is pinned — the one first drafted had been lifted
from a stale workflow comment and was wrong by ~1.7x.

`REFACTOR-03` enforcement claimed a pre-commit hook that warns on `refactor:` commits touching more
than one file. No such hook exists or ever did. Left unamended, the CSV would have asserted both that
this repository has no commit-message linter and that it has one.

Rule count unchanged at 74; no row added, removed or reordered. Every asserted control ships a
negative control demonstrating the guard fires — 17 in total.
