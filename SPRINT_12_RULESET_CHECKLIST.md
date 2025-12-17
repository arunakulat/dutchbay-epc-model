# SPRINT 12 RULESET CHECKLIST - DEVELOPMENT RULES

**Date:** December 17, 2025, 00:58 IST  
**Status:** 🟢 ACTIVE - ENFORCED FOR ALL CODE
**Rule Set:** v3.0 (Go-with-the-Flow)

---

## 🚨 CRITICAL ARCHITECTURAL RULES (For Every Script)

### 1. CONFIG-FIRST (ARCH-01, R2)
- ✅ **Hydra only** - All config via YAML/JSON, loaded by Hydra
- ✅ **No argparse** - BANNED repo-wide (R3, CLI-01)
- ✅ **No AST parsing** - No sys.argv manipulation
- ✅ **No hardcoded magic numbers** - Everything in conf/*.yaml

**Enforcement:**
```bash
LibCST tests ban argparse imports anywhere
LibCST tests ban Typer/Click in v14 scripts
```

### 2. CLI STRUCTURE (CLI-01, CLI-02, ADD-03)
- ✅ **Hydra-based entrypoints** - Use `@hydra.main` decorator
- ✅ **JSON output to stdout** - CLI-03 compliance
- ✅ **Config validation** - Call validate_config_for_v14 in strict mode (VAL-01, R5)
- ✅ **Schema guard enforcement** - R5, R22 always use strict=True

**Example:**
```python
from hydra import main as hydra_main
from omegaconf import DictConfig
from analytics.schema_guard import validate_config_for_v14

@hydra_main(config_path="conf", config_name="config", version_base="1.1")
def main(cfg: DictConfig) -> None:
    # Validate config in STRICT mode (R5, R22)
    validate_config_for_v14(cfg, strict=True)
    
    # Implementation
    results = process(cfg)
    
    # Output JSON (CLI-03)
    import json
    print(json.dumps(results, indent=2))
```

### 3. TYPE SAFETY (TYPE-01, R15)
- ✅ **100% type hints** - Every parameter, return, variable
- ✅ **Mypy clean** - Zero mypy errors before push
- ✅ **No broad Any** - Use TypedDict/Protocol for dicts
- ✅ **No untyped imports** - All imports typed

**Enforcement:**
```bash
pytest --no-cov  # Must pass
mypy . --quiet    # Must be clean
pre-commit hooks: mypy runs automatically
```

### 4. TESTING (TEST-01, TEST-02, R8, R11)
- ✅ **8+ tests per module** - Minimum coverage
- ✅ **Schema guard tests** - R22 compliance
- ✅ **Regression pins** - Key outputs pinned (TEST-01)
- ✅ **Fast-lane CI** - Use --no-cov locally, full coverage in CI

**Test Structure:**
```python
def test_module_basic():
    """Test basic functionality."""
    cfg = load_config('conf/scenarios/test_basic.yaml')
    result = function(cfg)
    assert result['key'] == expected_value  # REGRESSION PIN

def test_schema_guard_validation():
    """Test R22: Schema guard catches invalid configs."""
    bad_cfg = {'missing': 'fx'}  # No FX config
    with pytest.raises(ValueError):
        validate_config_for_v14(bad_cfg, strict=True)  # R5 strict mode
```

---

## 🔠 FINANCIAL LOGIC RULES (FIN-01, FIN-02, R7, R9, ARCH-03)

### 1. IRR/NPV ISOLATION (R7, ARCH-02)
- ✅ **Import from finance.irr only** - Never redefine IRR/NPV
- ✅ **No numerical instability** - Handle non-convergence gracefully
- ✅ **Return None for failures** - Log and don't crash

**Enforcement:**
```bash
LibCST tests ban IRR/NPV definitions outside finance/irr.py
```

**Usage:**
```python
from finance.irr import irr, npv  # ONLY source

irr_value = irr(cashflows, guess=0.1)
if irr_value is None:
    logger.warning("IRR did not converge; using safe default")
    irr_value = 0.0
```

### 2. UNITS & NAMING (FIN-02)
- ✅ **Explicit unit suffixes** - *_pct, *_years, *_usd, *_lkr
- ✅ **No ambiguous scalars** - 5 vs 0.05 must be clear
- ✅ **Schema enforces naming** - Code review checks

**Valid:**
```yaml
discount_rate_pct: 10.0        # Clear: percentage
construction_period_years: 5   # Clear: years
debt_principal_usd: 100000000  # Clear: USD
fx_rate_lkr_per_usd: 325.50    # Clear: LKR per USD
```

### 3. TRANCHE AWARENESS (R9, ARCH-03)
- ✅ **debt_v14.plan_debt returns tranches** - lkr, usd, dfi keys
- ✅ **Aggregates available** - total_idc, etc.
- ✅ **Legacy keys deprecated** - Don't use debt_outstanding

**Result Structure:**
```python
result = {
    'tranches': {
        'lkr': {'principal': X, 'idc': Y},
        'usd': {'principal': A, 'idc': B},
    },
    'total_idc': Y + B,
    'total_principal': X + A,
}
```

---

## 📋 DOCUMENTATION RULES (DOC-01, DOC-02, R17)

### 1. CASPER/CESSPIT Framework
- ✅ **Module docstring** - Context, Action, Specifications
- ✅ **CESSPIT structure** - Config, Execute, Status, Summary, Process, Interface, Terminal
- ✅ **Function docstrings** - Google-style: Args, Returns, Raises, Example
- ✅ **Type hints in docs** - Document types in signature

### 2. Inline Comments (R17)
- ✅ **Meaningful only** - No obvious comments
- ✅ **Complex logic explained** - Why, not what
- ✅ **Business rules documented** - Why validation matters

### 3. Model Change Log (DOC-02)
- ✅ **Update VERSION** - If financial logic changes
- ✅ **Update CHANGELOG** - If IRR/DSCR/NPV/covenant logic changes
- ✅ **Update regression tests** - If financial output changes

---

## 🔍 VALIDATION RULES (VAL-01, VAL-02, R5, R22)

### 1. Schema Guard (R5, R22)
- ✅ **Always strict=True** - No bypasses
- ✅ **FX mapping required** - fx.start_lkr_per_usd + fx.annual_depr
- ✅ **Tax rate required** - corporate_tax_pct via approved paths
- ✅ **Fail fast** - Invalid configs error immediately

**Implementation:**
```python
from analytics.schema_guard import validate_config_for_v14

# R5: Always strict (R22 compliance)
validate_config_for_v14(cfg, strict=True)
# Raises ValueError if FX or tax missing
```

### 2. Batch Handling (VAL-02)
- ✅ **Never crash on bad scenario** - Skip and log
- ✅ **Report failures explicitly** - n_success, n_failed
- ✅ **Expose error reasons** - Debug via logs

---

## 🌟 PRE-COMMIT & CI RULES (R10, R21)

### 1. Pre-Commit Hooks (R10)
```bash
# Run BEFORE git commit (automatic)
black .                 # Format code
ruff check .            # Lint
isort .                 # Sort imports
mypy . --quiet          # Type check
```

### 2. Local Development Workflow (R21)
```bash
# 1. Bootstrap
cd DutchBay_EPC_Model
source .venv311/bin/activate
python dutchbay_bootstrap.py  # ✅ Green

# 2. Test locally (--no-cov for speed)
pytest tests/api/test_module.py --no-cov
mypy . --quiet

# 3. Commit (pre-commit hooks run)
git add file.py
git commit -m "feat: description

- Detail 1
- Tests: 8 passing
- Mypy: clean"

# 4. Push to feature branch (NOT main)
git push origin feature/sprint12-monte-carlo

# 5. Wait for GitHub CI
# - pytest: full suite
# - mypy: strict
# - linting: ruff + black
# - LibCST lint: no argparse/Typer/AST
```

---

## 📋 R23 WORKFLOW (CRITICAL)

**NEVER commit directly to main.**

```
1. Branch: git checkout -b feature/sprint12-monte-carlo (DONE)
2. Develop: Edit + test locally until pytest ✅ + mypy ✅
3. Commit: git commit -m "type: summary" (R18)
4. Push: git push origin feature/sprint12-monte-carlo
5. GitHub CI: pytest, mypy, linting, LibCST
6. Review: Code review (human or auto)
7. Merge: Merge when all green
8. Cleanup: git branch -d feature/... && git pull origin main
```

---

## 🟢 SPRINT 12 MODULES - ENFORCED REQUIREMENTS

### Module 1: Refinancing (`finance/refinancing_v14_hydra.py`)
- ✅ Hydra CLI with conf/scenarios/*.yaml
- ✅ validate_config_for_v14(cfg, strict=True) - R5
- ✅ Import IRR from finance.irr only - R7
- ✅ 100% type hints - TYPE-01
- ✅ 8+ tests with regression pins - TEST-01
- ✅ JSON output - CLI-03
- ✅ CASPER/CESSPIT/CCCDIR docs

### Module 2: Equity Distribution (`finance/equity_distribution_v14_hydra.py`)
- Same as Module 1

### Module 3: Monte Carlo (`analytics/monte_carlo_v14.py`)
- ✅ Fixed random_seed for reproducibility - MRM-01
- ✅ Hydra CLI with conf/*.yaml
- ✅ 10+ tests (stochastic behavior) - MRM-01
- ✅ Schema guard validation - R5
- ✅ No numpy/scipy random without seed

### Module 4: Stress Tests (`analytics/stress_tests_v14.py`)
- ✅ Deterministic scenario generation
- ✅ Schema guard per scenario - R22
- ✅ Batch handling (VAL-02) - skip bad, report
- ✅ 6+ tests

### Module 5: Pipeline CLI (`scripts/run_full_pipeline_sprint12.py`)
- ✅ Hydra-based orchestration
- ✅ Calls validate_config_for_v14 - R5
- ✅ JSON summary output - CLI-03
- ✅ Smoke test in CI

---

## ✅ **DEVELOPMENT CHECKLIST (Per Commit)**

**Before `git commit`:**
- [ ] Code has 100% type hints (TYPE-01)
- [ ] CASPER/CESSPIT/CCCDIR docstrings complete
- [ ] pytest tests/api/test_module.py --no-cov ✅
- [ ] mypy . --quiet ✅
- [ ] validate_config_for_v14(..., strict=True) used - R5
- [ ] No argparse, no Typer, no AST - R3, R4
- [ ] No hardcoded numbers (all in config) - ARCH-01
- [ ] IRR/NPV imported from finance.irr only - R7
- [ ] Schema guard tests included - R22
- [ ] Regression pins for financial outputs - TEST-01
- [ ] 8+ tests per module minimum - TEST-01
- [ ] Unit suffixes in config (FX-02) - Config checked

**Before `git push`:**
- [ ] Commit message R18 format - R18
- [ ] All local tests green - R21
- [ ] All mypy warnings resolved
- [ ] Pre-commit hooks passed
- [ ] Ready for GitHub CI gate

---

## 📚 RULE REFERENCES

| Rule | Topic | Enforcement |
|------|-------|-------------|
| **ARCH-01** | Config-first | Hydra required |
| **CLI-01** | No argparse | LibCST test |
| **CLI-03** | JSON output | Smoke tests |
| **TYPE-01** | Type hints 100% | Mypy clean |
| **VAL-01** | Schema guard | validate_config_for_v14 |
| **R3** | No argparse | LibCST ban |
| **R4** | No Typer v14 | LibCST ban |
| **R5** | strict=True | Always enforce |
| **R7** | IRR/NPV in finance.irr | LibCST + import checks |
| **R9** | Tranche-aware debt | API structure |
| **R10** | Pre-commit hooks | Auto on git commit |
| **R15** | mypy strict | Pre-commit + CI |
| **R18** | Git messages | Convention |
| **R22** | Schema guard tests | Use strict=True |
| **R23** | Branch-based dev | GitHub protection |

---

**Status:** 🟢 READY FOR IMPLEMENTATION  
**Branch:** feature/sprint12-monte-carlo  
**Ruleset:** v3.0 GWTF - FULLY ENFORCED  

**PROCEED WITH CONFIDENCE - ALL RULES UNDERSTOOD AND WILL BE FOLLOWED.**
