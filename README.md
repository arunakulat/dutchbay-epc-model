# DutchBay EPC Model – 150MW Wind Farm Financial Model

[![CI v14chat](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/ci-v14.yml/badge.svg)](https://github.com/arunakulat/dutchbay-epc-model/actions/workflows/ci-v14.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Production-grade financial modeling suite for renewable energy project development, DFI/Lender analysis, and EPC evaluation.**

---

## 🚀 Quick Start

### For New AI Threads/Sessions

Restore full project context instantly:

**Quick:** See [THREAD_MIGRATION_QUICKSTART.md](THREAD_MIGRATION_QUICKSTART.md)
**Complete:** See [docs/THREAD_MIGRATION_PACKAGE.md](docs/THREAD_MIGRATION_PACKAGE.md)

### For Developers

```bash
# Clone repository
git clone https://github.com/arunakulat/dutchbay-epc-model.git
cd dutchbay-epc-model

# Create virtual environment
python3.11 -m venv .venv311
source .venv311/bin/activate  # On Windows: .venv311\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_dev.txt

# Run tests
pytest tests/

# Run scenario analysis
python analytics/run_full_pipeline.py --config scenarios/base.yaml
```

---

## 🏛️ Architecture Overview

### v14 Status: Production Ready ✅

The **v14chat** branch represents the canonical, hardened execution path featuring:

- ✅ **Validated scenario loader** with strict YAML/JSON parsing
- ✅ **Annual cashflow engine** (CFADS, OpEx, CapEx, debt service)
- ✅ **Debt modeling** (amortization, DSCR calculations)
- ✅ **Isolated IRR/NPV** calculations
- ✅ **Analytics pipeline** (sensitivity, Monte Carlo ready)
- ✅ **Export infrastructure** (CSV, Excel, JSON)
- ✅ **CI/CD pipeline** with regression testing

### Core Modules

```
analytics/                    # Analytics & scenario evaluation
  ├── foundation.py          # Base model (CRITICAL: do not rename)
  ├── scenario_loader.py     # YAML/JSON config parser
  ├── scenario_analytics.py  # KPI extraction & reporting
  ├── sensitivity/           # Sensitivity analysis modules
  └── monte_carlo/           # Monte Carlo simulation

finance/                      # Financial calculation engine
  ├── cashflow_v14.py        # Cash flow projections
  ├── debt_v14.py            # Debt modeling & DSCR
  ├── equity_v14.py          # Equity returns (IRR, NPV)
  └── tax.py                 # Tax calculations

scenarios/                    # Scenario configuration files
  ├── base.yaml              # Base case
  ├── optimistic.yaml        # Upside scenario
  └── pessimistic.yaml       # Downside scenario

exports/                      # Generated outputs (git-ignored)
  ├── *.csv
  ├── *.xlsx
  └── *.png

tests/                        # Test suite
  ├── contracts/             # Contract tests
  ├── analytics/             # Analytics tests
  └── integration/           # Integration tests

docs/                         # Documentation
  ├── THREAD_MIGRATION_PACKAGE.md  # AI context restoration guide
  ├── architecture_v14.md             # Technical architecture
  └── Dev_workflow_v14.md             # Development workflow
```

---

## 📊 Key Features

### Financial Modeling
- **Debt Structuring**: Multi-tranche debt (USD DFI, USD commercial, LKR local) with grace periods
- **Cash Flow Analysis**: CFADS, debt service coverage, operating cash flows
- **Returns Calculation**: Project IRR, Equity IRR, NPV (project & equity)
- **Risk Metrics**: DSCR (minimum, average), break-even analysis

### Analytics Capabilities
- **Scenario Analysis**: Compare base, optimistic, pessimistic cases
- **Sensitivity Analysis**: Tornado charts for key drivers
- **Monte Carlo Simulation**: Probabilistic modeling (in development)
- **Parameter Validation**: Strict YAML schema enforcement

### Export & Reporting
- **CSV/Excel**: Timestamped exports, never overwrites
- **Executive Workbooks**: Board-ready KPI summaries
- **JSON/JSONL**: Machine-readable outputs for pipelines
- **Charts**: Matplotlib-based visualizations

---

## 🔧 Development Standards

### "Go With The Flow" Rules

These non-negotiable principles ensure production-grade quality:

1. **Config-Driven**: All parameters in YAML with validation
2. **Batch-Friendly**: No hardcoded paths, CLI-compatible
3. **Stateless**: Reproducible results, no mutable globals
4. **Test-First**: Contract tests for all analytics
5. **Type-Safe**: Full mypy compliance

See [docs/THREAD_MIGRATION_PACKAGE.md](docs/THREAD_MIGRATION_PACKAGE.md) for complete standards.

### Code Quality

```bash
# Type checking
mypy analytics/ finance/

# Linting
flake8 analytics/ finance/
black --check analytics/ finance/
isort --check-only analytics/ finance/

# Testing with coverage
pytest --cov=analytics --cov=finance --cov-report=html
```

### CI/CD Pipeline

- **Quick Smoke**: CLI + core analytics (fast feedback)
- **Full Regression**: Complete v14 pipeline + coverage
- **Coverage Floor**: 65% minimum (current: ~70%)
- **FX Schema**: Strict enforcement (mapping-only, no scalars)

---

## 📝 Usage Examples

### Basic Scenario Run

```bash
python analytics/run_full_pipeline.py --config scenarios/base.yaml
```

### Sensitivity Analysis

```bash
python analytics/sensitivity_v14.py \
  --config scenarios/base.yaml \
  --output exports/
```

### Python API

```python
from analytics.scenario_loader import load_scenario_config
from analytics.scenario_analytics import run_scenario

# Load configuration
config = load_scenario_config("scenarios/base.yaml", validation_mode="strict")

# Run analysis
summary_df, timeseries_df = run_scenario(config)

# Access results
print(f"Project IRR: {summary_df['project_irr'].iloc[0]:.2%}")
print(f"Min DSCR: {summary_df['dscr_min'].iloc[0]:.2f}")
```

### Export to Excel

```python
from analytics.executive_workbook import create_executive_workbook

create_executive_workbook(
    summary_df=summary_df,
    timeseries_df=timeseries_df,
    output_path="exports/executive_summary.xlsx"
)
```

---

## 📚 Documentation

### For AI Assistants & Context Restoration
- [Thread Migration Quick Start](THREAD_MIGRATION_QUICKSTART.md) - Minimal paste for new threads
- [Complete Migration Package](docs/THREAD_MIGRATION_PACKAGE.md) - Full context & standards

### For Developers
- [Architecture Overview](docs/architecture_v14.md) - Technical design
- [Development Workflow](docs/Dev_workflow_v14.md) - Git workflow & practices
- [Analytics Layer](docs/ANALYTICS_SETUP_COMPLETE.md) - Analytics module details
- [Production Readiness](docs/ANALYTICS_PRODUCTION_READY.md) - Deployment guide

### For Project Managers
- [Changelog](CHANGELOG.md) - Version history
- [Release Process](RELEASING.md) - How to create releases
- [Security](SECURITY.md) - Security policy

---

## 🛣️ Roadmap

### Phase 2: Interactive Analytics (In Progress 🔄)
- [ ] Streamlit dashboard for scenario exploration
- [ ] REST API for sensitivity/Monte Carlo
- [ ] Real-time parameter validation UI

### Phase 3: Advanced Reporting (Planned 📋)
- [ ] Automated Excel report generation
- [ ] Chart export (PNG/SVG)
- [ ] Health/audit tracking

### Phase 4: Optimization (Planned 📋)
- [ ] Scenario comparison tools
- [ ] Multi-objective optimizer
- [ ] Version control for scenarios

### Phase 5: Stakeholder Deliverables (Planned 📋)
- [ ] DFI/Lender presentation mode
- [ ] Board presentation templates
- [ ] Risk dashboards

---

## ⚙️ Technical Requirements

- **Python**: 3.11+
- **Dependencies**: See `requirements.txt`
- **Dev Tools**: See `requirements_dev.txt`
- **Environment**: macOS, Linux, or Windows with WSL

---

## 🤝 Contributing

### Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes following "Go with the Flow" rules
3. Run tests: `pytest tests/`
4. Run quality checks: `mypy`, `flake8`, `black`
5. Commit: `git commit -am "feat: Your feature description"`
6. Push: `git push origin feature/your-feature`
7. Create Pull Request

### Before Committing

```bash
# Install pre-commit hooks
pre-commit install

# Run all checks
pre-commit run --all-files
```

---

## 📎 Project Information

- **Project**: Dutch Bay 150MW Wind Farm
- **Location**: Sri Lanka
- **Technology**: Onshore wind energy
- **Capacity**: 150 MW
- **Status**: Financial modeling & development phase

---

## 📝 License

Proprietary - All Rights Reserved

---

## 👥 Team & Support

- **Repository**: [arunakulat/dutchbay-epc-model](https://github.com/arunakulat/dutchbay-epc-model)
- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Documentation**: See `docs/` directory for detailed guides

---

**Last Updated**: November 24, 2025
**Version**: 1.0.0 (v14 production-ready)
