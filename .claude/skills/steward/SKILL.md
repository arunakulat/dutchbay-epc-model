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

## Tracker-first intake (`INTAKE-01`)

Before editing or taking over a PR, fetch and verify `origin/main`; consult the live
[capability tracker](https://github.com/arunakulat/dutchbay-epc-model/issues/1353)
and enumerate **all** open PRs. Match the proposed work to a scoped tracker item or a
focused issue linked from it, recording a new item before edits if none exists. Advance
an actionable overlapping PR first. Record blocked or owner-deferred PRs with their
blocker and revisit trigger; they do not freeze unrelated work. Refresh the sweep before
opening a PR. Its body names the scoped issue or tracker comment, base SHA and overlap
disposition; the required receipts job checks their presence and tracker linkage. It cannot
prove when editing began or decide
whether two PRs overlap, so the reviewer still checks chronology and scope. For an
automatically opened PR, require a non-bot tracker comment posted after creation and
naming the exact PR and work item before follow-up changes or merge. A direct tracker
comment work item has `Work item:` and `Done when:` lines, not placeholders.

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
  in, the API still holds the previous base. That older base usually pulls `main`'s own grid and
  workflow changes into the diff, so the prediction tends to say Grid Study will run where CI
  will skip it. It can also under-predict: for example when the branch reverts a change `main`
  made, or when its own diff is empty. Either way, the `Classify changed paths` job decides.
  The snippet refuses to predict unless the checkout is at the pull request's head.

  ```bash
  PR=$(gh api repos/arunakulat/dutchbay-epc-model/pulls/<number> --jq '.base.sha + " " + .head.sha')
  .venv/bin/python - "$PR" <<'PY'
  import re, subprocess, sys
  from scripts.ci.classify_grid_study_paths import requires_grid_study
  parts = sys.argv[1].split()
  if len(parts) != 2 or not all(re.fullmatch(r"[0-9a-f]{40}", p) for p in parts):
      sys.exit(f"no base.sha/head.sha: {sys.argv[1][:80]!r}; check the pull-request number and the gh call")
  base, head = parts
  local = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
  if local != head:
      sys.exit(f"checkout is at {local}, not the pull request's head {head}")
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

**Review comes before the full suite (`REVIEW-01`).**

1. Open the pull request as a draft and freeze its head.
2. Post one comment headed `Evidence pack`. It carries the base and head SHAs, the subject
   manifest with blob hashes, the complete diff or its exact range, your local receipts, and a
   local run of `scripts/ci/check_pr_receipts.py` and `scripts/ci/check_pr_intake.py` against
   the exact body. Lanes verify the pack at the objects; it is a claim, never a disposition.
3. The lanes bind to that draft head. Only then mark the pull request ready for review, so the
   full suite runs once. While it is a draft, `test-suite.yml` skips the shards, the Coverage
   Gate and Grid Study and reports `Test Summary (draft: full suite deferred)`; the required
   `Test Summary` appears only once the ready run finishes. A green draft summary is the fast
   gates, never the suite.
4. If that run forces a change to a subject blob, both reviews restart (module 3 §6). A base
   advance needs §7's three proofs and a rebind, as before.
5. Treat a reviewer's snippet as a description of the gap, never as code to commit: reimplement
   it in your own terms, so the lane that found the gap is still reviewing work it did not write
   (module 3 §1).

The lane count follows the risk class. The three bounded low-risk classes in module 1 §3.1
are `R1` and take one lane: presentation-only code, test-only guard tightening, and record
corrections. Everything else takes the domain and assurance pair. When unsure, it is `R2`.

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
     stated blocker in it stands until a coordinator on record attributes it, after which the
     next rule applies, or until the owner withdraws it. State it on the pull request as a
     blocker.
   - Drop a condition that a later record withdrew or discharged, citing that record. Only the
     party whose finding it is, or the owner, can withdraw it, and only the party whose finding
     it is, or a reviewer other than whoever made the fix, can discharge it. A reviewer's record
     that a coordinator posts stays the reviewer's: posting it does not make its findings the
     coordinator's. Restating a reviewer's finding in a reconciliation does not either, and
     nobody discharges a condition on their own fix.
   - The owner may also withdraw or waive a condition, or decide that a lane need not run.
     `RECRUIT-01` contains no such waiver, so it rests on the owner's own authority.
     - A waiver names each condition or lane it waives. A general instruction to merge, such as
       "merge on CI green", restates `MERGE-01`, whose boundary says it does not replace a
       required review, so it waives nothing.
     - It counts only on record, as above. The relaying session must have received the owner's
       words directly, and quotes them exactly with when and where it received them. A
       second-hand relay counts only once the owner confirms it.
     - It lifts no `HOLD`, and the merge message quotes it.
   - Confirm that no veto is outstanding. Confirm that each required disposition is non-blocking
     and bound to the exact head, or carried to it under module 3 §7. A required disposition is
     one from each reviewer role that `RECRUIT-01` module 1 requires for the risk class.
     Handovers, review records, governance, dependency bumps and any code outside module 1
     §3.1's bounded low-risk classes are `R2` there; those classes are `R1` and take one lane
     (`REVIEW-01`). A required lane that has
     not run, and that the owner has not waived on record, is a stated blocker, not a silent hold
     (`MERGE-01`): say on the pull request which lane is missing.
   - The head you merge must equal the head the dispositions are bound to. A later push or base
     merge, by anyone, voids the binding. A base update needs module 3 §7's three proofs and a
     rebind. A documentation-only receipt commit needs §6's proofs and a rebind, and so does any
     other push that changes no file, such as a reworded commit message. Any change to a subject
     byte restarts both reviews.
   - At merge, re-verify every disposition the merge relies on, whether a rebind or a review
     bound directly to the final head (module 3 §6). All of these must hold:
     - the comment you cite still exists at the URL or ID you recorded;
     - it is unedited: `updated_at` equals `created_at`. Record dispositions as issue comments:
       a pull-request review shows no edit time, so it cannot pass this check;
     - the SHA-256 of the record it transcribes equals both the digest it states and its
       durable record, which is the file the comment names and hashes. Hash the bytes between
       the `8<` markers, drop the blank line next to each marker, and end with one LF. A hash of
       the whole comment body does not match;
     - it names the reviewer, the exact commit, tree and base, and the subject-manifest digest.

     An edit, deletion or mismatch invalidates the disposition until the reviewer issues a new
     one. So does a comment that states no content digest, and a durable record you cannot
     read: ask the reviewer to reissue the record, or merge from where the durable record is
     kept. Name in every record you post where its durable record is kept.
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
3. **Verify against the SHA the merge returned.** The commit the merge created must equal the freshly fetched tip of
   `origin/main` and have the head's tree, and its first parent must be the `main` SHA recorded in
   step 2. A squash has one parent. A two-parent merge commit must also have the head as its second
   parent. Supply `MERGE_SHA`, `HEAD_SHA` and `MAIN_SHA` as full commit IDs and `PARENTS` as `1`
   for a squash or `2` for a merge commit. Run each Bash fence in a fresh shell with its named
   environment variables set from the recorded data. Never interpolate record text into shell code.

   ```bash
   set -euo pipefail
   unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
   unset GIT_ALTERNATE_OBJECT_DIRECTORIES
   export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null
   export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
   export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false
   test "$(git config --get core.commitGraph)" = false
   git fetch origin refs/heads/main:refs/remotes/origin/main
   for sha in "$MERGE_SHA" "$HEAD_SHA" "$MAIN_SHA"; do
     [[ $sha =~ ^[0-9a-f]{40}$ ]] || exit 1
     test "$(git cat-file -t "$sha")" = commit
   done
   [[ $PARENTS = 1 || $PARENTS = 2 ]] || exit 1
   test "$(git rev-parse refs/remotes/origin/main)" = "$MERGE_SHA"
   expected_parents=$MAIN_SHA
   if [[ $PARENTS = 2 ]]; then expected_parents+=" $HEAD_SHA"; fi
   parents=$(git show -s --format=%P "$MERGE_SHA")
   test "$parents" = "$expected_parents"
   head_tree=$(git rev-parse "$HEAD_SHA^{tree}")
   test "$(git rev-parse "$MERGE_SHA^{tree}")" = "$head_tree"
   echo "Merge check: OK"
   ```

   The block stops at its first failed `test` and passes only when it prints `Merge check: OK`.
   Object checks use the stored commits, without local replacement refs, grafts or a local
   commit-graph file, whose cached parents and trees Git otherwise trusts without re-reading the
   commits. The `unset` lines drop inherited Git settings that would outrank these controls or
   point the block at another repository, object store or index, such as the
   `GIT_CONFIG_PARAMETERS` an enclosing `git -c` leaves behind. The `test` line after the exports
   refuses a Git older than 2.31, which ignores `GIT_CONFIG_COUNT` without an error. Keep these
   lines in every block; a clean worktree alone does not establish object identity.
   Silence, or a missing `OK` line, is a failure. If it fails, stop. Report the mismatch on the pull
   request and take no further action on it until the mismatch is resolved (`RECRUIT-01` module 3
   §7).
4. **Retire only branches, worktrees and non-protected venvs you own (`CLEANUP-01`).** Immediately
   after step 3's merge verification succeeds:
   - Inform the session/project tasklist, post a closure/reconciliation receipt on #1353 naming
     the merged pull request and commit SHA on `origin/main`, and close only the focused issue
     named by number on the merged pull request's own `Work item:` or closing line (for a train,
     the train issue and the focused issue named on each car's line), and only when its
     deliverable is complete. A `Work item:` line that names a #1353 comment closes nothing, and
     cleanup never closes tracker #1353.
   - Cleanup never closes a pull request. Closing an unmerged pull request needs a
     cited owner decision (where and when the owner decided), posted as a comment on that pull
     request before it is closed. The one exception is a train car, closed under "Merge trains"
     step 5 below.
   - Synchronize the clean primary checkout, when no other session is using it (`git fetch origin main && git checkout main && git pull --ff-only origin main`),
     remove the merged task worktree (`git worktree remove <worktree-path>`), and run
     `git worktree prune`, preserving any dirty or concurrently owned worktrees (`WORKTREE-01`).
   - Delete a branch only when its pull request's `merged_at` is set and every ref still present
     equals the merged head. Run this block in a fresh shell with `PR` and `BRANCH` set from the
     merged pull request, and for a train car also `CAR_HEAD` (the car head recorded in the train
     issue) and `TRAIN_PR` (the train pull request). Never paste record text into the code. The
     block reads everything immediately before deleting and stops at the first failed check,
     before any delete. A missing `OK` line is a failure. The pull request's `head.ref` must name
     the branch. No open pull request may use the branch as its base; that pull request's writer
     retargets it first. The remote ref is checked if it still exists, and skipped if GitHub
     already auto-deleted it (`delete_branch_on_merge` is on). The local ref is checked if it
     exists. A squash merge makes `git branch -d` refuse, so the local delete uses `-D`, but only
     after the check. A train car's pull request must be closed under "Merge trains" step 5, the
     train pull request must have merged, and the train must carry the car's landed commit, whose
     subject ends `(#<car PR>)`. Every GitHub read is assigned or compared before anything uses it,
     so a failed API call stops the block rather than reading as "no open pull request". The remote
     delete carries a lease on the checked head, so a push between the check and the delete makes
     the delete fail.

     ```bash
     set -euo pipefail
     unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
     unset GIT_ALTERNATE_OBJECT_DIRECTORIES
     export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null
     export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
     export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false
     test "$(git config --get core.commitGraph)" = false
     repo=arunakulat/dutchbay-epc-model
     CAR_HEAD=${CAR_HEAD:-}; TRAIN_PR=${TRAIN_PR:-}
     [[ $PR =~ ^[1-9][0-9]*$ ]] || exit 1
     test "$(git check-ref-format --branch "$BRANCH")" = "$BRANCH"
     if [ -n "$CAR_HEAD$TRAIN_PR" ]; then
       [[ $CAR_HEAD =~ ^[0-9a-f]{40}$ && $TRAIN_PR =~ ^[1-9][0-9]*$ ]] || exit 1
     fi
     test "$(gh api "repos/$repo/pulls/$PR" --jq '.head.ref')" = "$BRANCH"
     if [ -z "$CAR_HEAD" ]; then
       test -n "$(gh api "repos/$repo/pulls/$PR" --jq '.merged_at // ""')"
       want=$(gh api "repos/$repo/pulls/$PR" --jq '.head.sha')
     else
       test "$(gh api "repos/$repo/pulls/$PR" --jq '.state')" = "closed"
       test "$(gh api "repos/$repo/pulls/$PR" --jq '.head.sha')" = "$CAR_HEAD"
       test -n "$(gh api "repos/$repo/pulls/$TRAIN_PR" --jq '.merged_at // ""')"
       train_subjects=$(gh api "repos/$repo/pulls/$TRAIN_PR/commits" --paginate --jq '.[].commit.message | split("\n")[0]')
       grep -qE " \(#$PR\)\$" <<<"$train_subjects"
       want=$CAR_HEAD
     fi
     [[ $want =~ ^[0-9a-f]{40}$ ]] || exit 1
     open_on_base=$(gh api -X GET "repos/$repo/pulls" -f state=open -f base="$BRANCH" --jq '.[].number')
     test -z "$open_on_base"
     remote_head=$(git ls-remote origin "refs/heads/$BRANCH" | cut -f1)
     if [ -n "$remote_head" ]; then test "$remote_head" = "$want"; fi
     local_present=no
     if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
       local_present=yes
       test "$(git rev-parse --verify "refs/heads/$BRANCH")" = "$want"
     fi
     if [ -n "$remote_head" ]; then
       git push origin --delete --force-with-lease="refs/heads/$BRANCH:$want" "$BRANCH"
     fi
     if [ "$local_present" = yes ]; then git branch -D "$BRANCH"; fi
     git fetch --prune origin
     echo "CLEANUP-01 branch retirement: OK: #$PR $BRANCH at $want (remote: ${remote_head:-auto-deleted}; local: $local_present)"
     ```

     A branch whose pull request is open, closed unmerged, or whose head moved after the merge is
     never deleted by cleanup. `tests/lint/test_gwtf_canonical_source.py` runs this block against
     stubbed `gh` and `git` for the passing and failing cases.
   - Remove any temporary, per-task or worktree-local virtual environments (`.venv`, `.venv311` or
     ad-hoc venvs) associated with the retired worktree, while NEVER deleting, clearing, pruning
     or modifying the protected persistent Python 3.12 environment at
     `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`, `ENV-01`).

### Merge trains (`TRAIN-01`)

A train lets two or three reviewed pull requests share one full-suite run and land as separate
commits. Only the delivery coordinator holding the merge lease builds and lands one, and never a
train that carries a car it wrote. A pull request may always land alone instead.

1. **Pick the cars.** Each car is a draft whose required lanes are bound to its frozen draft head
   (`REVIEW-01`), with its merge-boundary conditions collected (step 1 above). Take two or three
   adjacent cars in queue order. They must be path-disjoint, none may be stacked on another, and
   at most one may be `R3` or change a KPI.
2. **Record the cars.** Open a focused train issue that lists every car and record it on #1353. For
   each car, take the pull-request number and the reviewed head from the car's lane records, and
   check the head against `refs/pull/<pr>/head`. Record the check against both lane records and
   the live ref on the train PR. In a private directory outside the train checkout, prepare
   `<pr>.msg` (the car's hand-written merge message, which meets `R18` and whose subject ends with
   `(#<pr>)`) and `<pr>.author` (one line, `Name <email>`). The author is the car pull request's
   author, as a squash merge of that pull request would record it. List the same values on the
   train issue. Use canonical LF-terminated text for both files and confirm the entire message meets
   every merge-boundary and restricted-material condition above. Record each file's Git blob ID
   (`git hash-object --stdin < "$file"`) alongside its text on the issue. Verify the files against
   that authoritative issue record and the PR author before using them. Set `CAR_DIR` to the
   absolute directory and take `TRAIN_CARS` from the verified issue record in queue order, as two or
   three space-separated `pr:reviewed_head:message_blob:author_blob` records. Keep the records fixed
   through build and pre-landing verification. Set `TRAIN_BRANCH` to the new `train/<date>-<n>` name.
3. **Build the train** in its clean, dedicated checkout from the current `main`, one non-merge commit per car.

   ```bash
   set -euo pipefail
   unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
   unset GIT_ALTERNATE_OBJECT_DIRECTORIES
   export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null
   export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
   export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false
   test "$(git config --get core.commitGraph)" = false
   git fetch origin refs/heads/main:refs/remotes/origin/main
   [[ $CAR_DIR = /* && -d $CAR_DIR ]] || exit 1
   record='[1-9][0-9]*:[0-9a-f]{40}:[0-9a-f]{40}:[0-9a-f]{40}'
   list="^$record( $record){1,2}$"
   [[ $TRAIN_CARS =~ $list ]] || exit 1
   IFS=' ' read -r -a cars <<< "$TRAIN_CARS"
   [[ $TRAIN_BRANCH = train/* ]] || exit 1
   git check-ref-format --branch "$TRAIN_BRANCH" >/dev/null
   dirty=$(git status --porcelain)
   test -z "$dirty"
   seen=" "
   for car in "${cars[@]}"; do
     IFS=: read -r pr head msg_blob author_blob <<< "$car"
     [[ $seen != *" $pr "* ]] || exit 1
     seen+="$pr "
     test "$(git cat-file -t "$head")" = commit
     remote=$(git ls-remote --exit-code origin "refs/pull/$pr/head")
     test "$remote" = "$head"$'\t'"refs/pull/$pr/head"
     msg="$CAR_DIR/$pr.msg"; ident="$CAR_DIR/$pr.author"
     test "$(git hash-object --stdin < "$msg")" = "$msg_blob"
     test "$(git hash-object --stdin < "$ident")" = "$author_blob"
     author=$(cat "$ident")
     identity='^[^<>[:space:]][^<>[:cntrl:]]* <[^<>[:space:]]+@[^<>[:space:]]+>$'
     [[ $author =~ $identity ]] || exit 1
     test "$(printf '%s\n' "$author" | git hash-object --stdin)" = "$author_blob"
     normalized=$(git stripspace < "$msg" | git hash-object --stdin)
     test "$normalized" = "$msg_blob"
     IFS= read -r subject < "$msg"
     [[ $subject = *" (#$pr)" ]] || exit 1
   done
   main=$(git rev-parse refs/remotes/origin/main)
   git switch -c "$TRAIN_BRANCH" "$main"
   for car in "${cars[@]}"; do
     IFS=: read -r pr head msg_blob author_blob <<< "$car"
     base=$(git merge-base "$main" "$head")
     git diff --binary --no-ext-diff --no-textconv "$base" "$head" -- | git apply --index
     author=$(cat "$CAR_DIR/$pr.author")
     git commit -q --cleanup=verbatim --author="$author" -F "$CAR_DIR/$pr.msg"
   done
   built=$(git rev-parse HEAD)
   echo "TRAIN-01 train built: $built"
   ```

   If a car's diff does not apply cleanly, the block stops: delete the branch and rebuild without
   that car. Commit nothing else. **Run the pre-landing check (step 6) on the train before you open
   it.** Supply the built `TRAIN_SHA`, current `MAIN_SHA` and the verified car records. Then open the train as one pull request, ready for review, with the train issue as its
   `Work item:` and a `VERIFY-01` receipts table. The full suite runs once. If `main` moves before
   the train lands, never merge `main` into the train: a merge commit on it fails the pre-landing
   check. Rebuild the train from the new `main` instead, and repeat module 3 §8's proofs and the
   pre-landing check on the new train head.
4. **Carry the bindings.** Each car's lanes record module 3 §8's three proofs against the train
   head. A car whose proof fails leaves the train. For a KPI car, the train head's lender KPI vector
   must equal the vector the owner signed off, which is the vector at the car's reviewed head. If no
   car changes a KPI, it must equal `main`'s. Set `REFERENCE_SHA` to the signed-off car's reviewed head, or to the recorded
   `main` SHA when no car changes a KPI. Set `TRAIN_SHA` to the verified train head. From the
   repository root, use the absolute `DUTCHBAY_VENV` verified by the environment preflight.

   ```bash
   set -euo pipefail
   unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
   unset GIT_ALTERNATE_OBJECT_DIRECTORIES
   export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null
   export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
   export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false
   test "$(git config --get core.commitGraph)" = false
   [[ $DUTCHBAY_VENV = /* && -x $DUTCHBAY_VENV/bin/python ]] || exit 1
   for sha in "$REFERENCE_SHA" "$TRAIN_SHA"; do
     [[ $sha =~ ^[0-9a-f]{40}$ ]] || exit 1
     test "$(git cat-file -t "$sha")" = commit
   done
   measure() (
     set -euo pipefail
     rev=$1
     private=$(mktemp -d "${TMPDIR:-/tmp}/dutchbay-kpi.XXXXXXXX")
     private=$(cd -P -- "$private" && pwd -P)
     checkout="$private/checkout"
     printf 'KPI scratch for %s: %s\n' "$rev" "$private" >&2
     [[ ! -e $checkout && ! -L $checkout ]] || exit 1
     git worktree add -q --detach "$checkout" "$rev"
     owner=$(git -C "$checkout" rev-parse --absolute-git-dir)
     inspect_scratch() {
       previous=$1
       # Never delete from an evaluation trap: retain even apparently clean scratch state.
       [[ -d $checkout && ! -L $checkout ]] || exit 1
       test "$(git -C "$checkout" rev-parse --show-toplevel)" = "$checkout"
       test "$(git -C "$checkout" rev-parse --absolute-git-dir)" = "$owner"
       test "$(git -C "$checkout" rev-parse --abbrev-ref HEAD)" = HEAD
       test "$(git -C "$checkout" rev-parse HEAD)" = "$rev"
       flags=$(git -C "$checkout" ls-files -v | sed '/^H /d')
       test -z "$flags"
       special=$(find "$checkout" -mindepth 1 ! -type f ! -type d ! -type l -print)
       test -z "$special"
       dirty=$(git -C "$checkout" -c core.fsmonitor=false -c core.filemode=true status --porcelain --ignored --untracked-files=all --ignore-submodules=none)
       test -z "$dirty"
       printf 'KPI scratch retained for owner inspection: %s\n' "$private" >&2
       exit "$previous"
     }
     trap 'inspect_scratch "$?"' EXIT
     (
       cd -- "$checkout"
       PYTHONPATH="$checkout" PYTHONDONTWRITEBYTECODE=1 "$DUTCHBAY_VENV/bin/python" - <<'PY'
   import hashlib
   import json
   import logging
   import math
   import os
   import sys
   from pathlib import Path
   from contextlib import redirect_stdout

   if Path(sys.prefix).resolve() != Path(os.environ["DUTCHBAY_VENV"]).resolve():
       sys.exit("Unexpected lender-case interpreter")
   logging.disable(logging.INFO)
   with redirect_stdout(sys.stderr):
       from analytics import pipeline_v14_enhanced as pipeline
       if Path(pipeline.__file__).resolve() != Path.cwd() / "analytics/pipeline_v14_enhanced.py":
           sys.exit("The lender pipeline did not come from the measured checkout")
       result = pipeline.run_v14_pipeline(
           config="scenarios/dutchbay_lendercase_2025Q4.yaml", validation_mode="strict"
       )
   if result["status"] != "success" or result["validation_mode"] != "strict":
       sys.exit("Strict lender-case evaluation did not succeed")
   kpis = result["kpis"]
   numeric = set("""
   average_equity_cash_on_cash avg_dscr balloon_covenant_breach balloon_pct balloon_residual
   discount_rate_used dscr_max dscr_mean dscr_median dscr_min dscr_p10 dscr_p90 dscr_std
   equity_debt_service_shortfall_years equity_irr equity_moic equity_multiple equity_npv final_cfads_usd irr llcr max_debt_usd
   mean_operational_cfads_usd min_dscr min_dscr_period npv plcr project_irr project_npv
   project_npv_prudential prudential_rate_used total_cfads_usd total_equity_distributed_usd
   equity_sponsor_cure_usd total_idc_usd
   """.split())
   labels = {"scenario_name", "wacc_label", "equity_distribution_status", "project_irr_status"}
   expected = numeric | labels | {"dscr_series", "wacc_is_real", "equity_covenant_locked_years"}
   if not isinstance(kpis, dict) or kpis.keys() != expected:
       sys.exit("Unexpected lender KPI key set")

   def finite(value):
       return type(value) in (float, int) and math.isfinite(value)

   undefined_ok = {"equity_irr"}  # An undefined IRR is a supported value.
   if kpis.get("project_irr_status") == "undefined":
       undefined_ok |= {"project_irr", "irr"}
   for name in numeric:
       if name in undefined_ok and kpis[name] is None:
           continue
       if not finite(kpis[name]):
           sys.exit(f"Invalid lender KPI: {name}")
   if not all(isinstance(kpis[key], str) and kpis[key].strip() for key in labels):
       sys.exit("Invalid lender KPI label")
   series = kpis["dscr_series"]
   if not isinstance(series, list) or not series or not all(map(finite, series)):
       sys.exit("Invalid lender DSCR series")
   if (type(kpis["wacc_is_real"]) is not bool or type(kpis["equity_covenant_locked_years"]) is not int
           or kpis["equity_covenant_locked_years"] < 0 or kpis["equity_distribution_status"] != "computed"):
       sys.exit("Invalid lender KPI metadata")
   vector = {key: repr(value) if isinstance(value, float) else value for key, value in kpis.items()}
   encoded = json.dumps(vector, sort_keys=True, allow_nan=False).encode()
   print(len(kpis), hashlib.sha256(encoded).hexdigest())
   PY
     )
   )
   want=$(measure "$REFERENCE_SHA")
   got=$(measure "$TRAIN_SHA")
   receipt='^42 [0-9a-f]{64}$'
   [[ $want =~ $receipt && $got =~ $receipt ]] || exit 1
   printf 'reference: %s\ntrain: %s\n' "$want" "$got"
   test "$got" = "$want"
   echo "TRAIN-01 KPI check: OK"
   ```

   It prints the count and SHA-256 of the 42-KPI lender vector at each revision, and passes only
   when they are equal. The schema describes the current lender vector. A changed schema needs a
   reviewed contract update, and `tests/lint/test_train_policy.py` runs this schema check on the
   real lender case so that a new or removed KPI fails a test before it fails a train. Scratch worktrees are retained on success and failure: Git status
   is not proof that deleting a directory preserves every filesystem object. Index flags that
   can conceal tracked changes and special files also refuse the check. Inspect the named
   locations and reconcile ownership before any separately authorized retirement; this block
   performs no automatic removal. After inspection, retire each scratch with
   `git worktree remove <checkout>` and then `git worktree prune`. The operating system may clear
   `TMPDIR` on its own schedule (on macOS, under `/var/folders`), which leaves registrations that
   only `git worktree prune` removes. Both are owned scratch under `CLEANUP-01`.
5. **If the train goes red,** edit no car on it. Split the train and run each part as a smaller
   train or a single pull request. A fix goes on the car's own branch, which restarts its reviews
   (module 3 §6).
6. **Land it with rebase-merge, never squash.** Run the pre-landing check before the train is
   opened ready (step 3), and again just before landing, with the protected `main` SHA recorded at
   that moment. It checks that the recorded `main` is `origin/main`, that the train is exactly one
   non-merge commit per car on top of it, and that each train commit is exactly its car's reviewed
   diff, under its recorded message and author, with each car's reviewed head still its pull
   request's head:

   ```bash
   set -euo pipefail
   unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
   unset GIT_ALTERNATE_OBJECT_DIRECTORIES
   export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null
   export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
   export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false
   test "$(git config --get core.commitGraph)" = false
   git fetch origin refs/heads/main:refs/remotes/origin/main
   for sha in "$MAIN_SHA" "$TRAIN_SHA"; do
     [[ $sha =~ ^[0-9a-f]{40}$ ]] || exit 1
     test "$(git cat-file -t "$sha")" = commit
   done
   [[ $CAR_DIR = /* && -d $CAR_DIR ]] || exit 1
   record='[1-9][0-9]*:[0-9a-f]{40}:[0-9a-f]{40}:[0-9a-f]{40}'
   list="^$record( $record){1,2}$"
   [[ $TRAIN_CARS =~ $list ]] || exit 1
   IFS=' ' read -r -a cars <<< "$TRAIN_CARS"
   test "$(git rev-parse refs/remotes/origin/main)" = "$MAIN_SHA"
   n=${#cars[@]}
   merges=$(git rev-list --merges "$MAIN_SHA..$TRAIN_SHA")
   test -z "$merges"
   test "$(git rev-parse --verify "$TRAIN_SHA~$n")" = "$MAIN_SHA"
   raw_diff() {
     git diff --raw -z --no-renames --no-abbrev --no-ext-diff --ignore-submodules=none "$1" "$2" -- |
       od -An -v -tx1
   }
   seen=" "
   k=0
   for car in "${cars[@]}"; do
     IFS=: read -r pr head msg_blob author_blob <<< "$car"
     [[ $seen != *" $pr "* ]] || exit 1
     seen+="$pr "
     test "$(git cat-file -t "$head")" = commit
     remote=$(git ls-remote --exit-code origin "refs/pull/$pr/head")
     test "$remote" = "$head"$'\t'"refs/pull/$pr/head"
     msg="$CAR_DIR/$pr.msg"; ident="$CAR_DIR/$pr.author"
     test "$(git hash-object --stdin < "$msg")" = "$msg_blob"
     test "$(git hash-object --stdin < "$ident")" = "$author_blob"
     k=$((k + 1))
     commit=$(git rev-parse --verify "$TRAIN_SHA~$((n - k))^{commit}")
     base=$(git merge-base "$MAIN_SHA" "$head")
     want=$(raw_diff "$base" "$head")
     got=$(raw_diff "$commit^" "$commit")
     test -n "$want"
     test "$got" = "$want"
     message=$(git show -s --format=format:%B "$commit" | git hash-object --stdin)
     author=$(git show -s --format='%an <%ae>' "$commit" | git hash-object --stdin)
     test "$message" = "$msg_blob"
     test "$author" = "$author_blob"
     subject=$(git show -s --format=%s "$commit")
     [[ $subject = *" (#$pr)" ]] || exit 1
   done
   echo "TRAIN-01 pre-landing check: OK"
   ```

   The loop compares train commit `k` with car `k` using the complete NUL-framed raw diff. The hex
   encoding preserves every path byte, change status and both sides' modes and object IDs. The
   loop also compares the car's recorded message and author, and a
   subject ending with `(#<pr>)`. It also checks that `refs/pull/<pr>/head` is still the reviewed
   head, so a car list that pairs a number with another car's head fails. A train with two cars'
   messages swapped, a stray file, part of one car's diff in another car's commit, or a merge
   commit fails here, although every tree comparison would pass it (module 3 §8).

   Land the train with the merge call's expected head SHA set to `TRAIN_SHA`, as a single pull
   request's merge pins its head, so a late push to the train branch refuses the merge rather
   than reaching `main`.

   After it lands, set `LANDED_SHA` to the SHA the merge returned, `TRAIN_SHA` to the reviewed train
   head, `MAIN_SHA` to the base recorded before landing, and `CAR_COUNT` to the recorded count. The
   returned SHA must equal the fetched tip of protected main. If main advanced again, stop and
   reconcile the landing evidence. Verify the final tree and every car in both first-parent chains.

   ```bash
   set -euo pipefail
   unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
   unset GIT_ALTERNATE_OBJECT_DIRECTORIES
   export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null
   export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
   export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false
   test "$(git config --get core.commitGraph)" = false
   git fetch origin refs/heads/main:refs/remotes/origin/main
   for sha in "$MAIN_SHA" "$TRAIN_SHA" "$LANDED_SHA"; do
     [[ $sha =~ ^[0-9a-f]{40}$ ]] || exit 1
     test "$(git cat-file -t "$sha")" = commit
   done
   [[ $CAR_COUNT = 2 || $CAR_COUNT = 3 ]] || exit 1
   test "$(git rev-parse refs/remotes/origin/main)" = "$LANDED_SHA"
   merges=$(git rev-list --merges "$MAIN_SHA..$LANDED_SHA" "$MAIN_SHA..$TRAIN_SHA")
   test -z "$merges"
   test "$(git rev-parse --verify "$LANDED_SHA~$CAR_COUNT")" = "$MAIN_SHA"
   test "$(git rev-parse --verify "$TRAIN_SHA~$CAR_COUNT")" = "$MAIN_SHA"
   final_tree=$(git rev-parse --verify "$TRAIN_SHA^{tree}")
   test "$(git rev-parse --verify "$LANDED_SHA^{tree}")" = "$final_tree"
   for ((i=0; i<CAR_COUNT; i++)); do
     landed=$(git rev-parse --verify "$LANDED_SHA~$i^{commit}")
     train=$(git rev-parse --verify "$TRAIN_SHA~$i^{commit}")
     if ((i > 0)); then
       tree=$(git rev-parse "$train^{tree}")
       test "$(git rev-parse "$landed^{tree}")" = "$tree"
     fi
     format='format:%B%x00%an <%ae>'
     want=$(git show -s --format="$format" "$train" | git hash-object --stdin)
     got=$(git show -s --format="$format" "$landed" | git hash-object --stdin)
     test "$got" = "$want"
   done
   echo "TRAIN-01 landing check: OK"
   ```

   Each block stops at its first failed `test` and passes only when it prints its `OK` line.
   Silence, or a missing `OK` line, is a failure. Run each block whole, as written, and never
   drop its `set -euo pipefail` line. If a block fails, stop and report it on the train pull
   request (module 3 §8). Otherwise, on each car's pull request, first post a pointer comment
   naming its commit on `main`, then close that pull request. This is `CLEANUP-01`'s one exception
   to never closing a pull request, and it covers only the cars listed in the train issue whose
   commits the block above proved are on `main`.

The full suite ran on the union only. The commits between cars on `main` were never run by the
full suite on their own, and the train lifts no `HOLD`.

Merging is delivery authority only. Under `MERGE-01`'s boundary, it lifts no `HOLD` and
confers no grade, release, lender or Board authority.
