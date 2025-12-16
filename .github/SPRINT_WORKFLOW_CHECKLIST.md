# DutchBay Sprint Workflow Checklist

**Purpose:** Ensure every sprint/branch meets GWTF v3.0, CCCDIR, and quality standards

**When to Use:** At start of each sprint, before creating feature branches

**Last Updated:** December 16, 2025

---

## 📋 Pre-Sprint Planning

Before starting a new sprint or feature branch:

- [ ] **Read GWTF Ruleset** (`go_with_the_flow_rules_v3_0_clean.csv`)
- [ ] **Review Current Config** (`scenarios/dutchbay_lendercase_2025Q4.yaml`)
- [ ] **Check sprint plan** (SPRINT_11_PLAN.md or equivalent)
- [ ] **Identify config variables** that will be needed
- [ ] **Plan schema guard** integration points

---

## 🏗️ Architecture & Design Phase

### GWTF v3.0 Rules Compliance

#### ARCH-01: Config-First Architecture

- [ ] **No hardcoded values** in code
- [ ] **All parameters** from YAML config (`dutchbay_lendercase_2025Q4.yaml`)
- [ ] **Config paths documented** in module docstrings
- [ ] **Fallback logic** defined if config sections missing
- [ ] **Example:** `corporate_tax_rate = float(config.tax.corporate_tax_rate)` ✅
- [ ] **NOT:** `corporate_tax_rate = 0.24` ❌

**Verification:**
```bash
grep -r "^[A-Za-z_]* = [0-9\".]*$" finance/ --include="*.py"
# Should return ZERO matches (no hardcoded constants)
```

#### CLI-01: Hydra-Based CLI Framework

- [ ] **Use Hydra + OmegaConf** for all new CLIs
- [ ] **No argparse anywhere** in v14 code
- [ ] **DictConfig parameters** passed to functions
- [ ] **Config path** in Hydra entrypoint (`conf/*.yaml`)
- [ ] **CLI function signature** includes `cfg: DictConfig` parameter
- [ ] **Test CLI** with sample config overrides

**Example:**
```python
from hydra import initialize_config_dir, compose
from omegaconf import DictConfig

@hydra.main(version_base=None, config_path="conf", config_name="default")
def main(cfg: DictConfig) -> None:
    # ✅ cfg comes from Hydra
    tax_config = cfg.tax
```

**Verification:**
```bash
# Should fail (no argparse allowed)
grep -r "import argparse" finance/ dutchbay_v14chat/ run_*_v14.py
# Should return ZERO matches
```

#### VAL-01: Schema Guard Gatekeeper

- [ ] **Import schema guard** in main pipeline
- [ ] **Call validate_config_for_v14()** before processing
- [ ] **strict=True** for production runs
- [ ] **Error messages** logged with invalid configs
- [ ] **Fallback behavior** documented for strict=False

**Example:**
```python
from analytics.schema_guard import validate_config_for_v14

if __name__ == "__main__":
    cfg = OmegaConf.load("scenarios/dutchbay_lendercase_2025Q4.yaml")
    validate_config_for_v14(cfg, strict=True)  # ✅ Gatekeeper
    # Safe to proceed - config validated
```

**Verification:**
```bash
# Check schema guard is used
grep -r "validate_config_for_v14" run_*_v14.py analytics/
# Should find at least one usage
```

#### CST-01: LibCST Guardrails

- [ ] **LibCST linting tests** added for new module
- [ ] **Bans on argparse/Typer** enforced
- [ ] **Hardcoding detection** test added
- [ ] **Import safety** validated
- [ ] **Tests in** `tests/lint/test_module_compliance.py`

**Example:**
```python
# tests/lint/test_new_module_compliance.py
import libcst as cst

def test_new_module_no_hardcoded_constants():
    """Verify no magic constants."""
    module = Path("finance/new_module_v14.py").read_text()
    assert "rate = 0." not in module  # ✅
    assert "years = " not in module    # ✅
```

**Verification:**
```bash
pytest tests/lint/ -v --tb=short
# All linting tests must pass
```

#### TYPE-01: Full Type Annotations

- [ ] **All function signatures** typed
- [ ] **Return types** explicitly specified
- [ ] **Optional/Union types** used correctly
- [ ] **DictConfig/OmegaConf types** from omegaconf module
- [ ] **mypy --strict** passes without errors

**Example:**
```python
from typing import Optional, Sequence, Tuple
from omegaconf import DictConfig

def build_tax_profile(
    config_tax: DictConfig,              # ✅ Explicit type
    capex_depreciable_lkr: Optional[float],  # ✅ Explicit
    project_life_years: int,             # ✅ Explicit
) -> TaxProfile:                         # ✅ Return type
```

**Verification:**
```bash
mypy finance/new_module_v14.py --strict
# Should report: Success! no type errors (0 of 0)
```

---

## 📝 Implementation Phase

### CCCDIR Framework Checklist

#### C1: Configuration

- [ ] **Config source** documented in module docstring
- [ ] **Path example:** `scenarios/dutchbay_lendercase_2025Q4.yaml::tax`
- [ ] **Fallback paths** defined and tested
- [ ] **Config validation** required before use
- [ ] **Config_source parameter** tracked for audit

**Example:**
```python
"""
Configuration Path:
- scenarios/dutchbay_lendercase_2025Q4.yaml::tax (canonical)
- scenarios/dutchbay_lendercase_2025Q4.yaml::project (fallback)
"""

def build_tax_profile(
    config_tax: DictConfig,
    # ...
    config_source: str = "config",  # For audit trail
):
```

#### C2: CASPER (Clean Architecture)

- [ ] **Separation of concerns** - module does ONE thing
- [ ] **API contract** - clear public interface
- [ ] **No side effects** - pure functions where possible
- [ ] **Immutable outputs** - frozen dataclasses
- [ ] **Error handling** - explicit validation errors

**Example:**
```python
@dataclass(frozen=True)  # ✅ Immutable
class TaxProfile:
    corporate_tax_rate: float
    # ...

def build_tax_profile(config_tax: DictConfig) -> TaxProfile:  # ✅ Clear contract
    # Validate inputs
    if not (0.0 <= config_tax.corporate_tax_rate <= 1.0):
        raise ValueError(...)  # ✅ Explicit error
```

#### C3: CESSPIT (Core-Easy-Simple)

- [ ] **Core module** - focused, single responsibility
- [ ] **Easy to integrate** - simple factory pattern
- [ ] **Simple interface** - minimal parameters
- [ ] **Clear naming** - self-documenting code
- [ ] **Minimal dependencies** - only essentials imported

**Example:**
```python
# ✅ Simple: config in, profile out
def build_tax_profile(config_tax: DictConfig, ...) -> TaxProfile:
    """Factory pattern - easy to understand."""
    # Compute once, return immutable
```

#### C4: LIBsct (Linting-Import-Bans)

- [ ] **LibCST tests** written for module
- [ ] **Import bans** enforced (no argparse/Typer)
- [ ] **Hardcoding bans** tested
- [ ] **Hot-spot APIs** validated
- [ ] **CI fails** if violations detected

**Checklist:**
```bash
# Add to tests/lint/test_module_compliance.py
[ ] No argparse imports
[ ] No Typer imports (in v14 modules)
[ ] No hardcoded constants (numeric literals)
[ ] No interactive input() calls
[ ] Correct import paths (omegaconf, not sys.argv)
```

#### C5: CDIR (Config-Directory-Import-Reproducibility)

- [ ] **Config-first** - params from YAML
- [ ] **Directory structure** - correct location (finance/, analytics/, etc.)
- [ ] **Import patterns** - `from omegaconf import DictConfig`
- [ ] **Reproducibility** - config source tracked
- [ ] **Version tracking** - VERSION file updated

**Checklist:**
```
[ ] File in correct directory (finance/*, analytics/*, etc.)
[ ] Imports follow pattern: from omegaconf import ...
[ ] Config path documented: scenarios/dutchbay_lendercase_2025Q4.yaml
[ ] Config_source parameter included for audit
[ ] VERSION file updated if financial behavior changed
```

---

## 🧪 Testing Phase

### TEST-01: Regression Tests

- [ ] **Unit tests** for core functions
- [ ] **Integration tests** with sample config
- [ ] **Regression pins** defined (expected outputs)
- [ ] **Edge cases** covered (None, zero, negative, boundary)
- [ ] **Config variations** tested

**Example:**
```python
# tests/api/test_module_v14_regression.py

def test_tax_profile_lender_case_regression():
    """Regression pin: lender case tax profile."""
    config = OmegaConf.load("scenarios/dutchbay_lendercase_2025Q4.yaml")
    profile = build_tax_profile(config.tax, ...)
    
    # Pins from config
    assert profile.corporate_tax_rate == 0.3  # From YAML
    assert profile.tax_holiday_years == 12    # From YAML
```

**Verification:**
```bash
pytest tests/api/test_module_v14_regression.py -v
# All tests must pass
```

### TYPE-01: mypy --strict

- [ ] **No type errors** reported
- [ ] **All paths** type-checked
- [ ] **Any usage** minimized
- [ ] **Optional handling** explicit

**Verification:**
```bash
mypy finance/new_module_v14.py --strict
# Success! no type errors (0 of 0)
```

### Coverage

- [ ] **Core functions** covered (>90%)
- [ ] **Edge cases** covered
- [ ] **Error paths** tested
- [ ] **Config validation** covered

**Verification:**
```bash
pytest tests/api/test_module_v14_regression.py --cov=finance.new_module_v14 --cov-report=term-missing
# Check coverage meets threshold
```

---

## 📋 Code Review Phase

### Pre-Review Checklist

- [ ] **All hardcoding** removed
- [ ] **Schema guard** integrated
- [ ] **Hydra/OmegaConf** used (no argparse)
- [ ] **Type hints** complete (mypy --strict)
- [ ] **Tests** passing (unit, integration, regression)
- [ ] **Linting** passing (LibCST, black, isort, ruff)
- [ ] **Documentation** complete (docstrings, examples)
- [ ] **CHANGELOG** updated
- [ ] **VERSION** bumped (if financial behavior changed)

### Review Checklist Items

- [ ] **Config paths** verified (all from YAML, no hardcoding)
- [ ] **Schema guard** called before usage
- [ ] **DictConfig** used (not dict or custom objects)
- [ ] **Error handling** explicit (ValueError, TypeError with messages)
- [ ] **Immutability** enforced (frozen dataclass, tuple returns)
- [ ] **Audit trail** present (config_source parameter)
- [ ] **Type hints** complete (mypy clean)
- [ ] **Tests cover** happy path + edge cases
- [ ] **GWTF compliance** documented in PR

### PR Template Addition

```markdown
## GWTF v3.0 Compliance Checklist

- [ ] All variables from config YAML (no hardcoding)
- [ ] Hydra + OmegaConf used (no argparse)
- [ ] Schema guard integration verified
- [ ] LibCST linting passed
- [ ] Type hints complete (mypy --strict)
- [ ] CASPER + CESSPIT architecture followed
- [ ] CCCDIR framework aligned
- [ ] Tests passing (unit, integration, regression)
- [ ] Documentation complete
```

---

## ✅ Pre-Merge Checklist

Before merging to main/sprint branch:

- [ ] **All CI checks** pass
  - [ ] Linting (black, isort, ruff)
  - [ ] Type checking (mypy --strict)
  - [ ] Unit tests (pytest)
  - [ ] Integration tests
  - [ ] LibCST guardrails

- [ ] **GWTF Compliance** verified
  - [ ] ARCH-01: Config-first ✅
  - [ ] CLI-01: Hydra-based ✅
  - [ ] VAL-01: Schema guard ✅
  - [ ] CST-01: LibCST linting ✅
  - [ ] TYPE-01: Full types ✅
  - [ ] TEST-01: Regression tests ✅
  - [ ] R3: No argparse ✅
  - [ ] R5: Schema guard pre-flight ✅

- [ ] **CCCDIR Alignment** verified
  - [ ] Config-first: All from YAML ✅
  - [ ] CASPER: Clean separation ✅
  - [ ] CESSPIT: Core/Easy/Simple ✅
  - [ ] LIBsct: Linting enforced ✅
  - [ ] CDIR: Config/Directory/Import/Reproducible ✅

- [ ] **Quality Standards** met
  - [ ] No hardcoded values
  - [ ] No hardcoded defaults
  - [ ] Config source tracked
  - [ ] Error messages clear
  - [ ] Documentation complete
  - [ ] Examples provided

---

## 🚀 Post-Merge Checklist

After merge to production:

- [ ] **CHANGELOG** updated
- [ ] **VERSION** bumped (if applicable)
- [ ] **Documentation** published
- [ ] **Config examples** added
- [ ] **Integration verified** in pipeline
- [ ] **Monitoring** set up (if applicable)
- [ ] **Team notified** (if breaking changes)

---

## 📊 Compliance Scorecard Template

For each sprint/branch, fill out:

```markdown
# Sprint 11 Phase 1a - Compliance Scorecard

## GWTF v3.0 Compliance
- [x] ARCH-01: Config-First Architecture
- [x] CLI-01: Hydra-Based CLI Framework
- [x] VAL-01: Schema Guard Gatekeeper
- [x] CST-01: LibCST Guardrails
- [x] TYPE-01: Full Type Annotations
- [x] TEST-01: Regression Tests
- [x] R3: No argparse anywhere
- [x] R5: Schema guard pre-flight

**Score: 8/8 (100%)**

## CCCDIR Framework
- [x] C1: Configuration (YAML-driven)
- [x] C2: CASPER (Clean architecture)
- [x] C3: CESSPIT (Core/Easy/Simple)
- [x] C4: LIBsct (Linting enforced)
- [x] C5: CDIR (Config/Directory/Import/Reproducible)

**Score: 5/5 (100%)**

## Quality Standards
- [x] No hardcoded variables
- [x] No hardcoded defaults
- [x] Schema guard integrated
- [x] Config source tracked
- [x] Type hints complete
- [x] Tests passing (100% coverage)
- [x] Documentation complete

**Score: 7/7 (100%)**

## Overall Compliance: 100% ✅
```

---

## 🔗 References

- **GWTF Ruleset:** `go_with_the_flow_rules_v3_0_clean.csv`
- **Config Template:** `scenarios/dutchbay_lendercase_2025Q4.yaml`
- **Schema Guard:** `analytics/schema_guard.py`
- **LibCST Tests:** `tests/lint/`
- **API Tests:** `tests/api/`

---

## 💡 Usage Instructions

1. **At sprint start:** Copy checklist template
2. **During implementation:** Reference each section
3. **Before PR:** Complete pre-review checklist
4. **During review:** Use review checklist items
5. **At merge:** Verify pre-merge checklist
6. **After merge:** Update scorecard

---

**Last Updated:** December 16, 2025  
**Version:** 1.0.0  
**Status:** ACTIVE - Use for all future sprints
