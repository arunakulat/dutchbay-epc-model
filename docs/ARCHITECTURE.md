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
