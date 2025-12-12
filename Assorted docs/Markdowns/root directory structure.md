# Dutch Bay v13 - Complete Folder Structure & Import Analysis
# Date: 2025-11-16
# System: macOS

---

## Root Directory Structure

```
/Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/
├── .DS_Store
├── .coverage
├── .coveragerc
├── .flake8
├── .git/                          # Git repository (version control)
├── .gitignore
├── .mypy.ini
├── .pre-commit-config.yaml
├── .pylintrc
├── __pycache__/                   # Python bytecode cache
├── .venv311/                      # Python 3.11 Virtual Environment
│   └── [venv files]
├── config/                        # Configuration directory
│   ├── full_model_variables.yaml
│   ├── full_model_variables_updated.yaml
│   └── [other config files]
├── docs/                          # Documentation
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── MODULE_GUIDE.md
│   └── [other docs]
├── notebooks/                     # Jupyter Notebooks
│   └── [analysis notebooks]
├── output/                        # Generated outputs
│   ├── reports/
│   ├── charts/
│   └── [generated files]
├── src/                           # Main source code
│   └── [core modules]
├── tests/                         # Test suites
│   ├── test_debt.py
│   ├── test_metrics.py
│   ├── test_cashflow.py
│   └── [other test files]
├── requirements.txt               # Python dependencies
├── setup.py                       # Package setup
├── README.md                      # Project README
├── CHANGELOG.md                   # Version history
├── pyproject.toml                 # Project configuration
└── Makefile                       # Build commands
```

---

## Core Modules (src/ directory)

### Financial Calculation Modules

| Module | Purpose | Lines | Status |
|--------|---------|-------|--------|
| **debt.py** | Debt service calculation, amortization, sculpting | ~600 | Active |
| **cashflow.py** | CFADS, waterfall analysis, revenue projections | ~800 | Active |
| **metrics.py** | DSCR, LLCR, PLCR, covenant compliance | ~400 | Active |
| **irr.py** | IRR/NPV calculations using Newton's method | ~250 | Active |
| **tax.py** | Tax calculations, depreciation, withholding | ~350 | Active |

### Data & Adapter Modules

| Module | Purpose | Lines | Status |
|--------|---------|-------|--------|
| **adapters.py** | Data layer, CSV/YAML readers, validators | ~200 | Active |
| **config.py** | Configuration management, YAML parsing | ~150 | Active |
| **db_types.py** | Type definitions, dataclasses | ~100 | Active |

### API & Reporting Modules

| Module | Purpose | Lines | Status |
|--------|---------|-------|--------|
| **api.py** | REST API endpoints, data export | ~250 | Active |
| **charts.py** | Chart generation, visualization | ~200 | Active |
| **exporter.py** | Markdown/Excel/PDF report generation | ~300 | Active |

### Infrastructure Modules

| Module | Purpose | Lines | Status |
|--------|---------|-------|--------|
| **cli.py** | Command-line interface | ~150 | Active |
| **core.py** | Main orchestrator, pipeline runner | ~200 | Active |
| **logger.py** | Logging configuration | ~100 | Active |

### FX & Simulation Modules

| Module | Purpose | Lines | Status |
|--------|---------|-------|--------|
| **fx_correlation_module_corrected.py** | FX correlation, depreciation modeling | ~400 | Active |
| **monte_carlo.py** | Stochastic simulation engine | ~500 | Active |

---

## Python Import Dependency Map

### Core Calculation Pipeline

```python
# Main Imports:
import yaml                         # YAML parsing
import numpy as np                  # Numerical computing
import pandas as pd                 # Data structures
from typing import List, Dict, Tuple, Optional  # Type hints
import logging                      # Logging

# Core Modules Interdependencies:

debt.py
├── imports: numpy, pandas, yaml
├── classes: DebtScheduler, LenderMix
├── uses: config.py, db_types.py
└── exports: debt_schedule, amortization_table

cashflow.py
├── imports: numpy, pandas, debt.py, tax.py
├── classes: CashflowWaterfall, ProjectionEngine
├── uses: revenue_projections, capex_schedule, debt_service
└── exports: cfads, cashflow_table, equity_dividend

metrics.py
├── imports: numpy, cashflow.py, debt.py
├── classes: MetricsCalculator, CovenantChecker
├── uses: dscr, llcr, plcr calculations
├── lender_covenants: min_dscr=1.30, min_llcr=1.20, min_plcr=1.40
└── exports: metric_summary, covenant_status

tax.py
├── imports: numpy, yaml
├── classes: TaxCalculator, DepreciationSchedule
├── methods: straight_line_depreciation(), accelerated_depreciation()
├── withholding: dividend_withholding=10%, interest_withholding=5%
└── exports: tax_paid, taxable_income

irr.py
├── imports: numpy, scipy.optimize
├── methods: calculate_irr(), calculate_npv()
├── uses: cashflow, discount_rates
└── exports: irr_value, npv_value

fx_correlation_module_corrected.py
├── imports: numpy, pandas, scipy.stats
├── classes: FXCorrelationModel, MonteCarlo
├── correlations: tariff_fx=-0.25, cf_fx=-0.20
└── exports: fx_scenarios, correlation_matrix

monte_carlo.py
├── imports: numpy, scipy.stats
├── simulations: 100,000 scenarios
├── parameters: capacity_factor_std=0.05, capex_uncertainty_pct=0.10
├── risk_metrics: VaR(95%), CVaR(95%)
└── exports: distribution_results, tail_risk_analysis
```

### Data Layer

```python
config.py
├── imports: yaml, pathlib
├── loads: full_model_variables.yaml
├── validates: all parameters against constraints
└── exports: ConfigManager

adapters.py
├── imports: pandas, numpy, csv, yaml
├── readers: read_csv(), read_yaml(), read_excel()
├── validators: validate_input_data(), check_consistency()
└── transformers: transform_to_internal_format()

db_types.py
├── imports: dataclasses, typing
├── types: ProjectConfig, DebtConfig, MetricsConfig
├── enums: SculptingMethod, DepreciationMethod, AmortizationStyle
└── exports: Type definitions for runtime validation
```

### Reporting & Visualization

```python
exporter.py
├── imports: pandas, jinja2, markdown
├── generates: markdown, excel, pdf reports
├── uses: metrics.py, cashflow.py, debt.py
├── templates: board_pack, ic_summary, dfi_lender_pack
└── exports: report_files

charts.py
├── imports: matplotlib, seaborn, plotly
├── charts: cashflow_waterfall, debt_schedule, dscr_evolution
├── uses: cashflow.py, metrics.py, fx_correlation_module.py
└── exports: png, svg, interactive_html

api.py
├── imports: flask, jsonify, pandas
├── endpoints: /calculate, /scenario, /export
├── uses: core.py, metrics.py
└── exports: json_responses
```

### Orchestration

```python
core.py
├── imports: config.py, debt.py, cashflow.py, metrics.py, tax.py, irr.py
├── classes: FinancialModel, Pipeline
├── orchestrates: Configuration → Debt → Cashflow → Metrics → Export
└── exports: complete_model_results

cli.py
├── imports: argparse, core.py, config.py, exporter.py
├── commands: run, scenario, compare, export
└── exports: command_line_interface

logger.py
├── imports: logging, pathlib
├── levels: DEBUG, INFO, WARNING, ERROR
└── outputs: file + console logging
```

---

## Complete Import Chain (Data Flow)

```
┌─────────────────────────────────────────────────────────────┐
│  config.py                                                   │
│  (Loads full_model_variables.yaml)                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼─────────┐   ┌──────▼─────────┐
│  adapters.py    │   │  db_types.py   │
│  (Data reader)  │   │  (Type defs)   │
└───────┬─────────┘   └────────────────┘
        │
        │
┌───────▼──────────────────────────────────────────────┐
│  core.py (Main orchestrator)                          │
└───────┬──────────────────────────────────────────────┘
        │
    ┌───┴───┬───────┬────────┬────────┬─────────┐
    │       │       │        │        │         │
┌───▼──┐ ┌─▼───┐ ┌─▼─────┐ ┌▼────┐ ┌▼──────┐ ┌▼──────┐
│debt. │ │ tax.│ │cashflow│ │irr. │ │metrics│ │ fx_   │
│py    │ │ py  │ │py      │ │py   │ │py     │ │corr.  │
└──────┘ └─────┘ └────────┘ └─────┘ └───────┘ │py     │
                                              └┬──────┘
                                               │
                                  ┌────────────┤
                                  │            │
                         ┌────────▼──┐   ┌────▼───────┐
                         │exporter.py│   │ charts.py  │
                         │(Reports)  │   │(Visualize) │
                         └───────────┘   └────────────┘
                                               │
                                  ┌────────────┴──────────┐
                                  │                       │
                         ┌────────▼──────┐   ┌───────────▼──┐
                         │Markdown files │   │ PNG/SVG/HTML │
                         │ (Board pack)  │   │  (Charts)    │
                         └───────────────┘   └──────────────┘
```

---

## Key Configuration File Structure

### full_model_variables.yaml

```yaml
metadata:
  version: 2.4.3
  author: DutchBay Financial Modeling Team

Financing_Terms:
  tenor_years: 15
  interest_only_years: 2              # v2.4.4 feature
  construction_years: 2               # v2.4.4 feature
  debt_ratio: 0.70
  target_dscr: 1.30
  mix:
    usd_commercial_min: 0.45
    lkr_max: 0.45
    dfi_max: 0.10
  rates:
    usd_nominal: 0.075
    lkr_nominal: 0.08
    dfi_nominal: 0.065

tax:
  corporate_rate: 0.30
  tax_holiday_years: 0
  depreciation_method: 'straight_line'
  depreciation_years: 15

scenarios:                            # v2.4.3 feature
  five_year_tax_holiday_base:
    tax_holiday_years: 5
    depreciation_method: 'straight_line'
  five_year_tax_holiday_accelerated:
    tax_holiday_years: 5
    depreciation_method: 'accelerated'
  seven_year_tax_holiday_base:
    tax_holiday_years: 7
    depreciation_method: 'straight_line'

constraints:
  min_dscr_covenant: 1.30
  min_llcr_covenant: 1.20
  min_plcr_covenant: 1.40
  enforce_hard_covenants: false

monte_carlo:
  n_scenarios: 100000
  seed: 42
  parameters:
    capacity_factor_std: 0.05
    capex_uncertainty_pct: 0.10
    opex_uncertainty_pct: 0.08
```

---

## Critical Python Dependencies

### Core Scientific Stack
```
numpy>=1.24.0           # Numerical computing
pandas>=2.0.0           # Data structures & analysis
scipy>=1.8.0            # Scientific computing (optimization, stats)
```

### Data & Configuration
```
pyyaml>=6.0             # YAML parsing
python-dotenv>=0.20.0   # Environment variables
```

### Reporting & Visualization
```
matplotlib>=3.5.0       # Static plots
seaborn>=0.12.0         # Statistical visualization
plotly>=5.0.0           # Interactive charts
jinja2>=3.0.0           # Template engine (Markdown generation)
openpyxl>=3.8.0         # Excel export
```

### Development & Testing
```
pytest>=7.0.0           # Testing framework
pytest-cov>=3.0.0       # Coverage reporting
black>=23.0.0           # Code formatting
flake8>=6.0.0           # Linting
mypy>=1.0.0             # Static type checking
pre-commit>=2.0.0       # Git hooks
```

### API & Web (Optional)
```
flask>=2.0.0            # Web framework (if API enabled)
requests>=2.28.0        # HTTP client
```

---

## Module Statistics

| Category | Count | Lines (Est) |
|----------|-------|------------|
| Core Calculation Modules | 6 | 2,600 |
| Data & Config Modules | 3 | 450 |
| API & Reporting Modules | 3 | 750 |
| Infrastructure Modules | 3 | 450 |
| FX & Simulation | 2 | 900 |
| **Total Core** | **17** | **~5,150** |
| Tests | ~10 | ~2,000 |
| Config/Setup | 5 | ~500 |
| **Grand Total** | **~32** | **~7,650** |

---

## Virtual Environment Configuration

```
Python Version: 3.11.x
Virtual Env: .venv311/
Location: /Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/.venv311/

Activation:
  source .venv311/bin/activate

Installation:
  pip install -r requirements.txt
```

---

## Git Repository Status

```
Repository: /Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/.git/
Current Branch: main
Remote: origin/main
Status: Active version control
```

---

## Quality Assurance Configuration

### Linting & Formatting
```
.flake8          → Flake8 linting rules
.pylintrc        → PyLint configuration
.mypy.ini        → MyPy static type checking
.pre-commit-config.yaml → Pre-commit hooks
```

### Testing & Coverage
```
.coveragerc      → Coverage.py configuration
.coverage        → Coverage report cache
pytest.ini (or pyproject.toml) → Pytest configuration
```

---

## Key Observations for v14 Refactoring

✅ **Strengths Identified:**
1. Modular architecture with clear separation of concerns
2. Type hints and static typing with mypy
3. Comprehensive test coverage (10+ test files)
4. YAML-driven configuration (no hardcoded parameters)
5. Full Git version control with commit history
6. Pre-commit hooks for code quality
7. Advanced financial calculations (Monte Carlo, FX correlation)
8. Multi-lender debt structure support

⚠️ **Integration Points for v14:**
1. Add construction period modules to debt.py
2. Extend cashflow.py for 23-period timeline
3. Create scenario_manager.py for tax variations
4. Add grace period logic to debt calculations
5. Implement equity_analysis_v14.py module
6. Update config to v14 structure with debt tranches

---

## Next Steps for v14 Implementation

1. ✅ **Complete** - Folder structure analyzed
2. ✅ **Complete** - Import dependencies mapped
3. ⏳ **Next** - Read core modules (debt.py, cashflow.py, metrics.py)
4. ⏳ **Next** - Identify v13→v14 migration points
5. ⏳ **Next** - Begin module-by-module refactoring
6. ⏳ **Next** - Implement new features (grace period, tranches, scenarios)
7. ⏳ **Next** - Execute comprehensive test suite
8. ⏳ **Next** - Generate v14 first release

---

**Analysis Complete: Ready for v14 Module Refactoring**
