# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added
- **Live FX-sensitivity CLI surface + legacy `fx.fx_shock` base-key retirement (#659, analysis-only, KPI-neutral).**
  Closes the residual FX-reporting scope of #659 in two parts:
  - **New `scripts/run_fx_sensitivity.py`** — a thin argparse CLI (the FX analogue of
    `scripts/run_tornado_from_cli.py`; `scripts/` is the sanctioned argparse carve-out per
    `tests/lint/test_entrypoints_hydra_only.py`) that wraps
    `analytics.fx_sensitivity_real.FXSensitivityAnalyzer.analyze_fx_sensitivity`. It loads a
    scenario, sweeps the three LIVE engine FX levers (`fx.start_lkr_per_usd` / `fx.hedge_ratio`
    / `fx.spread_bps`, all wired by the FX-forward-hedging build #652/#666) around the
    scenario's own base, and emits a SINGLE JSON object to stdout or `--output`: the
    `fx_rate_points` / `hedge_ratio_points` / `spread_points` series plus the six engine-driven
    linear-fit summary sensitivities (`fx_rate_irr`/`fx_rate_npv`/`hedge_ratio_irr`/
    `hedge_ratio_npv`/`spread_irr`/`spread_npv`) and the scenario base metrics. The `fx_rate`
    IRR/NPV slopes are negative on the flat-LKR lender case (a weaker LKR erodes USD returns —
    the core bankability risk this surface quantifies). Fail-loud on a bad scenario / degenerate
    step count / negative spread band (exit 2, no traceback; CESSPIT).
  - **Retired the dead `fx.fx_shock` base key** from `FXSensitivityAnalyzer.run()`. The base
    evaluation used to seed `{"fx": {"fx_shock": 0.0}}`, but `fx.fx_shock` is a key the v14
    cashflow engine never reads (Fable finding from the #666 review), so it was inert; it is
    replaced with a clean no-override base call (`{}`). Proven byte-identical: the base metric
    is unchanged (a dedicated real-engine base-identity test pins `{} == {"fx": {"fx_shock":
    0.0}}`), and the stale "old keys" comment is corrected.
  - **Analysis surface only — no committed-scenario caller changes**, so every committed
    scenario's KPIs are byte-identical (verified via the all-scenarios KPI oracle, before-vs-
    after within the worktree).
- **Live long-term wind-resource & trend section wired into the lender report (#178 → #656, opt-in, disclose-only, KPI-neutral).**
  The Mann-Kendall + Sen's-slope trend analysis (`wind_resource.long_term_trend`) was complete
  and tested but reached no live path. It is now wired end-to-end as a report disclosure:
  - `wind_resource.era5_retrieval.ERA5RequestConfig` gains an opt-in `analyze_trend` flag
    (DEFAULT OFF; `download.analyze_trend` in YAML). When true, `run()` computes the trend on the
    SAME already-retrieved hub-height ERA5 series — **no second CDS fetch** — and attaches it
    under `result["long_term_trend"]`. A record shorter than `long_term_trend.MIN_TREND_YEARS`
    (10 yr) degrades **explicitly** (a recorded `analyzed: false` reason), never with a spurious
    tau (CESSPIT — fail-loud, no silent default).
  - `app.reports.report_model.ReportContext` gains an optional `resource_trend`
    (`ResourceTrendBlock`) projected from the live `analyze_long_term_resource` output
    (`render_trend_markdown` narrative + `trend_summary_dataframe` table, **not re-derived** —
    CCCDIR one-source-of-truth), and the lender report template renders an optional
    "Long-Term Wind Resource & Trend" section following the existing omit-when-absent pattern.
  - **Report / VALIDATE-only:** the section discloses a forward-looking P50 basis (IEC 61400-15-1
    / MEASNET) and explicitly states it does **not** overwrite the committed/frozen scenario P50.
    No engine, finance, or scenario-YAML value changes. Every existing report caller (the API
    report routes) supplies no ERA5 series, so `resource_trend` stays `None` and the rendered
    report is unchanged — all-scenarios KPIs are byte-identical (verified via the all-scenarios
    kpi oracle).
- **Distributional tail-risk for the lender report — first slice: MC per-case trial arrays + VaR/CVaR wire (#657, additive, opt-in, KPI-neutral).**
  `analytics.capital_risk_layer_v14.run_driver_mc` gains an opt-in `collect_trials=True`
  flag that additionally records the full per-trial metric arrays
  (`project_irr`/`equity_irr`/`project_npv`/`equity_npv`, per-trial `dscr_min`, and
  per-trial `llcr`/`plcr` scalars — coverage ratios are scenario scalars in
  `finance/debt_v14.py`, so one value per trial is the correct per-trial shape). The
  default three-key return (`equity_irr`, `equity_npv`, `min_dscr`) is preserved
  byte-for-byte; the RNG draw sequence is unchanged by the flag, so aggregate statistics
  are reproducible across both modes for a given seed.
  - `build_case_metadata_from_trials` packages those arrays into the exact
    `case["metadata"]["trials"][metric_key]` bucket shape that
    `analytics.sensitivity.tail_risk._extract_trials_from_case` reads — the shared
    metadata-plumbing prerequisite for all three distributional consumers, with no shape
    fork. `build_driver_mc_tail_snapshot` wires the previously-unconsumed distributional
    path onto these real arrays, producing per-metric VaR (P5/P10), CVaR / expected
    shortfall, and — for DSCR-like metrics — covenant-breach probability. This is exactly
    the distributional disclosure a project-finance due diligence wants and that the
    deterministic tornado path cannot give.
  - CESSPIT fail-loud preserved: `require_trials=True` yields an explicit `no_trials` note
    row when a metric's array is absent, never a silently fabricated distributional
    statistic. All evaluation flows through `evaluate_with_overrides` and no IRR/NPV math
    is added outside `finance/irr.py` (CCCDIR / ARCH-04). KPI-neutral report-layer metadata
    only — all committed-scenario KPIs are byte-identical (multi-scenario oracle).
  - Follow-ups filed for the two remaining wires of #657: `tail_risk_report` render into
    the capital-risk report output (needs the per-year DSCR/LLCR/PLCR `(n_scenarios,
    n_years)` matrix), and the `plot_npv_distribution` PNG from the same trial arrays.
  - **DSCR covenant-breach probability now robust to sculpt floor-pin representation noise
    (#657, Fable blocker — was a false lender risk number).** A dual-DSCR sculpt pins each
    trial's per-trial minimum DSCR at the covenant floor *by construction*, so the
    `dscr_min` trial array clusters at the floor to within ~1e-16 floating-point noise
    (values like `1.2999999999999996` for a 1.30 floor). The strict `arr < floor`
    comparison in `analytics.sensitivity.tail_risk._prob_breach` counted that sub-ULP
    scatter as breaches and reported an 85-93% DSCR breach probability on the flagship
    lender case whose true value is 0.0. `_prob_breach` now counts a breach only when a
    trial sits below the floor by more than representation noise (`arr < floor` and not
    `np.isclose(..., rtol=1e-9)`) — far tighter than any real DSCR margin, so genuine
    breaches are still counted. When the trial array is fully pinned at the floor,
    `build_driver_mc_tail_snapshot` now emits a disclosed `degeneracy` note on the DSCR row
    (`dscr_min_pinned_at_floor`): sculpted amortization makes per-trial min-DSCR invariant,
    so the informative lender tail lives in LLCR/PLCR and the balloon, not min-DSCR. Report
    diagnostic only — committed-scenario KPIs remain byte-identical (multi-scenario oracle).
- **PAWN (median-KS) global-sensitivity block in the lender report + PAWN (X, Y) given-data reuse (#645, additive, default-absent = byte-identical).**
  The lender report's Global Sensitivity area now carries an optional **PAWN** subsection
  alongside the existing Morris screening. PAWN (Pianosi & Wagener 2018) is a
  *distribution*-based (median Kolmogorov-Smirnov) index that stays bounded in [0, 1] and,
  unlike variance-based Sobol, is robust on the skewed / covenant-pinned (DSCR-floor) KPIs
  that are exactly the DutchBay case — so it is the natural complement to the Morris
  elementary-effects screening.
  - `app.services.report_global_sa.compute_report_global_sa_pawn` maps the canonical
    `analytics.sensitivity.global_sa.run_pawn` result to a render-ready `GlobalSABlock`
    (drivers ranked by median KS), reusing the same temp-file + CASPER degrade path as the
    Morris adapter (a nan_poisoned / flat_metric flag, a raising runner, or an empty result
    omits only that subsection — never sinks the core report; no SA logic reimplemented,
    CCCDIR). `GlobalSADriver` gains optional `median_ks` / `ks_cv` fields; `report.html.j2`
    renders the block as section 4g with the finite-sample **noise-floor** caveat (an inert
    driver measures a median KS of ~0.15 at n=256, s=10, so low-end ranks are sampling noise,
    not influence). Wired best-effort into the report route (`app/api/main.py`) via a new
    `global_sa_pawn` context field on `build_report_context`.
  - `run_pawn` gains optional **`given_x` / `given_y`** kwargs: pass a prior sweep's design
    matrix and its per-metric output vectors to REUSE them at zero extra evaluation cost (the
    given-data path — a Sobol / MC design already paid for can be re-decomposed by KS for
    free). `given_x` and `given_y` must be supplied together and shape-match the problem and
    each other or a `ValueError` is raised (CESSPIT — no silent LHS fallback); `n` is then
    ignored (`n_runs = len(given_x)`), and the reused design produces indices identical to the
    self-sampled path (closed-form Ishigami test). The self-sampled default is unchanged, so
    every committed scenario's KPIs are byte-identical (verified via the all-scenarios kpi
    oracle) and the report is byte-identical when the PAWN block is absent (default).
  - **Non-finite `given_x` is now a hard `ValueError`, naming the offending column and count
    (#645, Fable blocker — mirrors the #644 CESSPIT pattern).** `_validate_given_data` had
    validated `given_x`'s shape/alignment but not its finiteness, so a NaN/inf slipped in
    silently; PAWN then slices X with `np.nanquantile`, dropping those rows from the
    *conditional* CDFs while still counting them in the *unconditional* CDF — corrupting every
    reported KS index while the function's docstring promised "every mismatch raises
    ValueError." Unlike the Y-side (which takes the #644 row-mask), X cannot be masked without
    breaking PAWN's conditional design, so non-finite X is rejected outright. The finite reuse
    path is unaffected (indices stay bit-identical); no committed scenario exercises the
    given-data path, so all KPIs remain byte-identical.
  - The `--method pawn` CLI dispatch is tracked separately (#658); this change is the report
    surface + (X, Y)-reuse half only.
- **PAWN method + tax / DSCR presets exposed on the sensitivity CLIs (#658, closes #645, opt-in, report-only, KPI-neutral).**
  Three verified-existing, tested-but-CLI-orphaned sensitivity runners are now reachable from the
  two thin `scripts/` sensitivity CLIs. All additions are opt-in and change no computed KPI — the
  deterministic pipeline is untouched (all-scenarios kpi oracle byte-identical); the default
  behavior of both CLIs is unchanged.
  - `scripts/run_global_sensitivity.py` gains `--method pawn` (alongside `morris`/`sobol`;
    default stays `morris`) dispatching to `analytics.sensitivity.global_sa.run_pawn` with a new
    `--s` slice-count flag (`run_pawn` takes `n=`/`s=`, not `n_trajectories=`). PAWN is the
    moment-independent, KS-based index that stays bounded in `[0, 1]` on skewed / covenant-pinned
    KPIs where Sobol misbehaves. The stderr headline reports the median-KS ranking and discloses a
    `flat_metric` (covenant-pinned) or `nan_poisoned` (#644 finite-mask) block rather than
    presenting a zeroed ranking as an influence ranking (CESSPIT fail-loud). Prerequisite #644
    (partial-NaN finite mask) is merged, so `--method pawn` cannot emit fabricated rankings on a
    partially-NaN metric column.
  - `scripts/run_tornado_from_cli.py` gains `--preset tax` and `--preset dscr` (mutually exclusive
    with `--parameters`; each supplies its own drivers and fixes its own metric) routed through the
    sanctioned one-way wrappers `analytics.sensitivity.tax.run_tax_one_way` /
    `analytics.sensitivity.dscr.run_dscr_one_way`. The tax preset sweeps `tax.corporate_tax_rate`
    (pct band) + `tax.tax_holiday_years` (absolute 0→10) on `project_irr`; the DSCR preset sweeps
    the covenant levers (`Financing_Terms.target_dscr` / `debt_ratio` / `tenor_years`) on the
    canonical live `min_dscr` KPI key. The DSCR preset pins `min_dscr` (the key the gateway always
    emits — `analytics/core/metrics.py` sets both `min_dscr` and its `dscr_min` alias) rather than
    the `DscrSensitivityConfig` field default `dscr_min`, resolving the metric-key mismatch
    explicitly with no silent-KeyError / silent-fallback path.
  - These `scripts/` argparse additions stay within the thin-utility carve-out sanctioned by
    `tests/lint/test_entrypoints_hydra_only.py` / `test_no_argparse_anywhere.py` (both green); no
    argparse is introduced under `finance/`, `analytics/`, `dutchbay_v14chat/` or the canonical
    root entrypoints. Supersedes the `--method pawn` ask of #645 (its report-block extras remain
    out of scope).
- **Per-project approved AEP sources registered from YAML (#661, config-first provenance widening, opt-in, KPI-neutral).**
  A scenario may now declare an optional `resource.power_curve.approved_sources_yaml` naming a
  project-local YAML manifest of vetted AEP/curve sources (`{source_id: {type, description,
  iec_standard, [curve_key], ...}}`). At authored-scenario load and at both inline-config
  boundaries (the API and app-service seams), the new
  `analytics.aep_provenance.register_scenario_approved_sources` loads that manifest and registers
  each entry into the process-global `APPROVED_SOURCES` **before** the provenance guard
  (`enforce_aep_provenance`) runs — so a project can admit its own vetted turbine/source from
  config (ARCH-01) rather than editing the code registry, and all three live guard call sites
  (`enforce_aep_provenance`, `validate_curve_selection`, `validate_config_aep_provenance`) then
  accept it.
  - **Provenance-widening only, cannot weaken the contract.** Each entry is schema-validated by
    `aep_loader.register_approved_source` (required `type`/`description`/known `iec_standard`), and
    with the default `overwrite=False` a project YAML that re-declares a built-in `source_id` is
    refused — so config-driven registration admits new sources but cannot silently overwrite the
    placeholder / curve-key cross-check controls on the shipped entries.
  - **Fail-loud once declared (CESSPIT).** A declared `approved_sources_yaml` that is missing,
    unreadable, malformed, or non-string raises `AepProvenanceError`; the relative YAML path
    resolves against the scenario file's directory. No-op when the key is absent (the common
    case), so no committed scenario is affected and all-scenarios KPIs are byte-identical
    (verified via the all-scenarios kpi oracle).
  - `aep_loader.load_approved_sources_from_yaml` (and `register_approved_source`) are now in the
    module `__all__` (CASPER clean API surface).
- **Richer board-deck charts + embedded / live-formatted batch Excel (#662, opt-in, KPI-neutral).**
  The batch scenario-comparison export (`analytics.scenario_analytics.ScenarioAnalytics`, behind
  `run_scenario_analytics_v14.py`) gains a board-deck-grade enrichment on the charts-enabled path
  (`charts=true`):
  - `_export_charts` now also emits the cross-scenario `ChartGenerator` visuals into the
    `*_charts` sidecar — a KPI-comparison bar (`kpi_comparison.png`), a DSCR-comparison line with
    the 1.0 covenant floor (`dscr_comparison.png`), and an end-of-horizon debt waterfall
    (`debt_waterfall.png`) — alongside the existing per-scenario DSCR series and IRR histogram,
    and returns the written PNG paths.
  - The single `.xlsx` deliverable now embeds those PNGs into a dedicated `Charts` sheet
    (`ExcelExporter.add_chart_image`) and applies a **live** `CellIsRule` (`lessThan` 1.0) to the
    `DSCR_View` covenant column (`ExcelExporter.add_conditional_formatting`) — this re-evaluates as
    the reader edits, unlike the pre-existing static highlight fill.
  - **MRM-02 provenance** stamps every enriched artefact: a `Report_Cover` sheet and a
    `charts_metadata.json` sidecar carry the scenario list, scenarios directory, engine `VERSION`,
    commit, and economics basis, so any reported KPI set is reconstructable.
  - **DEFAULT OFF = byte-identical (#662).** With `charts=false` (the default for existing callers)
    the workbook is unchanged: no `Report_Cover`, no `Charts` sheet, no conditional-formatting rule,
    no charts directory. The two new `export_summary_and_timeseries` knobs
    (`dscr_conditional_threshold`, `embed_chart_images`) default to `None`. Exports are downstream of
    KPIs, so all committed-scenario KPIs are byte-identical (verified via the multi-scenario oracle).
    No new dependency (openpyxl / matplotlib already present, both optional).
- **Spatial-representativeness verdict wired into the GIS export / DataLake manifest (#660, WIND-10/#484, read-only diagnostic, KPI-neutral).**
  `analytics.gis.gis_export.run_gis_export` now retains the native n×n `CellResult`
  neighbourhood it samples per grid (previously discarded after `assemble_grids`) and runs
  the already-tested-but-unwired `wind_resource.era5_grid.spatial_representativeness` on it,
  attaching the `assessed: True` verdict (neighbourhood ws spread + centre-cell deviation vs
  tolerance) to BOTH the returned per-grid summary and each grid's `DataLake_Manifest_All.json`
  entry. Each interpolated (downscaled) grid carries its native source grid's verdict rather
  than recomputing one on the smoothed field. An even-`n` native grid (no well-defined centre
  cell) records an explicit `assessed: False` + reason instead of silently skipping the
  diagnostic (CESSPIT). The single-cell `wind_resource.era5_retrieval.run` result STAYS
  `assessed: False` (a single-point timeseries genuinely has no neighbourhood) but its reason
  string now points at the wired GIS-export path. `build_manifest_entry` gains an optional
  `representativeness` argument whose key is OMITTED when absent, so a manifest produced
  without a verdict is byte-identical to the pre-#660 manifest. Purely a provenance
  disclosure — it alters no exported raster, AEP or KPI (all-scenarios oracle byte-identical).
- **Tariff-breakeven and equity-IRR tariff solvers — on-demand analysis tools (#615, KPI-neutral).**
  Two additions to `analytics.core.parameter_solvers`, both routed ONLY through the
  `evaluate_with_overrides` gateway (ARCH-02: no direct IRR/NPV math — that stays in
  `finance/irr.py`), and with no committed-scenario caller so the KPI oracle is byte-identical
  across every scenario:
  (1) `solve_for_tariff_given_irr` is generalized with a `metric` parameter
  (`project_irr` | `equity_irr`); the project-IRR path is the default and unchanged, and a new
  `solve_for_tariff_given_equity_irr` wrapper pins the equity KPI. Both preserve the existing
  `_assert_override_is_live` / `_assert_target_bracketed` fail-loud guards and fail loud
  (CESSPIT) via a new `_require_kpi_present` check when the scenario computes no equity
  distribution (so `equity_irr` is absent) instead of silently solving project IRR.
  (2) `solve_tariff_breakeven` — a first-class breakeven surface (tariff at NPV=`target`, default
  NPV=0; or the tariff hitting an IRR hurdle) returning the centralized
  `contracts_v14.BreakevenResult` (CCCDIR: no new contract types) with `status`
  (`converged` | `max_iterations` | `unbracketed` | `error`) and the searched `bracket`
  populated, rather than a bare float — so a batch sweep gets structured infeasibility instead of
  a raised exception. HONEST convergence status (Fable blocker on #615): the underlying
  root-finders return the last midpoint on iteration exhaustion (they raise only when NO midpoint
  could be evaluated) and merely log a warning, so a naive wrapper would stamp `status="converged"`
  on a bound that misses the target by orders of magnitude. `solve_tariff_breakeven` now RE-VERIFIES
  the returned tariff via one extra `evaluate_with_overrides` evaluation and emits
  `status="converged"` ONLY when `|achieved - target| <= tolerance`; otherwise it reports
  `status="max_iterations"` with the residual (`achieved`, `target`, `abs_residual`, `tolerance`)
  in `metadata`. The inaccurate "raises on non-convergence" docstring claim (and the
  `solve_for_tariff_given_irr` / `_npv` "Raises: … fails to converge" sections) were corrected to
  state the true behaviour (they return the last bound on exhaustion, not raise). No behaviour
  change to the numeric bisection core. CLI exposure is deferred (module status note updated); any
  future CLI must be Hydra-only (R3).
- **Distribution-free order-statistic CI for the MC P90/P95 tail band + a Wilson breach-probability CI (#642, read-only/additive, KPI-neutral).**
  The convergence diagnostic (#590/#643) bounds only the *mean's* Monte Carlo error
  (`z·sd/√k`), but a lender reads the **P90/P95 band** (and the DSCR covenant breach
  probability), which converge slower than the mean. New
  `analytics.mc.convergence.percentile_ci_diagnostic` adds a distribution-free confidence
  interval for those percentiles — the classic **binomial order-statistic** interval (normal
  approximation to the rank bounds `n·p ± z·√(n·p·(1-p))`, floored/ceiled *outward* so
  coverage is conservative), with **no distributional assumption on the metric** (unlike the
  mean CI's i.i.d.-normal SE) — plus a **Wilson-score** CI for `P(dscr_min < covenant)`. It is
  computed from `result.trials` only and surfaced additively under
  `result.metadata['percentile_ci']` alongside `metadata['convergence']`. When `n` is too
  small to place a required rank (e.g. the P95 upper bound below ~73 trials) that bound is
  reported as `None` — loud omission, never a silent clamp to the extreme order statistic
  (CESSPIT). The `dscr_min` breach threshold is wired from the resolved DSCR covenant
  (`analytics.mc.covenant.resolve_min_dscr_covenant`, single source of truth). Student-t
  small-`k` widening is out of scope (documented): it refines the normal-theory *mean* SE and
  has no order-statistic analogue. `numpy`-only, import-light per the module charter (CASPER).
  Read-only/additive — same contract as #590; all committed-scenario KPIs verified byte-
  identical (all-scenarios kpi oracle).
- **Producer-side long-term-trend emission into the frozen wind export (#656, slice 4, opt-in, KPI-neutral).**
  Closes the loop opened by slice 3: a wind producer now MINTS the `long_term_trend` block that the
  finance-CLI Executive Workbook step decodes into the "ResourceTrend" sheet, so the sheet is
  producible end-to-end (no longer only from hand-/test-built exports). New
  `wind_resource.long_term_trend.build_resource_trend_export_block` computes the Mann-Kendall /
  Sen's-slope trend on an already-retrieved multi-year hub series and encodes it via the
  slice-3 `serialize_resource_trend` (exact inverse of the consumer decoder). It DEGRADES EXPLICITLY
  on a record shorter than `MIN_TREND_YEARS` (10 yr; IEC 61400-15-1 / MEASNET) — `{"analyzed": false,
  "reason": ...}`, never a spurious tau (CESSPIT). `WindPipeline.run_complete_assessment` gains an
  opt-in `analyze_trend` flag (DEFAULT OFF) that computes the block on the SAME series (no second CDS
  fetch) and attaches it under `long_term_trend`; `scripts/run_wind_analysis_v14.py`
  (`analyze_trend` in `conf/wind_analysis.yaml`, default false) surfaces it at the export top level so
  a frozen export captured from its stdout carries it. **Report/VALIDATE-only:** the block never
  touches the retrieved series, the committed AEP, or any KPI — the finance adapter reads only the
  `cashflow_export` contract — so every existing caller is byte-identical. (Also cleaned a
  pre-existing unused `sys` import in the wind CLI.)
- **Single-scenario Executive Workbook emission — a genuine live caller for `build_executive_workbook` (#656, slice 3, opt-in, KPI-neutral).**
  `analytics.executive_workbook.build_executive_workbook` shipped orphaned in PR #179 (its only
  caller was a unit test). This wires it into the canonical single-scenario CLI. New helpers
  `frames_from_pipeline_result` (assembles the five finance sheets — Summary / Cashflow /
  DebtService / Ratios / ScenarioSummary — from a plain `run_v14_pipeline` result; no financial
  value is derived, CCCDIR one-source) and `emit_executive_workbook_from_pipeline` (the live
  caller). `run_full_pipeline_v14.py` gains an opt-in Hydra step (`emit_executive_workbook`,
  default `false`; `executive_workbook_path`, default `<export_dir>/executive_workbook.xlsx`) that
  writes the workbook after a successful finance run and echoes the path under
  `result['executive_workbook_path']`. The long-term wind-resource trend reaches the optional
  "ResourceTrend" sheet by riding INSIDE the frozen wind export as a JSON-safe `long_term_trend`
  block — the finance CLI runs no live ERA5 (it stays cdsapi-free by design). `serialize_resource_trend`
  (producer encoder) and `resource_trend_df_from_wind_export` (consumer decoder) are exact inverses,
  so the tidy (Metric, Value) `summary_df` from `wind_resource.long_term_trend.analyze_long_term_resource`
  round-trips to the sheet unchanged. **Additive + default-off:** committed scenarios leave the step
  off, so all-scenario KPIs are verified byte-identical (all-scenarios kpi oracle). A producer-side
  emit (WindPipeline / era5 export carrying the trend block) is the natural next slice.
- **Project→equity IRR bridge in the lender report + OpenDSS-curtailment deferral ADR (#621, additive, KPI-neutral).**
  Two halves of the deferred/gated cluster.
  - **IRR bridge (built):** a new disclosure-only section that reconciles the engine's PUBLISHED
    project (unlevered) IRR to its published equity (levered) IRR, decomposing the leverage uplift
    into labelled legs — **leverage**, **cost of debt**, **tax shield** — plus an explicit
    **residual**. New frozen contracts `analytics.contracts_v14.IrrBridgeComponent` /
    `ProjectEquityIrrBridge` (CCCDIR — result types centralised) and builder
    `analytics.irr_bridge.build_project_equity_irr_bridge[_from_run]`. All IRR arithmetic is
    delegated to `finance.irr` (R7 single source of truth); the two endpoints are the headline
    KPIs and are never recomputed — the legs only *explain* the gap. Each leg is one substitution
    step on the engine's own published per-year figures (`cfads_usd` / `interest_usd` /
    `effective_tax_rate` and the authoritative equity return vector), and the residual is the
    closing term so that `sum(legs) + residual == equity_irr − project_irr` **exactly** (asserted
    at build time — CESSPIT; IRR is non-additive, so the residual honestly carries the interaction
    plus principal timing, covenant lockup, DSRA, WHT and terminal value). Wired into the lender
    report via a new `run_result` argument to `app.reports.report_model.build_report_context`
    (rendered as "Project → Equity IRR Bridge" with a new signed-percentage-point formatter
    `fmt_pp`). **Additive + default-off:** the section renders only when the caller supplies the
    full run result AND it carries a computed equity distribution; absent that, the section is
    omitted and no headline KPI is touched. All committed-scenario KPIs verified byte-identical
    (all-scenarios kpi oracle).
  - **OpenDSS power-flow curtailment (deferred):** recorded as an ADR
    (`docs/OPENDSS_CURTAILMENT_DECISION.md`) per the adapt+defer verdict — do NOT build the
    OpenDSSDirect integration (no CEB feeder data, no new hard dependency). The gate: real feeder
    data **and** explicit user authorization for the `OpenDSSDirect.py` dependency **and** a
    default-off config gate. The existing energy-balance shared-POI seam
    (`analytics/portfolio/poi_curtailment.py`) is preserved unchanged
    (`resolve_shared_poi_curtailment` still returns `None` absent the opt-in config).
- **Morris optimal-trajectories mode + SA method-selection decision tree (#617, opt-in, KPI-neutral).**
  `analytics.sensitivity.global_sa.run_morris` gains an optional `optimal_trajectories:
  Optional[int] = None` knob forwarded to SALib's `morris.sample`. When set, SALib draws
  `n_trajectories` candidate trajectories and keeps the `optimal_trajectories` subset with the
  widest spread in the input box (Campolongo/Ruano enhancement), dropping the cost from
  `n_trajectories·(D+1)` to `optimal_trajectories·(D+1)` evaluations while covering more of the
  space — the OSeMOSYS "10-from-100 at step-size-4" guidance. The chosen value is recorded in
  the result metadata next to `n_trajectories` / `n_runs`. `scripts/run_global_sensitivity.py`
  exposes a Morris-only `--optimal-trajectories` flag (fail-loud usage error if combined with
  `--method sobol`).
  - **Fail-loud validation (CESSPIT, no silent clamping).** `run_morris` raises `ValueError`
    unless `2 <= optimal_trajectories < n_trajectories`; it validates itself rather than defer
    to SALib, whose own bound check is inconsistent (it silently accepts `0`).
  - **DEFAULT OFF = byte-identical (#617).** `optimal_trajectories=None` is the vanilla Morris
    path: the SALib sampling call is verified byte-identical to the prior no-kwarg call, so the
    lender report's Morris SA section and all committed-scenario KPIs are unchanged. MRM-01: the
    subset selection is seeded (deterministic for a fixed `seed`).
  - New `docs/SENSITIVITY_DECISION_TREE.md` documents the SA method funnel (Morris screen →
    Sobol on the top subset → PAWN cross-check → local tornado), cross-linked from the
    `global_sa` module docstring.
- **Conditions-precedent (CP) checklist register — first slice of the feasibility-report generator (#616, config-first, soft-by-default, KPI-neutral).**
  New `analytics.conditions_precedent` adds the config-first data model for a DFI/lender
  conditions-precedent checklist: the discrete named line items that must be satisfied (or
  explicitly waived) before first drawdown / financial close — e.g. `ppa_executed`,
  `esia_approved`, `epc_contract_signed`, `security_package_perfected`. This is finer-grained
  than the development-readiness R/A/G register (`analytics.development_readiness`, which rolls
  a whole workstream to one status): the CP checklist tracks each named condition to a
  satisfied / waived / pending state and reports how many CPs remain outstanding (and so gate
  drawdown), rolled up overall and per workstream.
  - The taxonomy (satisfaction scale, canonical CP workstreams, and named CP items) lives in
    `config/conditions_precedent.yaml`; the enforcement policy resolves
    `scenario conditions_precedent.{enforce,require_complete}` → `config/defaults.yaml`
    `defaults.conditions_precedent.*` (CESSPIT / CCCDIR — no Python literals). Mirrors the
    development-readiness (#C11) and evidence-register (#C5) patterns.
  - **Soft by default, DEFAULT OFF** (`enforce: false`, `require_complete: false`). A scenario
    with no / partial checklist is reported on, never broken; `validate_conditions_precedent`
    is a pure detector (raises / warns / no-ops) wired into the same three seams as the
    readiness / evidence guards (`analytics.scenario_loader`, `api.pipeline_api`,
    `app.services.pipeline_service`). It changes no computed number. No committed scenario
    declares a `conditions_precedent` block, so all-scenarios KPIs are byte-identical
    (verified via the all-scenarios kpi oracle).
  - Registered in the central config schema (`RequiredFieldSpec`, module `conditions_precedent`,
    optional / warning-only) so it appears in the lender schema export.
  - This is slice 2 of 5 of the feasibility-report generator (#616). The remaining slices
    (20-section feasibility schema, IC executive summary + red-flag section, bankability
    evidence-completeness score, route/template wiring) are tracked as follow-up issues.
- **`MonteCarloResult.sampling_method` is now populated from the sampler actually used (#648a, provenance wiring, KPI-neutral).**
  The `sampling_method` field on `MonteCarloResult` (`analytics.contracts_v14`) existed but was
  never set, so every result reported the `None` default while the sampler identity lived only in
  the loose `metadata["sampler"]` dict (`"lhs"` or the opt-in `"sobol"`). `aggregate_trials`
  (`analytics.mc.aggregate`) now passes `sampling_method=meta.get("sampler")` into the result on
  BOTH the canonical LHS and the opt-in Sobol path, so the lender-facing MC risk blocks can
  attribute the bands to their generation method as a first-class field (CCCDIR). Pure additive
  metadata: the deterministic pipeline KPI oracle is byte-identical across all committed scenarios
  (they run LHS), and no config interpretation changes — the dead `monte_carlo.sampling_method`
  config key retirement remains gated in #648.
- **Opt-in solar frozen-export ingestion in the canonical CLI (#614, default OFF, KPI-neutral).**
  `run_full_pipeline_v14.py` + `conf/run_full_pipeline_v14.yaml` gain the opt-in,
  default-null Hydra keys `solar_assessment_json` (+ `solar_adapter_mode` /
  `solar_tolerance_pct` / `solar_export_scenario` / `solar_technology`), the photovoltaic
  analogue of the Sprint-19 wind ingestion path. When set, the CLI consumes a **frozen**
  solar export through the pvlib-free
  `solar_resource.cashflow_adapter.solar_export_to_scenario_patch` — patching the per-tech
  `generation.technologies.<tech>` block and re-blending `project.capacity_factor` — with
  semantics matching `app/services/pipeline_service.run_integrated_case` (it chains AFTER any
  wind patch). `compute_solar_aep` / `pvlib` are NEVER imported in the finance path, and
  there is deliberately no solar auto-orchestrate analogue: lender-grade runs consume an
  audited frozen export (CASPER/frozen-export design). Ingestion failures fail loud with a
  structured error JSON (`status='error'`, `phase='solar_resource_ingestion'`, or
  `error_type='SolarAdapterDriftError'` with `solar_value`/`drift_pct`) and exit 1 before
  finance. This closes #614's "or document" alternative — hybrid solar parity is via the
  frozen export, not a producer re-run. DEFAULT ABSENT = byte-identical: no committed
  scenario passes a solar export, verified via the all-scenarios KPI oracle (all 27 scenarios
  unchanged).
- **P90 (downside) debt-sizing detail surfaced in the lender report (#613, render-when-present, KPI-neutral).**
  The lender pack already renders "Binding sizing constraint … (P50/P90)" by default for
  every `debt_sizing: dual_dscr` scenario (`report.html.j2` via `api.pipeline_api._extract_debt`);
  #613 was a verification issue confirming that and closing the residual gap: for a scenario
  that opts into the downside-binding solve (`Financing_Terms.bind_downside`), the underlying
  P90 sizing detail was computed in the engine but never serialised, so its lender pack showed
  only the "(P90)" tag without the two gearing solves. `api.pipeline_api.DebtBlock` +
  `_extract_debt` now carry the optional additive fields `solved_gearing_p50`,
  `solved_gearing_p90`, `target_dscr_p90`, `downside_ratio`, `downside_source` — pure
  serialisation from `debt_result['dual_dscr']`, no finance logic — and the template renders
  the "Gearing solves (P50 / P90)", "P90 target DSCR" and "Downside CFADS ratio (P90/P50)"
  rows only when the P90 solve is present. `finance.debt_v14._maybe_autosolve_dscr` now also
  records the resolved `target_dscr_p90` on the `dual_dscr` detail (a pure metadata write,
  only when `bind_downside` is active). DEFAULT ABSENT = byte-identical: no committed scenario
  gains `bind_downside`; the default P50-only lender report is unchanged (the P90 rows stay
  omitted), and only the one committed scenario that already opts in
  (`dutchbay_hybrid_windsolar_2025Q4.yaml`) shows the new detail. All committed-scenario KPIs
  verified byte-identical (all-scenarios kpi oracle).
- **Opt-in MERRA-2 second-source cross-validation of the ERA5 wind resource (#612, disclose-don't-mutate, KPI-neutral).**
  New `wind_resource.crossval` runs a VALIDATE-mode sanity check of an independent reanalysis
  (MERRA-2) against the declared ERA5 baseline — the same disclose-don't-mutate contract as
  `wind_resource.arco_assessment` / `wind_resource.mcp`. `build_crossval_assessment` takes an
  **injected** second-source hub-height wind series, fits a Weibull, runs the canonical AEP
  engine on that fit for the *implied* CF/AEP, and returns a `mode:"validate"` disclosure block:
  the Weibull drift vs the declared `wind_resource.weibull_a/k` and the mean-ws / CF / AEP
  deviation vs the frozen `resource.wind` headline. It NEVER writes `wind_resource.*`,
  `resource.wind.*`, or the frozen AEP export — adopting a second source stays a deliberate,
  dated re-baseline.
  - **Strictly opt-in, DEFAULT OFF (CESSPIT).** `crossval_settings` returns `None` unless
    `resource.crossval.enabled` is true, so scenarios without the block are byte-identical (the
    disclosure block simply does not exist). Registered via the `RequiredFieldSpec` pattern
    (`analytics.wind.crossval_interface_schema`, module `"crossval"`) and auto-enforced by
    `schema_guard.validate_config_for_v14` ONLY when `resource.crossval` is declared — mirroring
    the existing wind/era5 auto-enforce hook. All committed-scenario KPIs verified byte-identical
    (all-scenarios kpi oracle).
  - **MERRA-2 is the implemented second source for the Sri Lanka flagship site** via the
    no-authentication NASA POWER hourly endpoint (`fetch_merra2_series`) or a user-supplied local
    series file; the `requests` import is CASPER call-time-guarded (no new import-time dependency).
    NEWA is documented as EU-coverage-only and is a labelled `source_type` only — never fetched
    (`load_reference_series` raises for it, pointing to a local series instead). No credentialed or
    paid API is used. Core comparison functions take injected `pd.DataFrame` series so CI exercises
    the whole path with ZERO network (the live fetch is monkeypatched at the `requests` boundary).
  - **Registry-clearing hardening in `schema_guard._ensure_module_registered`:** when a mapped
    interface module is already imported but its specs are absent from the process-global registry
    (e.g. a test snapshots/restores `config_schema._REGISTRY`, or evicts the `analytics.*` graph),
    the module is now `reload`-ed to re-run its import-time registration. Behaviour-neutral in the
    normal single-import lifecycle (the branch only fires when specs are missing), and it re-registers
    ALL python modules backing a multi-module logical name (e.g. `cashflow`).
- **Opt-in NREL-BLAST separable calendar+cycle BESS aging curve (#606, opt-in, KPI-neutral).**
  `finance.bess_revenue` gains a `revenue.soh_model` selector: the default (absent) `geometric`
  keeps the compounding `(1 − mdsc_fade_pct_annual)^t` state-of-health curve unchanged, while
  the new `separable_calendar_cycle` models calendar aging (loss ∝ time) and cycle aging
  (loss ∝ equivalent-full-cycle throughput = `cycles_per_year × depth_of_discharge`) as a
  linear superposition — the NREL **BLAST** decomposition used by SAM. New `revenue.*` keys
  `calendar_fade_pct_annual` and `cycle_fade_pct_per_efc` get fail-loud CESSPIT validation
  (non-numeric / out-of-`[0,1)` / a combined annual rate outside `[0,1)` raise with the full
  config path); the two models are mutually exclusive (mixing `mdsc_fade_pct_annual` with the
  separable keys, or an unknown `soh_model`, raises — no silent precedence). The `mdsc_floor_soh`
  floor and `augmentation_schedule` origin-reset semantics apply identically to both models.
  The curve is honoured by BOTH consumers through the single source of truth
  `mdsc_soh_for_year`: the resolver collapses the separable channels into one annual rate stored
  on the spec and threaded through `LcosSpec` / `resolve_lcos_specs` / the `compute_lcos`
  `soh_lookup`, so the cashflow revenue path and `finance.bess_lcos` can never diverge. The
  per-model depth-of-discharge defaults are now imported by `bess_lcos` from `bess_revenue`
  (single source of truth). DEFAULT OFF = byte-identical: both committed BESS scenarios
  (`ceb_bess_10mw_capacity_charge.yaml`, `ceb_solar_bess_nightpeak_10mw.yaml`) keep the
  geometric curve, and all committed-scenario KPIs are verified byte-identical (all-scenarios
  kpi oracle).
- **TCFD-aligned climate-risk fields in the risk / evidence register (#607, additive, KPI-neutral).**
  `RiskItem` (config) and its render twin `RiskRow` gain an OPTIONAL
  `climate_risk_category: physical | transition` field (pydantic `Literal`, `extra="forbid"`
  preserved) threaded through `_build_risk_register`; the report template renders a TCFD tag
  in the Risk Register only when the field is present (untagged rows render unchanged), so
  every existing config still loads. `config/evidence_register.yaml`'s `material_assumptions`
  taxonomy gains a `climate_risk` (CCRA-exists) entry, matching Equator Principles 4's
  mandatory TCFD-structured Climate Change Risk Assessment; enforcement stays soft
  (`enforce=false`, `require_complete=false` in `config/defaults.yaml`), so a scenario without
  a CCRA entry is warn-only, never blocked. The committed `report_defaults.yaml` tags
  Resource/Curtailment as `physical` and Regulatory/Tariff as `transition`; the lendercase
  scenario declares an honest `assumption`-tier `climate_risk` entry (analyst screen, not a
  commissioned CCRA). Pure detector + presentation — committed-scenario KPIs are byte-identical.
- **Scenario-YAML wiring for `resource.solar.uncertainty` (#604, opt-in, KPI-neutral).**
  `SolarResourceConfig.from_scenario` now accepts an OPTIONAL `resource.solar.uncertainty`
  mapping instead of rejecting it as an unknown key, closing the wind/solar asymmetry (wind
  already reads `resource.uncertainty`). The new pure helper
  `solar_resource.exceedance.solar_uncertainty_from_config` peels the `p50_haircut_pct` /
  `correlation` / `life_years` exceedance knobs off the block before building the
  `SolarUncertaintyBudget` (mirroring `analytics.wind.aep_summary_builder._uncertainty_from_config`);
  unknown budget keys still fail loud, now at config construction (CESSPIT pre-flight).
  `compute_solar_aep` consumes the block when `emit_exceedance=True` with precedence
  explicit kwarg > scenario block > module default (its exceedance kwargs are now
  `None`-sentinel defaults). DEFAULT ABSENT = byte-identical: no committed scenario carries
  the block, `emit_exceedance` stays default-False, and the absent-block solar haircut
  default remains **0.0** — the wind-side no-EYA `RECOMMENDED_P50_HAIRCUT_PCT` policy
  default (#587) deliberately does NOT port to solar (a separate user/policy decision).
  All committed-scenario KPIs verified byte-identical (all-scenarios kpi oracle).
- **Opt-in pymoo NSGA-II backend for the multi-objective Pareto optimizer (#603).**
  `analytics.sensitivity.optimizer.run_pareto_search` now accepts `plan_kind="pymoo"`: an
  adaptive NSGA-II search over each swept parameter's `[min(values), max(values)]` range,
  for >=2-parameter trade-offs (e.g. tariff vs gearing) where the Cartesian `grid` plan
  explodes past `max_points` and a coarse grid or the lightweight `lhs` sampler
  under-resolves the frontier.
  - Evaluation stays exclusively on the `analytics.evaluation_v14.evaluate_with_overrides`
    gateway (CCCDIR); results reuse the existing `ParetoPoint`/`ParetoResult` contracts, and
    the frontier is recomputed over ALL evaluated points with the module's own
    `pareto_frontier()`, so dominance semantics are identical to the `grid`/`lhs` plans.
  - Deterministic given `seed` (MRM-01); the process-global `random`/`numpy.random` states
    pymoo seeds are snapshot and restored around the run. The evaluation budget is
    `n_samples` (enforced `<= max_points`, keeping `max_points` the hard cap), shaped as
    `pop_size x n_gen` generations so the engine is never called more than `n_samples` times.
    A new keyword-only `pop_size` argument (default 32) shapes the population and is ignored
    by `grid`/`lhs`.
  - CASPER: pymoo is OPTIONAL — call-time `_require_pymoo()` guard mirroring
    `_require_salib` (actionable install message), import-safe module, and a new `[pareto]`
    extras group in pyproject (`pip install -e ".[pareto]"`); the base finance install and
    the default `grid`/`lhs` paths never import pymoo. Backend tests are
    `pytest.importorskip("pymoo")`-gated; the missing-dependency fail-loud path is tested
    without pymoo.
  - DEFAULT OFF / KPI-neutral: no committed scenario or caller selects the backend; all
    committed-scenario KPIs are oracle byte-identical.
- **Opt-in `method="bounded"` scalar optimizer mode in `optimize_parameter` (#602).**
  `analytics.optimization_v14.optimize_parameter` now accepts `method="grid"` (default — the
  unchanged exhaustive `np.linspace` sweep) or `method="bounded"`, which refines the constrained
  optimum with `scipy.optimize.minimize_scalar(method="bounded", bounds=(lower, upper))` over the
  same `evaluate_with_overrides` gateway (CCCDIR — no finance logic reimplemented; scipy is already
  a core dependency). Constraint-infeasible evaluations (judged with the same `_bound_slack`
  tolerance the grid path uses) and non-finite objectives are penalized with a large finite value
  so the search is steered back into the feasible region, and the converged point is re-checked:
  `best` is `None` if the solver converged on a penalized point — an infeasible point is never
  silently returned. Fail-loud validation (CESSPIT): unknown `method`, non-finite or inverted
  brackets, and invalid `bounded_xatol`/`bounded_maxiter` raise `ValueError`; non-convergence
  within `bounded_maxiter` raises `RuntimeError`. The search is deterministic (Brent/golden
  section, no randomness); `curve` holds the evaluation trace in evaluation order. Validated by
  analytic-optimum convergence tests (interior max/min, penalization wall, all-infeasible,
  NaN-objective, determinism) and a grid-vs-bounded cross-check on the committed lender case's
  DSCR-sculpt plateau, where the boundary-optimum divergence (bounded searches the open interval,
  the grid evaluates endpoints exactly) is documented and bounded at ~1e-4 IRR. Default
  `method="grid"` keeps all existing callers byte-identical; committed-scenario KPIs verified
  byte-identical via the multi-scenario kpi oracle (19 KPI-bearing scenarios).
- **Opt-in Gaussian-copula dependence for MC correlation (#601, default off — KPI-neutral).**
  `monte_carlo.correlation.method` now dispatches: the default `iman_conover` path is
  bit-identical to the previous single-path code (pinned by a reference-algorithm test and
  verified byte-identical via the all-scenarios KPI oracle), while `method: gaussian_copula`
  opts into Gaussian-copula dependence built from EXACT normal scores — the raw draws are
  whitened against their own sample covariance and recorrelated, so the scores carry the
  target correlation exactly instead of Iman-Conover's O(1/sqrt(n)) approximate Spearman
  (SOTA link-research digest correction). The quantile map onto each driver's empirical
  marginal reduces to a gather-by-rank, so marginals are preserved exactly; seeded
  determinism is pinned (MRM-01). Honest limitations documented in the docstring: the matrix
  parameterizes the LATENT-NORMAL scale (induced Spearman = (6/pi)*arcsin(rho/2), e.g. 0.60
  induces ~0.582, a distortion BOTH methods share), and a Gaussian copula has ZERO asymptotic
  tail dependence — the issue's tail-crisis motivation (FX-crisis x curtailment) requires a
  t-copula, an explicit non-goal left as a follow-up. `gaussian_copula` requires
  n_trials > n_params (fails loud). Unrecognized `correlation.method` values (e.g.
  `cholesky`) now FAIL LOUD at apply time instead of silently running Iman-Conover while the
  config claims another structure (CESSPIT); the engine's Sobol'+correlation warning now
  names the active method. No committed scenario sets a non-default method.
- **P99 (and P1) first-class in the Monte Carlo default percentile set (#599, additive-only,
  committed KPIs byte-identical).** `analytics.mc.aggregate` now exposes `DEFAULT_PERCENTILES =
  (1, 5, 10, 50, 90, 95, 99)` — extending the previous `(5, 10, 50, 90, 95)` default — because
  senior-debt loan-size capping is conventionally set at P99. Tail direction is handled
  explicitly per the #563 exceedance convention in `analytics.mc.exports`: the keys are RAW
  percentiles, so for higher-is-better metrics (DSCR/IRR/NPV/LLCR/PLCR) the lender's downside
  "P99" is the raw **1st** percentile (key `1`, shipped alongside), while the raw 99th (key `99`)
  is the upside tail — the raw 99th must never be reported as downside P99. Additive-only proof:
  each requested percentile is computed independently (`np.percentile` per level), so every
  pre-existing percentile key/value is unchanged (empirically verified: 0 removed / 0 changed,
  additions only at levels 1 and 99). Scenarios pinning `monte_carlo.percentiles` are unaffected —
  all committed lender/capex scenarios pin `[10, 25, 50, 75, 90]` (byte-identical, verified); the
  two committed scenarios WITHOUT a pin (`dutchbay_mc_enhanced_2025Q4.yaml`, which has no
  `monte_carlo` block at all, and `dutchbay_sprint17_enhanced.yaml`, whose legacy block has no
  `monte_carlo.parameters`) cannot produce MC artifacts through the canonical engine (fail-fast
  `MonteCarloConfigError` before aggregation, unchanged) and so needed no pin; the wind-resource
  MC (`config/wind_dutchbay_150mw.yaml`) computes its own percentiles and never consumes this
  default. The deterministic KPI surface is outside the MC aggregator entirely (kpi-oracle
  byte-identical across all committed scenarios).
- **BESS LCOS advisory sanity band vs PNNL ESGC 2024 / Lazard LCOS v10.0 non-ITC (#605, report-only).**
  `analytics.cost.benchmark.lcos_benchmark()` (mirroring `capex_benchmark`) checks the computed
  read-only LCOS (`finance.bess_lcos`) against the **USD 115–254/MWh non-ITC literature band**
  (Lazard LCOS v10.0, June-2025 LCOE+, unsubsidised — Sri Lanka has no US ITC; methodology
  cross-anchored to PNNL ESGC 2024). The band, source labels, and vintage are config-sourced from
  `defaults.cost_reference` in `config/defaults.yaml` (CCCDIR — no Python-literal anchors). Each
  per-BESS LCOS dict in the `ScenarioAnalytics` batch view gains an **additive** `benchmark`
  advisory (`within_band`/band/sources/note); an out-of-band LCOS **logs a WARNING citing the
  sources** — no raise, no value change — and an undefined LCOS (`None`, e.g. zero discharged
  energy) yields an explicit not-comparable note (`within_band: null`), never a crash or silent
  zero. Joins the fixed-dispatch limitation notes from #596: the model's LCOS is a fixed-cycling
  basis, so an out-of-band value is a review prompt, not an error. Every existing reported
  `lcos_usd_per_mwh` value and all committed-scenario KPIs are byte-identical.
- **Wind artifact hygiene (#618, KPI-neutral: committed scenarios byte-identical, frozen AEP artifacts untouched).**
  Three fixes on the `wind_resource` timeseries-diagnostic path (finance reads the frozen
  `aep_summary` JSON, so lender KPIs cannot move):
  - **Version strings**: `wind_resource.__version__`, the `ERA5Fetcher`/`WindPipeline`/
    `EnergyCalculator`/`WindAnalyzer` init logs, the ERA5 download-metadata `version` field and the
    `WindPipeline` results-metadata `version` field now derive from
    `analytics.run_manifest.engine_version()` (the repo `VERSION` file) instead of the stale
    hardcoded `1.0.0`/`1.1.0 (CCCDIR Compliant)` literals (runtime JSON artifacts now stamp e.g.
    `15.2.0`). Owned here per the #584 hand-off; a source-scan test fences the literals out.
  - **`resource.uncertainty.*` plumbing**: `EnergyCalculator.calculate_net_aep` builds its IEC
    61400-15-2 exceedance budget from an optional `uncertainty` mapping (new constructor knob,
    passed through `WindPipeline`) via a new shared, policy-free sigma parser
    `wind_resource.bankable_aep.budget_from_mapping` — the same parser
    `analytics.wind.aep_summary_builder._uncertainty_from_config` now delegates to, so the two
    consumers cannot drift. `correlation` and `life_years` are honoured; **`p50_haircut_pct` is
    deliberately NOT applied on this path** (kernel 0.0 pinned; a declared key is logged, not
    silently used) — the builder-vs-kernel haircut-policy question remains the user-gated #653 and
    is NOT settled here. Absent config = the previous `UncertaintyBudget()` defaults, exactly.
  - **Air density on timeseries AEP**: `EnergyCalculator.calculate_gross_aep` (and the monthly
    profile, for consistency) now applies the IEC 61400-12-1 velocity correction
    `(rho_site/rho_ref)**(1/3)` when `air_density_site_kgm3` is supplied (new constructor knobs,
    `ref` defaulting to the IEC 1.225 kg/m^3), matching the bankable path's
    `density_velocity_factor`; absent = factor 1.0, no correction — parity with
    `aep_summary_builder`'s fallback when a scenario declares no densities. The factor used is
    disclosed in the gross-AEP result.
- **FX forward hedging modelled in the cashflow engine (#652/#659, user-authorized KPI-capable feature).**
  Two optional `fx` config levers let a scenario replace part of its per-year LKR→USD conversion with a
  locked covered-interest-parity (CIP) forward rate instead of the projected spot:
  - `fx.hedge_ratio` (decimal 0.0–1.0, default **0.0**): fraction of each year's LKR CFADS/revenue
    converted at the forward.
  - `fx.spread_bps` (basis points, ≥0, default **0.0**): hedging cost loaded onto the forward as
    `forward · (1 + spread)`.

  The engine is USD-equivalent-numeraire, so FX risk enters only where LKR CFADS becomes `cfads_usd`
  (the stream debt sizing and DSCR run on, `finance.debt_v14`). The conversion is now a blend,
  `cfads_usd = (1−h)·(cfads_lkr/spot_t) + h·(cfads_lkr/(fwd_t·(1+spread)))`, applied consistently in
  both `calculate_single_year_cfads` and `build_annual_rows_efficient` (the two builders remain
  identical). The forward curve is CIP,
  `fwd_t = spot_0 · ((1+r_lkr)/(1+r_usd))^t`, anchored on the same `spot_0` the spot path uses; `t=0`
  yields spot. `(r_lkr, r_usd)` are resolved from `Financing_Terms.rates` using the **same key priority
  and normalization as `finance.debt_v14._solve_mix`** (`lkr_nominal`/`lkr_min`;
  `usd_nominal`/`usd_commercial_min`) — the forward uses the rates the facility is actually serviced at.
  A hedge with unresolvable rates fails loud; `fx.hedge_ratio`/`fx.spread_bps` are range-validated in
  both `finance.cashflow_v14_params.validate_parameters` and the strict `analytics.schema_guard`
  pre-flight gate (CESSPIT).

  - **Byte-identity:** at `hedge_ratio = 0` (the default) the blend is never evaluated — the original
    `value_lkr / spot` arithmetic is returned unchanged — so all committed scenarios are
    **kpi_oracle byte-identical (argv-correct, verified across all 27 committed scenarios)**. The
    feature is inert until a scenario opts in.
  - **Direction (verified, canonical lender case):** the CIP forward drift `(1+r_lkr)/(1+r_usd)−1`
    ≈ **5.48%/yr** is fractionally **below** the projected spot drift `fx.annual_depr` = **5.89%/yr**,
    because the committed `lkr_nominal` (13.39%) was itself built as additive UIP (usd 7.5% + drift
    5.89%). The forward is therefore slightly *less* depreciated than spot, so hedging yields marginally
    *more* USD and **raises** project IRR (2.68% → 2.94% at full hedge) / NPV / LLCR. `min_dscr` is
    invariant at the 1.30 target because debt auto-sizes to it (the effect surfaces in IRR/NPV/LLCR).
    This corrects the original design assumption that hedging would lower returns, which presumed
    `r_usd ≈ 6%`; with the scenario's own rates the FX forward is near a wash — the LKR rate already
    prices the depreciation via UIP.
  - **Limitations:** the CIP forward uses the project's LKR/USD *debt* rates (not risk-free money-market
    rates) as the parity inputs, a deliberate, auditable simplification (the rate the borrower actually
    transacts at). Hedge behaviour is pinned end-to-end by an integration regression test that overlays
    the lever on the live lender case (`tests/integration/test_fx_hedge_lendercase.py`), avoiding a
    duplicated hedged scenario fixture.
- **BESS LCOS fixed-dispatch limitation note extended to the energy-tariff model (#596,
  documentation/notes only, KPI-neutral).** `finance.bess_lcos.resolve_lcos_specs` now appends a
  fixed-dispatch-basis note for `model: energy_tariff` (a fixed `cycles_per_year` at full nameplate
  energy per cycle — RTE/SoH-derated, no depth-of-discharge factor, the post-M1/#557 revenue-export
  basis), mirroring the existing capacity-charge cycles-at-DoD note; the note surfaces additively in
  `LcosResult.notes` / `as_dict()` and hence in the analytics `bess_lcos` report block. The module
  docstring's LIMITATIONS block now states, for BOTH revenue models, that dispatch is not simulated
  or optimised — the fixed `cycles_per_year` basis is a known, intentional simplification versus
  2025–2026 MILP/stochastic dispatch-optimisation LCOS — and the discharged-energy formula reflects
  the model-gated `dod_factor` (M1) instead of an unconditional `depth_of_discharge`. No numeric
  field of `LcosSpec`/`LcosResult` changes; all committed KPIs byte-identical.

### Fixed
- **Long-term trend block is JSON-serializable on the `run()` success path (#656, KPI-neutral).**
  With `analyze_trend=True`, `wind_resource.era5_retrieval.run()` attached the raw `TrendResult`
  dataclass and a pandas `DataFrame` under `result["long_term_trend"]`, so `main()`'s
  `print(json.dumps(result))` crashed with `TypeError: Object of type TrendResult is not JSON
  serializable` **after** the full CDS retrieval + analysis. `run()` now attaches a **JSON-safe
  projection** (`dataclasses.asdict(trend)`; `summary_df.to_dict(orient="records")`; markdown /
  `period_aep` / `recommendation` pass through verbatim), so the whole result round-trips through
  `json.dumps` and downstream JSON consumers get clean data. The rich objects remain available to
  `report_model` via a direct `analyze_long_term_resource` call (that consumer wants the dataclass
  + DataFrame). The `analyzed: false` short-series shape and the disclose-don't-mutate invariant
  (committed AEP identical with the trend on/off) are unchanged; default-off all-scenarios KPIs
  remain byte-identical.
- **`SOLVER_REGISTRY['target_equity_irr']` no longer silently solves the WRONG KPI (#615, KPI-neutral).**
  The registry key `target_equity_irr` pointed at `solve_for_tariff_given_irr`, which was
  hardcoded to the `project_irr` KPI — so `get_solver("target_equity_irr")(…)` returned the
  tariff for a target PROJECT IRR while claiming to target equity IRR. It now resolves to the
  new `solve_for_tariff_given_equity_irr` (equity-IRR-pinned), which fails loud when the
  scenario computes no equity distribution. These solvers have no committed-scenario caller, so
  the KPI oracle is byte-identical; the fix corrects an analyst-facing answer, not a model KPI.
- **Global SA: shared finite-mask stops a partial-NaN metric column poisoning Sobol/Morris/PAWN
  indices (#644, KPI-neutral).** A metric column with SOME non-finite entries (an engine KPI
  returning `None` on a subset of sample rows) passed the `_is_flat_output` guard — which inspects
  only finite values — and fed NaNs straight into SALib `analyze`, yielding all-NaN indices plus a
  fabricated insertion-order `ranking` (`sorted()` over NaN keys). All three runners in
  `analytics.sensitivity.global_sa` now mask non-finite outputs BEFORE `analyze` via a shared
  helper (`_apply_finite_mask`) that respects each estimator's sample design: **Sobol** drops whole
  Saltelli blocks (`D+2` rows, `2D+2` with second order) and **Morris** whole trajectories
  (`D+1` rows) containing any non-finite output — never single rows, which would corrupt the
  A/B/AB and elementary-effect pairing (verified against SALib 1.5.2's block indexing) — while the
  given-data **PAWN** masks row-wise. Masking is deterministic (a pure function of the output
  vector, MRM-01) and loudly disclosed (CESSPIT): a `logger.warning` carries the metric name and
  dropped block/row count + share, and a `masked` disclosure dict is attached to the per-metric
  result. Documented thresholds (the issue names none): above a 10% dropped share the warning
  escalates; above 50% the metric is flagged **`nan_poisoned`** with zeroed indices (the NaN
  analogue of `flat_metric`, logged at ERROR) instead of analyzing an unrepresentative residue —
  flag-not-raise, so one poisoned metric cannot destroy the other metrics' indices in the same
  run. The all-NaN column still resolves via `_is_flat_output` (unchanged), clean-data index
  values are bit-identical to a direct SALib `sample->analyze` (pinned by test), and all committed
  scenarios are **kpi_oracle byte-identical (argv-correct)** — the guard is unreachable on the
  committed lender case, whose worst-corner KPIs are all finite.

  **Report layer (Fable-review blocker):** the lender report's Global-SA adapter
  (`app.services.report_global_sa.compute_report_global_sa`) previously read only
  `drivers`/`ranking` and stripped the flags, so a flagged metric's ZEROED placeholder drivers
  rendered a "Global Sensitivity — Morris Screening" section with every driver at 0.00% and no
  caveat — a confident false claim (e.g. "FX does not influence the IRR"). The adapter now takes
  its documented CASPER degrade path for a `nan_poisoned` — and, same placeholder shape, a
  `flat_metric` — target metric: it returns `None` (section omitted, engine reason logged),
  pinned end-to-end (adapter returns `None`; the template's existing `if ctx.global_sa` guard
  omission is already pinned). Two same-surface refinements from the same review: a flagged
  (`flat_metric`/`nan_poisoned`) Sobol metric now carries `interactions_present=None` ("not
  computed") instead of a definitive `False` no index backs (the CLI's truthy check degrades
  identically), and the masking disclosures pluralize their sample unit correctly
  ("trajectories", not "trajectorys").
- **MC CLI artifact no longer carries two conflicting `n_trials` (#647, KPI-neutral).** On the
  opt-in `monte_carlo.sampler: sobol` path (#589) a non-power-of-two trial request is rounded UP
  to the next 2**m and ALL points are evaluated; the engine already stamped the evaluated count in
  `metadata.n_trials` (plus the `sobol_n_requested`/`sobol_n_used` disclosure pair when they
  diverge), but `cli_monte_carlo_hydra` kept echoing the REQUESTED count at the payload/artifact
  top level — one `monte_carlo_summary.json` told two different trial-count stories. The CLI now
  sources the top-level `n_trials` (and the completion log line) from `result.metadata`, so
  top-level == metadata == trials actually run, with the original request still disclosed via
  `metadata.sobol_n_requested`. The pre-run error payload keeps the requested count (no result
  exists there — now commented as such). Default `lhs` path is untouched (requested == used);
  no other code reads the artifact's top-level `n_trials` (verified). Pinned by a CLI-level
  subprocess test (`tests/analytics/test_mc_sobol_sampler.py`) driving a 12→16 Sobol run and
  asserting stdout payload + written artifact agree with metadata.
- **Fail-loud-erosion cluster: silent-swallowing finance helpers hardened (#585, KPI-neutral).**
  Five verified erosions of the fail-loud stance closed; all committed scenarios verified
  **kpi_oracle byte-identical (argv-correct, 19/19 KPI-bearing scenarios)** — each fix only converts a
  previously-silent malformed/missing input into a raise or WARNING:
  - `finance.cashflow_v14_utils.as_float`/`as_int` now **raise `ValueError` on a present-but-malformed
    value** (e.g. `"12,5"`, a mapping) instead of silently returning the default; `None` still yields
    the default. A silent fallback here could move a tax/capex base with no trace (the call sites are
    precedence chains). The `as_float_or_none`/`as_int_or_none` probe variants keep their documented
    swallow semantics — the project-life heuristic tree-walk and capacity candidate scans depend on
    them (pinned by test). The `finance.utils` twin module (used by `debt_v14`/`epc_helper_v14` with
    explicit engine defaults) is out of this issue's scope and unchanged.
  - `validate_parameters` converts the new `as_int` raise for a malformed `tax.depreciation_years`
    into a **field-named validation error** (previously a malformed value silently PASSED validation);
    the validator keeps its report-all contract.
  - `finance.debt_v14` `amortization_style` is now **whitelisted** (`annuity`/`fixed` → annuity;
    `sculpted`/`auto` → DSCR-sculpted) mirroring the `balloon_treatment` whitelist. `auto` — used by
    committed scenarios — is an explicit, documented sculpted alias, not a fall-through accident; an
    unknown style WARNs and falls back to sculpted (exactly the old silent behaviour, now loud).
  - The compact `debt:` schema now emits the **same placeholder-substitution WARNs** as the
    `Financing_Terms` path (A1/#91) when it substitutes the `[0.5, 0.5]` even draw or `[40, 60]`
    construction phasing; the `Financing_Terms` path additionally WARNs on its previously-silent
    `[40, 60]` construction-schedule substitution. Values are unchanged.
  - `finance.debt_v14._pmt` raises a clear `ValueError` when `nper <= 0` with a non-zero rate instead
    of a raw `ZeroDivisionError` (defensive: the sole caller guards `amort_years > 0`); the
    `rate == 0` degenerate contract is untouched.
  The `_extract_project_life_years` heuristic tree-walk already WARNs (the issue's "silent" was
  overstated); its warning is now pinned by a dedicated test. Dedicated failure tests cover every new
  raise/warn path.

### Changed
- **Tooling: consolidate the lint stack toward ruff — retire flake8 + pylint (#610, tooling-only, KPI-neutral).**
  The dev/CI toolchain declared five overlapping linters (ruff/black/isort/flake8/pylint). flake8 is
  now RETIRED from `pyproject [dev]`, the `requirements.txt` lock, `fx-tests.yml` (its only invocation
  was an advisory `continue-on-error` FX-scoped step, never a mandatory gate), and the `scripts/ci/*`
  helper scripts — its rule families all live in ruff (E/W pycodestyle, F pyflakes, B flake8-bugbear,
  C90 mccabe), and the mandatory repo-wide `ruff check .` gate in `test-suite.yml` already enforces
  E/F, so no enforced check is lost. **black (format) and isort (import order) are KEPT unchanged:**
  ruff's own isort (`I`) cannot reproduce isort `profile=black` byte-for-byte on this tree (isort keeps
  an aliased `from X import a as b` on its own line while merging non-aliased siblings; 3 files diverge
  irreducibly, and `force-single-line`/`force-sort-within-sections` are far worse at 433/163 diffs), so
  per the issue's "don't drop it if import order changes" guardrail isort-the-tool stays. **pylint is
  retired from the toolchain too** (it was never a gate — only a non-blocking `--exit-zero` call in the
  unwired `scripts/ci/*` helpers): `pylint --errors-only` over the engine is a wall of false positives
  on the CASPER optional-dependency (`_require_*`-guarded imports) and dynamic-`__all__` re-export
  patterns (E0603/E0611/E0401/E1133), so a scoped real-error pylint pass is not viable here. Net: five
  linters -> four (ruff/black/isort/mypy), same enforced gate, a lighter CI install. Enabling ruff's `B`
  (flake8-bugbear) rule set as a mandatory gate is a documented follow-up (the tree carries ~18 `B904`
  `raise ... from` findings that need code fixes first, out of scope for this tooling-only change).
- **CI: shard the Test Suite into a parallel matrix to cut PR wall-clock (#729, infra-only, KPI-neutral).**
  `test-suite.yml`'s single `Run Tests` job (the full ~3,400-test tree + 6-package coverage on one
  runner, which had drifted to ~12-17 min as the suite grew) is split into a 4-way `pytest-split`
  shard matrix (`--splits 4 --group N`, still `-n auto` within each shard), so the gate's wall-clock
  is the slowest shard (~a quarter) instead of the whole run. The R8/TEST-02 95%-coverage floor is
  preserved exactly: each shard writes coverage DATA ONLY (distinct `COVERAGE_FILE`), and a new
  `coverage` gate job runs `coverage combine` + `coverage report --fail-under=95` over the union;
  `Test Summary` now also gates on it. `pytest-split>=0.8` added to the dev/test extras. No engine
  code touched — committed KPIs and the coverage gate strength are unchanged.
- **`build_lhs_plan` now samples via `scipy.stats.qmc.LatinHypercube` (#598, KPI-neutral).**
  The Pareto optimizer's `lhs` plan builder (`analytics.sensitivity.optimizer.build_lhs_plan`)
  replaces its hand-rolled stratified sampler — whose own docstring admitted it was "NOT full
  LHS" — with a formal scrambled Latin Hypercube: `qmc.LatinHypercube(d=len(grid),
  scramble=True, rng=np.random.default_rng(int(seed)))`, giving Koksma-Hlawka error bounds and
  no new dependency (scipy is already a base dep, `scipy>=1.10`). The public signature and
  semantics of `build_lhs_plan(grid, *, n_samples, seed=123)` are unchanged: same
  `List[(label, overrides)]` shape, same `[min(values), max(values)]` per-parameter ranges,
  same `f"{name}~{v:.6g}"` labels, same fail-loud validation (empty grid / `n_samples<=0`).
  - MRM-01: the drawn VALUES differ from the legacy stream (it is now genuine LHS), but this is
    an accepted change — `build_lhs_plan` has NO pipeline/report/committed-scenario caller (its
    only consumer is the on-demand `run_pareto_search(plan_kind="lhs")` analytics tool) and no
    test or artifact pins the specific value stream (tests assert shape, per-dimension bounds,
    same-seed reproducibility, the one-point-per-stratum LHS property and a degenerate pinned
    parameter — not values). All committed-scenario KPIs verified byte-identical (all-scenarios
    kpi oracle, 27 scenarios).
  - CASPER: `from scipy.stats import qmc` is a lazy call-time import with a fail-loud
    `ImportError` guard (actionable message; `grid` plan still needs numpy only), mirroring the
    established `analytics.mc.samplers` Sobol pattern (#650). Scaling uses the same manual
    `lo + u*(hi-lo)` affine map (NOT `qmc.scale`, which raises on a degenerate `lo == hi`
    parameter), so a pinned parameter yields a constant column exactly as before.
  - Scrambling/seed semantics (documented honestly): `scramble=True` applies an Owen-style
    random-linear scramble jittering each point within its stratum; the single seeded
    `default_rng` drives both the per-dimension stratum permutation and that scramble, so the
    output is a pure deterministic function of `(seed, n_samples, len(grid))`.
- **CASPER `mc_risk` covenant floor unified on the MC engine's resolver (#639).** The
  `mc_risk` block's DSCR breach floor was resolved from the pipeline's
  `debt_covenants.dscr_threshold` snapshot (= `Financing_Terms.target_dscr` only), while the
  MC engine's fixed-debt breach test used the 4-path precedence
  `constraints.min_dscr_covenant` → `Financing_Terms.target_dscr` → `Financing_Terms.min_dscr`
  → `monte_carlo.min_dscr_covenant` (default 1.30) — two resolutions that could disagree on
  the same scenario. The resolvers were extracted verbatim from `analytics.mc.engine` into the
  dependency-light `analytics.mc.covenant` (MOVE → SHIM; the engine re-exports them unchanged
  under their original private names), and `casper_payload` now resolves the floor with the
  shared resolver over the raw `ScenarioResult.config`, falling back to the
  `debt_covenants.dscr_threshold` snapshot and then the `CovenantSpec` default (1.30) only
  when no raw config is attached (bare-string/synthetic scenarios). Verified against all
  committed scenarios: every lendercase has both resolutions in agreement at 1.30
  (kpi-oracle byte-identical; the floor is not part of the committed KPI surface); the only
  runtime `mc_risk` movers are the two non-bankable mixed-covenant configs, which now adopt
  the engine floor the way the covenant surface always intended
  (`dutchbay_equitycase_2025Q4` 1.40 → 1.30; `edge_extreme_stress` 1.25 → 1.15), with the
  floor used still surfaced explicitly in `mc_risk.covenant.dscr_floor`. The four
- **Run manifest is now stamped inside the engine (#577, half 2 — engine-internal provenance,
  KPI-neutral).** `run_v14_pipeline_enhanced` stamps `result["run_manifest"]` itself, immediately
  after config resolution + schema validation, hashing the ALREADY-RESOLVED post-override config it
  actually evaluates (no re-load) — so every caller (CLI, web API, `evaluation_v14` gateway,
  MC/sensitivity per-trial entries, scripts) now receives a manifest whose `config_sha256` binds to
  the exact inputs, for both path and inline-Mapping configs. Outer stampers defer to it:
  `run_full_pipeline_v14` becomes stamp-if-absent (new `_stamp_manifest_if_absent` helper; the
  `_load_manifest_config` re-load with its loud degraded-path WARNING from half 1 is retained as the
  fallback), `api.pipeline_api.run_pipeline` returns the engine manifest instead of rebuilding one,
  and `app.services.pipeline_service.run_finance_case`'s existing stamp-if-absent guard is kept as a
  defensive fallback. `analytics.run_manifest.git_sha()` is now process-cached (`lru_cache` on the
  `git rev-parse HEAD` probe) so per-trial manifest stamping no longer forks a git subprocess per MC
  trial; the `DUTCHBAY_GIT_SHA`/`GIT_COMMIT` env override deliberately stays outside the cache and is
  consulted on every call. `ScenarioAnalytics` batch stamps are unchanged (that surface builds
  cashflow/debt/KPIs directly and never calls the engine). Additive metadata only: committed scenario
  KPIs are kpi-oracle byte-identical.
- **Batch-path economics now labelled non-authoritative in every emitted JSON (#611).** The batch
  comparison CLI (`run_scenario_analytics_v14.py` → `analytics.scenario_analytics`) computes DSCR/IRR
  on a deliberately lighter basis than the canonical pipeline (PIPE-1, #472: no build-up WACC, no
  two-pass interest tax shield, no equity waterfall), but only a docstring said so. Both emitted JSON
  payloads — the persisted `output_summary_json` (serialised `BatchResultSummary`, which gains a
  `basis` field defaulting to the new `analytics.scenario_analytics.BATCH_ECONOMICS_BASIS`) and the
  CLI stdout summary (now built by `run_scenario_analytics_v14._build_stdout_payload`) — carry a
  machine-readable `basis: "comparison_snapshot"` marker so a consumer cannot mistake batch numbers
  for `run_full_pipeline_v14.py` economics. Strictly ADDITIVE: no existing key is renamed, removed or
  revalued (downstream consumers grep-verified: tests only); committed scenario KPIs are
  kpi-oracle byte-identical. JSON-shape tests extended to pin the marker at both emission points.
- **Frozen-contract pattern extended to the report/job models (#608, KPI-neutral).** All 13
  report-section models in `app/reports/report_model.py` (`KpiRow`, `AssumptionRow`, `RiskRow`,
  `ReadinessRow`, `Verdict`, `ReportContext` — previously `extra="forbid"` only — plus
  `EvidenceRow`/`EvidenceBlock`, `MultiTechRow`/`MultiTechBlock`, `ThreeStatementBlock`,
  `WaterfallRow`/`WaterfallBlock`, which had no `model_config`) and `JobRecord` in
  `app/jobs/models.py` are now `ConfigDict(frozen=True)`, matching the 15 frozen pydantic contracts
  in `analytics/core/{returns,risk_metrics}.py`, `analytics/pipeline_analytics_v14.py` and the two
  cashflow adapters. Each model's existing `extra` policy is preserved (no silent forbid/ignore
  flips), and `JobProgress`'s deliberate `extra="ignore"` (computed-`pct` JSON round-trip) is
  untouched. Post-construction attribute assignment now raises `ValidationError`; derive variants
  with `model_copy(update=...)` — the path both job stores already use, so `InMemoryJobStore`/
  `RedisJobStore` update flows are unchanged. Report contexts are built once in
  `build_report_context` and consumed read-only by the renderer/API, so no production mutation site
  existed; the single test that mutated a fetched `JobRecord` in place
  (`tests/app/test_jobs_store.py::test_get_returns_detached_copy`) now asserts frozen semantics and
  covers deep-copy detachment via the nested mutable `progress` instead. Committed scenario KPIs are
  kpi-oracle byte-identical; passes the CI `pydantic.mypy` strict gate (#594).
- **Tiered MCP bankability guard on measurement-campaign duration (#597).** `wind_resource.mcp`
  previously enforced only a 24-sample statistical floor (`DEFAULT_MIN_CONCURRENT`, one day of hourly
  data) while its own comment conceded a bankable MCP needs months of concurrent data. `run_mcp()` now
  tiers the guard: below the unchanged hard floor it still raises unconditionally; in the band
  `min_concurrent <= n < BANKABLE_MIN_CONCURRENT` (new constant, 2,880 hourly samples ~= 4 months;
  Sheridan et al., Wind Energy Science 2025 — long-term capacity-factor errors ~47%/26%/16% at 1/3/6
  months) it fails loud (CESSPIT, no silent sub-bankable fits) unless the caller passes the new
  explicit opt-out `allow_below_bankable=True`, which downgrades the failure to a `logger.warning`
  bankability disclosure; at or above the threshold it runs clean. `mcp_settings()` resolves the
  matching scenario knob `resource.wind.mcp.allow_below_bankable` strictly (boolean only, non-boolean
  values raise; defaults OFF) and returns it alongside `method`/`min_concurrent`. The opt-out never
  bypasses the hard floor. The module remains opt-in with no scenario consumer, so committed
  scenarios are kpi-oracle byte-identical (verified empirically across all 27). Tier boundaries
  (23/24, 2,879/2,880), the override path, and the strict knob are pinned in `tests/wind/test_mcp.py`.
- **Batch discount-rate default consolidated to a single source of truth (#586).** The default was
  stated three times with two different values: a silent `0.10` fallback in
  `run_scenario_analytics_v14.py`, the authoritative `0.12` in `conf/run_scenario_analytics_v14.yaml`,
  and a `0.10` constructor default in `analytics.scenario_analytics.ScenarioAnalytics`. Now: the
  packaged YAML (`default_discount_rate: 0.12`) is THE source for batch runs and the CLI **fails loudly
  (`ValueError`) if the key is missing** instead of silently substituting 0.10 (CESSPIT — config
  explicit, no silent defaults); the direct-API constructor default is defined once as
  `analytics.scenario_analytics.DEFAULT_GLOBAL_DISCOUNT_RATE` (still `0.10`). No resolved value moves
  for any committed run: the packaged config always carries the key, invalid-value handling is
  unchanged, and direct-API callers keep 0.10. The only behavioural change is fail-loud on a config
  that omits the key (e.g. a `~default_discount_rate` Hydra delete-override), previously a silent
  0.10. Regression-pinned in `tests/analytics/test_run_scenario_analytics_discount_default.py`,
  including a pin on the committed YAML 0.12 so the authoritative batch value cannot drift silently.
- **Legacy `np.random.RandomState` retired from the test suite (#619, autonomous half).** The four
  remaining `RandomState` sites — all synthetic-input fixtures under `tests/analytics/`
  (`test_capital_risk_layer_v14.py` seed 0, `test_mc_aep_weibull.py` seed 7,
  `test_oem_parser.py` seeds 42/43) — moved to `np.random.default_rng(seed)` (PCG64) per NEP 19,
  completing the migration the #473 MC-5 dolphin applied to the production RNG. Determinism under
  fixed seeds is preserved (MRM-01); the sampled streams change, but every consuming assertion is
  band/ordering/statistical and was verified to hold with comfortable margins on the new streams
  (tightest: DSCR breach-prob 0.096 vs 0.106 ± 0.04; MC-AEP p50 402.76 vs 402.6 ± 10), so no
  assertion was re-baselined and no site needed seed-stream pinning. Test-only; the committed
  scenario KPI surface is kpi-oracle byte-identical. The `datetime.utcnow()` half of #619's sweep
  has exactly one live site (`analytics/pipeline_v14_enhanced.py:80`), owned by #586b and
  deliberately not touched here; the `pyxirr`/QuantLib lock fork stays user-gated (W5).
- **hydra-core pinned 1.3.2 → 1.3.3 + declared as an abstract runtime dep + maintenance-risk ADR (#609).**
  The reproducibility-lock pin moves to 1.3.3 (upstream is packaging-only — removes `setup.py`'s
  `pkg_resources` dependency, hydra#3207 — so runtime behaviour and all committed KPIs are unchanged;
  its transitive requirements were already satisfied by the lock, so no other pin moves).
  `hydra-core>=1.3.3` is now declared in `pyproject.toml [project.dependencies]`: the packaged
  `analytics.cli.*_hydra` modules import `hydra` at module scope, so its previous absence meant
  regenerating the lock from pyproject (the lock header's own recipe) would have silently dropped a
  load-bearing package. New ADR `docs/HYDRA_MAINTENANCE_DECISION.md` records the stalled upstream
  cadence (1.3.2 Feb-2023 → 1.3.3 Jun-2026, maintainer-status question unanswered) as an accepted
  risk — stale but stable: narrow `@hydra.main`+dotlist surface, everything pinned, OSV/pip-audit
  clean — with an OmegaConf + thin-CLI fallback plan (omegaconf is already a direct runtime dep) and
  explicit re-evaluation triggers.
- **`pydantic.mypy` plugin registered in the effective mypy config (#594, tooling-only, KPI-neutral).**
  `mypy.ini` (the config both CI gates actually read — `pyproject.toml`'s `[tool.mypy]` merely points
  `config_file = "mypy.ini"`) now sets `plugins = pydantic.mypy` plus the strictest `[pydantic-mypy]`
  profile (`init_forbid_extra`, `init_typed`, `warn_required_dynamic_aliases`). The CASPER-family
  frozen-contract boundary (pydantic v2 models in `analytics/core/risk_metrics.py`,
  `analytics/core/returns.py`, `analytics/fx/fx_contracts.py`,
  `finance/equity_distribution_v14_hydra.py` and the `api/`/`app/` layers) is now genuinely
  type-checked: precisely-typed synthesized `__init__` signatures, unknown constructor kwargs
  rejected, dynamic required aliases flagged. Verified against the CI-pinned mypy 1.19.0 +
  pydantic 2.13.4: zero new errors on both CI invocations (library/engine surface and the relaxed
  `scripts/` gate), plugin activation positively confirmed via an out-of-tree probe model. The now
  inert `[mypy-pydantic.*] ignore_missing_imports` block (pydantic v2 ships `py.typed`) is kept and
  annotated; its removal is deferred as a user-gated cleanup. No runtime code changed; kpi_oracle
  byte-identical across all committed scenarios.
- **CVaR labelled explicitly as Expected Shortfall + quantified small-sample caveat (#600, KPI-neutral).**
  The user-facing display label from `analytics.core.risk_metrics.TailRiskAnalyzer.calculate_var_cvar`
  moves `CVaR(95%)` → `CVaR/ES(95%)` (CVaR and Expected Shortfall are the same statistic; the label now
  names both). Docstrings at every CVaR computation surface (`analytics/core/risk_metrics.py`,
  `analytics/mc/engine.py::_tail_risk`, `analytics/capital_risk_layer_v14.py`,
  `analytics/sensitivity/tail_risk.py::_cvar`) plus `docs/ANALYTICS_INTEGRATION.md` now state
  CVaR == ES and carry a quantified small-sample caveat: the tail mean rests on only
  `(1 - confidence) * n` trials — at n=1000 a 1% tail averages ~10 raw trials (noisy for a
  covenant/pricing input) — and ES converges slower than the mean, so a tight mean CI from the
  post-hoc convergence diagnostic (`analytics/mc/convergence.py`, #643) does not certify the tail;
  the `>= max(20, 1/(1-confidence))`-sample floor in `capital_risk_layer_v14` is documented as a
  degeneracy guard, not statistical sufficiency. Strings/docs/Markdown only: no numeric computation,
  default, or config key changes (`cvar_confidence`/`cvar_alpha` untouched); committed scenario KPIs
  byte-identical (labels never enter committed KPI artifacts).
- **FX sensitivity sweeps wired to the live hedge engine (#652/#659).** With FX forward hedging
  modelled in the engine (above), the analysis layer's sweeps now drive the live keys end-to-end:
  - `FXSensitivityAnalyzer.run()`'s spread sweep drives `fx.spread_bps` (the legacy, engine-ignored
    `fx.spread_shock_bps` override and its "unmodeled lever" warning are retired) **jointly with an
    active hedge** — the engine prices a spread only on the hedged fraction, so the sweep runs at the
    scenario's own `fx.hedge_ratio` when > 0, else at a documented reference FULL hedge (h = 1.0); the
    coefficient reads "metric change per bp of hedging cost, if fully hedged".
  - **Spread-shock semantics settled:** `FXSensitivityConfig.spread_shocks_bps` are DELTAS (bps)
    around the scenario's base `fx.spread_bps`; the swept absolute spread is `base + shock` and a
    delta that crosses zero **fails loud** (never clamps), mirroring the engine's `>= 0` gate. The
    default grid moves `[-100, 0, 100]` → `[0, +50, +100]` so no unhedged (base-0) scenario can trip
    the gate.
  - `analyze_fx_sensitivity` now **uses** its `hedge_ratio_steps` / `spread_variation_bps` /
    `spread_steps` parameters (previously accepted and silently ignored — `hedge_ratio_points` /
    `spread_points` always came back empty): both sweeps are populated from the real pipeline, and
    `calculate_summary_metrics` fits engine-driven `hedge_ratio_irr/npv_sensitivity`,
    `spread_irr/npv_sensitivity` and `fx_rate_npv_sensitivity` (fx-rate IRR was previously the only
    fitted summary).
  Committed KPIs are untouched (analysis layer only; the engine is not modified). On the canonical
  lender case the surfaced sensitivities read: hedging raises IRR/NPV (CIP forward below spot, see
  the feature entry above), and each bp of spread is a cost (negative slope) under the reference
  hedge.
- **BESS default round-trip efficiency re-baselined 0.90 → 0.85 (#588, user-authorized KPI-move).**
  The default AC-AC round-trip efficiency (`finance.bess_revenue._DEFAULT_ROUND_TRIP_EFFICIENCY`) moves
  from the Ember-2025 upper-end 0.90 to NREL ATB 2024's representative utility-scale Li-ion figure (Cole &
  Karmakar 2023) — a conservative mid-market value. The duplicate mirror in `finance.bess_lcos` is
  **removed** and now imports the canonical constant (single source of truth — the two could previously
  drift; CCCDIR). Blast radius (all verified in the venv):
  - **Energy-tariff BESS** (the committed CEB Solar+BESS night-peak scenario, which explicitly overrode to
    0.90 → moved to 0.85 to match): revenue and the LCOS denominator are both linear in RTE, so both fall
    **−5.56%** (0.85/0.90); year-1 night-peak export 601.8M → 568.4M LKR, project IRR 9.72% → 8.77%.
  - **Capacity-charge BESS**: **revenue and every cashflow/return KPI (project IRR, NPV, DSCR) are
    RTE-independent and do NOT move** (revenue = R×MW×12). Its **reported LCOS analytic DOES move +5.88%**
    (76.19 → 80.67 USD/MWh) — correctly: LCOS is cost per *discharged* MWh, and a less-efficient pack
    discharges less per cycle, so a more realistic RTE gives a more realistic (higher) cost. This is a
    reporting metric, not a covenant/return KPI, and no test pins its value; it is disclosed, not frozen.
  - **Wind-only lender case**: carries no BESS revenue, so its committed KPIs (projIRR/eqIRR/DSCR/NPV) are
    **byte-identical (kpi_oracle-verified, argv-correct)**.
  Scenario/test pins updated accordingly.
- **Recommended default P50 over-prediction haircut wired at the config layer (#587).** The AEP
  summary builder's `resource.uncertainty.p50_haircut_pct` policy default moves from 0.0 to a
  documented `RECOMMENDED_P50_HAIRCUT_PCT` (**5.0%**, `wind_resource.bankable_aep`): a scenario
  that is SILENT on the haircut now corrects for the well-documented pre-construction P50
  over-prediction bias (Hammond & Simley, WES 2026: −6.6%/−7.4%; the ~0–7% range in the
  operational-vs-predicted validation literature) rather than assuming a naive 0%. The
  `exceedance_levels` KERNEL keeps its 0.0 identity default — this is a *policy* default applied only
  at config-consumption, never in the math (wind-only by design; the solar layer intentionally stays
  0.0). **KPI-neutral for every committed scenario, and every committed scenario is now made explicit**
  so the default never silently applies on a regeneration: the has-EYA DutchBay scenarios set
  `p50_haircut_pct: 2.0` (lender/5usc/hybrid, and now the two capex variants — previously they carried
  only a pinned/frozen 464.3 AEP, not an explicit knob), and the two no-EYA fixtures (kalpitiya_160m,
  mullikulam) set `0.0` (their frozen artifacts were built at 0%). Finance never recomputes AEP (it
  bills off the config `capacity_factor` / frozen `aep_summary_path`), so the wind lender case is
  **kpi_oracle byte-identical (argv-correct), and all 19 evaluable scenarios are byte-identical vs the
  parent**; the recommended default now governs only *future new* no-EYA scenarios. (Verify-before-apply:
  the issue's premise that the haircut was "unused at 0.0" was stale — it was already wired via
  WIND-5/#484; per user direction the flagship 2.0% is left untouched, tracked as a separate
  calibration note — see the OEM-EYA-bias caveat issue.)
- **Dependency version bounds tightened (SOTA benchmarking #592/#593).** `pandas>=2.0` gains a `<3.0`
  cap — pandas 3.0 (Jan 2026) makes Copy-on-Write mandatory and infers a default str dtype
  (unconditional breaking changes), so 3.0 must be a deliberate, KPI-oracle-verified migration, not an
  incidental resolve. The opt-in `[wind]` extra's `cdsapi>=0.6` floor is raised to `>=0.7.2`: the
  CDS-Beta platform is the sole live Copernicus endpoint since 26 Sep 2024 and needs `cdsapi>=0.7.0`
  (0.7.2+ recommended); a pre-CDS-Beta version resolves but silently fails against the live endpoint.
  Spec-metadata only — the pinned lock (`requirements.txt`, `pandas==2.3.3`) already satisfies the cap
  and `cdsapi` stays out of the base lock as an optional extra, so the installed test environment and
  the KPI oracle are unchanged.
- **Reconcile the frozen net-AEP P90 against the bankable summary export, restoring P50<->P90 guard
  symmetry (round-2 audit).** `analytics.aep_reconciliation` reconciled only
  `expected_results.net_aep_p50_gwh` (against `capacity_mw · CF · 8.760`); the frozen
  `net_aep_p90_gwh` had no load-time guard, yet it drives the hybrid P90-binds-gearing
  (`finance.debt_v14._resolve_downside_ratio` reads the P90/P50 ratio to size the `min(P50, P90)`
  gearing), so a stale P90 could silently move committed hybrid economics — and the only test that
  reconciled it against the live wind+solar model was `pvlib`-gated and skipped in the default CI
  gate. New `reconcile_frozen_p90_with_bankable_summary` (called from
  `reconcile_capacity_factor_with_bankable_aep`, independent of capacity/CF) fails loud when the
  frozen `net_aep_p90_gwh` diverges beyond tolerance from the authoritative
  `exceedance.net_aep_p90_1yr_gwh` in the scenario's `aep_summary_path` export — a `pvlib`-free check
  that runs in the default gate. No-op unless both values are present. KPI-neutral: all five committed
  scenarios that carry both agree exactly (hybrid 471.0, four wind-only cases 404.4 via the 10 MW
  summary), so nothing raises and the KPI oracle is byte-identical; kalpitiya/mullikulam summaries
  carry no P90 and are a clean no-op. Adds pass/fail/no-op regression tests.
- **Closed a username-enumeration timing oracle on the `/token` login route (round-2 audit, CWE-208).**
  `app.api.auth.authenticate_user` short-circuited on an unknown username (`encoded is None or not
  verify_password(...)`), so the ~600k-iteration PBKDF2 ran only for a *known* username with a wrong
  password; an unknown username returned the 401 in microseconds. Both cases already return the
  identical body, so timing was the only distinguishing signal — an unauthenticated caller could
  enumerate valid client usernames on the public, unrate-limited `/token` route. The unknown-username
  path now runs a PBKDF2 verification against a fixed module-level dummy hash and discards the result,
  equalizing the cost so the two paths are indistinguishable by response time. Adds a regression test
  asserting `verify_password` is invoked (against the dummy hash) on the unknown-user path. Web-authn
  hardening only; no `finance/` code and no committed KPI touched. KPI-neutral.
- **Fixed the dead-and-broken `FXSensitivityAnalyzer.analyze_fx_sensitivity()` public surface
  (round-2 audit).** Its helper `_run_pipeline_with_fx_params` built an inline dict config and passed
  it to `run_v14_pipeline_with_analytics`, which hard-guards its config to `(str | Path)` (added in
  #156), so the method always raised `TypeError` before returning a `RealFXSensitivityResult` — a
  permanently-broken public method that every test hid by monkeypatching the pipeline. It now routes
  the FX overrides through the path-based contract gateway `evaluate_with_overrides(base_config_path,
  {"fx": {...}}, return_full_result=True)` — the same seam `run()` already uses (the module-level
  wrapper gains a `return_full_result` passthrough) — and drops the unused `copy` import. Adds a
  non-mocked end-to-end regression that drives `analyze_fx_sensitivity` on the real lender scenario
  (so the previously-dead method is genuinely exercised) and reworks the monkeypatched tests onto the
  gateway seam. KPI-neutral: this analytics surface feeds no committed KPI (verified byte-identical
  via the KPI oracle); it previously failed loud rather than emitting a wrong number.
- **Normalized the `Financing_Terms.rates` tranche rates in `_solve_mix` (round-2 audit, FIN-02).**
  `finance.debt_v14._solve_mix` read the per-tranche rates (`lkr_nominal` / `usd_nominal` /
  `dfi_nominal` / `*_min`) with a bare `_as_float`, unlike the sibling `debt`-block path which
  already normalizes via `_rate_decimal`. A canonical `Financing_Terms.rates` entry authored in
  percent form (e.g. `lkr_nominal: 13.39` instead of `0.1339`) therefore reached the amortization
  arithmetic as `interest = balance * 13.39` (1339%/yr) with no error — the cost-free-debt guard only
  rejects `rate <= 0` — silently corrupting IDC/DSCR/every downstream KPI, and the result depended on
  which config shape was used. The rates now route through `_rate_decimal` (percent-form → decimal for
  any value > 1.0), matching the other path. KPI-neutral: every committed scenario declares decimal
  rates (< 1.0), so this is byte-identical for them (verified via the KPI oracle across the lender,
  base, equity and hybrid scenarios); it only rescues a mis-scaled percent-form input. Adds a
  regression test that a percent-form tranche rate resolves to the same schedule as its decimal form.
- **Sized the fund-at-close DSRA off operating year 1, not the synthetic half-year bridge period
  (round-2 audit).** `finance.debt_v14._build_funding` sized the funded Debt Service Reserve off
  `debt_service_total[construction_periods]`, which on the `_build_cfads_timeline` debt timeline is the
  synthetic half-year "bridge" lead-in period rather than operating year 1 (index
  `construction_periods + 1`). When `interest_only_years < 2` the bridge bears only a half-year of
  interest, so the DSRA was under-reserved (~50% low at io=0), understating equity-at-close and
  overstating equity IRR (the reserve is added to equity at financial close and surfaced at
  `api/pipeline_api.py`). It now reuses the engine's own operating-year-1 debt period (row 0 of
  `annual_row_debt_period_map`, the same period the year-1 DSCR is computed against), so it is correct
  whether or not a bridge period exists. KPI-neutral: every committed scenario uses
  `interest_only_years: 2` (bridge == op-year-1) and none enable `dsra.fund_at_close`, so the DSRA is
  0 for all of them; committed KPIs are byte-identical across the lender, base, equity and hybrid
  scenarios (verified before/after). Adds a regression test that forces io=0 and asserts the reserve
  is sized off operating year 1, not the bridge.
- **Stopped masking engine regressions behind first-party `ImportError`->`pytest.skip` in three
  integration test modules (round-2 audit).** `tests/integration/test_monte_carlo_integration.py`,
  `test_degradation_flow.py`, and `test_pipeline_end_to_end.py` wrapped FIRST-PARTY analytics imports
  (`MonteCarloEngine`, `MonteCarloResult`, `run_monte_carlo_analysis`, `analyze_dscr_sensitivity`) in
  `try/except ImportError -> pytest.skip(allow_module_level=True)`. Those symbols pull no optional
  dependency, so the guard could never legitimately fire for a missing extra — it only ever masked a
  rename/removal, silently skipping ~46 (15+15+16) engine regression tests while the suite stayed
  green (and the import-smoke lint does not bind-import the three symbols, so a rename passed smoke
  too). The first-party imports are now UNGUARDED so a broken symbol fails loudly at collection,
  matching the earlier D1 remediation. The per-test `@_REQUIRES_SENSITIVITY` marker guard in
  `test_pipeline_end_to_end.py` is left intact (it skips individual tests, not the whole module).
  Test infrastructure only; no `finance/` code and no committed KPI touched. KPI-neutral.
- **Report the P90/P95 downside (exceedance) tail for higher-is-better metrics in the Monte Carlo
  lender risk table (round-2 audit).** `analytics.mc.exports.build_lender_risk_table` emitted the raw
  90th/95th percentile — the favourable UPSIDE — for DSCR(min), project IRR/NPV and LLCR/PLCR,
  contradicting the exceedance convention used everywhere else (the sibling "Worst-year DSCR (P95
  downside)" row is the 5th pct; the AEP P90 is the 10th pct in `capital_risk_layer_v14`) and
  understating tail risk to a lender. For these higher-is-better metrics the `P90`/`P95` columns now
  report the adverse low tail (P90 = 10th pct, P95 = 5th pct), consistent with that sibling row.
  Off the committed-KPI path: this table feeds only the example lender-pack export, not the
  pipeline / `report_model` / api, so no committed KPI moves. Adds a deterministic
  direction-asserting regression test. KPI-neutral.
- **Migrated all scenario YAMLs and test fixtures to `enhanced_capital_allowance_multiple`
  (audit D8, step 2 of 2).** All 22 `scenarios/*.yaml` keys and the dict-key test fixtures now use
  the canonical multiplier name; each numeric value is byte-preserved, so committed KPIs are
  unchanged (verified byte-identical across the lender, base, equity and hybrid scenarios). Fixed the
  orphan `scenarios/test/base_scenario.yaml`, whose value was the percent-form `125` (never loaded —
  `enhanced_allowance_applies: false` and no consumer references it — but a latent unit-error that the
  `> 3.0` guard would reject): now `1.25`. The deprecated `enhanced_capital_allowance_pct` YAML alias
  remains supported (with a `DeprecationWarning`) per the deprecation lifecycle; the frozen
  `legacy_scenarios/archive/` copy is deliberately left untouched. KPI-neutral.
- **Renamed the tax field `enhanced_capital_allowance_pct` → `enhanced_capital_allowance_multiple`
  in the finance engine, with a deprecated YAML alias (audit D8, step 1 of 2).** The field is a
  MULTIPLIER on the depreciable base (1.0 = standard 100% allowance, 1.5 = a 150% enhanced
  allowance), never a percent, so the `_pct` suffix violated FIN-02 (unit-suffixed names). The
  `TaxConfig` dataclass field, its validators, the depreciation reader in `cashflow_v14.py`, and the
  contract doc comments now use `_multiple`; `TaxConfig.from_yaml` gains a
  `_get_enhanced_allowance_with_compat` helper (mirroring `_get_tax_rate_with_compat`) that accepts
  the new key and still resolves the legacy `enhanced_capital_allowance_pct` with a
  `DeprecationWarning`, so every existing scenario loads unchanged. KPI-neutral: committed KPIs
  (project/equity IRR, DSCR, LLCR/PLCR, NPV, WACC, CFADS) are byte-identical across the lender, base,
  equity and hybrid scenarios (verified before/after). Scenario YAMLs and dict-key test fixtures
  still carry the deprecated key; migrating them to the canonical key is step 2 (the alias remains as
  the backward-compat shim per the deprecation lifecycle).
- **Fixed a currency + phase mismatch in the enhanced-analytics returns view (audit D12).**
  `analytics.pipeline_analytics_v14._calculate_returns_analysis` built the CFADS series in LKR
  (`cfads_final_lkr`) while taking debt service from the USD, period-indexed
  `debt_result["debt_service_total"]` (which carries a construction/bridge lead-in) — a currency
  mismatch of ~one FX rate plus a multi-year phase offset that made debt service effectively vanish
  and grossly inflated the geared equity IRR on this surface. Both series are now read from the
  enriched per-row USD fields (`cf_pre_debt` and the operating-year-aligned, bridge-folded row-level
  `debt_service_total`), and the local `ReturnsConfig` neutralises `capex_fx_rate` to 1.0 so CAPEX
  and the equity base stay in USD too. Off the committed-KPI path: this `returns_analysis` surface
  feeds no committed IRR/DSCR/LLCR/PLCR/NPV/WACC/CFADS value (those come from the finance engine) and
  its only reader is an unreached fallback in `fx_sensitivity_real`; no pinned test value changes.
  KPI-neutral. Adds a regression test that geared equity IRR sits below project IRR when debt is
  priced above the project return, plus a docstring note that the returned `AllReturns` `*_lkr`
  fields carry self-consistent USD on this call path.
- **Corrected the read-only LCOS discharged-energy basis for `energy_tariff` BESS (audit M1).**
  `finance.bess_lcos.compute_lcos` applied a 0.40 depth-of-discharge to the discharged-energy
  denominator for the `energy_tariff` model, but `bess_revenue` exports the FULL nameplate energy
  per cycle for that model (no DoD) — so the reported LCOS was overstated by 1/0.40 = 2.5x. The DoD
  is now gated by `revenue_model` (applied only to `capacity_charge`, which IS dispatched to a
  fractional depth on call). Read-only reporting number, strictly off the cashflow path: no
  committed IRR/DSCR/NPV/CFADS/covenant value and no pinned test value changes; only the reported
  `energy_tariff` LCOS moves (2.5x lower, now consistent with its revenue energy basis).
- **Repo-wide `black` + `isort` reformat, and both promoted to mandatory CI gates.** Ran `isort .`
  + `black .` across the whole repo (210 files reformatted), clearing the ~212-file backlog that had
  kept `black` advisory (`|| true`). Added a `[tool.isort]` config (`profile = "black"`, `legacy/`
  excluded) so the two formatters converge instead of fighting — a hard prerequisite for enforcing
  both. The `test-suite` lint job now runs `black --check` and `isort --check-only` as MANDATORY
  gates (no `|| true`), matching `ruff`/`mypy`. Purely mechanical and behavior-preserving — the full
  test suite is unchanged. KPI-neutral. (A `.git-blame-ignore-revs` entry for the reformat commit
  follows so `git blame` skips it.)
- **CI cost reduction (~50–70% fewer minutes, zero tests touched).** Added a `concurrency` group
  with `cancel-in-progress` (scoped to `pull_request` events, so `main`/scheduled runs are never
  cancelled) to all four heavy workflows — a new push now aborts the superseded in-flight run
  instead of letting stale runs pile up. Dropped the `test-suite` `push` trigger from
  `[main, develop, feature/*, resolution/*]` to `[main]` only: feature/PR branches validate via
  `pull_request`, removing the push+pull_request double-run that doubled CI cost per PR commit
  (work reaches `main` only through PRs, so nothing loses a gate). `regression-smoke` drops the
  stale `v14chat-upgrade` branch. The suite still runs `-n auto` across all cores and all three
  required checks (`Test Summary`, `fastlane`, `smoke`) still run on every PR — deliberately NOT
  paths-scoped, since a paths-skipped required check would block PRs indefinitely.
- **Fixed a check-name collision** surfaced by the review: `fx-tests.yml` had two jobs whose display
  names (`Test Summary`, `Code Quality Checks`) collided with `test-suite.yml`'s jobs — and
  `Test Summary` is a *required* status check, so on an FX-touching PR two different "Test Summary"
  checks appeared, making the required-check identity ambiguous. Renamed the fx-tests jobs to
  `FX Test Summary` / `FX Code Quality Checks` (job IDs unchanged, so `needs:` is unaffected).
- **CI: dropped the redundant advisory black/isort steps from `fx-tests.yml`.** The FX code-quality
  job carried FX-scoped `black --check` / `isort --check-only` steps with `continue-on-error: true`
  (advisory only, predating the repo-wide gate). Formatting and import order are enforced repo-wide
  by the MANDATORY lint gate in `test-suite.yml` (#545), which strictly supersedes the advisory
  checks, so they only added CI time and a perpetually ignorable signal. The two steps are removed
  and `black`/`isort` dropped from that job's installs; the advisory mypy and flake8 steps are
  intentionally untouched (their fate belongs to the gated lint-stack consolidation, #610). No
  gate is weakened: the mandatory repo-wide black/isort checks still block every PR.

### Fixed
- **Hygiene cluster, docs/header/naming shims (#586, dolphin a of 3 — KPI-neutral).**
  - `finance/debt_v14.py`: replaced the corrupted stray header (`# [File content too long...]`,
    a leftover editing artifact) with the module's real docstring, now at the top of the file
    where Python actually binds `__doc__` (it previously sat as an inert string literal below
    the imports). Comment/docstring-only; no code change.
  - `analytics/pipeline_v14_enhanced.PipelineMetrics.timestamp`: deprecated naive
    `datetime.utcnow()` → tz-aware `datetime.now(timezone.utc)`. The ISO metadata timestamp now
    carries an explicit `+00:00` offset, matching the tz-aware run manifest. Metadata-only; no
    KPI reads this field. (Owned here; struck from the #619 repo-wide utcnow sweep.)
  - `analytics/mc/samplers.generate_lhs_samples`: the misleading `common_random_numbers`
    parameter is renamed `shared_permutation_stream` (it selects the permutation-stream
    derivation — CRN across runs comes from passing the same `seed`, not from this flag). The
    old keyword keeps working as a deprecated alias (DeprecationWarning; conflicting values
    fail loud with ValueError); output for either spelling is bit-identical. The engine-level
    `common_random_numbers` config/API/metadata name is unchanged — at that level it genuinely
    toggles the MC-9 CRN feature.
  - `analytics/core/sensitivity_runner`: the path-based entry point is canonically named
    `run_sensitivity_analysis_from_path`, disambiguating it from the engine orchestrator
    `analytics.sensitivity.run_sensitivity_analysis` (same exported name, incompatible
    keyword-only/in-memory signature). The historical `run_sensitivity_analysis` export remains
    as an additive module alias (same object) in both the module and `analytics.core.__all__`;
    all existing imports keep working. Alias retirement is deferred to a user-approved batch.
  - `analytics/pipeline_analytics_v14._calculate_risk_analysis`: documented (labeling only)
    that the enhanced-analytics risk path deliberately reads `cfads_final_lkr`, so its
    level-denominated outputs (VaR/CVaR, CFADS percentiles) are LKR-based — unlike the returns
    path, which #559 made USD-consistent. No numeric change; a USD re-basing of risk outputs
    requires separate user authorization.
  Validators, Sobol power-of-2, deep-merge and discount-default items are dolphins b/c of #586.

### Fixed
- **Hygiene cluster #586 (dolphin B of 3): validators + Sobol n gate + deep-merge aliasing.**
  Three fail-loud/additive consistency fixes; all committed scenario KPIs verified byte-identical
  (argv-correct kpi_oracle before/after across all 27 committed scenarios).
  - `project_life_years` schema validator (`finance.cashflow_v14._register_cashflow_schema`) now
    accepts integral floats (`20.0`) — the engine's own extraction (`as_int_or_none` → `int(value)`)
    already coerced `20.0` to `20`, so the strict pre-flight guard was rejecting configs the engine
    reads fine. It now also rejects `bool` (the old `isinstance(v, int)` let `True` pass as "1 year")
    and keeps rejecting non-integral floats (`20.5` fails loud rather than being silently truncated),
    non-positives, and strings. All committed scenarios carry plain-int year counts and validate
    identically.
  - `analytics.sensitivity.global_sa.run_sobol` now validates `n` is a positive power of 2
    (`ValueError`) before sampling. SALib's `sobol` sampler draws a base-2 Sobol' sequence whose
    balance properties only hold at powers of 2 — SALib merely warns and degrades the S1/ST
    estimates, so the gateway fails loud instead. The documented default `n=256` is unaffected.
  - `analytics.evaluation_v14._deep_merge_config` no longer aliases nested branches: the old
    shallow `dict(base)` seed left every branch NOT named in the overrides shared with the base
    config's own sub-dicts (and inserted override branches by reference), so an in-place mutation
    of the merged config could silently leak into the caller's base — a real hazard for
    Monte-Carlo / sensitivity loops that re-merge the SAME base mapping thousands of times. The
    merged dict is now structurally independent of both inputs (nested mappings and lists freshly
    copied; immutable scalar leaves shared; merge values and key order unchanged, pinned by
    regression tests). Limitation: exotic non-YAML containers (tuples, sets, arrays) still pass by
    reference and are documented as out of contract.

## v15.2.0 - 2026-07-01

_Consolidates everything merged since the v15.0.0 tag: the #529 solar re-baseline (which bumped the
interim `VERSION` to 15.1.0 but was never separately tagged) plus the #481 report-residuals work
(RPT-2/4/6/7/8/9) and its follow-ups. Committed wind-only lender-case economics are unchanged by
everything except #529 (hybrid solar P50 re-baseline)._

### Fixed
- **`finance.irr.irr` no longer trusts a `numpy_financial` result that is not actually a root (#595,
  audit §3.4).** `numpy_financial.irr` (frozen at v1.0.0) can return an in-band value that does not zero
  the NPV for multi-sign-change series (numpy-financial #28/#33/#39) — e.g. `irr([1, 1, -1, 1e-135])`
  returned `0.0` while `NPV(0.0)=1.0` and the true root is `~-0.382`. `irr` accepted the library result
  unchecked whenever it fell within `[lower, upper]`. It now verifies the candidate zeroes the NPV via a
  new `_is_npv_root` (relative to the discounted-absolute magnitude — scale- and steepness-invariant)
  and falls back to the robust bisection solver when it does not. Adds a **Hypothesis property test**
  asserting any returned root zeroes the NPV over an adversarial sign-changing-cashflow corpus (the
  guardrail that surfaced this). No-op for the well-conditioned committed cashflows (`numpy_financial`
  returns the correct root, the guard passes) — full suite 3019 green and the KPI oracle byte-identical.
- **Tail-risk snapshot: fixed inverted cost-driver labels and removed the false VaR/CVaR advertising
  (audit D5/D10, #576).** (1) `_tornado_tail_stats` keyed `downside`/`upside` to the shock *direction*
  (`min(low_case)` / `max(high_case)`), so for a cost driver — whose low-cost case is the *better*
  outcome — the lender-facing tail table reported the better figure as the "downside." They are now
  keyed to the KPI *outcome*: the worst and best KPI across all of the parameter's shock cases. (2) The
  live tornado path computes only 3-point downside/upside/impact — no distributional VaR/CVaR or
  breach probability (those need Monte Carlo trial arrays) — yet the module docstring/config promised
  them and the per-metric summary echoed `cvar_alpha`/`percentiles`/`dscr_floor`, which CASPER
  surfaced verbatim as if computed. The echoes are removed and the docstrings rewritten to state
  plainly what the live path does and does not compute (the distributional helpers remain as a
  separate, explicitly-unwired MC-backed API; use `analytics.mc` for real tail risk). Re-pins the
  tests that encoded the echoes and adds a cost-driver label regression test. KPI-neutral (a
  read-only tail table; deterministic KPIs untouched); oracle byte-identical.
- **The `debt` logical module now registers validation specs; strict `['cashflow','debt']` no longer
  guards zero debt fields (audit D11, #579).** `finance.debt_v14` registered no `RequiredFieldSpec`s, so
  `get_required_fields('debt') == []` and the canonical strict validation guarded nothing on the debt
  block. The debt engine is intentionally default-tolerant (a missing `tenor_years` defaults to 15) and
  several committed scenarios carry no debt block, so the new specs are **validate-when-present**
  (`required=False`): a missing value passes untouched, but a *present* malformed value — a non-positive
  tenor, a non-numeric/negative rate, or an out-of-[0,1] gearing — now fails loud at pre-flight instead
  of silently reaching the sizer. Every committed scenario's declared debt values already satisfy these
  (full suite 3012 green; KPI oracle byte-identical). The `irr` logical module **intentionally**
  registers no config specs (IRR/NPV are computed, the discount rate lives under the `wacc`/config
  surface with a documented default, and no live caller validates `irr`); this disposition is now
  documented at `schema_guard._MODULE_IMPORTS`.
- **Run manifest no longer silently degrades its config hash (audit D8, #577).** The CLI re-loaded the
  scenario config to hash it under a bare `except` with **no log line**, so a successful run could ship
  a manifest whose `config_sha256` binds to the file *path* rather than the resolved *contents* —
  tamper-evidence void, unnoticed. Extracted `_load_manifest_config`, which logs the degrade at WARNING
  with the traceback before falling back to the non-binding `{config_path: ...}` (the run is not
  aborted). Adds happy-path and degrade-warns tests. KPI-neutral; oracle byte-identical. (The broader
  engine-stamp-the-manifest half of #577 — so direct callers also get a manifest — remains as tracked
  follow-up.)
- **Reconciled the divergent NaN wind-shear-alpha fill across the two ERA5 paths (audit D13, #580).**
  When alpha (`ln(ws100/ws10)/ln(h_hi/h_lo)`) is uncomputable, `ERA5Fetcher` filled it with a
  config-driven `alpha_default` (0.143, the 1/7-power-law coastal/neutral value) but `era5_retrieval`
  filled it with `alpha_min` (0.05, the clip *floor*) — understating shear on gap-filled hours.
  `ERA5RequestConfig` gains an `alpha_default` field (default 0.143, overridable via
  `download.alpha_default`) and `build_hub_height_series` now fills NaN alpha with it before clipping,
  matching `ERA5Fetcher`. Bounded to gap-filled hours on the wind-diagnostic path; the committed frozen
  wind export is unaffected, so no lender KPI moves — oracle byte-identical. Adds a NaN-fill regression
  test and a `from_yaml` wiring test.
- **FX pre-flight now numeric-validates `start_lkr_per_usd` and `annual_depr`, not just their presence
  (audit D14, #581).** `schema_guard._validate_fx_section` only key-presence-checked the FX mapping, so
  `fx.annual_depr: 'not-a-number'` passed the gate (the loader would raise later, but CESSPIT wants the
  gatekeeper to name the field). It now rejects a non-finite `start_lkr_per_usd`/`annual_depr` and a
  non-positive `start_lkr_per_usd`, using `float()` semantics that mirror `scenario_loader._resolve_fx`
  (so numeric strings still pass — no over-tightening). Defense-in-depth only; every committed scenario
  has valid numeric FX, so full suite (3004) and the KPI oracle are unchanged. KPI-neutral.
- **Renamed the batch `ScenarioResult` to `BatchScenarioResult` to end a name collision with the
  canonical contract (audit D9, #578).** `analytics/scenario_analytics.py` defined a structurally
  different `ScenarioResult` dataclass sharing the name of the canonical
  `analytics.contracts_v14.ScenarioResult`, with no import/alias between them — a CCCDIR
  (FRAMEWORK-03) violation where two distinct result surfaces answered to one name. The batch
  comparison container is renamed `BatchScenarioResult` (matching the neighbouring
  `BatchResultSummary`), its docstring now names the canonical contract it is distinct from, and the
  two test modules that constructed it are updated. No shim — it is an internal batch container, not a
  public contract, and the only importers were tests. KPI-neutral; oracle byte-identical.
- **Global SA now flags a structurally-flat metric instead of emitting out-of-[0,1] Sobol indices
  (audit D4, #575).** The tornado engine guards a covenant-pinned metric with `_flag_degenerate_metric`,
  but global SA (`analytics/sensitivity/global_sa.py`) had no counterpart: a near-constant `min_dscr`
  (in `DEFAULT_METRICS`; debt is sized to the DSCR target, so the ratio is invariant to the swept
  drivers) made SALib return negative `S1` and `ST>1` with no warning and spurious `interactive`
  flags. `run_sobol`/`run_morris` now pre-check each metric's output range and, when
  structurally flat, log a loud covenant-aware warning and emit zeroed, in-band indices with
  `flat_metric: True` + `flat_metric_reason`, skipping the undefined decomposition. Real metrics carry
  `flat_metric: False` and are unchanged (Ishigami structure preserved). Read-only supplementary
  section — KPI-neutral, oracle byte-identical.
- **Wind monthly-energy profile no longer collapses all 8760 hours into month 1 (audit D3, #574).**
  `EnergyCalculator.calculate_monthly_energy` ran `pd.to_datetime(df.index).month`, which on the
  `WindPipeline` orchestrator's integer `RangeIndex` read the values as epoch-nanoseconds and bucketed
  every hour into January — a silent, meaningless `monthly_profile`, masked by a `DatetimeIndex` test
  fixture and a monkeypatched calculator. A new `_month_of_row` helper uses a `DatetimeIndex` directly
  and synthesizes a reference non-leap-year hourly calendar for a positional/`RangeIndex`, so each row
  maps to its true month. Adds a regression test exercising the real `RangeIndex` shape end-to-end
  (12 months present, not one bucket). Diagnostic (`wind_resource`) path only — the bankable AEP is
  index-independent (`analytics.wind.aep_summary_builder`), so **no lender KPI moves**; KPI oracle
  byte-identical.
- **`pct_to_decimal` fails loud on out-of-range rates instead of silently mis-scaling (audit D7,
  #573).** The `finance/cashflow_v14_utils.py` normalizer read *any* value `> 1.0` as a percentage,
  so `150 → 1.5` and `1.5 → 0.015` passed silently — a fail-loud violation. It now raises for a value
  `> 100` (valid under neither the decimal `<= 1` nor the percentage `<= 100` reading), keeps the
  `(1, 100] → /100` percent branch and the `<= 1` decimal branch (negatives, e.g. deflationary
  escalation, pass through unchanged). Every value on the canonical/committed path is `<= 100`
  (capacity factor, losses, fees, tax, escalation), so it is **byte-identical** for real inputs and
  only turns a previously-silent mis-scaling into a loud error. `validate_parameters` keeps its
  field-named "out of range" errors (tax / capacity factor / grid loss / risk haircut) via a local
  wrapper that degrades an impossible rate to its raw value rather than propagating the raise, so
  strict validation still names the offending field. (Note: `finance/wacc_v14.py` carries its own
  separate `_pct_to_decimal`; left untouched as it is not on the D7 path.) Adds fail-loud and
  negative-passthrough tests; full suite green. KPI-neutral, verified via the KPI oracle.
- **Post-tax risk haircut no longer inverts on loss years (audit D6, #572).** `_apply_risk_haircut`
  used `cfads * (1 - h)`, which on a *negative* post-tax CFADS *shrank* the loss toward zero
  (`-1000 → -900`) — softening the very downside the haircut exists to stress. It now worsens CFADS
  in the adverse direction regardless of sign: the non-negative branch keeps the exact
  `cfads * (1 - h)` expression (so the committed all-positive lender case is **byte-identical**, no
  floating-point reassociation), and a negative CFADS is deepened via `cfads * (1 + h)`. The reported
  `risk_haircut_amount_lkr` is consequently `h · |posttax|` (always a reduction). The two consistency
  tests whose fixtures are loss-making are re-pinned to the sign-safe invariant; a new unit test pins
  `-1000 → -1100`. KPI-neutral on every committed scenario (all post-tax CFADS positive), verified via
  the KPI oracle.
- **A single partial-KPI Monte Carlo trial no longer crashes the whole run (audit D2, #571).**
  `MonteCarloResult` requires every `trials[]` array to share one length (row alignment for
  breach/joint analytics), but `analytics/mc/aggregate.py` skipped `None` *per key*, so one trial
  missing a single KPI (e.g. an equity distribution that failed on that draw) produced ragged arrays
  and the frozen contract raised `ValueError`, aborting the entire lender pack instead of degrading.
  Replaced with a documented **complete-case** policy: a metric is "observed" if at least one trial
  produced a finite value for it, and a trial is aggregated only if it produced a finite value for
  every observed metric; partial trials are excluded from the arrays, counted in `failed_iterations`,
  and surfaced via a new `metadata['partial_trial_count']`. Non-numeric values are treated as missing
  rather than crashing. Byte-identical on runs where every trial is complete (all committed scenarios
  and tests). Adds regression tests covering the single-partial, different-missing-keys, and
  non-numeric cases. KPI-neutral (MC robustness).
- **Monte Carlo Iman-Conover rank correlation was numerically inert (audit D1, #570).** The reorder
  in `analytics/mc/correlation.py` scattered each marginal by rank (`out[y_ranks[:, j], j] =
  col_sorted`) — the INVERSE permutation — so the induced Spearman correlation collapsed to ~0 while
  the run metadata reported `correlation_enabled=true`. The committed lender case ships
  `monte_carlo.correlation.enabled: true` with authored 0.35/0.20 pairs, so its reported P50/P90/VaR/
  CVaR/breach bands were computed as if all drivers were independent, understating joint tail risk.
  Fixed to a GATHER by rank (`out[:, j] = col_sorted[y_ranks[:, j]]`), so each column's rank vector
  matches the correlated normals' and the target correlation is reproduced (empirically: target
  ρ=0.5 → induced +0.486 post-fix vs +0.011 pre-fix) while preserving the exact marginal. Adds two
  property tests asserting the *induced* Spearman matches the target (and stays ~0 at a zero target) —
  the pre-existing wiring test only checked `a != b`, which is why the bug survived. **KPI impact:**
  MC risk bands only; the committed deterministic covenant KPIs (project/equity IRR, DSCR, NPV, LLCR,
  PLCR) are MC-independent and verified byte-identical via the KPI oracle.
- **`pyproject.toml` version synced to `VERSION` (15.0.0 → 15.1.0).** The #529 release bumped the
  `VERSION` file to 15.1.0 but left `pyproject.toml` at 15.0.0; per `RELEASING.md` the two must be
  kept in lockstep. Packaging metadata only — no code or KPI change.

### Added
- **Optional Sobol' QMC Monte-Carlo sampler (#589).** New
  `analytics.mc.samplers.generate_sobol_samples` adds a scrambled Sobol' low-discrepancy
  (quasi-Monte-Carlo) draw as an **opt-in** alternative to the canonical LHS sampler, selected
  per-scenario via `monte_carlo.sampler: "sobol"` (default `"lhs"` — **byte-identical** to every
  existing run; the deterministic base case does not invoke MC at all, so the oracle is untouched).
  Deliberately opt-in, not the default: a scrambled Sobol' net's star discrepancy is `~O((log n)ᵈ/n)`
  versus MC's `O(n⁻¹ᐟ²)` RMSE, an advantage realised only for *smooth, low-effective-dimension*
  integrands, and DutchBay's binding KPIs are **not** smooth in the drivers (`min_dscr` clamps at the
  covenant floor; `equity_irr` kinks where debt is sized) — QMC buys little there and can alias against
  the sequence, so it is offered as an honest convergence option for the smoother KPIs (`project_npv`,
  mean `project_irr`) only. Because a scrambled Sobol' net keeps its balance/discrepancy guarantee only
  at `n = 2**m` (SciPy warns, and the property is genuinely lost, if a non-power-of-2 subset is
  truncated), a requested trial count is rounded **up** to the next power of two and all `2**m` points
  are used; the engine records `sobol_n_requested` / `sobol_n_used` in `result.metadata` so a consumer
  never mistakes the effective count for the request. Scaling uses the SAME per-dimension affine map as
  LHS (`lo + u·(hi−lo)`) rather than `qmc.scale`, so a **pinned driver** (`lo == hi`, an engine-accepted
  config shape) yields a constant column instead of the raw, param-anonymous `ValueError` `qmc.scale`
  raises on a non-strict bound — Sobol never fails on a config LHS accepts (CASPER). When Sobol is
  combined with an enabled correlation block the engine emits a one-time warning: Iman-Conover
  rank-reordering preserves the marginals but destroys the *joint* low-discrepancy structure, so the QMC
  benefit is limited to the marginals. `common_random_numbers` is recorded `null` (not a misleading flag)
  on a Sobol run, since CRN is inapplicable to a deterministic net. SciPy (`scipy.stats.qmc`) is imported
  lazily inside the sampler (CASPER — the module top-level stays numpy-only). Additive, read-only —
  KPI-neutral / oracle byte-identical; full suite green. Adds discrepancy, power-of-two-rounding,
  determinism, pinned-column, sampler-normalization and engine-switch tests. Independently re-evaluated
  by a **Fable-model** 3-lens adversarial review (QMC-numerics / KPI-neutrality / contracts-CASPER):
  initial gate **BLOCK** on two confirmed one-line defects — the pinned-`lo==hi` `qmc.scale` crash and a
  sibling `MonteCarloRunMeta` `sampler="lhs"` hardcode (a latent frozen-contract lie) — both fixed and
  re-gated **MERGE**; follow-ups filed #647 (CLI requested-vs-used `n_trials`), #648 (retire dead
  `monte_carlo.sampling_method` + wire `MonteCarloResult.sampling_method`), #649 (vestigial RunMeta).
  (This is the last of the P1
  methodology backlog; see the 2026-07-02 SOTA link-research digest for why QMC is framed as opt-in.)
- **PAWN (moment-independent) global sensitivity analysis (#591).** New
  `analytics.sensitivity.global_sa.run_pawn` adds a distribution-based (Kolmogorov-Smirnov) SA index
  alongside the variance-based Sobol/Morris. PAWN (Pianosi & Wagener 2018) stays bounded in [0,1] and,
  unlike variance-based Sobol, does not misbehave on bimodal / DSCR-floor-pinned outputs — exactly the
  DutchBay case — so it is the right complement for skewed KPIs (`min_dscr`, `equity_irr`). It is a
  given-data method (`SALib.analyze.pawn`, zero new dependency), driven here by its own LHS sample, and
  reports the **median** KS statistic per driver (with mean / CV). Empirically confirmed that a
  structurally-flat metric (a covenant-pinned `min_dscr` carrying only FP jitter) produces *spurious*
  non-zero PAWN indices, so the same `_is_flat_output` / `_flat_metric_reason` guard the Sobol path uses
  is applied — flagging and zeroing rather than reporting noise. A finite-sample noise floor (~0.15
  median KS for an inert driver at `n=256`, `s=10`) is documented. Additive, read-only — KPI-neutral /
  oracle byte-identical; full suite green. Adds Ishigami-ranking and flat-metric tests. (`run_pawn` is a
  standalone API for now; CLI/report wiring — and a shared partial-NaN finite-mask for
  Sobol/Morris/PAWN — are tracked follow-ups. Independently re-evaluated by a Fable-model adversarial
  review, gate MERGE.)
- **Monte Carlo convergence diagnostic (#590).** New `analytics/mc/convergence.py` computes a
  read-only per-metric convergence trace from the final trial arrays — running mean plus the CI
  half-width `err_k = z · sd_k / √k` (95% by default; equivalent to a Welford online accumulator) at
  log-spaced checkpoints ending at `n` — and the engine attaches it to `result.metadata["convergence"]`
  (headline `final_rel_ci_halfwidth = err_N / |mean|`, reported as `null` when the mean is within one
  half-width of zero — its sign is not even resolved, and the committed lender IRRs sit near zero, so a
  naive `|mean|` denominator would blow up to a spurious huge number), so a reader can see whether
  `n_trials` sufficed for THIS scenario. Each per-metric block is tagged `statistic: "mean"`. Deliberately
  a diagnostic, not an early-stopping rule: it never changes `n_trials` or any reported band (that would
  move the P50/P90 bands), so it is **KPI-neutral / oracle byte-identical**. Documents its limits (i.i.d.
  normal SE is approximate under LHS; bounds the MEAN only — P90/P95/P99/ES converge slower, so a tight
  mean-CI does not certify the bands a lender reads). Adds unit + engine-integration tests. (Independently
  re-evaluated by a Fable-model adversarial review — gate MERGE; its near-zero-mean and self-marker nits
  applied here; a P90 order-statistic CI is filed as a follow-up.)
- **CASPER payload now surfaces the lender-grade Monte Carlo risk table (`mc_risk`).** The
  `analytics.mc.exports.build_casper_risk_blocks` builder — a P50 + P90/P95 *downside* (exceedance)
  table for DSCR/IRR/NPV/LLCR/PLCR plus `Prob(DSCR < floor)` and the worst-year DSCR P95, computed
  from raw MC trial arrays — had **no production consumer** (flagged in the #576 tail-risk follow-up:
  it is the genuine distributional VaR/CVaR-style tail risk the one-way tornado path structurally
  cannot produce). It is now wired into `_casper_to_dict` as an additive `mc_risk` block. CASPER
  discipline: it degrades to `null` (never crashes the payload) when Monte Carlo was not run, when the
  result is summary-only (no raw `dscr_min` trial array), or when the optional `pandas` export
  dependency is absent; the DSCR covenant floor is resolved **config-first** from
  `debt_covenants.dscr_threshold` (falling back to the documented `CovenantSpec` default and surfaced
  explicitly in the emitted covenant block — no silent floor); the `DataFrame` is converted to
  JSON-safe records. Additive customer-visible key, so no `casper_result_v1` version bump (same posture
  as the earlier `generation` / `technology_breakdown` additions). Cells are **strict-JSON**-safe
  (non-finite floats — the covenant-row `NaN` placeholders — map to `None`, matching the payload's
  None-for-missing convention, so `json.dumps(allow_nan=False)` does not raise), and the guard is
  narrowed to the sanctioned degradation paths (`KeyError`/`RuntimeError`/`ImportError`) so a genuine
  bug propagates rather than being swallowed. Adds surfaced/absent/summary-only/config-first-floor/
  strict-JSON tests. Read-only; KPI-neutral (oracle byte-identical). Re-scopes the `mc/exports.py` item
  in #583 from "remove dead code" to "wired". (Adversarially reviewed against GWTF/CESSPIT/CCCDIR/CASPER
  before merge; the floor-source-consistency and docs follow-ups are tracked separately.)
- **Committed lender case now declares full assumption provenance (#481 RPT-2 follow-up).** The
  `dutchbay_lendercase_2025Q4.yaml` scenario gains an `evidence_register.entries` block declaring a
  source · as-of · tier for all 10 material assumptions (tariff, capex, opex, capacity_factor, fx,
  debt_terms, degradation, inflation, tax, discount_rate) — so the report's Evidence Register renders
  **10 of 10 covered** and the deepened Assumptions Register shows real provenance instead of
  em-dash. Honestly tiered against the development-readiness register: the flat 20.3 LKR tariff and
  the indicative debt terms are `assumption` (not yet executed), FX is `measured`, capex / opex /
  degradation / tax are `benchmark`, and capacity factor / discount rate are `derived`. A pure
  detector (`enforce: false`) — verified byte-identical KPIs (projIRR 0.0268 / minDSCR 1.30 / NPV
  −$65.46M / CFADS $202.33M unchanged). KPI-neutral.
- **Real end-to-end lender-report integration test (#481, RPT-7/8).** Adds
  `tests/integration/test_lender_report_e2e.py`: it drives a `WindFarmInputs` submission through the
  production report path (scenario → `run_finance_case` → `build_report_context` →
  `render_report_html`) and asserts the live pipeline KPIs reach the report, every major section
  renders (incl. the cash-flow waterfall and the three statements), the rendered waterfall's total
  CFADS ties to the headline `total_cfads_usd` KPI, the production builder's tornado + Morris
  global-SA sections render, and the auth-gated `POST /cases/report.html` route renders over HTTP —
  plus a gated PDF-render smoke. (The pre-existing `tests/integration/test_assessment_report.py`
  covers the solar script, not the lender report.) Test-only; KPI-neutral.
- **Async arq worker formalized as a deferred, Redis-gated follow-up (#481, RPT-6).** Documented
  the as-built status of the async ERA5 path in `docs/WEB_SERVICE_ROADMAP.md` — the worker
  (`app/jobs/worker.py`) and `RedisJobStore` are built and unit-tested but NOT wired; the live
  `POST /jobs` path runs in-process via `BackgroundTasks` / `InMemoryJobStore` through the
  `get_store` seam; the cutover (route enqueues to arq + `get_store` returns a `RedisJobStore`
  behind `[jobs]`) is a single Redis-gated switch that cannot be CI-verified without a live Redis.
  Added a gated import smoke test (`tests/app/test_jobs_worker.py`, skipped without the `[jobs]`
  extra) that guards the worker module against bit-rot. No production code change; KPI-neutral.
- **Assumptions register deepened + run-manifest left-aligned (#481, RPT-2/RPT-4).** The report's
  assumptions register now shows value · source · as-of · impact: source and as-of are
  cross-referenced from the scenario's evidence register where a material assumption maps to the
  line (no fabricated provenance — blank otherwise), and impact is a static, model-grounded note of
  the KPI each assumption most directly moves (tariff/resource dominate revenue; CAPEX drives
  gearing; FX erodes LKR revenue). Source/as-of are inert (render em-dash) until a committed
  scenario declares `evidence_register.entries`; populating that provenance is a separate data
  task. A malformed register (e.g. a bad `min_tier`) now degrades the cross-ref + evidence section
  gracefully instead of failing the whole report. Separately, the run-manifest values (run id,
  engine version, git SHA, config hash — identifiers, not numbers) are now left-aligned instead of
  right-aligned-numeric. Additive, read-only, KPI-neutral.
- **Cash-flow waterfall by payment priority in the report (#481, RPT-2).** New
  `analytics.three_statement.build_cashflow_waterfall` regroups the engine's OWN published
  per-operating-year USD figures into the lender priority cascade — CFADS (`cf_pre_debt`, the
  risk-haircut CFADS the DSCR uses) → scheduled senior debt service (`debt_service_total`, the DSCR
  denominator) → balloon sweep at maturity (shown SEPARATELY: senior to equity but excluded from
  the scheduled DSCR) → cash to equity (`cf_after_debt`) — per operating year plus project-life
  totals. Sourced from the engine, NOT reconstructed, so the section ties line-for-line to the rest
  of the report (CCCDIR — one source of truth): total CFADS matches the headline CFADS KPI and the
  scheduled debt service matches the Debt Structure & DSCR Profile section, so the report never
  presents two contradictory coverage numbers. The model sweeps 100% of post-senior cash to equity.
  Additive, read-only, KPI-neutral.
- **Synchronous-route hardening: PDF-filename sanitisation + bounded, time-limited compute (#481,
  RPT-9).** The `POST /cases/report.pdf` download filename is now sanitised
  (`_sanitise_filename_component`, `[A-Za-z0-9._-]` only) before it is interpolated into the
  `Content-Disposition` header, so no variant can break the quoted string or inject header bytes
  (defence in depth — the only current caller passes a constrained scenario-variant literal). The
  synchronous `/cases*` compute routes now run under a wall-clock ceiling (`_run_with_timeout`,
  default 120 s, env-overridable via `DUTCHBAY_SYNC_ROUTE_TIMEOUT`): a pathological hang returns
  `504` and frees the request instead of blocking the worker indefinitely. Honest limitation: the
  worker thread cannot be force-cancelled, so the ceiling bounds the client wait, not the
  computation — therefore the compute is also concurrency-bounded
  (`DUTCHBAY_SYNC_ROUTE_MAX_CONCURRENCY`, default 8) with a `503` load-shed when full, and a
  timed-out compute *keeps its slot for the worker thread's full lifetime* (held via
  `asyncio.shield`), so a slow client cannot accumulate unbounded background compute. The route
  `operation_id`s are pinned (`run_case` / `run_case_report_html` / `run_case_report_pdf`) so the
  client-facing API contract is decoupled from internal handler renames. KPI-neutral.
- **Three-statement output (P&L / cash flow / balance sheet) + tie-out checks (#479).** New
  `analytics.three_statement` assembles the three articulating statements from the engine's own
  outputs (no new finance logic), presented in USD (the reported-KPI numeraire — LKR P&L lines
  converted at each year's FX; the per-year debt figures are read from the engine's enriched
  `annual_rows` columns `interest_usd` / `debt_service_total` / `balloon_resolution`, which are
  phase-correct and fold the construction bridge into operating year 1, rather than re-derived
  from raw period indices). The balance sheet balances **by construction** (equity is the
  funding plug; cash, debt, depreciation and retained earnings roll forward), so
  `balance_sheet_balances` / `cashflow_reconciles` / `retained_earnings_rolls` are articulation
  invariants asserted as a guard against a builder regression. The genuinely **independent**
  tie-out is `debt_retires_to_residual`: the per-row principal + balloon repayments must
  amortise the engine's stated drawn debt down to its stated balloon residual (it has teeth —
  catches a debt stream that does not retire the financed debt). Surfaced as a report section
  with the tie-out status + the three statements. Verified on the committed hybrid and wind-only
  lender cases: balance residual $0.00, debt-retirement residual $0.00, year-1 interest incl.
  the bridge, the lender case's balloon residual carried correctly. Additive, read-only, KPI-neutral.

### Changed (KPI-moving — interim VERSION 15.0.0 -> 15.1.0, now shipped in 15.2.0)
- **Solar TMY ingest + hourly thermal; committed hybrid solar P50 re-baselined (#529,
  SOLAR-6/12).** `solar_resource.pv_producer` gains an opt-in `resource.solar.tmy_path`: when
  a FROZEN hourly TMY is supplied it uses the TMY's measured hourly GHI/DNI/DHI **and** its
  hourly ambient temp / wind for Faiman cell temperature (SOLAR-12), replacing the clear-sky
  year scaled to `annual_ghi_kwh_m2` and the scalar annual-mean temperature. Absent
  `tmy_path` the clear-sky path is byte-identical. Provenance: **frozen** (a committed PVGIS
  TMY at `inputs/solar_tmy/kalpitiya_pvgis_tmy_8.27N_79.75E.csv`), keeping finance
  pvlib/network-free + reproducible (the #469 ERA5 discipline).
  **KPI-MOVING re-baseline of the committed hybrid** (`dutchbay_hybrid_windsolar_2025Q4`):
  the frozen PVGIS TMY's real GHI (1871 kWh/m², vs the declared 2000) plus hot-hour thermal
  lower the modelled solar P50 CF **0.179 -> 0.1685 (-5.9%)**, solar AEP 78.4 -> 73.8 GWh,
  the blended project CF 0.295502 -> 0.292997, combined net P50 542.7 -> 538.1 GWh and net
  P90-1yr 475.1 -> 471.0 GWh (`aep_summary_dutchbay_hybrid.json`). The P90 binds the gearing
  (D4.6), so the hybrid financials move: **project_irr 0.01958 -> 0.01855, equity_irr
  -0.0272 -> -0.0285, project_npv -91.65M -> -92.67M, total CFADS 237.78M -> 235.66M;
  min_dscr holds 1.30** (debt sculpted to target). The wind-only lendercase is unaffected
  (no solar). Pins updated: scenario YAML, the frozen AEP summary, and
  `tests/finance/test_hybrid_scenario.py`.

### Added
- **Measure-correlate-predict (MCP) for the long-term wind resource (#477, WIND-1).** New
  `wind_resource.mcp` correlates a short on-site mast record against the concurrent ERA5
  reference and applies the fitted transfer to the full long-term reference to predict the
  long-term on-site wind-speed distribution (IEC 61400-15-2 / MEASNET). Two methods:
  `variance_ratio` (default — preserves on-site variance and the energy-relevant tail) and
  `linear_regression` (OLS; variance-deflating, diagnostic). Returns the transfer, the
  predicted long-term mean, and a Weibull fit of the predicted distribution (reusing
  `fit_weibull_on_series`). Opt-in via `resource.wind.mcp.enabled` — sites without a mast keep
  raw ERA5 (the default), so committed scenarios are byte-identical; like the other producer
  physics it feeds the frozen export only at a dated, authorized re-baseline. KPI-neutral.
- **Multi-technology report section + shared-POI curtailment seam (#476, ARCH-4/5).**
  **ARCH-4:** the lender report now renders a Multi-Technology Breakdown section for hybrid
  plants — per-technology net AEP, AEP/CFADS/CAPEX shares, OPEX and cost-of-equity, plus the
  financed-vs-attributed CAPEX residual and project blended WACC. Pure presentation, reusing
  the ARCH-2 generation view and the ARCH-3 work-breakdown; rendered only for 2+ generation
  technologies and omitted for single-tech/legacy reports. **ARCH-5:** a shared
  point-of-interconnection curtailment model (`analytics.portfolio.poi_curtailment`)
  computes, from per-technology hourly injection profiles against
  `generation.shared_poi.limit_mw`, the energy curtailed when combined injection exceeds the
  shared export limit (physically lost, distinct from grid-instructed curtailment the SPPA
  pays as deemed energy). Opt-in: absent a POI limit or hourly profiles it returns nothing,
  so curtailment is not modelled for any committed scenario (the DutchBay 220 kV line is a
  separate CEB project, not a binding POI; the seam dovetails with the hourly profiles
  tracked in #529). Both additive and **financially KPI-neutral** — no committed scenario's
  economics change; the committed hybrid's rendered report gains the additive Multi-Technology
  Breakdown section (presentation only).
- **Multi-tech residuals: margin-weighted per-tech CFADS + technology-type pre-flight
  validation (#488, ARCH-2/6).** **ARCH-2:** the multi-tech generation view
  (`build_multi_tech_from_run`) now apportions the run's combined CFADS by per-technology
  **operating margin** (revenue = net AEP x per-tech tariff / FX, minus per-tech opex from
  the ARCH-3 work-breakdown) instead of by raw AEP, so a technology with a different tariff
  or opex intensity gets a correct CFADS share (the old AEP split mis-attributed it). It
  remains an exact partition of the run's actual tax-netted CFADS (tax is project-level, not
  per-tech), and falls back to the AEP split (byte-identical) for single-tech or when
  FX/tariff do not resolve — so committed economics are unchanged (additive view).
  **ARCH-6:** `validate_config_for_v14` now rejects an unrecognised
  `generation.technologies.<name>.type` at pre-flight (against `finance.tech_types`), so a
  typo (`wnid`) or unsupported class (`battery`) fails fast (CESSPIT) rather than slipping
  downstream; untyped blocks remain the backward-compatible key-sniff path. KPI-neutral.
- **Per-technology cost/return work-breakdown (#475, ARCH-3).** New
  `analytics.portfolio.tech_wbs.build_multi_tech_wbs` + `MultiTechWBS` /
  `TechnologyCostReturn` contracts attribute a hybrid's reporting CAPEX/OPEX and per-tech
  cost-of-equity to each technology and **reconcile** the per-tech allocations against the
  financed totals: CAPEX against the debt engine's resolved total
  (`finance.debt_v14._extract_capex_usd`, so `derive_from_breakdown`/QRA scenarios
  reconcile honestly), OPEX against the project OPEX. A positive `capex_residual_usd` is
  the legitimate shared/balance-of-plant bucket; an allocation exceeding the financed
  total beyond tolerance fails loud (CESSPIT). The reconciliation #448 deferred. Per-tech
  WACC is **disclosure-only** (it does not feed financed economics); the blended
  `project_wacc_nominal` is supplied from the run's resolved WACC (build-up scenarios
  compute it in-pipeline from sized debt). Surfaced on `CasperResult.multi_tech_wbs` and
  in the CASPER JSON payload. Additive, read-only, **KPI-neutral** (the intentional
  phantom-capex decoupling is preserved; finance still reads one financed total).
  Financing a per-tech WACC into the blended cost of capital is a separate, KPI-moving,
  explicitly-authorized step (a decision point, not done here).
- **Solar yield cross-validation + audit dispositions (#485, SOLAR-4/7/8/9/10; SOLAR-6/12 deferred).**
  Added a SOLAR-10 cross-validation test pinning the pvlib producer's specific yield against the
  independent SolarGIS PVOUT reference for the site (1524 kWh/kWp, within ±10%) plus the
  SAM/PVsyst tropical fixed-tilt envelope (1450–1700) — KPI-neutral (reads the computed yield; no
  scenario/AEP mutation; solar P50/P75/P90 already shipped in #469). Re-verified the other
  findings against the code and documented their dispositions in `pv_producer`: **SOLAR-4**
  (producer is year-1 by design; multi-year degradation is the finance schedule's job — a
  producer curve would double-count), **SOLAR-7** (`pvlib.disc` is documented to take TRUE
  zenith, which it's given; Hay-Davies correctly uses apparent — the mixed convention is
  correct), **SOLAR-8** (`pdc0 = ac_nameplate/eta` saturates the inverter at the AC nameplate
  and the clip DOES engage at DC 50 MWp / ILR 1.2), and **SOLAR-9** (bifacial is a report-stage
  `cf_mono`/`cf_bifacial` disclosure only; the financed yield is monofacial) are all correct
  as-is. **SOLAR-6 (TMY ingest) + SOLAR-12 (hourly thermal) were deferred here and are now
  IMPLEMENTED in #529 (the "Changed (KPI-moving)" entry above)** — a frozen PVGIS TMY moved the
  committed hybrid solar P50 0.179 -> 0.1685. KPI-neutral (this #485 slice itself).
- **Wake-source disclosure + opt-in live PyWake at the headline (#478, WIND-2).** The headline
  AEP build now resolves the wake loss through `_resolve_wake_loss` and stamps a `wake_source`
  into the AEP summary. Default = the documented FROZEN `resource.losses.wake_loss_pct` — which
  for the lender case IS the granular PyWake Bastankhah result, computed offline with the real
  15-turbine layout and the SW-dominant wind rose, then frozen (the dependency-light
  frozen-export pattern; py_wake, like pvlib, is in zero CI lanes). A scenario can drive the
  wake LIVE by setting `resource.wake.model_live: true` and supplying the complete faithful
  inputs (`coordinates.x_m`/`y_m`, `wind_rose_freq`, a Ct-carrying curve); the live path FAILS
  LOUD on any missing input rather than silently degrading to a uniform-rose computation that
  would be *less* faithful than the frozen value. Verified the audit's premise was wrong — the
  headline already reflects the granular wake model, so this is **KPI-neutral**: the committed
  lender supplies no live spec → frozen path → headline byte-identical (still 464.3 GWh), now
  with `wake_source: "frozen_config_pct"` disclosed.
- **Spatial-representativeness diagnostic + single-cell disclosure (#484, WIND-10/3).** The
  resource assessment uses a single ERA5 cell, implicitly assuming it typifies the site
  neighbourhood — which can bias AEP on a coastal/ridge gradient. Added
  `wind_resource.era5_grid.spatial_representativeness(cells, n)`: given an n×n (odd) cell
  neighbourhood it computes the hub-height wind-speed spread `(max-min)/mean` and the centre
  cell's deviation from the neighbourhood mean, and flags `representative` when both are within
  tolerance (read-only — it never alters AEP). The single-cell `era5_retrieval.run()` output now
  carries an honest `spatial_representativeness: {assessed: false, reason: …}` block instead of
  leaving the limitation unstated, pointing to the n×n grid path that can populate it. WIND-3:
  documented (in `aep_tornado.gross_aep_farm_gwh`) that its implicit cut-out handling
  (`np.interp(right=0.0)`) and `bankable_aep`'s explicit cut-out zeroing are a bounded,
  verified <0.1% modelling-style difference — not a bug — and the committed 464.3 GWh is the
  frozen summary value regardless. Closes #484; KPI-neutral.
- **Interannual-variability validation: computed-vs-assumed (#484, WIND-6).** The bankable P90
  build-up uses an `UncertaintyBudget.interannual_variability_pct` (IEC default 4.0%) while
  `wind_analyzer.calculate_interannual_variability` independently computes the site's IAV
  (`cov_annual_ws`) from the ERA5 annual means — but the two were never compared, so the
  assumed 4.0% was asserted blind. Added `interannual_variability_drift(computed, assumed)`
  (mirroring the Weibull-drift check): it reports the percentage-point drift, a
  `within_tolerance` flag, and whether the assumed sigma is conservative vs the data, and the
  `wind_pipeline` summary now surfaces it as `interannual_variability_check`. Validate-mode
  only — it never mutates the budget or the committed P90 (404.4 GWh); adopting the measured
  IAV stays a deliberate, dated config edit. Also corrected the audit's "all hardcoded"
  premise: every category sigma is already config-drivable via `resource.uncertainty.*` — the
  values in `UncertaintyBudget` are IEC defaults, documented as such. KPI-neutral.
- **Energy-weighted Weibull goodness-of-fit + wind methodology honesty (#484, WIND-4/5/8/9).**
  The headline Weibull fit reported only a CDF `r_squared`, which is bulk-dominated and masks
  misfit in the high-wind TAIL — exactly where energy concentrates (power ∝ v³). Added
  `energy_moment_gof_pct` (and an `energy_gof_pct` field on `WeibullFit`/`as_dict`): the
  relative error of the fitted third moment `A³·Γ(1+3/k)` vs the empirical `mean(v³)` — a
  curve-independent, tail-sensitive diagnostic that flags an energy-relevant tail misfit a high
  R² would hide (WIND-9). The fit docstring now documents the pooled-all-hours temporal-
  invariance assumption and when a time-stratified fit would be needed (WIND-8). The lender
  scenario's P50 over-prediction haircut justification was **de-circularised** (WIND-5): the
  2.0% is now grounded in the site-independent pre-construction over-prediction literature
  (~0–7% range) as a conservative policy choice, with the project's own EIA demoted to an
  ex-post consistency check rather than the basis; the value was already parameterised. And the
  `EnergyCalculator` docstring records the verified disposition (WIND-4): the audit's
  "double-counts wake / mislabels gross" claim is **unfounded** — the module applies the loss
  stack exactly once and labels gross correctly, and it is off the finance path (a diagnostic
  timeseries integrator), so no fix was warranted. All KPI-neutral (diagnostic + docs; the
  frozen headline 464.3 GWh is untouched).
- **Default inter-driver correlation on the lender Monte-Carlo (#487, MC-7).** The Iman-Conover
  rank-correlation machinery (`analytics.mc.correlation`) was wired but DORMANT — no scenario
  declared a matrix, so the six lender MC drivers sampled independently, understating joint
  tail structure. The canonical `dutchbay_lendercase_2025Q4.yaml` now ships a documented 6×6
  default correlation: **capex↔opex +0.35** (capital and operating costs co-move → fattens the
  cost-overrun tail) and **capacity_factor↔curtailment +0.20** (on a constrained grid, windy
  high-output periods are exactly when congestion forces curtailment, so the two rise together).
  FX is left **uncorrelated on purpose** — unlike a USD-indexed PPA, the flat-LKR CEB PPA has no
  revenue/FX link — and the administered tariff is independent. A new
  `align_correlation_to_params` re-indexes the matrix onto the engine's ACTIVE parameters via
  the spec's `param_names`, so a consumer that overrides `monte_carlo.parameters` (e.g. the
  fx-calibration mode's single driver) subsets gracefully instead of hitting a shape mismatch.
  **KPI impact: MC-band stats only** — the deterministic lender case and every `expected_results`
  pin are unchanged. The correlation modestly *narrows* the band (the CF↔curtailment hedge
  dominates the cost-clustering in IRR leverage): at n=2000/seed 42, project-IRR VaR(95%)
  −0.0158→−0.0139, equity-IRR CVaR −0.1246→−0.1210, std 0.0207→0.0202.
- **Monte-Carlo fail-loud on toy fallback, opt-in (#473, MC-9).** The MC engine substitutes
  deterministic *toy* KPIs when a trial's full v14 evaluation raises (so a smoke run on a
  minimal config still yields an array). On a real run that means evaluation FAILED for that
  trial — the toy KPIs are fabricated. A scenario can now refuse the fallback with
  `monte_carlo.allow_toy_fallback: false`, which RAISES on the first failed trial instead of
  silently reporting fabricated KPIs; the resolved value is echoed in
  `result.metadata["allow_toy_fallback"]`. Default `true` keeps smoke tests and existing runs
  byte-identical. The engine docstring also now documents the common-random-numbers scope
  (CRN applies *within* a run; pairing two runs/variants on shared draws is done externally by
  passing the same seed + param set — by design, not a defect). KPI-neutral.
- **BESS availability liquidated-damages derate, opt-in (#486, BESS-2).** A standalone-BESS
  scenario that has a measured or projected monthly availability can now opt into the CEB
  tender's liquidated-damages formula — `derate = clip(1 - 2*(0.97 - MA), 0, 1)` (a month at/
  above the 97% guarantee = no penalty; 94% = 0.94) — by supplying
  `generation.technologies.<bess>.revenue.monthly_availability_pct` in place of the static
  `availability_factor`. Absent the new key the static factor is used, so every committed
  scenario is byte-identical. The module docstring also now documents BESS-6: the energy-tariff
  charging energy is uncosted on purpose (the BESS charges from a separate co-located solar PV
  plant the EPC owns; `round_trip_efficiency` already books the dispatch loss, so a
  charging-cost line would double-count).
- **Solar PV P50/P75/P90 uncertainty + itemised loss chain (#469, SOLAR-2).** The solar
  producer gained a real bankable uncertainty model mirroring the wind IEC 61400-15-2
  build-up: a config-first `SolarUncertaintyBudget` (IEA-PVPS Task 13 / IEC 61724-1
  categories) and `exceedance_levels_solar` (`solar_resource/exceedance.py`), sharing the
  one normal-distribution z-table now in `analytics/core/exceedance.py` (wind re-imports it —
  parity-tested, no fork). `compute_solar_aep` gained an optional `emit_exceedance` build-up
  and an itemised, config-first loss taxonomy (`defaults.solar_resource.loss_taxonomy` +
  `solar_resource/loss_model.py`, reusing the generic wind retention engine) that decomposes
  the flat `system_loss_pct`. `build_solar_cashflow_export` can now emit P75/P90. All of this
  is pvlib-free and additive (existing P50-only calls byte-identical). The hybrid scenario's
  `net_aep_p90` is now MODELLED (475.1 GWh = wind 404.4 + solar 70.7-1yr) rather than a
  ratio-preserved placeholder; this is reporting-only (`bind_downside` is false, so P90 does
  not bind debt/IRR — financed KPIs unchanged). The financing-policy switch to bind P90 to
  gearing is deliberately NOT included (a separate, KPI-moving decision).
- **GWTF governance rule `DELIVERY-01` ("Dolphins, not whales").** Codified the
  delivery-cadence principle as a new "Delivery Cadence" theme in
  `go_with_the_flow_rules_v3_0_clean.csv`: manage and ship all work as small,
  complete, frequently-surfacing increments (SMACs) rather than one large,
  long-submerged "whale" effort. It is the overarching philosophy that the
  code-level Dolphin Strategy (`REFACTOR-01..04`) implements for refactoring,
  generalised to all work (features, audits, docs, migrations). Inserted ahead of
  `REFACTOR-01`; ruleset now 62 rules (README count updated). Governance/docs-only,
  KPI-neutral.

### Changed
- **Honest label on the AEP Monte-Carlo loop (#487, MC-6).** The per-scenario AEP loop in
  `analytics/simulation/monte_carlo_aep.py` was commented "vectorized for speed" but is a
  genuine Python `for` loop — each scenario draws its own 8760-hour wind series and runs the
  power curve. (The five loss-factor *samplings* above it ARE vectorised.) Full vectorisation
  is infeasible — an `n×8760` wind array is ~7 GB of float64 at the production n=100k — so the
  comment was corrected to describe the per-scenario loop honestly rather than relabelling work
  that cannot be done. KPI-neutral (comment-only).
- **Monte-Carlo RNG isolation + modern Generator (#473, MC-5).** Migrated the three legacy
  `np.random` call sites to an isolated `numpy.random.default_rng` (PCG64). The genuine defect
  was `analytics/simulation/monte_carlo_aep.py`, which seeded the **process-global**
  `np.random` state (`np.random.seed`) and drew from module-global `np.random.normal/weibull`
  — non-isolated and not thread-safe (any other code touching `np.random` could perturb it,
  and vice-versa). `analytics/wind/mc_aep_weibull.py` and `analytics/capital_risk_layer_v14.py`
  were already isolated (`RandomState(seed)`) but on the legacy API; both moved to
  `default_rng` for consistency. Same seed still reproduces (MRM-01). **KPI impact:
  MC-band sidecar stats only — NOT the lender case or any committed scenario KPI.** The
  bankable AEP (deterministic Weibull integration) and the IEC exceedance P90 are untouched;
  only the uncertainty-simulation band values shift, by Monte-Carlo sampling noise between the
  two bit streams (on the test mock at n=2000, seed 42: p50 290.2→283.8, p90 204.8→196.3 GWh),
  which shrinks ~1/√n at production scale. Every affected test is structural/tolerance/
  reproducibility-based (e.g. `p50 ≈ 402.6 ±10`, exceedance ordering, same-seed equality) and
  stays green. Test fixtures that use `RandomState` to generate *synthetic input data* were
  left as-is (they are test inputs, not the production RNG).
- **Quarantined the built-but-unwired stress-test engine (#473, MC-2/3/4).** `StressTestEngine`
  (`stress_tests_v14`) was implemented and tested but reachable from NO production path — no
  Hydra CLI, pipeline, report, or app imports it (the only "use" was a commented-out stub in
  `scripts/run_full_pipeline_sprint12.py`). Moved it `analytics/ → legacy/` (now an importable
  quarantine package) so the production tree honestly reflects what runs; its test moved to
  `tests/legacy/` (still exercised so the code keeps working if reactivated, but out of the
  analytics coverage gate), and its now-stale CCCDIR import-allowlist entry was dropped. A
  banner on the module + a `legacy/README.md` note record why it was quarantined and how to
  reactivate it. The audit's other MC-2/3 targets were **verified wired/shimmed and left as-is**
  (`optimization_v14` via the solar-assessment script, `capital_risk_layer_v14` via its CLI
  runner, `sensitivity_v14`/`sensitivity_pareto` are deprecation shims). MC-4: the module's
  `var_95_usd`/`cvar_95_usd` are documented as **deterministic stress losses, not statistical
  VaR/CVaR** (the only mislabel — now in frozen legacy); the genuinely-empirical VaR/CVaR in
  `analytics/core/risk_metrics` + `analytics/sensitivity/tail_risk` were verified honest and
  unchanged, and the `capital_risk_layer` `p90 = percentile(aep, 10)` flagged by review is the
  **correct exceedance convention** (P90 = 10th pct), not a bug — left untouched. KPI-neutral.
- **Storage-only scenarios declare `capacity_factor: 0.0` honestly (#486, BESS-5).** The
  cashflow capacity-factor validator (all three guard surfaces: the `RequiredFieldSpec` in
  `cashflow_v14.py` and both checks in `cashflow_v14_params.py`) now admits a literal `0.0`
  for a storage-only scenario whose revenue is the BESS capacity charge, not generation —
  retiring the `0.0001` placeholder that the two CEB BESS scenarios carried to slip past the
  former strict-positive bound. Negatives and values `> 1`/`> 100%` remain config errors.
  `resolve_bess_specs` additionally guards `revenue.contract_years` against the resolved
  project life and **raises** when the BESS contract would run past the project horizon.
  KPI-neutral: both CEB scenarios (capacity-charge `projIRR 0.00615 / eqIRR -0.03840 / NPV
  -$2.33M`; night-peak `projIRR 0.09719`) are byte-identical with `0.0` vs `0.0001`. The
  API wizard's `WindFarmInputs` still rejects `capacity_factor: 0.0` (a wind farm needs a
  positive CF) — that surface is deliberately unchanged.
- **Hybrid lender case: the bankable P90 now binds the gearing (D4.6).**
  `scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml` sets `Financing_Terms.bind_downside: true`
  + `downside_aep_source: p90`, so the MODELLED net P90 (475.1 GWh, #469 dolphin 4c) — which
  was previously reporting-only — now constrains debt. The engine sizes a second gearing
  against a P90 cashflow (annual CFADS x the real P90/P50 ratio 475.1/542.7 = 0.8754) at the
  same 1.30 DSCR floor (`target_dscr_p90` defaults to `target_dscr`) and binds `min(P50, P90)`.
  P90 binds (`binding_production_case: P90`), shrinking the gearing 0.4225 -> 0.3675 (-13.8%
  debt). **KPI impact** (hybrid scenario only; wind-only lender case and the CEB BESS scenarios
  untouched): equity IRR -0.06115 -> **-0.02722 (+339 bps)**, LLCR 1.302 -> **1.497**, PLCR
  1.348 -> **1.550**, avg DSCR 1.387 -> 1.443, and — notably — the maturity **balloon collapses
  from 39.8% to 0%** (the smaller debt fully amortises over the 15-year tenor, resolving the
  long-flagged ~40-57% balloon). project IRR is unlevered and **unchanged** (0.019578); min DSCR
  holds 1.30; total CFADS is debt-independent and unchanged. project NPV edges down -$89.78M ->
  **-$91.65M** (the larger equity slice raises the build-up WACC). This is the lender-prudent
  reading — debt that services even at P90 — and it de-risks a structure whose 13.39% LKR debt
  was destroying equity value at the ~2% project return. `tests/finance/test_hybrid_scenario.py`
  and the hybrid tornado tests (`tests/analytics/test_multi_tech_tornado.py`: balloon_pct now
  joins min_dscr as structurally flat) re-pinned.
- **CEB BESS scenarios opted into MDSC state-of-health fade + augmentation (#470d, BESS-1/4).**
  The two committed CEB battery scenarios now exercise the year-indexed degradation and
  augmentation levers shipped KPI-neutral in #501/#502 (they previously booked a perfectly
  FLAT charge). `scenarios/ceb_bess_10mw_capacity_charge.yaml` gains
  `revenue.mdsc_fade_pct_annual: 0.011` (conservative-low LFP; field average is 2-3%/yr, so a
  2-3%/yr downside sensitivity is recommended) and a year-10 cell `augmentation_schedule`
  restoring SoH to nameplate. The augmentation capex is the HONEST SoH-gap cost, **not** a full
  replacement: by operating year 10 SoH has faded to `(1-0.011)^9 = 0.9052` (a 9.475% / 3.79 MWh
  shortfall), so replacing only the lost cells at a year-10 LFP unit price (~$120/kWh; NREL ATB
  2024 / Lazard LCOS) is `0.09475 x 40,000 kWh x $120/kWh = $455,000` (the directional unit test
  uses a deliberately-oversized $5M full-replacement stress amplitude, ~11x the honest top-up).
  `scenarios/ceb_solar_bess_nightpeak_10mw.yaml` gains `revenue.mdsc_fade_pct_annual: 0.005`
  (an optimistic / calendar-dominated bound for its shallow-DoD daily cycle; no augmentation over
  the shorter 10-year term). **KPI impact** (these two illustrative scenarios only; the wind-only
  lender case and the hybrid are untouched):
  - CEB capacity-charge: project IRR 0.02098 -> 0.00615 (-148 bps), equity IRR -0.04182 ->
    -0.03840 (+34 bps, *up* — the lower CFADS profile resizes the dual-DSCR debt down, de-levering
    a structure whose 13.4% LKR debt was destroying equity value), min DSCR holds 1.30, LLCR
    1.269 -> 1.345, project NPV -$2.05M -> -$2.33M. The year-10 augmentation costs ~254M LKR
    (= $455k after ~10 years of 5.89%/yr LKR depreciation on the USD-priced cells — honest FX
    erosion of an imported-cell cost).
  - CEB night-peak: project IRR 0.09995 -> 0.09719 (-28 bps), equity IRR 0.09029 -> 0.08438
    (-59 bps), min DSCR holds 1.30, project NPV +$0.395M -> +$0.312M.

  `tests/finance/test_bess_scenario.py` re-pinned from flat-revenue to the fade-then-augment
  shape (RUN+SHAPE pinned, not the illustrative bid economics, per the file's convention).
- **Solar P50 re-baselined to the pvlib-modelled CF for the hybrid lender case (#469).**
  `scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml` now bills solar off the pvlib-MODELLED
  P50 capacity factor (`generation.technologies.solar.capacity_factor` 0.20 -> 0.179, -10.5%)
  produced by `solar_resource.pv_producer`, replacing the prior declared 0.20. The blended
  headline `project.capacity_factor` re-blends to 0.295502, the bankable references
  (`expected_results`, `scenarios/aep_summary_dutchbay_hybrid.json`) drop solar to 78.4 GWh
  net P50 (combined 542.7 GWh), and the Monte-Carlo capacity-factor band recenters on the
  new base. **KPI impact** (hybrid scenario only): project IRR 0.02162 -> 0.01958 (-20 bps),
  equity IRR -0.0576 -> -0.0612, project NPV -$87.60M -> -$89.78M, CFADS $242.00M -> $237.78M
  (-1.7%); min DSCR holds at 1.30 (debt sculpted to the target). Solar AEP share 15.9% ->
  14.4%. `tests/finance/test_hybrid_scenario.py` re-pinned. The solar P90 preserves the prior
  P90/P50 ratio pending the dedicated PV P50/P90 step (#469 dolphin 4); the wind-only
  lendercase is unaffected. Delivered behind the frozen-export adapter from #494 (dolphin 1).
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
- Finance correctness cluster (#482, FIN-3/5/7/8/10/12; KPI-neutral): FIN-3 — the reported
  `effective_tax_rate` now divides tax by TAXABLE INCOME, not EBIT (reporting-only, lender-
  audit honesty). FIN-10 — `approx_project_irr` returns `None` on non-convergence instead of
  an unverified final-bracket midpoint (FIN-01; converged cases unchanged). FIN-5 (reviewed):
  sculpted principal is shared PRO-RATA BY BALANCE across tranches — documented as the
  deliberate pari-passu inter-creditor convention; cost-weighted ("retire the dearest debt
  first") allocation is non-standard and KPI-moving, so NOT adopted. FIN-7 (reviewed):
  depreciation tail-forfeiture past project life is the intentional, correct SL-tax treatment
  (the warning is the right response; committed scenarios use `start_year=1` so nothing is
  forfeited) — documented. FIN-8 (reviewed): the loss-vintages params-dict threading is a
  deliberate, byte-identical, contained side-effect (the vintages tuple cannot ride in the
  float-typed row) — documented; a return-tuple refactor is deferred as risk-disproportionate.
  No committed KPI moves (full finance+analytics suite green). FIN-12 (equity-WHT under-charge
  guard) is tracked as a follow-up on #482 — a distinct module needing its own careful guard.
  FIN-12 now CLOSED: `equity_distribution_v14_hydra` fails loud on an ENABLED-but-rate/data-
  ABSENT WHT inconsistency — interest/dividend WHT enabled without its rate, or `wht_gross_up`
  enabled while a row lacks `interest_usd` — which the gated idiom would otherwise resolve to
  0 and OVERSTATE equity IRR/NPV on a raw public-API config. Fire-on-inconsistency only (an
  explicit 0.0 rate is legitimate; absence-while-enabled raises); KPI-neutral — every
  committed scenario declares its rate and none set `wht_gross_up: true`.
- Money precision decision: keep float64 (#480, ADR): added
  `docs/MONEY_PRECISION_DECISION.md` recording the keep-`float` decision for the money path,
  backed by a measurement on the real lender cashflow — the float64-vs-exact-`Decimal` NPV
  error over the 20-year schedule is 1.31e-5 LKR (~4e-8 USD; relative error 2.4e-16, i.e.
  machine epsilon), ~10 orders of magnitude below lender precision. A `Decimal` migration
  would be a large, KPI-moving change interacting badly with the numpy/scipy numerics for
  zero material benefit. Documents the existing compute-in-float / present-rounded policy.
  Docs-only, KPI-neutral.
- Gate the enum-only generation technologies (#474, ARCH-1): `tidal` / `hydro` /
  `geothermal` / `run_of_river` are recognised generation types for classification and
  aggregation but are backed by no resource model, so billing one previously produced a
  SILENT, unvalidated flat `capacity_factor x tariff`. `resolve_tech_generation_specs` now
  fails loud on an explicitly-typed unmodelled generation tech unless the block sets
  `allow_unvalidated_flat_cf: true` (the explicit experimental-proxy opt-in) — so a user can
  never silently get a fake result. Added `MODELLED_GENERATION_TYPES = {wind, solar}` +
  `is_modelled_generation_type()` and the supported-tech matrix to `finance/tech_types.py`.
  KPI-neutral: no committed scenario uses a typed enum-only tech; wind/solar/BESS and
  untyped (key-sniffed) generation blocks are unaffected.
- Code-quality cleanup (#490, QUAL-6/7/8/10/11): archived 16 verified-unreferenced one-off
  developer shell scripts (fix/cleanup/phase/rollback/deploy/sprint-validation helpers) +
  the stray root "AAA - instructions" file to `legacy/dev_scripts/`, and the drifted
  sprint-snapshot docs (`SPRINT15_SECOND_ITERATION_FIXES.md`, `sprint_16/REGRESSION_TEST_SUITE.md`
  — the latter referenced the validator deleted in #472) to `legacy/sprint_snapshots/`
  (QUAL-7/8/10; GWTF R12 legacy isolation; live tooling such as the venv/setup, `gwtf-*`,
  release and sensitivity-validation scripts was left in place). QUAL-6 (repo-wide `black`):
  the `black --check .` CI step is deliberately advisory (`|| true`) so legacy/excluded code
  need not be reformatted — the engine packages are already black-clean (enforced by
  pre-commit + the scoped `analytics/fx/` gate), and a 243-file repo-wide reformat is
  intentionally NOT performed. QUAL-11: the full 3.11+3.12 matrix runs on push + nightly, the
  accepted safety net for the PR-time 3.12-only leg. Cleanup only, KPI-neutral.
- Property-based finance invariants (#491, audit §4.10): added the repo's first Hypothesis
  property tests (`tests/finance/test_finance_invariants_property.py`) asserting structural
  invariants across input ranges that pinned examples can't — NPV at 0% equals the
  undiscounted sum, NPV is additive in cashflows and monotone-decreasing in the discount
  rate for conventional series, a converged IRR is a numerical root of NPV, and the BESS
  state-of-health curve stays in `[floor, 1]` and is non-increasing without augmentation.
  Deterministic (`derandomize=True`, no deadline) for reproducible CI (MRM-01). Hypothesis
  is already a dev dependency. Test-only, KPI-neutral.
- Release workflow now publishes a GitHub Release (#457): `release-run.yml` (which fires
  only on a pushed `v*` tag) gained a step that packages the lendercase artifacts as
  `DutchBay_Model_V<version>.zip` (version from the `VERSION` file) and creates/updates the
  GitHub Release for the tag via the built-in `gh` CLI (no new action dependency; idempotent
  on re-tag; hyphenated tags marked pre-release). Previously it only kept a workflow-run
  artifact, so RELEASING.md §7's "creates a Release" claim was inaccurate and the v15.0.0
  Release had to be made by hand — §7 is now accurate. Added `contents: write` to the job.
  CI/docs only, KPI-neutral.
- Finance tax-scope + dead-code (#483, FIN-1/2/4): (FIN-1) deleted the parallel
  `finance/tax_v14.py` engine (a legacy `TaxCalculatorV14` wrapper with contradictory
  silent defaults — corporate rate 0.30 / 15-yr SL depreciation — that contradicted the
  canonical schema-strict `finance/cashflow_v14_tax.py`) plus the dead `finance/tax/`
  re-export package and its smoke test; nothing in production imported any of it.
  (FIN-2) removed the unused, unexported, self-contradictory `DEFAULT_TAX_CONFIG`
  (its `loss_carryforward_years=25` disagreed with the real `TaxProfile` default of 0).
  (FIN-4) documented the tax scope in the canonical engine's docstring: SSCL (2.5%) is
  modelled as a revenue deduction; VAT (18%) is deliberately excluded as a recoverable
  pass-through (cashflow-neutral to a BOO SPV), not a project P&L cost. KPI-neutral
  (no live consumer; no cashflow/debt path touched).
- Pipeline residuals (#489, PIPE-3/6): (PIPE-3) the FX spot cross-assert
  (`_assert_fx_spot_consistency`) — the one load-time integrity guard the in-memory
  service seam (`app.services.run_finance_case`, the web `/cases` + hybrid path) still
  skipped — now runs there too, so a caller cannot submit a scenario whose FX spot keys
  disagree and get a self-inconsistent lender pack (the #236 stale-FX class) silently; it
  is a no-op for consistent scenarios (KPI-neutral) and MC paths do not route through this
  seam. (PIPE-6) removed the dead `enable_sensitivity` / `enable_monte_carlo` /
  `enable_scenario_comparison` toggles from `analytics.pipeline_analytics_v14` (their
  helpers were stubs that silently returned `None`; real sensitivity lives in
  `analytics.sensitivity` + the report tornado, real MC in `analytics.mc`) along with the
  now-orphaned local result contracts and the `SCENARIO_COMPARISON_AVAILABLE` flag. The
  live `enable_returns` / `enable_risk` path is unchanged. KPI-neutral.
- Pipeline convergence + dead-validator removal (#472, PIPE-1/2): deleted the orphaned
  `analytics/contracts_v14_validators.py` (a post-execution result-bounds validator wired
  into no production path, duplicating the live `schema_guard` pre-flight; its `IRR_MIN`
  bound would in fact false-positive on this project's legitimately-negative IRRs) and its
  two test modules + the now-empty WACC-fence allowlist entry. Clearly marked
  `run_scenario_analytics_v14.py` as the deliberately LIGHTER batch-comparison path (it is
  NOT the canonical engine — informational WACC, no equity waterfall) vs the canonical
  `run_full_pipeline_v14.py` (→ `pipeline_v14_enhanced`), in both the CLI docstring and
  `docs/ARCHITECTURE.md`. KPI-neutral (dead-code removal + documentation only).
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
