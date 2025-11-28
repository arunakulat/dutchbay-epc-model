# 📝 DutchBay EPC Model - Developer Cheatsheet

**Quick reference for daily development tasks**

---

## ⚡ One-Liners

### Setup & Environment
```bash
# Create and activate venv
python3.11 -m venv .venv311 && source .venv311/bin/activate

# Install all dependencies
pip install -r requirements.txt -r requirements_dev.txt

# Install pre-commit hooks
pre-commit install
```

### Running Analysis
```bash
# Run base scenario
python analytics/run_full_pipeline.py --config scenarios/base.yaml

# Run with strict validation
python analytics/run_full_pipeline.py --config scenarios/base.yaml --mode strict

# Run sensitivity analysis
python analytics/sensitivity_v14.py --config scenarios/base.yaml --output exports/
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=analytics --cov=finance

# Run specific test file
pytest tests/analytics/test_scenario_analytics.py -v

# Run tests matching pattern
pytest -k "sensitivity"

# Run last failed tests
pytest --lf
```

### Code Quality
```bash
# Type checking
mypy analytics/ finance/

# Format code
black analytics/ finance/
isort analytics/ finance/

# Lint code
flake8 analytics/ finance/

# Run all quality checks
pre-commit run --all-files
```

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/your-feature

# Stage and commit
git add -A && git commit -m "feat: Your description"

# Push and set upstream
git push -u origin feature/your-feature

# Pull latest from main
git checkout main && git pull origin main

# Rebase feature branch
git checkout feature/your-feature && git rebase main
```

---

## 📚 Python Snippets

### Load and Run Scenario
```python
from analytics.scenario_loader import load_scenario_config
from analytics.scenario_analytics import run_scenario

config = load_scenario_config("scenarios/base.yaml")
summary_df, timeseries_df = run_scenario(config)
print(summary_df[['project_irr', 'dscr_min']])
```

### Validate Parameters
```python
from analytics.validation import validate_parameter_ranges

config = load_config('scenarios/base.yaml')
errors = validate_parameter_ranges(config, config['parameters'])
if not errors.empty:
    print("Validation errors:")
    print(errors)
```

### Export Results
```python
from datetime import datetime
from pathlib import Path

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_path = Path('exports') / f'results_{timestamp}.csv'
results.to_csv(output_path, index=False)
print(f"Saved to {output_path}")
```

### Create Executive Report
```python
from analytics.executive_workbook import create_executive_workbook

create_executive_workbook(
    summary_df=summary_df,
    timeseries_df=timeseries_df,
    output_path="exports/executive_summary.xlsx"
)
```

---

## 🛠️ Debugging

### Run with Debug Logging
```bash
export LOG_LEVEL=DEBUG
python analytics/run_full_pipeline.py --config scenarios/base.yaml
```

### Python Debugger
```python
import pdb; pdb.set_trace()  # Breakpoint

# Or use ipdb for better interface
import ipdb; ipdb.set_trace()
```

### Check Dataframe Issues
```python
import pandas as pd

# Inspect dataframe
print(df.info())
print(df.describe())
print(df.head())

# Check for NaN values
print(df.isnull().sum())

# Check datatypes
print(df.dtypes)
```

---

## 📊 Common Tasks

### Add New Scenario
```bash
# 1. Copy existing scenario
cp scenarios/base.yaml scenarios/new_scenario.yaml

# 2. Edit parameters
vim scenarios/new_scenario.yaml

# 3. Validate
python -c "from analytics.scenario_loader import load_scenario_config; load_scenario_config('scenarios/new_scenario.yaml', validation_mode='strict')"

# 4. Run
python analytics/run_full_pipeline.py --config scenarios/new_scenario.yaml
```

### Add New Test
```python
# tests/analytics/test_new_feature.py
import pytest
from analytics.new_module import new_function

def test_new_function_basic():
    """Test basic functionality."""
    result = new_function(input_data)
    assert result == expected_output

def test_new_function_edge_case():
    """Test edge case handling."""
    with pytest.raises(ValueError):
        new_function(invalid_input)
```

### Update Dependencies
```bash
# Update single package
pip install --upgrade package-name

# Freeze current environment
pip freeze > requirements_frozen.txt

# Update requirements.txt manually, then:
pip install -r requirements.txt --upgrade
```

---

## 📝 File Locations

### Critical Files (DO NOT RENAME)
- `analytics/foundation.py` - Base model foundation
- `finance/debt_v14.py` - Debt calculations
- `finance/equity_v14.py` - Equity returns
- `finance/cashflow_v14.py` - Cash flow engine

### Configuration
- `scenarios/*.yaml` - Scenario definitions
- `config/schema.yaml` - Parameter schema
- `.flake8` - Linting config
- `mypy.ini` - Type checking config
- `pytest.ini` - Test config

### Documentation
- `docs/THREAD_MIGRATION_PACKAGE.md` - Full context for AI
- `docs/architecture_v14.md` - Technical architecture
- `docs/Dev_workflow_v14.md` - Development workflow
- `THREAD_MIGRATION_QUICKSTART.md` - Quick AI restore

---

## ⚠️ Common Issues

### Import Errors
```bash
# Ensure you're in project root
cd /path/to/dutchbay-epc-model

# Activate virtual environment
source .venv311/bin/activate

# Reinstall in editable mode
pip install -e .
```

### Test Failures
```bash
# Clear pytest cache
pytest --cache-clear

# Run with verbose output
pytest -vv

# Run with print statements visible
pytest -s
```

### Type Checking Errors
```bash
# Clear mypy cache
rm -rf .mypy_cache/

# Run with verbose output
mypy analytics/ finance/ --verbose
```

---

## 🔗 Quick Links

- **Repository**: [github.com/arunakulat/dutchbay-epc-model](https://github.com/arunakulat/dutchbay-epc-model)
- **Issues**: [github.com/arunakulat/dutchbay-epc-model/issues](https://github.com/arunakulat/dutchbay-epc-model/issues)
- **CI/CD**: [github.com/arunakulat/dutchbay-epc-model/actions](https://github.com/arunakulat/dutchbay-epc-model/actions)

---

## 📌 Environment Variables

```bash
# Set model environment
export MODEL_ENV=development  # or production, staging

# Set output directory
export EPC_OUTPUT_DIR=./exports

# Set log level
export LOG_LEVEL=INFO  # or DEBUG, WARNING, ERROR

# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export MODEL_ENV=development' >> ~/.bashrc
```

---

## ⚙️ VS Code / Sublime Settings

### VS Code (`.vscode/settings.json`)
```json
{
  "python.defaultInterpreterPath": ".venv311/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

### Sublime Text Build System
See: `Python (venv311).sublime-build`

---

**Last Updated**: November 24, 2025
**For detailed documentation, see**: [docs/THREAD_MIGRATION_PACKAGE.md](docs/THREAD_MIGRATION_PACKAGE.md)
