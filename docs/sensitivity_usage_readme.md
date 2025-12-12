## CASPER Entry Points – analytics.sensitivity_v14

The v14 sensitivity layer exposes a small, CASPER-ready public surface that MUST be used for all deterministic tornado and breakeven work.

### 1. Canonical Contracts

- `ParameterRangeConfig`
  - Defines a single parameter shock band.
  - Fields: `variable_name`, `base_value`, `low_pct`, `high_pct`.
  - Percentages may be given as whole numbers (e.g. `-10`, `+5`) or decimals `< 1` (e.g. `-0.10`, `0.05`).

- `SensitivityRequest`
  - Bundle of inputs for a tornado run.
  - Fields:
    - `base_config_path: str`
    - `parameters: list[ParameterRangeConfig]`
    - `override_labels: dict[str, str] | None`
    - `metric: str` (e.g. `"project_irr"`, `"equity_irr"`, `"dscr_min"`)

### 2. Primary Functions

- `run(request: SensitivityRequest) -> SensitivitySuite`
  - **Canonical CASPER front door**.
  - One-way tornado on a single KPI (`request.metric`).
  - All evaluation flows through `analytics.evaluation_v14.evaluate_with_overrides()`.

- `run_tornado_sensitivity(request_or_path, parameters=None, metric=None) -> SensitivitySuite`
  - Thin wrapper around `run(...)`.
  - Supports both:
    - `SensitivityRequest` (preferred), and
    - legacy `(config_path: str, parameters, metric)` style for existing tests/CI.

- `run_multi_metric_tornado(request_or_path, metrics, parameters=None) -> MultiMetricSensitivitySuite`
  - Multi-KPI tornado (e.g. `project_irr`, `equity_irr`, `dscr_min`, `lcoe_usd_per_kwh`).
  - Returns per-parameter, per-metric low/high/base snapshots plus impact and direction.
  - Base metric values are stored once in `MultiMetricSensitivitySuite.base_metrics`.

- `run_breakeven_parameter(base_config_path, variable_name, target_metric="project_irr", target_value=0.0, ...) -> BreakevenResult`
  - Bisection search over a ±% band of the **base parameter value**.
  - Applies **absolute** overrides via the evaluation gateway (no fractional multipliers).
  - Typical use cases:
    - Tariff required for target project IRR.
    - Maximum CAPEX allowed for DSCR covenant.
    - Tenor bounds for acceptable equity IRR.

### 3. Export Helpers

- `tornado_suite_to_dataframe(suite: SensitivitySuite) -> pd.DataFrame`
  - One row per parameter.
  - Columns: `variable`, `base_irr`, `low_irr`, `high_irr`, `impact_abs`.
  - Intended for Excel / DFI tornado charts.

- `multi_metric_suite_to_dataframe(suite: MultiMetricSensitivitySuite) -> pd.DataFrame`
  - One row per `(variable, metric)` pair.
  - Columns: `variable`, `label`, `metric`, `base_value`, `low_value`, `high_value`, `impact`, `impact_dir`.
  - Designed for pivot tables and cross-metric ranking.

### 4. Gateway Invariants (GWTF / CESSPIT)

- All scenario evaluation MUST flow through:
  - `analytics.evaluation_v14.evaluate_with_overrides(config_path, overrides)`
- `None` is the canonical sentinel for "no overrides".
- `analytics.sensitivity_v14` MUST NOT import:
  - `finance.*`
  - `pipeline_v14` (or `analytics.pipeline_v14`)
- Parameter shocks are always applied as **absolute values** via
  `build_nested_override(variable_name, shocked_value)` and validated by
  `_sanitize_shocked_value(...)` before gateway calls.



 Nice, we’ve ticked off the scripts, so let’s do the tiny doc.

Here’s a **compact, CASPER/GWTF-compliant** README you can drop in as:

> `analytics/sensitivity/sensitivity_usage_readme.md`

````markdown
# analytics.sensitivity_v14 – Usage Notes

Deterministic tornado and breakeven hub for the v14 analytics layer.

This module sits **above** the v14 finance pipeline and talks only to:

- `analytics.evaluation_v14.evaluate_with_overrides`
- `analytics.contracts_v14` (for typed result surfaces)
- `analytics.scenarioloader` (for config access)

Everything else is **off-limits**: no direct `finance.*`, no direct `pipeline_v14` imports.

---

## 1. CASPER Front Door – `SensitivityRequest + run(...)`

For new code, the **canonical entry point** is:

```python
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity_v14 import SensitivityRequest, run

req = SensitivityRequest(
    base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
    parameters=[
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=1500.0,
            low_pct=-10.0,   # -10%
            high_pct=10.0,   # +10%
        ),
        ParameterRangeConfig(
            variable_name="generation.capacity_factor_pct",
            base_value=35.0,
            low_pct=-5.0,    # -5%
            high_pct=5.0,    # +5%
        ),
    ],
    metric="project_irr",
)

suite = run(req)
````

What you get back:

* `suite` is a `SensitivitySuite`
* `suite.tornado_results` is a list of `TornadoResult` rows
* `suite.base_metric` is the base KPI (e.g., base project IRR)
* `suite.metric` is the metric name (e.g., `"project_irr"`)

To export to Excel:

```python
from analytics.sensitivity_v14 import tornado_suite_to_dataframe

df = tornado_suite_to_dataframe(suite)
df.to_excel("tornado_project_irr.xlsx", index=False)
```

---

## 2. Multi-Metric Tornado – `run_multi_metric_tornado(...)`

When you need multiple KPIs in one shot:

```python
from analytics.sensitivity_v14 import run_multi_metric_tornado

metrics = ["project_irr", "equity_irr", "dscr_min"]

multi_suite = run_multi_metric_tornado(
    req,             # same SensitivityRequest as above
    metrics=metrics,
)
```

Highlights:

* `multi_suite` is a `MultiMetricSensitivitySuite`
* `multi_suite.base_metrics` holds base values for all requested KPIs
* Each `MultiMetricTornadoResult` row carries:

  * `base_values`, `low_values`, `high_values` (per metric)
  * `impacts` and `impact_dirs` (per metric)

Export to a long-form table:

```python
from analytics.sensitivity_v14 import multi_metric_suite_to_dataframe

df_multi = multi_metric_suite_to_dataframe(multi_suite)
# One row per (variable, metric) pair → easy pivot in Excel
df_multi.to_excel("tornado_multi_metric.xlsx", index=False)
```

---

## 3. Breakeven / “Solve for Tariff” – `run_breakeven_parameter(...)`

The breakeven helper solves for a parameter value that hits a target KPI,
using a simple bisection search on a percentage band around the **base** config value.

Example: solve for the tariff that yields 12% project IRR:

```python
from analytics.sensitivity_v14 import run_breakeven_parameter

result = run_breakeven_parameter(
    base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
    variable_name="tariff.tariff_lkr_per_kwh",
    target_metric="project_irr",
    target_value=0.12,     # 12% project IRR
    low_pct=-0.5,          # -50% of base tariff
    high_pct=0.5,          # +50% of base tariff
    tol=1e-4,
    max_iter=50,
)

print("Status:", result.status)
print("Breakeven tariff:", result.breakeven_value)
print("Bracket:", result.bracket)
```

Notes:

* `low_pct` / `high_pct` are **percentages**, not absolute values

  * `-0.5` → -50%, `0.5` → +50%
* Internally, the module:

  * pulls the base parameter value from the scenario config
  * converts percentage shocks to absolute values
  * runs all evaluations via `evaluate_with_overrides(...)`
  * applies pre-shock sanitization (e.g., no negative tariffs)

---

## 4. Percentage & Sanitization Behaviour (Gotchas)

**Percentage normalisation**

* Values with `abs(pct) > 1` are treated as whole-number percentages
  → `5` → `5%`, `-10` → `-10%`
* Values with `abs(pct) <= 1` are treated as already-decimal
  → `0.05` → `0.05` (5%), `-0.10` → `-0.10` (-10%)
* Ambiguous decimals like `0.075` are passed through as `0.075` (0.075%)
  → **Best practice:** use whole numbers in YAML (e.g. `low_pct: -10`)

**Pre-shock sanitization**

* Parameters whose names contain any of:

  * `capex`, `opex`, `tariff`, `capacity`, `rate`, `price`, `cost`
  * are treated as **positive-only**
* Shocks that push them to `<= 0` raise `ValueError` before hitting the pipeline
* Extremely large shocks (e.g. >10× or <0.1× base) emit warnings in logs

---

## 5. Legacy Usage (Avoid for New Code)

There is still a legacy style for tests / old wiring:

```python
from analytics.sensitivity_v14 import run_tornado_sensitivity

suite = run_tornado_sensitivity(
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    parameters=[...],         # list[ParameterRangeConfig]
    metric="project_irr",
)
```

This is kept for backwards compatibility, but new code should always go through:

* `SensitivityRequest`
* `run(...)`
* `run_multi_metric_tornado(...)`
* `run_breakeven_parameter(...)`

Those are the **CASPER-grade entry points** locked by tests.

```


```
