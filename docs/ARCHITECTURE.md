# DutchBay EPC Model — Architecture (Authoritative Reference)

> This is the **single authoritative description** of how the model runs.
> Point-in-time sprint retrospectives, handovers, audits, and implementation-status
> reports have been moved to [`docs/archive/`](archive/) — treat them as historical,
> not current. For the planned web-service productization see
> [`docs/WEB_SERVICE_ROADMAP.md`](WEB_SERVICE_ROADMAP.md).

---

## Canonical execution map

```
run_full_pipeline_v14.py            (Hydra CLI; conf/run_full_pipeline_v14.yaml)
   │   wind integration OFF by default (opt in via wind_assessment_json / wind_auto_orchestrate)
   ▼
analytics.pipeline_v14_enhanced.run_v14_pipeline   ← THE canonical pipeline
   (an alias of run_v14_pipeline_enhanced)
```

**`analytics/pipeline_v14_enhanced.py` is the canonical orchestrator.** The
legacy `analytics/pipeline_v14.py` is a **wind-only** pipeline with a *different*
output contract and is **not** canonical — do not wire new work to it. (The
analytics wrapper was routed off it in #286.)

For sensitivity / Monte-Carlo / programmatic / API callers, the canonical
gateway is **`analytics.evaluate_scenario.evaluate_with_overrides(base_config_path,
overrides, *, validation_mode, validation_modules)`** (and
`analytics.evaluation_v14.evaluate_with_overrides(config_path, overrides, …)`),
which run the same engine on an in-memory config + dotted-key overrides without
file-level re-validation. On a frozen `aep_summary` a full run is ~0.05s.

---

## Pipeline sequence (`run_v14_pipeline_enhanced`)

```
0. Config normalization        analytics.scenario_loader.load_scenario_config()
1. Pre-flight validation       analytics.schema_guard.validate_config_for_v14()   (strict by default)
2. Cashflow engine (lazy)      finance.cashflow_v14.build_annual_rows()           (+ cashflow_v14_tax)
3. Debt planning               finance.debt_v14.plan_debt()                       (DSCR + bridge-period alignment)
4. WACC / discount resolution  finance.wacc_v14.compute_wacc_from_config()
5. KPI calculation             analytics.core.metrics.calculate_scenario_kpis()
6. Equity distribution (lazy)  finance.equity_distribution_v14_hydra.calculate_equity_distribution_from_pipeline()
7. Result assembly             ScenarioResult dataclass → dict
```

Steps 2 and 6 use **lazy imports** (deliberate — to break an import-load cycle;
see #294/#298). Strict schema-spec registration is deterministic via
`schema_guard._MODULE_IMPORTS` mapping each logical module to **all** its
registering modules (#301).

### Result contract (top-level keys)

`status`, `scenario_result` (full `ScenarioResult`), `kpis` (flat:
`project_irr`, `equity_irr`, `min_dscr`, `avg_dscr`, `llcr`, `plcr`,
`project_npv`, …), `annual_rows`, `debt_result`, `equity_distribution`,
`metrics` (`PipelineMetrics` timings), `run_manifest` (config hash, engine
version, commit — ICAEW-style reproducibility).

---

## Wind → finance integration (narrow, frozen-export contract)

The finance pipeline **never** calls Copernicus/ERA5 directly. The wind producer
is a separate Hydra CLI; its output is frozen to JSON and bridged through a
schema-validated adapter:

```
wind producer (scripts/run_wind_analysis_v14.py, wind_resource.WindPipeline)
   ↓ produces   wind_export_P75.json
wind_resource/cashflow_adapter.py   (WindCashflowExport — Pydantic v2 contract, drift-checked)
   ↓ patches    the scenario's resource.wind block (temp YAML; original never mutated)
finance consumer (run_full_pipeline_v14.py)
```

The `resource.wind` handoff block: `ws150_mean_ms`, `ws150_std_ms`,
`capacity_factor`, `aep_gwh`, `source_id`, `source_type`. This decouples evolving
wind analytics from the cashflow engine and gives lender-grade reproducibility.

---

## Fully-integrated core modules

| Module | Role |
|---|---|
| `analytics/pipeline_v14_enhanced.py` | canonical orchestrator (`run_v14_pipeline`) |
| `analytics/evaluate_scenario.py`, `analytics/evaluation_v14.py` | override gateways |
| `analytics/contracts_v14.py` | Pydantic v2 contracts (`ScenarioResult`, `WaccResult`, …) |
| `analytics/scenario_loader.py` | config load + light normalization (authored-AEP reconciliation) |
| `analytics/schema_guard.py` | pre-flight validation (strict) |
| `analytics/core/metrics.py` | `calculate_scenario_kpis()` |
| `analytics/fx/*` | FX overlay (`fx_builder`, `fx_integration`, `fx_contracts`, `fx_fetch`) |
| `finance/cashflow_v14.py` (+ `_tax`, `_params`, `_fx`, `_production`) | cashflow engine |
| `finance/debt_v14.py` | debt structuring, DSCR sculpt |
| `finance/wacc_v14.py` | WACC |
| `finance/equity_distribution_v14_hydra.py`, `finance/equity_v14.py` | equity waterfall / returns |
| `finance/irr.py` | IRR/NPV/MIRR (the canonical numerics) |
| `wind_resource/cashflow_adapter.py` | wind→finance bridge |

---

## Off-path analytics — built & tested, but not on a live run

A whole-codebase audit (2026-06-22) found a body of wind-AEP analytics that is
implemented and green-tested but **reachable from no live entrypoint**
(`run_full_pipeline_v14.py`, `run_scenario_analytics_v14.py`,
`scripts/run_wind_analysis_v14.py`, `api/`, `app/`). It executes only in its own
tests. Two facts put it off-path:

1. The financed cashflow ingests a **pre-computed AEP from the scenario YAML**
   through `wind_resource/cashflow_adapter.py` (which imports **zero**
   analytics-AEP modules) — the frozen-export contract above. The analytics-AEP
   cluster is therefore not on the finance path.
2. No production caller passes the `'wind'` / `'era5'` validation modules to
   `validate_config_for_v14` (every live call uses `['cashflow']` or
   `['cashflow','debt']`), so the schemas registered at
   `analytics/schema_guard.py:55-56` never run outside their tests.

### The orphaned AEP cluster

| Module | Status | Role |
|---|---|---|
| `analytics/wind/losses_model.py` | **LIVE** | IEC loss taxonomy; reached via `wind_resource/bankable_aep.py` on the live WindPipeline |
| `analytics/loader/aep_loader.py` | **LIVE** (provenance) | AEP-provenance guard (`APPROVED_SOURCES`); the lender control of [`AEP_PROVENANCE.md`](AEP_PROVENANCE.md) — **now wired into the financed run** via `analytics/aep_provenance.py` (scenario load + API boundary). The summary-loading / MC helpers in the module remain off-path. |
| `analytics/wind/aep_summary_builder.py` | orphaned | builds the AEP summary block |
| `analytics/wind/pipeline_aep_v14.py` | orphaned | a parallel AEP pipeline |
| `analytics/wind/mc_aep_weibull.py` | orphaned | Monte-Carlo AEP from ECMWF-derived Weibull |
| `analytics/wind/aep_tornado.py` | orphaned | wind/shear/losses/power-curve AEP sensitivities |
| `analytics/wind/wind_interface_schema.py`, `era5_interface_schema.py` | orphaned | GIS→EPC schemas ([`WIND_INTERFACE_SCHEMA.md`](WIND_INTERFACE_SCHEMA.md)); registered but never invoked |
| `analytics/simulation/monte_carlo_aep.py` | orphaned | MC-AEP driver |
| `analytics/capital_risk_layer_v14.py` | orphaned | sole importer of `mc_aep_weibull` |

These import **each other** into a self-consistent cluster that sits parallel to
the **live** wind producer (`wind_resource/`: `WindPipeline` → `energy_calculator`
→ `bankable_aep` → `losses_model`), which is what actually makes the frozen export.

**Material gap, partly closed:** the **AEP-provenance guard** and the
**wind-interface schema** were lender-grade integrity controls **enforced only in
tests** (see [`WIND_AEP_CHAIN_OF_CUSTODY.md`](WIND_AEP_CHAIN_OF_CUSTODY.md)).
The **provenance half is now wired** (2026-06-23, item 2): `analytics/aep_provenance.py`
folds `aep_loader.validate_config_aep_provenance` into the financed path at **all three
live entrypoints** — scenario load (`analytics/scenario_loader.py`), the API boundary
(`api/pipeline_api.py`), and the framework-agnostic service seam
(`app/services/pipeline_service.py`, the web app's `POST /cases` + job runner, which
passes an in-memory dict that bypasses the load-time guard) — config-driven via
`defaults.aep_provenance` and a no-op when a scenario declares no
`resource.power_curve.source_id`, so a real run now refuses an unapproved or
placeholder turbine-curve source. (The sibling `aep_reconciliation` guard has the same
inline-dict bypass at the service seam; wiring it there is a tracked follow-up — it would
trip the synthetic non-reconciling scenarios several app/integration tests exercise.) The remaining off-path control is the
**wind-interface schema** (`'wind'`/`'era5'` validation modules, still passed by no
production caller); the rest of the AEP-analytics cluster (summary builder / parallel
pipeline / MC-AEP / tornado) is a decision to wire or retire so `wind_resource/` is the
single AEP engine.

### Orphaned multi-tech generation scaffold

`analytics/contracts_v14.py:412-471` (`GenerationProfile`,
`MultiTechGenerationResult`, `TechnologyBreakdown`) + `analytics/casper/` build and
serialize a **multi-technology (wind/solar/BESS)** generation payload, but nothing
**produces** a `MultiTechGenerationResult` from real generation — there is no solar
engine and no aggregator. This is Sprint 9/10 scaffolding (re-instated Sprint 18D).
The multi-tech build reuses these contracts and adds the producers (wind adapter →
`GenerationProfile`, solar engine, portfolio aggregation). Note: a *second*,
field-distinct `TechnologyBreakdown` lives in `finance.contracts` — same name,
different surface.

---

## Governance & quality posture

- **GWTF**: branch → PR → green CI → self-merge; never commit to `main`.
- **CESSPIT / CCCDIR / CASPER**: config-first (no hardcoded constants), always-strict
  validation (no `strict=False` bypass in production), clean typed interfaces,
  graceful optional-dep failure.
- **Test coverage**: the four engine packages (`analytics`, `finance`,
  `wind_resource`, `api`) are each ≥95% (overall ~98%, 2,200+ tests).
- **Auditability**: every run is stamped with a `run_manifest` (config hash,
  engine version, commit).

---

## Where things live

- **Current docs**: this file, `README.md`, `QUICK_START.md`, `CHANGELOG.md`,
  `RELEASING.md`, `SECURITY.md`, `schema.md`.
- **Historical** (point-in-time, superseded): [`docs/archive/`](archive/).
- **Productization plan**: [`docs/WEB_SERVICE_ROADMAP.md`](WEB_SERVICE_ROADMAP.md).
