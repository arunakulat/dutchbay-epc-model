# Session handover — 2026-10-05: v15.6.1 release and clean-thread bootstrap

## Status and predecessor

This is the current repository startup record once committed and selected by
`scripts/list_session_handover_records.py`. Its predecessor is
`docs/SESSION_HANDOVER_2026-09-26_PLATFORM_PLAN.md`. It supersedes the predecessor's
startup routing and live release/cleanup snapshot, not its recorded owner decisions,
source-handling restrictions, or unresolved workstream questions. The H08 and
September 7 records remain historical evidence; their pending-delivery instructions
and version numbers must not be replayed as current tasks. Reconcile any workstream
against its current PRs and controlling sources before implementation.

This record is a documentation-only successor to the completed release session.
Its own PR and Git history govern subsequent delivery status. At authoring, protected
`main` was `32eaa91f70d73ca1c2284761b003bdcb56792c3c`, tree
`c2d9e58ef1668373a36c35df79da5f5cf469beff`. Merging this handover advances `main`,
but does not move either release tag or create another release.

## Completed release work

- Original [PR #1298](https://github.com/arunakulat/dutchbay-epc-model/pull/1298)
  was superseded. PR #1311 added deterministic changelog batching; PRs #1312–#1316
  compiled and removed 167 fragments in batches of 40, 40, 40, 40 and 7.
- [PR #1317](https://github.com/arunakulat/dutchbay-epc-model/pull/1317) delivered
  corrected 15.6.0 metadata at `ad5596158a4e1c5eeae94937244a3ebaf4c696c7`.
  The unsigned annotated `v15.6.0` tag object is
  `8c8b70af675e1c7631f342c795fac883c40605fd`.
- [Release run 37177469212](https://github.com/arunakulat/dutchbay-epc-model/actions/runs/37177469212)
  failed: 8,774 passed, one failed, 18 skipped. The physical-receipt test needed
  historical commit `4da2a82352d532138ee7f2483b82dfbf5a1d9c2b`, unavailable in the
  shallow checkout. No 15.6.0 release artifact was published. Preserve the failed tag;
  do not retag it or retry it as the corrective release.
- [PR #1318](https://github.com/arunakulat/dutchbay-epc-model/pull/1318) fixed release
  checkout with `fetch-depth: 0`, added
  `tests/lint/test_release_workflow_history.py`, and updated 15.6.1 metadata and
  derived hashes. Reviewed remote head:
  `c2a884923c2d56617934993655d8d4cb25e7824a`; protected squash merge:
  `32eaa91f70d73ca1c2284761b003bdcb56792c3c`.

### Published artifact receipt

| Item | Recorded value |
|---|---|
| Public release | <https://github.com/arunakulat/dutchbay-epc-model/releases/tag/v15.6.1> |
| Publication | 2026-10-04 12:42:54 UTC; non-draft, non-prerelease |
| Tag | Unsigned annotated `v15.6.1`, message `DutchBay 15.6.1` |
| Tag object | `f542539d581c9d113cd6e79bfa5153c91e5424df` |
| Target commit | `32eaa91f70d73ca1c2284761b003bdcb56792c3c` |
| Release workflow | [37202114147](https://github.com/arunakulat/dutchbay-epc-model/actions/runs/37202114147), SUCCESS |
| Asset | `DutchBay_Model_V15.6.1.zip`, 44,578 bytes, asset ID `609831926` |
| Asset SHA-256 | `7c455b122d5a68f522a47a000747bb2646b6ecd7764519a61ee80f34b811055e` |

The release session recorded a successful download, size/hash verification and
`unzip -t`; its temporary download was then removed. The workflow ran the full suite,
stochastic qualification, report qualification and lender smoke before publishing.
These are historical release receipts, not tests rerun by this documentation change.
Revalidate the live asset against the digest before later redistribution or reliance
on artifact identity. Release metadata and issue state were rechecked on 2026-10-05.

## Authority and surviving HOLD

The owner explicitly authorized the public v15.6.0 lender-case artifact exception,
the corrective v15.6.1 release path and corresponding exact-artifact exception, and
the unsigned annotated tag exception. This is a coordinator transcription of session
authorization, not a new or general release permission. It applies only to those
artifacts/tags, not to a future version, changed artifact, or professional reliance.

**The broader Board/lender reliance HOLD remains active.**
[Issue #1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110) is OPEN.
Publication, green CI, engineering review and this handover do not establish
bankability, a programme RELEASED disposition, achieved grade, or Board/lender
reliance authority. No model/KPI change is made by this handover. For future finance
work, read the current canonical scenario, `tests/_canon.py`, responsiveness tests,
and applicable evidence rather than copying a historical KPI table.

Issue #1110 was inadvertently auto-closed by GitHub when the PR body put a closing
keyword before its reference inside a negative sentence. It was reopened on
2026-10-04 at 12:25:49 UTC and the body corrected. Never use a closing-keyword/issue
sequence even when negated. State positively that the issue remains OPEN.

## Cleanup snapshot and remaining work

The release session removed its obsolete remote `release/15.6.0` branch
(tip `1b8ff02968614692d2efb5f3aadeea69bc1c39b0`). The corrected 15.6.0 and 15.6.1
remote branches were already auto-deleted. Its local 15.6.1 branch, temporary venv,
verification download and temporary receipts were removed after delivery checks;
remote refs and worktrees were pruned. The release tags and public asset remain.
Historical commits/PRs retain the delivered work; the deleted temporary files are
not retained as a local recovery source.

At this handover's preflight there was one clean primary worktree on `main`, no open
PR, no pending changelog fragments (`changelog.d/README.md` only), and no active
release writer lease. The unrelated remote branch
`codex/track-project-codex-config` was preserved. This documentation task introduces
its own `docs/handover-2026-10-05` branch and worktree; its final delivery receipt must
confirm their retirement, not mistake the earlier snapshot for later cleanup proof.
Its changelog entry is compiled immediately so it adds no residual fragment.

No release work remains to replay. The next thread should bootstrap, report live
state, then await the owner's next bounded task. The platform-plan D3/D6/D7 decisions
and evidence requests in the predecessor remain questions to reconcile, not an
automatic instruction to implement a platform rebuild. The historical native merge
reservation was released by the owner on 2026-09-26 as recorded in `CLAUDE.md` and
issue #1255; do not restore it from H05–H08.

## Bootstrap for a new clean thread

1. Start in the `DutchBay_EPC_Model` project. Read `AGENTS.md` and `CLAUDE.md` from
   the actual checkout. Inspect ownership before any mutation:

   ```bash
   git rev-parse --show-toplevel
   git status --short --branch
   git worktree list
   git rev-parse HEAD HEAD^{tree}
   git rev-parse --is-shallow-repository
   ```

2. Select the governed runtime. On the owner's Mac, use the persistent Python 3.12
   environment, not a per-task replacement:

   ```bash
   export DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
   "$DUTCHBAY_VENV/bin/python" -VV
   ./check_venv.sh --no-bootstrap
   ```

   Run from `/Users/aruna/Downloads/dutchbay-epc-model` or its dedicated worktree,
   not the similarly named project folder. On an ephemeral cloud host only, with
   `DUTCHBAY_VENV` unset, use the permitted checkout-local fallback:

   ```bash
   CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/session-start.sh
   .venv/bin/python -VV
   ```

   Record that Mac-only context and private evidence were not verified from cloud.
   The full extras are the hook default; `DUTCHBAY_EXTRAS=dev` is appropriate only
   for a bounded task requiring tests/linters rather than feasibility capabilities.

3. Fetch `origin` and tags after ownership checks. If history is shallow, obtain full
   history (`git fetch --unshallow origin`) before the resolver or historical tests.
   Only fast-forward a clean, owned primary `main` to current `origin/main`.
   Preserve dirty, unfamiliar or concurrently owned state; never reset/stash/clean it.

4. With the selected governed interpreter (Mac shown below), run the resolver and
   read its first record. Stop if it fails; never guess the latest filename. Read the
   complete canonical CSV, its three unabridged FRAMEWORK rows, and applicable
   RECRUIT-01 modules, then validate:

   ```bash
   "$DUTCHBAY_VENV/bin/python" scripts/list_session_handover_records.py
   DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
     PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" dutchbay_bootstrap_rules.py
   ```

   In cloud, replace the interpreter with `.venv/bin/python`; do not assign a
   fictitious Mac path. The resolver requires matching committed/index/worktree
   handover inventories, so a new uncommitted handover intentionally makes it fail.
   Time it: `AGENTS.md` requires owner-led optimization/review before 60 seconds or
   100 records. The predecessor measured 50.3 seconds; that is historical, not a new
   benchmark or permission to ignore the threshold.

5. Reconcile current external state rather than trusting this snapshot:

   ```bash
   gh pr list --state open --limit 100
   gh issue view 1110 --json state,url
   gh release view v15.6.1 --json url,publishedAt,isDraft,isPrerelease,assets
   git rev-parse v15.6.1 v15.6.1^{commit}
   ```

   Run `scripts/compile_changelog.py --check` with the governed interpreter and
   inspect any later fragments; do not delete them without successful compilation.
   Do not retag, republish, lift the HOLD, or delete unrelated branches. For new work,
   start from current `origin/main` in a dedicated task worktree, issue a bounded
   writer lease, obtain risk-appropriate independent review, and use protected PR/CI
   delivery. This bootstrap transfers context, not an old writer lease.

## Assumptions and limitations

This is a cloud-authored continuity record, not a fresh audit of the entire project
or a replay of the release qualification. Private Mac evidence was not accessible.
Mutable GitHub state must be checked again at startup. HTTPS Git push previously
returned HTTP 401 while Git-data REST publication worked; inspect current credential
readiness without exposing secrets, and never bypass protected-main gates.

The documentation PR carries this handover's exact-object independent reviews,
verification commands/results, and final-head evidence. Release-session claims above
are distinguished from that new review. No predecessor pending review is presumed
accepted merely because this record exists.
