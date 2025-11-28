# 🚦 DutchBay EPC Model Thread Migration Package

**Version:** 1.0
**Last Updated:** November 24, 2025
**Purpose:** Restore full project context and quality standards for any AI assistant or collaborator

---

## Quick Start Instructions

### For New AI Thread/Session

Paste this statement at the beginning of any new conversation:

```
Resume with full DutchBay EPC Model context. Apply "Go with the Flow" rules:
All module APIs and exports must be batch/API/stateless. Assume technical
and diagnostic patterns from docs/THREAD_MIGRATION_PACKAGE.md in the
arunakulat/dutchbay-epc-model repository.
```

### For Team Onboarding

Refer collaborators to:
- This document: `docs/THREAD_MIGRATION_PACKAGE.md`
- Main README: `README.md`
- Architecture docs: `docs/architecture_v14.md`

---

## Core Components

### 1. "Go With The Flow" Ruleset

These are non-negotiable principles that define production-grade quality:

#### Configuration Management
- **YAML/config-driven first**: All scenario, parameter, and pipeline configs use YAML with environment-sensitive overlays
- **Validation before execution**: Always validate configs and parameter ranges before compute
- **No magic values**: All defaults must be explicit and documented

#### Code Architecture
- **Defensive programming**: Validate all inputs, handle all error cases gracefully
- **Batch/CLI friendly**: No function has hardcoded paths or states. Inputs/outputs routed by argument or env variable
- **Stateless APIs and results**: Any analytic/result must be callable/reproducible by REST UI and script
- **Test-first design**: All analytics (sensitivity, Monte Carlo, batch, export) are tested by docstring/example/test scaffolds

#### Development Standards
- **Type hints everywhere**: Full mypy compliance, no `Any` types without justification
- **Contract-driven**: Clear interfaces between modules using dataclasses or Pydantic
- **Mutation-averse**: Prefer immutable data structures, avoid side effects
- **Lint-clean**: flake8, black, isort compliance mandatory

---

### 2. Technical Notebook — Proven Patterns

#### YAML Handling
```python
import yaml
from pathlib import Path
from typing import Any, Dict

def load_config(path: Path) -> Dict[str, Any]:
    """Load YAML config with proper error handling."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except (IOError, yaml.YAMLError) as e:
        raise ConfigurationError(f"Failed to load {path}: {e}")
```

#### Validation Pattern
```python
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class ParameterRange:
    """Define valid parameter ranges."""
    name: str
    min_val: float
    max_val: float
    default: float
    unit: str
    description: str

def validate_parameter_ranges(
    config: Dict[str, Any],
    params: Dict[str, float]
) -> pd.DataFrame:
    """Validate parameters against defined ranges.

    Returns:
        DataFrame with validation results (errors if any)
    """
    errors = []
    for name, value in params.items():
        if name not in config['parameter_ranges']:
            errors.append({
                'parameter': name,
                'error': 'Unknown parameter',
                'value': value
            })
            continue

        range_def = config['parameter_ranges'][name]
        if not (range_def['min'] <= value <= range_def['max']):
            errors.append({
                'parameter': name,
                'error': f"Value {value} outside range [{range_def['min']}, {range_def['max']}]",
                'value': value
            })

    return pd.DataFrame(errors)
```

#### CLI Wrapper Pattern
```python
import argparse
from pathlib import Path
import sys

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Run DutchBay EPC Model analytics'
    )
    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help='Path to scenario YAML config'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('exports'),
        help='Output directory for results'
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
        results = run_analytics(config)
        save_results(results, args.output_dir)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

#### Export Pattern
```python
from datetime import datetime
from pathlib import Path
import pandas as pd

def save_results(
    results: pd.DataFrame,
    output_dir: Path,
    run_name: Optional[str] = None
) -> Path:
    """Save results with unique timestamped filename.

    Never overwrites existing files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if run_name is None:
        run_name = datetime.now().strftime('%Y%m%d_%H%M%S')

    output_path = output_dir / f"results_{run_name}.csv"

    # Ensure unique filename
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"results_{run_name}_{counter}.csv"
        counter += 1

    results.to_csv(output_path, index=False)
    return output_path
```

---

### 3. Active Development Roadmap

#### Phase 1: Foundation (COMPLETE ✅)
- [x] Publish/validate scenario loader and YAML driver configs
- [x] Expose core analytics (summary, cashflow, kpis)
- [x] Basic test coverage for contracts

#### Phase 2: Interactive Analytics (IN PROGRESS 🔄)
- [ ] Make tornado/sensitivity available via Streamlit
- [ ] Make Monte Carlo available via Streamlit
- [ ] Validation (guard) available as REST API
- [ ] Basic Streamlit dashboard with parameter inputs

#### Phase 3: Reporting & Export (PLANNED 📋)
- [ ] End-to-end Excel export with formatted sheets
- [ ] Markdown report generation with charts
- [ ] PNG chart export for presentations
- [ ] Health/audit tracking UI

#### Phase 4: Advanced Features (PLANNED 📋)
- [ ] Scenario comparison/audit dashboard
- [ ] Multi-objective optimizer
- [ ] Version history and rollback
- [ ] User notes and annotations

#### Phase 5: Stakeholder Deliverables (PLANNED 📋)
- [ ] DFI/Lender presentation mode
- [ ] Board presentation templates
- [ ] Executive summary auto-generation
- [ ] Risk heatmaps and dashboards

#### Technical Debt Tracking
- [ ] Remove/merge any legacy handler code
- [ ] Document all module entrypoints
- [ ] Complete OpenAPI doc for REST facade
- [ ] Add integration tests for full pipeline
- [ ] Performance profiling for Monte Carlo

---

### 4. Diagnostic Checklists

#### Pre-Commit Checks
```bash
# Validate all YAML files
find . -name '*.yaml' -o -name '*.yml' | xargs yamllint

# Or in Python
python -c 'import yaml; yaml.safe_load(open("scenarios/scenario.yaml"))'
```

#### Parameter Validation
```python
from analytics.validation import validate_parameter_ranges

config = load_config('scenarios/scenario.yaml')
params = config['parameters']
errors = validate_parameter_ranges(config, params)

if not errors.empty:
    print("Validation errors:")
    print(errors)
    sys.exit(1)
```

#### Integration Smoke Test
```bash
# Run all core tests
pytest tests/contracts/ -v

# Run analytics tests
pytest tests/analytics/ -v

# Check exports
ls -lh exports/
```

#### Batch Processing Verification
```bash
# Ensure all outputs go to exports/ with unique names
python analytics/run_full_pipeline.py --config scenarios/base.yaml

# Check no overwrites occurred
find exports/ -type f -name "*.csv" -o -name "*.xlsx" | wc -l
```

---

### 5. Command Reference

#### Core Operations
```bash
# Run scenario analysis
python analytics/run_full_pipeline.py --config scenarios/scenario.yaml

# Run sensitivity analysis
python analytics/sensitivity_v14.py --config scenarios/base.yaml --output exports/

# Launch Streamlit dashboard
streamlit run dashboard/streamlit_app.py

# Serve REST API
uvicorn api.sensitivity_api:app --reload --port 8000
```

#### Testing & Quality
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=analytics --cov=finance --cov-report=html

# Type checking
mypy analytics/ finance/

# Linting
flake8 analytics/ finance/
black --check analytics/ finance/
isort --check-only analytics/ finance/
```

#### Git Workflow
```bash
# Create feature branch
git checkout -b feature/xyz

# Make changes and commit
git add .
git commit -am "feat: Add XYZ functionality"

# Push and create PR
git push -u origin feature/xyz
```

#### Deployment
```bash
# Pull latest changes
git pull origin main

# Install/update dependencies
pip install -r requirements.txt

# Restart application (if using supervisor)
sudo supervisorctl restart epc-app
```

---

### 6. Project Structure Reference

```
dutchbay-epc-model/
├── analytics/              # Core analytics modules
│   ├── foundation.py       # Base model foundation (DO NOT RENAME)
│   ├── sensitivity/        # Sensitivity analysis modules
│   │   └── contracts_v14.py
│   ├── monte_carlo/        # Monte Carlo simulation
│   └── reporting/          # Report generation
├── finance/                # Financial calculation modules
│   ├── debt_v14.py        # Debt modeling and DSCR
│   ├── equity_v14.py      # Equity returns (IRR, NPV)
│   ├── cashflow_v14.py    # Cash flow projections
│   └── tax.py             # Tax calculations
├── config/                 # Configuration schemas
│   └── schema.yaml        # Parameter definitions
├── scenarios/              # Scenario YAML files
│   ├── base.yaml          # Base case scenario
│   ├── optimistic.yaml    # Upside scenario
│   └── pessimistic.yaml   # Downside scenario
├── exports/                # Output directory (git-ignored)
│   ├── *.csv
│   ├── *.xlsx
│   └── *.png
├── tests/                  # Test suite
│   ├── contracts/         # Contract tests
│   ├── analytics/         # Analytics tests
│   └── integration/       # Integration tests
├── docs/                   # Documentation
│   ├── THREAD_MIGRATION_PACKAGE.md  # This file
│   ├── architecture_v14.md
│   └── Dev_workflow_v14.md
└── dashboard/              # Streamlit UI (future)
    └── streamlit_app.py
```

**Critical Note**: `analytics/foundation.py` is the base script that other refactored modules may build on. **Do not rename or move it.**

---

### 7. Anti-Patterns (AVOID)

#### ❌ Hardcoded Paths
```python
# BAD
def load_data():
    return pd.read_csv('/Users/john/project/data.csv')

# GOOD
def load_data(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)
```

#### ❌ Unvalidated Configs
```python
# BAD
config = yaml.safe_load(open('config.yaml'))
value = config['parameters']['rate']  # May not exist!

# GOOD
from dataclasses import dataclass
from typing import Dict

@dataclass
class Config:
    parameters: Dict[str, float]

    @classmethod
    def from_yaml(cls, path: Path) -> 'Config':
        data = yaml.safe_load(open(path))
        # Validate structure
        if 'parameters' not in data:
            raise ValueError("Missing 'parameters' key")
        return cls(**data)
```

#### ❌ Mutable Global State
```python
# BAD
GLOBAL_CONFIG = {}

def set_config(config):
    global GLOBAL_CONFIG
    GLOBAL_CONFIG = config

# GOOD - Pass explicitly
def run_analysis(config: Config) -> Results:
    # Use config directly, no globals
    pass
```

#### ❌ Export Overwrites
```python
# BAD
results.to_csv('output.csv')  # Overwrites previous run!

# GOOD
from datetime import datetime
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
results.to_csv(f'exports/output_{timestamp}.csv')
```

---

## Success Metrics

Your implementation meets standards when:

### Code Quality
- ✅ All tests pass (`pytest tests/` shows 100% pass rate)
- ✅ Type checking passes (`mypy analytics/ finance/` shows no errors)
- ✅ Linting passes (`flake8`, `black --check`, `isort --check-only`)
- ✅ Code coverage > 80% for critical modules

### Functionality
- ✅ API/UI publish all key analytics (sensitivity, Monte Carlo, cashflow)
- ✅ Scenario can be re-run with identical results (reproducibility)
- ✅ All outputs saved to `exports/` with unique names (no overwrites)
- ✅ CLI works without hardcoded paths (can run from any directory)

### Documentation
- ✅ All public functions have docstrings with type hints
- ✅ README contains quick start guide
- ✅ API endpoints documented (OpenAPI/Swagger)
- ✅ Example scenarios in `scenarios/` directory

---

## Environment Setup

### Python Virtual Environment
```bash
# Create virtual environment
python3.11 -m venv .venv311

# Activate (macOS/Linux)
source .venv311/bin/activate

# Activate (Windows)
.venv311\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_dev.txt
```

### Development Tools
```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Environment Variables
```bash
# Set model environment
export MODEL_ENV=development

# Set output directory
export EPC_OUTPUT_DIR=./exports

# Set log level
export LOG_LEVEL=INFO
```

---

## References & Further Reading

### Project Documentation
- [Architecture Overview](./architecture_v14.md)
- [Development Workflow](./Dev_workflow_v14.md)
- [Analytics Setup](./ANALYTICS_SETUP_COMPLETE.md)
- [Production Readiness](./ANALYTICS_PRODUCTION_READY.md)

### Python in Finance Best Practices
- [Python for Finance](https://www.oreilly.com/library/view/python-for-finance/9781492024323/)
- [Financial Modeling with Python](https://www.manning.com/books/financial-modeling-with-python)
- [Quantitative Finance with Python](https://www.crcpress.com/Quantitative-Finance-with-Python/Fletcher/p/book/9781032014258)

### YAML & Config Management
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [Pydantic for Settings Management](https://pydantic-docs.helpmanual.io/usage/settings/)
- [Hydra for Config Composition](https://hydra.cc/)

### Testing & Quality
- [pytest Documentation](https://docs.pytest.org/)
- [mypy Type Checking](https://mypy.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)

### Project Structuring
- [Python Project Structure](https://docs.python-guide.org/writing/structure/)
- [Cookiecutter Data Science](https://drivendata.github.io/cookiecutter-data-science/)
- [Clean Code in Python](https://www.packtpub.com/product/clean-code-in-python/9781800560215)

---

## Version History

### v1.0 (2025-11-24)
- Initial thread migration package
- Core "Go with the Flow" ruleset established
- Technical patterns documented
- Command reference completed
- Project structure defined

---

## How to Use This Document

### For AI Assistants
1. At the start of each new thread/session, receive this context
2. Apply "Go with the Flow" rules to all code generation
3. Reference technical patterns for implementation details
4. Check success metrics before considering work complete
5. Update this document if patterns evolve

### For Developers
1. Read through entire document during onboarding
2. Bookmark for quick reference during development
3. Use command reference for daily tasks
4. Consult anti-patterns when reviewing code
5. Update roadmap as features complete

### For Project Leads
1. Use success metrics for quality gates
2. Track progress against roadmap
3. Reference when defining new features
4. Update as project standards evolve

---

**Paste this package into ANY new thread for seamless resumption and "always compliant" Go with the Flow work quality!**
