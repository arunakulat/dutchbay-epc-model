# 🔗 MASTER INTEGRATION ROADMAP
## DutchBay EPC Model - Cashflow → MC → Sensitivity → API Bridge

**Status:** 95% Complete (1 polish step to production-ready)
**Scope:** 5 Files, 3 Integration Guarantees, 2 Workstream Options
**Timeline:** 6-8 hours (distributed across 2 concurrent streams)

---

## 📍 CURRENT STATE

### What Local Dev Validated ✅

```
✅ Cashflow_v14 modular refactor COMPLETE
   ├─ cashflow_v14.py (facade, public API)
   ├─ cashflow_v14_params.py (extraction + validation)
   ├─ cashflow_v14_fx.py (FX resolution)
   ├─ cashflow_v14_tax.py (tax + depreciation + BOI)
   ├─ cashflow_v14_production.py (energy + opex + haircut)
   ├─ cashflow_v14_utils.py (shared helpers)
   └─ cashflow_v14_contracts.py (CashflowParams dataclass)

✅ Monte Carlo v14 CLEAN
   └─ Uses evaluate_with_overrides() → run_full_pipeline_v14()

✅ Sensitivity v14 FUNCTIONAL
   └─ Uses run_v14_pipeline() for tornado analysis

✅ API Spec DOCUMENTED
   └─ Executive Summary + API Contract Specifications define endpoints

🔄 1 POLISH STEP REMAINING
   └─ MonteCarloScenario.to_api_dict() method (5 min implementation)
```

---

## 🎯 THE FIVE MONTE CARLO GUARANTEES

### MC-1: Always Call Through Facade ✅

**Current Flow (CORRECT):**
```python
# monte_carlo_v14.py
for iteration in range(n_iterations):
    sampled_config = _apply_sample_to_config(sample)
    result = run_full_pipeline_v14(sampled_config)  # ← Facade call
    kpis.append(result["kpis"])
```

**Never Do This:**
```python
# ❌ WRONG - Direct computation
cfads_sample = calculate_cfads_directly(capacity, tariff)
dscr = cfads_sample / debt_service
```

**Validation:**
```bash
# Grep check: ensure no direct CFADS/IRR computation in monte_carlo_v14.py
grep -n "calculate_cfads\|calculate_irr\|calculate_dscr" analytics/monte_carlo_v14.py
# Expected: 0 matches (all calls go through pipeline)

# Expected 1 call pattern:
grep -n "run_full_pipeline_v14\|run_v14_pipeline" analytics/monte_carlo_v14.py
# Expected: Multiple matches (all iterations use facade)
```

---

### MC-2: Override Mapping Matches CashflowParams Surface ✅

**Current CashflowParams Fields (from refactor):**
```python
@dataclass
class CashflowParams:
    capacity_mw: float
    capacity_factor: float  # Already decimal (0.25, not 25)
    degradation: float      # Annual % (0.005 = 0.5%)
    grid_loss_pct: float
    tariff_lkr_per_kwh: float
    opex_usd_per_year: float
    success_fee_pct: float
    env_surcharge_pct: float
    social_levy_pct: float
    corporate_tax_rate: float
    depreciation_years: int
    tax_holiday_years: int
    tax_holiday_start_year: int
    enhanced_capital_allowance_pct: float
    risk_haircut_pct: float
```

**Correct Override Mapping (in _build_overrides_from_sample):**
```python
def _build_overrides_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """
    Map Monte Carlo sample to config override keys.

    RULE: Always override RAW CONFIG KEYS, not normalized CashflowParams.
    The facade (cashflow_v14.py) will normalize them via _build_cashflow_params.
    """
    return {
        # Production parameters
        "project.capacity_mw": sample.get("capacity_mw", 100.0),
        "project.capacity_factor_pct": sample.get("capacity_factor", 0.25) * 100,  # ← Scale to %
        "project.degradation_pct": sample.get("degradation", 0.005) * 100,  # ← 0.5% = 0.005
        "project.grid_loss_pct": sample.get("grid_loss_pct", 2.0),

        # Tariff (LKR)
        "tariff.lkr_per_kwh": sample.get("tariff_lkr_per_kwh", 12.5),

        # Operating expenses
        "opex.usd_per_year": sample.get("opex_usd_per_year", 150000.0),

        # Surcharges
        "surcharge.success_fee_pct": sample.get("success_fee_pct", 0.0),
        "surcharge.env_surcharge_pct": sample.get("env_surcharge_pct", 0.5),
        "surcharge.social_levy_pct": sample.get("social_levy_pct", 2.0),

        # Tax & depreciation
        "tax.corporate_rate_pct": sample.get("corporate_tax_rate", 14.0),
        "tax.depreciation_years": int(sample.get("depreciation_years", 20)),
        "tax.tax_holiday_years": int(sample.get("tax_holiday_years", 7)),
        "tax.tax_holiday_start_year": int(sample.get("tax_holiday_start_year", 1)),
        "tax.enhanced_capital_allowance_pct": sample.get("enhanced_capital_allowance_pct", 0.0),

        # Risk adjustment
        "risk_adjustment.cfads_haircut_pct": sample.get("risk_haircut_pct", 0.0) * 100,  # ← Scale to %
    }

# USAGE in monte_carlo_v14.py:
for iteration in range(n_iterations):
    sample = mc_sampler.next()  # dict from distribution
    overrides = _build_overrides_from_sample(sample)
    result = run_full_pipeline_v14(
        config=base_config,
        overrides=overrides  # ← Merged with config by facade
    )
```

**Validation:**
```python
# Test: Ensure override keys exist in v14 config schema
from analytics.schema_guard import validate_config_for_v14
from analytics.monte_carlo_v14 import _build_overrides_from_sample

sample = {"capacity_factor": 0.25, "tariff_lkr_per_kwh": 12.5}
overrides = _build_overrides_from_sample(sample)

# Merge and validate
merged_config = {**base_config, **overrides}
validate_config_for_v14(merged_config)  # Should not raise

print("✅ Override mapping valid")
```

---

### MC-3: Output Must Expose Same KPIs as API Spec ✅

**API Spec Requirement (from Executive Summary):**
```json
{
  "status": "success",
  "data": {
    "scenario": {
      "name": "dutchbay_lendercase_2025Q4",
      "description": "Base case with 15-year tenor",
      "source": "scenarios/dutchbay_lendercase_2025Q4.yaml"
    },
    "equity_irr": {
      "p10": 0.081,
      "p50": 0.152,
      "p90": 0.218,
      "mean": 0.150,
      "std": 0.035
    },
    "dscr_min": {
      "p10": 1.15,
      "p50": 1.42,
      "p90": 1.68,
      "mean": 1.41,
      "std": 0.18
    },
    "project_npv": {
      "p10": 2.5e6,
      "p50": 8.2e6,
      "p90": 14.1e6,
      "mean": 8.1e6,
      "std": 3.2e6
    },
    "correlations": {
      "capex_tariff": 0.15,
      "tariff_volume": 0.32
    },
    "tail_risk": {
      "probability_dscr_below_threshold": 0.08,
      "cvar_95": 1.18,
      "tail_ratio": 1.46
    }
  }
}
```

**Current MC Engine Output (validate this):**
```python
# In monte_carlo_v14.py, after running all iterations:

result = {
    "status": "success",
    "data": {
        "scenario": {
            "name": mc_scenario.scenario_name,
            "description": mc_scenario.scenario_descriptor,  # ← NEW: Add this
            "source": str(config_path),
        },
        "equity_irr": {
            "p10": np.percentile(equity_irr_samples, 10),
            "p50": np.percentile(equity_irr_samples, 50),
            "p90": np.percentile(equity_irr_samples, 90),
            "mean": np.mean(equity_irr_samples),
            "std": np.std(equity_irr_samples),
        },
        "dscr_min": {
            "p10": np.percentile(dscr_min_samples, 10),
            "p50": np.percentile(dscr_min_samples, 50),
            "p90": np.percentile(dscr_min_samples, 90),
            "mean": np.mean(dscr_min_samples),
            "std": np.std(dscr_min_samples),
        },
        "project_npv": {
            "p10": np.percentile(project_npv_samples, 10),
            "p50": np.percentile(project_npv_samples, 50),
            "p90": np.percentile(project_npv_samples, 90),
            "mean": np.mean(project_npv_samples),
            "std": np.std(project_npv_samples),
        },
        # OPTIONAL (Phase 3 feature):
        "correlations": _compute_parameter_correlations(...),
        "tail_risk": _compute_tail_risk(...),
    }
}
```

**Validation:**
```bash
# Run MC, capture output, validate schema
python -c "
from analytics.monte_carlo_v14 import run_monte_carlo
result = run_monte_carlo('scenarios/dutchbay_base.yaml', n_iterations=100)

# Check structure
assert result['status'] == 'success'
assert 'equity_irr' in result['data']
assert 'p50' in result['data']['equity_irr']
print('✅ MC output matches API spec')
"
```

---

### MC-4: CFADS Must Be USD-Compatible for API Timeseries ✅

**API Endpoint Response (Timeseries):**
```json
{
  "timeseries": [
    {
      "year": 1,
      "revenue_usd": 15234000,
      "cfads_usd": 5123000,
      "debt_service_usd": 2100000,
      "dscr": 2.44,
      "ebitda": 6234000
    },
    ...
  ]
}
```

**Current Cashflow Output (validate):**
```python
# From cashflow_v14.build_annual_rows():

annual_rows = [
    {
        "year": 1,
        "revenue_usd": 15234000.0,        # ✅ USD
        "cfads_usd": 5123000.0,           # ✅ USD (already normalized)
        "debt_service_usd": 2100000.0,    # ✅ USD
        "dscr": 2.44,                     # ✅ Unitless ratio
        "ebitda_usd": 6234000.0,          # ✅ USD
        ...
    },
    ...
]
```

**No Action Needed** — the refactored cashflow_v14 already outputs correct USD values.

**Validation:**
```python
# In tests/api/test_cashflow_usd_output.py
def test_cashflow_outputs_usd_values():
    annual_rows = build_annual_rows(config)
    for row in annual_rows:
        assert isinstance(row["revenue_usd"], float)
        assert isinstance(row["cfads_usd"], float)
        assert row["revenue_usd"] > 0  # Sanity check
        assert row["cfads_usd"] > 0
    print("✅ All cashflow outputs in USD")
```

---

### MC-5: Monte Carlo Scenario Description Aligns with API ✅

**Current MonteCarloScenario Class:**
```python
@dataclass
class MonteCarloScenario:
    scenario_name: str
    scenario_descriptor: str  # Path to config
    n_iterations: int
    random_seed: Optional[int] = None
    # ... other fields
```

**Missing: to_api_dict() method**

**Add This (5-minute change):**
```python
@dataclass
class MonteCarloScenario:
    scenario_name: str
    scenario_descriptor: str
    n_iterations: int
    random_seed: Optional[int] = None

    def to_api_dict(self) -> dict[str, Any]:
        """Export to API-compatible format."""
        return {
            "name": self.scenario_name,
            "description": self.scenario_descriptor or f"Monte Carlo ({self.n_iterations} iterations)",
            "source": self.scenario_descriptor,
            "iterations": self.n_iterations,
        }
```

**Usage in API Response:**
```python
# In FastAPI endpoint (monte_carlo router):
scenario = MonteCarloScenario(
    scenario_name="dutchbay_lendercase_2025Q4",
    scenario_descriptor="scenarios/dutchbay_lendercase_2025Q4.yaml",
    n_iterations=1000,
)

result = {
    "data": {
        "scenario": scenario.to_api_dict(),  # ← Now includes name + description
        "equity_irr": {...},
        ...
    }
}
```

**Validation:**
```bash
python -c "
from analytics.monte_carlo_v14 import MonteCarloScenario
scenario = MonteCarloScenario(
    scenario_name='test',
    scenario_descriptor='scenarios/test.yaml',
    n_iterations=100
)
api_dict = scenario.to_api_dict()
assert 'name' in api_dict
assert 'description' in api_dict
print('✅ MonteCarloScenario.to_api_dict() working')
"
```

---

## 🎯 SENSITIVITY INTEGRATION (SAME PRINCIPLE)

### Sensitivity Must Also Call Through Facade ✅

**Current Implementation (CORRECT):**
```python
# analytics/sensitivity_v14.py

def run_tornado_sensitivity(request: SensitivityRequest):
    """Tornado analysis with guaranteed convergence."""
    base_result = run_v14_pipeline(config=request.base_config)

    tornado_results = []
    for param in request.parameters:
        # DOWN shock
        down_overrides = _build_nested_override(param.variable_name, param.low_value)
        down_config = _deep_merge_config(request.base_config, down_overrides)
        down_result = run_v14_pipeline(config=down_config)  # ← Facade call

        # UP shock
        up_overrides = _build_nested_override(param.variable_name, param.high_value)
        up_config = _deep_merge_config(request.base_config, up_overrides)
        up_result = run_v14_pipeline(config=up_config)  # ← Facade call

        # Aggregate
        tornado_results.append({
            "parameter": param.variable_name,
            "base_value": base_result["kpis"].get(request.metric),
            "down_value": down_result["kpis"].get(request.metric),
            "up_value": up_result["kpis"].get(request.metric),
            "total_range": abs(up_result["kpis"].get(request.metric) -
                               down_result["kpis"].get(request.metric)),
        })

    return TornadoSuite(results=tornado_results)
```

**Convergence Validation (Tornado vs MC):**
```python
# NEW TEST: tests/api/test_tornado_mc_convergence.py

def test_tornado_base_matches_mc_median():
    """Verify single scenario matches MC baseline."""
    # 1. Run tornado base case
    tornado_result = run_tornado_sensitivity(
        SensitivityRequest(
            base_config_path="scenarios/base.yaml",
            parameters=[...],
            metric="project_irr",
        )
    )

    # 2. Run MC on same scenario
    mc_result = run_monte_carlo(
        config_path="scenarios/base.yaml",
        n_iterations=100,
    )

    # 3. Compare
    tornado_irr = tornado_result.base_irr
    mc_irr_p50 = mc_result["data"]["equity_irr"]["p50"]

    # Should agree (same scenario, same pipeline)
    assert abs(tornado_irr - mc_irr_p50) < 0.01, \
        f"Tornado {tornado_irr} ≠ MC P50 {mc_irr_p50}"

    print("✅ Tornado + MC converge on same baseline")
```

---

## 🏗️ WORKSTREAM DIVISION (2 OPTIONS)

### Option A: Complete Integration (Parallel Workstreams)

**Workstream 1: Engine Polish (3-4 hours)**
```
Tasks:
├─ Add MonteCarloScenario.to_api_dict() [5 min]
├─ Validate MC override mapping against CashflowParams [30 min]
├─ Create tests/api/test_monte_carlo_sensitivity_integration.py [1 hour]
├─ Verify convergence (tornado base = MC median) [1 hour]
└─ Phase 1-2 from IMPLEMENTATION_ROADMAP.md [1-2 hours]

Owner: Backend Engineer
Deliverable: ✅ All 282+ tests pass, MC + sensitivity converge
Timeline: 4 hours
```

**Workstream 2: API Bridge (2-3 hours)**
```
Tasks:
├─ Create FastAPI router scaffold (routes.py) [30 min]
├─ Implement /run/{id}/monte-carlo endpoint [30 min]
├─ Implement /run/{id}/sensitivity endpoint [30 min]
├─ Wire output schemas (Pydantic v2) [30 min]
├─ Create tests/api/test_fastapi_endpoints.py [30 min]
└─ Integration test: API → MC → cashflow_v14 [30 min]

Owner: API Engineer
Deliverable: ✅ All endpoints working, schema-validated
Timeline: 3 hours
```

**Total Effort:** 7 hours (can run in parallel → 4 hours wall time)

---

### Option B: Sequential (Single Engineer, Lower Context Switch)

**Phase 1: Engine Polish (4 hours)**
- All tasks from Workstream 1
- Deploy + validate locally

**Phase 2: API Bridge (3 hours)**
- All tasks from Workstream 2
- Deploy + validate with engine

**Total Effort:** 7 hours (sequential → 7 hours wall time)

---

## 📋 IMPLEMENTATION CHECKLIST

### Pre-Implementation Validation

```
BEFORE WE CODE:
☐ Confirm cashflow_v14 modular refactor is COMPLETE
  └─ All 7 submodules exist and pass tests

☐ Confirm monte_carlo_v14 uses evaluate_with_overrides()
  └─ Grep: "run_full_pipeline_v14" should appear

☐ Confirm sensitivity_v14 uses run_v14_pipeline()
  └─ Grep: "run_v14_pipeline" should appear

☐ Confirm CashflowParams dataclass is in cashflow_v14_contracts.py
  └─ All 14 fields present

☐ Confirm API spec is finalized (from Executive Summary)
  └─ Review: /run, /sensitivity, /monte-carlo endpoints

ANSWER: YES to all 5 → Proceed to implementation
```

---

### Phase 1: Engine Polish (4 hours)

#### Task 1.1: Add MonteCarloScenario.to_api_dict() [5 min]

**File:** `analytics/monte_carlo_v14.py`

**Change:**
```python
# Add to MonteCarloScenario dataclass:

def to_api_dict(self) -> dict[str, Any]:
    """Export to API-compatible format (for /monte-carlo endpoint)."""
    return {
        "name": self.scenario_name,
        "description": self.scenario_descriptor or f"MC {self.n_iterations} iter",
        "source": str(self.scenario_descriptor),
        "iterations": self.n_iterations,
    }
```

**Test:**
```bash
pytest tests/analytics_layer/test_monte_carlo_v14.py::test_scenario_to_api_dict -v
```

---

#### Task 1.2: Validate Override Mapping [30 min]

**File:** `analytics/monte_carlo_v14.py`

**Change:** Review + document _build_overrides_from_sample()

```python
def _build_overrides_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """
    Map Monte Carlo sample to config override keys.

    GOLDEN RULE:
    ─────────────
    Override RAW CONFIG KEYS (top-level YAML structure),
    NOT the normalized CashflowParams dataclass fields.

    The facade (cashflow_v14.build_annual_rows) will:
    1. Extract config keys → CashflowParams
    2. Validate fields
    3. Compute cashflows

    This ensures deterministic = stochastic = lender-compliant.

    Example Mappings:
    ─────────────────
    Sample Field              Config Key (Override)        Scaling
    ─────────────────────────────────────────────────────────────
    capacity_factor           project.capacity_factor_pct  * 100 (to %)
    degradation               project.degradation_pct      * 100 (to %)
    tariff_lkr_per_kwh        tariff.lkr_per_kwh           (as-is, LKR)
    opex_usd_per_year         opex.usd_per_year            (as-is, USD)
    corporate_tax_rate        tax.corporate_rate_pct       (as-is, %)
    risk_haircut_pct          risk_adjustment.cfads_haircut_pct  * 100 (to %)
    """
    return {
        "project.capacity_mw": sample.get("capacity_mw", 100.0),
        "project.capacity_factor_pct": sample.get("capacity_factor", 0.25) * 100,
        # ... (full mapping as shown earlier)
    }
```

**Test:**
```bash
pytest tests/api/test_monte_carlo_override_mapping.py -v
# Should validate: every override key exists in v14 schema
```

---

#### Task 1.3: Create Integration Test Suite [1 hour]

**File:** `tests/api/test_monte_carlo_sensitivity_integration.py` (NEW)

```python
"""
Integration tests: Verify MC ↔ Sensitivity convergence.

These tests ensure that:
1. Tornado base case = MC median (same scenario, same pipeline)
2. DSCR tracking is consistent
3. Both engines use run_v14_pipeline() as single source of truth
"""

import pytest
from analytics.monte_carlo_v14 import run_monte_carlo
from analytics.sensitivity_v14 import run_tornado_sensitivity, SensitivityRequest
from analytics.contracts_v14 import ParameterRangeConfig

def test_tornado_and_monte_carlo_converge():
    """Single scenario should produce same KPIs in both engines."""
    base_config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"

    # 1. Run tornado
    tornado_result = run_tornado_sensitivity(
        SensitivityRequest(
            base_config_path=base_config_path,
            parameters=[
                ParameterRangeConfig(
                    variable_name="project.capacity_factor_pct",
                    base_value=25.0,  # 25%
                    low_pct=-5.0,     # 20%
                    high_pct=5.0,     # 30%
                )
            ],
            metric="project_irr",
        )
    )

    # 2. Run MC
    mc_result = run_monte_carlo(
        config_path=base_config_path,
        n_iterations=100,
    )

    # 3. Compare: tornado base should match MC median
    tornado_irr = tornado_result.base_irr
    mc_irr_p50 = mc_result["data"]["equity_irr"]["p50"]

    assert abs(tornado_irr - mc_irr_p50) < 0.01, \
        f"Tornado IRR {tornado_irr} ≠ MC P50 {mc_irr_p50}"

def test_dscr_tracking_consistency():
    """DSCR should track identically in tornado and MC."""
    base_config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"

    # Tornado: DSCR metric
    tornado_result = run_tornado_sensitivity(
        SensitivityRequest(
            base_config_path=base_config_path,
            parameters=[...],
            metric="dscr_min",
        )
    )

    # MC: DSCR distribution
    mc_result = run_monte_carlo(config_path=base_config_path, n_iterations=100)

    # Both should report positive DSCR values
    assert tornado_result.base_dscr_min > 1.0
    assert mc_result["data"]["dscr_min"]["p50"] > 1.0

    # MC P50 should be in reasonable range of tornado base
    assert abs(tornado_result.base_dscr_min - mc_result["data"]["dscr_min"]["p50"]) < 0.2
```

**Test Command:**
```bash
pytest tests/api/test_monte_carlo_sensitivity_integration.py -v
# Expected: All tests pass
```

---

#### Task 1.4: Phase 1-2 of IMPLEMENTATION_ROADMAP [1-2 hours]

**From earlier roadmap:**
- Fix sensitivity_heatmap.py syntax (missing parens)
- Modernize type hints (Dict → dict)
- Run full test suite: pytest tests/ -v → 282+ passing

**Status:** Most likely already done by local dev, just verify:
```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
# Expected: "282 passed, 8 skipped"
```

---

### Phase 2: API Bridge (3 hours)

#### Task 2.1: Create FastAPI Router Scaffold [30 min]

**File:** `app/api/v1/routers/analysis.py` (NEW)

```python
"""
FastAPI router for sensitivity & Monte Carlo analysis.

Endpoints:
- POST /scenarios/{id}/monte-carlo
- POST /scenarios/{id}/sensitivity
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

from analytics.monte_carlo_v14 import run_monte_carlo
from analytics.sensitivity_v14 import run_tornado_sensitivity, SensitivityRequest
from analytics.contracts_v14 import ParameterRangeConfig

router = APIRouter(prefix="/api/v1", tags=["analysis"])
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# Request/Response Models (Pydantic v2)
# ─────────────────────────────────────────────────────────────────

class MonteCarloRequest(BaseModel):
    """Monte Carlo analysis request."""
    config_path: str = Field(..., description="Path to scenario config")
    n_iterations: int = Field(default=1000, ge=10, le=10000)
    random_seed: Optional[int] = None

class TornadoRequest(BaseModel):
    """Tornado sensitivity request."""
    config_path: str
    parameters: list[dict]  # From ParameterRangeConfig
    metric: str = "project_irr"

class APIResponse(BaseModel):
    """Standard API response."""
    status: str = "success"
    data: dict

# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.post("/scenarios/{scenario_id}/monte-carlo")
async def monte_carlo_analysis(scenario_id: str, request: MonteCarloRequest):
    """Run Monte Carlo analysis on a scenario."""
    try:
        result = run_monte_carlo(
            config_path=request.config_path,
            n_iterations=request.n_iterations,
            random_seed=request.random_seed,
        )
        return APIResponse(status="success", data=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"MC analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scenarios/{scenario_id}/sensitivity")
async def sensitivity_analysis(scenario_id: str, request: TornadoRequest):
    """Run tornado sensitivity analysis on a scenario."""
    try:
        # Convert request to SensitivityRequest
        params = [
            ParameterRangeConfig(**p) for p in request.parameters
        ]
        sensitivity_request = SensitivityRequest(
            base_config_path=request.config_path,
            parameters=params,
            metric=request.metric,
        )

        result = run_tornado_sensitivity(sensitivity_request)

        return APIResponse(
            status="success",
            data={
                "metric": request.metric,
                "results": [r.__dict__ for r in result.tornado_results],
            }
        )
    except Exception as e:
        logger.error(f"Sensitivity analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────
# Other endpoints (scaffold)
# ─────────────────────────────────────────────────────────────────

@router.get("/scenarios/{scenario_id}/timeseries")
async def get_timeseries(scenario_id: str):
    """Get annual cashflow timeseries."""
    # TODO: Implement
    pass

@router.get("/scenarios/{scenario_id}/covenants")
async def get_covenant_status(scenario_id: str):
    """Get covenant breach analysis."""
    # TODO: Implement
    pass

@router.post("/scenarios/{scenario_id}/export")
async def export_analysis(scenario_id: str, format: str = "excel"):
    """Export analysis to Excel/PDF."""
    # TODO: Implement
    pass
```

**Test:**
```bash
# Verify imports work
python -c "from app.api.v1.routers.analysis import router; print('✅ Router scaffold OK')"
```

---

#### Task 2.2: Implement /monte-carlo Endpoint [30 min]

**Update File:** `app/api/v1/routers/analysis.py`

**Enhancement:**
```python
@router.post("/scenarios/{scenario_id}/monte-carlo")
async def monte_carlo_analysis(scenario_id: str, request: MonteCarloRequest):
    """Run Monte Carlo analysis on a scenario."""
    try:
        logger.info(f"Starting MC analysis: {scenario_id}, {request.n_iterations} iterations")

        result = run_monte_carlo(
            config_path=request.config_path,
            n_iterations=request.n_iterations,
            random_seed=request.random_seed,
        )

        logger.info(f"MC analysis complete: {scenario_id}")
        return APIResponse(
            status="success",
            data=result,
        )
    except FileNotFoundError as e:
        logger.error(f"Config not found: {request.config_path}")
        raise HTTPException(status_code=404, detail=f"Config not found: {request.config_path}")
    except ValueError as e:
        logger.error(f"Invalid parameter: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"MC analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Test:**
```bash
# Use pytest + httpx
pytest tests/api/test_fastapi_monte_carlo.py -v
```

---

#### Task 2.3: Implement /sensitivity Endpoint [30 min]

**Update File:** `app/api/v1/routers/analysis.py`

**Same pattern as above** — wire SensitivityRequest to run_tornado_sensitivity()

---

#### Task 2.4: Wire Output Schemas (Pydantic v2) [30 min]

**File:** `app/schemas/analysis.py` (NEW)

```python
"""Response schemas for analysis endpoints (Pydantic v2)."""

from pydantic import BaseModel, Field
from typing import Optional

class DistributionStats(BaseModel):
    """Statistical distribution summary."""
    p10: float
    p50: float
    p90: float
    mean: float
    std: float

class ScenarioInfo(BaseModel):
    """Scenario metadata."""
    name: str
    description: Optional[str] = None
    source: str

class MonteCarloResponse(BaseModel):
    """MC analysis response."""
    status: str
    data: dict = Field(..., description="MC results with equity_irr, dscr_min, project_npv distributions")

class TornadoResponse(BaseModel):
    """Tornado analysis response."""
    status: str
    data: dict = Field(..., description="Tornado results with parameter rankings")
```

---

#### Task 2.5: Create API Integration Tests [30 min]

**File:** `tests/api/test_fastapi_endpoints.py` (NEW)

```python
"""Test FastAPI endpoints for analysis."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_monte_carlo_endpoint():
    """Test POST /scenarios/{id}/monte-carlo."""
    response = client.post(
        "/api/v1/scenarios/test_scenario/monte-carlo",
        json={
            "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
            "n_iterations": 100,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "equity_irr" in data["data"]
    assert "p50" in data["data"]["equity_irr"]

def test_sensitivity_endpoint():
    """Test POST /scenarios/{id}/sensitivity."""
    response = client.post(
        "/api/v1/scenarios/test_scenario/sensitivity",
        json={
            "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
            "parameters": [
                {
                    "variable_name": "project.capacity_factor_pct",
                    "base_value": 25.0,
                    "low_pct": -5.0,
                    "high_pct": 5.0,
                }
            ],
            "metric": "project_irr",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "results" in data["data"]
```

---

#### Task 2.6: Integration Test (API → MC → Cashflow) [30 min]

**File:** `tests/api/test_integration_api_to_cashflow.py` (NEW)

```python
"""End-to-end integration: API request → cashflow_v14."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_full_mc_flow():
    """Verify: API → FastAPI → Monte Carlo → run_v14_pipeline → cashflow_v14."""
    # 1. Make API request
    response = client.post(
        "/api/v1/scenarios/e2e_test/monte-carlo",
        json={
            "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
            "n_iterations": 50,  # Small for speed
        }
    )

    # 2. Verify response
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"

    # 3. Verify cashflow outputs are present
    assert "equity_irr" in result["data"]
    assert "dscr_min" in result["data"]
    assert "project_npv" in result["data"]

    # 4. Verify distributions
    equity_irr = result["data"]["equity_irr"]
    assert equity_irr["p10"] < equity_irr["p50"] < equity_irr["p90"]
    assert equity_irr["mean"] > 0

    print("✅ Full integration flow validated")
```

---

## 📊 FINAL VALIDATION MATRIX

| Component | Status | Test | Effort |
|-----------|--------|------|--------|
| **Cashflow_v14 modular refactor** | ✅ DONE | grep -r "cashflow_v14_" | 0h |
| **MC override mapping** | 🔄 VALIDATE | test_monte_carlo_override_mapping.py | 0.5h |
| **MC.to_api_dict()** | 🔄 ADD | test_scenario_to_api_dict | 0.25h |
| **MC convergence test** | 🔄 CREATE | test_monte_carlo_sensitivity_integration.py | 1h |
| **Sensitivity convergence** | ✅ EXISTS | existing tornado tests | 0h |
| **API router scaffold** | 🔄 CREATE | import test | 0.5h |
| **MC endpoint** | 🔄 IMPLEMENT | test_fastapi_monte_carlo.py | 0.5h |
| **Sensitivity endpoint** | 🔄 IMPLEMENT | test_fastapi_sensitivity.py | 0.5h |
| **Output schemas** | 🔄 CREATE | type validation | 0.5h |
| **E2E integration test** | 🔄 CREATE | test_integration_api_to_cashflow.py | 0.5h |

**Total:** 7 hours

---

## 🚀 RECOMMENDED EXECUTION

### For Parallel Execution (4 hours wall time)

```
Monday 8 AM
├─ Backend Engineer: Workstream 1 (Engine Polish, 4h)
│  └─ Tasks 1.1 - 1.4
└─ API Engineer: Workstream 2 (API Bridge, 3h)
   └─ Tasks 2.1 - 2.6

Monday 12 PM → Integration point
├─ Merge code
├─ Run full test suite (all 300+ tests)
└─ Validate API → Cashflow → MC flow

Monday 1 PM → Ready for deployment
```

### For Sequential Execution (7 hours wall time)

```
Monday 8 AM - 12 PM: Engine Polish (4h)
Monday 1 PM - 4 PM: API Bridge (3h)
Monday 5 PM: Deployment ready
```

---

## ✅ GO/NO-GO DECISION

**Before starting, confirm:**

- [ ] Cashflow_v14 modular refactor is 100% complete and tested
- [ ] Monte Carlo v14 currently uses run_v14_pipeline() (validate with grep)
- [ ] API Contract Specifications are finalized
- [ ] All 282+ existing tests pass locally

**If YES to all 4:** Proceed immediately 🚀

**If ANY NO:** Debug first (likely 0.5-1 hour additional work)

---

**Status: READY FOR PARALLEL IMPLEMENTATION** 🎯
