# Blue Whale Post-Merge Audit & Clean-Up (`v15.18.0`) — Ingress Brief & Receipt

**Document Version:** `1.1.0`
**Date:** 2026-11-06 (amended 2026-11-07: §5 records that the `MERGE-01` suspension is lifted)
**Governing Authority:** GWTF Ruleset `v3.0` (`go_with_the_flow_rules_v3_0_clean.csv`), `RECRUIT-01` Modules 1–4, `PERSIST-01`, `ENV-01`, `THREAD-01`
**Base Commit:** `cc4d1b59a7d9554ae9c6919d74fff623f62aa045` (`origin/main`, `VERSION 15.18.0`)
**Worktree / Branch:** `/Users/aruna/.gemini/antigravity/worktrees/dutchbay-epc-model/add_ingress_file` (`add_ingress_file`)

---

## 1. Safety Preflight Receipts (`RECRUIT-01` Module 4 §2)

Every prospective worker must complete the safety preflight before substantive ingress or mutation.

| Preflight Item | Requirement | Command / Probe | Verified Value / Receipt | Status |
|---|---|---|---|---|
| Python Runtime | Python 3.12 (`ENV-01`, `THREAD-01`) | `$DUTCHBAY_VENV/bin/python -VV` | `Python 3.12.13 (main, Mar  3 2026, 12:39:30) [Clang 21.0.0]` | **PASS** |
| Environment Integrity | Governed persistent `.venv` | `DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh` | Status `PASS`, 315 locked distributions, schema `dutchbay.development_environment_receipt.v1` | **PASS** |
| Ruleset Canon | Canonical CSV (`23074328...`) | `dutchbay_bootstrap_rules.py` | 79 rules, all active, latest `v3.0`, SHA-256 `230743289f135338344cba0740061935af461325d6729f3d210db3f3aee2e7a4` (`eb14d836...` at 78 rules prior to `CLEANUP-01`) | **PASS** |
| Handover Continuity | Resolver lineage verification | `scripts/list_session_handover_records.py` | Lineage verified back to founding records; latest introduction is `docs/SESSION_HANDOVER_2026-10-22_AUDIT_GATE_CLEARED_ON_MERIT.md` (`86ca5732`) | **PASS** |
| Protected Branch | Protected `main` read-only | `git branch --show-current` | Working on dedicated worktree branch `add_ingress_file` | **PASS** |
| Merge Authority | `MERGE-01` standing authority | Standing merge authority check | **SUSPENDED** by project owner at 2026-11-05T20:15:19+05:30 (Checkpoint 9 in `blue_whale_merge_train_ledger.md`). Strictly non-merging. *As recorded on 2026-11-06. Lifted by the owner on 2026-11-07; see §5.* | **HELD** on 2026-11-06; **LIFTED** 2026-11-07 (§5) |

---

## 2. Substantive Ingress Synthesis (`RECRUIT-01` Module 4 §3)

### Tier 1: Governing Normative Contracts & Charters
- **Repository Governance**: `AGENTS.md`, `CLAUDE.md`, `.claude/skills/steward/SKILL.md`, `docs/governance/agent_session_routing.md`, and `docs/governance/recruit_01/01_capability_and_risk.md` through `04_staged_delegation_and_ingress.md`.
- **Methodology & Source Standards**:
  - PUCSL 2026 FiT methodology (Gazette 2479/36, `conf/blue_whale_pucsl_fit_2026.yaml`).
  - CC&CRMD Coastal Zone and Coastal Resource Management Plan 2024–2029 (Cabinet approval 12 Aug 2024), Table 6-1, segment 2 setback rules.
  - Met-mast 617725 export and wind-resource evaluation (`docs/source_materials/met_mast_617725_2025/`).

### Tier 2: Prior Implementation & Review Chain
All 7 Blue Whale PRs along with prerequisite CI PR `#1548` have landed on `main`:
1. `#1530` (`15.12.0`, `0b78f5aa`): Single-turbine 9.5 MW EN-206/10.5 on flagged placeholder site Lot 5B.
2. `#1548` (`15.12.0`, `c3f23f5c`): Prerequisite CI `[solar]` extra in GitHub Actions test suite workflow.
3. `#1531` (`15.13.0`, `5a59ca01`): Blue Whale solar + BESS unit, dispatched hourly.
4. `#1532` (`15.14.0`, `99b75487`): Monte Carlo PV + BESS unit sizing and pricing.
5. `#1537` (`15.15.0`, `4e4b2ae6`): Two-project split under PUCSL 2026 FiT rules.
6. `#1538` (`15.16.0`, `a0fa3c9c`): Met mast 617725 transfer and yield re-derivation.
7. `#1540` (`15.17.0`, `9922363f`): Capex blending with China FOB + solar resource report.
8. `#1541` (`15.18.0`, `cc4d1b59`): 5 MW / 20 MWh solar + BESS commitment, after-tax NPV ranking.

- **Independent Review**: Every PR was independently reviewed and accepted by dedicated read-only R3 Domain and R3 Assurance subagents prior to ready-suite execution.
- **Owner KPI Sign-off**: Owner decision card `cmsg_01NZBxgCsuANZNkiqqCY1a9FUtcMyBiLppgPwkXDFZJqzd` (`2026-11-02T02:50:17Z`).

### Tier 3: Predecessor Findings & Open Residuals
- Standing merge authority suspended at Checkpoint 9. *(Residual as of 2026-11-06. Closed on 2026-11-07, when the owner lifted the suspension; see §5.)*
- Capability tracker `#1353` reconciled on 2026-11-06 06:50 Asia/Colombo (comment `6674071397`): 98 open issues, 13 open PRs (8 draft, 5 ready).
- Local branch `fix/blue-whale-audit-cleanup` carries commit `cc0fa69a` addressing initial audit findings.

### Tier 4: Live Implementation & Tests
- **Configs**: `conf/blue_whale_*.yaml` (strict v14 schema configs).
- **CLIs**: `scripts/run_blue_whale_*_v14.py`.
- **Scenarios**: `scenarios/blue_whale_*_lot5b_2026.yaml`.
- **Tests**: `tests/finance/test_blue_whale_scenario_kpis.py`, `tests/solar/test_blue_whale_site_inputs.py`, `tests/wind/test_blue_whale_wind_siting.py`.

### Tier 5: Current External State
- `origin/main` at `cc4d1b59a7d9554ae9c6919d74fff623f62aa045`.
- Full CI test shards, Coverage Gate, and Grid Study passed at merge commit.

---

## 3. Substantive Audit Findings & Traps (REMEDIATED)

### Finding 1: Cross-Platform Precision Variance in GeoJSON Validation (REMEDIATED)
- **Symptom**: `tests/wind/test_blue_whale_wind_siting.py::test_run_on_a_synthetic_curve` fails on macOS with `assert out["lot"]["site_geojson_matches_committed"] is True`.
- **Root Cause**: `scripts/run_blue_whale_wind_siting_v14.py` checked `json.loads(committed.read_text()) == site_doc`.
  On macOS Apple Silicon (Accelerate BLAS / libc), total-least-squares line fitting computes:
  - `west_edge_bearing_deg`: `28.11988655194687`
  - Committed on Linux runner: `28.119886551949254`
  The $2.38 \times 10^{-12}$ difference invalidated exact float equality in GeoJSON feature properties.
- **Remediation**: Replaced exact dict equality in `scripts/run_blue_whale_wind_siting_v14.py` with `_json_matches(..., abs_tol=1e-9)` and added `test_json_matches_tolerates_ulps_and_rejects_drift` in `tests/wind/test_blue_whale_wind_siting.py`.

### Finding 2: CLI Hygiene and Metadata Standards (`MRM-02`, `CLI-01`, `CLI-03`) (REMEDIATED)
- `scripts/run_blue_whale_capex_solar_resource_v14.py`:
  - Pinned `@hydra.main(version_base="1.3")`.
  - Suppressed routine logging output on stdout (`logging.disable(logging.WARNING)`).
  - Replaced runtime `assert isinstance(container, dict)` with explicit `TypeError`.
  - Added `schema`, `model_version` (`"15.18.0"`), `config`, and `scenario` metadata to `docs/blue_whale/capex_blend_summary.json` and `docs/blue_whale/solar_resource_summary.json`, guarded in `tests/solar/test_blue_whale_site_inputs.py`.
- `docs/blue_whale/met_mast_transfer_summary.json` and `docs/blue_whale/met_mast_wind_rose_130m.csv`: refreshed stale `model_version` (`15.16.0` -> `15.18.0`) so `tests/wind/test_met_mast_transfer.py::test_rerun_reproduces_the_committed_summary` passes when re-run against the private mast, NASA POWER, and confidential curve inputs.
- `analytics/gis/pv_array_layout.py` and `solar_resource/pv_bess_dispatch.py`: replaced bare runtime `assert` statements with explicit `ValueError` exceptions.

### Finding 3: Documentation Sync (REMEDIATED)
- `docs/blue_whale/INPUTS_REQUIRED.md`: Updated item F03 superseded hybrid tariff blend from `24.786` to `24.97218`.
- `tests/finance/test_blue_whale_scenario_kpis.py`: Updated module docstring reference from `(v0.6, model 15.14.0)` to `(v0.8, model 15.18.0)`.
- `docs/blue_whale/STATUS.md`: Added historical reference banners for intermediate iterations (PR 3 & PR 4).


---

## 4. Complete Repository & Host-Global Governance Ingress Matrix (`2026-11-06`)

### 4.1 Canonical GWTF Ruleset (`go_with_the_flow_rules_v3_0_clean.csv`)
- **Verified Count & Digest**: **79 active rules** (`79 rules; versions: v3.0; latest = v3.0; active=79`), SHA-256 `230743289f135338344cba0740061935af461325d6729f3d210db3f3aee2e7a4` (updated from 78 active rules / `eb14d836513fef208b59029c35bf6add826aa0c24dd764bb8a62f3a3acfee560` with owner-directed `CLEANUP-01`).
- **Complete Rule Family Synthesis** (rule-ID attributions corrected against the CSV on 2026-11-07 after the retrospective #1549 domain review; the CSV wins):
  - **Governance & Intake (`GOV-01`, `GOV-02`, `INTAKE-01`)**:
    - `GOV-01`: AI-assisted development contract (AI tools are bound by the ruleset and meet the same standards as human-written code; the owner's release, grade, lender, and Board authority boundaries are stated in `MERGE-01`, `REVIEW-01`, `TRAIN-01` and `RECRUIT-01`).
    - `GOV-02`: Never commit or push directly to `main`/`master`; verify `git branch --show-current` before every commit.
    - `INTAKE-01`: Before any edit or PR opening, fetch `origin/main`, inspect live capability tracker (`#1353`), enumerate all open PRs, record a scoped item in `#1353` or a linked focused issue **predating** the PR, and include work-item link, base SHA, and overlap disposition in the PR body (enforced by `scripts/ci/check_pr_intake.py` inside `Verification receipts (VERIFY-01)`).
  - **Architecture & Contracts (`ARCH-01..04`)**:
    - `ARCH-01`: Config-first design (`YAML`/`JSON`); no hard-coded business constants or hidden switches.
    - `ARCH-02`: `finance/irr.py` is the sole canonical implementation of `irr()`, `npv()`, and `xirr()`.
    - `ARCH-03`: Tranche-aware debt result surface (explicit tranche-level and aggregate debt sizing/schedule outputs without conflating senior, subordinated, or DFI tranches).
    - `ARCH-04`: Contract gateway pattern for analytics evaluation — all analytics outputs use canonical dataclasses in `analytics.contracts_v14` (`ScenarioResult`, `SensitivityResult`, `MonteCarloResult`, `CasperPayload`) and route evaluation exclusively through `analytics.evaluation_v14.evaluate_with_overrides()`, keeping optional dependencies import-safe via call-time `_require_*()` guards (`FRAMEWORK-01` / `CASPER`, except `DBPL-01` print core, which fails loud with `DbplDependencyError`).
  - **Canonical Framework Acronyms (`FRAMEWORK-01..03`)** (enforced by `tests/lint/test_framework_expansions_match_csv.py`):
    - `FRAMEWORK-01` (**CASPER**):
      - **Primary**: *Clear API Surfaces with Predictable Error Responses* (call-time `_require_*()` guards, explicit errors, clean documented contracts).
      - **Secondary**: *Contract-Assured Scenario Pipeline for Energy & Renewables*.
      - **MC Integration (`docs/CASPER_MC_INTEGRATION.md`, `#637`, `#639`)**: `build_casper_payload()` auto-wires top-level `mc_risk` (`{"lender_risk_table": [...], "covenant": {...}}`) into `casper_result_v1` via `build_casper_risk_blocks()` and `CovenantSpec`, resolving `dscr_floor` config-first via `analytics.mc.covenant.resolve_min_dscr_covenant` (`constraints.min_dscr_covenant` → `Financing_Terms.target_dscr` → `Financing_Terms.min_dscr` → `monte_carlo.min_dscr_covenant` → `1.30`) and degrading gracefully to `None` when MC is absent, summary-only, or `pandas` is missing.
    - `FRAMEWORK-02` (**CESSPIT**):
      - **Primary**: *Config Explicit, Schema Strict, Pre-flight Integrity Tests* (`validate_config_for_v14` strict by default; no `strict=False` weakening; no silent FX/tax/debt defaults).
      - **Secondary**: *Config-Enforced Schema Safety Pipeline Integration Triad*.
    - `FRAMEWORK-03` (**CCCDIR**):
      - **Primary**: *Contracts Centralized, Compliance Documented, Import Relationships explicit* (`analytics.contracts_v14` + `evaluate_with_overrides()` gateway only).
      - **Secondary**: *Config-Centric Contract-Driven Integration Rules*.
  - **CLI & Tooling (`CLI-01..03`, `R1..R9`, `ADD-01..03`, `R26`)**:
    - `CLI-01`: Hydra (`hydra-core`) is the CLI framework for all v14 CLIs; `argparse` is banned repo-wide (also `R3`) and legacy Typer/Click CLIs are frozen (Typer: `R4`).
    - `CLI-02` / `R1`: Canonical v14 entrypoints (`run_full_pipeline_v14.py`, `run_scenario_analytics_v14.py`); `R2`: config-first CLIs via Hydra overrides.
    - `CLI-03`: JSON-first output on stdout (a single JSON object summarising the run).
    - `R26`: Convert PDFs via local MarkItDown in `$DUTCHBAY_VENV` before parsing; never infer from raw PDF bytes.
  - **Validation, Typing, Testing, Finance & Presentation (`VAL-01..02`, `CST-01`, `TYPE-01`, `TEST-01..05`, `FIN-01..02`, `MRM-01..02`, `DOC-01..02`, `DBPL-01`)**:
    - `VAL-01`: Strict v14 schema validation (`validate_config_for_v14`); `VAL-02`: ScenarioAnalytics batch behaviour; `CST-01`: LibCST import and hot-spot API guardrails; `FIN-02`: explicit units in field names (`*_pct`, `*_years`, `*_usd`, `*_lkr`).
    - `TEST-01`: Independent-oracle requirement — finance-material code must answer to an oracle that did not originate in the same change (pre-existing test, external benchmark, closed-form identity, independent implementation, or invariant), and any pinned constant must be paired with a responsiveness guard.
    - `TEST-02` / `R8`: Coverage thresholds apply to the full suite (the gate is `coverage report --fail-under=95` in `.github/workflows/test-suite.yml`); `TEST-05`: independent GitHub-hosted Grid Study evidence for QSTS execution claims.
    - `FIN-01`: Numeric robustness and IRR/NPV safety; `MRM-01`: explicit seed for stochastic runs; `MRM-02`: scenario name, config path or hash, and model version on exported artefacts; `DOC-02`: VERSION and CHANGELOG update for any change that can affect IRR, DSCR, NPV or covenant logic.
    - `DBPL-01`: DutchBay Presentation Layer PDFs must route through `app.reports.dbpl.print_core.render_dbpl_pdf` with the complete `[report]` extra (`weasyprint`, `reportlab`, `geopandas`, `contextily`), fail loud via `DbplDependencyError`, keep all design tokens in `app/reports/dbpl/style.py`, keep running header/footer/caveat band un-suppressible, and surface font substitutions (`docs/dbpl_styleguide.md`).
  - **Git Workflow, Delivery, Persistence, Environment, Recruitment & Security (`R10..R25`, `DELIVERY-01`, `REFACTOR-01..04`, `WORKTREE-01`, `DATA-01`, `PERSIST-01`, `ENV-01`, `THREAD-01`, `VERIFY-01`, `MERGE-01`, `RECRUIT-01`, `SECDEP-01`, `REVIEW-01`, `TRAIN-01`, `CLEANUP-01`)**:
    - `R18`: Eleven sanctioned Conventional Commit types (`build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`); `deploy` is unsanctioned.
    - `R21`: Run the narrowest meaningful check before each commit, and the full suite before pushing.
    - `DELIVERY-01` & `REFACTOR-01..04`: Dolphin Strategy — one small, complete, independently reversible change per branch/PR (`MOVE -> SHIM -> UPDATE -> DEPRECATE`).
    - `WORKTREE-01`: One dedicated git worktree and branch per concurrent writing agent; never use `git stash` across worktrees.
    - `DATA-01`: Lossless source ingestion — capture every source datum, cell, unit, caveat, and provenance; keep raw values alongside interpretation; verify `MANIFEST.sha256` (`tests/lint/test_nso_corpus_manifest_integrity.py`).
    - `PERSIST-01`: Checkpoint durable state early and often to survive session interruptions; maintain the linear handover chain verified by `scripts/list_session_handover_records.py`.
    - `ENV-01` & `THREAD-01`: Root repository work at the active checkout/worktree with `PYTHONPATH="$PWD"` first, bound to the persistent governed Python 3.12 environment `DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"` (`./check_venv.sh`); shared-venv governance edits require `scripts/verify_shared_venv_worktrees.py` across two clean worktrees during a quiet window.
    - `VERIFY-01`: "A claimed check without a receipt is not a check" — enforced by required CI check `Verification receipts (VERIFY-01)`.
    - `MERGE-01`: Standing authorization to merge when all required checks are green on the exact current HEAD (delivery authority only; suspended by owner at Checkpoint 9 on `2026-11-05T20:15:19+05:30` unless explicitly authorized per PR, as recorded on 2026-11-06. **The suspension was lifted on 2026-11-07; see §5. `MERGE-01` is in force as written in the CSV.**)
    - `SECDEP-01`: Every suppressed `pip-audit` advisory in `PIP_AUDIT_IGNORES` must declare exact package pin, forcing cap, lifting release, and runtime defensibility (`tests/lint/test_pip_audit_allowlist.py`).
    - `REVIEW-01`: Open PR as draft first (fast gates only; shards, Coverage Gate, and Grid Study defer and report `Test Summary (draft: full suite deferred)`), freeze HEAD, post `Evidence pack` comment, bind required review lanes (`R1` = 1 lane; `R2`/`R3` = Domain + Assurance pair) to the draft HEAD, then mark ready for review so the full suite runs once.
    - `TRAIN-01`: Merge coordinator may combine 2–3 path-disjoint, import-isolated reviewed draft PRs ("cars", at most one `R3`/KPI-changing) onto `train/<date>-<n>` so they share one full-suite run and land by **rebase-merge** (never squash) with Module 3 §8 carry-forward proofs and pre/post-landing checks.
    - `CLEANUP-01`: Post-merge tracker notification (`#1353` & tasklist), completed focused GitHub issue closure, primary `main` synchronization, merged worktree and branch removal/pruning (`git worktree remove`, `git worktree prune`, `git branch -d`, `git push origin --delete`), and cleanup of any non-protected venvs while strictly preserving `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`THREAD-01`, `ENV-01`).

### 4.2 `RECRUIT-01` Canonical Modules (`docs/governance/recruit_01/01..04.md`)
1. **Module 1 (`01_capability_and_risk.md`)**:
   - Capabilities `C1`–`C7` and semantic risk classes `R0` (no repo mutation), `R1` (low-risk bounded), `R2` (standard code/config/tests), `R3` (finance/KPI/contract/grid/governance/corpus-handling material).
   - **§3.1 Three Bounded `R1` Single-Lane Classes**: (1) presentation-only code with no effect on any computed value, input, output file, API contract, or report figure; (2) test-only guard tightening that adds or tightens a guard without changing any oracle's expected value, tolerance, or fixture data and without removing, skipping, or weakening an assertion; and (3) record corrections that fix a dated record's receipts or citations without changing any disposition, authority, finding state, or carried-forward instruction. Everything else requires the 2-lane Domain + Assurance review pair.
2. **Module 2 (`02_writer_lease_and_recovery.md`)**:
   - One sole-writer coordinator per worktree/branch (`GRANTED -> ACTIVE -> CHECKPOINTED -> COMPLETED`).
   - Any session interruption, timeout, crash, or rate-limit **revokes** lease continuity (`INTERRUPTED -> REVOKED`); successor must run full `ENV-01`/`WORKTREE-01` recovery before writing. Subagents never commit (`D-1`).
3. **Module 3 (`03_independent_review_and_attestation.md`)**:
   - Reviewers are strictly read-only (`EnableWriteTools=false`) and bind dispositions (`ACCEPT`, `CONDITIONAL_ACCEPT`, `REJECT`, `HOLD`) to exact `subject_head_sha`, `subject_tree_sha`, and `base_sha`.
   - **§8 Base Fast-Forward Carry-Forward Carve-Out**: A review disposition survives a base move (or merge-train stacking) **only** if three proofs are recorded: (1) blob-hash identity (`git rev-parse <sha>:<path>`) for every reviewed file, (2) bidirectional import isolation between the candidate and intervening commits, and (3) the complete reviewed-to-updated diff. Any change to the candidate's own files restarts review.
4. **Module 4 (`04_staged_delegation_and_ingress.md`)**:
   - Mandatory **5-Tier Worker Ingress Order**: Tier 1 (normative contracts/charters) → Tier 2 (accepted implementation & review chain) → Tier 3 (open residuals/predecessor findings) → Tier 4 (live code, configs, tests) → Tier 5 (live external CI/PR/tracker state).
   - Prior assistant/handover/memory statements are claims to verify, never authority. Generation capacity must never outrun verification capacity.

### 4.3 Steward Skill (`.claude/skills/steward/SKILL.md`)
- Governs PR driving, base-currency maintenance, Grid Study path classification, `Evidence pack` formatting, `MERGE-01` boundary conditions, attribution vs GitHub login checks, and `TRAIN-01` merge-train assembly (`train/<date>-<n>`), rebase-merge landing, and post-merge verification.

### 4.4 Hidden Directories, Hooks, Skills, Agents & Global Memory Inventory
| Surface / Path | Purpose & Key Governance Findings |
|---|---|
| `.claude/settings.json` & `.claude/hooks/session-start.sh` | Repo-local Claude hook running `check_venv.sh`, `dutchbay_bootstrap_rules.py`, and `scripts/list_session_handover_records.py` at session start. |
| `.codex/config.toml` & `.codex/environments/environment.toml` | Repo-local Codex config (`project_root_markers = [".git"]`) and environment setup actions (`./check_venv.sh`, `pytest`). |
| `/Users/aruna/.codex/AGENTS.md`, `config.toml`, `hooks.json`, `hooks/session-root-check.sh` | Global Codex instructions, `gpt-5.4` model config, `SessionStart` hook enforcing repo-root CWD (`ENV-01`), and `DutchBay_EPC_Model` trust levels. |
| `/Users/aruna/.codex/memories/` | `raw_memories.md`, `memory_summary.md`, `MEMORY.md`, and `skills/dutchbay-shared-venv-quiet-window/SKILL.md` (enforces zero concurrent venv processes during `verify_shared_venv_worktrees.py`). |
| `/Users/aruna/.codex/skills/` & `automations/` | `chronicle/SKILL.md`, `.system/review-agent/SKILL.md`, and `continue-dutchbay-oldest-first-delivery/automation.toml` (scheduled oldest-first PR steward). |
| `/Users/aruna/.claude/CLAUDE.md`, `settings.json`, `hooks/session-root-check.sh` | Global Claude config `@import`-pinning `dutchbay_gwtf_ruleset_and_framework_acronyms.md` and `global_commit_and_delegation_directives.md` (`G1`–`G6` operating directives). |
| `/Users/aruna/.claude/projects/-Users-aruna-Downloads/memory/` | 40+ durable project & workflow memory notes (`MEMORY.md`, `engineering_workflow_lessons.md`, `agentic_delivery_practitioner_evidence.md`, `dutchbay_presentation_layer_dbpl.md`, `collect_all_data_points_on_ingestion.md`, etc.). |
| Session Subagents (`r3_domain_reviewer`, `r3_assurance_reviewer`) | Defined in this conversation via `define_subagent` with `EnableWriteTools=false`, matching `.agents/agents/r3_*_reviewer/agent.md`. |

### 4.5 Governance Drift & Errata Discovered (and Remediated)
1. **Stale GWTF Rule Counts in Global Claude Memory (REMEDIATED)**:
   - `/Users/aruna/.claude/projects/-Users-aruna-Downloads/memory/MEMORY.md` (line 4) and `dutchbay_gwtf_ruleset_and_framework_acronyms.md` (lines 18, 91) referenced `74 rules` / `77 rules` (`2026-10-26`, missing `TRAIN-01` and `CLEANUP-01`).
   - **Action Taken**: Updated both files with the dated `2026-11-06` count receipt of **79 active rules** (SHA-256 `230743289f135338344cba0740061935af461325d6729f3d210db3f3aee2e7a4`, documenting `TRAIN-01`, `CLEANUP-01`, and the Checkpoint 9 `MERGE-01` hold).
2. **Broken `@import` Paths in `/Users/aruna/.codex/AGENTS.md` (REMEDIATED)**:
   - Lines 5, 14, and 23 of `/Users/aruna/.codex/AGENTS.md` contained `@/Users/aruna/.Codex/projects/-Users-aruna-Downloads/memory/...`.
   - Repaired to point to the live directory `/Users/aruna/.claude/projects/-Users-aruna-Downloads/memory/...`.

---

## 5. Addendum (2026-11-07): `MERGE-01` suspension lifted

This addendum supersedes every statement above that the standing merge authority is suspended
(the §1 Merge Authority row, the §2 Tier 3 residual, and the `MERGE-01` entry in §4.1). Those
statements are kept as the receipts recorded on 2026-11-06. They do not describe the current
state.

- **What changed.** The project owner lifted the Checkpoint 9 suspension of `MERGE-01` on
  2026-11-07. `MERGE-01` is in force as written in `go_with_the_flow_rules_v3_0_clean.csv`
  (SHA-256 `230743289f135338344cba0740061935af461325d6729f3d210db3f3aee2e7a4`), where its status
  is `active`. No ruleset row changes.
- **Sources.** The owner's handback of coordinator and merge authority on 2026-11-07, quoted with
  times in [#1353 comment 6702383287](https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6702383287);
  the reconciling note in [#1353 comment 6702809373](https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6702809373);
  and the owner's request, in the project thread at 2026-11-07T05:26:34Z, that these references
  be corrected so that no agent reads `MERGE-01` as suspended. The work item for this addendum is
  [#1353 comment 6702818232](https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6702818232).
- **Who merges.** The project coordinator orders the queue and grants merge slots, and the
  merge-lease holder executes merges (#1353 comment 6702809373). Lifting the suspension does not
  let any other session merge.
- **What it does not change.** `MERGE-01` is delivery authority only. The lift waives no
  `REVIEW-01` lane, required check, `VERIFY-01` receipt or owner KPI sign-off, and it lifts no
  other HOLD: #1110, `v15.6.1` and F-5 remain, and so does the hold on merge trains until #1529's
  pull request (#1542) lands.
- **§4.5 item 1.** That item records an action taken on 2026-11-06: owner-side memory files were
  updated to document the Checkpoint 9 hold. It stays as a dated receipt. Those files are outside
  this repository; whether they still describe the hold as current is not verified here.
