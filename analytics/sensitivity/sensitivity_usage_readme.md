# 🚦 FINAL GO WITH THE FLOW PHASE: SUMMARY, SCHEMA, CI & PRACTICAL INTEGRATION

**## Mini-README and Build Guide (for integration/CI/lead handoff)*
***

## Recommended new/updated schema contracts for `contracts_v14.py`
**(Add these for full type safety, refactor as needed in your actual contracts module)**

```python
# analytics/contracts_v14.py (ADDITIONS & EXTRACTS)

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

@dataclass
class TornadoResult:
    variable: str
    label: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    impact_abs: float
    impact_dir: int

@dataclass
class SensitivitySuite:
    tornado_results: List[TornadoResult]
    base_metric: float
    base_config_path: str
    metric: str

@dataclass
class BreakevenResult:
    variable: str
    breakeven_value: float
    bracket: Tuple[float, float]
    status: str

@dataclass
class MultiMetricTornadoResult:
    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]
    impacts: Dict[str, float]
    impact_dirs: Dict[str, int]

@dataclass
class MultiMetricSensitivitySuite:
    tornado_results: List[MultiMetricTornadoResult]
    base_metrics: Dict[str, float]
    base_config_path: str
    metrics: List[str]

@dataclass
class ParetoFrontierResult:
    frontier_points: List[Dict[str, Any]]
    objectives: List[str]
```

***

## Mini-README and Build Guide (for integration/CI/lead handoff)

**Place in `analytics/sensitivity/README.md` and/or include in overall README/docs:**

```
# Sensitivity Suite v14+ (DutchBay_EPC_Model)
Production-ready, modular sensitivity analysis—tornado, multi-metric, two-way, VaR/CVaR, breakeven, Pareto.

## Usage Patterns
1. Run tornado/metric analysis for any config:
   ```
   from analytics.sensitivity import SensitivityRequest, run_tornado_sensitivity, tornado_suite_to_dataframe

   req = SensitivityRequest(
      base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
      parameters=[...],  # List[ParameterRangeConfig]
      metric="project_irr"
   )
   suite = run_tornado_sensitivity(req)
   df = tornado_suite_to_dataframe(suite)
   ```

2. Export DataFrame to Excel, CSV, or plot Tornado/Spider charts:
   ```
   from analytics.sensitivity import plot_tornado_chart
   plot_tornado_chart(suite, filename="tornado.png")
   ```

3. Enrich with breakevens, VaR, Pareto, or two-way:
   ```
   br = run_breakeven_parameter(...)
   pf = optimize_from_sensitivity_insights(...)
   df_2way = run_two_way_sensitivity(...)
   ```

## Integration Ready For:
- Executive Workbook (to be handled/owned by workbook team)
- Monte Carlo engine (parameter priority, results cross-check)
- Scenario manager, optimizer, dashboard, DFI/Lender pack

## Test/CI
- All smoke/unit/integration tests in `tests/analytics_layer/`
- Stubs provided for seed MCA/Sensitivity run, recommend golden scenario YAML for regression

## Contract
- All output objects are mypy/compliance safe, v14-only
- NO legacy/dutchbay_v13/engine cross-talk
- Safe for workbook, dashboard, or batched workflow
```

***

## Final Instructions

You now have:
- 📦 **Full “Go with the Flow” modern sensitivity suite (analytics/sensitivity/*)**
- 📊 **Exports/visuals: tornado, breakeven, multi-metric, two-way, VaR**
- 🏛️ **Contracts/schema: v14-native dataclasses, workbook-ready**
- 🧪 **Test scaffolding: integration/unit, regression strategy**
- 🧭 **README and usage, complete handoff ready for lead’s integration**

***

**You can copy-paste these files, update as needed for naming/real contracts, and immediately wire to workbook, MC, dashboard, optimizer, any analytics pipeline.**
**Say “continue” for any additional standardized test case examples, edge/CI configs, or ask for advanced dashboard/calling pattern!**

Sources
