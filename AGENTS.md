# DutchBay EPC Model — Codex Instructions

## Authority and scope

These instructions apply to the entire repository. User instructions and higher-priority
Codex policies take precedence. The canonical project governance source is
`go_with_the_flow_rules_v3_0_clean.csv`; this file is a concise Codex gateway, not a
replacement copy of the GWTF ruleset.

Before substantial work, load the rules relevant to the task and validate the canonical
CSV when governance or workflow is in scope:

```bash
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python \
  dutchbay_bootstrap_rules.py
```

When historical sprint instructions conflict with current governance, follow the newer
current workflow, especially `WORKTREE-01`, `GOV-02`, `R23`, `R25`, `DELIVERY-01`,
`DATA-01`, `PERSIST-01`, and `THREAD-01`. Never restore a retired sprint integration branch or a
nonexistent ruleset filename.

## Required Codex task origin and Python runtime

- Create every new task, regardless of subject, from the Codex project named
  `DutchBay_EPC_Model`. Do not start any work as an unscoped task or from another Codex
  project.
- The durable project folder is `/Users/aruna/Downloads/Dutchbay_EPC_Model`; its persistent
  governed Python 3.12 environment is
  `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`.
- At task start, verify that project association and run
  `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV`. Invoke Python and other
  environment tools from that absolute `.venv/bin` path, or prepend it to `PATH`.
- Continue to run repository and Git operations from the active
  `/Users/aruna/Downloads/dutchbay-epc-model` checkout or its dedicated worktree. The Codex
  project association does not replace the repository-root requirement in `ENV-01`.
- Do not create or select a per-task or temporary environment, a checkout-local replacement
  `.venv`, `.venv311`, bare/system Python, or another project's environment. If the project
  association or persistent venv is unavailable or not Python 3.12, stop before substantive
  work and repair the context or request user direction.

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
- Do not use `git stash` for cross-branch peeking because the stash namespace is shared
  across worktrees.
- Stage only files belonging to the task. Commit, push, and open or merge PRs only when
  authorized by the user or clearly required by the requested delivery workflow.
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
