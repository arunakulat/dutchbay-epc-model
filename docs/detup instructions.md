# Dutch Bay v2.4.4 - Setup Instructions

**Version:** 2.4.4
**Date:** November 16, 2025
**Purpose:** Complete setup guide for clean v2.4.4 installation

---

## Prerequisites

- Python 3.11 or higher
- pip package manager
- Git (optional, for version control)

---

## Step 1: Create Project Directory

```bash
mkdir DutchBay_v244
cd DutchBay_v244
```

---

## Step 2: Create Folder Structure

```bash
mkdir -p config
mkdir -p modules
mkdir -p scripts
mkdir -p tests
mkdir -p data
mkdir -p output
mkdir -p docs
```

Your structure should look like:
```
DutchBay_v244/
├── config/          # YAML configuration files
├── modules/         # Core Python modules
├── scripts/         # Pipeline and utility scripts
├── tests/           # Test suites
├── data/            # CSV and data files
├── output/          # Generated reports
├── docs/            # Documentation
└── README.md
```

---

## Step 3: Create Virtual Environment

### On macOS/Linux:
```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
```

### On Windows:
```bash
python -m venv .venv311
.venv311\\Scripts\\activate
```

---

## Step 4: Install Dependencies

Create `requirements.txt`:
```txt
pyyaml>=6.0
numpy>=1.24.0
pandas>=2.0.0
mypy>=1.0.0
pytest>=7.0.0
black>=23.0.0
flake8>=6.0.0
```

Install:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 5: File Placement Guide

### Configuration Files (config/)
- `config_v244.yaml` - Main configuration (download from assets)

### Python Modules (modules/)
From your v13 codebase, place refactored versions:
- `cashflow.py`
- `debt.py`
- `metrics.py`
- `fx_correlation_module.py`
- `scenario_manager.py` (new for v2.4.4)
- `tax_calculator.py` (new for v2.4.4)

### Scripts (scripts/)
- `run_full_pipeline.py`
- `run_exporter.py`
- `parameter_validation.py`

### Tests (tests/)
- `test_metrics_complete.py`
- `test_debt_with_grace.py` (new)
- `test_scenarios.py` (new)
- `run_all_py_checks.sh`

### Data (data/)
- `data.csv`
- `fxdata.csv`

### Documentation (docs/)
- `DutchBay_Codebase_Inventory_v244.md`
- `IMPLEMENTATION_GUIDE_v244.md`
- `SETUP_INSTRUCTIONS_v244.md` (this file)

---

## Step 6: Environment Configuration

Create `.env` file (optional):
```bash
# Project Configuration
PROJECT_VERSION=2.4.4
DEFAULT_CONFIG=config/config_v244.yaml
DEFAULT_SCENARIO=five_year_tax_holiday_no_accel_dep

# Paths
DATA_DIR=data
OUTPUT_DIR=output
LOG_DIR=logs
```

---

## Step 7: Verify Installation

Run validation script:
```bash
python scripts/parameter_validation.py --config config/config_v244.yaml
```

Expected output:
```
✓ Configuration file loaded successfully
✓ All required parameters present
✓ Scenarios validated: 3 found
✓ Grace period configuration valid
✓ Drawdown schedule parameters valid
```

---

## Step 8: Run Type Checking

```bash
mypy modules/ --ignore-missing-imports
```

Expected: No errors

---

## Step 9: Run Test Suite

```bash
pytest tests/ -v
```

Or use the bash script:
```bash
bash tests/run_all_py_checks.sh
```

---

## Step 10: Test Basic Pipeline

Run a simple test:
```bash
python scripts/run_full_pipeline.py \\
    --config config/config_v244.yaml \\
    --scenario five_year_tax_holiday_no_accel_dep \\
    --output output/test_run.md
```

Check `output/test_run.md` for results.

---

## File Import Structure

Ensure proper imports in your Python files:

### In `run_full_pipeline.py`:
```python
import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'modules'))

from cashflow import calculate_cfads_with_construction
from debt import calculate_debt_service_with_grace
from metrics import calculate_metrics
from scenario_manager import ScenarioManager
```

### In test files:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'modules'))

import pytest
from debt import calculate_drawdown_schedule
```

---

## Git Setup (Optional)

Initialize repository:
```bash
git init
```

Create `.gitignore`:
```
# Virtual Environment
.venv*/
venv*/
env*/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# IDE
.vscode/
.idea/
*.swp
*.swo

# Output
output/*.md
output/*.csv
output/*.pdf

# Logs
logs/
*.log

# Data (if sensitive)
data/*.csv

# OS
.DS_Store
Thumbs.db
```

Initial commit:
```bash
git add .
git commit -m "Initial v2.4.4 setup"
```

---

## Troubleshooting

### Import Errors
If you get "module not found" errors:
```bash
export PYTHONPATH="${PYTHONPATH}:${PWD}/modules"
```

### YAML Parsing Errors
Validate YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('config/config_v244.yaml'))"
```

### Virtual Environment Issues
Deactivate and recreate:
```bash
deactivate
rm -rf .venv311
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
```

---

## Next Steps

1. **Review Implementation Guide:** Read `IMPLEMENTATION_GUIDE_v244.md` thoroughly
2. **Refactor v13 Code:** Update your modules according to guide
3. **Add New Modules:** Create `scenario_manager.py` and `tax_calculator.py`
4. **Test Incrementally:** Test each module as you refactor
5. **Run Full Pipeline:** Test all three scenarios
6. **Generate Reports:** Create board packs for each scenario

---

## Maintenance

### Updating Configuration
Always validate after changes:
```bash
python scripts/parameter_validation.py --config config/config_v244.yaml
```

### Running Different Scenarios
```bash
# Scenario 1: 5-year base
python scripts/run_full_pipeline.py --scenario five_year_tax_holiday_no_accel_dep

# Scenario 2: 5-year accelerated
python scripts/run_full_pipeline.py --scenario five_year_tax_holiday_accel_dep

# Scenario 3: 7-year base
python scripts/run_full_pipeline.py --scenario seven_year_tax_holiday_no_accel_dep
```

### Code Quality Checks
Before committing changes:
```bash
black modules/ scripts/ tests/  # Format code
flake8 modules/ scripts/ tests/  # Lint
mypy modules/ --ignore-missing-imports  # Type check
pytest tests/ -v  # Run tests
```

---

## Support

For issues or questions:
1. Check `IMPLEMENTATION_GUIDE_v244.md`
2. Review `DutchBay_Codebase_Inventory_v244.md`
3. Validate configuration with `parameter_validation.py`

---

## Version History

| Version | Date       | Changes                                      |
|---------|------------|----------------------------------------------|
| 2.4.4   | 2025-11-16 | Grace period, scenarios, drawdown tranches   |
| 2.4.3   | 2025-11-16 | Added tax scenarios                          |
| 2.4.2   | 2025-11-16 | Comprehensive equity analysis table          |
| 2.4.1   | 2025-11-16 | Initial YAML-driven architecture             |

---

**Ready to Begin!** You now have a clean foundation for v2.4.4 development.
