- **An agent worktree no longer dirties the tree or trips a governance test** — when a
  Claude Code subagent runs with worktree isolation the harness leaves a full nested
  checkout under `.claude/worktrees/` and registers it in `git worktree list`. Two
  consequences, both fixed here. (1) `.claude/` is a tracked directory
  (`hooks/session-start.sh`, `settings.json`), so the untracked scaffolding appeared in
  every `git status` and invited someone to commit a second checkout into the repository;
  it is now ignored by an **anchored**, directory-only rule that cannot repeat the
  unanchored `lib/` rule which silently swallowed committed files until #1040 — verified
  by re-listing all 1,249 tracked files against `git check-ignore` and confirming none is
  matched. (2) `tests/lint/test_irr_location_v14.py` walks the tree with `rglob` rather
  than `git ls-files`, so `.gitignore` does not reach it: the worktree's copy of
  `finance/irr.py` was reported as an out-of-home **R7 violation**, a false architectural
  alarm for any maintainer running a subagent. `.claude` joins `SKIP_DIR_NAMES`. The guard
  was re-proved against a planted `npv` in `analytics/`, so it is fixed, not silenced.
