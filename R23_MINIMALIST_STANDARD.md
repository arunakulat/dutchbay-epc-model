# R23 + CASPER/CESSPIT + CCCDIR - Minimalist Standard

**Rule:** R23 (Branch-based dev) + CASPER/CESSPIT (Script framework) + CCCDIR (Code standard)
**Status:** 🟢 ACTIVE  
**Date:** December 17, 2025, 00:48 IST

---

## 📋 DOCUMENTATION PHILOSOPHY

### External Documentation: MINIMAL
- ✅ Quick start card only (this document)
- ✅ R23 workflow reference (1 page)
- ❌ No detailed guides (documentation IN scripts)
- ❌ No separate tutorials (examples IN scripts)

### Internal Documentation: COMPREHENSIVE
- ✅ **CASPER Comments** - Context, Action, Specifications in every script
- ✅ **CESSPIT Sections** - Clear logical flow: Config, Execute, Status, Summary, Process, Interface, Terminal
- ✅ **CCCDIR Code** - Concise, Clear, Correct, DRY, Idiomatic, Readable
- ✅ **Inline Examples** - Use cases shown in docstrings

---

## 🚀 R23 QUICK START (Minimalist)

### Setup (5 min)
```bash
cd DutchBay_EPC_Model
source .venv311/bin/activate
python dutchbay_bootstrap.py
pytest tests/api/ --no-cov -q && mypy . --quiet
```

### Workflow (4 steps)
```
1. Edit code (in feature branch)
2. pytest ✅ + mypy ✅
3. git commit + push
4. Wait CI → Merge → Cleanup
```

### Commit Message (R18)
```
type: what changed

- Detail
- Tests: passing
- Mypy: clean
```

---

## 📝 CASPER/CESSPIT Script Template

All Sprint 12 scripts MUST follow this pattern:

```python
#!/usr/bin/env python
"""Module description (1 line).

Detailed description with use cases.

Usage:
    python script.py --config path/to/config.yaml
    python script.py --n-iterations 10000

Context:
    - Runs in feature branch (R23)
    - Uses Hydra for config (ARCH-01)
    - Outputs JSON for automation (CLI-03)

Action:
    1. Load config via Hydra
    2. Validate schema (VAL-01)
    3. Execute core logic
    4. Export results (JSON + CSV)

Specifications:
    - Type hints: 100% (TYPE-01)
    - Tests: 8+ cases minimum
    - Mypy: clean (TYPE-01)
    - No argparse: Hydra only (CLI-01)
    - No storage: All in-memory (APP security)
"""

# CESSPIT Sections
# C: Config - Hydra setup, schema validation
# E: Execute - Core algorithm/logic
# S: Status - Progress logging, error handling
# S: Summary - Aggregate results
# P: Process - Main execution flow
# I: Interface - CLI entrypoint, arguments
# T: Terminal - Output formatting, JSON export

from typing import Any, Optional
from omegaconf import OmegaConf, DictConfig
import logging
import json

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> DictConfig:
    """Load and validate Hydra config.
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Validated OmegaConf DictConfig
        
    Raises:
        ValueError: If schema validation fails
        
    Example:
        >>> cfg = load_config('config/dutchbay.yaml')
        >>> cfg.financial.debt.principal_usd
        105000000.0
    """
    # C: CONFIG - Load config
    cfg = OmegaConf.load(config_path)
    
    # C: CONFIG - Validate schema
    from analytics.schema_guard import validate_config_for_v14
    validate_config_for_v14(cfg, strict=True)  # VAL-01 compliance
    
    return cfg


def execute_core_logic(cfg: DictConfig) -> dict[str, Any]:
    """Execute main algorithm.
    
    Args:
        cfg: Validated config
        
    Returns:
        Dictionary with results
        
    Example:
        >>> result = execute_core_logic(cfg)
        >>> result['project_irr']
        0.1788
    """
    # E: EXECUTE - Core logic
    # Implementation here
    results = {}
    return results


def summarize_results(results: dict) -> dict:
    """Aggregate results for output.
    
    Args:
        results: Raw results from execute_core_logic
        
    Returns:
        Summary statistics
    """
    # S: SUMMARY - Aggregate results
    summary = {
        'project_irr': results.get('irr'),
        'min_dscr': results.get('min_dscr'),
        'n_success': results.get('success_count'),
    }
    return summary


def main(config_path: str) -> None:
    """Main execution flow (CESSPIT Process).
    
    Args:
        config_path: Path to config YAML
    """
    # P: PROCESS - Main flow
    logger.info(f"Loading config: {config_path}")
    cfg = load_config(config_path)  # C: CONFIG
    
    logger.info("Executing core logic...")
    results = execute_core_logic(cfg)  # E: EXECUTE
    
    logger.info("Generating summary...")
    summary = summarize_results(results)  # S: SUMMARY + S: STATUS
    
    # T: TERMINAL - Output as JSON
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    # I: INTERFACE - Hydra CLI
    from hydra import main as hydra_main
    
    @hydra_main(config_path="conf", config_name="config", version_base="1.1")
    def cli(cfg: DictConfig) -> None:
        main(cfg.config_path)
    
    cli()
```

---

## 🎯 CCCDIR Code Standards

Every line of code must be:

| Standard | Definition | Example |
|----------|-----------|----------|
| **C** | Concise | `irr = npv_to_irr(cf)` not `irr_value_for_project = calculate_internal_rate_of_return_from_cashflows(cashflows)` |
| **C** | Clear | Variable names: `debt_principal_usd` not `dp` |
| **C** | Correct | Type hints: `def calc(x: float) -> float:` not `def calc(x):` |
| **D** | DRY | No repeated logic; extract functions |
| **I** | Idiomatic | Use Python conventions: `for item in items:` not `for i in range(len(items)):` |
| **R** | Readable | Max 88 chars/line (black formatter), meaningful names, docstrings |

---

## 📚 External Documentation Strategy

### What Gets External Docs?
- ❌ Script usage (IN script docstring)
- ❌ API examples (IN function examples)
- ❌ Troubleshooting (IN inline comments)
- ✅ Repository architecture (README.md - high level only)
- ✅ Git workflow (R23 summary - 1 page)
- ✅ Rule changes (go_with_the_flow_rules_v3_0_clean.csv - governance only)

### What's External for Reference Only?
- `README.md` - 10 lines describing what repo does
- `R23_WORKFLOW_SUMMARY.md` - 1 page git workflow
- `SPRINT_12_START.md` - This document only

---

## 🔍 Script Self-Documentation Pattern

Every Sprint 12 script follows this:

### Top of File
```python
"""1-line description.

Detailed description (2-3 paragraphs).

Usage:
    python script.py --config config.yaml
    python script.py --n-iterations 10000

Context: Why this script exists
Action: What it does
Specifications: Requirements
"""
```

### Per Function
```python
def function_name(arg: Type) -> ReturnType:
    """1-line summary.
    
    Detailed description.
    
    Args:
        arg: Description
        
    Returns:
        What gets returned
        
    Raises:
        ValueError: When this happens
        
    Example:
        >>> result = function_name(x)
        >>> result['key']
        'expected_value'
    """
    # Implementation
```

### Per Complex Logic Block
```python
# SECTION NAME: What this does
# Why: The business reason
# Algorithm: Brief description of approach
logic_here()
```

---

## 📋 Sprint 12 Modules (Self-Documented)

### Module 1: Refinancing
**File:** `finance/refinancing_v14_hydra.py`
- 💬 Docstring: Full usage + examples
- 💬 Class docstring: CASPER context/action/specs
- 💬 Inline comments: Algorithm steps
- ❌ No external docs needed

### Module 2: Equity Distribution
**File:** `finance/equity_distribution_v14_hydra.py`
- Same pattern as Module 1
- Self-contained documentation
- Examples in docstrings

### Module 3: Monte Carlo
**File:** `analytics/monte_carlo_v14.py`
- CASPER: Context (100K iterations), Action (LHS), Specs (converge)
- CESSPIT: Config (params), Execute (sampling), Summary (stats)
- CCCDIR: Clean, typed, DRY
- Examples: 3+ usage patterns in docstring

### Module 4: Stress Tests
**File:** `analytics/stress_tests_v14.py`
- Self-documented via docstrings
- Examples of each stress scenario in docs
- No separate guide needed

### Module 5: Pipeline CLI
**File:** `scripts/run_full_pipeline_sprint12.py`
- Help text in script: `python script.py --help`
- Docstring shows all use cases
- Examples integrated

---

## ✅ Documentation Checklist (Per Script)

- [ ] Module docstring: 1-line + 3-5 line description
- [ ] CASPER sections: Context, Action, Specifications clear
- [ ] Usage examples: In docstring
- [ ] Function docstrings: All public functions documented
- [ ] Type hints: 100% coverage
- [ ] Inline comments: Complex logic explained
- [ ] CCCDIR compliance: Code is concise, clear, correct, DRY, idiomatic, readable
- [ ] Examples: 2+ examples in main docstring
- [ ] Error cases: Documented in Raises section
- [ ] No external README needed: All info in script

---

## 🚀 Total Documentation Package

**External (Minimal):**
- ✅ This file (R23_MINIMALIST_STANDARD.md) - 1 file
- ✅ R23 workflow summary - 1 page
- ✅ README.md - 10 lines max

**Internal (Comprehensive):**
- ✅ 5 scripts with full CASPER/CESSPIT/CCCDIR docs
- ✅ 30+ functions with complete docstrings
- ✅ 15+ usage examples in code
- ✅ 100% type hints
- ✅ Strategic inline comments

---

## 📊 Comparison: Old vs New

| Aspect | Old Approach | New Approach (R23 + CASPER + CCCDIR) |
|--------|--------------|--------------------------------------|
| **External Docs** | 20+ pages | 3-5 pages (this + R23 summary + README) |
| **Script Docs** | Minimal | Comprehensive (CASPER/CESSPIT) |
| **Learning Curve** | Read docs → read code | Read script → understand everything |
| **Maintenance** | Update docs + code | Update code (docs auto-sync) |
| **Clarity** | Split between docs/code | All in one script |
| **Examples** | In separate docs | In script docstrings |

---

## 🎯 Your Workflow (Simplified)

### Phase 1: Development
```bash
# Edit script with full CASPER/CESSPIT/CCCDIR docs
vim finance/refinancing_v14_hydra.py

# Script itself IS the documentation
# No separate guide needed
```

### Phase 2: Testing
```bash
# Tests verify behavior (docstring examples work)
pytest tests/api/test_refinancing_v14.py --no-cov
mypy finance/refinancing_v14_hydra.py
```

### Phase 3: Commit
```bash
git commit -m "feat: add refinancing (CASPER/CESSPIT/CCCDIR)

- Full docstrings with examples
- Type hints: 100%
- Tests: 8 passing
- Mypy: clean"
```

### Phase 4: Done!
No external docs to write. The code IS the documentation.

---

## 💡 Key Principles

1. **Self-Documenting Code** - Read the script, understand everything
2. **CASPER Framework** - Context, Action, Specifications in every module
3. **CESSPIT Structure** - Config, Execute, Status, Summary, Process, Interface, Terminal
4. **CCCDIR Standards** - Concise, Clear, Correct, DRY, Idiomatic, Readable
5. **Minimal External Docs** - Only what can't be in code (architecture, git workflow)

---

## 🎉 Result

✅ **Less documentation overhead** - More time coding  
✅ **Better code quality** - Forced to be clear  
✅ **Easier maintenance** - No docs to update separately  
✅ **Faster onboarding** - Read code, understand it  
✅ **GWTF Compliant** - All rules followed automatically  

---

**Status:** 🟢 READY FOR MINIMALIST DEVELOPMENT  
**Rule:** R23 + CASPER + CESSPIT + CCCDIR  
**Documentation:** Internal in scripts, minimal external

**Let's build! 🚀**
