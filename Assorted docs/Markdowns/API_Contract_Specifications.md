# 🔌 API Contract Specifications & Data Schemas

**Technical Interface Definitions for DutchBay UI-Backend Integration**

---

## 1. Core API Endpoints

### 1.1 Project Operations

#### GET `/api/v1/projects/{project_id}`
**Purpose:** Fetch current project configuration and metrics.

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "dutchbay-150mw",
    "name": "DutchBay 150MW Wind Project",
    "description": "Wind energy project with DFI financing",
    "current_scenario": "basecase",
    "scenarios_available": ["basecase", "optimistic", "conservative", "pe_case"],
    "last_updated": "2025-12-07T11:20:22Z",
    "financial_metrics": {
      "project_npv_usd": 45200000,
      "project_irr": 0.128,
      "equity_irr": 0.185,
      "dscr_min": 1.45,
      "llcr": 2.35,
      "capex_total_usd": 250000000,
      "capex_total_lkr": 93750000000
    }
  }
}
```

---

#### POST `/api/v1/projects/{project_id}/run`
**Purpose:** Execute full financial model for a project and scenario.

**Request:**
```json
{
  "scenario_name": "basecase",
  "config_path": "scenarios/dutchbay_master_config_v14.yaml",
  "overrides": {
    "project.capacityfactor": 0.40,
    "debt.leverageratio": 0.70,
    "tariff.lkrperkwh": 20.3
  },
  "include_sensit": false
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "scenario": {
      "name": "basecase",
      "description": "Base case with P75 wind resource"
    },
    "project_metrics": {
      "npv_usd": 45.2e6,
      "irr": 0.128,
      "pi": 1.42,
      "payback_years": 8.5
    },
    "equity_metrics": {
      "npv_usd": 18.4e6,
      "irr": 0.185,
      "moic": 3.2,
      "payback_years": 7.2
    },
    "debt_metrics": {
      "dscr_min": 1.45,
      "dscr_avg": 1.67,
      "llcr": 2.35,
      "plcr": 3.12,
      "covenant_compliant": true
    },
    "timeseries": {
      "years": [2026, 2027, 2028, ...],
      "revenue_usd": [60.2e6, 64.5e6, ...],
      "opex_usd": [6.2e6, 6.4e6, ...],
      "cfads_usd": [54e6, 58.1e6, ...],
      "debt_service_usd": [37.2e6, 37.2e6, ...],
      "dscr": [1.45, 1.56, ...]
    },
    "warnings": [],
    "calculation_time_ms": 245
  }
}
```

---

#### PUT `/api/v1/projects/{project_id}/settings`
**Purpose:** Update project assumptions and configuration.

**Request:**
```json
{
  "project": {
    "capacitymw": 150,
    "capacityfactor": 0.40,
    "degradation": 0.006,
    "projectlifeyears": 25
  },
  "capex": {
    "usdtotal": 250000000,
    "freightpct": 0.05,
    "contingencypct": 0.10
  },
  "financing": {
    "debtratio": 0.70,
    "interestrate": 0.075,
    "tenoryears": 15,
    "graceyears": 3
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "message": "Project settings updated",
    "validation_errors": [],
    "validation_warnings": ["CAPEX contingency >10% is aggressive"],
    "updated_metrics": {
      "project_irr": 0.128,
      "equity_irr": 0.185
    }
  }
}
```

---

### 1.2 Scenario Operations

#### GET `/api/v1/scenarios`
**Purpose:** List all available scenarios.

**Response:**
```json
{
  "status": "success",
  "data": {
    "scenarios": [
      {
        "id": "basecase",
        "name": "DutchBay Base Case",
        "description": "P75 wind resource with standard DFI financing",
        "resource_assumption": "P75 wind, 3% annual degradation",
        "financing_type": "DFI-led",
        "key_metrics": {
          "equity_irr": 0.185,
          "dscr_min": 1.45
        }
      },
      {
        "id": "optimisticwind",
        "name": "DutchBay Optimistic",
        "description": "P50 wind resource with better wind profile",
        "key_metrics": {
          "equity_irr": 0.215,
          "dscr_min": 1.67
        }
      },
      {
        "id": "conservativewind",
        "name": "DutchBay Conservative",
        "description": "P90 conservative with stress test",
        "key_metrics": {
          "equity_irr": 0.145,
          "dscr_min": 1.21
        }
      }
    ]
  }
}
```

---

#### POST `/api/v1/scenarios`
**Purpose:** Create a new custom scenario.

**Request:**
```json
{
  "name": "custom_low_tariff",
  "base_scenario": "basecase",
  "overrides": {
    "tariff.lkrperkwh": 18.5,
    "project.degradation": 0.008,
    "debt.leverageratio": 0.65
  },
  "description": "Lower tariff scenario for sensitivity",
  "save_to_file": true
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "scenario_id": "custom_low_tariff",
    "metrics": {
      "project_irr": 0.098,
      "equity_irr": 0.155,
      "dscr_min": 1.28
    },
    "file_path": "scenarios/custom_low_tariff.yaml",
    "message": "Scenario created and saved"
  }
}
```

---

#### GET `/api/v1/scenarios/{scenario_id}/compare`
**Purpose:** Compare multiple scenarios side-by-side.

**Query Parameters:**
```
?scenarios=basecase,optimisticwind,conservativewind,pe_case
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "base_scenario": "basecase",
    "comparison": {
      "basecase": {
        "project_irr": 0.128,
        "equity_irr": 0.185,
        "dscr_min": 1.45,
        "irr_vs_base": 0.0
      },
      "optimisticwind": {
        "project_irr": 0.162,
        "equity_irr": 0.215,
        "dscr_min": 1.67,
        "irr_vs_base": 0.034  // 340 bps upside
      },
      "conservativewind": {
        "project_irr": 0.085,
        "equity_irr": 0.145,
        "dscr_min": 1.21,
        "irr_vs_base": -0.043  // -430 bps downside
      },
      "pe_case": {
        "project_irr": 0.095,
        "equity_irr": 0.275,
        "dscr_min": 1.18,
        "irr_vs_base": -0.033  // Lower project IRR due to higher leverage, but higher equity IRR
      }
    },
    "insights": [
      "Optimistic case provides +340 bps equity IRR upside",
      "Conservative case shows DSCR vulnerability at 1.21x",
      "PE case leverages up to 75% for higher equity returns"
    ]
  }
}
```

---

### 1.3 Analytics Endpoints

#### POST `/api/v1/scenarios/{scenario_id}/sensitivity`
**Purpose:** Run tornado (parameter sensitivity) analysis.

**Request:**
```json
{
  "metric": "equity_irr",
  "parameters": [
    {
      "name": "capacity_factor",
      "base_value": 0.40,
      "range_down": -0.05,
      "range_up": 0.05
    },
    {
      "name": "opex_usd_per_year",
      "base_value": 3000000,
      "range_down": -0.15,
      "range_up": 0.15
    },
    {
      "name": "tariff_lkr",
      "base_value": 20.3,
      "range_down": -0.10,
      "range_up": 0.10
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "base_value": 0.185,
    "tornado": [
      {
        "parameter": "tariff_lkr",
        "base": 20.3,
        "down_scenario": 18.27,
        "down_metric_value": 0.105,
        "down_impact": -0.080,
        "up_scenario": 22.33,
        "up_metric_value": 0.265,
        "up_impact": 0.080,
        "total_range": 0.160,
        "rank": 1
      },
      {
        "parameter": "capacity_factor",
        "base": 0.40,
        "down_scenario": 0.35,
        "down_metric_value": 0.125,
        "down_impact": -0.060,
        "up_scenario": 0.45,
        "up_metric_value": 0.245,
        "up_impact": 0.060,
        "total_range": 0.120,
        "rank": 2
      },
      {
        "parameter": "opex_usd",
        "base": 3000000,
        "down_scenario": 2550000,
        "down_metric_value": 0.195,
        "down_impact": 0.010,
        "up_scenario": 3450000,
        "up_metric_value": 0.175,
        "up_impact": -0.010,
        "total_range": 0.020,
        "rank": 3
      }
    ],
    "pareto_80_20": {
      "parameters": ["tariff_lkr", "capacity_factor"],
      "combined_impact": 0.280,
      "pct_of_total": 0.88
    }
  }
}
```

---

#### POST `/api/v1/scenarios/{scenario_id}/monte-carlo`
**Purpose:** Run stochastic (Monte Carlo) analysis.

**Request:**
```json
{
  "samples": 1000,
  "parameters": [
    {
      "name": "capacity_factor",
      "distribution": "normal",
      "mean": 0.40,
      "std_dev": 0.03
    },
    {
      "name": "tariff_lkr",
      "distribution": "normal",
      "mean": 20.3,
      "std_dev": 1.2
    }
  ],
  "metrics": ["equity_irr", "dscr_min", "project_npv"]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "samples": 1000,
    "equity_irr": {
      "mean": 0.1847,
      "median": 0.1852,
      "std_dev": 0.0342,
      "min": 0.0845,
      "max": 0.2834,
      "percentile_5": 0.1285,
      "percentile_25": 0.1623,
      "percentile_75": 0.2071,
      "percentile_95": 0.2409,
      "tail_risk": {
        "prob_below_target": 0.12,
        "cvar_95": 0.1089
      }
    },
    "dscr_min": {
      "mean": 1.453,
      "median": 1.462,
      "std_dev": 0.187,
      "min": 0.921,
      "max": 1.986,
      "percentile_5": 1.148,
      "percentile_25": 1.327,
      "percentile_75": 1.579,
      "percentile_95": 1.761,
      "tail_risk": {
        "prob_below_minimum_covenant": 0.03,
        "covenant_breach_probability": 0.03
      }
    },
    "project_npv": {
      "mean": 45.2e6,
      "median": 45.8e6,
      "std_dev": 8.4e6,
      "percentile_5": 31.2e6,
      "percentile_95": 59.4e6
    },
    "correlation_matrix": {
      "equity_irr_vs_dscr": 0.87,
      "equity_irr_vs_npv": 0.92,
      "dscr_vs_npv": 0.89
    }
  }
}
```

---

### 1.4 Covenant Analysis

#### GET `/api/v1/projects/{project_id}/covenants`
**Purpose:** Get covenant compliance status.

**Response:**
```json
{
  "status": "success",
  "data": {
    "scenario": "basecase",
    "covenants": [
      {
        "name": "Minimum DSCR",
        "type": "minimum",
        "threshold": 1.20,
        "actual": 1.45,
        "status": "PASS",
        "margin": 0.25,
        "margin_pct": 20.8,
        "first_breach_year": null,
        "severity": "OK"
      },
      {
        "name": "Minimum LLCR",
        "type": "minimum",
        "threshold": 1.50,
        "actual": 2.35,
        "status": "PASS",
        "margin": 0.85,
        "margin_pct": 56.7,
        "first_breach_year": null,
        "severity": "OK"
      },
      {
        "name": "Maximum Leverage (LTV)",
        "type": "maximum",
        "threshold": 0.75,
        "actual": 0.70,
        "status": "PASS",
        "margin": 0.05,
        "margin_pct": 6.7,
        "first_breach_year": null,
        "severity": "OK"
      },
      {
        "name": "FX Exposure (LKR per USD)",
        "type": "range",
        "lower_threshold": 300,
        "upper_threshold": 450,
        "actual": 375,
        "status": "PASS",
        "severity": "OK"
      }
    ],
    "overall_status": "COMPLIANT",
    "compliance_score": 0.95,
    "alert_summary": {
      "total_covenants": 4,
      "passing": 4,
      "warning": 0,
      "breached": 0
    }
  }
}
```

---

### 1.5 Export Operations

#### POST `/api/v1/projects/{project_id}/export`
**Purpose:** Generate and download financial reports.

**Query Parameters:**
```
?format=xlsx|csv|json
&include=metrics,timeseries,covenants,sensitivity
```

**Response (for format=xlsx):**
- File download: `dutchbay_150mw_basecase_2025-12-07.xlsx`
- Contains sheets:
  - Executive Summary (KPIs)
  - Annual Cashflow (timeseries)
  - Debt Schedule
  - Covenants
  - Sensitivity Analysis
  - Monte Carlo Results (if available)

---

## 2. Data Type Definitions

### 2.1 Financial Metrics

```typescript
interface ProjectMetrics {
  // Core NPV/IRR
  project_npv_usd: number;
  project_irr: number;
  project_pi: number;  // Profitability index
  project_payback_years: number;

  // Debt metrics
  dscr_min: number;
  dscr_avg: number;
  llcr: number;
  plcr: number;

  // Equity metrics
  equity_npv_usd: number;
  equity_irr: number;
  equity_moic: number;
  equity_payback_years: number;

  // Capital structure
  capex_total_usd: number;
  capex_total_lkr: number;
  debt_total_usd: number;
  equity_total_usd: number;

  // Status
  covenant_compliant: boolean;
  warnings: string[];
}
```

### 2.2 Timeseries Data

```typescript
interface AnnualTimeseries {
  years: number[];

  // Revenue side
  revenue_usd: number[];
  revenue_lkr: number[];

  // Costs
  opex_usd: number[];
  opex_lkr: number[];
  depreciation_usd: number[];
  ebitda_usd: number[];

  // Financing
  cfads_usd: number[];
  debt_outstanding: number[];
  debt_service_principal: number[];
  debt_service_interest: number[];
  dscr: number[];

  // Returns
  tax_usd: number[];
  equity_cashflow: number[];

  // FX
  fx_rate_lkr_per_usd: number[];
}
```

### 2.3 Scenario Configuration

```typescript
interface ScenarioConfig {
  metadata: {
    id: string;
    name: string;
    description: string;
    version: string;
  };

  project: {
    technology: string;
    capacity_mw: number;
    capacity_factor: number;
    degradation: number;
    project_life_years: number;
    cod_year: number;
  };

  capex: {
    usd_total: number;
    freight_pct: number;
    contingency_pct: number;
  };

  revenue: {
    tariff: {
      lkr_per_kwh: number;
      ppa_term_years: number;
      inflation: number;
    };
  };

  opex: {
    fixed_usd_per_year: number;
    variable_pct_of_revenue: number;
    escalation: number;
  };

  financing: {
    debt_ratio: number;
    tenor_years: number;
    grace_years: number;
    interest_rate: number;
    target_dscr: number;
    dscr_covenant_minimum: number;
  };

  fx: {
    base_rate_lkr_per_usd: number;
    annual_depreciation: number;
  };

  tax: {
    corporate_tax_rate: number;
    depreciation_years: number;
    tax_holiday_years: number;
    enhanced_capital_allowance: number;
  };
}
```

---

## 3. Error Handling

### Standard Error Response

```json
{
  "status": "error",
  "data": {},
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Capacity factor must be between 0.0 and 1.0",
      "field": "project.capacity_factor",
      "path": "/api/v1/projects/test/settings"
    }
  ]
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Valid calculation completed |
| 400 | Bad Request | Invalid parameter value |
| 404 | Not Found | Scenario doesn't exist |
| 422 | Validation Error | Config fails schema validation |
| 500 | Server Error | Python exception during calculation |
| 503 | Service Unavailable | Heavy load, try again |

---

## 4. Webhooks (Optional, for Async)

### Event: `scenario.calculation.completed`

```json
{
  "event": "scenario.calculation.completed",
  "timestamp": "2025-12-07T12:30:45Z",
  "project_id": "dutchbay-150mw",
  "scenario_id": "basecase",
  "job_id": "job-xyz-123",
  "result": {
    "project_irr": 0.128,
    "equity_irr": 0.185,
    "dscr_min": 1.45
  }
}
```

Webhook endpoint configured in `/api/v1/projects/{id}/settings/webhook`

---

## 5. Authentication (If Required)

```
Authorization: Bearer <JWT_TOKEN>
```

Token contains:
- `sub`: user ID
- `project_ids`: array of accessible projects
- `exp`: expiration timestamp

---

**End of API Contract Specifications**
