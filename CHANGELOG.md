# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Changed
- **Coverage-hardening + `pipeline_v14` consolidation (#456, audit finding `QUAL-9`).**
  Added `solar_resource` to the coverage gate (`.coveragerc` source + the CI `--cov`
  flags + `make` `COV`); the floor still holds at ~97% (`solar_resource` measures 100%
  after marking its two physically-unreachable defensive guards `# pragma: no cover`).
  Resolved the half-retired `analytics/pipeline_v14.py` (a legacy wind-only pipeline
  excluded from coverage yet still imported): both of its script consumers
  (`scripts/export_to_excel.py`, `scripts/legacy_runners/run_complete_analysis_fixed.py`)
  were already reading the *enhanced* finance contract (`annual_rows`/`debt_result`/`kpis`),
  so they were folded onto the canonical `analytics/pipeline_v14_enhanced.py` and the
  legacy module + its base-specific strict-validation regression test were deleted.
  Removed the now-dangling `--cov=analytics.pipeline_v14` from `fx-tests.yml`, the stale
  `.coveragerc` omit entry, and the stale lint exemption. KPI-neutral (no `finance/` change).

### Security
- **Web-surface authentication + per-client job isolation (#449, audit finding
  `RPT-3`).** `/cases`, `/cases/report.{html,pdf}`, and all `/jobs*` routes now
  require a bearer token (`get_current_subject`); each `JobRecord` is bound to its
  JWT subject, and a non-owner (or unknown id) gets a non-leaking 404 on both the
  record and its SSE event stream. Tokens are stdlib-only **HMAC-SHA256 JWTs** with
  **PBKDF2-SHA256** password hashing (`app/api/auth.py`) — no new dependency, so the
  pinned `requirements.txt` and the `pip-audit` gate are untouched. Config is
  fail-closed: `DUTCHBAY_JWT_SECRET` (required; a missing secret is a 500, never a
  default) and `DUTCHBAY_API_USERS`. `POST /token` accepts a JSON body (not an
  OAuth2 form) to avoid pulling in `python-multipart`. Out of scope (noted
  follow-ups): the lower-level `/run-pipeline` and the mounted `/sensitivity` app
  remain unguarded; username-enumeration timing is not hardened.

## v15.0.0 - 2026-06-29

Consolidates all work merged since the v14.15.0 tag (the prior `[Unreleased]` range
"#220–#264" was stale — this also includes the audit-remediation cluster #439–#445).
Grouped by theme; see `git log` / `gh pr view <n>` for per-PR detail.

### Engineering & audit remediation (2026-06)
- Coverage-gate honesty (#439): retired `pytest.ini` / `pytest.ci.ini` / `tox.ini`;
  `pyproject.toml` is now the single pytest config and `.coveragerc` the single
  coverage config; `--cov-fail-under=95` is enforced in CI and `make test`.
- Documentation honesty (#440, #441, #442, #444, #445): corrected the stale
  coverage / package-count / test-count figures in `ARCHITECTURE.md`; documented
  `contracts_v14` as frozen dataclasses (not "Pydantic V2"); removed
  "skeleton/placeholder" wording from the live MC sampler/correlation and the DSCR
  sensitivity module; stripped migration-narration comments from the engine imports;
  annotated the pipeline-sequence diagram's load-time-only guards.

### Wind resource & bankable AEP
- **Bankable AEP engine** (#220): IEC 61400-12-1 air-density correction, PyWake
  Bastankhah–Porté-Agel granular wake (TurbOPark cross-check), IEC 61400-15-2 P50/P75/P90
  uncertainty build-up. Adopted **15 × IEA-10MW** as the canonical lender case (#221, #223).
- **ARCO single-point ERA5 → fitted Weibull** wiring in VALIDATE mode (#224); config-driven
  ERA5-fitted Kalpitiya 160 m scenario (#234).
- **Canonical Weibull re-baseline** to the ERA5-fitted shape (k 2.1→2.665), net AEP
  483.6→473.8 GWh (#237). Configurable P50 bankability haircut + correlation-aware
  uncertainty (#244); IEC 61400-15-1 vs -2 doc clarification (#245).

### FX & currency
- **Corrected the hardcoded USD/LKR 300→333.79** and added a config-driven FX routine
  (`analytics/fx/fx_fetch.py`, FIXED/LATEST/VALIDATE) with a no-magic-FX lint guard (#236).
- Currency numéraire settled as **LKR-primary by design** (soft lock documented; #264).

### Global reusability (ARCH-01 hardening)
- Removed DutchBay/Kalpitiya site & turbine defaults from `WindPipeline`,
  `ERA5RequestConfig`, the AEP tornado/MC engines and GIS export — identity is now
  config-required, enforced by lint (#225–#231). Added the **WORKTREE-01** governance rule
  (worktree-per-concurrent-agent) and a gis_export fence scan (#232).

### Cost engine (AACE / LandBOSSE roadmap)
- Single cost-basis-year anchor (#246), QRA-driven contingency per AACE RP 119R-21 (#247),
  canonical bottom-up cost WBS + IRENA $/kW sanity banner (#248), probabilistic CAPEX
  Monte Carlo → P-level economics (#249), AACE estimate-class attribute + LandBOSSE
  balance-of-plant WBS split (#260). Granular bottom-up CAPEX/OPEX + OPEX escalation (#241).

### Finance & debt
- Bankable **P90 downside case can bind debt sizing** (#259); **DSRA funded at financial
  close** + a Sources-and-Uses statement (#261); config-/data-driven refinancing coupon
  (#230).

### Governance, API & correctness
- Auditable **run manifest** (config sha256 + engine version + git sha) stamped on pipeline
  and API outputs (#256). Config-driven IEC 61400-15-2 loss taxonomy that fails loud on
  unknown loss keys (#254). `POST /run-pipeline` full-report endpoint (#243). Fixed an
  `analytics.wind ↔ monte_carlo_aep` circular import (#233).

### Scenarios
- New config-driven **Mullikulam 2×50MW (Mannar)** scenario (#235); Kalpitiya lender case
  at a 5 US-cent/kWh fixed-LKR tariff (#240); scenario config hygiene + sibling re-baseline
  (#239); **honest Mullikulam Lot-1 re-baseline** correcting a 3×-inflated capacity_mw and a
  stale opex, plus capex-breakdown reconciliation (#263).

### Architecture & repo hygiene
- Removed dead revenue modules (#238), expired Sprint-18 compat shims (#257), the
  `_quarantine` test tier + parked-tests workflow (#258), and untracked generated artifacts
  (#253). Refreshed stale `pyproject` package metadata; version-agnostic `RELEASING.md`.

### CI & dependencies
- Parallelised the suite with `pytest-xdist -n auto` (#250); 3.12-only on PRs with the full
  3.11+3.12 matrix on merge/nightly (#251); consolidated redundant workflows off the PR
  critical path (#252). Curated security/maintenance pip bumps (#262).

## v14.15.0 - 2026-05-27

### Sprint 19 — Wind→Finance Integration Bridge

This release closes the long-standing gap between the `wind_resource`
package (ERA5 ingestion, Weibull fit, Wake/Pcurve modelling, P50/P75/P90
computation) and the `run_full_pipeline_v14` finance CLI. Prior to
v14.15.0, the wind capability existed in the repo but was not packaged,
not wired, and not testable end-to-end; the v14 pipeline docstring
over-claimed integration that did not exist. This release introduces a
pure-function adapter and an opt-in CLI wiring so frozen wind exports
flow into the lender-grade cashflow model with deterministic,
auditable provenance — and zero behaviour change for callers who do
not opt in.

#### Added
- **`wind_resource/cashflow_adapter.py`** (+394 LOC) — pure function
  `wind_export_to_scenario_patch()` that consumes a frozen
  `WindPipeline.export_for_cashflow_model()` payload and returns a
  patched v14 scenario dict. Highlights:
  - Pydantic `WindCashflowExport` model enforces the 11-key producer
    contract (`scenario`, `annual_generation_mwh`,
    `capacity_factor_percent`, `revenue_annual_usd`,
    `revenue_cumulative_usd`, `project_capacity_mw`, `num_turbines`,
    `rated_capacity_per_turbine_kw`, `ppa_years`, `tariff_lkr_per_kwh`,
    `exchange_rate_lkr_usd`) with `extra="allow", frozen=True` for
    forward compatibility.
  - Three merge modes selectable per-run: `overwrite` (wind wins),
    `fill_if_absent` (default — wind fills only missing/zero slots and
    validates drift on populated ones), and `validate_only` (no writes
    to economic fields; provenance metadata still recorded).
  - Symmetric relative drift detection `100 * |a-b| / max(|a|,|b|)`
    (zero-safe). Default tolerance ±0.5%. Drift breaches raise
    `WindAdapterDriftError` with structured fields (`field`,
    `wind_value`, `scenario_value`, `drift_pct`, `tolerance_pct`,
    `mode`).
  - Normalisation: producer emits capacity factor as percent (e.g.
    42.8); adapter converts to decimal (0.428) before writing to the
    canonical `project.capacity_factor` slot (priority-2 in the v14
    cashflow resolution order — lower slots would have silently
    shadowed the wind value).
  - Provenance metadata written under `wind_resource.*` in the
    patched scenario in **all** modes (including `validate_only`).
  - **Leaf module** — does NOT import `cdsapi`/`xarray`/`netcdf4`, so
    consumers (notably `run_full_pipeline_v14`) can import it without
    the `[wind]` extra installed.
- **`tests/wind/test_cashflow_adapter.py`** (+32 tests, all green) —
  30 contract tests covering the 11-key validation surface,
  PERCENT→DECIMAL conversion, all three merge modes, drift
  computation edge cases, and provenance metadata; plus 2 round-trip
  integration tests gated by `pytest.importorskip('numpy_financial')`
  that drive a synthetic export through the full v14 cashflow path
  and assert IRR/NPV/DSCR stability within ±0.5%.
- **`pyproject.toml [project.optional-dependencies] wind`** — declares
  `cdsapi>=0.6`, `xarray>=2023.6`, `netcdf4>=1.6` as the `[wind]`
  extra. Wind producer (`scripts/run_wind_analysis_v14.py`) needs
  this; the finance consumer does not (unless
  `wind_auto_orchestrate=true` — see below).
- **`pyproject.toml [tool.setuptools.packages.find]`** — added
  `wind_resource*` to the include list. Prior to this release the
  wind package would not have shipped in a wheel build.
- **`run_full_pipeline_v14.py` — five new Hydra parameters** (all
  optional, all OFF by default):
  - `wind_assessment_json`: Path to a frozen wind export. When set,
    the finance run consumes this export via the adapter.
  - `wind_auto_orchestrate`: If `true` AND `wind_assessment_json` is
    null, subprocess the wind producer to mint a fresh export before
    the finance run. Requires the `[wind]` extra. Default `false` —
    lender-grade runs should consume an audited frozen export.
  - `adapter_mode`: `overwrite` | `fill_if_absent` | `validate_only`.
    Default `fill_if_absent`.
  - `wind_tolerance_pct`: Drift tolerance (percent). Default `0.5`.
  - `wind_export_scenario`: P-level selector (`P50` | `P75` | `P90`).
    Default `P75`.
  - When wind ingestion is active, the original scenario YAML is
    **never mutated** — a temp `.patched.yaml` is written alongside
    the original (so relative paths still resolve), the pipeline
    reads from that, and a `finally`-block cleans it up on every
    exit path. Structured `status="error"` JSON is emitted on any of
    four failure modes: missing export file, `[wind]` extra not
    installed in auto-orchestrate, producer subprocess failure, or
    adapter drift breach.

#### Changed
- **`run_full_pipeline_v14.py` docstring** — rewritten to match the
  implementation. Pre-Sprint-19 docstring claimed wind-resource
  integration that did not exist (Sprint 19 defect W4). Now
  documents the OFF-by-default contract, the two-CLI topology
  (producer vs. consumer), the three adapter modes, the structured
  error JSON shape, and all five Hydra params with their defaults
  and semantics. Module version header bumped 2.2.2 → 2.3.0.
- **`scripts/legacy_runners/run_wind_analysis_v14.py` →
  `scripts/run_wind_analysis_v14.py`** (`git mv`). The wind
  producer had been parked in `legacy_runners/` despite being the
  canonical wind CLI. Hydra `config_path="conf"` was also broken
  in the legacy location — it resolved to a non-existent
  `scripts/legacy_runners/conf/`. Promotion + `config_path="../conf"`
  fixes both issues. `scripts/legacy_runners/README.md` added to
  document the (now correctly populated) deprecated-runners folder.

#### Fixed
- **`pyproject.toml [project] version`**: stale `14.14.0` → `14.15.0`.
  pyproject was one patch behind `VERSION` on main pre-Sprint-19
  (14.14.0 vs. 14.14.1); this release re-aligns both files.
- **Wind producer Hydra config resolution** (latent bug uncovered
  during W.5 promotion): the producer at
  `scripts/legacy_runners/run_wind_analysis_v14.py` declared
  `config_path="conf"`, which Hydra resolved relative to the script
  file as `scripts/legacy_runners/conf/` — a directory that does not
  and never did exist. The promotion + `config_path="../conf"`
  correction makes the producer actually loadable.

#### Defects deferred
- **`enrich_tornado_with_tail_risk` / `build_tail_risk_snapshots_for_metrics`**
  signature compatibility (carried from Sprint 18D Defect #2): the
  symbol names referenced in `analytics/evaluation_v14.py:454-461`
  exist under a different identifier (`enrich_suite_with_tail_risk`
  in `analytics/sensitivity/tail_risk.py`); the production caller is
  `try/except ImportError`-guarded so the path is silently inactive.
  A signature-compat audit is scheduled for a follow-on sprint —
  out of scope for the Sprint 19 wind→finance bridge.

#### Commit ledger (this release)

| SHA      | Phase | Purpose                                                                |
| -------- | ----- | ---------------------------------------------------------------------- |
| 99913a5  | W.1   | pyproject: declare `[wind]` optional extra                             |
| da278ef  | W.2   | pyproject: include `wind_resource*` in setuptools package discovery    |
| e3250ab  | W.3   | NEW `wind_resource/cashflow_adapter.py` (394 LOC, pure function)       |
| a0ccbd0  | W.4   | NEW 32 adapter tests (contract + round-trip)                           |
| e79b9d1  | W.5   | promote `run_wind_analysis_v14.py` out of `legacy_runners`             |
| 4efe80d  | W.6   | wire wind ingestion into `run_full_pipeline_v14` (additive, OFF-default) |
| 5b8a718  | W.7   | docstring alignment with W.6 wiring                                    |
| _(this)_ | W.X   | VERSION 14.14.1 → 14.15.0, CHANGELOG, pyproject realignment            |

## v14.14.1 - 2026-05-26

### Sprint 18D — CASPER Contract Alignment (Patch)

#### Fixed
- **CASPER payload ↔ canonical EquityPerformance contract alignment**
  (`analytics/casper/casper_payload.py`, +31/-15). Sprint 18B rewrote
  `EquityPerformance` to expose only `equity_irr`, `equity_npv`,
  `equity_multiple` and `metadata`. The payload's
  `_scenario_summary_to_dict` was still reading the pre-Sprint-18B
  attribute surface (`ep.downside`, `.moic`, `.dpi`, `.rvpi`, `.tvpi`,
  `.average_coc`, `.payback_period_years`), which would raise
  `AttributeError` on every real CASPER run
  (`analytics/pipeline_v14_enhanced.py:535-585` populates
  `scenario.equity_performance` on every CASPER call). CI did not
  detect the bug because canonical CASPER test paths are 4-line stubs
  and the real tests sat in `tests/_quarantine/`. The fix:
  - reads legacy PE metrics (`moic`, `dpi`, `rvpi`, `tvpi`,
    `average_coc`, `payback_period_years`) from `ep.metadata` with
    `.get()` guards (graceful `None` for leaner producers);
  - adds the canonical `equity_multiple` field to the payload (net
    additive);
  - synthesises the `downside` dict from `MonteCarloResult` percentile
    fields (`project_irr_p10`, `project_npv_p10`, `dscr_min_p10`) when
    `monte_carlo` is provided, since `DownsideMetrics` is declared in
    `contracts_v14` but never attached to any `ScenarioResult`.
  - The `downside` dict's keys therefore change from
    `{prob_negative_npv, prob_below_hurdle, worst_case_irr, max_drawdown}`
    (no producer existed) to `{project_irr_p10, project_npv_p10,
    dscr_min_p10}`. Top-level payload keys are unchanged.
- **Re-instated `MultiTechGenerationResult`, `TechnologyBreakdown`, and
  `GenerationProfile` in `analytics/contracts_v14.py`** (+84 LOC). These
  three dataclasses were originally introduced in Sprint 9 (commit
  `260fc3b`) and consumed by `analytics/casper/casper_payload.py`. They
  were inadvertently deleted from `contracts_v14.py` during the Palette
  refactor (commit `979520b`, Feb 24 2026) while their import sites in
  `casper_payload.py:7-14` were left untouched. The defect was latent
  because no test imported `analytics.casper.casper_payload` at module
  level (canonical CASPER tests were stubs); Sprint 18D's revived
  contract-freeze test (D.5) exposed it at pytest collection.
  Consequences on main pre-fix:
  - `import analytics.casper.casper_payload` raised `ImportError:
    cannot import name 'MultiTechGenerationResult'`.
  - `analytics.casper.__init__` (which re-exports `build_casper_payload`)
    therefore also failed to import, breaking the entire `analytics.casper`
    package.
  - `analytics/casper/casper_v14.py:97` calls `build_casper_payload(...)`
    in the production tail-risk evaluation path — that path has been
    silently unreachable since Feb 24 2026.
  Restoration matches the original Sprint 9 surface exactly, adapted to
  the current `dataclass(frozen=True) + ContractMixin` style. Field
  surfaces precisely match the live consumer expectations in
  `_generation_to_dict` and `_technology_breakdown_to_list`.
  Naming note: `TechnologyBreakdown` is *intentionally distinct* from
  `finance.contracts.TechnologyBreakdown` which carries a different
  field surface (`capacity_mw`, `capex_usd`, `opex_annual_usd`) for a
  different consumer. The name collision is historical and documented
  inline in both modules.

#### Added
- **Eight regression tests pinning the bug class**
  (`tests/analytics/test_casper_payload_equity_contract.py`, +231 new):
  no-AttributeError guard, metadata surfacing, lean-metadata graceful
  `None`, `equity_multiple` presence, downside synthesis on/off, JSON
  round-trip, contract version pin.
- **Revived CASPER tail-risk smoke test from quarantine**
  (`tests/analytics_layer/test_evaluation_casper_tail_risk.py`, +196
  rewritten; `tests/analytics_layer/_casper_fakes.py`, +141 restored
  from commit `3f0297f`). Adapted to today's `TornadoResult` /
  `SensitivitySuite` contract surfaces and to the canonical
  `enrich_tornado_with_tail_risk` consumer.
- **Revived CASPER contract freeze test from quarantine**
  (`tests/api/test_casper_contract_freeze.py`, +94 rewritten). Pins
  payload contract-version string, contracts_v14 contract-version
  string, canonical `CasperResult` field set, and method-form contract
  version.

#### Changed
- Bumped project version 14.14.0 → **14.14.1** (bug-fix patch).
- CASPER JSON contract version unchanged at `casper_result_v1` (silent
  fix; payload structure realigned to documented surface).

#### Disclosures (pre-existing follow-ups; NOT introduced by this PR)
- **`MonteCarloResult.success_rate()` is called but not defined**
  (`analytics/casper/casper_payload.py:269`). The regression test
  exercises `_scenario_summary_to_dict` directly rather than
  `build_casper_payload` for the MC-present case to avoid coupling to
  this unrelated defect. Recorded as a follow-up.
- **`enrich_tornado_with_tail_risk` and
  `build_tail_risk_snapshots_for_metrics` are imported by
  `analytics/evaluation_v14.py:457-458` but do not exist on the shim or
  canonical `analytics.sensitivity.tail_risk` module**. In production
  this raises `ImportError`, which is silently swallowed; the
  `tail_risk_block` therefore stays `None` and `metadata["tail_risk"]`
  is never populated. The revived tail-risk smoke test injects both
  missing symbols via `monkeypatch.setattr(raising=False)` so the
  assembly path can be exercised. Recorded as a follow-up.
- **Two divergent `CASPER_CONTRACT_VERSION` constants**:
  `analytics.casper.casper_payload.CASPER_CONTRACT_VERSION =
  "casper_result_v1"` (emitted into every payload) vs
  `analytics.contracts_v14.CASPER_CONTRACT_VERSION = "v1.0"` (returned
  by `CasperResult.contract_version()`). These have silently disagreed
  since at least Sprint 14. The freeze test pins each in its own module
  so the drift cannot widen. Reconciliation is a follow-up.
- **`CasperResult.contract_version` is a no-args method, not an
  attribute** (likely refactor regression). Tests call it as a method.
  Follow-up.
- **Stale `tests/legacy_v14/README.md`** previously claimed an
  `IndentationError at line 71` in `analytics/casper/casper_payload.py`.
  That claim was inaccurate — the file parses cleanly via `ast.parse`.
  The README is corrected in this PR.
- **`analytics.casper.casper_payload` was unimportable on `main`**
  due to `from analytics.contracts_v14 import MultiTechGenerationResult,
  TechnologyBreakdown` referencing names deleted in the Palette refactor
  (`979520b`, Feb 24 2026). This was a latent production-blocker: the
  entire `analytics.casper` package failed to load, silently disabling
  the tail-risk evaluation path at `analytics/casper/casper_v14.py:97`.
  **Resolved in this PR (commit `92f514b`)** by re-instating the three
  missing contracts in `analytics/contracts_v14.py` (see Fixed section
  above). Discovered when the revived D.5 freeze test triggered pytest
  collection on the import chain.
- **`analytics.casper.kpi_normalizer` was unimportable on `main`** due to
  `NormalizedKPIs.capacity_mw` (non-default, declared with
  `field(repr=False)` which suppresses repr but does NOT supply a default)
  being declared *after* the defaulted `llcr_min: Optional[float] = None`.
  This violated Python's dataclass field-ordering rule and raised
  `TypeError: non-default argument 'capacity_mw' follows default argument`
  at class-creation time. Same Palette-era lineage as the
  `MultiTechGenerationResult` defect above — a module that no test or
  call site imported until Sprint 18D's revived freeze test triggered
  package-level loading. **Resolved in this PR (commit `0139469`)** by
  reordering the fields so `capacity_mw` precedes the two optional
  fields; `field(repr=False)` semantics preserved and `capacity_mw`
  remains required (smoke test verifies omitting it still raises
  TypeError — no silent default was introduced).
- **`MonteCarloResult.success_rate()` was called but not defined**
  (`analytics/casper/casper_payload.py:269` writes
  `"success_rate_pct": mc.success_rate()` into every CASPER JSON payload).
  Any payload that included Monte Carlo results raised `AttributeError`
  at runtime. **Resolved in this PR (commit `ba25a54`)** by adding the
  method to `MonteCarloResult` in `contracts_v14.py`. Computed from
  existing `iterations` and `failed_iterations` fields as
  `(iterations - failed_iterations) / iterations * 100`. Returns `0.0`
  when `iterations == 0` to avoid division-by-zero. Smoke verified for
  99.5% / zero-iter guard / all-failed / perfect-run cases.
- **Two divergent `CASPER_CONTRACT_VERSION` constants** existed:
  `analytics.contracts_v14.CASPER_CONTRACT_VERSION = "v1.0"` (internal
  Python constant) and
  `analytics.casper.casper_payload.CASPER_CONTRACT_VERSION = "casper_result_v1"`
  (customer-visible JSON payload key). Both were re-exported via package
  `__init__.py` files — consumers received different strings depending on
  import path. **Resolved in this PR (commit `ba25a54`)** by unifying
  the `contracts_v14` constant to `"casper_result_v1"` (the value already
  shipping in the JSON payload). The freeze test
  (`tests/api/test_casper_contract_freeze.py`) was updated to pin the
  unification rather than the prior drift: both constants MUST now be
  equal AND equal `"casper_result_v1"`. Companion test update
  (`tests/contracts/test_contracts_v14_import_surface.py:137`) committed
  separately as `d82a2f6`.
- **`CasperResult.contract_version` was a method, not an attribute.**
  Defined as `def contract_version(self) -> str`, this silently became
  a bound-method object whenever callers used attribute access
  (`result.contract_version` rather than `result.contract_version()`).
  Consequences: (a) any serializer using attribute access embedded a
  method-repr string into the output, (b) the sibling
  `RefinancingResult.contract_version` is a real string attribute, so
  the API was inconsistent within the same module, (c) the quarantined
  test already asserted attribute access and would have caught this
  immediately if not excluded from collection. **Resolved in this PR
  (commit `889381f`)** by converting to a class-level frozen attribute:
  `contract_version: str = field(default=CASPER_CONTRACT_VERSION, init=False)`.
  Properties (smoke-verified): attribute access returns string, not
  method; `init=False` rejects constructor override; frozen dataclass
  semantics preserved; `ContractMixin.model_dump()` includes it.
  Test assertions updated from method-call to attribute-access form.

#### Sprint 18D Provenance
- Branch cut from `b4a2498` (Sprint 18B merge on `main`).
- Thirteen surgical commits, all reversible:
  1. `4d65575` — D.2: payload fix
  2. `2ac6e06` — D.3: regression tests
  3. `7ca6d68` — D.4: tail-risk smoke test revived
  4. `a10f99d` — D.5: contract freeze test revived
  5. `f6def23` — D.6: legacy_v14 README corrected
  6. `4bbe31d` — D.X: VERSION bump 14.14.0 → 14.14.1 + initial CHANGELOG
  7. `92f514b` — D.X+2: re-instate MultiTechGenerationResult /
     TechnologyBreakdown / GenerationProfile (resolves 1st CI
     collection failure exposed by D.5)
  8. `25c4707` — docs: CHANGELOG records D.X+2
  9. `0139469` — D.X+3: reorder NormalizedKPIs fields so required
     `capacity_mw` precedes defaults (resolves 2nd CI collection
     failure exposed beneath D.X+2)
  10. `218555c` — docs: CHANGELOG records D.X+3
  11. `ba25a54` — D.X+4 + D.X+5: add MonteCarloResult.success_rate()
      and unify CASPER_CONTRACT_VERSION to `"casper_result_v1"`
      (Defects #1 and #3)
  12. `d82a2f6` — test adaptations for D.X+5 (freeze + import-surface)
  13. `889381f` — D.X+6: CasperResult.contract_version converted from
      method to class-level frozen attribute (Defect #4)
- Defect #2 (`enrich_tornado_with_tail_risk` /
  `build_tail_risk_snapshots_for_metrics` referenced by
  `analytics/evaluation_v14.py:457-458` but not exported by
  `analytics.sensitivity.tail_risk` under those names) deferred to
  Sprint 19 — the actual public name is `enrich_suite_with_tail_risk`
  and resolving the call sites requires signature-compatibility
  investigation that exceeds Sprint 18D's scope. The production call
  site is currently guarded by a `try/except ImportError` block that
  silently swallows the failure, so no runtime crash is exposed; the
  tail-risk enrichment is simply unreachable. Original disclosure
  text was imprecise ("not defined anywhere") and is corrected here.
- Investigation artefact retained as a workspace-only deliverable:
  `CASPER_INVESTIGATION_REPORT.md`.

#### Compliance
- GWTF: R23/R25 (feature branch + PR + CI), ARCH-04 (single canonical
  contract surface), TYPE-01 (mypy --strict clean), TEST-01
  (regression pins), DOC-02 (VERSION + CHANGELOG together), no edits
  on `main` until investigation was complete.

## v14.14.0 - 2026-05-26

### Sprint 18B — Equity Distribution Productionisation

#### Added
- **Equity distribution pipeline-ready API** (`finance/equity_distribution_v14_hydra.py`, +559/-87): Hydra/OmegaConf-driven config surface and pipeline-ready entry points.
- **Pipeline wiring** (`analytics/pipeline_v14_enhanced.py`, +68/-6): equity distribution integrated into the v14 enhanced pipeline.
- **CLI artifact exposure** (`run_full_pipeline_v14.py`, +26/-84): equity distribution result exposed through the full-pipeline CLI.
- **Production API re-exports** (`finance/equity/__init__.py`, +55/-32): canonical equity distribution surface re-exported.
- **Regression suite** (`tests/api/test_equity_distribution_pipeline_integration.py`, +98 new): equity distribution pipeline regression tests.
- **Runtime dependency:** `omegaconf` added to `pyproject.toml` (required by the Hydra-style config surface).

#### Changed
- **ARCH-04 alignment in `finance/equity_v14.py`** (+43/-232): `calculate_equity_performance` now returns the canonical `analytics.contracts_v14.EquityPerformance` (fields: `equity_irr`, `equity_npv`, `equity_multiple`, `metadata`). Auxiliary statistics (`moic`, `dpi`, `rvpi`, `tvpi`, `downside`, `average_coc`, `payback_period_years`) are now nested inside `metadata`. Import-safe fallback repaired. Private helper `_calculate_downside_proxy` removed (no external importers).
- **Equity compliance guard** (`tests/lint/test_equity_distribution_compliance.py`, +60/-80): narrowly relaxed to permit `__all__` metadata exports. No global-state policy changed.
- Bumped project version 14.13.0 → **14.14.0** (additive feature surface + ARCH-04 canonicalisation of `EquityPerformance` consumers).

#### Skipped (intentional)
- Sprint 18B commit `0bff333` ("derive debt timeline from tenor and CFADS") **superseded upstream**: main's PR #107 (`fde8dec`) achieves the same via a cleaner `_build_cfads_timeline()` helper extraction in `finance/debt_v14.py`. The feature branch's `finance/debt_v14.py` is byte-identical to main.

#### Disclosures
- **Pre-existing latent break — NOT introduced by this PR:** `analytics/casper/casper_payload.py` (lines 185-186) reads legacy `EquityPerformance` attributes (`.downside`, `.moic`, `.dpi`, `.rvpi`, `.tvpi`, `.average_coc`, `.payback_period_years`) that no longer exist on the canonical shape. The file is already broken on `main` (IndentationError at line 71, documented in `tests/legacy_v14/README.md`); CASPER tests are already quarantined. Follow-up issue to be filed for a separate sprint.
- **`EquityPerformance` shape change is a soft public-API shift** for any external caller reading `.moic/.dpi/.rvpi/.tvpi/.downside` top-level — those values now live under `metadata`. No in-repo callers affected.

#### Sprint 18B Provenance
- All 9 sprint-18b commits accounted for: **8 cherry-picked** (each with `-x` provenance recorded), **1 skipped** (subsumed upstream — see above).
- Net diff vs main: **+951 / -523 across 10 files** (8 code/test files + `VERSION`, `pyproject.toml`, `CHANGELOG.md`).
- Cherry-pick order (new → old SHA): `9aa3d1c←d725187`, `4220861←94bd03d`, `daf7501←995eea1`, `b82f023←bbd0c8d`, `1bba038←25f93e8`, `fc465b0←c37db4e`, `d98243f←55ce7eb`, `2bd40dc←ab6033c`.
- Read-only audit and disclosures retained as workspace-only artefacts (`SPRINT_18B_DOLPHIN_AUDIT.md`, `SPRINT_18B_DOLPHIN_DISCLOSURES.md`).

#### Compliance
- GWTF v3.0 R23/R25 (feature branch + PR + CI gate; zero direct-to-main commits — surgical cherry-picks only)
- ARCH-04 (single canonical contract surface in `contracts_v14` — equity_v14 now consumes canonical `EquityPerformance`)
- TYPE-01 (mypy --strict — verified via CI on Draft PR)
- TEST-01/R11 (9 canonical v14 tests green; new equity distribution regression suite added)
- FIN-01/02 (additive changes only; IRR/DSCR/NPV pins unchanged — sprint 18B is equity-distribution work, not core math)
- DOC-02 (this CHANGELOG entry + VERSION bump in same PR)
- MRM-02 (junit artefacts retained via standard CI)

## v14.13.0 - 2026-05-26

### Sprint 18C — ARCH-04 SensitivitySuite Unification

#### Added
- `SensitivitySuite` audit fields: `base_kpis`, `scenario_name`, `analysis_timestamp` (all optional, backward compatible)
- Parked-tests observability workflow (`.github/workflows/parked-tests-observability.yml`) — non-blocking junit-xml + html artefact pipeline for the test surface outside the canonical v14 nine; 30-day retention; runs on push/PR/manual/daily 07:00 UTC
- Pin test `test_sensitivity_suite_audit_fields_are_optional_and_serializable` in `tests/contracts/`

#### Changed
- Bumped project version from 14.12.2 → **14.13.0** (additive contract surface change)
- Aligned `pyproject.toml` version (was 14.0.1) with `VERSION` file

#### Removed
- **Phase 3 dead-code island** (1,423 lines): `analytics/contracts/_phase_3_sensitivity.py`, `analytics/contracts/_phase_3_sensitivity_loaders.py`, `analytics/contracts/_phase_3_visualization.py` — zero external importers; closed self-referential island
- **Definition C stubs** in `finance/contracts.py`: `SensitivitySuite` and `MultiMetricSensitivitySuite` (54 lines) — zero external importers
- Dead Phase 3 integration test `tests/integration/test_phase3_sensitivity_contracts.py` (419 lines, 24 funcs, 0% coverage)

#### Fixed
- `tests/_quarantine/test_sensitivity_v14_all.py` — imported `SensitivityRequest` from canonical `analytics.contracts_v14` (the `analytics.sensitivity_v14` shim does not re-export it)

#### Architecture (ARCH-04)
- **Three-way SensitivitySuite contention resolved.** The codebase now has a single canonical class at `analytics/contracts_v14.py:209`. Definitions B (`analytics/contracts/_phase_3_sensitivity.py`) and C (`finance/contracts.py`) deleted. Closes #52.
- Parked-tests observability drift inventory tracked in #115 (7 fronts catalogued).
- Sprint 18C follow-ups:
  - #117 — PR-10 follow-up: v14 SensitivityRunner end-to-end test
  - #118 — ARCH-04 follow-up: retire `analytics.contracts_v14_compat.MultiMetricSensitivitySuite` stub (Sprint 19 candidate)

#### Observability needle (parked-tests, pre→post)
| Metric | Main baseline | After PR #116 | Δ |
|---|---|---|---|
| Collected | 155 | 154 | −1 (Phase 3 test deleted) |
| Passed | 37 | 37 | 0 |
| Failed | 109 | 109 | 0 |
| Errors | 6 | 5 | −1 (TaxShockLibrary ImportError gone) |
| Skipped | 3 | 3 | 0 |
| `base_kpis` TypeError class | many | **0** | extinguished |
| `TaxShockLibrary` ImportError class | present | **0** | extinguished |
| `SensitivityRequest` ImportError class | masked | **0** | exposed & fixed |
| `_phase_3_sensitivity` references | present | **0** | extinguished |
| `finance.contracts.SensitivitySuite` references | present | **0** | extinguished |

#### Compliance
- GWTF v3.0 R23/R25 (feature branch + PR + CI gate; zero direct-to-main commits)
- ARCH-04 (single canonical contract surface in `contracts_v14`)
- TYPE-01 (mypy --strict clean)
- TEST-01/R11 (9 canonical v14 tests green; pin tests added)
- FIN-01/02 (additive changes only; IRR/DSCR/NPV pins unchanged)
- DOC-02 (this CHANGELOG entry + VERSION bump in same PR)
- MRM-02 (junit artefacts retained; `scenario_name` + `analysis_timestamp` now in audit trail)



## v0.3.1 - 2025-12-11

- Sprint 10 – evaluation_v14 + Monte Carlo gateway hardened (CASPER & tail-risk green)



## v14.2.1 - 2025-12-11

- Fix Sprint 9 CASPER tail-risk integration

- Add scenario_config_path parameter to fake_run_monte_carlo_analysis
- Remove invalid success_rate constructor argument
- Add raw_results with Monte Carlo samples for tail-risk analysis
- Fix Monte Carlo config path in test_casper_v14_smoke_iteration1
- All CASPER tail-risk tests now passing (335/345 total)
- Coverage: 66.51% (above 55% threshold)



## v0.3.x - 2025-12-10

- Sprint 9 – CASPER v1 contract freeze + sensitivity_v14.run façade



## v0.3.1 - 2025-12-10

- Sprint 9 – CASPER tail-risk wiring (v14 MC snapshots + payload)



## v0.3.0 - 2025-12-09

- Sprint 9: Complete Integration Analysis & Design (CASPER/GWTF Compliant)



## v0.3.x - 2025-12-08

- Sprint 9 – v14 Monte Carlo front door + regression guard



## v0.3.0 - 2025-12-07

- Sprint 8 – v14 lender pipeline hardened (tests green, coverage 59.82%)



## v0.3.0 - 2025-12-05

- feat: add PySAM sandbox module (isolated, optional, validation-first)

- analytics/pysam_sandbox: Optional PySAM wrapper (mypy+ruff clean)
- scripts/validate_pysam_offline.py: Validation script (<5% deviation gate)
- Uses importlib.util.find_spec for PySAM availability (ruff-compliant)
- Compliance: ARCH-01, TYPE-01, FIN-01, FIN-02, R10, R17

Pre-commit: black/ruff/isort auto-formatted 36 files
Status: Day 1 complete - ready for Day 2-3 validation phase



## v0.3.0 - 2025-12-05

- feat: add PySAM sandbox module (isolated, optional, validation-first)

- analytics/pysam_sandbox: Optional PySAM wrapper (mypy+ruff clean)
- scripts/validate_pysam_offline.py: Validation script (<5% deviation gate)
- Uses importlib.util.find_spec for PySAM availability (ruff-compliant)
- Compliance: ARCH-01, TYPE-01, FIN-01, FIN-02, R10, R17

Status: Day 1 complete - ready for Day 2-3 validation phase



## v2.6.0 - 2025-12-04

- Sprint 8 - IRR ring-fence + v14 sensitivity API (mypy-clean core)



## v2.5.2 - 2025-12-04

- Sprint 8 – v14 equity + cashflow contracts + run_full_pipeline_v14 wiring



## v2.5.0 - 2025-12-04

- Sprint 7 – v14 pipeline + sensitivity + metrics typing



## v0.2.3 - 2025-11-26

- v14 pipeline surface frozen; CLI shim wired



## v0.2.3.1 - 2025-11-24

- docs: Add Thread Migration Package suite for seamless AI context restoration



## v1.0.0 - 2025-11-24

- docs: Add comprehensive Thread Migration Package



## v0.2.3.1 - 2025-11-24

- docs: Add Thread Migration Package suite for seamless AI context restoration



## v0.2.3 - 2025-11-23

- ScenarioAnalytics batch + Excel export helpers hardening



## v0.2.2 - 2025-11-23

- IRR engine hardening + v14 KPI refactor (project NPV/IRR, DSCR sanitiser)



## v0.2.2 - 2025-11-22

- v14 cashflow & metrics mypy-clean spine



## v0.2.2 - 2025-11-22

- Promote v14 finance modules + schema guard for bad_missing_tax



## v0.2.8 - 2025-11-22

- Document v14 analytics, architecture, and executive workbook



## v0.2.6 - 2025-11-22

- Top-up coverage with finance.utils tests



## v0.2.6 - 2025-11-21

- Docs: add v14 dev workflow



## v0.2.6 - 2025-11-21

- Docs: analytics + architecture + executive workbook



## v0.2.5 - 2025-11-21

- Lock FX schema to structured mapping + scenario guard tests



## v0.2.5 - 2025-11-21

- Tighten v14 coverage gates; CI + local green



## v0.2.5 - 2025-11-21

- CI v14chat green; v14 stack stabilized



## v0.2.4 - 2025-11-21

- CI v14chat: add .venv reset step



## v0.2.3 - 2025-11-21

- Wire CI v14chat workflow



## v0.2.2 - 2025-11-21

- Fix regression_smoke date for macOS; v14-only smoke



## v0.2.1 - 2025-11-21

- Analytics exports + ScenarioAnalytics DF unit tests



## v0.2.1 - 2025-11-21

- v14 CI baseline – upstream auto




## [0.1.6] – 2025-11-20

### Added
- ExcelExporter: new `add_dataframe_sheet`, `add_conditional_formatting`, and
  `add_chart_image` helpers for richer, board-pack-friendly workbooks.
- Board-focused export: `export_summary_and_timeseries` now writes Summary/Timeseries
  plus optional DSCR/IRR views and auto-fits all sheets.
- ChartExporter: PNG chart helpers for DSCR time series and IRR histograms, safe to
  call in CLI/CI environments (no Excel dependency).
- ChartGenerator: lightweight KPI/NPV/DSCR/debt chart generator for Monte Carlo and
  sensitivity runs, returning file paths for downstream use.

### Fixed
- Tightened FX configuration validation in `scenario_loader`: scalar `fx` is now
  rejected with a clear error, enforcing the structured `fx` mapping policy in v14
  configs.
- Expanded export/analytics tests, raising coverage over the analytics and helper
  modules while keeping CLI and pipeline smokes green.

- TBD

## v0.2.0 - 2025-11-21
- v14 CI baseline

## [1.0.0] - Initial public baseline
- CI: matrix (Ubuntu/Windows/macOS) + Python 3.10–3.12, workflow_dispatch, nightly, concurrency guard
- Pre-commit: black/flake8/isort/mypy + hygiene hooks
- Strict configs: .flake8, mypy.ini, pytest.ini (coverage ≥90% gate)
- Scenario runner: YAML → JSONL/CSV, multi-path `--scenarios`
- CLI: modes mapped (baseline/sensitivity/optimize/report/scenarios/api) + finance handlers + EPC
- Schema/docs: EPC parameters (ranges + units) in `schema.py`/`schema.md`
- Packaging: `python -m build`, smoke-install, artifact upload with versioned names
- Security/hygiene: CODEOWNERS, SECURITY.md, CONTRIBUTING.md
