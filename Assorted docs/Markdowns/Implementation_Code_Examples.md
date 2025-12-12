# 💻 Implementation Code Examples

**Ready-to-Use Code Snippets for DutchBay Integration**

---

## 1. FastAPI Application Skeleton

```python
# main.py - FastAPI application entry point
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DutchBay EPC API",
    description="Financial modeling API for renewable energy projects",
    version="1.0.0"
)

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProjectRunRequest(BaseModel):
    """Request to run financial model for a scenario."""
    scenario_name: str = "basecase"
    config_path: str = "scenarios/dutchbay_master_config_v14.yaml"
    overrides: Optional[Dict[str, Any]] = None
    include_sensitivity: bool = False

    @field_validator('scenario_name')
    @classmethod
    def validate_scenario_name(cls, v):
        if not v or len(v) < 1:
            raise ValueError('Scenario name required')
        return v

class ProjectMetricsResponse(BaseModel):
    """Financial metrics for a project."""
    npv_usd: float
    irr: float
    pi: float
    dscr_min: float
    equity_irr: float
    equity_moic: float
    capex_total_usd: float

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    status: str  # "success" or "error"
    data: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return APIResponse(status="success", data={"message": "API is running"})

@app.post("/api/v1/projects/{project_id}/run")
async def run_project(project_id: str, request: ProjectRunRequest):
    """
    Run full financial model for a project scenario.

    Args:
        project_id: Project identifier (e.g., "dutchbay-150mw")
        request: ProjectRunRequest with scenario config

    Returns:
        APIResponse with project metrics and timeseries data
    """
    try:
        logger.info(f"Running project {project_id} with scenario {request.scenario_name}")

        # Import backend modules (lazy import for performance)
        from analytics.scenario_loader import loadscenario
        from analytics.evaluate_scenario import evaluatescenario

        # Load scenario configuration
        config = loadscenario(request.config_path)

        # Apply any parameter overrides from request
        if request.overrides:
            logger.info(f"Applying {len(request.overrides)} overrides to config")
            _apply_overrides_to_config(config, request.overrides)

        # Run financial model
        result = evaluatescenario(config, scenario_name=request.scenario_name)

        # Convert result to JSON-serializable format
        response_data = {
            "project_id": project_id,
            "scenario": request.scenario_name,
            "project_metrics": {
                "npv_usd": float(result.get('project_npv', 0)),
                "irr": float(result.get('project_irr', 0)),
                "pi": float(result.get('pi', 0)),
                "dscr_min": float(result.get('dscr_min', 1.0)),
                "equity_irr": float(result.get('equity_irr', 0)),
                "equity_moic": float(result.get('equity_moic', 0)),
                "capex_total_usd": float(result.get('capex_total', 0))
            },
            "timeseries": {
                "years": result.get('years', []),
                "revenue_usd": [float(x) for x in result.get('revenue', [])],
                "opex_usd": [float(x) for x in result.get('opex', [])],
                "dscr": [float(x) for x in result.get('dscr', [])]
            },
            "calculation_time_ms": result.get('calculation_time_ms', 0),
            "warnings": result.get('warnings', [])
        }

        logger.info(f"Calculation complete: IRR={response_data['project_metrics']['irr']:.1%}")

        return APIResponse(status="success", data=response_data)

    except FileNotFoundError as e:
        logger.error(f"Config file not found: {e}")
        return APIResponse(
            status="error",
            data={},
            errors=[{"code": "FILE_NOT_FOUND", "message": str(e)}]
        )
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return APIResponse(
            status="error",
            data={},
            errors=[{"code": "VALIDATION_ERROR", "message": str(e)}]
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return APIResponse(
            status="error",
            data={},
            errors=[{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}]
        )

@app.get("/api/v1/scenarios")
async def list_scenarios():
    """Get available scenarios."""
    try:
        from analytics.scenario_loader import list_available_scenarios
        scenarios = list_available_scenarios()
        return APIResponse(status="success", data={"scenarios": scenarios})
    except Exception as e:
        return APIResponse(status="error", data={}, errors=[{"message": str(e)}])

@app.post("/api/v1/scenarios/{scenario_id}/sensitivity")
async def run_sensitivity(scenario_id: str):
    """Run sensitivity analysis for a scenario."""
    try:
        from analytics.sensitivity_v14 import run as run_sensitivity
        from analytics.scenario_loader import loadscenario

        config = loadscenario(f"scenarios/{scenario_id}.yaml")
        result = run_sensitivity(config, metric="equity_irr")

        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", data={}, errors=[{"message": str(e)}])

@app.get("/api/v1/projects/{project_id}/covenants")
async def get_covenants(project_id: str):
    """Check covenant compliance for a project."""
    try:
        from analytics.contracts_v14 import evaluate_covenants
        from analytics.scenario_loader import loadscenario

        config = loadscenario("scenarios/dutchbay_master_config_v14.yaml")
        result = evaluate_covenants(config)

        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", data={}, errors=[{"message": str(e)}])

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _apply_overrides_to_config(config: dict, overrides: dict) -> None:
    """
    Apply parameter overrides to configuration using dot notation.

    Example: {"project.capacityfactor": 0.40} updates config['project']['capacityfactor']
    """
    for key_path, value in overrides.items():
        keys = key_path.split('.')
        current = config

        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set value
        current[keys[-1]] = value

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload in development
        log_level="info"
    )
```

---

## 2. Frontend Data Binding (Vanilla JavaScript)

```javascript
// dashboard.js - Wire design system to backend API

class DashboardController {
  constructor() {
    this.apiBase = 'http://localhost:8000/api/v1';
    this.projectId = 'dutchbay-150mw';
    this.currentScenario = 'basecase';
    this.metrics = {};
  }

  // ============================================================================
  // INITIALIZATION
  // ============================================================================

  async initialize() {
    console.log('[Dashboard] Initializing...');

    try {
      // Load initial data
      await this.loadProjectMetrics();

      // Bind event listeners
      this.bindEventListeners();

      console.log('[Dashboard] Initialization complete');
    } catch (error) {
      console.error('[Dashboard] Initialization failed:', error);
      this.showError('Failed to initialize dashboard');
    }
  }

  // ============================================================================
  // DATA LOADING
  // ============================================================================

  async loadProjectMetrics() {
    console.log('[API] Fetching metrics for scenario:', this.currentScenario);

    try {
      const response = await fetch(`${this.apiBase}/projects/${this.projectId}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          scenario_name: this.currentScenario,
          config_path: 'scenarios/dutchbay_master_config_v14.yaml'
        })
      });

      const result = await response.json();

      if (result.status === 'success') {
        this.metrics = result.data;
        this.updateDashboard(this.metrics);
        this.showSuccess(`Loaded ${this.currentScenario} scenario`);
      } else {
        this.showError(result.errors[0]?.message || 'Unknown error');
      }
    } catch (error) {
      console.error('[API] Request failed:', error);
      this.showError('Failed to fetch metrics: ' + error.message);
    }
  }

  async loadSensitivityAnalysis() {
    console.log('[API] Running sensitivity analysis...');

    try {
      const response = await fetch(
        `${this.apiBase}/scenarios/${this.currentScenario}/sensitivity`,
        { method: 'POST' }
      );

      const result = await response.json();

      if (result.status === 'success') {
        this.updateTornadoChart(result.data);
        console.log('[Dashboard] Sensitivity analysis complete');
      } else {
        this.showError('Sensitivity analysis failed');
      }
    } catch (error) {
      console.error('[API] Sensitivity request failed:', error);
    }
  }

  async loadCovenantStatus() {
    console.log('[API] Checking covenant compliance...');

    try {
      const response = await fetch(
        `${this.apiBase}/projects/${this.projectId}/covenants`,
        { method: 'GET' }
      );

      const result = await response.json();

      if (result.status === 'success') {
        this.updateCovenantStatus(result.data);
      }
    } catch (error) {
      console.error('[API] Covenant check failed:', error);
    }
  }

  // ============================================================================
  // UI UPDATES
  // ============================================================================

  updateDashboard(data) {
    console.log('[Dashboard] Updating UI with new metrics');

    // Update metric cards
    this.updateMetricCard('npv', data.project_metrics.npv_usd, 'USD');
    this.updateMetricCard('irr', data.project_metrics.irr * 100, '%');
    this.updateMetricCard('dscr', data.project_metrics.dscr_min, 'x');
    this.updateMetricCard('equity-irr', data.project_metrics.equity_irr * 100, '%');

    // Update timeseries chart
    if (data.timeseries) {
      this.updateChart(data.timeseries);
    }

    // Update calculation timestamp
    const timestamp = new Date().toLocaleTimeString();
    document.querySelector('[data-timestamp]').textContent = timestamp;
  }

  updateMetricCard(metricId, value, unit) {
    const card = document.querySelector(`[data-metric="${metricId}"]`);
    if (!card) return;

    const valueElement = card.querySelector('.metric-value');
    const unitElement = card.querySelector('.metric-unit');

    if (valueElement) {
      // Format value based on unit
      if (unit === 'USD') {
        valueElement.textContent = `$${(value / 1e6).toFixed(1)}M`;
      } else if (unit === '%') {
        valueElement.textContent = value.toFixed(1);
      } else {
        valueElement.textContent = value.toFixed(2);
      }
    }

    if (unitElement) {
      unitElement.textContent = unit;
    }
  }

  updateChart(timeseries) {
    // Example: Using Chart.js if available
    const canvas = document.getElementById('revenue-cost-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Destroy existing chart if it exists
    if (window.revenueChart) {
      window.revenueChart.destroy();
    }

    // Create new chart
    window.revenueChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: timeseries.years,
        datasets: [
          {
            label: 'Revenue',
            data: timeseries.revenue_usd.map(v => v / 1e6),
            borderColor: 'rgb(45, 166, 178)',
            backgroundColor: 'rgba(45, 166, 178, 0.1)',
            tension: 0.3
          },
          {
            label: 'OPEX',
            data: timeseries.opex_usd.map(v => v / 1e6),
            borderColor: 'rgb(255, 84, 89)',
            backgroundColor: 'rgba(255, 84, 89, 0.1)',
            tension: 0.3
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top' },
          title: { display: true, text: 'Annual Revenue vs OPEX' }
        },
        scales: {
          y: {
            title: { display: true, text: 'USD Millions' }
          }
        }
      }
    });
  }

  updateCovenantStatus(covenants) {
    const container = document.querySelector('[data-covenant-status]');
    if (!container) return;

    const html = covenants.covenants.map(cov => `
      <div class="covenant-item ${cov.status.toLowerCase()}">
        <div class="covenant-name">${cov.name}</div>
        <div class="covenant-value">${cov.actual.toFixed(2)}</div>
        <div class="covenant-threshold">(Min: ${cov.threshold.toFixed(2)})</div>
        <div class="covenant-status ${cov.status}">${cov.status}</div>
      </div>
    `).join('');

    container.innerHTML = html;
  }

  // ============================================================================
  // EVENT HANDLERS
  // ============================================================================

  bindEventListeners() {
    // Scenario selector
    document.querySelectorAll('[data-scenario-btn]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        this.switchScenario(e.target.dataset.scenarioBtn);
      });
    });

    // Refresh button
    document.querySelector('[data-refresh-btn]')?.addEventListener('click', () => {
      this.loadProjectMetrics();
    });

    // Tab switcher
    document.querySelectorAll('[data-tab]').forEach(tab => {
      tab.addEventListener('click', (e) => {
        const tabName = e.target.dataset.tab;
        this.switchTab(tabName);
      });
    });
  }

  async switchScenario(scenarioName) {
    console.log('[Dashboard] Switching to scenario:', scenarioName);
    this.currentScenario = scenarioName;
    await this.loadProjectMetrics();
  }

  switchTab(tabName) {
    console.log('[Dashboard] Switching to tab:', tabName);

    // Hide all panels
    document.querySelectorAll('[data-panel]').forEach(p => {
      p.style.display = 'none';
    });

    // Show selected panel
    document.querySelector(`[data-panel="${tabName}"]`).style.display = 'block';

    // Load data for tab if needed
    if (tabName === 'sensitivity') {
      this.loadSensitivityAnalysis();
    } else if (tabName === 'covenants') {
      this.loadCovenantStatus();
    }
  }

  // ============================================================================
  // NOTIFICATIONS
  // ============================================================================

  showSuccess(message) {
    console.log('[Notification] Success:', message);
    this.showToast({ type: 'success', message });
  }

  showError(message) {
    console.error('[Notification] Error:', message);
    this.showToast({ type: 'error', message });
  }

  showToast(options) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${options.type}`;
    toast.textContent = options.message;
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      padding: 16px;
      background: ${options.type === 'error' ? '#ff5459' : '#2da6b2'};
      color: white;
      border-radius: 8px;
      z-index: 1000;
    `;

    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 4000);
  }
}

// ============================================================================
// INITIALIZE ON PAGE LOAD
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  window.dashboard = new DashboardController();
  window.dashboard.initialize();
});
```

---

## 3. HTML Integration (Within Prototype)

```html
<!-- Add to DutchBay_Prototype.html before closing </body> -->

<!-- Metric Cards Container -->
<div class="metrics-grid">
  <div class="metric-card" data-metric="npv">
    <div class="metric-label">NPV (USD)</div>
    <div class="metric-value">$45.2M</div>
    <div class="metric-unit">USD</div>
  </div>

  <div class="metric-card" data-metric="irr">
    <div class="metric-label">Project IRR</div>
    <div class="metric-value">12.8%</div>
    <div class="metric-unit">%</div>
  </div>

  <div class="metric-card" data-metric="dscr">
    <div class="metric-label">Min DSCR</div>
    <div class="metric-value">1.45x</div>
    <div class="metric-unit">x</div>
  </div>

  <div class="metric-card" data-metric="equity-irr">
    <div class="metric-label">Equity IRR</div>
    <div class="metric-value">18.5%</div>
    <div class="metric-unit">%</div>
  </div>
</div>

<!-- Scenario Selector -->
<div class="scenario-selector">
  <button data-scenario-btn="basecase" class="btn btn-primary">Base Case</button>
  <button data-scenario-btn="optimisticwind" class="btn btn-secondary">Optimistic</button>
  <button data-scenario-btn="conservativewind" class="btn btn-secondary">Conservative</button>
  <button data-scenario-btn="pe_case" class="btn btn-secondary">PE Case</button>
</div>

<!-- Chart Container -->
<div class="chart-container">
  <canvas id="revenue-cost-chart"></canvas>
</div>

<!-- Covenant Status -->
<div class="covenant-status" data-covenant-status>
  <!-- Populated by JavaScript -->
</div>

<!-- Last Updated Timestamp -->
<div class="metadata">
  <small>Last updated: <span data-timestamp>-</span></small>
</div>

<!-- Include dependencies -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
<script src="dashboard.js"></script>
```

---

## 4. Docker Configuration

```dockerfile
# Dockerfile for DutchBay API

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml for local development

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
      - ENV=development
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - api

  # Optional: PostgreSQL for scenario storage
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: dutchbay
      POSTGRES_USER: dutchbay
      POSTGRES_PASSWORD: changeme
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## 5. Testing Template

```python
# tests/test_api.py - Unit tests for API endpoints

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestProjectEndpoints:
    """Test project calculation endpoints."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_run_project_success(self):
        """Test successful project run."""
        response = client.post(
            "/api/v1/projects/dutchbay-150mw/run",
            json={"scenario_name": "basecase"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "project_metrics" in data["data"]
        assert data["data"]["project_metrics"]["irr"] > 0

    def test_run_project_with_overrides(self):
        """Test project run with parameter overrides."""
        response = client.post(
            "/api/v1/projects/dutchbay-150mw/run",
            json={
                "scenario_name": "basecase",
                "overrides": {
                    "project.capacityfactor": 0.35
                }
            }
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_invalid_scenario(self):
        """Test handling of invalid scenario."""
        response = client.post(
            "/api/v1/projects/test/run",
            json={"scenario_name": "nonexistent"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert len(data["errors"]) > 0

class TestSensitivityEndpoints:
    """Test sensitivity analysis endpoints."""

    def test_list_scenarios(self):
        """Test scenario listing."""
        response = client.get("/api/v1/scenarios")

        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data["data"]
        assert len(data["data"]["scenarios"]) > 0

    def test_sensitivity_analysis(self):
        """Test sensitivity analysis."""
        response = client.post(
            "/api/v1/scenarios/basecase/sensitivity"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
```

---

**End of Code Examples**

Ready to copy-paste and customize for your project! 🚀
