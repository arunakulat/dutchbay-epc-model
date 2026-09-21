# DutchBay EPC Model — repository brief

**Snapshot, not normative text.** Every figure below was measured on 2026-09-21 against `main`
at `322e5e4` and is dated for that reason: this file records what was observed, it does not
govern anything. `go_with_the_flow_rules_v3_0_clean.csv` and `AGENTS.md` remain the governance
sources, and where this file disagrees with either of them, this file is the stale one. Do not
cite a count from here as current — re-measure it with the command given beside it.

## What the project is

A lender and DFI-grade project-finance model for the Dutch Bay 150 MW onshore wind farm in
Sri Lanka (Kalpitiya), with optional BESS and hybrid solar. It computes a full cashflow
waterfall, sizes multi-tranche debt against DSCR covenants, applies the Sri Lanka tax regime,
runs Monte Carlo and global sensitivity analysis, and drives an ERA5 → Weibull → AEP → finance
pipeline. Outputs are CSV, Excel and JSON artifacts plus an HTML or PDF lender report.

`VERSION` reads `15.5.0`. The licence is proprietary with an explicit evaluation-and-audit
grant: you may read, run and publish criticism of the model, but not deploy or redistribute it.

## Layout

The canonical execution path is "v14". All CLIs are Hydra (`key=value`, never `--flags`).

| Area | What lives there |
| --- | --- |
| `analytics/` | Evaluation gateway (`evaluation_v14.py`), result contracts (`contracts_v14.py`), pipeline orchestration, Monte Carlo (`mc/`), sensitivity, CASPER risk blocks, FX, wind/GIS/grid bridges |
| `finance/` | Cashflow engine, debt and DSCR, tax, and the canonical IRR/NPV (`irr.py`) and WACC (`wacc_v14.py`) |
| `wind_resource/` | ERA5 → Weibull → PyWake bankable AEP (opt-in `[wind]`) |
| `solar_resource/` | pvlib solar producer (opt-in `[solar]`) |
| `app/`, `api/` | FastAPI service, arq/Redis async jobs, the lender report. `api/` is the legacy standalone surface kept for compatibility |
| `scenarios/`, `conf/`, `config/`, `inputs/` | Configuration and source inputs |
| `tests/` | Unit, contract, lint/architecture, integration and financial regression |
| `docs/` | Controlled research and due-diligence corpus |

Three traps in the layout, each of which has misled a reader before:

- Top-level `monte_carlo/` holds Monte Carlo scenario YAML, **not** engine code. The engine is
  `analytics/mc/`.
- There are two FastAPI surfaces: `app/api/` is current, `api/` is legacy.
- The durable project folder `Dutchbay_EPC_Model` (underscores) and the Git checkout
  `dutchbay-epc-model` (hyphens) are complementary under `ENV-01`, not alternatives.

## How it runs and is tested

```bash
export DUTCHBAY_VENV=/absolute/path/to/persistent/.venv
make setup                  # create or validate the Python 3.12 venv
source scripts/venv_up.sh   # activate and bind imports to this checkout

python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
```

Gates, all mirrored in CI:

```
make lint      # ruff (mandatory) + black/isort (advisory — the tree is style-drifted by design)
make type      # strict, complete-annotation mypy over the engine surface
make security  # bandit SAST + pip-audit of the pinned lock (the allowlist is currently EMPTY)
make test      # pytest -n auto with a 95% coverage floor
```

Dependencies are two-layer: `pyproject.toml` is the abstract source of truth, `requirements.txt`
is the fully pinned lock, regenerated only through `make lock`. Fourteen opt-in extras
(`dev`, `test`, `api`, `dashboard`, `wind`, `micrositing`, `solar`, `pareto`, `gis`,
`ingestion`, `report`, `jobs`, `grid`, `feasibility`), each import-guarded so a missing extra
fails at call time with an actionable message, never at import time.

CI workflows: `test-suite.yml` (sharded suite, plus a weekly schedule on Mondays 03:17 UTC as a
backstop), `ci_v14_fastlane.yml`, `regression-smoke.yml`, `pr-receipts.yml`, `fx-tests.yml`,
`docker-build.yml`, `release-run.yml`, `audit-cloud-sandbox.yml`.

Measurements on the snapshot commit, with the command that produced each:

| Measure | Value | Command |
| --- | --- | --- |
| Test files | 389 | `find tests -name 'test_*.py' \| wc -l` |
| Skip/xfail markers | 19 | `grep -rn 'pytest.mark.skip\|pytest.mark.xfail' tests/ --include=*.py \| wc -l` |
| TODO/FIXME in the engine | 5 | `grep -rn 'TODO\|FIXME' analytics finance app api wind_resource solar_resource scripts` |
| Pending changelog fragments | 152 | `ls changelog.d \| wc -l` |
| GWTF rules | 74, all active | `dutchbay_bootstrap_rules.py` |

Scheduled `test-suite` runs on `main` were green through 2026-09-14.

### This repository is already provisioned for Claude Code on the web

`.claude/settings.json` sets `DUTCHBAY_EXTRAS=dev,feasibility,jobs,solar,pareto` and registers
`.claude/hooks/session-start.sh`, which provisions a Python 3.12 venv, installs the pinned lock
plus those extras, and starts Redis. It is idempotent via a manifest hash and exits immediately
on local sessions. It worked unmodified in the session that wrote this file.

One gap worth knowing before you rely on the documented startup path: the remote container
clones shallow, and `scripts/list_session_handover_records.py` fails closed on a shallow history
("repository history is shallow; fetch complete history"). A web session must run
`git fetch --unshallow` before the `AGENTS.md` session-continuity entrypoint works at all.

## Conventions a contributor must follow

- **Governance is a file.** `go_with_the_flow_rules_v3_0_clean.csv` (GWTF v3.0) is canonical;
  `AGENTS.md` is the concise gateway. Named rules recur constantly in commit messages:
  `DELIVERY-01`, `VERIFY-01`, `TEST-01`, `MERGE-01`, `ENV-01`, `THREAD-01`, `RECRUIT-01`,
  `DATA-01`, `PERSIST-01`.
- **Dolphin Strategy** (`DELIVERY-01`): one small, complete, independently reversible change per
  branch and PR. Split broad initiatives into sequential green PRs. `main` is protected and work
  reaches it only through a PR.
- **Receipts, not claims** (`VERIFY-01`): the PR template carries a receipts table and
  `pr-receipts.yml` is a *required* check that fails a PR whose Result cells are blank. A check
  you did not run is declared as `not run — <reason>`, never left silent. The job reads the cells
  for presence, not truth, so a stale number passes it — green there means nothing was left
  silent, not that the figures are right.
- **Independent oracle** (`TEST-01`): finance-material code must answer to an oracle that did not
  originate in the same change. A change whose only evidence is tests written alongside it is
  unverified, however green.
- **Merge on green** (`MERGE-01`): merging a green PR is standing-authorized. Do not hold a
  finished PR waiting for a per-PR go-ahead, and do not ask whether to merge.
- **The ruleset serializes merges.** GitHub rejects a merge once the branch is behind `main`
  ("4 of 4 required status checks are expected"), so a batch cannot land together: update from
  `main`, push, wait for CI, merge, one at a time. Merges are squashes titled `subject (#NNNN)`.
- **Changelog fragments** go in `changelog.d/` as `<id>.<category>.md`, never as an edit to
  `CHANGELOG.md`. `VERSION` and the changelog move when committed financial behaviour changes.
- **Architecture guardrails**: config-first (no hidden constants), strict schema validation,
  evaluate only through `evaluate_with_overrides()`, IRR/NPV/WACC defined only in `finance/`,
  units in field names (`*_pct`, `*_usd`, `*_mw`), Hydra and JSON-first for new CLIs (`argparse`
  is banned), typed code with Google-style docstrings.
- **Session continuity** (`PERSIST-01`): each session writes a successor handover record under
  `docs/`, resolved by `scripts/list_session_handover_records.py`. Read the newest first and
  follow the chain back only as far as it tells you to.

## In flight on the snapshot date

**Open PRs — 9 including this brief's own, and five of them the dependabot queue at its cap.**

| PR | Opened | State |
| --- | --- | --- |
| #1271 types-openpyxl | 2026-09-16 | dependabot |
| #1255 make ANDES ride-through codegen serial | 2026-09-09 | owner's, ready, not merged |
| #1251 pyproj 3.8.0 | 2026-09-09 | dependabot |
| #1249 numerics group | 2026-09-09 | dependabot |
| #1241 NSO Addendum 01 citation | 2026-09-06 | draft |
| #1231 sub-annual cashflow rows | 2026-09-04 | draft |
| #1221 click 8.5.0 | 2026-09-02 | dependabot |
| #1220 hypothesis 6.167.1 | 2026-09-02 | dependabot |

**Open issues — 22**, dominated by the P1 audit programme (#1110 and its children #1158–#1162,
all labelled `blocking`), plus #1229 (grid numba SIGSEGV, `bug`), #1270, #1265 and #1262
(governance and test defects opened 2026-09-13/14), and #1169 (numpy 2.5, blocked by
pandapower's `numpy<2.5` ceiling).

**How fast this section goes stale.** `main` took eleven commits between 2026-09-15 and
2026-09-21, three of them landing while this brief was being written. Two items this file
listed as open when it was drafted on 2026-09-20 were closed before it was committed:

- #1274 added the in-image HarfBuzz assertion (`scripts/check_image_harfbuzz_subset.py`) and
  the `docs/deploy/DEPLOY.md` runtime-library callout. Both gaps are shut.
- #1272 corrected the `python312-report-jobs` fragment that named WeasyPrint 69.0 against a
  70.0 lock.

What is genuinely still open from the 2026-09-14/15 batch is one decision: the `wind_resource`
call — spec new modules, or review the existing ones. #1280 rewrote `wind_resource/README.md`
against the built package, which moves the "review" side along; whether new modules are wanted
has not been answered.

Treat the tables above the way the header says: re-measure, do not cite.

## Recurring chores

Cadence and scope set by the project owner on 2026-09-20. These are standing maintenance, not
suggestions.

1. **Dependabot sweep — daily.** Dry-run install, check CI, then merge or close, so the queue
   keeps moving. It matters because `.github/dependabot.yml` sets
   `open-pull-requests-limit: 5` and exactly five dependabot PRs were open on the snapshot date,
   the oldest from 2026-09-02: at the cap, new proactive updates are silently not raised at all.
   The config's own instruction is "always `pip install --dry-run` a Dependabot PR before merge".
2. **Green-main check — weekly.** The scheduled `test-suite` run on Mondays 03:17 UTC is the
   backstop that catches dependency drift on an otherwise unchanged tree. Its result currently
   goes nowhere a person will see it, so the check is to read it and report it.
3. **Handover-record hygiene — followed, not optional.** Write a successor record before a
   session ends and correct a live one as soon as it states something false. `AGENTS.md` also
   requires the resolver to be optimized and reviewed before its runtime exceeds 60 seconds or
   the corpus reaches 100 records: on the snapshot date the resolver listed 5 records in the
   current family and `docs/` held 37 files with `HANDOVER` in the name.
4. **Stale drafts — updated, synced, merged, then pruned.** Draft PRs are not left to rot: bring
   each up to date with `main`, drive it green, merge it, and prune its branch and worktree
   afterwards. #1231 (opened 2026-09-04) and #1241 (2026-09-06) had not moved on the snapshot
   date.

## A companion repository

`tests/lint/test_nso_corpus_manifest_integrity.py` and
`docs/NSO_MANIFEST_PYCACHE_REPAIR_REVIEW_RECORD_2026-09-04.md` both reference a private
**`DutchBay_RAG`** corpus — the NSO BESS commercial offers, held by hash rather than by content.
It is a real structural dependency of the evidence corpus and belongs in scope for any session
doing corpus work, even though the 2026-09-14/15 work did not touch it.
