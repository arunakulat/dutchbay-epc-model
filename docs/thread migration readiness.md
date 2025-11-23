# DutchBay EPC Model - Thread Migration Package

**Project:** DutchBay 150MW Wind Farm Financial Model  
**Repository:** dutchbay-epc-model (GitHub)  
**Environment:** Python 3.11 (.venv311), macOS  
**Migration Date:** November 23, 2025

---

## 🎯 Quick Context Snippet (Copy/Paste to New Thread)

```
I'm continuing work on the DutchBay EPC Model—a production-grade DFI/Lender/EPC financial modeling suite for a 150MW wind farm in Sri Lanka. The project uses Python 3.11, YAML-driven configuration, and follows "Go With The Flow" standards: build once, build right, mypy-clean, AST-safe, lint-compliant. 

Active Sprint: Phase 1-5 pipeline hardening (YAML validation, batch processing, board-pack exports).

I need code that is: config-driven, defensive, batch-friendly, test-first, and production-ready with type hints and proper error handling.
```

---

## 📋 1. "GO WITH THE FLOW" RULESET

### Core Principles
**Build Once, Build Right** - Production-grade code from the start, no placeholder logic.

### 1.1 Configuration-Driven Architecture
```python
# ✅ CORRECT: YAML-driven, no hardcoded paths
from pathlib import Path
import yaml

def load_config(config_path: Path) -> dict[str, Any]:
    """Load and validate YAML configuration."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    validate_config(config)
    return config

# ❌ WRONG: Hardcoded paths
scenario_path = "/Users/john/project/scenarios/base.yaml"
```

### 1.2 Defensive Programming
```python
# ✅ CORRECT: Robust error handling with context
def process_scenario(scenario_data: dict[str, Any]) -> ScenarioResult:
    """Process scenario with validation and error context."""
    try:
        validate_scenario_structure(scenario_data)
        result = calculate_metrics(scenario_data)
        return result
    except KeyError as e:
        raise ValueError(f"Missing required field in scenario: {e}") from e
    except Exception as e:
        logger.error(f"Failed to process scenario: {e}")
        raise

# ❌ WRONG: Silent failures
def process_scenario(scenario_data):
    try:
        return calculate_metrics(scenario_data)
    except:
        pass  # Silent failure
```

### 1.3 Batch-Friendly Patterns
```python
# ✅ CORRECT: Batch processing with individual error handling
def run_batch_scenarios(
    scenario_paths: list[Path],
    output_dir: Path
) -> dict[str, ScenarioResult]:
    """Run multiple scenarios, continue on individual failures."""
    results = {}
    for path in scenario_paths:
        try:
            scenario = load_scenario(path)
            result = process_scenario(scenario)
            results[path.stem] = result
            logger.info(f"✓ Completed: {path.stem}")
        except Exception as e:
            logger.error(f"✗ Failed {path.stem}: {e}")
            results[path.stem] = ScenarioResult(status="failed", error=str(e))
    return results

# ❌ WRONG: Fail entire batch on first error
def run_batch_scenarios(scenario_paths):
    results = []
    for path in scenario_paths:
        results.append(process_scenario(load_scenario(path)))  # Crashes batch
    return results
```

### 1.4 Test-First Design
```python
# ✅ CORRECT: Testable, injectable dependencies
def calculate_wacc(
    equity_ratio: float,
    debt_ratio: float,
    cost_of_equity: float,
    cost_of_debt: float,
    tax_rate: float
) -> float:
    """Calculate weighted average cost of capital."""
    if not abs(equity_ratio + debt_ratio - 1.0) < 0.0001:
        raise ValueError("Equity + Debt ratios must equal 1.0")
    return (equity_ratio * cost_of_equity + 
            debt_ratio * cost_of_debt * (1 - tax_rate))

# Test
def test_wacc_calculation():
    wacc = calculate_wacc(0.7, 0.3, 0.12, 0.06, 0.28)
    assert abs(wacc - 0.0972) < 0.0001

# ❌ WRONG: Untestable, hardcoded values
def calculate_wacc():
    equity = CONFIG['equity']  # Global state
    return equity * 0.12 + (1-equity) * 0.06 * 0.72
```

### 1.5 Type Safety & Linting
```python
# ✅ CORRECT: Full type hints, mypy-compliant
from typing import Optional
from dataclasses import dataclass

@dataclass
class ScenarioConfig:
    name: str
    capacity_mw: float
    turbine_count: int
    capex_usd_per_kw: float
    discount_rate: Optional[float] = None

def validate_scenario(config: ScenarioConfig) -> bool:
    """Validate scenario configuration."""
    return config.capacity_mw > 0 and config.turbine_count > 0

# ❌ WRONG: No type hints
def validate_scenario(config):
    return config.capacity_mw > 0
```

### 1.6 Export & Document Generation
```python
# ✅ CORRECT: Metadata-rich exports with validation
from docx import Document
from datetime import datetime

def export_board_pack(
    scenario_result: ScenarioResult,
    output_path: Path,
    metadata: dict[str, str]
) -> None:
    """Generate board-ready document with cover page."""
    doc = Document()
    
    # Cover page with metadata
    doc.add_heading(f"Project: {metadata['project_name']}", 0)
    doc.add_paragraph(f"Scenario: {scenario_result.name}")
    doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph(f"Version: {metadata['version']}")
    
    # Financial summary
    doc.add_heading("Executive Summary", 1)
    add_financial_table(doc, scenario_result.financials)
    
    # Pre-save validation
    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True)
    
    doc.save(output_path)
    logger.info(f"✓ Exported board pack: {output_path}")

# ❌ WRONG: No metadata, no validation
def export_board_pack(result, path):
    doc = Document()
    doc.add_paragraph(str(result))
    doc.save(path)  # May crash if directory doesn't exist
```

---

## 📓 2. TECHNICAL NOTEBOOK

### 2.1 YAML Configuration Pattern
```python
# config/scenarios/base_case.yaml
scenario:
  name: "Base Case - 150MW"
  capacity_mw: 150
  turbine_count: 30
  turbine_model: "Vestas V150-5.0"
  
financial:
  capex:
    turbines_usd_per_kw: 850
    bop_usd_per_kw: 200
    grid_connection_usd: 15000000
  
  revenue:
    ppa_price_usd_per_mwh: 65
    annual_aep_gwh: 450
    degradation_rate: 0.005
  
  financing:
    equity_ratio: 0.70
    debt_ratio: 0.30
    debt_tenor_years: 15
    debt_interest_rate: 0.06
    cost_of_equity: 0.12
    tax_rate: 0.28

# Python loader with validation
from pathlib import Path
import yaml
from typing import Any

def load_scenario_config(path: Path) -> dict[str, Any]:
    """Load and validate scenario YAML configuration."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Validate required sections
    required_sections = ['scenario', 'financial']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section: {section}")
    
    # Validate numeric ranges
    scenario = config['scenario']
    if scenario.get('capacity_mw', 0) <= 0:
        raise ValueError("capacity_mw must be positive")
    
    return config
```

### 2.2 Batch Processing Pipeline
```python
# batch_processor.py
from pathlib import Path
from typing import Iterator
import logging

logger = logging.getLogger(__name__)

class BatchScenarioProcessor:
    """Process multiple scenarios with robust error handling."""
    
    def __init__(self, config_dir: Path, output_dir: Path):
        self.config_dir = config_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def discover_scenarios(self) -> list[Path]:
        """Find all YAML scenario files."""
        return sorted(self.config_dir.glob("*.yaml"))
    
    def process_batch(self) -> dict[str, Any]:
        """Process all scenarios, continue on failures."""
        scenarios = self.discover_scenarios()
        logger.info(f"Found {len(scenarios)} scenarios")
        
        results = {
            'successful': [],
            'failed': [],
            'summary': {}
        }
        
        for scenario_path in scenarios:
            scenario_name = scenario_path.stem
            try:
                config = load_scenario_config(scenario_path)
                result = self.run_scenario(config)
                self.export_results(scenario_name, result)
                
                results['successful'].append(scenario_name)
                results['summary'][scenario_name] = {
                    'status': 'success',
                    'npv': result.npv,
                    'irr': result.irr
                }
                logger.info(f"✓ {scenario_name}: NPV=${result.npv:,.0f} IRR={result.irr:.2%}")
                
            except Exception as e:
                results['failed'].append(scenario_name)
                results['summary'][scenario_name] = {
                    'status': 'failed',
                    'error': str(e)
                }
                logger.error(f"✗ {scenario_name}: {e}")
        
        self.generate_batch_report(results)
        return results
    
    def run_scenario(self, config: dict[str, Any]) -> ScenarioResult:
        """Run financial model for single scenario."""
        # Implementation here
        pass
    
    def export_results(self, name: str, result: ScenarioResult) -> None:
        """Export individual scenario results."""
        output_path = self.output_dir / f"{name}_results.json"
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
```

### 2.3 Financial Metrics Calculations
```python
# analytics/metrics.py
import numpy as np
from typing import Optional

def calculate_npv(
    cash_flows: list[float],
    discount_rate: float,
    initial_investment: float
) -> float:
    """Calculate Net Present Value."""
    if discount_rate < 0:
        raise ValueError("Discount rate must be non-negative")
    
    pv_cash_flows = sum(
        cf / (1 + discount_rate) ** (i + 1)
        for i, cf in enumerate(cash_flows)
    )
    return pv_cash_flows - initial_investment

def calculate_irr(
    cash_flows: list[float],
    initial_investment: float,
    guess: float = 0.1
) -> Optional[float]:
    """Calculate Internal Rate of Return using numpy."""
    full_cash_flows = [-initial_investment] + cash_flows
    try:
        irr = np.irr(full_cash_flows)
        return float(irr) if not np.isnan(irr) else None
    except Exception as e:
        logger.warning(f"IRR calculation failed: {e}")
        return None

def calculate_dscr(
    operating_cash_flow: float,
    debt_service: float
) -> float:
    """Calculate Debt Service Coverage Ratio."""
    if debt_service <= 0:
        raise ValueError("Debt service must be positive")
    return operating_cash_flow / debt_service

def calculate_lcoe(
    total_lifetime_costs: float,
    total_lifetime_generation_mwh: float
) -> float:
    """Calculate Levelized Cost of Energy ($/MWh)."""
    if total_lifetime_generation_mwh <= 0:
        raise ValueError("Total generation must be positive")
    return total_lifetime_costs / total_lifetime_generation_mwh
```

### 2.4 Document Generation Pattern
```python
# export/document_generator.py
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime

class BoardPackGenerator:
    """Generate professional board-ready documents."""
    
    def __init__(self, template_path: Optional[Path] = None):
        self.doc = Document(template_path) if template_path else Document()
    
    def add_cover_page(self, metadata: dict[str, str]) -> None:
        """Add professional cover page with metadata."""
        # Title
        title = self.doc.add_heading(metadata['project_name'], 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtitle
        subtitle = self.doc.add_paragraph(metadata['scenario_name'])
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.runs[0].font.size = Pt(16)
        
        # Metadata table
        self.doc.add_paragraph()  # Spacer
        table = self.doc.add_table(rows=5, cols=2)
        table.style = 'Light Grid Accent 1'
        
        metadata_rows = [
            ('Generated', datetime.now().strftime('%Y-%m-%d %H:%M')),
            ('Version', metadata.get('version', '1.0')),
            ('Author', metadata.get('author', 'DutchBay Team')),
            ('Status', metadata.get('status', 'Draft')),
            ('Confidentiality', 'Restricted')
        ]
        
        for i, (key, value) in enumerate(metadata_rows):
            table.rows[i].cells[0].text = key
            table.rows[i].cells[1].text = value
        
        self.doc.add_page_break()
    
    def add_executive_summary(self, result: ScenarioResult) -> None:
        """Add executive summary with key metrics."""
        self.doc.add_heading('Executive Summary', 1)
        
        # Key metrics in styled table
        self.doc.add_paragraph('Key Financial Metrics', style='Heading 2')
        table = self.doc.add_table(rows=6, cols=2)
        table.style = 'Medium Shading 1 Accent 1'
        
        metrics = [
            ('NPV (USD)', f"${result.npv:,.0f}"),
            ('IRR', f"{result.irr:.2%}"),
            ('Payback Period', f"{result.payback_years:.1f} years"),
            ('Min DSCR', f"{result.min_dscr:.2f}x"),
            ('LCOE', f"${result.lcoe:.2f}/MWh"),
            ('Equity IRR', f"{result.equity_irr:.2%}")
        ]
        
        for i, (metric, value) in enumerate(metrics):
            table.rows[i].cells[0].text = metric
            table.rows[i].cells[1].text = value
    
    def add_cash_flow_table(self, cash_flows: list[dict]) -> None:
        """Add detailed cash flow waterfall table."""
        self.doc.add_heading('Project Cash Flows', 1)
        
        # Create table with proper headers
        num_years = len(cash_flows)
        table = self.doc.add_table(rows=num_years + 1, cols=7)
        table.style = 'Light Grid'
        
        # Headers
        headers = ['Year', 'Revenue', 'OpEx', 'EBITDA', 'Debt Service', 'Tax', 'FCF']
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].font.bold = True
        
        # Data rows
        for i, cf in enumerate(cash_flows):
            row = table.rows[i + 1]
            row.cells[0].text = str(cf['year'])
            row.cells[1].text = f"${cf['revenue']:,.0f}"
            row.cells[2].text = f"${cf['opex']:,.0f}"
            row.cells[3].text = f"${cf['ebitda']:,.0f}"
            row.cells[4].text = f"${cf['debt_service']:,.0f}"
            row.cells[5].text = f"${cf['tax']:,.0f}"
            row.cells[6].text = f"${cf['fcf']:,.0f}"
    
    def save(self, output_path: Path) -> None:
        """Save document with validation."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(output_path)
        logger.info(f"✓ Document saved: {output_path}")
```

---

## ✅ 3. ACTIVE TO-DO LIST

### Phase 1: Pipeline Hardening (IMMEDIATE)
- [ ] **YAML Validation Suite**
  - [ ] Schema validation for all scenario configs
  - [ ] Range checks on financial parameters
  - [ ] Cross-field validation (e.g., equity + debt = 1.0)
  - [ ] Friendly error messages with line numbers

- [ ] **Batch Processing Robustness**
  - [ ] Fix any remaining `self.save()` typos
  - [ ] Ensure per-scenario error isolation
  - [ ] Add progress indicators for long batches
  - [ ] Generate batch summary report (success/fail counts)

- [ ] **Board Pack Export**
  - [ ] Implement cover page with metadata
  - [ ] Add executive summary section
  - [ ] Include cash flow waterfall tables
  - [ ] Add sensitivity analysis charts
  - [ ] Pre-export validation checks

### Phase 2: Testing & Validation (THIS WEEK)
- [ ] **Unit Tests**
  - [ ] Test WACC calculation edge cases
  - [ ] Test NPV/IRR with known scenarios
  - [ ] Test DSCR calculation boundary conditions
  - [ ] Test YAML loading with malformed files

- [ ] **Integration Tests**
  - [ ] End-to-end scenario batch test
  - [ ] Validate all exports generated correctly
  - [ ] Test with missing optional parameters
  - [ ] Test with extreme parameter values

- [ ] **Edge Case Testing**
  - [ ] Zero debt scenarios
  - [ ] Negative cash flows
  - [ ] Very high/low discount rates
  - [ ] Missing YAML sections

### Phase 3: Advanced Features (NEXT SPRINT)
- [ ] **Monte Carlo Simulation**
  - [ ] Implement probability distributions for key inputs
  - [ ] Run 1000+ iterations per scenario
  - [ ] Generate P10/P50/P90 outputs
  - [ ] Visualize risk distributions

- [ ] **Sensitivity Analysis**
  - [ ] Tornado diagrams for parameter sensitivity
  - [ ] Two-way sensitivity tables
  - [ ] Break-even analysis
  - [ ] Export to board pack

- [ ] **Scenario Comparison**
  - [ ] Side-by-side metric comparison
  - [ ] Delta analysis between scenarios
  - [ ] Ranking and optimization
  - [ ] Export comparison matrix

### Phase 4: Performance & Scale (MEDIUM TERM)
- [ ] **Optimization**
  - [ ] Profile batch processing performance
  - [ ] Implement caching for repeated calculations
  - [ ] Parallelize independent scenarios
  - [ ] Optimize memory usage for large batches

- [ ] **Documentation**
  - [ ] API documentation (docstrings → Sphinx)
  - [ ] User guide for scenario creation
  - [ ] Troubleshooting guide
  - [ ] Code architecture diagram

### Phase 5: Integration & Deployment (LONG TERM)
- [ ] **CI/CD Pipeline**
  - [ ] GitHub Actions for automated testing
  - [ ] Lint and mypy checks on PR
  - [ ] Automated test coverage reporting
  - [ ] Release versioning automation

- [ ] **External Integrations**
  - [ ] Excel/CSV import for legacy models
  - [ ] Power BI / Tableau export formats
  - [ ] API endpoints for web dashboard
  - [ ] Database persistence layer

### Known Technical Debt
- [ ] Refactor legacy modules to "Go With The Flow" standards
- [ ] Consolidate duplicate error handling patterns
- [ ] Standardize logging format across modules
- [ ] Remove any remaining hardcoded paths/values
- [ ] Update all docstrings to Google style

---

## 🔍 4. DIAGNOSTIC CHECKLISTS

### 4.1 YAML Troubleshooting
**Symptom:** Scenario fails to load

**Checklist:**
1. ✓ File exists at specified path?
2. ✓ Valid YAML syntax (use online validator)?
3. ✓ All required sections present (scenario, financial)?
4. ✓ No tab characters (use spaces only)?
5. ✓ Numeric values not quoted?
6. ✓ Indentation consistent (2 or 4 spaces)?
7. ✓ No duplicate keys in same section?
8. ✓ Float values use decimal point (0.5 not ,5)?

**Common Fixes:**
```yaml
# ❌ WRONG: Tabs, inconsistent indentation
scenario:
	name: "Test"
  capacity_mw: "150"  # Should not be quoted

# ✅ CORRECT: Spaces, consistent, proper types
scenario:
  name: "Test"
  capacity_mw: 150
```

### 4.2 Python Integration Troubleshooting
**Symptom:** Module import errors or type errors

**Checklist:**
1. ✓ Virtual environment activated (.venv311)?
2. ✓ All dependencies installed (`pip install -r requirements.txt`)?
3. ✓ Working directory is project root?
4. ✓ `__init__.py` files in all package directories?
5. ✓ Type hints consistent with mypy strict mode?
6. ✓ No circular imports?
7. ✓ Python version 3.11+?

**Common Fixes:**
```bash
# Activate virtual environment
source .venv311/bin/activate

# Verify Python version
python --version  # Should show 3.11.x

# Reinstall dependencies
pip install -r requirements.txt

# Run mypy to catch type errors
mypy --strict src/
```

### 4.3 Batch Processing Troubleshooting
**Symptom:** Batch job fails or produces incomplete results

**Checklist:**
1. ✓ All scenario files valid individually?
2. ✓ Output directory exists and writable?
3. ✓ Sufficient disk space for exports?
4. ✓ Error logging enabled?
5. ✓ Each scenario isolated (no shared state)?
6. ✓ Progress tracking functional?
7. ✓ Failed scenarios logged separately?

**Debugging Commands:**
```bash
# Test single scenario first
python -m src.main --scenario config/scenarios/base_case.yaml

# Run batch with verbose logging
python -m src.main --batch config/scenarios/ --log-level DEBUG

# Check failed scenarios
cat logs/batch_failures.log

# Verify outputs generated
ls -lh output/scenarios/
```

### 4.4 Export Generation Troubleshooting
**Symptom:** Documents fail to generate or are malformed

**Checklist:**
1. ✓ python-docx library installed?
2. ✓ Output path directory exists?
3. ✓ No special characters in filename?
4. ✓ Template file accessible (if used)?
5. ✓ All result data present before export?
6. ✓ Tables have valid row/column counts?
7. ✓ No None values in formatted strings?

**Common Fixes:**
```python
# Pre-export validation
def safe_export(result: ScenarioResult, path: Path) -> None:
    # Validate data completeness
    if result.npv is None:
        raise ValueError("NPV not calculated")
    
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate document
    try:
        doc = generate_document(result)
        doc.save(path)
        logger.info(f"✓ Exported: {path}")
    except Exception as e:
        logger.error(f"✗ Export failed: {e}")
        raise
```

---

## 💻 5. COMMAND REFERENCE

### Development Commands
```bash
# Activate virtual environment
source .venv311/bin/activate

# Install/update dependencies
pip install -r requirements.txt
pip freeze > requirements.txt  # Update after adding packages

# Run linting
flake8 src/ --max-line-length=100
black src/ --check  # Formatting check
black src/  # Auto-format

# Type checking
mypy --strict src/
mypy --strict src/ --no-error-summary  # Clean output

# Run tests
pytest tests/ -v
pytest tests/ -v --cov=src  # With coverage
pytest tests/test_wacc.py -k "test_edge_cases"  # Specific test

# Run main application
python -m src.main --scenario config/scenarios/base_case.yaml
python -m src.main --batch config/scenarios/
python -m src.main --batch config/scenarios/ --output results/
```

### Git Workflow
```bash
# Status check
git status
git diff  # See changes

# Commit changes
git add src/analytics/metrics.py
git commit -m "feat: add LCOE calculation with validation"

# Push to GitHub
git push origin main

# Create feature branch
git checkout -b feature/monte-carlo-simulation
git push -u origin feature/monte-carlo-simulation

# Sync with remote
git pull origin main
git fetch --all
```

### File Management
```bash
# Create project structure
mkdir -p config/scenarios output/reports logs tests

# Find files
find . -name "*.yaml" -type f
find src/ -name "*.py" | xargs wc -l  # Line count

# Archive project (excluding venv)
zip -r dutchbay_backup.zip . -x "*.venv311/*" "*.git/*" "*__pycache__/*"

# Check file sizes
du -sh output/*
du -sh .venv311  # Virtual environment size
```

### Debugging Commands
```bash
# Interactive Python session
python -i -m src.main  # Load modules interactively

# Profile performance
python -m cProfile -o profile.stats -m src.main --batch config/scenarios/
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumtime').print_stats(20)"

# Check logs
tail -f logs/application.log
grep "ERROR" logs/application.log
grep "✗" logs/batch_processing.log  # Failed scenarios

# Environment info
python --version
pip list | grep -E "(numpy|pandas|pyyaml|python-docx)"
which python  # Verify virtual environment
```

---

## 🚀 6. HOW TO USE THIS MIGRATION PACKAGE

### In a New AI Thread

**Option A: Full Context (Comprehensive Projects)**
```
I'm continuing work on DutchBay EPC Model. Please review the complete migration package I'm pasting below and acknowledge understanding of:
1. "Go With The Flow" ruleset
2. Current technical notebook patterns
3. Active to-do list priorities
4. Diagnostic procedures

[Paste entire document]
```

**Option B: Quick Start (Focused Tasks)**
```
I'm working on DutchBay EPC Model using Python 3.11 on macOS. 

Context:
- Production-grade financial modeling suite (150MW wind farm)
- YAML-driven config, mypy-strict, test-first
- "Go With The Flow" standards: defensive, batch-friendly, no placeholders

Current Sprint: [Paste relevant Phase from To-Do List]

I need help with: [Your specific task]

Coding standards: [Paste relevant section from Ruleset]
```

**Option C: Troubleshooting Mode**
```
I'm debugging [specific issue] in DutchBay EPC Model.

Project standards: [Paste Quick Context Snippet]

Error: [Your error message]

Relevant diagnostic checklist: [Paste relevant checklist from Section 4]

What I've tried: [Your debugging steps]
```

### Updating This Document
As your project evolves, update this migration package:

1. **Add New Patterns** - When you establish a new proven code pattern, add it to Section 2 (Technical Notebook)
2. **Update To-Do List** - Mark completed items ✓, add new priorities
3. **Expand Ruleset** - Document new standards or anti-patterns discovered
4. **Add Diagnostics** - After solving a tricky bug, add troubleshooting steps to Section 4
5. **Version Control** - Commit this document to your repo: `docs/thread_migration.md`

---

## 📊 7. PROJECT SUCCESS METRICS

### Code Quality Metrics
- ✓ 100% mypy strict compliance (no errors, no `type: ignore`)
- ✓ Flake8 clean (max line length 100)
- ✓ All functions have type hints and docstrings
- ✓ Black formatted (consistent style)
- ✓ No hardcoded paths or magic numbers

### Functionality Metrics
- ✓ All scenarios process successfully in batch mode
- ✓ Exports generated with proper metadata and formatting
- ✓ Error handling provides actionable messages
- ✓ Results validated against known test cases

### Performance Metrics
- ✓ Single scenario processes in < 5 seconds
- ✓ 30-scenario batch completes in < 3 minutes
- ✓ Document export in < 2 seconds per scenario
- ✓ Memory usage stable across batches

### Test Coverage Metrics
- ✓ Unit test coverage > 80%
- ✓ All financial calculation functions have edge case tests
- ✓ Integration tests cover happy path and failure modes
- ✓ CI pipeline passes on all commits

---

## 🎯 END OF MIGRATION PACKAGE

**Document Version:** 1.0  
**Last Updated:** November 23, 2025  
**Maintained By:** DutchBay Project Team

**Usage Note:** This document represents the collective knowledge, standards, and working context accumulated through intensive development on the DutchBay EPC Model. It is designed to be pasted into new AI threads to instantly restore full project understanding and ensure consistent, production-quality code generation.

**Next Steps:**
1. Copy relevant sections to your new thread
2. Continue with current sprint priorities (Phase 1-5)
3. Update this document as patterns evolve
4. Commit to repo for team reference
