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

1. **Collect the merge-boundary conditions before anything else.** A merge-boundary condition is
   any finding or disposition that blocks at the merge itself. Examples: a squash message that
   must name something or cite particular pull requests, a required merge method, a corrected
   pull-request body, or a rebind after a base refresh. #1231's assurance finding F-09 is the
   worked example: the squash message must name the A1 restore and reference #1225 and #1232, or
   the pull request must merge with a merge commit.
   - Look in the pull-request body, its comments and review threads, and the durable records they
     cite. List every condition, including ones carried forward from earlier cycles and re-imposed
     unchanged.
   - Count only records from the project owner, the coordinator and the reviewers the coordinator
     recruited on record. Drop a condition that a later record withdrew or discharged, citing
     that record.
   - Confirm that no veto is outstanding. Confirm that each required disposition is non-blocking
     and bound to the exact head, or carried to it under `RECRUIT-01` module 3 §7.
   - A condition set by a review overrides the defaults in step 2.
   - If a condition cannot be met, do not merge. The same applies if a record it depends on cannot
     be read, for example one held on the owner's Mac. State on the pull request what blocks and
     who can clear it.
2. **Merge.** Record the protected `main` SHA, and pin the expected head SHA so that a late push
   cannot slip in.
   - The default is a squash merge titled as the pull-request title followed by
     ` (#<number>)`.
   - The message body must carry:
     - the text each merge-boundary condition requires, verbatim where the condition names
       words or references;
     - every `HOLD` that survives the merge, quoted, so that it survives in `main`'s history
       rather than only in a pull-request comment. Take them from the latest reconciled
       disposition. Where there is none, take them from each review record and from the writer's
       `HOLD`s (module 3 §2). A condition that the merge itself discharges is not a surviving
       `HOLD`.
   - `main`'s history is public and cannot be redacted. A `HOLD` that cites withheld or
     restricted material (`AGENTS.md` "Four ways a corpus commit goes wrong", items 2 and 3)
     must not be quoted. State it abstractly, and cite the record's URL and content SHA-256.
   - Use a two-parent merge commit instead of a squash when a condition requires it. A merge
     commit brings every branch commit into `main`. Check their subjects against `R18` first,
     and prefer a squash that meets the condition wherever the condition allows one.
   - Before submitting, re-read each condition against the final message text.
3. **Verify against the SHA the merge returned.** The commit the merge created must have the
   head's tree, and its first parent must be the `main` SHA recorded in step 2. A two-parent merge
   commit must also have the head as its second parent:

   ```bash
   git fetch origin main
   test "$(git rev-parse <merge-sha>^{tree})" = "$(git rev-parse <head-sha>^{tree})"
   test "$(git rev-parse <merge-sha>^1)" = "<main-sha-recorded-in-step-2>"
   test "$(git rev-parse <merge-sha>^2)" = "<head-sha>"   # two-parent merge commit only
   ```

   If any test fails, stop. Report the mismatch on the pull request and take no further action on
   it until the mismatch is resolved (`RECRUIT-01` module 3 §7).
4. Retire only branches and worktrees you own.

Merging is delivery authority only. Under `MERGE-01`'s boundary, it lifts no `HOLD` and
confers no grade, release, lender or Board authority.
