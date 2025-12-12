# 🔗 DutchBay EPC: UI/UX ↔ Backend Integration Strategy

**Comprehensive Pathway for Integrating DutchBay Design System with v14 Financial Engine**

**Status:** Production-Ready Integration Blueprint
**Date:** December 7, 2025
**Architecture:** 3-Layer Model (UI ↔ API ↔ Engine)

---

## 📊 Executive Summary

Your project has two perfectly complementary pieces:

1. **Design System** (Complete, production-ready UI specification)
   - 6 interactive screens, CSS tokens, component library, accessibility standards
   - Pure front-end (HTML/CSS/JS) with NO backend dependencies

2. **Financial Engine** (Complete, production-ready Python backend)
   - 261 files organized in modular Python packages
   - Multi-currency DCF model, IRR/NPV/DSCR calculations, sensitivity analysis
   - Scenario management, Monte Carlo, lender covenants, tax calculations

**Integration Task:** Build the API bridge that wires these together.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND LAYER (UI)                         │
│                     (Your Design System)                        │
│  Dashboard | Scenarios | Metrics | Reports | Settings          │
│  (Interactive HTML/CSS with components)                         │
└─────────────────────┬───────────────────────────────────────────┘
                      │ JSON/REST API
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                   API GATEWAY LAYER (FastAPI)                   │
│  /api/v1/projects    /api/v1/scenarios   /api/v1/analytics     │
│  /api/v1/export      /api/v1/covenants   /api/v1/calculate     │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Python function calls
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                 BACKEND ENGINE LAYER (Python)                   │
│  /finance       /analytics      /utils                          │
│  - cashflow_v14.py             - sensitivity_v14.py             │
│  - debt_v14.py                 - contracts_v14.py               │
│  - equity_v14.py               - monte_carlo_v14.py             │
│  - irr.py                       - scenario_analytics.py          │
│  - wacc_v14.py                 - export_helpers.py              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Codebase Index & Mapping

### A. BACKEND STRUCTURE (261 files, 2.0 MB)

#### Core Financial Engines (Read your code here ⭐)

| Module | Purpose | Key Functions | UI Integration |
|--------|---------|---|---|
| **finance/cashflow_v14.py** (51 KB) | Annual revenue, costs, tax, depreciation | `buildannualrows()` | Revenue chart, cost breakdown |
| **finance/debt_v14.py** (16 KB) | Debt drawdown, IDC, amortization, DSCR | `plandebt()` | Debt schedule, DSCR covenant |
| **finance/equity_v14.py** (13 KB) | Equity returns, MOIC, payback | `calculateequityperformance()` | Equity IRR card, payback period |
| **finance/irr.py** (12 KB) | NPV/IRR/XIRR solvers with bounds | `irr()`, `npv()`, `xirr()` | All KPI cards (NPV, IRR, DSCR) |
| **finance/wacc_v14.py** (20 KB) | CAPM, cost of debt/equity, WACC | `computewaccfromconfig()` | Discount rate, prudential bump |
| **finance/tax_v14.py** (3 KB) | Depreciation, tax shields, holiday | `calculatetaxseries()` | Tax impact in metrics detail |
| **finance/epc_helper_v14.py** (15 KB) | Capex breakdown, FX, contingency | `epcbreakdownfromconfig()` | Project assumptions |

#### Analytics Layer (Where scenarios come alive)

| Module | Purpose | Key Functions | UI Integration |
|--------|---------|---|---|
| **analytics/scenario_analytics.py** (21 KB) | Multi-scenario evaluation | `evaluatescenario()` | Scenario comparison cards |
| **analytics/sensitivity_v14.py** (38 KB) | Tornado charts, parameter ranges | `runsensitivity()` | Sensitivity tab, tornado chart |
| **analytics/monte_carlo_v14.py** (25 KB) | Stochastic risk analysis | `runnmontecarlo()` | Risk distribution, tail metrics |
| **analytics/contracts_v14.py** (34 KB) | Covenant monitoring, lender tests | `evaluatecovenant()` | Covenant status badges, alerts |
| **analytics/export_helpers.py** (26 KB) | Excel/CSV/JSON export | `toexcel()`, `tocsv()` | Report download buttons |
| **analytics/scenario_manager.py** (5 KB) | Scenario CRUD operations | `loadscenario()`, `savescenario()` | Scenario creation dialog |

#### Configuration & Schema

| Module | Purpose | UI Integration |
|--------|---------|---|
| **analytics/config_schema.py** | YAML validation | Settings screen validation |
| **analytics/scenario_loader.py** | Load YAML scenarios | Scenario selector |
| **analytics/schema_guard.py** | Data integrity checks | Input validation, error messages |

#### Data Contracts

| File | Purpose | UI Integration |
|------|---------|---|
| **analytics/contracts_v14.py** | Dataclass definitions for flows | TypeScript type generation |
| **scenarios/*.yaml** | Test/demo scenarios | Seed data, test fixtures |
| **config/*.yaml** | Default settings | Project defaults |

### B. FRONTEND STRUCTURE (Design System, 5 files)

| File | Purpose | Integration Point |
|------|---------|---|
| **DutchBay_Design_System.css** | Tokens, components, utilities | Apply to API response data |
| **DutchBay_Prototype.html** | 6 interactive screens | Shell for dynamic data binding |
| **README.md** | Component reference | Developer onboarding |
| **Figma_Component_Specs.md** | Layer specs, variants | Design-to-code handoff |
| **DutchBay_Figma_JSON.json** | Token metadata | Figma sync, documentation |

---

## 🎯 Best Pathways for Integration

### **PATHWAY 1: RECOMMENDED (Fastest to MVP) - FastAPI + JavaScript**

#### Tech Stack
```
Frontend:  HTML/CSS/JavaScript (vanilla or Preact)
API:       FastAPI (Python)
Deployment: Docker + AWS/GCP
Database:  PostgreSQL (optional, for scenario storage)
```

#### Data Flow

```
UI Form Input
    ↓
POST /api/v1/projects/{id}/run
    ↓
FastAPI receives + validates
    ↓
Call: finance.cashflow_v14.buildannualrows()
Call: finance.debt_v14.plandebt()
Call: analytics.contracts_v14.evaluatecovenant()
    ↓
Return: {
  "npv": 45.2M,
  "irr": 12.8%,
  "dscr": 1.45x,
  "chart_data": [...],
  "warnings": [...]
}
    ↓
Update UI components with data
```

#### Implementation Steps

**Phase 1: API Layer (2-3 days)**

```python
# main.py - FastAPI app
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json

app = FastAPI(title="DutchBay v14 API", version="1.0.0")

# ============================================================================
# REQUEST/RESPONSE MODELS (Pydantic)
# ============================================================================

class ProjectRunRequest(BaseModel):
    scenario_name: str = "basecase"
    config_path: str = "scenarios/dutchbay_master_config_v14.yaml"
    overrides: dict = {}

class ProjectMetrics(BaseModel):
    npv: float
    irr: float
    dscr_min: float
    revenue_total: float
    cost_total: float
    # ... add all KPIs

class APIResponse(BaseModel):
    status: str  # "success", "error"
    data: dict
    errors: list = []

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.post("/api/v1/projects/{project_id}/run")
async def run_project(project_id: str, request: ProjectRunRequest):
    """
    Run full financial model for project with given scenario.
    Maps directly to: run_full_pipeline_v14.py
    """
    try:
        from analytics.scenario_loader import loadscenario
        from analytics.evaluate_scenario import evaluatescenario

        # Load scenario config
        config = loadscenario(request.config_path)

        # Apply any overrides
        if request.overrides:
            config.update(request.overrides)

        # Run full pipeline
        result = evaluatescenario(config, scenario_name=request.scenario_name)

        # Convert to JSON-serializable format
        metrics = ProjectMetrics(
            npv=result.get('project_npv', 0),
            irr=result.get('project_irr', 0),
            dscr_min=result.get('dscr_min', 0),
            revenue_total=result.get('revenue_total', 0),
            cost_total=result.get('cost_total', 0)
        )

        return APIResponse(
            status="success",
            data=json.loads(metrics.model_dump_json())
        )

    except Exception as e:
        return APIResponse(
            status="error",
            data={},
            errors=[str(e)]
        )

@app.get("/api/v1/scenarios")
async def list_scenarios():
    """Get available scenarios."""
    from analytics.scenario_loader import list_available_scenarios
    scenarios = list_available_scenarios()
    return APIResponse(status="success", data={"scenarios": scenarios})

@app.post("/api/v1/scenarios/{scenario_id}/sensitivity")
async def run_sensitivity(scenario_id: str, request: SensitivityRequest):
    """Run tornado sensitivity analysis."""
    from analytics.sensitivity_v14 import run as run_sensitivity
    result = run_sensitivity(request)
    return APIResponse(status="success", data=result)

@app.post("/api/v1/projects/{project_id}/export")
async def export_project(project_id: str, format: str = "xlsx"):
    """Export results to Excel, CSV, or JSON."""
    from analytics.export_helpers import toexcel, tocsv, tojson

    if format == "xlsx":
        file_path = toexcel(project_data)
    elif format == "csv":
        file_path = tocsv(project_data)
    else:
        return APIResponse(status="error", data={}, errors=["Invalid format"])

    return FileResponse(file_path, media_type="application/octet-stream")
```

**Phase 2: Frontend Data Binding (2-3 days)**

```javascript
// dashboard.js - Wire design system to API
class DashboardController {
  constructor() {
    this.apiBase = 'http://localhost:8000/api/v1';
    this.projectId = 'dutchbay-150mw';
  }

  async initialize() {
    // Load project data on page load
    const response = await fetch(`${this.apiBase}/projects/${this.projectId}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_name: 'basecase',
        config_path: 'scenarios/dutchbay_master_config_v14.yaml'
      })
    });

    const result = await response.json();

    if (result.status === 'success') {
      this.updateDashboard(result.data);
    } else {
      this.showError(result.errors);
    }
  }

  updateDashboard(data) {
    // Update metric cards
    document.querySelector('[data-metric="npv"] .metric-value')
      .textContent = `$${(data.npv / 1e6).toFixed(1)}M`;

    document.querySelector('[data-metric="irr"] .metric-value')
      .textContent = `${(data.irr * 100).toFixed(1)}%`;

    document.querySelector('[data-metric="dscr"] .metric-value')
      .textContent = data.dscr_min.toFixed(2) + 'x';

    // Update chart
    if (data.chart_data) {
      this.updateChart(data.chart_data);
    }
  }

  async switchScenario(scenarioName) {
    const response = await fetch(`${this.apiBase}/projects/${this.projectId}/run`, {
      method: 'POST',
      body: JSON.stringify({ scenario_name: scenarioName })
    });

    const result = await response.json();
    this.updateDashboard(result.data);
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const dashboard = new DashboardController();
  dashboard.initialize();

  // Wire scenario selector
  document.querySelectorAll('.scenario-card').forEach(card => {
    card.addEventListener('click', (e) => {
      const scenarioId = e.currentTarget.dataset.scenario;
      dashboard.switchScenario(scenarioId);
    });
  });
});
```

**Phase 3: Deployment (1 day)**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Expose API
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Docker Compose for local dev
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - PYTHONUNBUFFERED=1

  frontend:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
```

---

### **PATHWAY 2: MODERN (React + TypeScript + GraphQL)**

For teams wanting type safety and modern tooling:

```
Frontend:  React 18 + TypeScript
API:       FastAPI + Strawberry GraphQL
State:     TanStack Query (data fetching) + Zustand (state)
Styling:   Your CSS system as Tailwind classes
```

#### Key differences from Pathway 1:

```typescript
// types.ts - Auto-generated from Python Pydantic models
export interface ProjectMetrics {
  npv: number;
  irr: number;
  dscr_min: number;
  // ... auto-generated from FastAPI schema
}

// hooks.ts - Data fetching patterns
export const useProjectMetrics = (projectId: string) => {
  return useQuery({
    queryKey: ['projects', projectId],
    queryFn: async () => {
      const response = await fetch(`/api/v1/projects/${projectId}/run`);
      return response.json();
    }
  });
};

// Dashboard.tsx - Component layer
export const Dashboard = ({ projectId }: { projectId: string }) => {
  const { data, isLoading, error } = useProjectMetrics(projectId);

  if (isLoading) return <LoadingSketch />;
  if (error) return <ErrorBoundary error={error} />;

  return (
    <div className="dashboard">
      <MetricCard label="NPV" value={data.npv} unit="M" />
      <MetricCard label="IRR" value={data.irr} unit="%" />
      <MetricCard label="DSCR" value={data.dscr_min} unit="x" />
    </div>
  );
};
```

---

### **PATHWAY 3: SERVERLESS (AWS Lambda + RDS)**

For scale without ops overhead:

```
Frontend:  S3 + CloudFront (static site)
API:       API Gateway + Lambda functions
Engine:    Docker container in Lambda (layer)
Database:  RDS PostgreSQL for scenario storage
```

Benefits: Auto-scaling, pay-per-use, no server management
Trade-off: Cold starts (mitigated with provisioned concurrency)

---

## 📋 Detailed Integration Checklist

### ✅ Step-by-Step Implementation

#### **Week 1: Foundation (API Layer)**

- [ ] **Day 1: Project Setup**
  - [ ] Create new directory: `dutchbay-api/`
  - [ ] Copy backend code: `finance/`, `analytics/`
  - [ ] Create `requirements.txt` with dependencies
  - [ ] Set up virtual environment: `python -m venv .venv311`
  - [ ] Install: `pip install fastapi uvicorn pydantic pyyaml`

- [ ] **Day 2: Core Endpoints**
  - [ ] Create `main.py` with FastAPI app skeleton
  - [ ] Implement `/api/v1/projects/{id}/run` endpoint
  - [ ] Map request → `evaluatescenario()` function
  - [ ] Define request/response Pydantic models
  - [ ] Add error handling middleware

- [ ] **Day 3: Additional Endpoints**
  - [ ] `/api/v1/scenarios` (list scenarios)
  - [ ] `/api/v1/scenarios/{id}/sensitivity` (tornado analysis)
  - [ ] `/api/v1/projects/{id}/export` (Excel/CSV/JSON)
  - [ ] `/api/v1/covenants/{id}` (covenant status)

- [ ] **Day 4: Testing**
  - [ ] Write unit tests for each endpoint
  - [ ] Test with Postman or Thunder Client
  - [ ] Validate Pydantic model serialization
  - [ ] Check error handling

- [ ] **Day 5: Documentation**
  - [ ] Generate OpenAPI/Swagger docs (automatic with FastAPI)
  - [ ] Write endpoint documentation
  - [ ] Create example curl requests

#### **Week 2: Frontend Integration (Data Binding)**

- [ ] **Day 6: HTML-to-API Wiring**
  - [ ] Update `DutchBay_Prototype.html`
  - [ ] Add JavaScript fetch handlers
  - [ ] Wire dashboard metrics to API
  - [ ] Handle API responses, errors, loading states

- [ ] **Day 7: Dynamic Components**
  - [ ] Scenario selector → switch scenarios
  - [ ] Form inputs → trigger calculations
  - [ ] Chart data binding (Chart.js or D3.js)
  - [ ] Real-time metric updates

- [ ] **Day 8: Reports & Export**
  - [ ] Download buttons → `/api/v1/projects/{id}/export`
  - [ ] Generate Excel with sensitivity analysis
  - [ ] Create markdown report generator

- [ ] **Day 9: Settings Screen**
  - [ ] Project assumptions form → YAML generator
  - [ ] Validate inputs against schema_guard
  - [ ] Save custom scenarios

- [ ] **Day 10: Integration Testing**
  - [ ] End-to-end test flows
  - [ ] Cross-browser testing
  - [ ] Mobile responsiveness

#### **Week 3: Deployment & Optimization**

- [ ] **Day 11: Containerization**
  - [ ] Create `Dockerfile` for API
  - [ ] Create `docker-compose.yml` for dev
  - [ ] Test locally with Docker

- [ ] **Day 12: Database (Optional)**
  - [ ] Set up PostgreSQL
  - [ ] Create scenario storage schema
  - [ ] Add SQLAlchemy ORM layer

- [ ] **Day 13: Performance**
  - [ ] Cache scenario results (Redis)
  - [ ] Optimize sensitivity analysis (batch jobs)
  - [ ] Profile API response times

- [ ] **Day 14: Deployment**
  - [ ] Deploy to AWS/GCP/DigitalOcean
  - [ ] Set up CI/CD pipeline (GitHub Actions)
  - [ ] Configure monitoring & alerting

- [ ] **Day 15: Documentation**
  - [ ] Write API documentation
  - [ ] Create deployment guide
  - [ ] Update README with setup instructions

---

## 🔐 Data Flow Examples

### Example 1: Dashboard Load

```
User opens: http://app.dutchbay.com/dashboard

→ Dashboard.tsx mounts
  → useProjectMetrics('dutchbay-150mw') hook fires
  → GET /api/v1/projects/dutchbay-150mw/current

FastAPI receives request
→ Loads config from scenarios/dutchbay_master_config_v14.yaml
→ Calls evaluatescenario(config, 'basecase')
  → buildannualrows(config)        // Annual P&L
  → plandebt(config, annual_rows)  // Debt schedule + DSCR
  → calculateequityperformance()   // Equity IRR + MOIC
  → evaluatecovenant()             // Covenant status

→ Returns JSON:
{
  "status": "success",
  "data": {
    "npv": 45200000,
    "irr": 0.128,
    "dscr_min": 1.45,
    "revenue_total": 128400000,
    "cost_total": 82100000,
    "chart": {
      "years": [2026, 2027, ...],
      "revenue": [60M, 64M, ...],
      "costs": [40M, 42M, ...]
    },
    "warnings": []
  }
}

→ UI updates:
  ✓ Metric cards (NPV, IRR, DSCR)
  ✓ Revenue/Cost chart
  ✓ Status table (all green)
```

### Example 2: Sensitivity Analysis

```
User clicks "Sensitivity" tab
→ SensitivityPage component mounts
  → POST /api/v1/scenarios/basecase/sensitivity
  → { "parameters": ["capacity_factor", "opex_usd", "tariff"], "ranges": {...} }

FastAPI receives request
→ Gets scenario config
→ Calls sensitivity_v14.runsensitivity()
  → For each parameter variation:
    → Recalculate equity IRR
    → Store result with parameter value
  → Compile tornado chart data

→ Returns JSON:
{
  "tornado": [
    { "parameter": "tariff_lkr", "down": -0.05, "up": 0.08 },
    { "parameter": "opex_usd", "down": -0.03, "up": 0.04 },
    ...
  ],
  "base_irr": 0.128
}

→ UI renders tornado chart using Chart.js
```

### Example 3: Custom Scenario Creation

```
User clicks "Create Scenario"
→ Modal opens with form fields:
  - Capacity Factor
  - CAPEX USD
  - Debt Ratio
  - Interest Rate
  - Tariff LKR/kWh

User submits
→ POST /api/v1/scenarios
  {
    "name": "my_custom_scenario",
    "base_scenario": "basecase",
    "overrides": {
      "project.capacityfactor": 0.38,
      "debt.leverageratio": 0.65,
      ...
    }
  }

FastAPI receives request
→ Validates against schema_guard.validateconfigforv14()
→ If valid:
  ✓ Loads base scenario config
  ✓ Applies overrides
  ✓ Runs evaluatescenario() with new config
  ✓ Saves scenario to scenarios/my_custom_scenario.yaml
  ✓ Returns results

→ UI updates:
  ✓ Scenario appears in selector
  ✓ Shows metrics
  ✓ Allows comparison with base case
```

---

## 🛠️ Key Integration Patterns

### Pattern 1: Request Validation (FastAPI + Pydantic)

```python
from pydantic import BaseModel, field_validator

class ScenarioRequest(BaseModel):
    capacity_factor: float  # Must be 0.0-1.0
    opex_usd: float         # Must be positive
    tariff_lkr: float       # Must be positive

    @field_validator('capacity_factor')
    @classmethod
    def validate_cf(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Capacity factor must be 0-100%')
        return v

    @field_validator('opex_usd', 'tariff_lkr')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('Must be positive')
        return v
```

### Pattern 2: Error Handling (Consistent Across Stack)

```python
# API layer - catches all exceptions, returns consistent format
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return APIResponse(
        status="error",
        data={},
        errors=[{
            "code": type(exc).__name__,
            "message": str(exc),
            "path": str(request.url)
        }]
    )

# Frontend - handles all API errors uniformly
const handleApiError = (error) => {
  if (error.status === 'error') {
    error.errors.forEach(err => {
      showToast({
        type: 'error',
        title: err.code,
        message: err.message
      });
    });
  }
};
```

### Pattern 3: Caching Layer (For Performance)

```python
from functools import lru_cache
import redis

cache = redis.Redis(host='localhost', port=6379)

@app.post("/api/v1/projects/{project_id}/run")
async def run_project(project_id: str, request: ProjectRunRequest):
    # Check cache first
    cache_key = f"project:{project_id}:{request.scenario_name}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # Run calculation if not cached
    result = evaluatescenario(...)

    # Cache for 1 hour
    cache.setex(cache_key, 3600, json.dumps(result))

    return APIResponse(status="success", data=result)
```

---

## 🎯 UI Components ↔ Backend Functions Matrix

| UI Component | API Endpoint | Backend Function | Data Contract |
|---|---|---|---|
| **Metric Cards (NPV/IRR/DSCR)** | `POST /projects/{id}/run` | `evaluatescenario()` | `ProjectMetrics` |
| **Revenue Chart** | `POST /projects/{id}/run` | `buildannualrows()` | `AnnualRow[]` |
| **Debt Schedule Table** | `GET /projects/{id}/debt` | `plandebt()` | `DebtSchedule` |
| **Covenant Status** | `GET /projects/{id}/covenants` | `evaluatecovenant()` | `CovenantStatus` |
| **Sensitivity Tornado** | `POST /scenarios/{id}/sensitivity` | `sensitivity_v14.run()` | `TornadoResult` |
| **Monte Carlo Distribution** | `POST /scenarios/{id}/monte-carlo` | `monte_carlo_v14.run()` | `MonteCarloResult` |
| **Tax Breakdown** | `GET /projects/{id}/tax` | `calculatetaxseries()` | `TaxSchedule` |
| **Scenario Comparison** | `GET /scenarios/compare` | `scenario_analytics.compare()` | `ScenarioComparison` |
| **Export to Excel** | `POST /projects/{id}/export?format=xlsx` | `export_helpers.toexcel()` | File download |
| **Project Settings Form** | `PUT /projects/{id}/settings` | `scenario_loader.savescenario()` | `ProjectConfig` |

---

## 📊 Data Structures for API Response

### Core Financial Metrics

```python
@dataclass
class FinancialMetrics:
    # Project-level metrics
    project_npv: float          # USD
    project_irr: float          # Decimal (0.128 = 12.8%)
    project_pi: float           # Profitability index

    # Equity investor metrics
    equity_npv: float           # USD
    equity_irr: float           # Decimal
    equity_moic: float          # Multiple on invested capital
    equity_irr_lower: float     # For risk bounds
    equity_irr_upper: float

    # Debt metrics
    dscr_min: float             # Min DSCR over period
    dscr_avg: float             # Average DSCR
    llcr: float                 # Loan life coverage ratio
    plcr: float                 # Project life coverage ratio

    # Time series (for charts)
    annual_revenue: List[float]
    annual_opex: List[float]
    annual_ebitda: List[float]
    annual_debt_service: List[float]
    annual_dscr: List[float]

    # Status
    covenant_compliant: bool
    warnings: List[str]
```

### Scenario Comparison

```python
@dataclass
class ScenarioComparison:
    base_case: ProjectMetrics
    optimistic: ProjectMetrics
    conservative: ProjectMetrics
    pe_case: ProjectMetrics
    hybrid: ProjectMetrics

    comparisons: Dict[str, Dict[str, float]]  # Relative deltas
```

---

## 🚀 Optimization Tips

### 1. Batch Processing (For Heavy Calculations)

```python
# Instead of running sensitivity one param at a time:
# UI → POST /scenarios/batch-sensitivity
# {
#   "parameters": [...],
#   "samples": 100
# }
# → Runs in background job, returns job_id
# → UI polls GET /jobs/{job_id} for status
# → When complete, results available at GET /jobs/{job_id}/results
```

### 2. Streaming Large Exports

```python
# For large Excel files, stream the response:
@app.get("/projects/{id}/export/stream")
async def export_stream(id: str):
    def generate():
        for chunk in export_generator(id):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
```

### 3. Lazy Loading (UI Performance)

```javascript
// Load metrics only when tab is active
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      fetchMetricsForTab(entry.target.dataset.tab);
    }
  });
});

document.querySelectorAll('.tab-panel').forEach(el => {
  observer.observe(el);
});
```

---

## 📚 Testing Strategy

### 1. Unit Tests (Backend)

```python
# tests/api/test_endpoints.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_run_project():
    response = client.post(
        "/api/v1/projects/test/run",
        json={"scenario_name": "basecase"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "data" in response.json()

def test_invalid_scenario():
    response = client.post(
        "/api/v1/projects/test/run",
        json={"scenario_name": "nonexistent"}
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"
```

### 2. Integration Tests (End-to-End)

```javascript
// tests/integration/dashboard.test.js
describe('Dashboard Integration', () => {
  it('loads metrics from API and updates UI', async () => {
    // Mock API response
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({
          status: 'success',
          data: {
            npv: 45200000,
            irr: 0.128
          }
        })
      })
    );

    // Render dashboard
    const dashboard = new DashboardController();
    await dashboard.initialize();

    // Verify UI was updated
    const npvCard = document.querySelector('[data-metric="npv"]');
    expect(npvCard.textContent).toContain('45.2M');
  });
});
```

---

## 🎓 Developer Onboarding

### New Team Member Checklist

1. **Environment Setup** (30 min)
   - [ ] Clone repo
   - [ ] Create venv: `python -m venv .venv311`
   - [ ] Install deps: `pip install -r requirements.txt`
   - [ ] Install dev deps: `pip install -r requirements_dev.txt`

2. **Understand the Architecture** (1 hour)
   - [ ] Read this document (you are here!)
   - [ ] Look at `finance/cashflow_v14.py` - understand the data model
   - [ ] Look at `analytics/scenario_analytics.py` - understand orchestration
   - [ ] Skim `finance/irr.py` - understand financial calculations

3. **Run Locally** (1 hour)
   - [ ] Start API: `uvicorn main:app --reload`
   - [ ] Open Swagger docs: `http://localhost:8000/docs`
   - [ ] Try POST `/api/v1/projects/test/run`
   - [ ] Open frontend: `http://localhost:8000/static/index.html`

4. **Make First Change** (2 hours)
   - [ ] Add a new metric endpoint: `/api/v1/projects/{id}/payback`
   - [ ] Wire it to frontend
   - [ ] Add to Settings screen

---

## 🔗 Cross-Reference Map

**If you want to...** → **Look at these files:**

| Task | Files |
|------|-------|
| Add a new KPI metric | `finance/equityv14.py` + `analytics/core/metrics.py` + API endpoint |
| Change DSCR calculation | `finance/debtv14.py` → `plandebt()` function |
| Add sensitivity parameter | `analytics/contracts_v14.py` + `scenarios/sensitivity_defaults.yaml` |
| Modify UI colors | `DutchBay_Design_System.css` (--color-* variables) |
| Change scenario structure | `analytics/config_schema.py` + validation schema |
| Add new export format | `analytics/export_helpers.py` + new format function |
| Modify tax calculation | `finance/tax_v14.py` → `TaxCalculatorV14` class |
| Add Monte Carlo scenario | `analytics/monte_carlo_v14.py` + stochastic setup |

---

## ✅ Success Criteria

By end of implementation:

- [ ] API responds to dashboard load in <500ms (excluding cold start)
- [ ] Sensitivity analysis completes in <5 seconds
- [ ] All 6 UI screens display correct data
- [ ] User can create custom scenario and see results
- [ ] Excel export contains all calculations
- [ ] Covenant breaches highlighted in UI with explanation
- [ ] Mobile responsive (tablet view working)
- [ ] Deployed to staging environment
- [ ] Team can onboard new dev in <2 hours

---

## 🤝 Handoff Checklist

**Before going to production:**

- [ ] All unit tests passing (pytest)
- [ ] All integration tests passing (API + UI)
- [ ] API documented (FastAPI auto-docs + custom README)
- [ ] Frontend documented (component guide + usage examples)
- [ ] Security review (CORS, rate limiting, auth if needed)
- [ ] Performance baseline established (load tests)
- [ ] Monitoring & alerting configured
- [ ] Disaster recovery plan (backup scenarios, DB recovery)
- [ ] User documentation (how to use each screen)
- [ ] Training video for business users (10 min)

---

## 🎯 Next Steps

### Immediately (Today)

1. **Review this document** with your team
2. **Assess your tech preferences**:
   - Pathway 1 (FastAPI + Vanilla JS)? → Start with `main.py` skeleton
   - Pathway 2 (React + TypeScript)? → Set up Create React App + TypeScript
   - Pathway 3 (Serverless)? → Set up AWS Lambda layer

3. **Assign team roles**:
   - Backend engineer → APIs, FastAPI
   - Frontend engineer → HTML/CSS wiring, JavaScript
   - DevOps → Docker, deployment pipeline

### This Week

- [ ] Set up dev environment (all team members)
- [ ] Create API endpoint skeleton
- [ ] Wire first metric to dashboard
- [ ] Deploy to staging

### This Month

- [ ] Complete all 6 screens
- [ ] Production deployment
- [ ] User training

---

**Questions?** Refer to specific sections above or consult the codebase directly.

**Good luck! 🚀**
