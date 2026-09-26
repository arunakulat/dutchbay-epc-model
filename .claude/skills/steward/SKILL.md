---
name: steward
description: Repository conventions for driving a dutchbay-epc-model pull request to a mergeable state - base currency, what "green" means here, Grid Study, VERIFY-01 receipts, changelog fragments, corpus manifests and merge mechanics. Use when watching, fixing or merging a pull request in this repository.
---

# Steward: driving a pull request in dutchbay-epc-model

This skill collects the pull-request conventions that sessions otherwise rediscover. It
cites rules rather than restating them. The authority is `go_with_the_flow_rules_v3_0_clean.csv`
and `AGENTS.md`, and where they disagree with this file, they win.

Load the ruleset and the three framework principles before acting. `CLAUDE.md` "Rules and
formats that govern this repository" has the command and the rule IDs.

This skill confers no merge authority. Merge when the session has been asked to deliver or
merge the pull request. Once it has been asked, `MERGE-01` means you merge on green without
asking again.

## Read the whole pull request first

On every event or check-in, read the current head and act on all of it:
- its mergeable state;
- every check run on that exact SHA;
- the receipts table in the body;
- open review threads.

A red or conflicted head is work now, never "waiting on review".

## Base currency

`MERGE-01` does not apply while a branch is behind `main`, and the pull request then reports
`behind`. Bring `main` in with a **merge commit**. Never rebase or force-push a branch you do
not own. The pull request's diff should not change: confirm with
`git diff --stat origin/main...HEAD`. Re-read the mergeable state at the moment of merging,
because `main` moves while CI runs.

## What green means here (`MERGE-01`)

Green means every check on the exact head succeeded, or was skipped for a stated reason:
- `Stochastic Qualification` and `Report Qualification` run only on schedule or manual
  dispatch, so they skip on pull requests.
- `Grid Study` may skip only when `Classify changed paths` classified the diff as unrelated to
  the governed QSTS/grid surface. When the diff touches that surface, Grid Study must *run and
  pass* on the exact head (see `AGENTS.md` "Verification"). Predict the classification locally:

  ```bash
  .venv/bin/python - <<'PY'
  import subprocess
  from scripts.ci.classify_grid_study_paths import requires_grid_study
  paths = subprocess.check_output(["git", "diff", "--name-only", "origin/main...HEAD"], text=True).split()
  print("Grid Study required:", requires_grid_study(paths))
  PY
  ```

- A diff made only of `*.md`, `changelog.d/` and `docs/` skips the sharded suite. For such a
  diff, `fastlane` is the real gate, including the corpus manifest guard
  `tests/lint/test_nso_corpus_manifest_integrity.py`.
- `Verification receipts (VERIFY-01)` reads the pull-request body. Every Result cell of the
  receipts table must hold a result or `not run - <reason>`. Editing the body re-runs it.

## Changes you push

- **Receipts.** For a CI fix, reproduce the failure, then show the same check passing. Paste
  the command and its result into the body's receipts table (`VERIFY-01`).
- **Changelog.** Add one fragment, `changelog.d/<id-or-slug>.<category>.md`, whose body has no
  Markdown headings. Never edit `CHANGELOG.md` directly. Validate with
  `.venv/bin/python scripts/compile_changelog.py --dry-run`.
- **Commits.** Follow `R18`, which admits only the eleven Conventional Commits types.
- **Corpus and manifests.** Work through `AGENTS.md` "Four ways a corpus commit goes wrong".
  `sha256sum -c MANIFEST.sha256` must exit 0. Refresh parent manifests with
  `scripts/analysis/refresh_corpus_manifest.py`.
- **Financial-model changes.** Follow `AGENTS.md` "Financial-model changes": regression tests,
  impact disclosure, `VERSION` and `CHANGELOG.md`, and `TEST-01`'s independent oracle.
- **Local runs.** Use `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. Five failures in
  `tests/lint/test_cloud_audit_review_sandbox.py` are local to cloud containers and
  pre-existing (see `CLAUDE.md`). Declare them in your receipts; never skip a test.
- **Size.** Keep each fix minimal. One validated push beats several speculative ones
  (`DELIVERY-01`).

## Review

Where `RECRUIT-01` independent review was not run, record it in the receipts as
`not run - <reason>`. Never assert a reviewer's acceptance that is not on record; the #1292
changelog erratum records what happens when that goes wrong.

## Merging

1. Squash merge, titled as the pull-request title followed by ` (#<number>)`, with the
   expected head SHA pinned so a late push cannot slip in.
2. Afterwards, confirm the squash commit's tree equals the pull-request head's tree and that
   its parent is the previous `main`:

   ```bash
   git fetch origin main
   test "$(git rev-parse origin/main^{tree})" = "$(git rev-parse <head-sha>^{tree})"
   test "$(git rev-parse origin/main^)" = "<previous-main-sha>"
   ```

3. Retire only branches and worktrees you own.

Merging is delivery authority only. Under `MERGE-01`'s boundary, it lifts no `HOLD` and
confers no grade, release, lender or Board authority.
