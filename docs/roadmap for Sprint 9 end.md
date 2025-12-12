Alright, let’s turn this into a **doable hit-list** instead of a vibe. Tail-risk + Monte Carlo + sensitivity stack, Sprint-9 Phase-2 style.

I’ll structure it so your local devs can literally pick items and go.

---

## 0. Baseline sanity (before touching more code)

**Why:** Lock in the “all green” you just got.

**Commands:**

```bash
python -m mypy analytics finance run_full_pipeline_v14.py
pytest \
  tests/api/test_monte_carlo_regression_toy.py \
  tests/analytics_layer/test_monte_carlo_v14.py \
  tests/analytics_layer/test_sensitivity_tail_risk.py \
  -q
```

If that’s green, move to the roadmap below.

---

## 1. contracts_v14 hardening for tail risk + Monte Carlo

**Goal:** Make contracts_v14 the **single source of truth** for all Monte Carlo / sensitivity / tail-risk surfaces.

**Concrete edits:**

1. In `analytics/contracts_v14.py`:

   * Confirm / add exports for:

     * `MonteCarloResult`
     * `SensitivitySuite`
     * Any rich types you’re already using for tornado (e.g. `TornadoResult`, `SensitivityResult`, etc.).
   * Optionally define a tiny **tail-risk view type** (if needed later):

     ```python
     @dataclass
     class TailRiskSnapshot:
         metric: str
         confidence: float
         var: float
         cvar: float
         p10: float
         p90: float
         breach_probability: float
     ```

     (You don’t have to use it yet, but having it here keeps the contract future-proof.)

2. Ensure `__all__` (if used) exposes these, so **no module reaches into Monte Carlo internals directly**.

**Tests:**

* Add a small test to `tests/api/test_contracts_v14.py` (or equivalent):

  ```python
  from analytics.contracts_v14 import SensitivitySuite, MonteCarloResult

  def test_contracts_expose_monte_carlo_and_sensitivity():
      assert SensitivitySuite is not None
      assert MonteCarloResult is not None
  ```

---

## 2. sensitivity_v14 boundaries (GWTF rule: coordinator only)

**Goal:** Sensitivity layer **never** touches cashflow/debt directly; it only talks to the v14 pipeline wrapper.

**Steps:**

1. Open `analytics/sensitivity_v14.py` and check imports:

   * **Allowed:** `run_v14_pipeline` (or the canonical wrapper), `contracts_v14` types, scenario loader helpers.
   * **Forbidden:** `finance.cashflow_v14`, `finance.debt_v14`, any direct finance imports.

2. If any direct finance imports exist:

   * Replace them with calls into the canonical pipeline (`run_v14_pipeline_v14` or similar).

3. Ensure all API entry points:

   * `run(...)`, `SensitivityRequest(...)`, etc.
   * Accept **config path + overrides + metric** and internally call the pipeline once per case.

**Tests:**

* In `tests/analytics_layer/test_sensitivity_v14_imports.py` (your new LibCST lint test):

  * Add explicit assertions that `sensitivity_v14` does **not** import `finance.*` or `dutchbay_v13.*`.
* Add a simple functional smoke:

  ```python
  def test_sensitivity_run_smoke(tmp_path):
      # Use a tiny known scenario YAML
      result = run(
          config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
          metric="project_irr",
      )
      assert result.tornado is not None
      assert len(result.parameters) > 0
  ```

---

## 3. scenario_analytics_v14 cleanup (single canonical path)

**Goal:** One clear coordinator for “scenario analytics” that plays nice with sensitivity + Monte Carlo + exports.

**Steps:**

1. Inspect `analytics/scenario_analytics_v14.py`:

   * Remove any lingering references to `dutchbay_v14chat` / legacy packages.
   * Ensure it depends only on:

     * `analytics.contracts_v14`
     * `analytics.sensitivity_v14`
     * `analytics.monte_carlo_v14`
     * `run_full_pipeline_v14` (or the canonical pipeline function).

2. Normalize the **scenario descriptor**:

   * Use a single `ScenarioDescriptor` type from `contracts_v14` if available.
   * Make sure every public function returns **contracted types**, not random dicts.

3. If there are ad-hoc helper functions that duplicate logic from Monte Carlo or sensitivity:

   * Thin them out, and **reuse** the canonical helpers instead.

**Tests:**

* Add a small contract test file, e.g. `tests/analytics_layer/test_scenario_analytics_v14.py`:

  * Smoke test that `run_scenario_analytics(...)` (or whatever the main entry is called) returns:

    * A `ScenarioResult` / `ScenarioDescriptor`.
    * Consistent attributes: `name`, `base_case`, `tornado`, `monte_carlo` references, etc.

---

## 4. Strict-mode schema guards everywhere (CASPER: Config → Schema → Engine)

**Goal:** Every analytics entry point (sensitivity, Monte Carlo, scenario analytics) enforces the **same** schema rules as the base pipeline.

**Steps:**

1. Identify all public analytics entry points:

   * `analytics.monte_carlo_v14.run_monte_carlo(...)`
   * `analytics.sensitivity_v14.run(...)`
   * Any scenario analytics “high-level” wrappers.

2. For each:

   * Ensure they:

     * Load config using the **same loader** as `run_full_pipeline_v14`.
     * Call `validate_config_for_v14(..., validation_mode="strict", modules=[...])` **before** cashflow/debt.

3. Plumb through a `validation_mode` kwarg with sensible default:

   ```python
   def run_monte_carlo(..., validation_mode: str = "strict", ...):
       ...
   ```

4. Make sure gwth rules hold:

   * Strict mode must **require `annual`**.
   * Same error messages as the main pipeline (“Please fix the above fields in: <config_path> and rerun.” once we add that UX later).

**Tests:**

* Extend existing Monte Carlo test:

  * Call `run_monte_carlo(..., validation_mode="strict")` and confirm it passes.
* Add a **negative** test with a deliberately broken config (missing `annual`) and assert it raises the same schema error type/message as the core pipeline.

---

## 5. Monte Carlo → CASPER wrapper (clean, dashboard-ready API)

**Goal:** One thin helper that turns Monte Carlo + tail risk into a **CASPER-friendly bundle** (no numpy, no weird types).

**Steps:**

1. In `analytics/monte_carlo_v14.py` (or a new file `analytics/monte_carlo_casper.py` if you want stricter separation):

   * Implement something like:

     ```python
     from analytics.contracts_v14 import MonteCarloResult, SensitivitySuite

     def build_casper_payload(
         mc_result: MonteCarloResult,
         tornado_suite: SensitivitySuite | None = None,
         metric: str = "project_irr",
         confidence: float = 0.9,
     ) -> dict[str, Any]:
         """
         CASPER-facing payload: JSON-safe dict with summary stats, tail risk,
         and (optionally) tornado/tail-risk-enriched DataFrame as records.
         """
     ```

2. Use your new `enrich_tornado_with_tail_risk(...)`:

   * Convert resulting DataFrame to **records**:

     ```python
     tdf = enrich_tornado_with_tail_risk(tornado_suite, mc_result, metric, confidence)
     tornado_records = tdf.to_dict(orient="records")
     ```

3. Ensure everything in the returned dict is:

   * JSON-serializable: `float`, `str`, `dict`, `list`.
   * No numpy dtypes or Pandas objects leaking out.

4. Include at minimum:

   * `metric`
   * `confidence`
   * `mean`, `std`, `p10`, `p50`, `p90`
   * `var`, `cvar`
   * `breach_probability` (relative to some covenant threshold, if relevant)
   * Optional: `tornado_records` if `tornado_suite` is provided.

**Tests:**

* New `tests/analytics_layer/test_monte_carlo_casper.py`:

  * Build a tiny `MonteCarloResult` with synthetic data.
  * Call `build_casper_payload(...)`.
  * Assert:

    * Return type is `dict`.
    * All nested structures are JSON-serializable (you can literally `json.dumps` it).
    * Tail risk values match expectations for a simple synthetic distribution.

---

## 6. Multi-tech / multi-metric breakdown – end-to-end check

**Goal:** Prove the stack can handle **multiple metrics and multiple parameters** without silently breaking.

If you don’t have multi-tech wiring yet, treat this as **multi-metric** for now.

**Steps:**

1. Extend `test_monte_carlo_v14.py` (or add a new test) to:

   * Run Monte Carlo for **two metrics**, like `project_irr` and `equity_irr`.
   * Use the CASPER payload helper to build a summary for both.

2. Confirm:

   * Each metric gets its own summary + tail risk snapshot.
   * No cross-contamination between metrics.

3. If you already have multi-tech config (e.g., solar+wind, or multiple plants under one umbrella):

   * Add a tiny YAML with two “projects” and ensure:

     * CFADS aggregation works.
     * Monte Carlo + sensitivity still behave as expected.

**Tests:**

* A new test in `tests/analytics_layer/test_monte_carlo_multimetric.py`:

  * Very small sample size (e.g., 100) just to keep it fast.

---

## 7. Exporter stability + KPI normalization

**Goal:** Excel/DFI exports are **stable, boring, and predictable** – global fund manager doesn’t have to guess what column means what.

**Steps:**

1. Open `analytics/sensitivity_export.py`:

   * Confirm `tornado_suite_to_dataframe(...)` is the canonical tornado exporter.
   * Ensure `enrich_tornado_with_tail_risk(...)` builds on top of this without changing existing columns (only **adds**).

2. Standardize column names across tornado + tail risk:

   * Example set:

     * `Parameter`
     * `Base Metric`
     * `Low Metric`
     * `High Metric`
     * `VaR`
     * `CVaR`
     * `P10`
     * `P50`
     * `P90`
     * `BreachProb`

3. In Monte Carlo + CASPER payloads:

   * Normalize KPI keys:

     * `project_irr`
     * `equity_irr`
     * `min_dscr`
     * `avg_dscr`
     * `npv_project`
     * `npv_equity`
   * No camelCase / snakeCase mix-ups.

**Tests:**

* Add to `test_sensitivity_tail_risk.py`:

  * Assert that the returned DataFrame contains the **full expected column set**.
* Add a tiny export test:

  * Convert tail-risk-enriched DataFrame to Excel/CSV (in memory) and ensure no type errors.

---

## 8. CI wiring (keep everything enforced)

**Goal:** If someone violates these boundaries later, CI screams before they hit `main`.

**Steps:**

1. Update `pytest` default command (or at least your “fast lane”) to include:

   ```bash
   pytest \
     tests/api/test_monte_carlo_regression_toy.py \
     tests/analytics_layer/test_monte_carlo_v14.py \
     tests/analytics_layer/test_sensitivity_tail_risk.py \
     tests/analytics_layer/test_sensitivity_v14_imports.py \
     tests/analytics_layer/test_monte_carlo_casper.py
   ```

2. Ensure `python -m mypy analytics finance run_full_pipeline_v14.py` is in:

   * Either `pre-commit` or the main GitHub Actions workflow.

3. Optionally:

   * Use `gh_tools.py` to create a **Sprint-9 tail-risk/Monte-Carlo** milestone and issues corresponding to **1–7** above so devs have tickets to chew through.

---

## Confidence

* **Internal (model) confidence:** 0.86
* **External (evidence/grounding) confidence:** 0.80

If you tell me **which item you want to start with first** (e.g. “do CASPER payload next” or “lock strict-mode guards”), I can turn that single item into a **ready-to-paste code patch** plus its tiny test file.
