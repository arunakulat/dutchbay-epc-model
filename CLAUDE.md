# DutchBay EPC Model — Claude Code entry point

Claude Code loads this file automatically. It adds no governance of its own. The authority is
the canonical ruleset `go_with_the_flow_rules_v3_0_clean.csv`, and `AGENTS.md` is the
repository's gateway to it. Read `AGENTS.md` before substantial work. Where this file disagrees
with either of them, this file is stale: correct it rather than follow it.

## What changes in a cloud session

`AGENTS.md` is written for local Codex tasks on the owner's Mac. In a Claude Code cloud session:

- **Python environment.** `THREAD-01` and `ENV-01` bind *local* threads to the persistent
  runtime at `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, which does not exist in a
  container. Both rules permit the checkout-local `.venv` as the portable fallback on "an
  ephemeral CI/container host", and that is the case here. `.claude/hooks/session-start.sh`
  provisions it: Python 3.12, the pinned lock and the full extras set. The hook is registered
  in this checkout's `.claude/settings.json`, so a session that starts in a parent directory
  (a multi-repository session, for example) never runs it. If `.venv/` is missing, run it
  yourself from the repository root and allow several minutes. Prefix `DUTCHBAY_EXTRAS=dev`
  for a faster tests-and-linters-only environment.

  ```bash
  CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/session-start.sh
  .venv/bin/python -VV   # must report Python 3.12
  ```

- **Codex-only steps do not apply.** The Codex project association and the
  `check_venv.sh` run against the Mac path cannot be verified in a container. Their absence
  is not a reason to stop. Record the container environment in your receipts instead.
- **Native reservation.** The `MERGE_CAPACITY_NATIVE_RESERVATION.json` protocol in the H05–H08
  handovers was released by the project owner on 2026-09-26, recorded on #1255. It does not
  gate merges.
- **Evidence on the owner's Mac.** Handovers and review records cite files under
  `/Users/aruna/Downloads/...`. A container cannot read them. Say so rather than infer their
  contents.

Everything else in `AGENTS.md` applies unchanged: the start-of-task checks, Dolphin-sized
pull requests (`DELIVERY-01`), no direct commits to `main` (`GOV-02`), receipts (`VERIFY-01`),
and the financial-model and corpus-commit rules.

## Rules and formats that govern this repository

A single ruleset governs both this repository and `DutchBay_RAG`: the Go-with-the-Flow (GWTF)
CSV, `go_with_the_flow_rules_v3_0_clean.csv`. It is held only here. `DutchBay_RAG`'s lint
fetches it from this repository at a pinned commit rather than keeping a copy. Load it at
the start of substantial work:

```bash
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" \
  .venv/bin/python dutchbay_bootstrap_rules.py
```

- **The framework principles are rules.** CASPER, CESSPIT and CCCDIR are the CSV rows
  `FRAMEWORK-01`, `FRAMEWORK-02` and `FRAMEWORK-03`. They are peers, not parts of one another,
  and each carries a primary and a secondary meaning. Read them in the CSV and cite them by
  rule ID. Any spelled-out expansion that is not in the CSV fails
  `tests/lint/test_framework_expansions_match_csv.py`, because invented expansions have
  reached this repository before (#1283, #1286).
- **Formats the repository checks or relies on:**
  - *Receipts* (`VERIFY-01`): the table in `.github/pull_request_template.md`, checked by
    `scripts/ci/check_pr_receipts.py`.
  - *Commits*: `R18`.
  - *Changelog*: one fragment per change, named `changelog.d/<id>.<category>.md`
    (`scripts/compile_changelog.py`). Changes to committed financial behaviour also need
    `VERSION` and `CHANGELOG.md` (`RELEASING.md`).
  - *Handover records* (`PERSIST-01`): `docs/SESSION_HANDOVER_*` and `docs/H<n>_*`, ordered by
    `scripts/list_session_handover_records.py`.
  - *Review, lease and delegation records* (`RECRUIT-01`): the four modules in
    `docs/governance/recruit_01/`.
  - *Evidence corpus* (`DATA-01`): `MANIFEST.sha256` files and handling notes under
    `docs/source_materials/`. See `AGENTS.md` "Four ways a corpus commit goes wrong".
  - *PDFs* (`DBPL-01`): `docs/dbpl_styleguide.md`.

## Full history and tags

Cloud clones are usually shallow and carry no tags. The handover resolver refuses shallow
history, and `tests/lint/test_audit_findings_current_state_overlay.py` needs the release
tags. Fetch both before relying on either:

```bash
git fetch --unshallow --tags origin main
python scripts/list_session_handover_records.py
```

Then follow `AGENTS.md` "Session continuity". Under `PERSIST-01`, write a successor record
before a session ends if it changed load-bearing state.

## Pull requests

Watching, fixing or merging a pull request follows `.claude/skills/steward/SKILL.md`.

## Known local-only failures

In cloud containers, five tests in `tests/lint/test_cloud_audit_review_sandbox.py` (the
sandbox watchdog and process-reaping cases) fail identically on an unmodified `main` and pass
in CI (recorded on #1289 and #1292). Declare them in your receipts as pre-existing and local;
do not skip them, and do not treat them as caused by your change.
