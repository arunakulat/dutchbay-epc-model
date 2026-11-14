# P2.3: Common Run/Evidence Identity, Units and Reliance Labels Across Report, Workbook and API

**Document status:** Governed inventory baseline (Refs #1427, Tracker milestone P2.3).
**Record date:** 2026-11-14.
**Baseline commit:** `d4934e07076184d4a4dd2cb9bd663503cc70881a` (`origin/main`).
**Governing mandate:** Claude claim split on tracker #1353 (#issuecomment-6876603269) — **INVENTORY ONLY, NO CODE** for this slice. Code delivery follows after the active PR queue lands.
**HOLD union:** `F-5, #1110, v15.6.1`. Issue #1110 remains `OPEN_HOLD` (no Board or lender circulation without explicit Board release).

---

## 1. Executive Summary and Scope Authority

Issue #1427 addresses the cross-surface consistency of DutchBay EPC Model outputs:
- **Run and evidence identity:** Ensuring reports, workbooks, and API payloads carry consistent machine-verifiable provenance (git commit SHA, resolved config digest, engine version, timestamp, invocation ID).
- **Reliance labels & governance gates:** Explicitly flagging non-bankable outputs, unapproved drafts, and Board/lender circulation holds (Issue #1110).
- **Within-year vs. approved covenant metrics (F-5):** Enforcing a strict distinction between allocated within-year cash flows (monthly or quarterly liquidity profiles) and approved annual covenant metrics (such as minimum DSCR, LLCR, PLCR).
- **Synthetic grid screens vs. site evidence:** Segregating advisory synthetic grid screening studies (D1–D7, QSTS) from empirical site measurements and canonical bankable cash flows.
- **D7 Formula Workbook:** Recording the owner decision boundary regarding live Excel formulas versus data-only workbooks.

This inventory audits every output surface against `origin/main` (`d4934e07076184d4a4dd2cb9bd663503cc70881a`), identifies concrete gaps, and provides structured issue proposals for focused implementation once the queue lands.

---

## 2. Inventory Surface 1: HTML & DBPL Presentation Layer (Reports)

### 2.1 Generators and Components
- **Primary Generator:** `app/reports/renderer.py` driving Jinja2 template `app/reports/templates/report.html.j2` from `ReportContext` (`app/reports/report_model.py`).
- **DBPL Print Core:** `app/reports/dbpl/print_core.py` and `app/reports/dbpl/style.py` producing PDF prints under strict styling and un-suppressible running headers/footers.
- **Ancillary Emitters:**
  - `app/reports/grid_screening_emit.py` (`templates/grid_screening.html.j2`)
  - `app/reports/synthetic_qsts_finance_report.py` (`templates/synthetic_qsts_finance_report.html.j2`)
  - `app/reports/tender_gap_dossier_emit.py` (`templates/tender_gap_dossier.html.j2`)
  - `app/reports/capital_risk_emit.py`, `app/reports/interaction_grid_emit.py`, `app/reports/tech_comparison_emit.py`

### 2.2 Current State Audit
1. **Run and Evidence Identity:**
   - `ReportContext.meta` (from `app/reports/report_config.py`) exposes `title`, `subtitle`, `organization`, `version`, `confidentiality`, and `disclaimer`.
   - `ReportContext.manifest` exposes the structured run manifest from `analytics.run_manifest.build_run_manifest()`: `config_sha256`, `engine_version`, `git_sha`, `generated_at`, and `validation_mode`. Rendered in Section 9 ("Audit Manifest & Methodology") in `report.html.j2`.
   - `ReportContext.report_grade` surfaces `"screening"` / `"developer"` / `"lender"` / `"ic"` on the cover page when declared in `run.mode`.
   - DBPL running footer embeds document ID, version, and generation date.
2. **Units:**
   - Formatted cleanly via `format_kpi_value()` and typed formatters (`fmt_usd`, `fmt_gwh`):
     - Ratios / IRRs formatted as percentages: `4.22%`.
     - Multiples formatted with `x`: `1.30x`.
     - Currencies formatted with accounting sign: `-$57,994,286`.
     - Energy formatted with units: `76.5 GWh`.
   - Table column headers consistently carry unit parentheticals: `(USD)`, `(GWh)`, `(%)`.
3. **Reliance Labels & Caveats:**
   - Un-suppressible confidentiality tag on cover and running footer.
   - `fx_warning` and `fx_fallback_note` rendered as high-visibility warning blocks.
   - `model_limitations` table explicitly surfaces scope caveats and unverified parameters.
   - `ic_summary` red-flag block highlights covenant breaches and below-hurdle returns.
   - Grid screening reports (`grid_screening_emit.py`) carry `MANDATORY_SCREENING_CAVEAT`, `EMT_GAP_CAVEAT`, and `TENDER_EVIDENCE_CAVEAT`.
   - Synthetic QSTS reports carry `SYNTHETIC_PROCESS_PROVENANCE_WARNING` ("based on synthetic data - non-bankable - only for process provenance purposes").
4. **F-5 Sub-Annual / Covenant Status:**
   - Headline figures surface `min_dscr` (folded annual min) and `min_dscr_period` (sculpt period floor).
   - In `cashflow_waterfall`, figures are rendered on annual basis. When sub-annual within-year profiles are supplied, there is no separate sub-annual table; intra-year liquidity risks are uncoupled from annual debt service covenants.

### 2.3 Identified Gaps on Surface 1
- **Gap R-1 (Top-Level HOLD Banner):** When Issue #1110 is active (`OPEN_HOLD`) or when `report_grade != "lender"`, the report cover lacks an un-suppressible top-level visual banner stating: `"DRAFT / INTERNAL USE ONLY — NOT FOR LENDER OR BOARD RELIANCE (Issue #1110 HOLD)"`.
- **Gap R-2 (Cross-Surface Grid Warning):** When technical chapters of `report.html.j2` mention grid curtailment or POI export limits derived from advisory grid screens, they do not embed a direct link or indicator to the non-bankable status established by `grid_screening_emit.py`.
- **Gap R-3 (F-5 Sub-Annual Caveat):** If a scenario config specifies `cashflow.within_year_profile`, the report does not render an explicit F-5 warning note clarifying that intra-year profile shapes do not alter or substitute for annual debt-service covenant calculations.

---

## 3. Inventory Surface 2: Excel Workbooks (`.xlsx`)

### 3.1 Generators and Components
- **Primary Generator:** `analytics/executive_workbook.py` (`build_executive_workbook`, `emit_executive_workbook_from_pipeline`).
- **Reproducibility Layer:** `analytics/reproducible_workbook.py` (`normalize_xlsx_reproducible`, `freeze_workbook_reproducible`).
- **Ancillary Generators:** `analytics/scenario_analytics.py` (`ExcelExporter`), `analytics/mc/exports.py` (`export_mc_run_to_excel`).

### 3.2 Current State Audit
1. **Sheet Structure (`executive_workbook.py`):**
   - `"Summary"`: Scalar KPIs as a two-column `(Metric, Value)` table.
   - `"Cashflow"`: Annual cashflow table (`year`, revenue, opex, tax, CFADS, etc.).
   - `"DebtService"`: Per-period debt schedule (`period`, debt outstanding, interest, debt service, DSCR).
   - `"Ratios"`: DSCR/LLCR/PLCR stats plus covenant thresholds and audit status.
   - `"ScenarioSummary"`: One-row headline summary.
   - `"ResourceTrend"` (optional): Long-term wind/solar trend commentary.
2. **Run and Evidence Identity:**
   - **MAJOR DEFECT:** There is NO "Manifest", "Cover", or "Metadata" sheet in the workbook!
   - `git_sha`, `config_sha256`, `engine_version`, and `generated_at` are completely absent from the sheets.
   - To make workbooks byte-reproducible for regression tests, `normalize_xlsx_reproducible` resets `docProps/core.xml` timestamps to a static synthetic constant `2020-01-01T00:00:00Z` (`REPRODUCIBLE_EPOCH`). As a consequence, openpyxl archive metadata contains no real build timestamp.
3. **Reliance Labels:**
   - **MAJOR DEFECT:** The workbook is completely silent regarding reliance, draft status, or governance state.
   - There is no header, watermark, or metadata cell indicating whether the workbook is a screening draft, a lender package, or subject to Issue #1110 / F-5 HOLD.
4. **Units & Cell Formatting:**
   - In `"Summary"`, values are raw unformatted floats. Ratios (`project_irr: 0.0984`) and large currency amounts (`total_capex_usd: 207500000.0`) look like plain numbers without percentage or dollar formatting.
   - In `"ScenarioSummary"`, column headers have mixed suffix conventions (`project_npv` without `_usd`, but `max_debt_usd` with `_usd`).
   - In `"DebtService"`, `period` is an unadorned integer (`0, 1, 2...`), without indicating whether period represents construction months, semi-annual repayment, or calendar year.
5. **Within-Year vs. Approved Covenant Metrics (F-5):**
   - In `"Ratios"`, `min_dscr` (folded annual min) and `min_dscr_period` (sculpt period floor) are listed adjacently as raw numbers with no note distinguishing the approved covenant metric from the sculpt period floor.

### 3.3 Identified Gaps on Surface 2
- **Gap W-1 (Missing Manifest & Provenance Cover Sheet):** Add a mandatory `"Cover"` / `"Manifest"` sheet to `executive_workbook.py` exporting `scenario_name`, `git_sha`, `config_sha256`, `engine_version`, `report_grade`, and real build timestamp.
- **Gap W-2 (Un-suppressible Reliance Header):** Display a prominent top banner across the cover sheet and summary sheet stating: `"DRAFT / INTERNAL USE ONLY — NOT FOR LENDER RELIANCE (HOLD union: F-5, #1110, v15.6.1)"`.
- **Gap W-3 (Openpyxl Number Formatting & Unit Suffixes):** Apply explicit openpyxl number formatting (`0.00%` for rates/IRRs, `"$#,##0"` for currencies, `0.00"x"` for DSCR/LLCR multiples) and enforce explicit `_usd`, `_pct`, `_gwh` suffixes in metric names.
- **Gap W-4 (F-5 Covenant Clarification on Ratios Sheet):** Include explicit metadata text on the `"Ratios"` sheet clarifying that `min_dscr` is the annual folded covenant basis, while `min_dscr_period` is the debt-sculpting schedule floor, preventing sub-annual substitution.

---

## 4. Inventory Surface 3: JSON API (`api/pipeline_api.py`)

### 4.1 Endpoints and Contracts
- **Primary Endpoint:** `POST /pipeline/run` accepting `RunPipelineRequest` and returning `RunPipelineResponse`.
- **Sensitivity Endpoint:** `POST /sensitivity/run` returning `RunSensitivityResponse`.
- **Contract Models:** `analytics/contracts_v14.py` (`EvaluationResult`, etc.).

### 4.2 Current State Audit
1. **Run and Evidence Identity:**
   - `RunPipelineResponse.manifest` (`ManifestBlock`) provides strong provenance:
     - `config_sha256: str`
     - `engine_version: str`
     - `git_sha: str`
     - `generated_at: str`
     - `validation_mode: Optional[str]`
     - `manifest_schema_version: str`
     - `seed: Optional[int]`
   - Top-level response includes `scenario_name: str` and `config_path: Optional[str]`.
2. **Units:**
   - Explicit typed fields with unit suffixes in field names:
     - `KpiBlock`: `project_npv_usd`, `equity_npv_usd`, `discount_rate_used`, `equity_multiple`, `equity_payback_years`.
     - `AepBlock`: `net_p50_gwh`, `net_p75_gwh`, `net_p90_gwh`, `gross_gwh`, `capacity_factor`.
     - `DebtBlock`: `debt_total_usd`, `total_idc_usd`, `gearing`, `avg_debt_rate_pct`, `balloon_pct`, `balloon_remaining_usd`.
     - `CostBlock`: `capex_total_usd`, `capex_per_kw_usd`, `irena_benchmark_per_kw`.
     - `FundingBlock`: `initial_dsra_usd`, `capex_usd`, `import_levies_usd`, `idc_usd`, `senior_debt_usd`, `equity_usd`.
3. **Reliance Labels:**
   - **GAP:** `RunPipelineResponse` carries no `reliance_label`, `report_grade`, `hold_status`, or disclaimer string.
   - An API consumer receives financial KPIs without programmatic indication of whether the run represents a screening estimate, a developer model, or an approved lender case, or whether Issue #1110 / F-5 HOLD applies.
4. **Within-Year vs. Approved Covenant Metrics (F-5):**
   - `KpiBlock.min_dscr` returns the annual fold-corrected covenant minimum.
   - `DebtScheduleRow` returns annual rows (`year: int`, `dscr: Optional[float]`, `debt_outstanding_usd: Optional[float]`, `debt_service_usd: Optional[float]`).
   - If a within-year profile (`cashflow.within_year_profile`) is evaluated, intra-year period rows are not exposed at the top-level API, and no `covenant_basis: "annual"` field is declared.
5. **Synthetic Grid Screens:**
   - Grid screening is intentionally kept out of `RunPipelineResponse` (asynchronous, advisory only).
   - In `analytics/contracts_v14.py`, synthetic QSTS and feeder data are pinned with `output_class = "synthetic_process_provenance"` and `required_warning = SYNTHETIC_PROCESS_PROVENANCE_WARNING`.

### 4.3 Identified Gaps on Surface 3
- **Gap A-1 (API Reliance and Grade Exposure):** Add `report_grade: Optional[str]` ("screening" | "developer" | "lender" | "ic") and `reliance_label: str` ("non_bankable_draft" | "hold_1110" | "lender_cleared") to `RunPipelineResponse.manifest`.
- **Gap A-2 (Invocation UUID):** Add a unique `run_id: str` (UUID4) to `ManifestBlock` to identify individual execution instances alongside the deterministic `config_sha256`.
- **Gap A-3 (Covenant Basis Metadata):** Add `covenant_basis: Literal["annual_audited", "sculpt_period"]` and explicitly expose `min_dscr_period` alongside `min_dscr` in `KpiBlock` so API consumers cannot mistake intra-year sculpt profiles for approved annual covenants.

---

## 5. Inventory Surface 4: Formula Workbook / D7 Status

### 5.1 Owner Decision Boundary
Issue #1427 explicitly notes:
> *"The D7 formula workbook remains an owner decision."*

### 5.2 Current Technical Reality
- The current workbook generator (`analytics/executive_workbook.py`) is strictly **values-only**. DataFrames are written via pandas and openpyxl as raw static values (`.to_excel()`), with zero embedded Excel formulas (`=SUM(...)`, `=IRR(...)`, `=IF(...)`).
- Translating DutchBay's complex financial logic (sculpted dual-DSCR debt, circular IDC solving, TLCF tax depreciation, multi-tranche debt waterfalls, and currency swaps) into native Excel formulas introduces severe formula-drift risk, dual-engine maintenance overhead, and circular reference instability.
- In accordance with CCCDIR (single canonical engine in Python), the D7 live-formula workbook remains an owner decision and is **deferred**. The executive workbook remains an authoritative static data-and-ratios export.

---

## 6. Actionable Focused Delivery Issues Proposed

To resolve the gaps identified in this inventory once the open PR queue lands, the following five focused dolphin issues are structured for delivery:

### Issue Card 1: `export(workbook): add Manifest cover sheet and un-suppressible reliance header to executive workbook (#1427 Gap 1 & 2)`
- **Scope:** Update `analytics/executive_workbook.py` to insert a leading `"Cover"` sheet containing `scenario_name`, `git_sha`, `config_sha256`, `engine_version`, `report_grade`, real build timestamp, and un-suppressible banner: `"DRAFT / INTERNAL USE ONLY — NOT FOR LENDER RELIANCE (HOLD union: F-5, #1110, v15.6.1)"`. Ensure `normalize_xlsx_reproducible` preserves cover sheet contents while freezing ZIP archive headers.
- **Done when:** `tests/test_executive_workbook.py` proves cover sheet presence, exact manifest keys, reliance banner, and byte-reproducibility.

### Issue Card 2: `export(workbook): standardise unit column and openpyxl cell formatting across executive workbook sheets (#1427 Gap 3)`
- **Scope:** Update `analytics/executive_workbook.py` to add an explicit `Unit` column in `"Summary"` and apply openpyxl `number_format` strings (`0.00%`, `"$#,##0"`, `0.00"x"`) across all exported tables. Align column names to use explicit unit suffixes (`_usd`, `_pct`).
- **Done when:** Unit tests verify cell formatting strings and column headers across all five standard sheets.

### Issue Card 3: `api(reporting): surface report_grade, invocation run_id, and reliance_label in RunPipelineResponse (#1427 Gap 4)`
- **Scope:** Extend `ManifestBlock` in `api/pipeline_api.py` to include `run_id: str`, `report_grade: Optional[str]`, and `reliance_label: str`. Populate from evaluated scenario metadata and governance rules.
- **Done when:** `tests/api/test_pipeline_api.py` verifies presence and schema validation of new manifest fields across all response modes.

### Issue Card 4: `reporting(f5): formally distinguish within-year profiles from approved annual covenant metrics across report, workbook and API (#1427 Gap 5)`
- **Scope:** Add explicit `covenant_basis: Literal["annual_audited"]` and `F-5 intra-year non-reliance caveat` to `ReportContext`, `executive_workbook.py` (`"Ratios"` sheet), and `RunPipelineResponse.kpis`. Ensure `min_dscr_period` is documented as the period sculpting floor and never confused with annual covenant compliance.
- **Done when:** Regression tests verify that enabling `cashflow.within_year_profile` triggers the F-5 caveat banner across HTML reports, workbook ratios, and API schemas.

### Issue Card 5: `reporting(grid): unify synthetic process provenance warning banners across main report and API export routes (#1427 Gap 6)`
- **Scope:** Ensure that any summary reference in `report.html.j2` or API metadata to grid study metrics (curtailment, POI limits) carries the un-suppressible `SYNTHETIC_PROCESS_PROVENANCE_WARNING` tag and a direct link to the advisory grid screening report.
- **Done when:** Tests prove that grid-enabled scenario runs embed the mandatory non-bankable notice in the executive summary whenever grid-derived curtailment is referenced.

---

## 7. Receipts and Verification Restatement

| Surface | File(s) Audited | SHA-256 Digest | Status |
|---|---|---|---|
| Reports | `app/reports/report_model.py`<br>`app/reports/templates/report.html.j2`<br>`app/reports/grid_screening_emit.py` | `0ea903960166a9ba8db780000a6530a6182c0fa02005a30e844e1160a0f0559f`<br>`1b67f73db124ba16a9efc9e782e4f01416631ad021d7c34b6b1981a8c089d7fa`<br>`5669b359c25f479a9f9c7be78a2e1d03ff4207963d3f9b2d861614cb02fa2d7f` | Audited |
| Workbooks | `analytics/executive_workbook.py`<br>`analytics/reproducible_workbook.py` | `fb87f16183e95bf06ca8a0a911765c9c4fb25c1da8cce584bfb6c936ef018274`<br>`8595cb640d244f77a88448b1115bc26dd9c7fa6992be77e9b04fba2cf78bbf5e` | Audited |
| API | `api/pipeline_api.py`<br>`analytics/contracts_v14.py` | `a65a25eef02b1f0c2941fa44b3605273faea62391ce42ea8ff98e0bbbf1d7d08`<br>`61e7a5bb065ec015ef41473fa48a0a905be0cbe9080c102a7b7bb5770ca2b069` | Audited |

*End of P2.3 Inventory Document.*
