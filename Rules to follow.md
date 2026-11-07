# Rules to Follow — Unified Governance, Frameworks & Multi-Agent Reference

> **Authority & Non-Forking Notice (`GOV-01`, `RECRUIT-01`)**
> The single canonical source of truth for project governance is [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv). This document is an index and summary across the governance modules, the architectural frameworks, and the AI agent hosts that work in this repository (Claude, OpenAI Codex, Google Antigravity / Gemini, Kimi, Perplexity, GitHub Copilot, and CI bots). Where any summary disagrees with [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv), the CSV wins. Cite a rule by its ID and read its text in the CSV; the rule index in §3.0 gives each ID's exact CSV title, and `tests/lint/test_rules_to_follow_index.py` keeps that index, and every bold heading that pairs a rule ID with a title, equal to the CSV.
> This document grants no merge, review, lease, release, grade, lender, or Board authority to any session.

---

## 1. Session Bootstrap (`THREAD-01`, `ENV-01`)

Before editing any file, opening a PR, or claiming verification, run the bootstrap from the active checkout or its dedicated worktree, with that checkout first on `PYTHONPATH`. Which Python 3.12 environment you use depends on the host.

**Local sessions on the owner's machine** use the persistent governed environment that `THREAD-01` names:

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

**Ephemeral CI or container hosts, and unconfigured developer hosts,** leave `DUTCHBAY_VENV` unset and use the checkout-local `.venv`. `THREAD-01` and `ENV-01` permit it only as this portable fallback, never as a per-task replacement for the persistent environment on the owner's machine. In a Claude Code cloud session, `.claude/hooks/session-start.sh` provisions it ([`CLAUDE.md`](CLAUDE.md)):

```bash
CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/session-start.sh
.venv/bin/python -VV   # must report Python 3.12
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" \
  .venv/bin/python dutchbay_bootstrap_rules.py
```

### Core Primary Sources (Click to Open)

| Document | Scope & Authority |
|---|---|
| [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv) | **Canonical GWTF v3.0 Ruleset** (79 active rules across 41 categories; validated by [`dutchbay_bootstrap_rules.py`](dutchbay_bootstrap_rules.py) and [`tests/lint/test_gwtf_canonical_source.py`](tests/lint/test_gwtf_canonical_source.py)). |
| [`AGENTS.md`](AGENTS.md) | **Codex & Universal Agent Gateway** — runtime requirements (`ENV-01`, `THREAD-01`), intake (`INTAKE-01`), delivery (`DELIVERY-01`, `REVIEW-01`, `TRAIN-01`, `MERGE-01`, `CLEANUP-01`), corpus manifest rules (`DATA-01`), and `DBPL-01`. Guarded by [`tests/lint/test_codex_project_guidance.py`](tests/lint/test_codex_project_guidance.py). |
| [`CLAUDE.md`](CLAUDE.md) | **Claude Code entry point** — what changes in a cloud session (the checkout-local `.venv`, Codex-only steps), the formats the repository checks, and a pointer to [`AGENTS.md`](AGENTS.md). |
| [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md) | **Multi-Agent Session Router** — routes any non-Codex or cloud session to its governing documents. Guarded by [`tests/lint/test_agent_session_routing.py`](tests/lint/test_agent_session_routing.py). |
| [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md) | **Steward Skill** — PR driving, base-currency maintenance, `Evidence pack` formatting, Grid Study classification, `MERGE-01` boundary checks, and `TRAIN-01` merge-train execution. |
| [`docs/governance/recruit_01/01_capability_and_risk.md`](docs/governance/recruit_01/01_capability_and_risk.md) | **`RECRUIT-01` Module 1** — Written capability profiles, semantic risk classes (`R0_READ_ONLY` to `R3_CONSEQUENTIAL`), and the §3.1 bounded low-risk classes (`REVIEW-01`). |
| [`docs/governance/recruit_01/02_writer_lease_and_recovery.md`](docs/governance/recruit_01/02_writer_lease_and_recovery.md) | **`RECRUIT-01` Module 2** — One-writer invariant, lease fields, the mandatory state machine, interruption recovery, and dead-worker takeover. |
| [`docs/governance/recruit_01/03_independent_review_and_attestation.md`](docs/governance/recruit_01/03_independent_review_and_attestation.md) | **`RECRUIT-01` Module 3** — Independence, the frozen subject manifest, structured disposition receipts, §7 base movement and merge continuity, and §8 `TRAIN-01` merge-train carry-forward. |
| [`docs/governance/recruit_01/04_staged_delegation_and_ingress.md`](docs/governance/recruit_01/04_staged_delegation_and_ingress.md) | **`RECRUIT-01` Module 4** — Source hierarchy, safety preflight, substantive ingress order, capacity admission, and evidence-yield states (`EVIDENCE_RETURNED`, `NO_FINDING_WITH_EVIDENCE`, `NO_EVIDENCE`, `BLOCKED_WITH_RECEIPT`). |
| [`.github/SPRINT_WORKFLOW_CHECKLIST.md`](.github/SPRINT_WORKFLOW_CHECKLIST.md) | **Sprint Workflow Checklist** — pre-sprint, implementation, review, and pre-merge compliance checklist derived from the CSV. |
| [`docs/AGENTIC_DELIVERY_PRACTICE.md`](docs/AGENTIC_DELIVERY_PRACTICE.md) | **Agentic Delivery Practice** — empirical practitioner evidence, anti-gaming controls ([`tests/finance/test_canon_vector_is_computed.py`](tests/finance/test_canon_vector_is_computed.py)), verification capacity principle, and explicitly rejected agent patterns. |

---

## 2. Canonical Framework Acronyms (`FRAMEWORK-01` – `FRAMEWORK-03`)

`CASPER`, `CESSPIT`, and `CCCDIR` are **three peer rules** in [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv) (Category: `Framework Principles`), guarded across all tracked files by [`tests/lint/test_framework_expansions_match_csv.py`](tests/lint/test_framework_expansions_match_csv.py). Never use retired or invented expansions.

### `FRAMEWORK-01`: CASPER
- **Primary Definition**: **CASPER** — *Clear API Surfaces with Predictable Error Responses*.
  - Modules expose clean, documented interfaces with consistent error handling patterns.
  - Optional dependencies fail gracefully at call time, not import time, with actionable error messages (in this codebase, call-time `_require_*()` guards). `DBPL-01` is the deliberate exception: a DBPL print fails loud with `DbplDependencyError`.
- **Secondary Definition**: *Contract-Assured Scenario Pipeline for Energy & Renewables*.
- **Monte Carlo Integration** ([`docs/CASPER_MC_INTEGRATION.md`](docs/CASPER_MC_INTEGRATION.md)):
  - [`analytics/casper/casper_payload.py`](analytics/casper/casper_payload.py) (`build_casper_payload()`) auto-wires top-level `mc_risk` (`{"lender_risk_table": [...], "covenant": {...}}`) into `casper_result_v1` payloads via `build_casper_risk_blocks()` and `CovenantSpec`, resolving `dscr_floor` config-first via [`analytics/mc/covenant.py`](analytics/mc/covenant.py) (`resolve_min_dscr_covenant`).

### `FRAMEWORK-02`: CESSPIT
- **Primary Definition**: **CESSPIT** — *Config Explicit, Schema Strict, Pre-flight Integrity Tests*.
  - All scenario parameters live in `YAML`/`JSON` configs; no silent defaults or fallbacks for critical parameters (FX, tax, debt terms).
  - [`analytics/schema_guard.py`](analytics/schema_guard.py) (`validate_config_for_v14`) is the pre-flight gatekeeper, strict by default (`R5`, `R22`). Never weaken validation with `strict=False`.
- **Secondary Definition**: *Config-Enforced Schema Safety Pipeline Integration Triad*.

### `FRAMEWORK-03`: CCCDIR
- **Primary Definition**: **CCCDIR** — *Contracts Centralized, Compliance Documented, Import Relationships explicit*.
  - All canonical result types (`ScenarioResult`, `SensitivityResult`, `MonteCarloResult`, `CasperPayload`) live in [`analytics/contracts_v14.py`](analytics/contracts_v14.py).
  - Analytics modules import result types from `contracts_v14` and evaluation only through [`analytics/evaluation_v14.py`](analytics/evaluation_v14.py) (`evaluate_with_overrides()`); direct imports of internal evaluation logic are forbidden ([`tests/lint/test_contracts_gateway_imports.py`](tests/lint/test_contracts_gateway_imports.py), [`tests/lint/test_no_direct_finance_pipeline_imports.py`](tests/lint/test_no_direct_finance_pipeline_imports.py)).
- **Secondary Definition**: *Config-Centric Contract-Driven Integration Rules*.

---

## 3. GWTF v3.0 Ruleset Summary

### 3.0 Rule Index (exact CSV IDs, categories and titles)

Every active rule in the CSV, in CSV order. A bold heading below that pairs a rule ID with a title uses that rule's exact CSV title; the explanation that follows it is a summary, and the CSV text governs.

| Rule | Category | Title |
|---|---|---|
| `GOV-01` | Governance | AI-assisted development contract |
| `INTAKE-01` | Governance & Workflow | Record work before development and reconcile the live queue |
| `ARCH-01` | Architecture & Config | Config-first architecture |
| `R1` | CLI Entry | Canonical v14 entrypoints |
| `CLI-01` | CLI & Tooling | CLI framework scope |
| `ADD-01` | Addendum - Hydra & LibCST | Hydra integration rationale and pattern |
| `VAL-01` | Validation & Schema Guard | Schema-first validation for v14 scenarios |
| `CST-01` | LibCST & Banned APIs | LibCST guardrails for imports and hot-spot APIs |
| `TYPE-01` | Types & Tests & CI | Typed-first v14 code |
| `TEST-01` | Types & Tests & CI | Regression tests and pins for financial behaviour |
| `FIN-01` | Financial Modelling | Numeric robustness and IRR/NPV safety |
| `DOC-01` | Documentation | Documented scenarios and assumptions |
| `MRM-01` | Model Risk & Reproducibility | Deterministic runs for stochastic components |
| `R2` | Config Model | Config-first CLIs via Hydra |
| `CST-02` | LibCST & Banned APIs | Safe refactoring with LibCST |
| `DOC-02` | Documentation | Model change log for IRR/DSCR-impacting changes |
| `DOC-03` | Documentation | Board-ready and lender-DD-safe documentation |
| `ADD-02` | Addendum - Hydra & LibCST | LibCST enforcement of CLI framework rules |
| `FIN-02` | Financial Modelling | Explicit units and naming conventions |
| `TEST-02` | Types & Tests & CI | Coverage philosophy and fast-lane CI |
| `TEST-03` | Types & Tests & CI | Bound stochastic model evaluations in the ordinary pytest suite |
| `TEST-04` | Types & Tests & CI | Separate report transport contracts from live report qualification |
| `TEST-05` | Types & Tests & CI | Require independent CI evidence for QSTS execution claims |
| `VAL-02` | Validation & Schema Guard | ScenarioAnalytics batch behaviour |
| `CLI-02` | CLI & Tooling | Canonical v14 entrypoints |
| `MRM-02` | Model Risk & Reproducibility | Reproducible artefacts and audit trail |
| `ARCH-02` | Architecture & Config | IRR / NPV isolation |
| `CLI-03` | CLI & Tooling | JSON-first outputs for automation |
| `ADD-03` | Addendum - Hydra & LibCST | Extending Hydra + LibCST to new tasks |
| `ARCH-03` | Architecture & Config | Tranche-aware debt result surface |
| `R3` | Banned APIs | No argparse anywhere in repo |
| `R4` | Banned APIs | No Typer in v14 CLIs |
| `R5` | Schema Guard | Schema guard as pre-flight gatekeeper |
| `R6` | FX Config | FX is a mapping, not a scalar |
| `R7` | IRR/NPV Location | IRR/NPV live only in finance/irr.py |
| `R8` | Coverage | Coverage philosophy (fast lane vs full suite) |
| `R9` | Debt & KPIs | Tranche-aware debt_result surface |
| `R10` | Code Quality | Pre-commit hooks mandatory |
| `R11` | Testing | v14 API tests are canonical |
| `R12` | Repository Structure | Legacy code isolation |
| `R13` | Data Organization | FX data in inputs/fxdata/ |
| `R14` | Module Organization | Scripts belong in scripts/ |
| `R15` | Type Safety | mypy strict mode for new code |
| `R16` | Import Safety | No circular imports |
| `R17` | Documentation | Docstrings for public APIs |
| `R18` | Git Workflow | Descriptive commit messages |
| `R19` | File Naming | No spaces in filenames |
| `R20` | Output Management | Generated files in outputs/ |
| `R21` | Developer Workflow | Standard local workflow: bootstrap + pytest |
| `R22` | Schema Guard | Test configs must be v14-compliant |
| `R23` | Git Workflow | Branch-based development with full CI gate |
| `ARCH-04` | Architecture & Config | Contract gateway pattern for analytics evaluation |
| `SPRINT16_DOC_MGMT_R1` | Documentation Delivery | AI-Generated docs pushed to feature branch first |
| `SPRINT_BOOTSTRAP_PROC_R1` | Sprint Initialization | Mandatory Sprint Bootstrap Documentation Delivery Procedure |
| `R24` | Code Quality | Docstring-first development minimal external documentation |
| `R25` | Git Workflow | Protected-main PR and worktree integration strategy |
| `FRAMEWORK-01` | Framework Principles | CASPER - Clear API Surfaces with Predictable Error Responses |
| `FRAMEWORK-02` | Framework Principles | CESSPIT - Config Explicit Schema Strict Pre-flight Integrity Tests |
| `FRAMEWORK-03` | Framework Principles | CCCDIR - Contracts Centralized Compliance Documented Import Relationships explicit |
| `DELIVERY-01` | Delivery Cadence | Dolphins, not whales - incremental delivery as the default |
| `REFACTOR-01` | Refactoring Strategy | Dolphin Strategy - Zero-Breakage Incremental Migration |
| `REFACTOR-02` | Refactoring Strategy | Import Safety Patterns for Migration |
| `REFACTOR-03` | Refactoring Strategy | Migration Commit Standards |
| `REFACTOR-04` | Refactoring Strategy | Shim Lifecycle Management |
| `WORKTREE-01` | Concurrency & Isolation | Dedicated git worktree per concurrent agent or session |
| `GOV-02` | Governance & Workflow | No direct commits to protected branches; verify the active branch |
| `R26` | CLI & Tooling | Convert PDFs with governed MarkItDown before parsing |
| `DATA-01` | Data & Ingestion | Lossless ingestion - capture every data point from ingested material |
| `PERSIST-01` | Continuity & Persistence | Checkpoint durable state early and often to survive interruptions |
| `ENV-01` | Continuity & Persistence | Root repository work at the active checkout and bind shared Python imports to it |
| `THREAD-01` | Continuity & Persistence | Create every new thread in the DutchBay_EPC_Model project and use its persistent venv |
| `DBPL-01` | Documentation Delivery | DutchBay Presentation Layer - DBPL PDFs use the full [report] stack and house style |
| `VERIFY-01` | Verification | A claimed check without a receipt is not a check |
| `MERGE-01` | Git Workflow | Merge on green - standing authorization, no per-PR go-ahead |
| `RECRUIT-01` | Recruitment & Review | Recruit through globally applicable, risk-scaled operational modules |
| `SECDEP-01` | Dependency Security | A suppressed advisory declares the cap that forces it and the release that lifts it |
| `REVIEW-01` | Recruitment & Review | Review before the full suite: one lane for bounded low-risk work, two for load-bearing |
| `TRAIN-01` | Git Workflow | Merge trains: reviewed pull requests share one full-suite run and land as separate commits |
| `CLEANUP-01` | Git Workflow | Post-merge tracker notification, issue closure, and worktree/branch/venv retirement |

### 3.1 Governance & Intake
- **`GOV-01`: AI-assisted development contract**: AI tools are bound by the Go-with-the-Flow ruleset. They must not bypass tests, CI, schema guard, or code review, and AI-generated changes meet the same standards as human-written code, including typing, tests, and documentation. (The owner's release, grade, lender and Board authority boundaries are stated in `MERGE-01`, `REVIEW-01`, `TRAIN-01` and `RECRUIT-01`, not in `GOV-01`.)
- **`GOV-02`: No direct commits to protected branches; verify the active branch**: Never commit directly to `main` or any protected branch. Verify `git branch --show-current` before every commit, and recover commits that landed on the wrong branch remote-first.
- **`INTAKE-01`: Record work before development and reconcile the live queue**: Before editing any file or opening a PR:
  1. Fetch and verify `origin/main`.
  2. Read the live capability tracker ([Issue #1353](https://github.com/arunakulat/dutchbay-epc-model/issues/1353)) and enumerate every open PR.
  3. Advance an actionable overlapping PR first; record a blocked or owner-deferred PR with its revisit trigger.
  4. Record the scoped work on `#1353` or a focused issue linked from it **before editing**, and cite the work item, base SHA, and open-PR sweep disposition in the PR body. CI ([`scripts/ci/check_pr_intake.py`](scripts/ci/check_pr_intake.py), [`tests/lint/test_pr_intake_policy.py`](tests/lint/test_pr_intake_policy.py)) can check that the record predates the PR, not that it predates the first edit.

### 3.2 Architecture & Config
- **`ARCH-01`: Config-first architecture**: All scenario parameters and pipeline modes live in YAML/JSON config files, not hardcoded; no hidden config switches in code.
- **`ARCH-02`: IRR / NPV isolation**: `irr`, `xirr`, and `npv` are defined only in [`finance/irr.py`](finance/irr.py) (also `R7`). Enforced by [`tests/lint/test_irr_location_v14.py`](tests/lint/test_irr_location_v14.py).
- **`ARCH-03`: Tranche-aware debt result surface**: `finance.debt_v14.plan_debt` returns tranche-keyed metrics plus aggregates such as `total_idc`; legacy flat keys are deprecated (also `R9`).
- **`ARCH-04`: Contract gateway pattern for analytics evaluation**: Analytics modules use [`analytics/contracts_v14.py`](analytics/contracts_v14.py) for result types and `analytics.evaluation_v14.evaluate_with_overrides()` as the only evaluation entry point (`FRAMEWORK-03`).

### 3.3 CLI & Tooling
- **`CLI-01`: CLI framework scope**: All v14 CLIs use Hydra (`hydra-core`). `argparse` is banned repo-wide, and legacy Typer/Click tools are frozen. Enforced by [`tests/lint/test_entrypoints_hydra_only.py`](tests/lint/test_entrypoints_hydra_only.py).
- **`CLI-02`: Canonical v14 entrypoints**: The single-scenario entrypoint is `run_full_pipeline_v14.py` and the batch ScenarioAnalytics entrypoint is `run_scenario_analytics_v14.py`; both are Hydra-based and emit JSON plus artefacts (also `R1`).
- **`CLI-03`: JSON-first outputs for automation**: Hydra CLIs emit a single JSON object to stdout summarising the run (KPIs, counts, paths); logging may share stdout only if tests can reliably slice out the JSON block.
- **`R2`: Config-first CLIs via Hydra**: Defaults live under `conf/*.yaml`; runtime changes use Hydra overrides; no manual `sys.argv` parsing.
- **`R3`: No argparse anywhere in repo**: Enforced by [`tests/lint/test_no_argparse_anywhere.py`](tests/lint/test_no_argparse_anywhere.py).
- **`R4`: No Typer in v14 CLIs**: Enforced by [`tests/lint/test_no_typer_v14.py`](tests/lint/test_no_typer_v14.py).
- **`ADD-01`, `ADD-02`, `ADD-03`** (Hydra & LibCST addendum): why Hydra centralises CLI configuration, how LibCST enforces the CLI framework bans, and how new pipeline components extend both.
- **`R26`: Convert PDFs with governed MarkItDown before parsing**: Never parse a PDF from raw WebFetch/HTTP output. Convert it with the governed Python 3.12 MarkItDown toolchain (`.venv/bin/python -m markitdown <file-or-url.pdf>`), corroborate with `pdfplumber`/`PyMuPDF` where layout or completeness matters, and render/OCR image-only PDFs before drawing claims.

### 3.4 Validation, Schema Guard, LibCST & Typing
- **`VAL-01`: Schema-first validation for v14 scenarios**: `validate_config_for_v14` is the pre-flight gatekeeper; in strict mode a config must provide a valid FX mapping and a corporate tax rate, and invalid configs fail fast (also `R5`, `R6`, `R22`).
- **`VAL-02`: ScenarioAnalytics batch behaviour**: One bad scenario never crashes the batch; invalid scenarios are logged with reasons and skipped, and the summary exposes `n_success`, `n_failed`, and per-scenario failure messages.
- **`FIN-02`: Explicit units and naming conventions**: Config fields encode units in their names (`*_pct`, `*_years`, `*_usd`, `*_lkr`); never mix percentage forms such as `5` and `0.05` without explicit naming, and never conflate currency, MW, and hours.
- **`CST-01`: LibCST guardrails for imports and hot-spot APIs**: LibCST-based tests ban `argparse` imports anywhere and Typer/Click imports in v14-critical paths, forbid interactive `input()` in CI-covered code, and confine IRR/NPV definitions to `finance/irr.py`.
- **`TYPE-01`: Typed-first v14 code**: New v14 modules are fully type-annotated, and `mypy` is clean for `analytics/`, `finance/`, and `dutchbay_v14chat/` (also `R15`). Docstrings are `R17` and `R24`, guarded by [`tests/lint/test_docstring_coverage.py`](tests/lint/test_docstring_coverage.py).

### 3.5 Testing, Coverage & Verification
- **`TEST-01`: Regression tests and pins for financial behaviour**:
  - Core financial behaviour is covered by regression tests with stable pins, and tests are updated whenever business logic changes.
  - A pin proves only that a number did not change; pair it with a **responsiveness guard** (for example [`tests/finance/test_canon_vector_is_computed.py`](tests/finance/test_canon_vector_is_computed.py)).
  - Finance-material code must also answer to an **independent oracle** that did not originate in the same change (a pre-existing test, an external benchmark, a closed-form check, an independent implementation, or a property/invariant).
- **`TEST-02`: Coverage philosophy and fast-lane CI**: Fast-lane CI covers style, `mypy`, and CLI smoke tests; coverage thresholds apply to the full suite (also `R8`). The full-suite gate is `coverage report --fail-under=95` in [`.github/workflows/test-suite.yml`](.github/workflows/test-suite.yml), checked by [`tests/lint/test_coverage_gate_policy.py`](tests/lint/test_coverage_gate_policy.py).
- **`TEST-03`: Bound stochastic model evaluations in the ordinary pytest suite**: The ordinary suite is a deterministic regression and coverage gate; a test that repeatedly executes the Monte Carlo model or full pipeline uses no more than 200 effective model evaluations ([`tests/lint/test_stochastic_suite_policy.py`](tests/lint/test_stochastic_suite_policy.py)).
- **`TEST-04`: Separate report transport contracts from live report qualification**: Ordinary report and API tests exercise transport and renderer contracts without repeatedly recomputing the full supplemental-sensitivity stack.
- **`TEST-05`: Require independent CI evidence for QSTS execution claims**: A PR whose acceptance depends on QSTS execution needs a GitHub-hosted `Grid Study` on Python 3.12 bound to the exact head SHA ([`tests/lint/test_grid_ci_policy.py`](tests/lint/test_grid_ci_policy.py)).
- **`VERIFY-01`: A claimed check without a receipt is not a check**:
  - Every PR records each check's command and result, or an explicit `not run - <reason>`, in the receipts table of `.github/pull_request_template.md`. Enforced by the required check `Verification receipts (VERIFY-01)` ([`scripts/ci/check_pr_receipts.py`](scripts/ci/check_pr_receipts.py), [`.github/workflows/pr-receipts.yml`](.github/workflows/pr-receipts.yml), [`tests/lint/test_pr_receipts_policy.py`](tests/lint/test_pr_receipts_policy.py)).
  - A new guard ships with the negative control demonstrating that it fires.

### 3.6 Finance, Documentation, Model Risk & Presentation
- **`FIN-01`: Numeric robustness and IRR/NPV safety**: IRR/NPV routines use stable numeric methods with sensible tolerances, handle non-convergence gracefully (for example return `None` and log), and never fall back silently in a way that changes financial meaning.
- **`DOC-01`: Documented scenarios and assumptions**: Key financial assumptions (tariff, FX regime, tax rules, leverage, DSCR thresholds) are documented both in YAML configs and in generated summary tables usable with lenders and stakeholders.
- **`DOC-02`: Model change log for IRR/DSCR-impacting changes**: Any change that can affect IRR, DSCR, NPV, or covenant logic updates the model [`CHANGELOG.md`](CHANGELOG.md) (via `changelog.d/`) and bumps [`VERSION`](VERSION), with regression test updates and explicit reviewer sign-off.
- **`DOC-03`: Board-ready and lender-DD-safe documentation**: Documentation meets institutional review standards: verified claims with explicit sources, documented contract changes, and no hyperbole or informal tone.
- **`MRM-01`: Deterministic runs for stochastic components**: Monte Carlo and other stochastic routines accept an explicit seed or RNG config; CI uses fixed seeds and production runs log the seed.
- **`MRM-02`: Reproducible artefacts and audit trail**: Exported artefacts carry the scenario name, config path or hash, and model version, so any reported KPI set can be reconstructed.
- **`DBPL-01`: DutchBay Presentation Layer - DBPL PDFs use the full [report] stack and house style**:
  - Any PDF described as a DBPL document must be rendered through [`app/reports/dbpl/print_core.py`](app/reports/dbpl/print_core.py) (`render_dbpl_pdf`), requiring the complete `[report]` extra (`weasyprint`, `reportlab`, `geopandas`, `contextily`) and failing loud with `DbplDependencyError` if any dependency is missing.
  - Design tokens are generated from [`app/reports/dbpl/style.py`](app/reports/dbpl/style.py); document control and the running page furniture are mandatory ([`docs/dbpl_styleguide.md`](docs/dbpl_styleguide.md)).

### 3.7 Git Workflow, Delivery & Refactoring
- **`R10`–`R25`** (code quality, repository layout and workflow): pre-commit hooks are mandatory (`R10`); legacy code is isolated under `legacy/` (`R12`, [`tests/lint/test_no_legacy_imports.py`](tests/lint/test_no_legacy_imports.py)); Python filenames carry no spaces or special characters (`R19`); generated files go to `outputs/` (`R20`); development is branch-based with a full CI gate (`R23`) on a protected `main` (`R25`). The index in §3.0 lists every title.
- **`R18`: Descriptive commit messages**: Subjects use `type: summary` or `type(scope): summary` from the eleven Conventional Commits types (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`); `deploy` is not sanctioned. There is no commit-message linter; [`tests/lint/test_commit_message_conformance.py`](tests/lint/test_commit_message_conformance.py) measures conformance and binds its type set to the CSV.
- **`R21`: Standard local workflow: bootstrap + pytest**: Run the narrowest meaningful check before each commit while iterating, and the full suite before pushing.
- **`DELIVERY-01`: Dolphins, not whales - incremental delivery as the default** and **`REFACTOR-01`: Dolphin Strategy - Zero-Breakage Incremental Migration** (with `REFACTOR-02`–`REFACTOR-04`):
  - Ship work as small, complete, independently reversible PRs ("dolphins"), never monolithic "whale" mega-PRs.
  - Incremental refactoring follows `MOVE → SHIM → UPDATE → DEPRECATE` one module at a time with zero breakage.
- **`WORKTREE-01`: Dedicated git worktree per concurrent agent or session**: Every concurrent or background agent that mutates the working tree uses its own dedicated `git worktree` and branch. Never use `git stash` for cross-branch peeking.
- **`REVIEW-01`: Review before the full suite: one lane for bounded low-risk work, two for load-bearing**:
  1. Open PR as a **draft** (`test-suite.yml` runs fast gates only and reports `Test Summary (draft: full suite deferred)`).
  2. Freeze the draft HEAD and post one `Evidence pack` comment.
  3. Bind independent review lanes to that exact draft HEAD (`R1` including Module 1 §3.1's 3 bounded classes = 1 lane; `R2`/`R3` = 2 lanes: Domain + Assurance).
  4. Mark the PR **ready for review** so the full sharded suite runs once. Any subsequent change to the PR's files restarts all reviews (Module 3 §6). Enforced by [`tests/lint/test_review_first_policy.py`](tests/lint/test_review_first_policy.py).
- **`TRAIN-01`: Merge trains: reviewed pull requests share one full-suite run and land as separate commits**:
  - The merge coordinator (who is not the writer of any car) may combine 2 or 3 reviewed draft PRs ("cars") that are path-disjoint, unstacked, and bidirectionally import-isolated (with at most one `R3`/KPI-changing car) onto a branch `train/<date>-<n>` starting at `origin/main` (one non-merge commit per car).
  - Review bindings carry forward onto the train head only via `RECRUIT-01` Module 3 §8's three proofs (blob-hash identity, bidirectional import isolation, complete reviewed-to-updated diff).
  - The train runs the full suite once and lands via **rebase-merge** (never squash), verified before and after landing by the fail-closed shell blocks in [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md) and [`tests/lint/test_train_policy.py`](tests/lint/test_train_policy.py).
- **`MERGE-01` (Standing Merge-on-Green Authority & Boundaries)**:
  - Standing authorization to merge a PR as soon as every required check reports success on the exact current HEAD (`Test Summary`, `Code Quality Checks`, `Security Scan`, `Verification receipts (VERIFY-01)`, and conditional `Coverage Gate` / `Grid Study`) with no conflict and up-to-date base.
  - **Boundary**: Merging is delivery authority only; it lifts no `HOLD` (such as `#1110`), and confers no grade, release, audit, lender, or Board authority. *(Note: When the project owner places a temporary session hold on `MERGE-01`, honour that hold until explicitly lifted.)*
- **`CLEANUP-01` (Post-Merge Tracker Notification, Issue Closure & Worktree/Branch/Venv Retirement)**:
  - Immediately after any PR or `TRAIN-01` merge train lands on `origin/main` and protected-main ancestry/tree verification succeeds:
    1. **Inform Tasklist & GitHub Issues**: Update the session/project tasklist, post a closure/reconciliation receipt on [Issue #1353](https://github.com/arunakulat/dutchbay-epc-model/issues/1353) naming the merged PR and commit SHA on `origin/main`, and close completed focused GitHub issue(s) (or each car PR and train issue for a train).
    2. **Clear, Prune & Close Worktrees**: Synchronize the primary checkout (`git fetch origin main && git checkout main && git pull --ff-only origin main`), remove the merged task worktree (`git worktree remove <worktree-path>`), and run `git worktree prune` (preserving any dirty or concurrently owned worktrees belonging to other active tasks).
    3. **Delete Merged Branches**: Delete the merged branch locally (`git branch -d <branch>`) and remotely (`git push origin --delete <branch>`), and run `git fetch --prune origin`.
    4. **Clean Non-Protected Venvs**: Remove any temporary, per-task, or worktree-local virtual environments (`.venv`, `.venv311`, or ad-hoc venvs) associated with the retired worktree/task, while **NEVER** deleting, clearing, pruning, or modifying the protected persistent Python 3.12 environment at `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`, `ENV-01`). Guarded by [`tests/lint/test_gwtf_canonical_source.py`](tests/lint/test_gwtf_canonical_source.py).

### 3.8 Data Ingestion, Persistence, Environment & Dependency Security (`DATA-01`, `PERSIST-01`, `ENV-01`, `THREAD-01`, `SECDEP-01`)
- **`DATA-01` (Lossless Ingestion & Corpus Manifest Integrity)**:
  - Capture every source datum, table cell, unit, caveat, precision, and provenance location. Preserve raw values alongside interpretation.
  - Every corpus area under `docs/source_materials/` must maintain a verified `MANIFEST.sha256` and registered handling statement. After any manifest edit, refresh parent pins with [`scripts/analysis/refresh_corpus_manifest.py`](scripts/analysis/refresh_corpus_manifest.py) and verify via [`tests/lint/test_nso_corpus_manifest_integrity.py`](tests/lint/test_nso_corpus_manifest_integrity.py).
- **`PERSIST-01`: Checkpoint durable state early and often to survive interruptions**: Commit coherent slices early, write workflow, subagent and review results to durable files the moment they land, and resolve session handovers via [`scripts/list_session_handover_records.py`](scripts/list_session_handover_records.py).
- **`ENV-01`: Root repository work at the active checkout and bind shared Python imports to it** and **`THREAD-01`: Create every new thread in the DutchBay_EPC_Model project and use its persistent venv**:
  - Root every task at the active checkout or its dedicated worktree, with that worktree first on `PYTHONPATH`. Local threads bind to the governed Python 3.12 environment `DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"`.
  - Do not create or select a temporary or per-thread replacement venv, `.venv311`, or bare/system Python. The one exception is the checkout-local `.venv` as the portable fallback when `DUTCHBAY_VENV` is unset on an unconfigured developer host or an ephemeral CI/container host (§1).
  - Shared-venv governance changes must pass [`scripts/verify_shared_venv_worktrees.py`](scripts/verify_shared_venv_worktrees.py) across two clean worktrees during a quiet window.
- **`SECDEP-01`: A suppressed advisory declares the cap that forces it and the release that lifts it**:
  - Every suppressed `pip-audit` advisory in `Makefile` (`PIP_AUDIT_IGNORES`) is a dated claim that must declare the exact package pin, the dependency/constraint cap forcing it, the upstream release that lifts it, and why the suppression is defensible. Re-check the cap before `make lock` ([`RELEASING.md`](RELEASING.md), [`tests/lint/test_pip_audit_allowlist.py`](tests/lint/test_pip_audit_allowlist.py), [`tests/lint/test_security_gate_coverage.py`](tests/lint/test_security_gate_coverage.py)).

---

## 4. `RECRUIT-01` — Multi-Agent Recruitment, Lease & Review Architecture

**`RECRUIT-01`: Recruit through globally applicable, risk-scaled operational modules**. Its executable requirements live in four canonical modules:

1. **Module 1 — Capability profiles and semantic risk ([`01_capability_and_risk.md`](docs/governance/recruit_01/01_capability_and_risk.md))**:
   - A written capability profile precedes dispatch; a worker's self-description is a claim to verify.
   - **Risk classes** (classify the highest semantic consequence; filename and language do not lower the class):
     - `R0_READ_ONLY`: inspection, inventory, diagnosis, or discussion with no governed mutation.
     - `R1_ROUTINE`: non-authoritative prose and other clearly reversible changes with no behavioural or authority effect, plus §3.1's **three bounded low-risk classes**: (a) presentation-only code, (b) test-only guard tightening that never removes or weakens an assertion, and (c) record corrections. One independent reviewer.
     - `R2_LOAD_BEARING`: any code outside §3.1's classes, contracts, schemas, oracle-defining tests, governance, charters, handovers, review records, provenance, security, data ingestion, and similar work. Two independent reviewers: one task-domain and one separate assurance reviewer.
     - `R3_CONSEQUENTIAL`: finance/KPI behaviour, lender or Board-facing evidence, grade/release logic, security boundaries, and similar consequential work. At least the `R2` pair plus every specialist, oracle, human authority and gate the controlling rules require.
2. **Module 2 — Writer leases, recovery, and closure ([`02_writer_lease_and_recovery.md`](docs/governance/recruit_01/02_writer_lease_and_recovery.md))**:
   - One delivery coordinator; at most **one participant holds an active writer lease** for a worktree and checkpoint, and every other participant, including all reviewers, stays read-only.
   - Leases follow a mandatory state machine from `READ_ONLY` through `LEASED`, `FROZEN`, `UNDER_REVIEW`, `MERGED` and `WORKTREE_AND_BRANCH_RETIRED` to `CLOSED`; a writer lease expires at `CHECKPOINT_VERIFIED`.
   - Any interruption, drift, or unexpected writer activity revokes the lease (`PRESERVE_OBSERVED_STATE → REVOKE_LEASE → READ_ONLY`); a non-responsive worker is replaced only through `DEAD_WORKER_TAKEOVER`.
3. **Module 3 — Independent review and exact-object attestation ([`03_independent_review_and_attestation.md`](docs/governance/recruit_01/03_independent_review_and_attestation.md))**:
   - Required reviewers are distinct from the writer, the coordinator and each other, stay read-only, and return their initial dispositions independently. One veto blocks acceptance. A reviewer supplies findings, not subject bytes ([`tests/lint/test_recruit_01_reviewer_supplied_code.py`](tests/lint/test_recruit_01_reviewer_supplied_code.py)).
   - Every disposition binds to an exact frozen object and is recorded as a structured receipt (`candidate_commit`, `candidate_tree`, `base_sha`, `subject_manifest_sha256`, and the other §4 fields). A disposition naming no exact object is not a disposition.
   - **§7 Base movement & §8 Merge-train carry-forward**: an acceptance survives a base advance or train assembly **only** when three recorded proofs hold: (1) **blob-hash identity** for every reviewed file, (2) **bidirectional import isolation**, and (3) the **complete diff** from the reviewed head to the updated or train head.
4. **Module 4 — Staged delegation, ingress, and evidence yield ([`04_staged_delegation_and_ingress.md`](docs/governance/recruit_01/04_staged_delegation_and_ingress.md))**:
   - Safety preflight first, then **substantive ingress in authority order**: (1) governing contracts, standards, sources and charters → (2) prior accepted implementation and the review chain → (3) predecessor findings and open residuals → (4) live code, configs, tests and evidence → (5) current external state.
   - Prior assistant, handover, memory, and worker statements are **claims to verify, never authority**.
   - Every worker outcome is `EVIDENCE_RETURNED`, `NO_FINDING_WITH_EVIDENCE`, `NO_EVIDENCE` (never treated as acceptance), or `BLOCKED_WITH_RECEIPT`.

---

## 5. AI-Specific Governance & Host Directives Across the Codebase

Every AI system interacting with this repository is bound to [`go_with_the_flow_rules_v3_0_clean.csv`](go_with_the_flow_rules_v3_0_clean.csv) and [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md). The host-specific notes below describe each host's surfaces. Anything they list that is not a CSV row, such as files under a host's home directory, is host-local guidance that this repository cannot verify. It is never a rule, and the CSV wins.

### 5.1 OpenAI Codex (`AGENTS.md`, `.codex/`, `~/.codex/`)
- **Repo Surfaces**: [`AGENTS.md`](AGENTS.md), [`.codex/config.toml`](.codex/config.toml), [`.codex/environments/environment.toml`](.codex/environments/environment.toml) (guarded by [`tests/lint/test_codex_project_guidance.py`](tests/lint/test_codex_project_guidance.py) and [`tests/lint/test_codex_local_environment.py`](tests/lint/test_codex_local_environment.py)).
- **Host-local surfaces** (outside the repository): Codex's global instructions, config, hooks, memories, skills and automations under `~/.codex/`.
- **Repository rules that apply**:
  - Every Codex thread is created from the `DutchBay_EPC_Model` project and binds to `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`).
  - Shared-venv verification (`scripts/verify_shared_venv_worktrees.py`) runs during a quiet window (`ENV-01`).

### 5.2 Anthropic Claude Code (`CLAUDE.md`, `.claude/`, `~/.claude/`)
- **Repo Surfaces**: [`CLAUDE.md`](CLAUDE.md), [`.claude/settings.json`](.claude/settings.json), [`.claude/hooks/session-start.sh`](.claude/hooks/session-start.sh), and [`.claude/skills/steward/SKILL.md`](.claude/skills/steward/SKILL.md).
- **Host-local surfaces** (outside the repository): Claude Code's global `~/.claude/` instructions, settings, hooks and memory on the owner's machine. Any operating directives kept there are host-local guidance, not GWTF rules.
- **Repository rules that apply**: local sessions follow `THREAD-01` and `ENV-01`; cloud sessions use the checkout-local `.venv` fallback that [`CLAUDE.md`](CLAUDE.md) provisions (§1).

### 5.3 Google Antigravity / Gemini (`~/.gemini/antigravity/`, `.agents/`)
- **Surfaces**: [`AGENTS.md`](AGENTS.md) (loaded as workspace rule), [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md), and host-local worktrees and conversation artifacts under `~/.gemini/antigravity/`.
- **Repository rules that apply**:
  - Start from [`docs/governance/agent_session_routing.md`](docs/governance/agent_session_routing.md) and [`AGENTS.md`](AGENTS.md).
  - Use dedicated worktrees under `WORKTREE-01` and the persistent `DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"` runtime with `PYTHONPATH="$PWD"` (`ENV-01`, `THREAD-01`).
  - Sub-agents that a session spawns for itself are not `RECRUIT-01` review lanes. Module 3 requires reviewers distinct from the writer and the coordinator, recruited per Module 1.

### 5.4 Moonshot Kimi (`docs/knowledge_base/`, `docs/PR1336_D1_DOMAIN_REVIEW_R1.md`, `~/.kimi-*`)
- **Surfaces**: [`docs/knowledge_base/06_finance_python_renewables_comparative_review.md`](docs/knowledge_base/06_finance_python_renewables_comparative_review.md) (§ *"Disposition of the KIMI Q4 2026 comparison"*), [`docs/PR1336_D1_DOMAIN_REVIEW_R1.md`](docs/PR1336_D1_DOMAIN_REVIEW_R1.md) (`KIMI-FALSE-BESS-GAP`), and host-local bridge directories under `~/.kimi-*`.
- **Repository rules that apply**:
  - External AI research reports (such as Kimi comparative reviews) are claims to verify, never primary sources or authority (`DATA-01`, `RECRUIT-01` Module 4).
  - False capability gap claims (such as `KIMI-FALSE-BESS-GAP`, which overlooked [`finance/bess_revenue.py`](finance/bess_revenue.py), [`finance/bess_lcos.py`](finance/bess_lcos.py), and [`finance/bess_project_economics.py`](finance/bess_project_economics.py)) must be verified against the live codebase before opening work items.

### 5.5 Perplexity, Grok & External Research LLMs (`legacy/dev_scripts/`, `docs/AGENTIC_DELIVERY_PRACTICE.md`)
- **Surfaces**: [`legacy/dev_scripts/AAA - instructions for make clean zip.md`](<legacy/dev_scripts/AAA - instructions for make clean zip.md>) (historical Perplexity snapshot workflow, now isolated under `legacy/`) and [`docs/AGENTIC_DELIVERY_PRACTICE.md`](docs/AGENTIC_DELIVERY_PRACTICE.md).
- **Repository rules that apply**:
  - Instructions in `legacy/` (including retired sprint integration branches like `feature/add-finance-contracts-pydantic-v2-20251219`) are retired historical artifacts and must never be restored (`R25`, [`tests/lint/test_gwtf_canonical_source.py`](tests/lint/test_gwtf_canonical_source.py)).
  - Any external LLM output (Perplexity, Grok, ChatGPT, etc.) is subject to `DATA-01` lossless capture, `TEST-01` independent-oracle checks, and `RECRUIT-01` Module 4's claims-to-verify rule.

### 5.6 GitHub Copilot, Dependabot, Renovate & GitHub Actions Bots (`scripts/ci/`)
- **Surfaces**: [`scripts/ci/check_pr_intake.py`](scripts/ci/check_pr_intake.py), [`scripts/ci/check_pr_receipts.py`](scripts/ci/check_pr_receipts.py), [`tests/lint/test_pr_intake_policy.py`](tests/lint/test_pr_intake_policy.py), and [`tests/lint/test_pr_receipts_policy.py`](tests/lint/test_pr_receipts_policy.py).
- **Repository rules that apply**:
  - `check_pr_receipts.py` exempts the bot set `{dependabot[bot], github-actions[bot], copilot[bot], renovate[bot]}` from the receipts table (`VERIFY-01`).
  - Under `INTAKE-01`, a bot PR is an intake event: `check_pr_intake.py` passes it only after a non-bot comment on [Issue #1353](https://github.com/arunakulat/dutchbay-epc-model/issues/1353), posted after the PR was created, names it. No follow-up modification or merge proceeds before that record.

---

## 6. Quick Pre-Commit & Pre-Push Verification Commands

Run the narrowest meaningful checks before each commit (`R21`), and broaden before pushing. `PY` is the environment chosen in §1: `"$DUTCHBAY_VENV/bin/python"` on the owner's machine, `.venv/bin/python` on a CI or container host.

```bash
# 1. Confirm branch is NOT main/master (GOV-02)
git branch --show-current
git status --short --branch

# 2. Validate canonical GWTF CSV & handover chain (PERSIST-01)
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$PY" dutchbay_bootstrap_rules.py
"$PY" scripts/list_session_handover_records.py

# 3. Run focused pytest, ruff & whitespace checks (R21, VERIFY-01)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" "$PY" -m pytest -p no:cacheprovider tests/lint/ -q
"$PY" -m ruff check <changed-paths>
"$PY" -m ruff format --check <changed-paths>
git diff --check
```
