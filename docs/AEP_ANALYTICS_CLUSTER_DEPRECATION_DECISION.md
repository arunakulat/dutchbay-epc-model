# Architecture Decision Record: AEP Analytics Cluster Deprecation & Boundary Freeze

- **Status**: Accepted (Phase 0 boundary freeze active); amended 2026-11-16 under #1615 (section 5); step B delivered 2026-11-21 (section 6)
- **Date**: 2026-11-12
- **Issue**: [#1551](https://github.com/arunakulat/dutchbay-epc-model/issues/1551)
- **Authoritative references**: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) (section "Off-path analytics"), [`docs/WIND_AEP_CHAIN_OF_CUSTODY.md`](WIND_AEP_CHAIN_OF_CUSTODY.md)

---

## 1. Context & Background

During whole-codebase architecture audits, an off-path body of wind-AEP analytics was identified sitting parallel to the canonical production pipeline. These modules were implemented and unit-tested, but reachable from no live entrypoint:

- **Canonical Live Path**: `wind_resource/` (`WindPipeline` → `energy_calculator` → `bankable_aep` → `losses_model` → frozen export → `wind_resource/cashflow_adapter.py` → finance pipeline). Financed cashflows consume pre-computed AEP numbers from scenario configurations via the strict frozen-export contract.
- **Orphaned Parallel Cluster**:
  - `analytics/wind/aep_summary_builder.py` (builds AEP summary block)
  - `analytics/wind/pipeline_aep_v14.py` (parallel AEP pipeline)
  - `analytics/wind/mc_aep_weibull.py` (Monte Carlo AEP from ECMWF-derived Weibull)
  - `analytics/wind/aep_tornado.py` (resource-side tornado sensitivity analysis)
  - `analytics/wind/wind_interface_schema.py` (GIS→EPC schema; registered in `schema_guard.py` but never invoked on live runs)
  - `analytics/wind/era5_interface_schema.py` (ERA5 retrieval schema; registered in `schema_guard.py` but never invoked on live runs)
  - `analytics/simulation/monte_carlo_aep.py` (standalone MC-AEP driver)

Two critical integrity controls historically associated with this cluster:
1. **AEP-provenance guard**: Previously wired into the live path in 2026-06-23 (`analytics/aep_provenance.py` → scenario load, API boundary, and service seam).
2. **Wind-interface schema**: Remains off-path as no production caller invokes `'wind'` or `'era5'` validation modules.

---

## 2. Decision

1. **Single Canonical Wind Engine**:
   - `wind_resource/` is formally affirmed as the **sole canonical wind AEP producer** for the DutchBay EPC model.
   - The finance pipeline's consumption of frozen wind/solar exports via `wind_resource/cashflow_adapter.py` remains immutable. No live ERA5, PyWake, or GIS calls may be introduced into the finance execution loop.

2. **Deprecation of Parallel Cluster**:
   - The parallel AEP cluster (`analytics/wind/aep_summary_builder.py`, `pipeline_aep_v14.py`, `mc_aep_weibull.py`, `aep_tornado.py`, `wind_interface_schema.py`, `era5_interface_schema.py`, and `simulation/monte_carlo_aep.py`) is **formally deprecated**.

3. **Phase 0 Boundary Freeze (Immediate CI Guard)**:
   - A dedicated LibCST architectural boundary guard (`tests/lint/test_aep_analytics_cluster_boundary.py`) enforces that no live entrypoint (`run_full_pipeline_v14.py`, `run_scenario_analytics_v14.py`, `scripts/run_wind_analysis_v14.py`, `analytics/evaluation_v14.py`, `finance/`, `api/`) may newly import from the deprecated cluster.
   - Pre-existing legacy callers were frozen to a minimal allowlist (`wind_resource/arco_assessment.py`, `wind_resource/crossval.py`, and `app/reports/report_model.py`) to prevent expansion while Phase 1 utility extraction proceeds. Since #1615 (section 5) the allowlist is empty.

---

## 3. Caller Inventory (Whole-Codebase Audit)

| Deprecated Module | Production Callers | Test / Non-Production Callers | Status |
|---|---|---|---|
| `analytics/wind/aep_summary_builder.py` | None since #1615: the body moved to `wind_resource/aep_summary.py`, which `wind_resource/arco_assessment.py`, `wind_resource/crossval.py` and `app/reports/report_model.py` now import | `tests/analytics/test_aep_summary_builder.py` (still imports the old path, which resolves through the re-export to `wind_resource.aep_summary`) | Re-export only (section 5) |
| `analytics/wind/pipeline_aep_v14.py` | None | `tests/analytics/test_pipeline_aep_v14.py`, `tests/analytics/test_pipeline_aep_integration.py` | Deprecated (0 live callers) |
| `analytics/wind/mc_aep_weibull.py` | `analytics/capital_risk_layer_v14.py` | `tests/analytics/test_mc_aep_weibull.py` | Deprecated; reached from the live path only through the report seam `app/reports/aep_resource_sensitivity.py` (step B, section 6) |
| `analytics/wind/aep_tornado.py` | None. Its Weibull integral `gross_aep_farm_gwh` moved to `wind_resource/aep_integral.py` under #1615 and is re-exported here | `tests/analytics/test_aep_tornado.py` | Deprecated; reached from the live path only through the report seam `app/reports/aep_resource_sensitivity.py` (step B, section 6) |
| `analytics/wind/wind_interface_schema.py` | `analytics/schema_guard.py` (registry only) | `tests/analytics/test_wind_interface_schema.py` | Deprecated (0 live callers) |
| `analytics/wind/era5_interface_schema.py` | `analytics/schema_guard.py` (registry only) | `tests/analytics/test_era5_interface_schema.py` | Deprecated (0 live callers) |
| `analytics/simulation/monte_carlo_aep.py` | `analytics/wind/pipeline_aep_v14.py`, `analytics/wind/wind_integration.py` | `tests/analytics/test_monte_carlo_aep_losses.py` | Deprecated (0 live callers) |

---

## 4. Multi-Phase Roadmap

- **Phase 0 — Discovery & Boundary Freeze (Delivered in #1551)**:
  - CI LibCST boundary test enforcing zero new imports (`tests/lint/test_aep_analytics_cluster_boundary.py`).
  - Recorded caller inventory across entire repository.
  - Published ADR and linked from `docs/ARCHITECTURE.md`.
- **Phase 1 — Cluster Cleanup & Utility Extraction**:
  - Extract pure wind rose and AEP summary utility functions needed by `arco_assessment.py` and `report_model.py` into a shared package under `wind_resource/`.
  - Remove deprecated modules and their dedicated test suites from the main CI gate.
  - Clean `schema_guard.py` registration of `'wind'` and `'era5'` schemas.
- **Phase 2 — Multi-Tech Generation Scaffold Resolution**:
  - Evaluate multi-tech generation contracts (`GenerationProfile`, `MultiTechGenerationResult`, `TechnologyBreakdown`).
  - Either complete the solar producer integration + portfolio aggregator or archive the scaffolding outside core contracts.

---

## 5. Amendment, 2026-11-16 (#1615)

The owner ruled on #1615 on 2026-11-16 ("Wire into reports") and added that the live helpers move into the main wind engine. This amends sections 2 to 4 as follows.

1. **The live helpers move into `wind_resource/` (delivered in the #1615 step A pull request).** Three functions had live callers:
   - `gross_aep_farm_gwh`, the analytic Weibull-by-power-curve integral, used by the Blue Whale wind scripts, `analytics/wind/met_mast_transfer.py` and the summary builder. It now lives in `wind_resource/aep_integral.py`.
   - `build_aep_summary_from_config`, used by `wind_resource/crossval.py` and `wind_resource/arco_assessment.py`.
   - `_resolve_wind_rose`, used by the report wind rose in `app/reports/report_model.py`.

   The last two moved with the rest of the summary builder into `wind_resource/aep_summary.py`. The code moved unchanged. `analytics/wind/aep_tornado.py` and `analytics/wind/aep_summary_builder.py` re-export the moved names, so there is one implementation and the old import paths keep working. The summary's `generated_by` field keeps the old dotted name, so committed summaries stay byte-identical. `PHASE_0_LEGACY_ALLOWLIST` in the boundary guard is now empty, and `wind_resource/` and `app/` take no exceptions. This delivers the "utility extraction" part of Phase 1 for these three functions.

2. **The tornado and the AEP P50/P90 go into the report (step B, a separate R3 pull request).** The resource-side tornado and the AEP P50/P90 get report sections, labelled as model outputs with no bankable claim. There is no measured site wind data and no P90 evidence (#1110 L04). Step B widens the boundary guard only for the report seam that builds those sections. `finance/`, `api/` and the top-level runners stay closed. If a committed figure moves, step B carries a before/after table and needs owner sign-off.

3. **The cluster Monte Carlo goes into the report too, as a labelled resource sensitivity (step B).** The owner's ruling wires the AEP cluster into reports, and that includes the Monte Carlo AEP in `mc_aep_weibull.py`. Step B shows it in the report as a labelled resource sensitivity, next to the tornado. The report basis does not change: the energy and every financial figure stay on the committed IEC P50/P90 from the frozen export, and the cluster Monte Carlo is shown beside that basis, never in place of it. Step B's boundary-guard widening for the report seam therefore covers `mc_aep_weibull.py` as well as the tornado.

4. **What does not change.** The rest of the cluster (`pipeline_aep_v14.py`, the two interface schemas and `simulation/monte_carlo_aep.py`) stays deprecated and off the live path until Phase 1 removes or re-homes it. `wind_resource/` remains the sole canonical producer, and finance still consumes only frozen exports.

5. **Logger name.** The summary builder's two `logger.info` lines now log under `wind_resource.aep_summary` instead of `analytics.wind.aep_summary_builder`, because the module moved. No code, test or logging configuration in the repository filters on the old name. A caller that does should switch to the new name; the re-export does not carry the logger.

---

## 6. Step B delivered, 2026-11-21 (#1615)

Step B wires the resource-side tornado and the Monte Carlo AEP into the command-line lender report (#1752) as one labelled section, "Wind Resource Sensitivity — Net AEP".

1. **One seam.** `app/reports/aep_resource_sensitivity.py` is the only live file that imports the cluster, and it imports `analytics.wind.aep_tornado` and `analytics.wind.mc_aep_weibull` only. The boundary guard records it in `REPORT_SEAM_ALLOWLIST`; a test pins that list to this one file and these two modules, and negative controls show the rest of the cluster, and every other `app/` file, stay closed. `finance/`, `api/`, `wind_resource/` and the runners are unchanged.
2. **Inputs from the scenario.** The Weibull (`wind_resource.weibull_a/k`), turbine count and hub height, power curve and its air-density basis, loss stack and `monte_carlo.weibull_uncertainty_pct` all come from the scenario. A scenario that lacks any of them gets the section listed under "Sections not run" with the missing key named, never a default figure.
3. **Reconciled, not substituted.** The section shows the cluster's base net AEP, the tornado and the Monte Carlo P50/P75/P90/P99 beside the committed net P50/P90 the finance run uses (`yield_reconciliation`), and says why they differ: the committed P50 carries the scenario's pre-construction haircut, which the cluster does not apply, and the committed P90 comes from the IEC 61400-15-2 uncertainty budget, while the cluster's spread comes from a one-sigma on the Weibull A and k alone. The energy and every financial figure stay on the committed basis; no KPI moves.
4. **Labelled.** The section says it is a model output and a resource sensitivity, not the report basis, and that with no measured site wind data and no P90 evidence it supports no bankable resource claim (#1110 L04). It carries the F-5 caption.
5. **API route.** The synchronous API report does not build the section (latency ledger #645); the API report is unchanged by step B.

