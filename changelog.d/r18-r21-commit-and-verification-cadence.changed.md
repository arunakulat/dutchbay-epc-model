Reconciled `R18` and `R21` with the convention `main` actually follows.

`R18` now sanctions the eleven-type Conventional Commits / Angular set, records `deploy` as
unsanctioned so it is not re-litigated, makes scope *expected* with an explicit carve-out for
cross-cutting changes and `REFACTOR-03` Dolphin Strategy commits, and restates its test-status
clause as a `VERIFY-01` receipt. Its enforcement cell now says plainly that no commit-message
linter exists here, and cites measured conformance (363/400 scoped; the last 504 consecutive
commits conforming) instead of the stale `fb3b1f7` example.

`R21` step (5) now requires the narrowest meaningful check before each commit and the full suite
before pushing. The previous literal wording — run `pytest` before committing or pushing — is not
viable per-commit against a ~3,600-test tree, and `AGENTS.md` already instructs the graduated form.

Rule count is unchanged at 74; no row was added, removed or reordered.
