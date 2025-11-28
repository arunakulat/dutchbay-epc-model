# DutchBay v14 Scenario Analytics Layer

This README documents the v14 *analytics* surface that sits on top of the DutchBay EPC model. It is the canonical entrypoint for running multi-scenario analyses against the v14 cashflow + debt stack and producing board‑grade KPI tables.

The current design keeps analytics thin and pushes heavy lifting into the v14 finance modules (`dutchbay_v14chat.finance.*`) and a small set of shared helpers under `analytics/`.

---

## 1. Overview

The analytics layer is responsible for:

- Loading scenario configs in a v13/v14‑compatible way.
- Running the v14 cashflow + debt pipeline for each scenario.
- Computing per‑scenario KPIs (NPV, IRR, DSCR stats, CFADS stats, debt stats).
- Optionally deriving an EPC cost breakdown for reporting.
- Aggregating results into:
  - a **summary** DataFrame (one row per scenario), and
  - a **timeseries** DataFrame (one row per year per scenario).
- Optionally exporting Excel and charts via `analytics.export_helpers`.

The v14 analytics layer is deliberately self‑contained and *does not* depend on the old `dutchbay_v13.scenario_runner`. v13 tests are quarantined; v14 is the canonical surface.

---

## 2. Key modules and responsibilities

### 2.1 `analytics/scenario_loader.py`

**Purpose:** single, v13/v14‑aware scenario loader.

Key behaviours:

- Accepts YAML or JSON configs via:

  ```python
  from analytics.scenario_loader import load_scenario_config

  config = load_scenario_config("scenarios/example_a.yaml")
  ```

- Normalises field naming via `FIELD_ALIASES`, so old and new configs both work:

  - `capex`: `["capex", "total_capex", "project_cost"]`
  - `opex`: `["opex", "annual_opex", "operating_expense"]`
  - `tariff`: `["tariff", "tariff_config", "ppa_tariff"]`

- Resolves FX in a tolerant way (`_resolve_fx`):
  - Looks for a scalar `config["fx"]` if present.
  - Falls back to nested `fx.start_lkr_per_usd` if defined.
  - Otherwise uses `DEFAULT_FX_USD_TO_LKR` from `constants.py`.

- Auto‑populates missing currency fields (`_populate_currency_fields`):
  - **CAPEX**: ensures `capex.usd_total` **and** `capex.lkr_total` exist.
  - **OPEX**: ensures `opex.usd_per_year` **and** `opex.lkr_per_year` exist.

- Minimal structure validation (`_validate_required_fields`):
  - Requires top‑level `capex`, `opex`, `tariff` keys.
  - Requires at least one of `capex.usd_total` / `capex.lkr_total`.
  - Requires at least one of `opex.usd_per_year` / `opex.lkr_per_year`.

As a result, anything handed off to `dutchbay_v14chat.finance.cashflow.build_annual_rows` has a consistent, predictable shape.

---

### 2.2 `analytics/core/metrics.py`

**Purpose:** centralised KPI engine for NPV/IRR and DSCR/CFADS statistics.

Imports:

- `DEFAULT_DISCOUNT_RATE` from `constants.py`
- `as_float`, `get_nested` from `finance.utils`
- `numpy_financial` as `npf`

#### Helper functions

- `_safe_float(value, default=0.0) -> float`  
  Defensive float conversion (rarely needed outside this module).

- `_summary_stats(values) -> dict`  
  Returns `{min, max, mean, median}` for a numeric series, with all fields `None` on empty input.

#### `calculate_scenario_kpis(...)`

This is the **only** public surface the rest of the code should use.

Signature (simplified):

```python
from analytics.core.metrics import calculate_scenario_kpis

result = calculate_scenario_kpis(
    annual_rows=annual_rows,          # optional
    debt_result=debt_result,          # REQUIRED
    config=config,                    # optional, for equity investment
    discount_rate=0.08,               # optional
    scenario_name="example",          # optional
    valuation={"npv": ..., "irr": ...},  # optional override
    cfads_series_usd=[...],           # optional explicit CFADS
)
```

Two supported call styles:

1. **Pipeline style** (used by `ScenarioAnalytics`):

   ```python
   kpis = calculate_scenario_kpis(
       annual_rows=annual_rows,
       debt_result=debt_result,
       config=config,
       discount_rate=0.08,  # or None → DEFAULT_DISCOUNT_RATE
   )
   ```

2. **Unit‑test / functional style** (used in `tests/test_scenario_analytics_smoke.py`):

   ```python
   kpis = calculate_scenario_kpis(
       scenario_name="example",
       valuation={"npv": 1_234_567.0, "irr": 0.15},
       debt_result={"dscr_series": [1.5, None, 2.0, 0.0, float("inf")]},
       cfads_series_usd=[100.0, 200.0, 300.0],
   )
   ```

Key behaviours and contracts:

- **CFADS series** (Section 1 in the code):
  - If `cfads_series_usd` is provided, it is cleaned via `as_float` into `cfads_series_clean`.
  - Else, if `annual_rows` is provided, CFADS is pulled from each row’s `cfads_usd` field.
  - Else, it falls back to a zero CFADS series sized to the DSCR series length.

- **DSCR cleaning** (Section 2):
  - Takes `debt_result["dscr_series"]`.
  - Drops:
    - `None`
    - non‑numeric values (TypeError / ValueError)
    - non‑finite values (`NaN`, `+/-inf`)
    - **zero or negative values** (`<= 0.0`)
  - The cleaned list is exposed as `result["dscr_series"]`.
  - Summary stats (`dscr_min`, `dscr_max`, `dscr_mean`, `dscr_median`) are computed from the cleaned series only.
  - If the cleaned series is empty, all four stats are `None`.

  This behaviour is pinned by the DSCR micro‑test:

  ```python
  dscr_series = [1.5, None, 2.0, 0.0, float("inf")]
  # → result["dscr_series"] == [1.5, 2.0]
  #   and stats based only on [1.5, 2.0]
  ```

- **Valuation (Section 3)**:
  - If `valuation` is provided:
    - Passthrough: `npv = valuation["npv"]`, `irr = valuation["irr"]` (if present).
  - Else:
    - Derives equity investment as:
      - `capex_total = config["capex"]["usd_total"]` (via `get_nested` + `as_float`).
      - `debt_raised = sum(debt_result["principal_series"])` (via `as_float`).
      - `equity_investment = capex_total - debt_raised`.
    - Builds equity cashflow series: `[-equity_investment] + cfads_series_clean`.
    - Computes:
      - `irr_value = npf.irr(cash_flows)` (or `None` on failure).
      - `npv_value = npf.npv(discount_rate or DEFAULT_DISCOUNT_RATE, cash_flows)` (or `None`).

- **Debt & CFADS stats (Section 4)**:
  - Reads from `debt_result`:
    - `max_debt_usd`
    - `final_debt_usd`
    - `total_idc_usd`
  - Computes CFADS summary stats and aggregates from `cfads_series_clean`:
    - `cfads_min`, `cfads_max`, `cfads_mean`, `cfads_median`
    - `total_cfads_usd` (sum)
    - `final_cfads_usd` (last year)
    - `mean_operational_cfads_usd` (simple average)

Return payload (core keys):

```python
{
    "npv": npv_value,
    "irr": irr_value,
    "dscr_min": ...,
    "dscr_max": ...,
    "dscr_mean": ...,
    "dscr_median": ...,
    "dscr_series": [...],
    "max_debt_usd": ...,
    "final_debt_usd": ...,
    "total_idc_usd": ...,
    "cfads_min": ...,
    "cfads_max": ...,
    "cfads_mean": ...,
    "cfads_median": ...,
    "total_cfads_usd": ...,
    "final_cfads_usd": ...,
    "mean_operational_cfads_usd": ...,
    # and optionally:
    "scenario_name": "example",  # if provided
}
```

All of this is designed to be stable and test‑driven so downstream reporting code can rely on it.

---

### 2.3 `analytics/core/epc_helper.py`

**Purpose:** derive a simple EPC cost breakdown from the scenario config for reporting.

Usage:

```python
from analytics.core.epc_helper import epc_breakdown_from_config

epc = epc_breakdown_from_config(config)
```

Key behaviours:

- Reads CAPEX in USD via `capex.usd_total` (falling back to LKR via FX if needed).
- Tries to extract the following components (all in USD):
  - `capex.components.epc_usd`
  - `capex.components.freight_usd`
  - `capex.components.contingency_usd`
  - `capex.components.development_usd`
- If components are missing, defaults them to `0.0` while preserving the total.
- Computes a residual `other_usd = max(capex_total_usd - sum(components), 0.0)`.
- Returns a dict:

```python
{
    "total_usd": capex_total_usd,
    "epc_usd": epc_usd,
    "freight_usd": freight_usd,
    "contingency_usd": contingency_usd,
    "development_usd": development_usd,
    "other_usd": other_usd,
}
```

Failures in this helper are caught by `ScenarioAnalytics` and must **never** break the main pipeline.

---

### 2.4 `analytics/scenario_analytics.py`

**Purpose:** orchestrate the full v14 pipeline over a set of scenarios and assemble analytics‑grade outputs.

Key imports:

- `load_scenario_config` from `analytics.scenario_loader`
- `build_annual_rows` from `dutchbay_v14chat.finance.cashflow`
- `apply_debt_layer` from `dutchbay_v14chat.finance.debt`
- `calculate_scenario_kpis` from `analytics.core.metrics`
- `epc_breakdown_from_config` from `analytics.core.epc_helper`
- Optional: `ExcelExporter`, `ChartExporter` from `analytics.export_helpers`

#### `ScenarioResult` dataclass

A simple container:

```python
@dataclass
class ScenarioResult:
    name: str
    config_path: Path
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]
```

#### `ScenarioAnalytics` class

Constructed as:

```python
from analytics.scenario_analytics import ScenarioAnalytics

sa = ScenarioAnalytics(
    scenarios_dir=Path("scenarios"),
    output_path=Path("exports/scenario_analytics.xlsx"),
)
```

Core methods:

- `discover_scenarios() -> List[Path]`  
  - Scans `scenarios_dir` for `*.yaml`, `*.yml`, `*.json`.  
  - Raises `FileNotFoundError` if the directory itself is missing.

- `process_scenario(config_path: Path) -> ScenarioResult`  
  For a single scenario:
  1. Loads and normalises the config via `load_scenario_config`.
  2. Builds annual cashflows via `build_annual_rows(config)`.
  3. Applies the debt layer via `apply_debt_layer(config, annual_rows)`.
  4. Optionally derives an EPC breakdown via `epc_breakdown_from_config(config)`.
  5. Computes KPIs via `calculate_scenario_kpis(...)`.
  6. Merges EPC breakdown into the KPI dict (if available).
  7. Returns a `ScenarioResult` with all artefacts attached.

- `_build_dataframes(results)` (internal)  
  - Builds:
    - **summary_df**: one row per scenario, essentially `result.kpis` plus `scenario_name`.
    - **timeseries_df**: flattens each `annual_rows` list into long form with scenario labels.

- `run(export_excel=True, export_charts=False)`  
  - Discovers all scenarios under `scenarios_dir`.
  - Runs `process_scenario` for each, capturing any failures.
  - Logs a multi‑scenario summary, including a list of failures if any.
  - Builds summary and timeseries DataFrames.
  - If `ExcelExporter` is available **and** `export_excel=True`:
    - Writes an Excel workbook to `output_path` (by default `exports/scenario_analytics.xlsx`).
  - If `ChartExporter` is available **and** `export_charts=True`:
    - Emits charts into the same output directory.
  - Returns `(summary_df, timeseries_df)`.

Note: there is a small, internal `_summarise_dscr` helper on `ScenarioAnalytics` which is now effectively redundant because DSCR stats come from `calculate_scenario_kpis`. It can be safely removed if not used elsewhere.

#### CLI entrypoint

The module also exposes a CLI in its `__main__` block.

Usage from the repo root:

```bash
python -m analytics.scenario_analytics   --scenarios-dir scenarios   --output exports/scenario_analytics.xlsx   --charts   -v
```

CLI options (from `_build_arg_parser`):

- `--scenarios-dir`: directory containing scenario YAML/JSON files (default: `scenarios`).
- `--output`: path to Excel output file (default: `exports/scenario_analytics.xlsx`).
- `--no-excel`: don’t write Excel output (still builds and returns DataFrames).
- `--charts`: export charts (requires `ChartExporter`).
- `--strict`: fail‑fast on first scenario error.
- `-v / --verbose`: increase logging verbosity (`-v` → INFO, `-vv` → DEBUG).

---

### 2.5 `constants.py`

A small, centralised set of project defaults used by the analytics layer and finance modules, including:

- `DEFAULT_FX_USD_TO_LKR = 375.0`
- `DEFAULT_PROJECT_LIFE_YEARS = 20`
- `DEFAULT_CAPACITY_FACTOR = 0.35`
- `DEFAULT_DEGRADATION = 0.005`
- `DEFAULT_DISCOUNT_RATE = 0.08`
- `DEFAULT_DSCR_THRESHOLD = 1.25`
- Validation ranges for capacity and capacity factor.

These provide sensible defaults and keep magic numbers out of the analytics code.

---

## 3. Tests and pytest configuration

### 3.1 `tests/test_scenario_analytics_smoke.py`

This file covers:

1. A **batch smoke test** over the example scenarios directory:
   - Runs `ScenarioAnalytics` on the bundled scenario configs.
   - Asserts that:
     - The summary DataFrame has expected KPI columns (`npv`, `irr`, DSCR stats, CFADS aggregates, etc.).
     - The timeseries DataFrame contains at least one row per scenario/year.
     - The per‑scenario KPI dict includes a numeric `dscr_series`.

2. A **micro‑unit test of DSCR cleaning**:
   - Directly calls `calculate_scenario_kpis(...)` with a synthetic `debt_result` that includes:
     - valid DSCR values,
     - `None`,
     - `0.0`,
     - `inf`.
   - Asserts that:
     - Only valid, positive, finite DSCRs are retained.
     - Stats are computed on the cleaned list only.
     - No NaNs/Infs leak into `dscr_min`, `dscr_max`, `dscr_mean`, `dscr_median`.

This file is the primary contract for:
- DSCR cleaning semantics.
- KPI payload shape for the analytics layer.

### 3.2 `pytest.ini`

The `pytest.ini` is deliberately narrow to keep CI signal clean while v14 hardens:

```ini
[pytest]
testpaths =
    tests
    dutchbay_v14chat/tests

python_files =
    test_scenario_analytics_smoke.py
    test_metrics_integration.py
    test_debt_validation.py
    test_v14_pipeline_smoke.py
    test_v14_mapping_smoke.py
    test_cli_v14_smoke.py

addopts =
    --cov=analytics
    --cov=dutchbay_v14chat
    --cov=finance
    --cov-fail-under=20
```

Notes:

- Only the specified `python_files` are collected, even under `testpaths`. This effectively quarantines legacy/v13 tests.
- Coverage focuses on:
  - `analytics` (this layer),
  - `dutchbay_v14chat` (v14 finance stack),
  - `finance` (shared utilities).
- The coverage floor is modest (`20%`) while v14 is still evolving; it can be raised once more tests are in place.

---

## 4. Running the analytics layer

### 4.1 Prerequisites

From imports seen in this layer, you will need at least:

- Python 3.11+ (recommended)
- `pandas`
- `numpy`
- `numpy-financial`
- `pyyaml`
- The `dutchbay_v14chat` package/modules available on `PYTHONPATH`.

Install typical dependencies (example):

```bash
pip install pandas numpy numpy-financial pyyaml pytest
```

Make sure you run commands from the project root so that `analytics/`, `finance/`, and `dutchbay_v14chat/` are importable.

### 4.2 CLI usage

From the project root:

```bash
python -m analytics.scenario_analytics   --scenarios-dir scenarios   --output exports/scenario_analytics.xlsx   --charts   -v
```

This will:

1. Load all `*.yaml` / `*.yml` / `*.json` configs under `scenarios/`.
2. Run the v14 cashflow + debt pipeline for each scenario.
3. Compute KPIs via `calculate_scenario_kpis`.
4. Optionally export Excel and charts.
5. Log a brief head of the summary and timeseries DataFrames.

### 4.3 Programmatic usage

Example minimal Python snippet:

```python
from pathlib import Path
from analytics.scenario_analytics import ScenarioAnalytics

sa = ScenarioAnalytics(
    scenarios_dir=Path("scenarios"),
    output_path=Path("exports/scenario_analytics.xlsx"),
)

summary_df, timeseries_df = sa.run(
    export_excel=True,
    export_charts=False,
)

print(summary_df.head())
print(timeseries_df.head())
```

---

## 5. Design notes and extension points

- **Single source of truth for KPIs**: all NPV/IRR/DSCR/CFADS stats should flow through `calculate_scenario_kpis`. If you need new KPIs, add them there and pin them in tests.
- **Config compatibility**: `load_scenario_config` exists to smooth over v13 vs v14 schema differences. If you introduce new config fields, consider:
  - Extending `FIELD_ALIASES` (if needed).
  - Adding minimal validation in `_validate_required_fields` or a separate validator.
- **EPC extensions**: if lenders/board require finer EPC granularity (e.g. separate foundations, grid connection, soft costs), extend `epc_breakdown_from_config` and update the analytics tests to assert the new keys.
- **Tests as contracts**: treat `tests/test_scenario_analytics_smoke.py` as the contract for:
  - Scenario discovery behaviour.
  - Output DataFrame structure.
  - DSCR cleaning rules.
  - KPI columns required for reporting.

Once v14 stabilises, coverage can be raised and additional tests (e.g. for export helpers, CLI flags, strict mode) can be wired in without changing the public surface described here.
