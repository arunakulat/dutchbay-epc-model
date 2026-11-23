# Output Surface Consumer Matrix (#1815)

**Status:** Active governance contract (Issue #1815 Slice 2b).
**HOLD union:** `F-5, #1110, v15.6.1` (unchanged; zero lender, Board, covenant, or release authority).
**Canonical contract module:** [`analytics/run_identity.py`](../analytics/run_identity.py).

## 1. Purpose

This matrix binds every output surface of the DutchBay EPC Model to one shared:

1. **Run & configuration identity** (`RUN_IDENTITY_FIELDS`): `config_sha256`, `engine_version`, `git_sha`, `generated_at`, `manifest_schema_version`, `validation_mode`, and `seed`.
2. **Unit contract** (`KPI_UNIT_CONTRACTS`, `metric_unit`, `UNIT_EXCEL_NUMBER_FORMATS`): explicit machine units (`pct`, `usd`, `lkr`, `lkr_per_usd`, `mw`, `gwh`, `kwh`, `years`, `multiple`, `count`) and consistent display/Excel formatting.
3. **Section disposition** (`SECTION_DISPOSITIONS`): `computed`, `allocated`, `degraded`, `omitted`, `not_run`.
4. **Reliance & hold labels** (`RELIANCE_LABELS`, `HOLD_UNION`, `F5_NON_RELIANCE_NOTICE`):
   - `lender_reliance_prohibited`: F-5 / `#1110` / `v15.6.1` non-reliance notice is un-suppressible across surfaces.
   - `screening_only_synthetic_grid`: synthetic QSTS / grid screening outputs (`bankable=False`, `SYNTHETIC_PROCESS_PROVENANCE_WARNING`, `MANDATORY_SCREENING_CAVEAT`) remain strictly screening-only and never feed canonical finance.
   - `allocated_within_year_non_covenant`: allocated within-year / intra-year / per-period figures (`subannual_rows_v14`, `min_dscr_period`, `multi_tech` WBS allocations) remain explicitly distinguishable from approved annual covenant metrics (`min_dscr`).

No independent Excel formula-engine completion is implied by the DFI foundation workbook (`analytics/dfi_workbook/foundation.py`); workbook calculations remain engine-supplied except where explicitly bounded (`Module_Ledger` `COUNTIF`/`SUM` rollups).

---

## 2. Cross-Surface Consumer Matrix

| Dimension | API (`RunPipelineResponse` / `CaseSurface`) | Report & DBPL (`ReportContext` / HTML / `to_dbpl_print_html`) | Executive Workbook (`analytics/executive_workbook.py`) | DFI Foundation Workbook (`analytics/dfi_workbook/foundation.py`) |
|---|---|---|---|---|
| **Run / Config Identity** | `RunPipelineResponse.manifest` (`ManifestBlock`); `CaseSurface.run_manifest` | `ReportContext.manifest`; DBPL `Control` table & table `Source` notes (`git_sha`, `config_sha256`) | `Manifest` sheet (`RUN_IDENTITY_FIELDS`: `config_sha256`, `engine_version`, `git_sha`, `generated_at`, `manifest_schema_version`, `validation_mode`, `seed`) | `Control_Provenance` sheet (`config_sha256`, `engine_version`, `generated_at`, `scenario_name`) |
| **Unit Contracts** | Typed suffix fields (`*_usd`, `*_pct`, `*_gwh`, `*_years`) + `KpiCard.unit` & `KpiCard.display` (`%`, `x`, `$`) | `KpiRow.display` via `format_kpi_value` (`%`, `x`, `$`), typed `fmt_usd` / `fmt_gwh` / `fmt_x` / `fmt_ratio_pct` | Openpyxl `number_format` stamped per `UNIT_EXCEL_NUMBER_FORMATS` (`0.00%`, `0.00"x"`, `$#,##0;-$#,##0;"$0"`, `"LKR "#,##0`) across `Summary`, `Cashflow`, `DebtService`, `Ratios`, `ScenarioSummary` | `WorkbookInputItem.unit` + validated `number_format` on `Inputs` registered in `CellRegistry` |
| **Section Dispositions** | `CaseSurface.section_dispositions` (`computed`, `allocated`, `degraded`, `omitted`, `not_run`); sync OOB blocks explicitly `omitted` | `ReportContext.sections_not_run` (`SectionNotRun`), `tornado_not_computed`, presence-gated blocks (`multi_tech` -> `allocated`) | Core finance sheets always emitted; optional `ResourceTrend` emitted only when analyzed trend exists | `Module_Ledger` sheet validated against `ModuleExecutionLedger` (`ModuleExecutionStatus`) & `config/module_roles.yaml` |
| **F-5 / #1110 Reliance** | `CaseSurface.reliance_notice` (`F5_NON_RELIANCE_NOTICE`) + `CaseSurface.reliance_label="lender_reliance_prohibited"` | `ReportContext.f5_notice` on cover + every DBPL section band (`dbpl-caveat`) & running banner | `Summary!A1 = EXECUTIVE_WORKBOOK_F5_CAVEAT` (exact `F5_NON_RELIANCE_NOTICE`) | `Control_Provenance!A1 = DFI_WORKBOOK_F5_CAVEAT`; free-text metadata rejects hold-withdrawal wording |
| **Allocated vs Covenant** | `KpiBlock.min_dscr` (annual folded covenant); `CaseSurface.section_dispositions["multi_tech"] == "allocated"` when hybrid | `min_dscr` headline vs `min_dscr_period`; `multi_tech` labeled additive attribution; F-5 bars quarterly CFADS/intra-year DSCR covenant use | `Ratios` surfaces both `min_dscr` and `min_dscr_period`; `Summary!A1` bars intra-year DSCR covenant reliance | `formula_boundary_note` states engine-computed schedules; no simplified spreadsheet covenant substitution |
| **Synthetic Grid Screening** | Excluded from canonical `RunPipelineResponse` finance KPIs; `output_class="synthetic_process_provenance"` | `grid_screening_emit.py` (`MANDATORY_SCREENING_CAVEAT`, `bankable=False`) & `synthetic_qsts_finance_report.py` (`SYNTHETIC_PROCESS_PROVENANCE_WARNING`) | Advisory grid study excluded from canonical finance sheets | `Module_Ledger` records grid modules with `non_model_adapter` / `governance_metadata` and non-bankable provenance |

---

## 3. Canonical Unit Contracts

| Unit Token | Suffix / Metric Keys | Display Format | Openpyxl `number_format` |
|---|---|---|---|
| `pct` | `*_pct`, `project_irr`, `equity_irr`, `discount_rate_used`, `balloon_pct`, `gearing`, `capacity_factor` | `0.00%` (e.g. `1.46%`) | `0.00%` |
| `usd` | `*_usd`, `project_npv`, `equity_npv`, `balloon_residual`, `cf_after_debt`, `cf_pre_debt`, `debt_service_total` | `-$#,##0` / `$#,##0` | `$#,##0;-$#,##0;"$0"` |
| `lkr` | `*_lkr`, `carried_forward_losses`, `wht_on_interest` | `LKR #,##0` | `"LKR "#,##0;-"LKR "#,##0;"LKR 0"` |
| `lkr_per_usd` | `fx_rate` | `#,##0.00` | `#,##0.00` |
| `multiple` | `min_dscr`, `min_dscr_period`, `avg_dscr`, `dscr_*`, `llcr`, `plcr`, `equity_moic`, `equity_multiple` | `0.00x` (e.g. `1.29x`) | `0.00"x"` |
| `mw` / `gwh` / `kwh` | `*_mw`, `*_gwh`, `*_kwh`, `grid_loss` | `<val> MW` / `GWh` / `kWh` | `#,##0.0" MW"` / `#,##0.1" GWh"` / `#,##0" kWh"` |
| `years` | `*_years`, `equity_payback_period_years` | `<val> years` | `0.0" years"` |
| `count` | `year`, `period`, `years_below_threshold`, `first_breach_year`, `last_breach_year` | integer | `#,##0` |

---

## 4. Automated Verification Controls

Implemented in [`analytics/run_identity.py`](../analytics/run_identity.py) and exercised by [`tests/app/test_run_identity_parity_1815.py`](../tests/app/test_run_identity_parity_1815.py) and [`tests/app/test_surface_consumer_matrix_1815.py`](../tests/app/test_surface_consumer_matrix_1815.py):

- `require_same_run_identity` — verifies identical `RUN_IDENTITY_FIELDS` across surfaces and fails on missing or tampered fields.
- `require_unit_contracts_aligned` & `validate_display_matches_unit` — verifies cross-surface unit alignment and display-string conformance.
- `require_consistent_section_dispositions` — verifies `SECTION_DISPOSITIONS` and refuses contradictions (except explicitly permitted sync-API omissions).
- `require_reliance_labels` & `check_no_hold_withdrawal` — verifies `F-5`, `#1110`, `v15.6.1`, synthetic-grid screening-only status, and allocated-vs-covenant separation while rejecting hold-withdrawal wording.
- `verify_consumer_matrix` — runs all four cross-surface checks together as a single audit gate.
