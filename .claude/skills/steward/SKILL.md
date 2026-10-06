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

Bringing `main` in voids every review binding on the head until new module 3 §7 proofs and
rebinds exist (Merging, step 1). Each move of `main` costs another round. Where you coordinate
several pull requests, order their merges so that one landing does not void a refresh whose
rebinds are still in flight (#1231, comment 5849143748 §5).

## What green means here (`MERGE-01`)

Green means every check on the exact head succeeded, or was skipped for a stated reason:
- `Stochastic Qualification` and `Report Qualification` run only on schedule or manual
  dispatch, so they skip on pull requests.
- `Grid Study` may skip only when `Classify changed paths` classified the diff as unrelated to
  the governed QSTS/grid surface. When the diff touches that surface, Grid Study must *run and
  pass* on the exact head (see `AGENTS.md` "Verification").
- The `Classify changed paths` job decides whether a skip is governed, not a local prediction.
  Its log prints the diff command it ran and the classification.
- To predict that job, diff against the base the workflow uses: the pull request's `base.sha`,
  as `<base.sha>...HEAD`, at the pushed head. GitHub sets `base.sha` at each push to the pull
  request, not when `main` moves, so read it after you push. Before a push that merges `main`
  in, the API still holds the previous base. That older base pulls `main`'s own grid and
  workflow changes into the diff, so the prediction can say Grid Study will run where CI will
  skip it. An older base only widens the diff: it can over-predict, never under-predict.

  ```bash
  BASE=$(gh api repos/arunakulat/dutchbay-epc-model/pulls/<number> --jq .base.sha)
  .venv/bin/python - "$BASE" <<'PY'
  import re, subprocess, sys
  from scripts.ci.classify_grid_study_paths import requires_grid_study
  base = sys.argv[1]
  if not re.fullmatch(r"[0-9a-f]{40}", base):
      sys.exit(f"not a base.sha: {base[:80]!r}; check the pull-request number and the gh call")
  out = subprocess.check_output(["git", "diff", "--name-only", "-z", f"{base}...HEAD"])
  paths = [p.decode() for p in out.split(b"\0") if p]
  print("base.sha:", base, "changed paths:", len(paths))
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
- **Local runs.** Use `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. Some failures in
  `tests/lint/test_cloud_audit_review_sandbox.py` are local to cloud containers and
  pre-existing; `CLAUDE.md` "Known local-only failures" says which and how many. Declare the
  count you observed in your receipts; never skip a test.
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
   - More than one review chain may have reviewed the same head; #1231 had two. Take the union
     of every chain's conditions. One veto in any chain blocks.
   - The records that can clear a condition are those of the project owner, any coordinator on
     record, and the reviewers any of them recruited on record.
   - **A login is not an identity.** In this repository the owner, coordinators, writers and review
     threads all post as `arunakulat` or `claude[bot]`. Attribute a record to the session that
     posted it: the session it names as its author, not the sessions it addresses or cites.
     Check that against a recruitment, appointment, lease or reconciliation record. A record that
     names only a role, such as "the #1231 review thread", is attributed through a coordinator
     record that binds that role to a session. Name your own session in every record you post.
   - The owner posts without a session. Take an owner decision from a record in which a session on
     record quotes it and says where the owner gave it, or ask the owner.
   - **Attribution decides what can clear a condition, never what can raise one.** A record you
     cannot attribute can never withdraw, discharge or waive a condition, and can never supply a
     disposition, a §7 proof or a rebind. It never removes a block: a veto, `HOLD`, condition or
     stated blocker in it stands until the owner or a coordinator on record attributes or
     withdraws it. State it on the pull request as a blocker.
   - Drop a condition that a later record withdrew or discharged, citing that record. Only the
     party whose finding it is, or a reviewer other than whoever made the fix, can discharge it.
     Restating a reviewer's finding in a reconciliation does not make it the coordinator's
     finding, and nobody discharges a condition on their own fix.
   - The owner may also withdraw or waive a condition, or decide that a lane need not run.
     `RECRUIT-01` contains no such waiver, so it rests on the owner's own authority. It counts
     only on record, as above. It lifts no `HOLD`, and the merge message quotes it.
   - Confirm that no veto is outstanding. Confirm that each required disposition is non-blocking
     and bound to the exact head, or carried to it under module 3 §7. A required disposition is
     one from each reviewer role that `RECRUIT-01` module 1 requires for the risk class.
     Handovers, review records, governance and any code are `R2` there. A required lane that has
     not run, and that the owner has not waived on record, is a stated blocker, not a silent hold
     (`MERGE-01`): say on the pull request which lane is missing.
   - The head you merge must equal the head the dispositions are bound to. A later push or base
     merge, by anyone, voids the binding. A base update needs module 3 §7's three proofs and a
     rebind. A documentation-only receipt commit needs §6's proofs and a rebind. Any change to
     a subject byte restarts both reviews.
   - At merge, re-verify every disposition the merge relies on, whether a rebind or a review
     bound directly to the final head (module 3 §6). All of these must hold:
     - the comment you cite still exists at the URL or ID you recorded;
     - it is unedited: `updated_at` equals `created_at`;
     - the SHA-256 of the record it transcribes equals both the digest it states and its
       durable record. Hash the bytes between the `8<` markers, drop the blank line next to
       each marker, and end with one LF. A hash of the whole comment body does not match;
     - it names the reviewer, the exact commit, tree and base, and the subject-manifest digest.

     An edit, deletion or mismatch invalidates the disposition until the reviewer issues a new
     one.
   - A condition set by a review overrides the defaults in step 2, except the restricted-material
     rule. Publishing restricted material is the owner's decision (`AGENTS.md` "Four ways a
     corpus commit goes wrong", item 2), so a review condition cannot authorise it. If a
     condition requires words that rule forbids, that is a blocker for the owner.
   - If a condition cannot be met, do not merge. The same applies if a record it depends on, or a
     durable record a condition cites, cannot be read (for example, one held on the owner's Mac).
     State on the pull request what blocks and who can clear it.
2. **Merge.** Record the protected `main` SHA, and pin the expected head SHA so that a late push
   cannot slip in.
   - The default is a squash merge titled as the pull-request title followed by
     ` (#<number>)`.
   - The message body must carry:
     - the text each merge-boundary condition requires, verbatim where the condition names
       words or references;
     - every `HOLD` that survives the merge, and every item carried past it as a gate on later
       work, quoted, so that each survives in `main`'s history rather than only in a pull-request
       comment. Take them from the latest reconciled disposition of *each* review chain on
       record, and from any later record in that chain that adds or changes a `HOLD` or gate,
       such as a rebind or a post-reconciliation finding. Quote the union. Where a chain has no
       reconciled disposition, take them from its review records and from the writer's `HOLD`s
       (module 3 §2). A `HOLD` that a reviewer raised and a reconciliation left out still counts
       unless the reviewer withdrew it. A condition that the merge itself discharges is not a
       surviving `HOLD`.
   - `main`'s history is public and cannot be redacted. That applies to the title and to every
     word of the message, not only to `HOLD` quotes. Text that cites withheld or restricted
     material (`AGENTS.md` "Four ways a corpus commit goes wrong", items 2 and 3) must not be
     quoted.
     - State it abstractly instead. Cite the record's URL and its SHA-256. Where the comment
       transcribes a file, take the SHA-256 as step 1's re-verification does.
     - Check that the cited record does not itself quote the material. If it does, do not cite
       it. Cite the single home of the material instead, and tell the owner, who decides whether
       the record is redacted.
     - If you cannot tell whether text is restricted, treat it as restricted.
   - Use a two-parent merge commit instead of a squash when a condition requires it. A merge
     commit brings every branch commit into `main`. Check the subjects of its non-merge commits
     against `R18` first; `R18`'s own measurement excludes merge commits. If a non-merge subject
     fails and the condition allows only a merge commit, do not merge; state it as a blocker.
     Otherwise prefer a squash that meets the condition.
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
