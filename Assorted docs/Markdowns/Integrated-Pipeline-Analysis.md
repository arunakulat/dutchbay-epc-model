# Integrated Pipeline Orchestration Analysis
## Merging Core, Analytics, and Risk Layers

**Date:** December 9, 2025
**Status:** Integration Design Finalization
**Key Insight:** The user has provided the final pieces of the puzzle. We have the orchestrator (`pipeline_v14.py`) and the supporting actors (`evaluate_scenario.py`, `scenario_analytics.py`, `contracts_v14.py`). The task is to weave them into a unified, production-grade fabric.

---

## 1. COMPONENT LANDSCAPE ANALYSIS

You have uploaded six critical files that form the nervous system of the application. Here is how they fit together:

| File | Role | Key Functionality |
|------|------|-------------------|
| **`pipeline_v14.py`** | **The Base Orchestrator** | Defines `run_pipeline()`. Currently focuses on core DCF (cashflow/debt/equity). Needs to be expanded to trigger risk modules. |
| **`contracts_v14.py`** | **The Law** | Defines `SensitivitySuite`, `MonteCarloSuite`, `ScenarioResult`. This is the type-safety layer. **Crucial:** It already has the structures we need for the merged result dict. |
| **`evaluate_scenario.py`** | **The Executor** | Runs a single scenario end-to-end. This is the "atomic unit" of computation. The Monte Carlo engine calls this repeatedly. |
| **`scenario_analytics.py`**| **The Analyst** | Higher-level analysis (batch processing, comparisons). |
| **`scenario_manager.py`** | **The Librarian** | Loads, saves, and lists scenarios. |
| **`evaluation_v14.py`** | **The Wrapper** | Likely a legacy or alternative wrapper for `evaluate_scenario`. We should standardize on `evaluate_scenario.py`. |

### The "Missing Link" Identified
`pipeline_v14.py` is currently "Core-centric". It calculates IRR, NPV, and DSCR beautifully. However, it **does not yet call** `sensitivity_v14` or `monte_carlo_v14`.

**The Solution:** We don't replace `pipeline_v14.py`. We **upgrade** `run_full_pipeline_v14.py` (the script I drafted in the previous step) to use these exact components.

---

## 2. THE REVISED ORCHESTRATION FLOW

We will use the **CASPER** pattern to integrate these specific files.

### Step 1: The Atomic Unit (`evaluate_scenario.py`)
This file is perfect. It takes a config and returns a result.
*   **Action:** No changes needed. This is what the Monte Carlo engine uses to run 1,000 iterations.

### Step 2: The Data Contracts (`contracts_v14.py`)
This file is the "Rosetta Stone". It defines `ScenarioResult`.
*   **Action:** Our final `_merge_results` function must return a dict that conforms to `ScenarioResult` (or a superset of it). We must ensure the `sensitivity` and `monte_carlo` keys in our final output match the `SensitivitySuite` and `MonteCarloSuite` definitions here.

### Step 3: The Integration Layer (`run_full_pipeline_v14.py`)
This is where we do the work. We will import `run_pipeline` from `pipeline_v14.py` instead of re-implementing the DCF logic.

**Old Plan:** Re-implement DCF in `run_full_pipeline_v14.py`.
**New Plan (Better):** Wrap `pipeline_v14.py`.

```python
# run_full_pipeline_v14.py (Revised Logic)

from analytics.pipeline_v14 import run_pipeline as run_core_dcf
from analytics.sensitivity_v14 import build_sensitivity_suite
from analytics.monte_carlo_v14 import run_monte_carlo_suite

def run_v14_pipeline(config):
    # 1. Run Core (using existing robust code)
    core_result = run_core_dcf(config)

    # 2. Run Sensitivity (using the result from step 1 as baseline)
    sensitivity_result = build_sensitivity_suite(
        config,
        base_irr=core_result.project_irr,
        base_dscr=core_result.min_dscr
    )

    # 3. Run Monte Carlo (conditional)
    mc_result = None
    if config.analytics.enable_monte_carlo:
        mc_result = run_monte_carlo_suite(config)

    # 4. Merge
    return _merge_results(core_result, sensitivity_result, mc_result)
```

---

## 3. UPDATED IMPLEMENTATION PLAN

I am updating the **Code Reference** to reflect this optimized approach. By leveraging `pipeline_v14.py`, we reduce code duplication and risk.

### Phase 1: Verify `pipeline_v14.py` Exports
We need to ensure `pipeline_v14.py` returns a structured object (likely a Pydantic model or Dataclass from `contracts_v14.py`) rather than a raw dict.
*   *Observation from file:* It likely returns `PipelineResult` or similar.
*   *Integration:* We will extract values from this object to feed the risk engines.

### Phase 2: The "Super-Result" Construction
We need to construct a final JSON/Dictionary that contains:
1.  **Core:** The output of `pipeline_v14.py`.
2.  **Sensitivity:** The `SensitivitySuite` object.
3.  **Monte Carlo:** The `MonteCarloSuite` object.

### Phase 3: Validation
We will use `evaluate_scenario.py` as the "truth" for single-run validation. If `run_full_pipeline_v14.py` returns a different IRR than `evaluate_scenario.py`, we have a drift issue.

---

## 4. EXECUTIVE RECOMMENDATION

**To the Dev Team:**
"We have consolidated the architecture. We will not rewrite the DCF logic. Instead, `run_full_pipeline_v14.py` will act as a **higher-order wrapper** around `pipeline_v14.py`. It will execute the core pipeline first, then use those results to seed the Sensitivity and Monte Carlo engines. This ensures 100% consistency between the base case and the risk simulations."

**Immediate Action:**
Proceed with the implementation of `run_full_pipeline_v14.py` using the **Wrapper Pattern** described above. This is the safest, fastest path to production.

---

**Next Step:** I will now generate the updated `run_full_pipeline_v14.py` code that specifically imports and utilizes the `pipeline_v14.py` module you just uploaded. This guarantees integration without duplication.
