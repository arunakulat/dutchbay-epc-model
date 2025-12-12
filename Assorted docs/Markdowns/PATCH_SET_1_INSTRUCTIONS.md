"""
PATCH SET #1: analytics/sensitivity_v14.py → evaluation_v14-only

OBJECTIVE
─────────
Refactor sensitivity_v14.py to use ONLY evaluate_scenario() from evaluation_v14.py
as the evaluation gateway. No direct imports from pipeline_v14 or scenario_loader.

SCOPE
─────
This is a surgical refactoring that:
1. Adds SensitivityResult dataclass (internal Phase 1 contract)
2. Rewires _analyze_single_parameter to use evaluate_scenario() only
3. Keeps all existing public API (run_tornado_sensitivity, etc) unchanged
4. Maintains backwards compatibility (legacy tests keep working)

FILES TO MODIFY
───────────────
analytics/sensitivity_v14.py

KEY CHANGES
───────────

BEFORE:
  from analytics.pipeline_v14 import run_v14_pipeline
  from analytics.scenario_loader import load_scenario_config

  def _analyze_single_parameter(...):
      base_config = load_scenario_config(base_config_path)
      low_config = _deep_merge_config(base_config, overrides_low)
      low_pipeline_result = run_v14_pipeline(config=low_config, validation_mode="strict")
      low_kpis = low_pipeline_result["kpis"]

AFTER:
  from analytics.evaluation_v14 import evaluate_scenario

  def _analyze_single_parameter(...):
      low_kpis = evaluate_scenario(base_config_path, overrides=overrides_low)

INSTRUCTIONS FOR LOCAL DEVS
────────────────────────────

1. REPLACE imports block

   OLD:
   ```python
   from analytics.pipeline_v14 import run_v14_pipeline
   from analytics.scenario_loader import load_scenario_config
   ```

   NEW:
   ```python
   from analytics.evaluation_v14 import evaluate_scenario
   ```

2. ADD new SensitivityResult dataclass after imports

   ```python
   @dataclass(slots=True)
   class SensitivityResult:
       \"\"\"
       Canonical sensitivity result surface for a single scenario config.

       base_kpis:
           KPI snapshot at unshocked (base) configuration.

       shocked_kpis:
           For each parameter_name, a mapping:
               shock_label -> KPI snapshot

           e.g.
               {
                   "project.capex_usd_per_kw": {
                       "down": {...},
                       "up": {...},
                   },
               }
       \"\"\"

       base_kpis: Dict[str, float]
       shocked_kpis: Dict[str, Dict[str, Dict[str, float]]]
   ```

3. REFACTOR _evaluate_base_kpis() helper

   Add this NEW helper function:

   ```python
   def _evaluate_base_kpis(config_path: str | Path) -> Dict[str, float]:
       \"\"\"
       Evaluate base (unshocked) KPIs for a scenario.

       All analytics must use this gateway, not the pipeline directly.
       \"\"\"
       return evaluate_scenario(config_path=config_path, overrides=None)
   ```

4. REFACTOR _analyze_single_parameter()

   Replace the ENTIRE function body with this (keep function signature the same):

   ```python
   def _analyze_single_parameter(
       base_config_path: str,
       base_metric_value: float,
       metric_name: str,
       param: ParameterRangeConfig,
       override_labels: dict[str, str] | None = None,
   ) -> TornadoResult:
       \"\"\"
       Run low/high shocks for single parameter and return TornadoResult.

       Now uses evaluate_scenario() gateway instead of direct pipeline calls.
       \"\"\"
       variable_name = param.variable_name

       # Convert percentages to decimals (handle both formats)
       low_pct_decimal = (
           param.low_pct / 100.0 if abs(param.low_pct) > 1.0 else param.low_pct
       )
       high_pct_decimal = (
           param.high_pct / 100.0 if abs(param.high_pct) > 1.0 else param.high_pct
       )

       base_value = param.base_value

       # Calculate absolute perturbed values
       low_value = base_value * (1.0 + low_pct_decimal)
       high_value = base_value * (1.0 + high_pct_decimal)

       # Build nested override dicts
       overrides_low = _build_nested_override(variable_name, low_value)
       overrides_high = _build_nested_override(variable_name, high_value)

       logger.debug(
           \"_analyze_single_parameter: variable=%s base=%s \"
           \"low_pct=%s%% high_pct=%s%% → low_value=%s high_value=%s\",
           variable_name,
           base_value,
           param.low_pct,
           param.high_pct,
           low_value,
           high_value,
       )

       # REFACTORED: Use evaluate_scenario gateway (no direct pipeline calls)
       low_kpis = evaluate_scenario(
           config_path=base_config_path,
           overrides=overrides_low,
       )
       high_kpis = evaluate_scenario(
           config_path=base_config_path,
           overrides=overrides_high,
       )

       try:
           low_metric = float(low_kpis[metric_name])
           high_metric = float(high_kpis[metric_name])
       except KeyError as exc:
           raise KeyError(
               f\"Metric {metric_name!r} not found in KPI dict for variable \"
               f\"{variable_name!r}. Available keys: {list(low_kpis.keys())}\"
           ) from exc

       impact_abs = max(
           abs(low_metric - base_metric_value),
           abs(high_metric - base_metric_value),
       )

       impact_dir = 1 if high_metric >= base_metric_value else -1

       label = (
           override_labels.get(variable_name, variable_name)
           if override_labels is not None
           else variable_name
       )

       logger.debug(
           \"_analyze_single_parameter: variable=%s label=%s \"
           \"base=%s low=%s high=%s impact=%s dir=%s\",
           variable_name,
           label,
           base_metric_value,
           low_metric,
           high_metric,
           impact_abs,
           impact_dir,
       )

       return TornadoResult(
           variable=label,
           base_irr=base_metric_value,
           low_irr=low_metric,
           high_irr=high_metric,
       )
   ```

5. UPDATE run_tornado_sensitivity()

   Replace the base evaluation lines:

   OLD:
   ```python
   base_config = load_scenario_config(base_config_path)
   base_pipeline_result = run_v14_pipeline(
       config=base_config,
       validation_mode="strict",
   )
   base_kpis = base_pipeline_result["kpis"]
   ```

   NEW:
   ```python
   # Use evaluate_scenario gateway
   base_kpis = _evaluate_base_kpis(base_config_path)
   ```

6. UPDATE run_multi_metric_tornado()

   Same change as step 5:

   OLD:
   ```python
   base_config = load_scenario_config(base_config_path)
   base_pipeline_result = run_v14_pipeline(
       config=base_config,
       validation_mode="strict",
   )
   base_kpis = base_pipeline_result["kpis"]
   ```

   NEW:
   ```python
   # Use evaluate_scenario gateway
   base_kpis = _evaluate_base_kpis(base_config_path)
   ```

7. UPDATE run_breakeven_parameter()

   Replace base evaluation:

   OLD:
   ```python
   base_config = load_scenario_config(base_config_path)
   base_pipeline_result = run_v14_pipeline(
       config=base_config,
       validation_mode="strict",
   )
   base_kpis = base_pipeline_result["kpis"]
   ```

   NEW:
   ```python
   # Use evaluate_scenario gateway
   base_kpis = _evaluate_base_kpis(base_config_path)
   ```

   And in the objective() function inside run_breakeven_parameter():

   OLD:
   ```python
   def objective(x: float) -> float:
       overrides = _build_nested_override(variable_name, x)
       base_config = load_scenario_config(base_config_path)
       override_config = _deep_merge_config(base_config, overrides)
       pipeline_result = run_v14_pipeline(
           config=override_config,
           validation_mode="strict",
       )
       kpis = pipeline_result["kpis"]
   ```

   NEW:
   ```python
   def objective(x: float) -> float:
       overrides = _build_nested_override(variable_name, x)
       # Use evaluate_scenario gateway (no deep merge, no manual pipeline call)
       kpis = evaluate_scenario(
           config_path=base_config_path,
           overrides=overrides,
       )
   ```

VERIFICATION STEPS (Local Devs)
───────────────────────────────

After applying all changes, run:

```bash
# Type checking
mypy analytics/sensitivity_v14.py analytics/evaluation_v14.py --strict

# Formatting
black analytics/sensitivity_v14.py

# Linting
ruff check analytics/sensitivity_v14.py

# Import sorting
isort analytics/sensitivity_v14.py

# Existing sensitivity tests (should all pass)
pytest tests/ -k sensitivity -v

# Spot check: ensure _evaluate_base_kpis works
python -c "
from analytics.sensitivity_v14 import _evaluate_base_kpis
kpis = _evaluate_base_kpis('scenarios/dutchbay_lendercase_2025Q4.yaml')
print('Base KPIs:', kpis)
"
```

EXPECTED RESULTS
────────────────

✅ All existing tornado tests pass (no functional changes)
✅ mypy clean (new SensitivityResult is typed)
✅ No imports from pipeline_v14 or scenario_loader remain in sensitive_v14.py
✅ No direct run_v14_pipeline() calls remain (all go through evaluate_scenario)
✅ _build_nested_override() logic unchanged (still the single source of truth)

BACKWARDS COMPATIBILITY
───────────────────────

✅ public run_tornado_sensitivity() behavior unchanged
✅ public run_multi_metric_tornado() behavior unchanged
✅ public run_breakeven_parameter() behavior unchanged
✅ All legacy test patterns still work
✅ No breaking changes to contracts_v14 imports

FAILURE MODES & DEBUGGING
──────────────────────────

If tests fail after patching:

1. mypy errors about SensitivityResult:
   → Make sure dataclass is imported: `from dataclasses import dataclass`

2. KeyError in evaluate_scenario:
   → Means evaluation_v14.py's KPI extraction differs from your pipeline's
   → Check kpis key naming (should be dict, not wrapped in "scenario_result")
   → Verify CANONICAL_KPIS in evaluation_v14 matches your pipeline output

3. evaluate_scenario not found:
   → Ensure evaluation_v14.py exists in analytics/
   → Check imports: `from analytics.evaluation_v14 import evaluate_scenario`

4. Tests pass but performance changes:
   → Lazy config loading in evaluate_scenario_from_dict() not yet used
   → Phase 2 will wire that for sensitivity parameter sweeps

NEXT STEPS AFTER PATCH SET #1
──────────────────────────────

Phase 1B: Add test coverage for new _evaluate_base_kpis() and verify
          evaluate_scenario gateway is the only entry point.

Phase 2:  Add evaluate_scenario_from_dict() usage to sensitivity for
          lazy config loading (eliminate N file I/O).
"""
