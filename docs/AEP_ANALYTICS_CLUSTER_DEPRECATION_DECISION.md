# Architecture Decision Record: AEP Analytics Cluster Deprecation & Boundary Freeze

- **Status**: Accepted (Phase 0 boundary freeze active)
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
   - Pre-existing legacy callers are frozen to a minimal allowlist (`wind_resource/arco_assessment.py`, `wind_resource/crossval.py`, and `app/reports/report_model.py`) to prevent expansion while Phase 1 utility extraction proceeds.

---

## 3. Caller Inventory (Whole-Codebase Audit)

| Deprecated Module | Production Callers | Test / Non-Production Callers | Status |
|---|---|---|---|
| `analytics/wind/aep_summary_builder.py` | `wind_resource/arco_assessment.py` (`build_aep_summary_from_config`), `wind_resource/crossval.py` (`build_aep_summary_from_config`), `app/reports/report_model.py` (`_resolve_wind_rose`) | `tests/analytics/test_aep_summary_builder.py` | Frozen in Phase 0 allowlist; targeted for utility extraction in Phase 1 |
| `analytics/wind/pipeline_aep_v14.py` | None | `tests/analytics/test_pipeline_aep_v14.py`, `tests/analytics/test_pipeline_aep_integration.py` | Deprecated (0 live callers) |
| `analytics/wind/mc_aep_weibull.py` | `analytics/capital_risk_layer_v14.py` | `tests/analytics/test_mc_aep_weibull.py` | Deprecated (0 live entrypoints) |
| `analytics/wind/aep_tornado.py` | None | `tests/analytics/test_aep_tornado.py` | Deprecated (0 live callers) |
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
