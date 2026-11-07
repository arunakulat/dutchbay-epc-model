# Rules to Follow — Unified Governance, Frameworks & Multi-Agent Reference

> **Authority & Non-Forking Notice (`GOV-01`, `RECRUIT-01`)**
> The single canonical source of truth for project governance is [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv). This document is a unified index and summary across all governance modules, architectural frameworks, and AI agent hosts (Claude, OpenAI Codex, Google Antigravity / Gemini, Kimi, Perplexity, GitHub Copilot, and CI bots). Where any summary disagrees with [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv), the CSV wins.
> This document grants no merge, review, lease, release, grade, lender, or Board authority to any session.

---

## 1. Mandatory Session Bootstrap (Run First in Every Session)

Before editing any file, opening a PR, or claiming verification, every agent or developer session must execute the environment and ruleset bootstrap:

```bash
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
"$DUTCHBAY_VENV/bin/python" -VV
DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
"$DUTCHBAY_VENV/bin/python" scripts/list_session_handover_records.py
git status --short --branch
git worktree list
```

### Core Primary Sources (Click to Open)

| Document | Scope & Authority |
|---|---|
| [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv) | **Canonical GWTF v3.0 Ruleset** (79 active rules across 19 categories; validated by [`dutchbay_bootstrap_rules.py`](dutchbay_bootstrap_rules.py) and [`tests/lint/test_gwtf_canonical_source.py`](tests/lint/test_gwtf_canonical_source.py)). |
| [`AGENTS.md`](AGENTS.md) | **Codex & Universal Agent Gateway** — runtime requirements (`ENV-01`, `THREAD-01`), intake (`INTAKE-01`), delivery (`DELIVERY-01`, `REVIEW-01`, `TRAIN-01`, `MERGE-01`, `CLEANUP-01`), corpus manifest rules (`DATA-01`), and `DBPL-01`. Guarded by [`tests/lint/test_codex_project_guidance.py`](tests/lint/test_codex_project_guidance.py). |
| [`CLAUDE.md`](CLAUDE.md) | **Claude Code Gateway** — build/lint/test commands, architecture map, config-first rules, and pointer to [`AGENTS.md`](AGENTS.md). |
| [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md) | **Multi-Agent Session Router** — routes any non-Codex or cloud session to its governing documents. Guarded by [`tests/lint/test_agent_session_routing.py`](tests/lint/test_agent_session_routing.py). |
| [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md) | **Steward Skill** — PR driving, base-currency maintenance, `Evidence pack` formatting, Grid Study classification, `MERGE-01` boundary checks, and `TRAIN-01` merge-train execution. |
| [`docs/governance/recruit_01/01_capability_and_risk.md`](docs/governance/recruit_01/01_capability_and_risk.md) | **`RECRUIT-01` Module 1** — Capability classes (`C1`–`C7`), semantic risk classes (`R0`–`R3`), and §3.1 bounded low-risk classes (`REVIEW-01`). |
| [`docs/governance/recruit_01/02_writer_lease_and_recovery.md`](docs/governance/recruit_01/02_writer_lease_and_recovery.md) | **`RECRUIT-01` Module 2** — One-active-writer lease state machine, interruption revocation, and dead-worker takeover. |
| [`docs/governance/recruit_01/03_independent_review_and_attestation.md`](docs/governance/recruit_01/03_independent_review_and_attestation.md) | **`RECRUIT-01` Module 3** — Read-only exact-object review (`subject_head_sha`, `subject_tree_sha`, `base_sha`), §7 base fast-forward proofs, and §8 `TRAIN-01` merge-train carry-forward. |
| [`docs/governance/recruit_01/04_staged_delegation_and_ingress.md`](docs/governance/recruit_01/04_staged_delegation_and_ingress.md) | **`RECRUIT-01` Module 4** — Capacity admission, 5-tier worker ingress order, and outcome classification (`EVIDENCE_RETURNED`, `NO_FINDING_WITH_EVIDENCE`, `NO_EVIDENCE`, `BLOCKED_WITH_RECEIPT`). |
| [`.github/SPRINT_WORKFLOW_CHECKLIST.md`](.github/SPRINT_WORKFLOW_CHECKLIST.md) | **Sprint Workflow Checklist** — pre-sprint, implementation, review, and pre-merge compliance checklist derived from the CSV. |
| [`docs/AGENTIC_DELIVERY_PRACTICE.md`](docs/AGENTIC_DELIVERY_PRACTICE.md) | **Agentic Delivery Practice** — empirical practitioner evidence, anti-gaming controls ([`tests/finance/test_canon_vector_is_computed.py`](tests/finance/test_canon_vector_is_computed.py)), verification capacity principle, and explicitly rejected agent patterns. |

---

## 2. Canonical Framework Acronyms (`FRAMEWORK-01` – `FRAMEWORK-03`)

`CASPER`, `CESSPIT`, and `CCCDIR` are **three peer rules** in [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv) (Category: `Framework Principles`), guarded across all tracked files by [`tests/lint/test_framework_expansions_match_csv.py`](tests/lint/test_framework_expansions_match_csv.py). Never use retired or invented expansions.

### `FRAMEWORK-01`: CASPER
- **Primary Definition**: **CASPER** — *Clear API Surfaces with Predictable Error Responses*.
  - Modules expose clean, documented interfaces with explicit error types (`ValueError`, `TypeError`, `RuntimeError`).
  - Optional dependencies (`openpyxl`, `pandas`, `matplotlib`, `scipy`, `pyyaml`, `salib`, `rasterio`, etc.) must be import-safe and fail gracefully at call time via `_require_*()` guards, never at import time.
- **Secondary Definition**: *Contract-Assured Scenario Pipeline for Energy & Renewables*.
- **Monte Carlo Integration** ([`docs/CASPER_MC_INTEGRATION.md`](docs/CASPER_MC_INTEGRATION.md)):
  - [`analytics/casper/casper_payload.py`](analytics/casper/casper_payload.py) (`build_casper_payload()`) auto-wires top-level `mc_risk` (`{"lender_risk_table": [...], "covenant": {...}}`) into `casper_result_v1` payloads via `build_casper_risk_blocks()` and `CovenantSpec`, resolving `dscr_floor` config-first via [`analytics/mc/covenant.py`](analytics/mc/covenant.py) (`resolve_min_dscr_covenant`).

### `FRAMEWORK-02`: CESSPIT
- **Primary Definition**: **CESSPIT** — *Config Explicit, Schema Strict, Pre-flight Integrity Tests*.
  - All scenario parameters live in `YAML`/`JSON` configs; no hardcoded business constants or silent defaults for FX, tax, or debt terms.
  - [`analytics/schema_guard.py`](analytics/schema_guard.py) (`validate_config_for_v14(cfg, strict=True)`) is the strict-by-default pre-flight gatekeeper. Never weaken validation with `strict=False` in production code.
- **Secondary Definition**: *Config-Enforced Schema Safety Pipeline Integration Triad*.

### `FRAMEWORK-03`: CCCDIR
- **Primary Definition**: **CCCDIR** — *Contracts Centralized, Compliance Documented, Import Relationships explicit*.
  - All canonical result types (`ScenarioResult`, `SensitivityResult`, `MonteCarloResult`, `CasperPayload`) live in [`analytics/contracts_v14.py`](analytics/contracts_v14.py).
  - Analytics and presentation consumers invoke evaluation exclusively through [`analytics/evaluation_v14.py`](analytics/evaluation_v14.py) (`evaluate_with_overrides()`). Direct imports of internal evaluation state or `finance/` pipeline internals are banned ([`tests/lint/test_contracts_gateway_imports.py`](tests/lint/test_contracts_gateway_imports.py), [`tests/lint/test_no_direct_finance_pipeline_imports.py`](tests/lint/test_no_direct_finance_pipeline_imports.py)).
- **Secondary Definition**: *Config-Centric Contract-Driven Integration Rules*.

---

## 3. Complete GWTF v3.0 Ruleset Summary (All 79 Active Rules by Category)

### 3.1 Governance & Intake (`GOV-01`, `GOV-02`, `INTAKE-01`)
- **`GOV-01` (AI-Assisted Development Governance)**: AI agents are bound to the same engineering, verification, and provenance standards as human contributors. Human project owner retains all release, grade, audit, lender, and Board reliance authority.
- **`GOV-02` (Branch Protection & Commit Safety)**: `main` and `master` are strictly read-only. Verify `git branch --show-current` before **every** commit. Never commit or push directly to a protected branch.
- **`INTAKE-01` (Tracker-First Intake & Open-PR Sweep)**: Before editing any file or opening a PR:
  1. Fetch and verify `origin/main`.
  2. Read the live capability tracker ([Issue #1353](https://github.com/arunakulat/dutchbay-epc-model/issues/1353)) and enumerate every open PR.
  3. Advance an actionable overlapping PR first; record a blocked or owner-deferred PR with its revisit trigger.
  4. Record a scoped work item on `#1353` (with named deliverable and done-when criterion) or a focused issue **before** opening the PR, and cite the work-item link, base SHA, and overlap disposition in the PR body. Enforced by [`scripts/ci/check_pr_intake.py`](scripts/ci/check_pr_intake.py) and [`tests/lint/test_pr_intake_policy.py`](tests/lint/test_pr_intake_policy.py).

### 3.2 Architecture (`ARCH-01` – `ARCH-04`)
- **`ARCH-01` (Config-First Design)**: Business values, tariffs, FX curves, debt terms, and pipeline modes belong in `scenarios/*.yaml` or `conf/*.yaml`, never hardcoded in Python.
- **`ARCH-02` (Single IRR / NPV / XIRR Source)**: Define `irr`, `npv`, and `xirr` only in [`finance/irr.py`](finance/irr.py). Enforced by [`tests/lint/test_irr_location_v14.py`](tests/lint/test_irr_location_v14.py).
- **`ARCH-03` (Tranche-Aware Debt Result Surface)**: Debt sizing and schedule results expose explicit tranche-level and aggregate metrics cleanly without conflating senior, subordinated, or DFI tranches.
- **`ARCH-04` (Contract Gateway Pattern for Analytics Evaluation)**: Use [`analytics/contracts_v14.py`](analytics/contracts_v14.py) and `analytics.evaluation_v14.evaluate_with_overrides()` as the sole evaluation gateway, and keep optional dependencies import-safe behind call-time `_require_*()` helpers (`CASPER` / `FRAMEWORK-01`).

### 3.3 CLI & Tooling (`CLI-01` – `CLI-03`, `R1` – `R9`, `ADD-01` – `ADD-03`, `R26`)
- **`CLI-01` / `R1` (Hydra Standard)**: All canonical CLIs (`run_*_v14.py`, `scripts/run_*_v14.py`) use `@hydra.main(version_base="1.3", config_path=..., config_name=...)`. Enforced by [`tests/lint/test_entrypoints_hydra_only.py`](tests/lint/test_entrypoints_hydra_only.py).
- **`CLI-02` / `R2` (JSON-First Output)**: CLIs emit structured JSON on stdout (`logging.disable(logging.WARNING)` when emitting pure JSON stdout).
- **`CLI-03` / `R3` (No `argparse` / Frozen Legacy CLIs)**: `argparse` is banned repo-wide ([`tests/lint/test_no_argparse_anywhere.py`](tests/lint/test_no_argparse_anywhere.py)); legacy Typer/Click scripts are frozen ([`tests/lint/test_no_typer_v14.py`](tests/lint/test_no_typer_v14.py)).
- **`R4` – `R9` & `ADD-01` – `ADD-03`**: Structured config composition via OmegaConf `DictConfig`, pre-flight `validate_config_for_v14`, deterministic CLI exit codes, and reproducible JSON/CSV export artifacts.
- **`R26` (MarkItDown-First PDF Ingestion)**: Convert PDFs using the governed Python 3.12 MarkItDown toolchain (`"$DUTCHBAY_VENV/bin/python" -m markitdown` or `pdfplumber`/`PyMuPDF`) before interpreting them. Never infer claims from raw PDF bytes.

### 3.4 Validation, LibCST & Typing (`VAL-01`, `VAL-02`, `CST-01`, `TYPE-01`)
- **`VAL-01` & `VAL-02`**: Strict v14 schema validation and explicit unit suffixes in field and contract names (`*_pct`, `*_years`, `*_usd`, `*_lkr`, `*_mw`, `*_mwh`). Never silently mix percentage (`0.15` vs `15.0`) or currency (`USD` vs `LKR`) scales.
- **`CST-01`**: LibCST structural AST guardrails in `tests/lint/` enforce import boundaries, ban hardcoded FX/discount/grid constants, and block `argparse`.
- **`TYPE-01`**: Full type annotations on all public modules, classes, and functions, verified by `mypy` (`mypy.ini`) and Google-style docstrings ([`tests/lint/test_docstring_coverage.py`](tests/lint/test_docstring_coverage.py)).

### 3.5 Testing, Verification & Oracles (`TEST-01` – `TEST-05`, `VERIFY-01`)
- **`TEST-01` (Regression Pins & Independent Oracle Clause)**:
  - Finance-material code must answer to an **independent oracle** that did not originate in the same change (pre-existing test, external benchmark, closed-form check, independent implementation, or property/invariant test).
  - A pinned constant proves only that a number did not move, not that it is still computed; pair pinned constants with a **responsiveness guard** (e.g., [`tests/finance/test_canon_vector_is_computed.py`](tests/finance/test_canon_vector_is_computed.py)).
- **`TEST-02` – `TEST-04`**: Unit, contract, integration, and stochastic test separation; ordinary test runs do not establish Monte Carlo convergence, tail adequacy, or bankability ([`tests/lint/test_stochastic_suite_policy.py`](tests/lint/test_stochastic_suite_policy.py)).
- **`TEST-05` (Coverage Gate & Independent Grid Study)**:
  - Enforces the repository coverage floor ([`tests/lint/test_coverage_gate_policy.py`](tests/lint/test_coverage_gate_policy.py)).
  - Any PR touching governed QSTS/grid execution paths must independently run and pass the GitHub-hosted `Grid Study` job on the exact PR head SHA ([`tests/lint/test_grid_ci_policy.py`](tests/lint/test_grid_ci_policy.py)).
- **`VERIFY-01` ("A Claimed Check Without a Receipt Is Not a Check")**:
  - Every PR must carry an explicit verification receipts table (`.github/pull_request_template.md`) with exact commands and outcomes, or an explicit `not run — <reason>` / `required-not-run` declaration. Enforced by required CI check `Verification receipts (VERIFY-01)` ([`scripts/ci/check_pr_receipts.py`](scripts/ci/check_pr_receipts.py), [`.github/workflows/pr-receipts.yml`](.github/workflows/pr-receipts.yml), [`tests/lint/test_pr_receipts_policy.py`](tests/lint/test_pr_receipts_policy.py)).
  - Every new lint/policy guard must include a **negative control** that mutates the input and watches the guard fail.

### 3.6 Finance, Model Risk Management & Presentation (`FIN-01`, `FIN-02`, `MRM-01`, `MRM-02`, `DOC-01`, `DOC-02`, `DBPL-01`)
- **`FIN-01` & `FIN-02`**: Explicit impact disclosure for any change affecting IRR, DSCR, NPV, covenants, debt sizing, tax, tariff, FX, or AEP; like-for-like scenario comparisons only; bump [`VERSION`](VERSION) and update [`CHANGELOG.md`](CHANGELOG.md) (via `changelog.d/`) when committed financial behavior changes.
- **`MRM-01` & `MRM-02`**: Stochastic simulations require an explicit `seed`; governed output artifacts must record `schema`, `model_version`, config hash, and provenance.
- **`DOC-01` & `DOC-02`**: Keep documentation candid, source-grounded, and assumption-explicit; archive superseded sprint notes rather than leaving conflicting instructions live.
- **`DBPL-01` (DutchBay Presentation Layer)**:
  - Any PDF described as a DBPL document must be rendered through [`app/reports/dbpl/print_core.py`](app/reports/dbpl/print_core.py) (`render_dbpl_pdf`), requiring the complete `[report]` extra (`weasyprint`, `reportlab`, `geopandas`, `contextily`) and failing loud with `DbplDependencyError` if any dependency or font is missing.
  - Design tokens live only in [`app/reports/dbpl/style.py`](app/reports/dbpl/style.py). Running header, running footer (`Page n of m`), and section caveat bands are un-suppressible, and font substitutions must be surfaced ([`docs/dbpl_styleguide.md`](docs/dbpl_styleguide.md)).

### 3.7 Git Workflow, Delivery & Refactoring (`R10` – `R25`, `DELIVERY-01`, `REFACTOR-01` – `REFACTOR-04`, `WORKTREE-01`, `MERGE-01`, `REVIEW-01`, `TRAIN-01`, `CLEANUP-01`)
- **`R10` – `R17` & `R19` – `R25`**: Pre-commit hooks enabled (never use `--no-verify`), ruff/black/isort formatting clean, legacy code isolated under `legacy/` ([`tests/lint/test_no_legacy_imports.py`](tests/lint/test_no_legacy_imports.py)), branch-PR-CI-merge workflow against `origin/main`.
- **`R18` (Conventional Commits)**: Commit subjects must use `type(scope): summary` from the 11 sanctioned types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert` (`deploy` is unsanctioned). Guarded by [`tests/lint/test_commit_message_conformance.py`](tests/lint/test_commit_message_conformance.py).
- **`R21` (Graduated Verification Cadence)**: Run the narrowest meaningful check before each commit while iterating, and run the full relevant suite before pushing.
- **`DELIVERY-01` ("Dolphins, Not Whales") & `REFACTOR-01` – `REFACTOR-04`**:
  - Ship work as small, complete, independently reversible PRs ("dolphins"), never monolithic "whale" mega-PRs.
  - Incremental refactoring follows `MOVE → SHIM → UPDATE → DEPRECATE` one module at a time with zero breakage.
- **`WORKTREE-01` (Dedicated Worktree Isolation)**: Every concurrent or background writing agent must use its own dedicated `git worktree` and branch. Never use `git stash` for cross-branch peeking.
- **`REVIEW-01` (Review Before Full Suite)**:
  1. Open PR as a **draft** (`test-suite.yml` runs fast gates only and reports `Test Summary (draft: full suite deferred)`).
  2. Freeze the draft HEAD and post one `Evidence pack` comment.
  3. Bind independent review lanes to that exact draft HEAD (`R1` including Module 1 §3.1's 3 bounded classes = 1 lane; `R2`/`R3` = 2 lanes: Domain + Assurance).
  4. Mark the PR **ready for review** so the full sharded suite runs once. Any subsequent change to the PR's files restarts all reviews (Module 3 §6). Enforced by [`tests/lint/test_review_first_policy.py`](tests/lint/test_review_first_policy.py).
- **`TRAIN-01` (Merge Trains)**:
  - The merge coordinator (who is not the writer of any car) may combine 2 or 3 reviewed draft PRs ("cars") that are path-disjoint, unstacked, and bidirectionally import-isolated (with at most one `R3`/KPI-changing car) onto a branch `train/<date>-<n>` starting at `origin/main` (one non-merge commit per car).
  - Review bindings carry forward onto the train head only via `RECRUIT-01` Module 3 §8's three proofs (blob-hash identity, bidirectional import isolation, complete reviewed-to-updated diff).
  - The train runs the full suite once and lands via **rebase-merge** (never squash), verified before and after landing by the fail-closed shell blocks in [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md) and [`tests/lint/test_train_policy.py`](tests/lint/test_train_policy.py).
- **`MERGE-01` (Standing Merge-on-Green Authority & Boundaries)**:
  - Standing authorization to merge a PR as soon as every required check reports success on the exact current HEAD (`Test Summary`, `Code Quality Checks`, `Security Scan`, `Verification receipts (VERIFY-01)`, and conditional `Coverage Gate` / `Grid Study`) with no conflict and up-to-date base.
  - **Boundary**: Merging is delivery authority only; it lifts no `HOLD` (such as `#1110`), and confers no grade, release, audit, lender, or Board authority. *(Note: When the project owner places a temporary session hold on `MERGE-01`, honour that hold until explicitly lifted.)*
- **`CLEANUP-01` (Post-Merge Tracker Notification, Issue Closure & Worktree/Branch/Venv Retirement)**:
  - Immediately after any PR or `TRAIN-01` merge train lands on `origin/main` and protected-main ancestry/tree verification succeeds:
    1. **Inform Tasklist & GitHub Issues**: Update the session/project tasklist, post a closure/reconciliation receipt on [Issue #1353](https://github.com/arunakulat/dutchbay-epc-model/issues/1353) naming the merged PR and commit SHA on `origin/main`, and close only the focused GitHub issue named by number on the merged PR's own `Work item:` or closing line (for a train, the train issue and the focused issue named on each car's line), and only when its deliverable is complete. A `Work item:` line that names a #1353 comment closes nothing, and cleanup never closes tracker #1353. Cleanup never closes a pull request.
    2. **Clear, Prune & Close Worktrees**: Synchronize the primary checkout (`git fetch origin main && git checkout main && git pull --ff-only origin main`), remove the merged task worktree (`git worktree remove <worktree-path>`), and run `git worktree prune` (preserving any dirty or concurrently owned worktrees belonging to other active tasks).
    3. **Delete Merged Branches**: Only when the branch's pull request has `merged_at` set, its `head.ref` names the branch, every ref still present (remote and local) equals the merged head, and no open pull request uses the branch as its base (all read immediately before deleting), delete the branch locally (`git branch -D <branch>`, since a squash merge makes `-d` refuse) and remotely (`git push origin --delete <branch>`, skipped if GitHub already auto-deleted it), and run `git fetch --prune origin`. A `TRAIN-01` car branch qualifies only when the train PR merged, the car PR was closed as a landed car, and each ref equals the car head recorded in the train issue. A branch whose pull request is open, closed unmerged, or whose head moved after the merge is never deleted by cleanup.
    4. **Clean Non-Protected Venvs**: Remove any temporary, per-task, or worktree-local virtual environments (`.venv`, `.venv311`, or ad-hoc venvs) associated with the retired worktree/task, while **NEVER** deleting, clearing, pruning, or modifying the protected persistent Python 3.12 environment at `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`, `ENV-01`). Guarded by [`tests/lint/test_gwtf_canonical_source.py`](tests/lint/test_gwtf_canonical_source.py).
  - **No pull request closure**: Cleanup never closes a pull request, and closing an unmerged pull request is never a cleanup step. It needs a cited owner decision, posted as a comment on that pull request before it is closed. The one exception is a `TRAIN-01` car, closed only after the train's post-landing verification proves its commit is on `origin/main`, with the pointer comment posted first. (On 2026-11-05 #1520 and #1525 were closed unmerged seconds after #1531 and #1537 merged.)

### 3.8 Data Ingestion, Persistence, Environment & Dependency Security (`DATA-01`, `PERSIST-01`, `ENV-01`, `THREAD-01`, `SECDEP-01`)
- **`DATA-01` (Lossless Ingestion & Corpus Manifest Integrity)**:
  - Capture every source datum, table cell, unit, caveat, precision, and provenance location. Preserve raw values alongside interpretation.
  - Every corpus area under `docs/source_materials/` must maintain a verified `MANIFEST.sha256` and registered handling statement. After any manifest edit, refresh parent pins with [`scripts/analysis/refresh_corpus_manifest.py`](scripts/analysis/refresh_corpus_manifest.py) and verify via [`tests/lint/test_nso_corpus_manifest_integrity.py`](tests/lint/test_nso_corpus_manifest_integrity.py).
  - Never quote confidential/hash-only commercial terms in public docs, changelogs, or review records.
- **`PERSIST-01` (Early & Frequent Durable Checkpointing)**:
  - Commit coherent slices early, write subagent/review outputs and workflow journals to durable files immediately on completion, and resolve session handovers strictly via [`scripts/list_session_handover_records.py`](scripts/list_session_handover_records.py).
- **`ENV-01` & `THREAD-01` (Repository Rooting & Persistent Python 3.12 Runtime)**:
  - Bind every local session to the durable project `/Users/aruna/Downloads/Dutchbay_EPC_Model` and its governed Python 3.12 virtual environment `DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"`, with the active checkout/worktree first on `PYTHONPATH`.
  - Never create or use `.venv311`, per-task/worktree-local `.venv`s, or bare/system Python. Shared-venv governance changes must pass [`scripts/verify_shared_venv_worktrees.py`](scripts/verify_shared_venv_worktrees.py) across two clean worktrees during a quiet window.
- **`SECDEP-01` (Dependency Advisory Suppression Discipline)**:
  - Every suppressed `pip-audit` advisory in `Makefile` (`PIP_AUDIT_IGNORES`) is a dated claim that must declare the exact package pin, the dependency/constraint cap forcing it, the upstream release that lifts it, and why runtime exposure is defensible. Re-check before `make lock` ([`RELEASING.md`](RELEASING.md), [`tests/lint/test_pip_audit_allowlist.py`](tests/lint/test_pip_audit_allowlist.py), [`tests/lint/test_security_gate_coverage.py`](tests/lint/test_security_gate_coverage.py)).

---

## 4. `RECRUIT-01` — Multi-Agent Recruitment, Lease & Review Architecture

[`RECRUIT-01`](docs/governance/recruit_01/01_capability_and_risk.md) governs all multi-agent and single-agent task execution across four normative modules:

1. **Module 1 — Capability & Semantic Risk Classification ([`01_capability_and_risk.md`](docs/governance/recruit_01/01_capability_and_risk.md))**:
   - **Risk Classes**:
     - `R0_READ_ONLY`: Inspection/research with zero repository mutation.
     - `R1_ROUTINE`: Routine low-risk docs and §3.1's **three bounded low-risk classes**: (a) presentation-only code, (b) test-only guard tightening that never removes/weakens an assertion, and (c) record corrections. Takes **1 independent reviewer lane**.
     - `R2_LOAD_BEARING`: All other code, CI/merge gates, dependency bumps, governance, oracle-defining tests, or writer-authorizing handovers. Takes **2 independent reviewer lanes** (Domain + Assurance).
     - `R3_CONSEQUENTIAL`: Finance/KPI-moving changes, canonical contracts, grid/QSTS execution, or corpus-handling boundaries. Takes **2 independent reviewer lanes** (R3 Domain + R3 Assurance) plus owner KPI sign-off when canonical KPIs move.
2. **Module 2 — Writer Lease & Recovery ([`02_writer_lease_and_recovery.md`](docs/governance/recruit_01/02_writer_lease_and_recovery.md))**:
   - At most **one participant holds an active writer lease** on a branch/worktree (`GRANTED → ACTIVE → CHECKPOINTED → COMPLETED`).
   - Subagents never commit (`D-1`); the sole-writer coordinator verifies and commits.
   - Any session interruption, timeout, crash, or rate-limit immediately revokes lease continuity (`INTERRUPTED → REVOKED`), requiring `DEAD_WORKER_TAKEOVER` preflight before writing resumes.
3. **Module 3 — Independent Exact-Object Review & Attestation ([`03_independent_review_and_attestation.md`](docs/governance/recruit_01/03_independent_review_and_attestation.md))**:
   - Reviewers are strictly read-only (`READ_ONLY_NO_MUTATION`) and never self-approve writer work ([`tests/lint/test_recruit_01_reviewer_supplied_code.py`](tests/lint/test_recruit_01_reviewer_supplied_code.py)).
   - Every review disposition (`ACCEPT`, `CONDITIONAL_ACCEPT`, `REJECT`, `HOLD`) binds to the exact frozen candidate `subject_head_sha`, `subject_tree_sha`, `base_sha`, and sorted subject blob manifest.
   - **§7 Base Fast-Forward & §8 Merge-Train Carry-Forward**: A review disposition survives a base advance or train assembly **only** when three recorded proofs hold: (1) **blob-hash identity** for every reviewed file, (2) **bidirectional import isolation**, and (3) **complete diff** from reviewed head to updated/train head.
4. **Module 4 — Staged Delegation & 5-Tier Worker Ingress ([`04_staged_delegation_and_ingress.md`](docs/governance/recruit_01/04_staged_delegation_and_ingress.md))**:
   - **5-Tier Ingress Order**: Tier 1 (normative contracts & ruleset) → Tier 2 (prior accepted implementation & review chain) → Tier 3 (open residuals & predecessor findings) → Tier 4 (live code, configs, tests) → Tier 5 (live GitHub CI, PRs, tracker `#1353`).
   - Prior assistant, handover, or memory claims are **claims to verify, never authority**.
   - Classify every delegated task outcome as `EVIDENCE_RETURNED`, `NO_FINDING_WITH_EVIDENCE`, `NO_EVIDENCE` (never treated as acceptance), or `BLOCKED_WITH_RECEIPT`.

---

## 5. AI-Specific Governance & Host Directives Across the Codebase

Every AI system interacting with this repository is bound to [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv) and [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md), plus the host-specific controls below:

### 5.1 OpenAI Codex (`AGENTS.md`, `.codex/`, `~/.codex/`)
- **Repo Surfaces**: [`AGENTS.md`](AGENTS.md), [`.codex/config.toml`](.codex/config.toml), [`.codex/environments/environment.toml`](.codex/environments/environment.toml) (guarded by [`tests/lint/test_codex_project_guidance.py`](tests/lint/test_codex_project_guidance.py) and [`tests/lint/test_codex_local_environment.py`](tests/lint/test_codex_local_environment.py)).
- **Host Global Surfaces**: `~/.codex/AGENTS.md`, `~/.codex/config.toml`, `~/.codex/hooks.json`, `~/.codex/hooks/session-root-check.sh`, `~/.codex/memories/skills/dutchbay-shared-venv-quiet-window/SKILL.md`, and `~/.codex/automations/continue-dutchbay-oldest-first-delivery/automation.toml`.
- **Key Rules**:
  - Every Codex task must originate from the `DutchBay_EPC_Model` project and bind to `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`).
  - Runtime diagnostic logs are ephemeral by default; suppress routine `INFO` output during long runs and retain only structured validation facts and governed evidence artifacts.
  - Shared-venv verification (`scripts/verify_shared_venv_worktrees.py`) must run in a quiet window with zero concurrent `$DUTCHBAY_VENV` processes.

### 5.2 Anthropic Claude Code (`CLAUDE.md`, `.claude/`, `~/.claude/`)
- **Repo Surfaces**: [`CLAUDE.md`](CLAUDE.md), [`.claude/settings.json`](.claude/settings.json), [`.claude/hooks/session-start.sh`](.claude/hooks/session-start.sh), and [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md).
- **Host Global Surfaces**: `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/hooks/session-root-check.sh`, and `~/.claude/projects/-Users-aruna-Downloads/memory/` (including `dutchbay_gwtf_ruleset_and_framework_acronyms.md` and `global_commit_and_delegation_directives.md`).
- **Global Operating Directives (`G1` – `G6`)**:
  - **`G1` (Atomic Commits)**: Standing authorization for small, coherent commits on a verified feature branch (`git branch --show-current` first; explicit `git add <paths>`; never `git add -A`/`.`; no `--no-verify`; `R18` commit message; `R21` narrowest check before commit, full suite before push).
  - **`G2` (Risk-Floored Model Tiers)**: Subagent model selection is floored by `RECRUIT-01` risk class (`R0`/`R1` → haiku/sonnet; `R2` → sonnet writer floor, opus reviewers; `R3` → opus writer and reviewers).
  - **`G3` (Self-Contained Briefs)**: Subagent prompts must include exact file paths, line numbers, constraints, and verification commands; subagents never commit (`D-1`).
  - **`G4` (Verify-Then-Accept)**: Inspect `git diff`/`git status`, verify the `TEST-01` independent oracle, and reject `NO_EVIDENCE` returns.
  - **`G5` (Durable Workflow Journals)**: Stream per-agent results immediately to durable storage under `PERSIST-01`.
  - **`G6` (Coordinator Discipline)**: When delegating, the coordinator manages leases, verification, and integration rather than duplicating worker edits.

### 5.3 Google Antigravity / Gemini (`~/.gemini/antigravity/`, `.agents/`)
- **Surfaces**: [`AGENTS.md`](AGENTS.md) (loaded as workspace rule), [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md), `~/.gemini/antigravity/worktrees/`, conversation artifacts under `~/.gemini/antigravity/brain/<conversation-id>/`, and read-only subagent definitions (`r3_domain_reviewer`, `r3_assurance_reviewer` with `EnableWriteTools=false`).
- **Key Rules**:
  - Starts from [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md) and [`AGENTS.md`](AGENTS.md).
  - Uses dedicated worktrees under `WORKTREE-01` and the persistent `DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"` runtime with `PYTHONPATH="$PWD"` (`ENV-01`, `THREAD-01`).
  - Preserves durable artifacts and checkpoints state early (`PERSIST-01`), enforces read-only R3 Domain and R3 Assurance subagent attestation on frozen commit/tree/base SHAs (`RECRUIT-01` Module 3), and formats responses with clickable `file://` links.

### 5.4 Moonshot Kimi (`docs/knowledge_base/`, `docs/PR1336_D1_DOMAIN_REVIEW_R1.md`, `~/.kimi-*`)
- **Surfaces**: [`docs/knowledge_base/06_finance_python_renewables_comparative_review.md`](docs/knowledge_base/06_finance_python_renewables_comparative_review.md) (§ *"Disposition of the KIMI Q4 2026 comparison"*), [`docs/PR1336_D1_DOMAIN_REVIEW_R1.md`](docs/PR1336_D1_DOMAIN_REVIEW_R1.md) (`KIMI-FALSE-BESS-GAP`), and host bridge directories `~/.kimi-webbridge/` and `~/.kimi-work/`.
- **Key Rules**:
  - External AI research reports (such as Kimi comparative reviews) are treated strictly as **unverified claim sets (`Tier 3/4` claims to verify), never as primary sources or authority** (`DATA-01`, `RECRUIT-01` Module 4).
  - Opaque search markers or inaccessible third-party figures (e.g., unverified Lazard/IEA numbers) are **rejected** until primary source documents are ingressed and hash-pinned.
  - False capability gap claims (such as `KIMI-FALSE-BESS-GAP`, which overlooked [`finance/bess_revenue.py`](finance/bess_revenue.py), [`finance/bess_lcos.py`](finance/bess_lcos.py), and [`finance/bess_project_economics.py`](finance/bess_project_economics.py)) must be verified against the live codebase before opening work items.

### 5.5 Perplexity, Grok & External Research LLMs (`legacy/dev_scripts/`, `docs/AGENTIC_DELIVERY_PRACTICE.md`)
- **Surfaces**: [`legacy/dev_scripts/AAA - instructions for make clean zip.md`](legacy/dev_scripts/AAA - instructions for make clean zip.md) (historical Perplexity snapshot workflow, now isolated under `legacy/`) and [`docs/AGENTIC_DELIVERY_PRACTICE.md`](docs/AGENTIC_DELIVERY_PRACTICE.md).
- **Key Rules**:
  - Legacy instructions in `legacy/` (including retired sprint integration branches like `feature/add-finance-contracts-pydantic-v2-20251219` or autonomous-mode overrides) are **retired historical artifacts** and must never be restored ([`tests/lint/test_gwtf_canonical_source.py`](tests/lint/test_gwtf_canonical_source.py)).
  - Any external LLM output (Perplexity, Grok, ChatGPT, etc.) is subject to `DATA-01` primary-source verification, `TEST-01` independent-oracle checks, and `GOV-01` authority boundaries.

### 5.6 GitHub Copilot, Dependabot, Renovate & GitHub Actions Bots (`scripts/ci/`)
- **Surfaces**: [`scripts/ci/check_pr_intake.py`](scripts/ci/check_pr_intake.py), [`scripts/ci/check_pr_receipts.py`](scripts/ci/check_pr_receipts.py), [`tests/lint/test_pr_intake_policy.py`](tests/lint/test_pr_intake_policy.py), and [`tests/lint/test_pr_receipts_policy.py`](tests/lint/test_pr_receipts_policy.py).
- **Key Rules**:
  - The recognized bot set `{dependabot[bot], github-actions[bot], copilot[bot], renovate[bot]}` is exempt from author-side PR body template formatting only at initial PR creation.
  - Under `INTAKE-01` and [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md), **before** any human or agent steward modifies, updates, or merges an automated/bot PR, a **non-bot tracker comment** naming the exact PR (`#N`) must be posted on [Issue #1353](https://github.com/arunakulat/dutchbay-epc-model/issues/1353), and attribution must be verified by comparing `commits[].author.login` against the PR `user.login`.

---

## 6. Quick Pre-Commit & Pre-Push Verification Commands

Run the narrowest meaningful checks before each commit (`R21`), and broaden before pushing:

```bash
# 1. Confirm branch is NOT main/master (GOV-02)
git branch --show-current
git status --short --branch

# 2. Validate canonical GWTF CSV & handover chain (PERSIST-01)
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python \
  dutchbay_bootstrap_rules.py
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python scripts/list_session_handover_records.py

# 3. Run focused pytest, ruff & whitespace checks (R21, VERIFY-01)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
  -p no:cacheprovider tests/lint/ -q
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff check <changed-paths>
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff format --check <changed-paths>
git diff --check
```
