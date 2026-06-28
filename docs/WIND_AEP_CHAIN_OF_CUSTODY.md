# Wind → AEP Chain of Custody

**Project:** DutchBay 150 MW Wind Farm (Kalpitiya, Puttalam District, Sri Lanka)
**Document purpose:** Lender / DFI technical-advisor (TA) provenance trace from raw atmospheric reanalysis through to the Annual Energy Production (AEP) figure that enters the v14 financial model.
**Scope:** Wind resource → Weibull fit → power curve + losses → AEP P50/P75/P90 → finance.
**Audience:** Lender's independent engineer, DFI environmental/technical due diligence, internal audit.
**Status:** Issue #27 (docs / P2 / DFI / audit).

> **Read this first — two distinct pipelines exist in the repo.**
> 1. **FINANCED PATH** — package `wind_resource/*`. This is the code that ingests ERA5, fits Weibull, applies the power curve and losses, produces P50/P75/P90 AEP, and feeds the v14 finance model via `wind_resource/cashflow_adapter.py`. It is gated and green in CI (installed via the `[wind]` extra; round-trip test `tests/wind/test_cashflow_adapter.py`).
> 2. **AUXILIARY / NON-REVENUE PATH** — `analytics/loader/aep_loader.py` + `analytics/simulation/monte_carlo_aep.py` + `analytics/power_curves/oem_parser.py`. This is a **risk-quantification (Monte Carlo) and Data-Lake loader** stack. Its power curve is a **10 MW PLACEHOLDER extrapolated from the 6.5 MW certified curve** (the module says so in its own comments). It must **not** be treated as the source of the bankable energy yield until OEM-certified 10 MW data replaces the placeholder.
>
> A lender's TA should audit the financed path for the energy yield and treat the auxiliary path as a sensitivity/uncertainty overlay only.

---

## 1. Executive provenance summary

| Link | Module (financed path) | Input | Output | Provenance stamped? |
|------|------------------------|-------|--------|---------------------|
| 1. Reanalysis source | `wind_resource/era5_fetcher.py` | Copernicus CDS `reanalysis-era5-single-levels` (u/v @ 10 m & 100 m) | `era5_<site>_<start>_to_<end>.csv` | **Yes** — `_save_metadata()` writes a JSON sidecar (source, resolution, config values, download timestamp) |
| 2. Hub-height extrapolation | `wind_resource/era5_fetcher.py::extrapolate_to_hub_height` | `ws_100m`, per-hour shear `alpha` | `ws_150m` | Partial — shear `alpha` and reference height carried in metadata |
| 3. Weibull fit | `wind_resource/wind_analyzer.py::fit_weibull` | `ws_150m` timeseries | shape `k`, scale `c`, R², KS p-value | **Yes** — fit stats embedded in assessment JSON |
| 4. Power curve | `wind_resource/energy_calculator.py::_load_power_curve_from_config` | `wind_resource/config/power_curves.yaml` | interpolated P(v) | **Yes** — turbine model + rated capacity in assessment `config` block |
| 5. Losses + P-levels | `wind_resource/energy_calculator.py::calculate_net_aep` | gross AEP, `losses`, `p_levels` (from `era5_config.yaml`) | net AEP P50/P75/P90 | **Yes** — `total_loss_factor` + `individual_losses` returned |
| 6. Assessment export | `wind_resource/wind_pipeline.py::run_complete_assessment` | all of the above | `<site>_assessment_*.json` | **Yes** — full `metadata` block (assessment date, location, data period, version) |
| 7. Cashflow handoff | `wind_resource/wind_pipeline.py::export_for_cashflow_model` → `wind_resource/cashflow_adapter.py` | assessment JSON, scenario YAML | patched v14 scenario dict + `wind_resource` provenance block | **Yes** — adapter stamps `source`, `scenario`, `net_aep_mwh`, `capacity_factor_decimal`, `adapter_mode`, `adapter_tolerance_pct` |
| 8. Finance consumption | `finance/cashflow_v14_params.py` | scenario `project.capacity_factor` | v14 cashflow / DSCR | n/a (downstream) |

---

## 2. Link-by-link audit trail (FINANCED PATH — `wind_resource/*`)

### Link 1 — Reanalysis source: ERA5 / ECMWF via Copernicus CDS

**Module:** `wind_resource/era5_fetcher.py` (class `ERA5Fetcher`, header version "1.1.0 (CCCDIR Compliant)", `era5_fetcher.py:1-24`).

- **Source dataset:** Copernicus Climate Data Store, product `reanalysis-era5-single-levels`, `product_type='reanalysis'` (`era5_fetcher.py:280-291`).
- **Variables downloaded:** 10 m and 100 m u/v wind components, sourced from config not hardcoded — `self.variables = self.config['variables']` (`era5_fetcher.py:145`, `era5_fetcher.py:284`). The config lists `10m_u/v_component_of_wind` and `100m_u/v_component_of_wind` (`wind_resource/config/era5_config.yaml`, `variables:` block).
- **Spatial extent:** a box of `±area_buffer_degrees` (0.5°) around the site (`era5_fetcher.py:268-274`; buffer from `era5_config.yaml api.area_buffer_degrees: 0.5`). Grid resolution declared `0.25°` (`era5_config.yaml api.grid_resolution`).
- **Temporal coverage:** all months/days/hours across the requested year range (`era5_fetcher.py:285-288`); default assessment window `2014-12-01` → `2025-12-31` (`wind_pipeline.py:153-155`).
- **Credentials:** `~/.cdsapirc` (referenced in error path, `era5_fetcher.py:296-298`).
- **Wind metrics derived:** wind speed `ws_10m`/`ws_100m = sqrt(u² + v²)`, meteorological direction, and per-hour shear exponent `alpha = ln(ws_100/ws_10) / ln(10)` (`era5_fetcher.py:359-370`). `alpha` is clipped to `[alpha_min, alpha_max]` and NaN-filled to `alpha_default` from config (`era5_fetcher.py:373-374`; config `wind_shear: alpha_min 0.05, alpha_max 0.40, alpha_default 0.143`).

**Provenance metadata stamped (audit-grade):** `ERA5Fetcher._save_metadata` writes a per-download JSON sidecar to `inputs/wind_data/metadata/<file>_metadata.json` containing: `source = "ERA5 Reanalysis via Copernicus CDS"`, `spatial_resolution = "~31km (0.25°)"`, `temporal_resolution = "hourly"`, `download_timestamp`, `config_file` path, and the full `config_values` snapshot (`era5_fetcher.py:449-475`). **This is the lender's reproducibility anchor for the raw-data link.**

> **TA caveat — ERA5 is reanalysis, not measurement.** ERA5 is a modelled atmospheric reanalysis at ~31 km grid resolution, not on-site met-mast data. The lender scenario itself acknowledges this: `data_confidence: "Medium (5-year ERA5 validated against 1-year met mast)"` (`scenarios/dutchbay_lendercase_2025Q4.yaml`, `wind_resource.data_confidence`). For bankability, ERA5 should be MCP-correlated (Measure-Correlate-Predict) against a site mast; the code does not perform MCP — it extrapolates ERA5 directly.

### Link 2 — Hub-height extrapolation (power law)

**Module:** `wind_resource/era5_fetcher.py::extrapolate_to_hub_height` (`era5_fetcher.py:378-432`), invoked at `wind_pipeline.py:206`.

- **Method:** power law `ws(h) = ws_100m * (h / h_ref)^alpha` using the per-hour shear `alpha` and config `reference_height` (100 m) (`era5_fetcher.py:425`; `reference_height = self.config['wind_shear']['reference_heights'][1]`, `era5_fetcher.py:149`).
- **Target hub height:** 150 m (default `WindPipeline(hub_height=150.0)`, `wind_pipeline.py:77`). Produces column `ws_150m` (`era5_fetcher.py:422`).
- **Guard:** raises if `hub_height <= reference_height` (`era5_fetcher.py:409-413`).

> **TA caveat — single-mast-free shear.** The shear exponent is derived purely from the ERA5 10 m/100 m pair, then clipped to `[0.05, 0.40]`. There is no terrain/roughness model and no measured shear. Extrapolation from 100 m to 150 m is a 1.5× height ratio; sensitivity to `alpha` should be checked in the lender's independent yield review.

### Link 3 — Weibull fit

**Module:** `wind_resource/wind_analyzer.py::fit_weibull` (`wind_analyzer.py:146-205`), invoked via `analyze_all()` at `wind_pipeline.py:213`.

- **Method:** maximum-likelihood estimation, `scipy.stats.weibull_min.fit(ws_data, floc=0)` returning shape `k` and scale `c` (`wind_analyzer.py:169-172`). Method is config-driven (`weibull.method: mle`, `wind_analyzer.py:135`, `era5_config.yaml`).
- **Goodness-of-fit emitted:** R² of empirical vs theoretical CDF and a Kolmogorov–Smirnov p-value (`wind_analyzer.py:184-199`). These are the auditable fit-quality stamps.
- **Also computed:** temporal patterns (monthly/seasonal/diurnal, `wind_analyzer.py:207-256`) and **inter-annual variability** CoV (`wind_analyzer.py:277-319`) — the latter is the basis for the P-level spread a lender expects.

> **TA note.** The Weibull fit is performed on the **full hub-height timeseries** (all hours pooled). The R² and KS p-value are stamped into the assessment JSON (`wind_pipeline.py:280-283`), so a reviewer can independently judge distributional fit.

### Link 4 — Power curve

**Module:** `wind_resource/energy_calculator.py::_load_power_curve_from_config` (`energy_calculator.py:164-215`).

- **Source of truth:** `wind_resource/config/power_curves.yaml`. The financed default turbine is **`envision_en171_6p5`** — the Envision EN-171/6.5, **rated 6,500 kW**, cut-in 3.0 / rated 12.0 / cut-out 25.0 m/s (`power_curves.yaml:4-15`). This default is hard-set in `WindPipeline.__init__(turbine_model='envision_en171_6p5')` (`wind_pipeline.py:78`).
- **Interpolation:** `scipy.interpolate.interp1d(ws, power, kind='linear', bounds_error=False, fill_value=(0,0))` — zero power outside the tabulated range (`energy_calculator.py:205-210`).
- **Provenance stamped:** turbine model name, `rated_capacity_kw`, and total capacity are written into the assessment `metadata.configuration` and `energy_production.config` blocks (`wind_pipeline.py:236-242`, `energy_calculator.py:484-489`).

> **TA caveat — financed curve is 6.5 MW; the scenario declares 10 MW.** The financed `wind_resource` path defaults to the **6.5 MW** Envision curve (`power_curves.yaml:4`, `wind_pipeline.py:78`), whereas the v14 lender scenario and the auxiliary AEP summary both describe a **10 MW** machine (`scenarios/dutchbay_lendercase_2025Q4.yaml` `turbine.model: "Envision EN-171-10.0 (Extrapolated)"`, `rated_power_mw: 10.0`; `tests/mocks/aep_summary_dutchbay.json` `rated_power_kw: 10000`). **There is no certified 10 MW power curve in the financed path** — `power_curves.yaml` contains only 6.5/5.6/5.5 MW machines. This turbine-class mismatch must be reconciled (either by adding a certified 10 MW curve to `power_curves.yaml` or by confirming the project is on 6.5 MW machines). See §4.

### Link 5 — Losses and P-level scenarios → net AEP

**Module:** `wind_resource/energy_calculator.py` (`calculate_gross_aep` `energy_calculator.py:263-302`; `calculate_net_aep` `energy_calculator.py:304-361`).

- **Gross AEP:** mean power over all hours × 8760 h × number of turbines (`energy_calculator.py:279-291`).
- **Loss stack (multiplicative, config-driven):** `_calculate_total_loss()` multiplies every factor in the config `losses` block (`energy_calculator.py:252-261`). From `era5_config.yaml`:
  - availability 0.97 (3% downtime)
  - grid_curtailment 0.98 (2%)
  - electrical 0.98 (2% transmission)
  - wake 0.95 (5%)
  - environmental 0.99 (1% degradation/icing)
  - **Combined ≈ 0.876 (≈12.4% total loss)** — product of the five factors above.
- **P-levels (applied on top of losses):** `net_p{50,75,90} = gross × total_loss × p_levels[...]` (`energy_calculator.py:335-337`). From config `p_levels`: **P50 = 1.00, P75 = 0.90, P90 = 0.80** (`era5_config.yaml`, commented "P75 … LENDER BASE").
- **Provenance stamped:** `calculate_net_aep` returns `total_loss_factor` and the full `individual_losses` dict alongside the three net AEP values and their net capacity factors (`energy_calculator.py:345-355`).

> **TA caveat — P-levels are flat scalars, not statistically derived.** The P75/P90 outputs are produced by multiplying the P50 by fixed config constants 0.90/0.80 (`era5_config.yaml p_levels`), **not** by propagating the inter-annual variability or uncertainty budget through a distribution. The variability CoV is computed (`wind_analyzer.py:277-319`) but is **not** wired into the P-level scalars. A lender expecting an IEC-61400-15-style uncertainty build-up (inter-annual + measurement + model + future-variability, combined and mapped to exceedance probabilities) will find this is a **deterministic haircut**, not a derived exceedance. The Monte Carlo on the auxiliary path (§3) is the only place a distribution is actually sampled — but it runs on the placeholder 10 MW curve.

### Link 6 — Assessment export (the audit artifact)

**Module:** `wind_resource/wind_pipeline.py::run_complete_assessment` (`wind_pipeline.py:152-266`).

Writes `outputs/wind_assessment/<site>_assessment_<start>_to_<end>.json` (`wind_pipeline.py:259-261`) containing a complete `metadata` block: assessment timestamp, location, data period + data-point count, configuration (hub height, turbine model, rated capacity, total MW), and version string (`wind_pipeline.py:228-244`). This JSON is the **single auditable artifact** a TA should request — it joins raw-data provenance (Link 1 sidecar), the Weibull fit (Link 3), and the loss/P-level stack (Link 5) in one file.

### Link 7 — Handoff to the v14 financial model

**Modules:** `wind_resource/wind_pipeline.py::export_for_cashflow_model` (`wind_pipeline.py:299-364`) → `wind_resource/cashflow_adapter.py::wind_export_to_scenario_patch` (`cashflow_adapter.py:255-394`).

- **Export contract:** `export_for_cashflow_model(scenario='P75')` emits a dict with `annual_generation_mwh`, `capacity_factor_percent`, revenue, capacity, turbine count, PPA years, tariff and FX (`wind_pipeline.py:343-355`). **P75 is the default / lender base case** (`wind_pipeline.py:299`, mirroring the config comment).
- **Boundary validation:** the adapter validates the export against the Pydantic `WindCashflowExport` model, which enforces positivity and a unit sanity check that capacity factor is a **percent** (rejects values ≤ 1.0 that would indicate a decimal slipped in) (`cashflow_adapter.py:135-169`).
- **Merge into scenario YAML:** the adapter maps `capacity_factor_percent → project.capacity_factor` (converting percent→decimal), plus capacity, tariff and FX (`cashflow_adapter.py:188-213`). It writes to `project.capacity_factor` specifically because that is the slot the canonical lender scenarios occupy — the highest-priority slot the finance reader actually finds populated. The reader checks `project.capacity_factor_pct` first (priority 1), but the lender scenarios leave that empty, so `project.capacity_factor` (priority 2) is the operative slot; writing to any lower-priority slot would be silently shadowed (`cashflow_adapter.py:39-56`).
- **Lender-defensible default mode:** `adapter_mode='fill_if_absent'` (`cashflow_adapter.py:260`) **refuses to silently overwrite** a human-curated YAML value; instead it validates that the wind export agrees with the existing scenario value within `tolerance_pct` (default **0.5%**, `cashflow_adapter.py:89-95`) and raises `WindAdapterDriftError` on drift (`cashflow_adapter.py:358-367`). A `validate_only` mode exists for CI to prove an approved YAML still matches the latest wind run (`cashflow_adapter.py:30-36`).
- **Provenance stamped into the scenario:** the adapter always writes a `wind_resource` block carrying `source`, `scenario`, `net_aep_mwh`, `capacity_factor_decimal`, `adapter_mode`, `adapter_tolerance_pct`, turbine count, rated capacity and PPA years — even in `validate_only` mode (`cashflow_adapter.py:371-392`). **This is the trace that lets an auditor tie a finance run back to a specific wind assessment.**

**Design isolation (important for the lender):** the adapter is a **pure function** with no I/O, and it deliberately does **not** import `cdsapi`/`xarray`/`netcdf4` (`cashflow_adapter.py:1-16`). This means the **finance consumer can run off a frozen wind-export JSON without Copernicus credentials or the NetCDF toolchain** — the heavy `[wind]` extra is only needed by the *producer* of the export (`pyproject.toml` lines 38-48; producer = `scripts/run_wind_analysis_v14.py`, consumer = `run_full_pipeline_v14.py` + `cashflow_adapter`).

### Link 8 — Finance consumption

**Module:** `finance/cashflow_v14_params.py`. The v14 parameter builder reads capacity factor from a priority-ordered list, with `project.capacity_factor` as the canonical lender-case home (`cashflow_v14_params.py:217-230`, and validation at `cashflow_v14_params.py:511-529`). The wind adapter writes to exactly this slot (Link 7), so the energy yield flows cleanly into the cashflow / DSCR engine. Wind revenue itself is computed by `finance/cashflow_v14.py::_calculate_revenue_lkr` (net energy × the LKR/kWh tariff; call site `cashflow_v14.py:319`).

---

## 3. The AUXILIARY / NON-REVENUE path (do NOT use for the bankable yield)

This stack exists for **AEP uncertainty quantification (Monte Carlo)** and **Data-Lake provenance loading**, not to generate the financed energy yield.

### 3a. AEP loader — `analytics/loader/aep_loader.py`

- Loads a pre-computed AEP summary JSON/CSV (`load_aep_from_summary`, `aep_loader.py:93-200`) and validates the `source_id` against an **approved manifest** `APPROVED_SOURCES` (`aep_loader.py:42-59`, `aep_loader.py:160-167`).
- **Provenance is strong here:** computes a **SHA-256 checksum** of the data (`aep_loader.py:80-90`, `aep_loader.py:187`), records IEC standard version, validation timestamp, `derived_from` lineage, and absolute file path into a `provenance` block (`aep_loader.py:181-190`); can export a lender audit report (`export_provenance_report`, `aep_loader.py:229-255`).
- **The summary it loads for DutchBay** (`tests/mocks/aep_summary_dutchbay.json`) is itself flagged: `"notes": "10 MW turbine data is EXTRAPOLATED from 6.5 MW baseline. Replace with OEM-certified data when available."` and `source_id: "OEM_ENVISION_EN171_10_PC"` with certificate "CGC-B-FNc-2024-184 (extrapolated)".

> **TA caveat — this is a mock under `tests/mocks/`.** The lender scenario points `resource.aep_summary_path` at `tests/mocks/aep_summary_dutchbay.json` (`scenarios/dutchbay_lendercase_2025Q4.yaml`). A figure consumed from a path under `tests/mocks/` is, by definition, **not production data**. The SHA-256/manifest machinery is sound, but the *content* is a placeholder.

### 3b. OEM power-curve parser — `analytics/power_curves/oem_parser.py` (config-sourced; placeholder retired)

- **Updated 2026-06-28:** the hand-typed 10 MW *placeholder* curve and the 6.5↔10 MW symbol
  *aliasing* this section previously described have been **REMOVED** from `oem_parser.py` (see the
  module's own history note at the top of the file). The module no longer fabricates curve data
  (GWTF ARCH-01); the canonical curve is the **config-sourced Envision EN-171/6.5** (`CANONICAL_CURVE_KEY
  = "envision_en171_6p5"`, loaded from `wind_resource/config/power_curves.yaml`). There is no longer a
  `iec_certificate` / `power_curve_version` placeholder field nor a "CRITICAL placeholder" warning.
- Air-density correction is still applied per IEC 61400-12-1 (`P_site = P_ref·(ρ_site/ρ_ref)^(1/3)`).
- `parse_envision_en171_curve(...)` now returns the real EN-171/6.5 curve from config, not an
  extrapolated placeholder. (Note: this parser remains an **auxiliary** path — the financed bankable
  AEP comes from the `wind_resource` pipeline; the OEM parser feeds only the secondary `monte_carlo_aep`
  tooling. Real 10 MW *reference* curves (IEA/DTU/NREL) live in `power_curves.yaml`, selectable by slug.)

### 3c. Monte Carlo AEP — `analytics/simulation/monte_carlo_aep.py`

- 100k-scenario Monte Carlo sampling Weibull A/k (±10%) and wake/availability/electrical losses, producing P50/P75/P90/P99 and 95% CI (`monte_carlo_aep.py:71-301`). Loss/Weibull means default from the loaded AEP summary (`monte_carlo_aep.py:139-152`).
- It **synthesises** an 8760-hour wind series from sampled Weibull params (`np.random.weibull`, `monte_carlo_aep.py:210`) — it does **not** use the ERA5 timeseries from the financed path. If `weibull_a` is not supplied it is back-estimated from capacity factor via a labelled **"Heuristic"** (`monte_carlo_aep.py:145-149`).
- It computes AEP via `compute_aep_from_curve` using the **placeholder** curve (`monte_carlo_aep.py:160`, `monte_carlo_aep.py:213-222`).

> **TA caveat — auxiliary Monte Carlo is non-revenue and curve-placeholdered.** This path is suitable as a *sensitivity/uncertainty overlay* once the placeholder is replaced, but its absolute AEP values inherit the extrapolated 10 MW curve and a synthetic (not site-measured, not ERA5-driven) wind series. Do not lift its P50 into the term sheet.

---

## 4. Cross-path consistency check (numbers a TA must reconcile)

There are **two different energy-yield figures** in the repository for the same project, on two different turbine assumptions:

| Quantity | FINANCED path / lender scenario | AUXILIARY mock summary |
|----------|-------------------------------|------------------------|
| Turbine | Envision EN-171 **6.5 MW** curve (financed default, `power_curves.yaml:4`, `wind_pipeline.py:78`); scenario *declares* 10 MW "(Extrapolated)" | Envision EN-171 **10 MW** placeholder (`oem_parser.py:60-72`) |
| Net AEP P50 | **473.8 GWh** (`scenarios/dutchbay_lendercase_2025Q4.yaml` `expected_results.net_aep_p50_gwh`) | **402.6 GWh** net (`tests/mocks/aep_summary_dutchbay.json net_site_aep_gwh`) |
| Capacity factor | **0.339** (`scenarios/dutchbay_lendercase_2025Q4.yaml project.capacity_factor`) | **0.307** (`aep_summary_dutchbay.json capacity_factor`) |
| Total losses | 14.48% (financed mock `aep_summary_dutchbay_10mw.json losses.total_loss_pct`, IEC-61400-15-2 build-up) | 12.4% (`aep_summary_dutchbay.json total_loss_pct`) |
| Turbine basis | 15 × IEA-10MW (198 m), ERA5-fitted Weibull A=8.199/k=2.665 | EN-171/6.5 characterization mock (retained sensitivity machine) |
| Source label | "ECMWF ERA5 Reanalysis 2020-2024", med confidence vs 1-yr mast | "OEM_ENVISION_EN171_10_PC (extrapolated)" |

**Reconciliation actions for the data room (issue #27 follow-ups):**
1. **Resolve the turbine class.** The financed `power_curves.yaml` has no certified 10 MW curve; the scenario and auxiliary summary assume 10 MW. Confirm the contracted turbine and load the matching **OEM-certified** curve into `wind_resource/config/power_curves.yaml`.
2. **Replace the placeholder.** `oem_parser.py:39-42` and `aep_summary_dutchbay.json` notes both demand OEM-certified 10 MW data. Until then, neither path's 10 MW AEP is bankable.
3. **RESOLVED (#237 re-baseline + #268 reconciliation guard).** The two figures are now two *different turbine bases* by design, not an inconsistency: the financed path is the canonical **15 × IEA-10MW** (473.8 GWh / CF 0.339, ERA5-fitted Weibull) and the auxiliary mock is the retained **EN-171/6.5** characterization machine (402.6 GWh / CF 0.307). The financed cashflow resolves `project.capacity_factor` generically (`cashflow_v14_params.py` via `CAPACITY_FACTOR_PATHS`), and the AEP↔CF reconciliation guard (#268, `analytics/aep_reconciliation.py`) now FAILS LOUD if `capacity_mw × CF × 8.760` diverges from the declared bankable net AEP — so the financed yield can no longer silently diverge from its own bankable AEP. The earlier 563/0.428 vs 485/0.375 figures were the discredited pre-re-baseline values.
4. **Move the AEP summary out of `tests/mocks/`.** A production scenario should not reference `tests/mocks/aep_summary_dutchbay.json` (`scenarios/dutchbay_lendercase_2025Q4.yaml resource.aep_summary_path`).

---

## 5. Controls, gating and reproducibility (what makes this auditable)

- **CI gating (financed path is green):** the `[wind]` extra (xarray/netcdf4/cdsapi) is installed in the test and lint jobs (`.github/workflows/test-suite.yml` lines ~40 and ~125; `.github/workflows/ci_v14_fastlane.yml:38`), and the full `tests/` tree is run (no path-omission dodging — see the in-workflow note in `test-suite.yml`). The adapter round-trip test `tests/wind/test_cashflow_adapter.py` proves a wind P75 AEP flows through to `finance.cashflow_v14` within ±0.5%.
- **mypy gate:** a strict, complete-annotation gate runs in CI (`test-suite.yml`, "Code Quality Checks" job) over the full typed surface — `mypy finance/ analytics/ wind_resource/ solar_resource/ api/ app/ analysis_tools/` plus the root entrypoints, with **no `--ignore-missing-imports`** (every untyped third-party dep is declared per-module in `mypy.ini`). The wind/finance surface is type-checked.
- **Config centralisation (CCCDIR / GWTF ARCH-01):** loss factors, P-levels, shear limits, tariff and FX are all read from `wind_resource/config/era5_config.yaml`; turbine curves from `power_curves.yaml`. No hardcoded loss/P-level constants in the financed calculator (`energy_calculator.py:149-160`, `energy_calculator.py:252-261`, `energy_calculator.py:335-337`).
- **Provenance artifacts to request in the data room:**
  1. ERA5 download sidecar(s): `inputs/wind_data/metadata/*_metadata.json` (Link 1).
  2. Wind assessment JSON: `outputs/wind_assessment/<site>_assessment_*.json` (Link 6).
  3. The patched scenario `wind_resource` block (adapter provenance, Link 7).
  4. The AEP-loader SHA-256 provenance report (auxiliary, `export_provenance_report`).

---

## 6. Lender / DFI red-flag register (grounded in code)

| # | Finding | Evidence | Severity |
|---|---------|----------|----------|
| R1 | 10 MW power curve is a **placeholder extrapolated from 6.5 MW**; not OEM-certified | `oem_parser.py:39-42`, `:70-71`, `:117`; `aep_summary_dutchbay.json` notes | High — blocks bankable yield until replaced |
| R2 | Financed `wind_resource` path defaults to **6.5 MW** curve while scenario/auxiliary assume **10 MW** | `power_curves.yaml:4`, `wind_pipeline.py:78` vs `scenarios/...lendercase...yaml turbine`, `aep_summary` | High — turbine-class mismatch |
| R3 | **RESOLVED (#237 re-baseline + #268 guard).** Financed **473.8 GWh / CF 0.339** (15×IEA-10MW) and auxiliary **402.6 GWh / CF 0.307** (EN-171/6.5 characterization) are now distinct turbine bases by design; the AEP↔CF reconciliation guard fails loud if the financed CF diverges from its bankable net AEP. (Was the discredited 563/0.428 vs 485/0.375 split.) | `analytics/aep_reconciliation.py`, `scenarios/...lendercase...yaml` | Resolved |
| R4 | P75/P90 are **flat config haircuts (0.90/0.80)**, not uncertainty-derived exceedances | `era5_config.yaml p_levels`, `energy_calculator.py:335-337` | Medium — not IEC-61400-15 uncertainty build-up |
| R5 | Resource is **ERA5 reanalysis** (~31 km), only "medium" confidence vs a 1-yr mast; **no MCP** in code | `era5_fetcher.py:456`, scenario `data_confidence`; no MCP module | Medium — wind measurement campaign / MCP recommended |
| R6 | Production scenario references an AEP summary under **`tests/mocks/`** | `scenarios/...lendercase...yaml resource.aep_summary_path` | Medium — promote to production input |
| R7 | Auxiliary Monte Carlo Weibull A can be **back-estimated by a "Heuristic"** if not supplied | `monte_carlo_aep.py:145-149` | Low — only on auxiliary path; supply A/k explicitly |
| R8 | Legacy "6.5 MW" symbol names on the auxiliary path **alias to the 10 MW placeholder** | `oem_parser.py:301-311`, `:314-334` | Low — naming hazard; financed path unaffected |
| R9 | Grid **curtailment is a flat 2% placeholder** (in `resource.losses`, embedded in CF), **not a physics-based interconnection study** — a constrained CEB grid (Mannar/Kalpitiya) plausibly curtails more, so 2% may understate a real bankability risk | `resource.losses.curtailment_pct`, `losses_model.py` | Medium — UNVALIDATED pending a CEB interconnection study. Now a first-class **financed** stress lever (`project.curtailment_pct`, default 0) in the tornado + Monte-Carlo, swept to 15% total; a 10% incremental curtailment turns project NPV negative (+$2.0M → −$17.1M) |

---

## 7. One-paragraph statement for the credit memo

> The DutchBay energy yield that enters the v14 financial model is produced by the `wind_resource` package: ERA5/ECMWF reanalysis (10 m/100 m winds, Copernicus CDS) is downloaded with a JSON provenance sidecar, extrapolated to 150 m hub height via a per-hour power-law shear, fitted to a 2-parameter Weibull (MLE, with R²/KS goodness-of-fit recorded), converted to energy through a configured turbine power curve and a five-component multiplicative loss stack (~12.4%), and reported at P50/P75/P90 (with **P75 the lender base case**). The result is exported as a frozen JSON and merged into the lender scenario by a pure, drift-checked adapter that stamps full provenance and feeds `project.capacity_factor` into the cashflow/DSCR engine. **Three items require resolution before reliance: (i) the financed power curve is the 6.5 MW Envision while the scenario assumes a 10 MW machine whose only available curve is an explicit placeholder extrapolated from 6.5 MW; (ii) the financed P50 (now the canonical 473.8 GWh / CF 0.339 on 15 × IEA-10MW, ERA5-fitted Weibull) is reconciled fail-loud against its bankable net AEP by the #268 guard — the earlier 563/0.428-vs-485/0.375 split is resolved (the auxiliary 402.6 GWh / CF 0.307 is now an explicitly distinct EN-171/6.5 characterization case); and (iii) on the legacy auxiliary energy-calculator path the P-levels remain fixed config haircuts rather than a full IEC-61400-15 uncertainty build-up.** The separate `analytics` Monte Carlo / AEP-loader stack is a non-revenue uncertainty overlay that currently runs on the placeholder curve and a `tests/mocks/` summary, and must not be cited as the bankable yield.

---

*Generated for issue #27 (docs / P2 / DFI / audit). All assertions are traceable to the cited `file:line`. Replace the placeholder 10 MW curve and reconcile the cross-path yield (R1–R3) before this document is relied upon in a binding lender data room.*
