# DutchBay EPC Model — Codex Instructions

## Authority and scope

These instructions apply to the entire repository. User instructions and higher-priority
Codex policies take precedence. The canonical project governance source is
`go_with_the_flow_rules_v3_0_clean.csv`; this file is a concise Codex gateway, not a
replacement copy of the GWTF ruleset.

Before substantial work, load the rules relevant to the task and validate the canonical
CSV when governance or workflow is in scope:

```bash
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
```

When historical sprint instructions conflict with current governance, follow the newer
current workflow, especially `WORKTREE-01`, `GOV-02`, `R23`, `R25`, `DELIVERY-01`,
`DATA-01`, `PERSIST-01`, `THREAD-01`, and `MERGE-01`. Never restore a retired sprint integration
branch or a nonexistent ruleset filename.

## Session continuity

Before starting work, read the newest record in `docs/SESSION_HANDOVER_*.md` — currently
`docs/SESSION_HANDOVER_2026-08-29_3.md` — and execute its **Bootstrap — run this first**
section before substantive work. Each record names its predecessor and states which parts
of it still stand, so read the newest first and follow the chain back only as far as it
tells you to. These are the PERSIST-01 durable records: they carry the canonical KPI set,
the traps that have already cost a session real time, and the open-item list.

The handover bootstrap is an executable startup checklist, not an independent governance
source. Where a handover and this file disagree about environment or governance, this file
and the canonical CSV win, and the handover is stale.

Write a successor record before a session ends, and correct a live one as soon as it
states something false — a durable record that is confidently wrong is worse than a thin
one, because the next session acts on it.

## Required Codex task origin and Python runtime

- Create every new task, regardless of subject, from the Codex project named
  `DutchBay_EPC_Model`. Do not start any work as an unscoped task or from another Codex
  project.
- The durable project folder is `/Users/aruna/Downloads/Dutchbay_EPC_Model`; its persistent
  governed Python 3.12 environment is
  `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`.
- At task start, verify that project association and run
  `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV`. Invoke Python and other
  environment tools from that absolute `.venv/bin` path, or set `DUTCHBAY_VENV` to the
  persistent path and prepend its `bin` directory to `PATH`.
- Continue to run repository and Git operations from the active
  `/Users/aruna/Downloads/dutchbay-epc-model` checkout or its dedicated worktree. The Codex
  project association does not replace the repository-root requirement in `ENV-01`. Put the
  active checkout first on `PYTHONPATH`; a shared environment must never decide which
  worktree supplies DutchBay imports.
- Local Codex tasks must not create or select a per-task or temporary environment, a
  checkout-local replacement `.venv`, `.venv311`, bare/system Python, or another project's
  environment. The config-first portable `.venv` fallback is permitted only when
  `DUTCHBAY_VENV` is unset on an unconfigured developer host or an ephemeral CI/container
  host; it is not a substitute for the persistent local Codex environment.
- At startup run:

  ```bash
  DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh
  ```

  If project association or the persistent environment cannot be verified, stop before
  substantive work and repair the context or request user direction.

## Start every task safely

1. Run `git status --short --branch` and `git worktree list` before any mutation.
2. Confirm the active branch and worktree. Treat `main` and `master` as protected and
   read-only.
3. Inspect the relevant code, tests, configs, and recent history before editing.
4. Preserve unrelated and pre-existing user changes. Never reset, checkout, stash, or
   clean them away.
5. Resolve secrets through environment or hosting secret stores. Never print, record, or
   commit credentials.

## Git, isolation, and delivery

- Every concurrent or background writing session uses its own dedicated worktree and
  branch. Read-only inspection may use the shared checkout without changing it.
- Base new work on current `origin/main`. Verify the branch again before every commit.
- Follow the Dolphin Strategy: one small, complete, independently reversible change per
  branch and PR. Split broad initiatives into sequential green PRs.
- Never commit or push directly to a protected branch. Merge only through a PR after all
  required CI checks pass and the branch is current.
- Follow `MERGE-01`: merging a green PR is standing-authorized, so do not hold a finished PR
  waiting for a per-PR go-ahead and do not ask whether to merge. Green means every *required*
  check reports success on the exact current head with no failed, pending or unreported required
  check and no conflict; a skipped advisory job is neither a blocker nor a substitute. Red,
  unreported or conflicted means drive it back to green first. Merging on green is delivery
  authority only: it lifts no `HOLD` and confers no grade, release, audit, lender or Board
  authority.
- Do not use `git stash` for cross-branch peeking because the stash namespace is shared
  across worktrees.
- Stage only files belonging to the task. Commit, push and open PRs when the requested delivery
  workflow calls for it; merging is standing-authorized on green under `MERGE-01`.
- Checkpoint long-running results and coherent work to durable storage early. Do not
  leave load-bearing results only in chat context.

## Runtime logging and evidence retention

- Runtime diagnostics are ephemeral by default. Do not create durable per-trial,
  per-record, repeated `INFO`, or other high-volume runtime log files unless the user
  explicitly requests retention or a controlling requirement makes it necessary.
- For long-running calculations, suppress routine `INFO` output. Keep concise start,
  completion, and essential warning/error messages as transient process output.
- If failure triage genuinely requires a temporary log capture, give it a narrow,
  explicit path and delete that named capture at the earliest safe opportunity after
  extracting the minimum structured validation facts.
- Durable validation controls should retain only the minimum useful structured facts,
  such as status, warning category/count, timestamps, hashes, and limitations. Do not
  retain raw or repeated runtime log text.
- Governed results, source/raw evidence, model inputs and outputs, manifests, hashes,
  run specifications, and concise validation records are evidence artifacts rather than
  runtime logs; preserve them under the applicable evidence-retention controls.

## Architecture and implementation guardrails

- Keep financial and scenario behavior config-first. Business values and pipeline modes
  belong in YAML or JSON configuration, never hidden constants or switches.
- Use strict v14 schema validation and fail loudly with precise, actionable errors. Do
  not weaken validation with `strict=False` for convenience.
- Use `analytics.contracts_v14` for canonical result contracts and
  `analytics.evaluation_v14.evaluate_with_overrides()` as the evaluation gateway. Do not
  import evaluation internals directly.
- Define IRR, XIRR, and NPV only in `finance/irr.py`; consumers import those functions.
- Keep optional dependencies import-safe and raise actionable errors at call time.
- New canonical CLIs use Hydra and emit JSON-first output. `argparse` is banned; do not
  extend frozen Typer or Click tooling.
- New Python code is typed and uses concise Google-style docstrings for public modules,
  classes, and functions.
- Preserve units in field names and contracts (`*_pct`, `*_years`, `*_usd`, `*_lkr`,
  `*_mw`, and similar). Never silently mix percentage or currency scales.

## Financial-model changes

- Changes that can alter IRR, DSCR, NPV, covenants, debt sizing, tax, tariff, FX, AEP, or
  other lender outputs require focused regression tests and explicit impact disclosure.
- Update `VERSION` and `CHANGELOG.md` when the change affects committed financial
  behavior, following the repository release policy.
- Do not compare newly assessed locations, turbines, tariffs, or FX cases against a
  frozen reference that is no longer the applicable basis. Reconciliation guards must
  compare like-for-like cases and expose provenance.
- Stochastic analysis must accept or record an explicit seed so results are reproducible.
- Follow `TEST-01`'s independent-oracle clause. A pinned value proves only that a number
  has not changed, never that it is still being derived, so a pinned-constant oracle is
  paired with a responsiveness guard. Finance-material code must answer to an oracle that
  did not originate in the same change — a pre-existing test, an external benchmark, a
  closed-form check, an independent implementation, or a property/invariant. A change whose
  only evidence is tests written alongside it is unverified, however green.

## Source ingestion and documentation

- Follow `DATA-01`: capture every source datum, table cell, term, caveat, precision, and
  source location. Preserve raw values alongside interpretation; mark uncertainty rather
  than dropping it.
- Convert PDFs with the repository's local MarkItDown workflow before interpreting them.
  Do not infer claims from raw PDF bytes.
- Keep documentation professional, source-grounded, assumption-explicit, and candid
  about limitations. Avoid marketing language and unsupported claims.
- Do not publish confidential or third-party materials without explicit authorization.
  Retain original provenance and confidentiality markings when publication is authorized.

## Presentation layer and PDF generation

- Follow `DBPL-01`. **DBPL / dbpl / DutchBay Presentation Layer names a print contract, not a
  look.** Any PDF described as a DBPL document MUST be generated through
  `app.reports.dbpl.print_core.render_dbpl_pdf`, which requires the **complete** `[report]`
  optional extra — `weasyprint`, `reportlab`, `geopandas` **and** `contextily` — plus the DBPL
  font stack. Never call WeasyPrint directly for a DBPL document.
- The print core **fails loud** rather than degrading: an incomplete, mis-pinned or
  installed-but-unimportable stack raises `DbplDependencyError`. This is a deliberate exception to
  the CASPER degradation default, because for a DBPL PDF the PDF *is* the deliverable. Use
  `app.reports.renderer` for a best-effort render, and do not call that result DBPL.
- Design tokens live only in `app/reports/dbpl/style.py` and are emitted into the stylesheet.
  A surface that hard-codes its own colours, sizes or margins has forked the house style.
- The structural furniture — running header banner, running footer with document ID/version/date
  and `Page n of m`, and a caveat band under every section heading — is **un-suppressible**.
- Surface font provenance. WeasyPrint renders successfully with a substituted face, so a
  successful render proves nothing about which font was used; record substitutions, never hide
  them.
- Full guide: `docs/dbpl_styleguide.md`.

## Verification

Run the narrowest meaningful checks while iterating, then broaden in proportion to risk.
Preferred focused commands are:

```bash
PYTHONDONTWRITEBYTECODE=1 \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
  -p no:cacheprovider <test-paths> -q
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff check <changed-python-paths>
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff format --check <changed-python-paths>
git diff --check
```

For shell changes, run `bash -n` and, when the script supports zsh, `zsh -n`. For broad or
financially material changes, run the relevant integration/regression suite and the full
repository gates when practical. GitHub required checks remain the merge authority.

Changes to shared-environment governance must also run
`scripts/verify_shared_venv_worktrees.py` with two distinct, clean worktrees and the one
configured `DUTCHBAY_VENV`; retain its concise receipt, not raw test or runtime logs.

A pull request whose acceptance criteria depend on QSTS execution must independently run
and pass the GitHub-hosted `Grid Study` job against the exact pull-request head SHA before
merge. The governed persistent local environment remains the iteration surface, but its
local evidence is supplementary and cannot replace this independent check. A skipped Grid
Study is acceptable only when the fail-closed changed-path policy classifies the pull
request as unrelated to the governed QSTS/grid execution surface.

## Repository map

- `analytics/`: canonical evaluation, contracts, sensitivity, Monte Carlo, wind, and FX
  analytics.
- `finance/`: cash flow, debt, tax, WACC, equity, and the canonical IRR/NPV implementation.
- `app/` and `api/`: asynchronous jobs and web/API presentation surfaces; no duplicated
  finance mathematics.
- `conf/`, `config/`, `scenarios/`, and `inputs/`: configuration and source inputs.
- `tests/`: unit, contract, lint, integration, and financial regression coverage.
- `docs/`: controlled research and due-diligence corpus; generated runtime artifacts go
  under `outputs/`.

## Handoff

Report the outcome first, then list material files changed and exact checks run. State
clearly whether work is uncommitted, committed, pushed, opened as a PR, or merged. After a
successful merge, synchronize `main` and remove obsolete task branches/worktrees only when
it is safe to do so.
