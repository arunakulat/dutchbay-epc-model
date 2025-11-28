# **DutchBay EPC Model --- v14 Analytics Layer (Snapshot README)**

**Status: November 2025**

This document captures the current stable state of the v14 analytics
stack after the refactor and DSCR/KPI test alignment work.\
Use this README as the baseline reference when continuing development in
a new environment or new ChatGPT thread.

------------------------------------------------------------------------

## **1. Architectural Positioning**

### **v14 is the canonical pipeline.**

The analytics layer (ScenarioAnalytics + metrics + loader + EPC helper)
is now stable and test-validated.\
v13 components (scenario_runner, old CLI, old pipeline tests) are
*legacy* and used only for isolated compatibility runners.

### **Analytics layer sits *above* the modelling engines.**

-   `analytics/scenario_loader.py` = central loader\
-   `analytics/core/metrics.py` = unified KPI computation\
-   `analytics/scenario_analytics.py` = scenario orchestration + summary
    builder\
-   `analytics/core/epc_helper.py` = v14-style EPC breakdown
    (analytics-facing only)

v14 finance modules (`dutchbay_v14chat/finance/*`) remain underlying
engines and will be progressively rewired into analytics outputs.

------------------------------------------------------------------------

## **2. What Works (Stable & Tested)**

### **ScenarioAnalytics v14 path**

-   Loads configs via central loader
-   Produces CFADS series + debt_result via v14 engines\
-   Computes KPIs through unified metrics module\
-   Merges EPC breakdown into scenario summaries\
-   Handles multiple scenario files cleanly

### **DSCR filtering logic**

Enforced by tests: - Drop non-finite values: `nan`, `inf`, `-inf`\
- Drop non-positive values (`<= 0`)\
- Compute: - `dscr_min`\
- `dscr_max`\
- `dscr_mean`\
- `dscr_median`\
- Return cleaned `dscr_series` in output payload

### **KPI calculation**

`calculate_scenario_kpis()`: - Uses `npf.npv()`, `npf.irr()`\
- Falls back to CFADS-derived equity investment if valuation block is
incomplete\
- Accepts `valuation` and `debt_result` dicts from upstream\
- Fully test-covered

### **EPC breakdown**

`epc_breakdown_from_config()`: - Extracts EPC/Capex buckets from
v14-style configs - Adds `epc_usd`, `freight_usd`, `contingency_usd`,
`development_usd`, `other_usd` to summary table - Purely
analytics-facing (not yet wired into cashflow timing)

------------------------------------------------------------------------

## **3. Shared Constants**

`constants.py` defines project-wide defaults:\
- Currency\
- Project life / CF / degradation\
- Discount rate\
- DSCR thresholds\
- Validation boundaries\
This prevents scattered magic numbers across modules.

------------------------------------------------------------------------

## **4. Test Environment**

### **Active tests (as per pytest.ini)**

Only relevant v14 tests are enabled:

    testpaths =
        tests
        dutchbay_v14chat/tests

Current green set: - `tests/test_scenario_analytics_smoke.py` -
`tests/test_scenario_analytics_kpi_dscr_filtering.py`

Coverage threshold: **20%** (met)

------------------------------------------------------------------------

## **5. Required Files for Rehydrating Context in a Fresh Thread**

1.  `project_structure.json`\
2.  `analytics/core/metrics.py`\
3.  `analytics/scenario_analytics.py`\
4.  `analytics/scenario_loader.py`\
5.  `analytics/core/epc_helper.py`\
6.  `tests/test_scenario_analytics_smoke.py`\
7.  `pytest.ini`\
8.  `constants.py`

Additional helpful uploads: scenario configs, finance modules, legacy
runner.

------------------------------------------------------------------------

## **6. Recommended Next Steps**

1.  Add minimal v14 pipeline smoke test\
2.  Fix `project_life_years` extraction\
3.  Enhance analytics metrics (P50/P90 DSCR, etc.)\
4.  Wire EPC fully into cashflow\
5.  Harden CLI interface

------------------------------------------------------------------------

## **7. Clean Start Procedure**

Paste this at the start of a new ChatGPT thread:

    This is a continuation of the v14chat-upgrade work.
    ScenarioAnalytics + DSCR micro-test are passing.
    v13 tests are quarantined.
    I will upload the key repo files next.

------------------------------------------------------------------------

## **8. Ownership**

This README captures the canonical state as of the final consolidation.
Future refactors should preserve established API contracts unless
explicitly versioned.
