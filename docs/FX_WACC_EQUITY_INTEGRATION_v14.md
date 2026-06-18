# FX / WACC / Equity Integration (v14)

**Status:** Current / as-built (verified against source)
**Scope:** How structured FX, WACC, and equity-performance results are produced and attached to `ScenarioResult` in the v14 analytics stack.
**Supersedes for FX/WACC/Equity:** `docs/ANALYTICS_INTEGRATION.md` (dated 2025-12-21) and the pipeline-wiring pseudocode in `docs/FX_INTEGRATION_v14R6.md` (dated 2025-12-18). See [Section 6 — Stale docs](#6-relationship-to-existing-docs-corrections).
**Issue:** #34.

> This document describes only the integration that exists in code today. Where a module is defined but **not actually wired into the running financial pipeline**, that is called out explicitly. Aspirational docstrings inside the source (e.g. "called from `pipeline_v14.run_full_pipeline_v14()`") are corrected here.

---

## 1. The canonical financial entry point

The single financial-scenario entry point is `run_v14_pipeline_enhanced` in `analytics/pipeline_v14_enhanced.py:439`, aliased as `run_v14_pipeline` at `analytics/pipeline_v14_enhanced.py:629`. Downstream evaluation code imports it from there: `analytics/evaluate_scenario.py:9` and `analytics/evaluation_v14.py:12` both `from analytics.pipeline_v14_enhanced import run_v14_pipeline`. The top-level Hydra runner `run_full_pipeline_v14.py` also imports and calls this alias (`run_full_pipeline_v14.py:103,515`).

> **Do not confuse with `analytics/pipeline_v14.py`.** Despite the name, `analytics/pipeline_v14.py:1` is the *wind-resource* pipeline (`from wind_resource import WindPipeline`, `analytics/pipeline_v14.py:43`). Its `run_v14_pipeline` (`analytics/pipeline_v14.py:50`) returns AEP/Weibull/revenue outputs, not a `ScenarioResult`, and it does **not** touch FX/WACC/equity. The FX docstrings that reference `pipeline_v14.run_full_pipeline_v14()` (e.g. `analytics/fx/fx_integration.py:55`, `analytics/fx/fx_builder.py:13`) point at a function that does not exist — there is no `run_full_pipeline_v14` function in the `analytics.pipeline_v14` module (its only Hydra entry is `cli`, `analytics/pipeline_v14.py:361`).

### 1.1 Data-flow overview (config → pipeline → ScenarioResult)

```
config (str | Path | Mapping)
  │
  ▼
_validate_config_type_and_structure()              pipeline_v14_enhanced.py:94
  │   └─ load_scenario_config()  (rejects scalar fx) scenario_loader.py:168
  ▼
validate_config_for_v14()   [strict mode only]      pipeline_v14_enhanced.py:486
  ▼
build_annual_rows(cfg)                              finance/cashflow_v14.py  → annual_rows
  ▼
plan_debt(annual_rows, cfg)                         finance/debt_v14.py      → debt_result
  ▼
_enrich_annual_rows_with_debt()                     pipeline_v14_enhanced.py:197
  ▼
calculate_scenario_kpis()                           analytics/core/metrics.py → kpis (project_npv/irr…)
  ▼
calculate_equity_distribution_from_pipeline()       finance/equity_distribution_v14_hydra.py:439
  └─ _update_kpis_with_equity_distribution()        pipeline_v14_enhanced.py:399 → EquityPerformance
  ▼
compute_wacc_from_config(cfg)  → dict               finance/wacc_v14.py:366
  └─ _build_wacc_contract(dict) → WaccResult        pipeline_v14_enhanced.py:227
  ▼
ScenarioResult(...)                                 pipeline_v14_enhanced.py:563
  │   wacc, wacc_label, equity_performance, debt_profile, debt_covenants populated
  │   fx_block / fx_curve / fx_risk_profile = None  (NOT populated here — see §2.4)
  │   wacc_is_real = None                           (default; not set here — see §3.4)
  ▼
asdict(scenario_result)  →  result["scenario_result"]   pipeline_v14_enhanced.py:598
```

Fields **populated** by the enhanced pipeline on `ScenarioResult`: `wacc` (`pipeline_v14_enhanced.py:571`), `wacc_label` (`:573`), `discount_rate_used` (hard-coded `0.10`, `:572`), `equity_performance` (`:581`), `debt_profile`, `debt_covenants`, `kpis`, `annual_rows`, `debt_result`, `config`, `metadata`.

Fields **left at their dataclass defaults** (i.e. `None`) by the enhanced pipeline: `fx_block`, `fx_curve`, `fx_risk_profile`, `wacc_is_real`, `cashflow`.

---

## 2. Structured FX block

### 2.1 The scalar → structured migration and the schema guard

FX configuration must be a **mapping**, never a scalar. The loader enforces this in two places in `analytics/scenario_loader.py`:

- **Strict resolver `_resolve_fx`** (`analytics/scenario_loader.py:107`): raises `ValueError` when `fx` is missing (`:116`), when `fx` is an `int`/`float` scalar (`:123` — message `"Scalar 'fx' not supported; use mapping with 'start_lkr_per_usd' and 'annual_depr'"`), when it is not a mapping (`:129`), and when `start_lkr_per_usd` is absent (`:135`). On success it returns the normalized mapping `{"start_lkr_per_usd": float, "annual_depr": float}` (`:150`), with `annual_depr` defaulting to `0.0` (`:146`).
- **Public loader `load_scenario_config`** (`analytics/scenario_loader.py:168`): independently re-checks the raw config and **raises `ValueError` on a scalar `fx`** at `analytics/scenario_loader.py:183-188`, before any caller asks for `_resolve_fx`. This is the gate the enhanced pipeline hits, because `_validate_config_type_and_structure` calls `load_scenario_config` for `str`/`Path` configs (`analytics/pipeline_v14_enhanced.py:98`).

Net effect: any scenario whose `fx` is `300.0` (the legacy scalar form) is rejected at load time; only `fx: {start_lkr_per_usd: …, annual_depr: …}` is accepted.

### 2.2 FX contracts — `analytics/fx/fx_contracts.py`

All FX contracts are frozen dataclasses with `__post_init__` validation. The three that attach to `ScenarioResult`:

| Contract | Defined at | Key fields | Validation highlights |
|---|---|---|---|
| `FXStructuredBlock` | `analytics/fx/fx_contracts.py:304` | `strategy` (`Literal["natural_hedge","fixed_ccy","hedged","blended"]`, default `"blended"`), `base_currency`/`reporting_currency` (default `"USD"`), `volumetry: List[FXVolumetry]`, `debt_tranches: Dict[str,str]`, `revenue_currencies` (default `["LKR"]`), `fx_match_ratio`, `hedging_coverage_pct`, `notes` | `fx_match_ratio`/`hedging_coverage_pct` ∈ [0,100] (`:339`,`:344`); currencies ∈ {USD,LKR,CNY,EUR,GBP} (`:350`) |
| `FXCurveOutput` | `analytics/fx/fx_contracts.py:86` | `years: List[int]`, `lkr_usd: List[float]`, optional `lkr_cny`/`lkr_eur`/`lkr_gbp`, `source` (default `"base_case"`), `notes` | `len(years)==len(lkr_usd)` (`:113`); optional curves length-checked (`:120`); all `lkr_usd>0` (`:133`) |
| `FXRiskProfile` | `analytics/fx/fx_contracts.py:191` | `var_95_usd_million`, `cvar_95_usd_million`, `debt_lkr_pct`/`debt_usd_pct`/`debt_cny_pct`, `debt_concentration_hhi`, `revenues_lkr_pct`, `correlation_shock_scenario`, `worst_case_year`, `recovery_years_to_1x_llcr` | debt %s sum to ~100 (95–105) (`:231`); VaR ≤ CVaR (`:238`); HHI ∈ [0,1] (`:244`) |

Supporting contract `FXVolumetry` (per-period exposure) is at `analytics/fx/fx_contracts.py:41`. Each of the three primary contracts exposes `to_dict()` for JSON/dashboard export (`:382`, `:173`, `:253`). The module also carries legacy compat shapes (`FXRegimeConfig` `:275`, `FXRegimeScenario` `:414`, `FXMonteCarloConfig` `:436`) that are **not** part of the `ScenarioResult` surface.

### 2.3 FX builder and integration helpers

`analytics/fx/fx_builder.py` provides three pure factory functions (all keyword-only):

- `compute_fx_structured_block(config, debt_result, annual_rows)` (`analytics/fx/fx_builder.py:42`): reads the FX section case-insensitively via `config.get("FX") or config.get("fx")` (`:63`); defaults `strategy` to `"blended"` and coerces unknown strategies back to `"blended"` (`:70`); maps `debt_result["tranches"][name]["currency"]` into `debt_tranches` (`:83`) and **logs a warning if no tranches are found** (`:92`); builds one `FXVolumetry` per annual row from `total_debt_lkr/usd/cny`, `revenue_lkr/usd`, `interest_lkr`, `principal_lkr` (`:107`), failing fast on a malformed row (`:121`).
- `compute_fx_curve(config, annual_rows)` (`analytics/fx/fx_builder.py:163`): derives `years` from each row's `"year"` (`:193`); reads `fx.curve.lkr_usd`, else falls back to a **flat curve** at `fx.curve.spot_lkr_usd` (default `300.0`) (`:199`); optional CNY/EUR/GBP curves; raises `ValueError` on any length mismatch (`:227`, `:239`, `:250`, `:261`).
- `compute_fx_risk_profile(fx_block, fx_curve)` (`analytics/fx/fx_builder.py:302`): returns a minimal profile when volumetry/debt is empty (`:319`, `:343`); otherwise computes debt-currency percentages from the **final** volumetry period (`:334`), a **simplified** 5%-LKR-depreciation `var_95` with `cvar_95 = 1.5 × var_95` (`:368-371`), and an HHI of debt concentration (`:378`). Note the explicit in-code caveat that this is "a simplified calculation; full Monte Carlo would be more rigorous" (`:367`).

`analytics/fx/fx_integration.py:45` defines `integrate_fx_into_scenario_result(scenario_result, config, debt_result, annual_rows)`, which calls the three builders (`:111-124`), then rebuilds the frozen `ScenarioResult` via `dataclasses.asdict(...)` + re-instantiation with `fx_block`/`fx_curve`/`fx_risk_profile` set (`analytics/fx/fx_integration.py:133-140`). It uses `TYPE_CHECKING` + a runtime in-function import of `ScenarioResult` to break the circular import (`:32`, `:86`). `analytics/fx_integration.py` is a backward-compat shim re-exporting from the new location, and `analytics/fx/__init__.py` lazily re-exports the function via `__getattr__`.

### 2.4 How `ScenarioResult` carries FX — and the current wiring gap

`ScenarioResult` declares the three optional FX fields at `analytics/contracts_v14.py:157-159`:

```python
fx_block: FXStructuredBlock | None = None
fx_curve: FXCurveOutput | None = None
fx_risk_profile: FXRiskProfile | None = None
```

`contracts_v14` imports these types directly from `analytics/fx/fx_contracts.py` (`analytics/contracts_v14.py:16`) and re-exports them (`:481-483`).

**Current state (as-built):** `run_v14_pipeline_enhanced` does **not** call `integrate_fx_into_scenario_result`. No call site of that function exists in the live financial pipeline; the only references are its own definition/docstrings, the `analytics/fx/__init__.py` lazy re-export, the `analytics/fx_integration.py` compat shim, and import-smoke tests (`tests/lint/test_import_smoke.py`). Consequently, when the enhanced pipeline assembles `ScenarioResult` (`analytics/pipeline_v14_enhanced.py:563`), the three FX fields are left at their `None` defaults.

The enhanced pipeline carries **FX scaffolding that is never exercised**: `PipelineMetrics` declares `fx_integration_time_sec` (`analytics/pipeline_v14_enhanced.py:70`), `fx_integration_attempted = False` (`:76`), and `fx_integration_succeeded = False` (`:77`); the entry point accepts `allow_fx_degradation` but immediately discards it via `del allow_fx_degradation` (`analytics/pipeline_v14_enhanced.py:447`). None of these flags are ever flipped to `True`, and `fx_integration_time_sec` stays `0`.

**Conclusion:** the FX *contracts, builder, and integration helper* are fully built and validated, and the `ScenarioResult` slots exist, but the **live financial pipeline does not populate them**. FX population today happens only if a caller invokes `integrate_fx_into_scenario_result` directly on an already-built `ScenarioResult`. No downstream consumer reads the FX fields off `ScenarioResult` today — in particular, the CASPER payload (`analytics/casper/casper_payload.py`) serializes WACC, equity, debt, and DSCR but does **not** read `fx_block`/`fx_curve`/`fx_risk_profile` at all — so the `None` defaults are simply never observed.

---

## 3. WACC v14

### 3.1 `compute_wacc_from_config` → dict

`finance/wacc_v14.py:366` `compute_wacc_from_config(config)` returns a **plain `dict`** (via `dataclasses.asdict` of the *finance-local* `WaccComponents` at `finance/wacc_v14.py:71`), not a contract object. It supports two modes:

- **Simple/fixed** (`finance/wacc_v14.py:394`): when `wacc.discount_rate` is present and `mode ∈ {"", "simple", "fixed"}`. `_pct_to_decimal` treats values > 1.0 as percentages (`finance/wacc_v14.py:122`). Emits `mode="fixed"`, `wacc_nominal = discount_rate`, `wacc_prudential = discount_rate + prudential_spread`, `wacc_real=None`.
- **CAPM** (`finance/wacc_v14.py:429`): `Ke = Rf + β_equity·MRP` (`calculate_cost_of_equity_capm`, `:213`), with beta re-levering `β_equity = β_asset·[1+(1−T)(D/E)]` (`relever_beta`, `:225`) and after-tax WACC `(E/V·Ke)+(D/V·Kd·(1−T))` (`calculate_after_tax_wacc`, `:242`). Real WACC via Fisher is computed only when `inflation_rate` is provided and > 0 (`build_wacc`, `finance/wacc_v14.py:333-335`). Accepts dual config naming (`risk_free`/`risk_free_rate`, `beta`/`asset_beta`, `gearing`/`target_debt_to_equity`, `cost_of_debt` or `base_rate+margin`); pulls `tax_rate` from `wacc.tax_rate` else `tax.corporate_tax_rate_pct`/`tax.corporate_tax_rate` (`finance/wacc_v14.py:513-519`).

If there is **no `wacc` block**, the function returns `{}` and logs a warning (`finance/wacc_v14.py:383-386`).

> Naming note: the task brief's "`compute_wacc_from_config -> WaccResult`" is shorthand. The function itself returns a `dict`; the conversion to the `WaccResult` contract happens in the pipeline adapter described next. There are two distinct `WaccComponents` classes — the finance-local one (`finance/wacc_v14.py:71`) and the contract one (`analytics/contracts_v14.py:66`); the adapter bridges them.

### 3.2 The single entry point and the CCCDIR adapter

Inside `run_v14_pipeline_enhanced` the WACC phase is:

```python
wacc_dict = compute_wacc_from_config(cfg)          # pipeline_v14_enhanced.py:547
wacc_contract = _build_wacc_contract(wacc_dict)    # pipeline_v14_enhanced.py:548
```

`_build_wacc_contract` (`analytics/pipeline_v14_enhanced.py:227`) is the **CCCDIR adapter from the finance dict to `contracts_v14.WaccResult`**:

- returns `None` for an empty/`None` dict (`:230`);
- constructs a contract `WaccComponents` (imported as `ContractWaccComponents`, `analytics/pipeline_v14_enhanced.py:43`) field-by-field with safe `float(...)`/`int(...)` coercion and defaults (`:234-254`); `wacc_prudential` falls back to `wacc_nominal` if absent (`:238`);
- on any `KeyError`/`TypeError`/`ValueError` it logs a warning and returns `None` rather than raising (`:255-257`);
- wraps the components in `WaccResult(base=…, prudential_rate=base.wacc_prudential, prudential_npv=None, meta={"mode": base.mode})` (`analytics/pipeline_v14_enhanced.py:259-264`).

### 3.3 What lands on `ScenarioResult`

- `ScenarioResult.wacc = wacc_contract` (`analytics/pipeline_v14_enhanced.py:571`) — a `WaccResult | None` (field declared at `analytics/contracts_v14.py:145`). `WaccResult` itself is at `analytics/contracts_v14.py:87` (`base: WaccComponents`, `prudential_rate`, `prudential_npv`, `meta`).
- `ScenarioResult.wacc_label = wacc_dict.get("mode") if wacc_dict else None` (`analytics/pipeline_v14_enhanced.py:573`) — i.e. the string `"capm"` or `"fixed"`, or `None` when no WACC block exists.
- `ScenarioResult.discount_rate_used = 0.10` — **hard-coded** at `analytics/pipeline_v14_enhanced.py:572` (and the same `0.10` is passed to `calculate_scenario_kpis`, `:520`). The computed WACC is recorded on the result but is **not** the discount rate used for the KPI NPV in this pipeline.

### 3.4 `wacc_is_real`

`ScenarioResult.wacc_is_real` (field at `analytics/contracts_v14.py:156`) is **not set** by `run_v14_pipeline_enhanced`; it stays at its `None` default. The only place `wacc_is_real` is materialized is the KPI layer, where `calculate_scenario_kpis` hard-codes `result["wacc_is_real"] = False` (`analytics/core/metrics.py:313`); the evaluator surface (`analytics/evaluate_scenario.py:208`) and the CASPER payload (`analytics/casper/casper_payload.py:124`, via `getattr(s, "wacc_is_real", None)`) read it defensively. So today WACC is treated as nominal: there is no path in the enhanced pipeline that sets `wacc_is_real=True`.

---

## 4. Equity performance

### 4.1 The contract

`EquityPerformance` is a frozen dataclass at `analytics/contracts_v14.py:377`:

```python
equity_irr: float | None = None
equity_npv: float | None = None
equity_multiple: float | None = None
metadata: dict[str, Any] = field(default_factory=dict)
```

`ScenarioResult.equity_performance: EquityPerformance | None = None` is declared at `analytics/contracts_v14.py:161`.

### 4.2 Where it is computed

Within `run_v14_pipeline_enhanced`:

```python
equity_distribution = calculate_equity_distribution_from_pipeline(   # pipeline_v14_enhanced.py:529
    config=cfg, annual_rows=annual_rows_enriched, debt_result=debt_result, kpis=kpis,
)
equity_performance = _update_kpis_with_equity_distribution(kpis, equity_distribution)  # :535
```

`calculate_equity_distribution_from_pipeline` lives at `finance/equity_distribution_v14_hydra.py:439`. It:

- returns `status="disabled"` with an empty summary when equity distribution is disabled (`:451`), and `status="failed"` when `annual_rows` is empty (`:461`) or the equity investment cannot be derived (`:477`);
- otherwise derives the equity investment (`_derive_equity_investment_usd`, `:471`; a config default yields `investment_source="defaulted"`, `finance/equity_distribution_v14_hydra.py:318`), builds the distribution schedule, then computes `equity_irr` via `calculate_equity_irr` (`:508`), `equity_npv` via `calculate_equity_npv` (`:509`), and `equity_multiple = total_distributed / equity_investment` (`:513`). These IRR/NPV/MOIC helpers come from `finance/equity_v14.py` (`calculate_equity_irr` `:67`, `calculate_equity_npv` `:72`, `calculate_moic` `:102`);
- sets `status = "defaulted" if investment_source == "defaulted" else "computed"` (`:530`) and returns the three headline numbers under `equity_summary` (`finance/equity_distribution_v14_hydra.py:538-545`).

### 4.3 The adapter into `EquityPerformance`

`_update_kpis_with_equity_distribution` (`analytics/pipeline_v14_enhanced.py:399`) is the bridge:

- records `kpis["equity_distribution_status"]` (`:404`);
- returns `None` (so `ScenarioResult.equity_performance` stays `None`) unless `status ∈ {"computed", "defaulted"}` (`analytics/pipeline_v14_enhanced.py:406`) **and** `equity_summary` is a mapping (`:411`);
- copies a set of summary metrics into the KPI surface, e.g. `equity_irr`, `equity_npv`, `equity_multiple`, `moic`→`equity_moic`, payback, total distributed, cash-on-cash, covenant-locked years (`analytics/pipeline_v14_enhanced.py:413-425`);
- builds `EquityPerformance(equity_irr=…, equity_npv=…, equity_multiple=…, metadata={"source": "equity_distribution_v14_hydra", "status": status, "equity_investment_source": …})` (`analytics/pipeline_v14_enhanced.py:427-436`).

The returned `EquityPerformance` is attached as `ScenarioResult.equity_performance` at `analytics/pipeline_v14_enhanced.py:581`. The distribution dict is also surfaced in the pipeline result under `"equity_distribution"` (`:602`) and its status in `ScenarioResult.metadata` (`:582`).

---

## 5. Quick reference — field provenance on `ScenarioResult`

| `ScenarioResult` field | Populated by enhanced pipeline? | Source line(s) |
|---|---|---|
| `wacc` (`WaccResult`) | Yes (or `None` if no WACC block) | `pipeline_v14_enhanced.py:548,571`; adapter `:227` |
| `wacc_label` | Yes (`"capm"`/`"fixed"`/`None`) | `pipeline_v14_enhanced.py:573` |
| `discount_rate_used` | Yes — hard-coded `0.10` | `pipeline_v14_enhanced.py:572` |
| `wacc_is_real` | **No** — stays `None` | declared `contracts_v14.py:156`; KPI sets `False` at `core/metrics.py:313` |
| `equity_performance` | Yes when status ∈ {computed, defaulted}, else `None` | `pipeline_v14_enhanced.py:535,581`; adapter `:399` |
| `fx_block` / `fx_curve` / `fx_risk_profile` | **No** — stay `None` (helper exists but is unwired) | declared `contracts_v14.py:157-159`; helper `fx/fx_integration.py:45` |

---

## 6. Relationship to existing docs (corrections)

- **`docs/ANALYTICS_INTEGRATION.md` (2025-12-21, v1.0) is stale.** It documents a different module (`analytics/pipeline_analytics_v14.py`, `docs/ANALYTICS_INTEGRATION.md:5`) and marks several capabilities as "STUB" (sensitivity/Monte-Carlo/scenario-comparison at `docs/ANALYTICS_INTEGRATION.md:15-17`, `:154-158`, `:323-325`). For the FX/WACC/Equity surface specifically, treat **this** document as authoritative; the older guide predates the built-out FX contracts and the enhanced-pipeline WACC adapter and equity wiring described above.
- **`docs/FX_INTEGRATION_v14R6.md` (2025-12-18) overstates pipeline wiring.** Its "Pipeline Execution" section shows `run_full_pipeline_v14()` calling `integrate_fx_into_scenario_result()` (`docs/FX_INTEGRATION_v14R6.md:160-173`) — that call site does not exist in the current code (see [§2.4](#24-how-scenarioresult-carries-fx--and-the-current-wiring-gap)). The FX **architecture, contracts, and builder** described in that doc remain accurate and are still valid references for the data shapes; only the "FX is wired into the live pipeline" claim is incorrect today. The aspirational docstrings inside `analytics/fx/fx_integration.py` and `analytics/fx/fx_builder.py` carry the same stale claim.

---

## 7. Practical notes

- To actually populate FX on a result today, a caller must invoke `integrate_fx_into_scenario_result` (`analytics/fx/fx_integration.py:45`) on a built `ScenarioResult`, passing the same `config`, `debt_result`, and enriched `annual_rows` the pipeline used. Wiring this into `run_v14_pipeline_enhanced` (between WACC and `ScenarioResult` assembly) and flipping the existing `fx_integration_*` metrics flags is the natural follow-up; the scaffolding in `PipelineMetrics` (`analytics/pipeline_v14_enhanced.py:70-77`) anticipates it. (Note: the only current references to the helper are its definition/docstrings, the `analytics/fx/__init__.py` re-export, the `analytics/fx_integration.py` compat shim, and import-smoke tests — there is no live call site.)
- WACC is computed and recorded but is **not** the NPV discount rate in this pipeline — KPIs use the hard-coded `0.10` (`analytics/pipeline_v14_enhanced.py:520,572`). Any reconciliation of "discount rate used" vs "computed WACC" must account for this.
- FX `var_95`/`cvar_95` from `compute_fx_risk_profile` are deliberately simplified (5% shock, `cvar = 1.5 × var`), per the in-code caveat at `analytics/fx/fx_builder.py:367`.
