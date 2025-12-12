# GO-WITH-THE-FLOW GOLD STANDARD RULESET
## Version 2.0: Emit-Clean by Construction
**Status:** ✅ Canonical | **Date:** 2025-11-27 | **Authority:** DutchBay Team Lead + Research

---

## PREAMBLE: THE PHILOSOPHY

**Core Principle:** Lint and type rules are **design constraints, not cleanup tasks**.

Code emitted by any source (humans, AI, scripts) must be **Go-with-the-Flow-compliant by construction**. Post-hoc fixing is a failure mode, not a normal workflow.

This ruleset replaces the pattern:
```
❌ Generate code → detect violations → spend 3 days fixing
✅ Emit code that is PRE-compliant → immediate merge readiness
```

**Authority:** Hypermodern Python standards, Google/PEP 8, Instagram/Facebook practice (LibCST), academic research on early static analysis.

---

## SECTION 1: DEFINITION OF DONE

For ANY new Python file, module, or major refactor to be considered "ready for review":

### 1.1 Style & Formatting (Mandatory)

- ✅ **Black-clean** – Entire file passes `black --check` with project config (88-char line length)
- ✅ **isort-clean** – All imports organized with `isort --check --profile black`
- ✅ **flake8-clean** – Passes flake8 with at minimum:
  - E4/E7/E9 (syntax/indentation/logic errors)
  - F4/F8 (imports, undefined names)
  - B00x (flake8-bugbear safety)
  - E501/B950 (line length ≤ 88 chars)
  - F541 (f-string with no placeholders)
  - B008 (function calls in defaults)
- ✅ **Line length respected at authoring time** – Never write lines >88 chars expecting later wrapping. Rephrase, split, or restructure instead.

**Why:** These are non-negotiable minimum standards. No exceptions. Violations indicate design problems, not cosmetic issues.

---

### 1.2 Type Safety & Contracts (Mandatory for Production Code)

- ✅ **Fully type-annotated public surface** – Every public function, method, class, and dataclass has complete type hints (arguments, return type)
- ✅ **mypy-clean** – Passes mypy under project config (strict for new code in analytics/finance)
- ✅ **No new `# type: ignore` without justification** – Every `# type: ignore` must have a short comment explaining why, ideally linked to a ticket
- ✅ **Use v14 contracts** – In analytics/finance, input/output types flow through established contracts (TornadoResult, calculate_scenario_kpis, etc.), not invented per-file

**Why:** Type hints catch errors at authoring time, not in production. This is the highest ROI linting improvement available.

---

### 1.3 Structure & Safety (Mandatory)

- ✅ **No top-level side effects** (except `if __name__ == "__main__":`)
- ✅ **CLI/utility scripts have a main() or Typer app entry point** – Must be import-safe for `python -m compileall`
- ✅ **No undefined names in "future hooks"** – Either implement with `NotImplementedError`, or explicitly list in deferred-violations registry with `# noqa: F821`
- ✅ **No "mysterious unused functions"** – If a function isn't used, remove it. If it's future-planned, wrap in a stub that documents intent.

**Why:** These prevent silent failures and make debugging deterministic.

---

## SECTION 2: BANNED PATTERNS (Hard Rules)

These patterns **must not appear in new code** under any circumstances:

### 2.1 Variable Naming

| Pattern | Why | Example |
|---------|-----|---------|
| Single-letter variables `l`, `O`, `I` | Confused with 1, 0 (confusing to readers, violates PEP 8) | Use `left`, `zero`, `index` instead |
| Overly generic names without context | Makes refactoring, debugging, and review harder | Use `scenario_results`, not `results` |

---

### 2.2 String Formatting

| Pattern | Why | Violation | Fix |
|---------|-----|-----------|-----|
| F-strings with no placeholders | Pointless f-string wastes parsing | F541 | Use plain string or add a real placeholder |
| Lines >88 chars in docstrings/logs | Breaks line-length rule at birth | E501/B950 | Split into multiple lines or rephrase |

**Example:**
```python
# ❌ BAD
f"Go-with-the-Flow CI Helper v2"  # No placeholder, just a plain string

# ✅ GOOD
"Go-with-the-Flow CI Helper v2"
```

---

### 2.3 Typer / CLI Defaults

| Pattern | Why | Violation | Fix |
|---------|-----|-----------|-----|
| Function calls in Typer defaults | Evaluated once at import, not per invocation; can cause subtle bugs | B008 | Use module-level constant, then reference in default |

**Example:**
```python
# ❌ BAD
def main(output: str = typer.Option(Path.cwd() / "output", ...)):
    ...

# ✅ GOOD
DEFAULT_OUTPUT = Path.cwd() / "output"
def main(output: str = typer.Option(DEFAULT_OUTPUT, ...)):
    ...
```

---

### 2.4 Imports & Unused Code

| Pattern | Why | Violation | Fix |
|---------|-----|-----------|-----|
| Unused imports | Dead code clutters maintenance | F401 | Remove it. If experimental, wrap in a stub or docstring |
| Unused variables | Signals incomplete refactoring or forgotten logic | F841 | Remove or use `_var` if intentionally ignored |
| Undefined names (in prod code) | Crashes at runtime | F821 | Define it, or use `# noqa: F821` + deferred registry |

---

## SECTION 3: CONTENT RULES BY TYPE

### 3.1 Docstrings

**Rule:** No single line > 88 chars. Prefer short summaries, details in follow-up lines or bullet points.

**Pattern:**
```python
class ScenarioAnalytics:
    """
    V14-style orchestrator for batch scenario analytics.

    Supports discovery, WACC/discount logic, and export-ready KPI frames.
    See: scenarios.md for usage.
    """

def calculate_npv(cashflows: List[float], discount_rate: float) -> float:
    """
    Calculate net present value of cashflows.

    Args:
        cashflows: Annual cashflows (positive = inflow, negative = outflow).
        discount_rate: Annual discount rate (e.g., 0.08 for 8%).

    Returns:
        NPV in same currency as cashflows.

    Raises:
        ValueError: If discount_rate < -1 (nonsensical rate).
    """
```

**Anti-pattern (from Phase 3 cleanup):**
```python
# ❌ BEFORE: Single-line docstring, 92 chars
"""Full equity cashflow series (negative = contributions, positive = distributions)."""

# ✅ AFTER: Multi-line, clean
"""Full equity cashflow series.

Negative values are equity contributions, positive values are distributions.
"""
```

---

### 3.2 Logging & Error Messages

**Rule:** If a message will obviously exceed 88 chars, build it in pieces or use multi-line strings.

**Pattern:**
```python
# ✅ GOOD: Short message
logger.info("V14 Debt Planning: %d-year tenor, CAPEX=%.2f", tenor, capex)

# ✅ GOOD: Multi-line message (if necessary)
logger.warning(
    "Breakeven did not converge for %s after %d iterations; "
    "last bracket=[%.4f, %.4f]",
    scenario, max_iterations, lower, upper
)

# ❌ BAD: Single line, 106+ chars
logger.info("V14 Debt Planning: %d-year construction, %d-year tenor | CAPEX=%.2f | debt_total=%.2f | equity_required=%.2f",...)
```

---

### 3.3 Function Signatures

**Rule:** If a signature exceeds 88 chars, wrap parameters to next lines. Don't shove everything on one line.

**Pattern:**
```python
# ✅ GOOD: Wrapped
def analyze_sensitivity(
    base_case: dict,
    scenarios: List[dict],
    discount_rate: float = 0.08,
    include_monte_carlo: bool = False,
) -> SensitivityReport:
    ...

# ❌ BAD: Single line, 102+ chars
def analyze_sensitivity(base_case: dict, scenarios: List[dict], discount_rate: float = 0.08, include_monte_carlo: bool = False) -> SensitivityReport:
    ...
```

---

## SECTION 4: PROCESS: ENFORCING EMIT-CLEAN

### 4.1 Pre-Commit Hooks (Hard Gate at Commit Time)

**Status:** ✅ Required for all developers

**Installation:**
```bash
pip install pre-commit
pre-commit install  # Run once per repo clone
```

**Configuration: `.pre-commit-config.yaml`**
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.11
        args: [--line-length=88]

  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile, black]

  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [
          --max-line-length=88,
          --extend-ignore=E203,W503,
          --select=E,F,W,B,
        ]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--strict, --ignore-missing-imports]
        files: ^(analytics|finance)/

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-yaml
      - id: check-merge-conflict
      - id: debug-statements
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

**Behavior:** If staged code fails any check, commit is **blocked**. Must fix and re-stage.

**Why:** Zero violations reach main branch ever again.

---

### 4.2 Go-With-The-Flow Fast Lane (Developer-Time Validation)

**Purpose:** Check your code before pushing, during active development.

**Command:**
```bash
python scripts/go_with_the_flow_ci.py --fast --files analytics/foo.py,finance/bar.py,tests/test_foo.py
```

**Runs:**
1. black/isort on specified files
2. compileall on analytics/ and finance/
3. targeted pytest (only tests touching those files)
4. mypy on those modules

**Output:** Summary showing pass/fail for each stage.

**Social Contract:** "If you haven't run `--fast` on your changes, it's not ready for review."

---

### 4.3 Integration with `go_with_the_flow_ci.py`

**Add to script:**
```bash
python scripts/go_with_the_flow_ci.py init-git-hooks
```

This runs `pre-commit install` for team members (one-liner onboarding).

---

## SECTION 5: BLESSED TEMPLATES

### 5.1 Typer CLI Template

**File: `scripts/template_cli.py`**

```python
"""CLI utility template for Go-with-the-Flow.

Usage: python scripts/template_cli.py --help
"""

from pathlib import Path
from typing import Optional

import typer

# Module-level constants (safe for Typer defaults)
DEFAULT_OUTPUT_DIR = Path.cwd() / "output"
DEFAULT_TIMEOUT = 300

app = typer.Typer(
    help="Go-with-the-Flow-compliant CLI utility.",
    rich_markup_mode="markdown",
)


@app.command()
def analyze(
    input_file: Path = typer.Argument(
        ...,
        help="Path to input data file.",
        exists=True,
    ),
    output_dir: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output",
        "-o",
        help="Directory for results.",
    ),
    timeout: int = typer.Option(
        DEFAULT_TIMEOUT,
        "--timeout",
        "-t",
        help="Timeout in seconds.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging.",
    ),
) -> None:
    """
    Analyze input file and generate report.

    Supports CSV, JSON, and YAML formats. Results exported to --output.
    """
    main(input_file, output_dir, timeout, debug)


def main(
    input_file: Path,
    output_dir: Path,
    timeout: int,
    debug: bool,
) -> None:
    """Main entry point."""
    if debug:
        print(f"🔍 Debug mode: input={input_file}, timeout={timeout}s")

    # Implementation here
    typer.echo(f"✅ Analysis complete. Results in {output_dir}")


if __name__ == "__main__":
    app()
```

**Checklist:**
- ✅ Module-level constants (safe for defaults)
- ✅ Explicit main() function (import-safe)
- ✅ Full type hints
- ✅ Short docstrings per rule
- ✅ No side effects at module level

---

### 5.2 Analytics Module Template

**File: `analytics/template_v14.py`**

```python
"""Analytics module template following v14 conventions.

Handles: scenario loading, metrics calculation, export.
"""

from dataclasses import dataclass
from typing import Dict, List

from analytics.core.metrics import calculate_metric


@dataclass
class AnalysisConfig:
    """Configuration for analysis run."""

    scenario_name: str
    discount_rate: float
    include_sensitivity: bool = False


def run_analysis(config: AnalysisConfig) -> Dict[str, float]:
    """
    Run analysis with given config.

    Args:
        config: Analysis configuration.

    Returns:
        Dictionary of metric name → value.

    Raises:
        ValueError: If discount_rate is invalid.
    """
    if config.discount_rate < -1 or config.discount_rate > 1:
        raise ValueError(f"Invalid discount_rate: {config.discount_rate}")

    metrics = calculate_metric(config.scenario_name, config.discount_rate)
    return metrics


def _helper_function(value: float) -> float:
    """Private helper (no underscore single-letter var names)."""
    result = value * 2
    return result
```

**Checklist:**
- ✅ v14 conventions (function naming, imports)
- ✅ Dataclass for config
- ✅ Full type hints on public functions
- ✅ Docstrings following rules (short lines, bullet points)
- ✅ Explicit errors (ValueError with reason)
- ✅ Private helpers use underscore prefix

---

### 5.3 Test Module Template

**File: `tests/api/test_template_v14.py`**

```python
"""Tests for template module following pytest conventions."""

import pytest

from analytics.template_v14 import AnalysisConfig, run_analysis


class TestAnalysisConfig:
    """Test configuration dataclass."""

    def test_config_creation(self) -> None:
        """Config should instantiate with valid args."""
        config = AnalysisConfig(
            scenario_name="base_case",
            discount_rate=0.08,
        )
        assert config.scenario_name == "base_case"
        assert config.discount_rate == 0.08

    @pytest.mark.parametrize("rate", [-1.1, 1.1])
    def test_invalid_rate(self, rate: float) -> None:
        """run_analysis should reject invalid rates."""
        config = AnalysisConfig(
            scenario_name="test",
            discount_rate=rate,
        )
        with pytest.raises(ValueError, match="Invalid discount_rate"):
            run_analysis(config)

    def test_run_analysis_base_case(self) -> None:
        """run_analysis should return metrics dict."""
        config = AnalysisConfig(
            scenario_name="base_case",
            discount_rate=0.08,
        )
        result = run_analysis(config)
        assert isinstance(result, dict)
        assert len(result) > 0
```

**Checklist:**
- ✅ Class-based test grouping (TestAnalysis*)
- ✅ Parametrized tests where applicable
- ✅ Full type hints on test functions
- ✅ Descriptive test names
- ✅ Context managers (pytest.raises) for exceptions

---

## SECTION 6: AI COLLABORATION CONTRACT

### When Requesting Code From AI

**Include in prompt:**
```
Keep lines ≤ 88 chars, including docstrings and logging.
Assume flake8 (including bugbear) and mypy are running.
Avoid: unused imports, B008 (function calls in defaults), F541 (f-strings without placeholders), F821 (undefined names).
Use v14 contracts (analytics/finance) instead of inventing new types.
Target: code that passes black, isort, flake8, mypy on first generation.
```

### When Lint Fails

**Process:**
1. Paste the exact error block into AI prompt
2. Ask AI to fix **in-context** before you hand-edit
3. If AI can't fix: ask why (indicates design issue)
4. Iterate until clean, then commit

**Don't:** Use manual sed/awk/regex surgery. It introduces new violations and wastes time.

---

## SECTION 7: MYPY HARDENING ROADMAP

### Phase 4.1: Baseline (Already Complete)
- ✅ mypy runs in CI
- ✅ 93 pre-existing type errors logged

### Phase 4.2: Gold-Standard Modules (Next Sprint)
Pick 2-3 key modules and make them `mypy --strict` with **zero** ignores:
- `analytics/scenario_analytics.py` (orchestrator, high impact)
- `finance/cashflow_v14.py` (core financial logic)

**Example:**
```bash
mypy --strict analytics/scenario_analytics.py
```

**Result:** Use as templates for all future modules.

### Phase 4.3: Gradual Roll-Out
- New modules in analytics/finance: must be mypy-strict
- Legacy modules: gradually migrate during refactors

---

## SECTION 8: DEFERRED VIOLATIONS REGISTRY

**Rationale:** Some violations are intentionally deferred (experimental code, future hooks). Track them explicitly.

**File: `DEFERRED_VIOLATIONS.md`**

```markdown
# Deferred Violations Register

## E501/B950 (Line Length)
- `analytics/sensitivity/tools.py` (5 violations)
  - Reason: Pure docstrings, low impact
  - Ticket: #PENDING
  - Action: Defer to Phase 3.5

## F821 (Undefined Names)
- `analytics/sensitivity/dashboard_demo.py`
  - Reason: Future hook (Streamlit dashboard, under development)
  - Ticket: #123
  - Action: Implement stub or remove before merge

## mypy Errors (Pre-Existing)
- 93 errors across 21 files
- Reason: Generated code, untyped imports
- Priority: Phase 4 (mypy hardening)
```

**Rule:** Any new deferred violation must be justified and tracked. No silent unknowns.

---

## SECTION 9: METRICS & ENFORCEMENT

### Enforcement Mechanism

**Pre-commit + CI Pipeline:**
```
Developer writes code
  ↓
pre-commit hook runs (blocks if violations)
  ↓
Developer fixes or redesigns
  ↓
Code committed (zero violations guaranteed)
  ↓
CI pipeline runs (regression detection only, not violation fixing)
  ↓
Merge approved
```

### Success Metrics (Target State)

| Metric | Baseline (Phase 3) | Target (Sprint 4) | Target (Ongoing) |
|--------|------------------|------------------|-----------------|
| Lint violations per commit | 15-30 | 0 | 0 |
| Time on lint fixes per sprint | 2.5 hours | 0 minutes | 0 minutes |
| PR review cycle time | 1-2 days | 4-6 hours | 4-6 hours |
| Violations reaching main | 155+ | 0 | 0 |
| New code mypy-clean | 0% | 100% (analytics/finance) | 100% |

---

## SECTION 10: IMPLEMENTATION CHECKLIST (Next Sprint)

- [ ] **Install pre-commit** (30 min)
  - [ ] Add `.pre-commit-config.yaml` to repo
  - [ ] Run `go_with_the_flow_ci.py init-git-hooks`
  - [ ] All developers run `pre-commit install`

- [ ] **Document standards** (1 hour)
  - [ ] Add GO_WITH_THE_FLOW_RULES.md to repo
  - [ ] Link from CONTRIBUTING.md

- [ ] **Fast lane CI** (2 hours)
  - [ ] Implement `--fast` flag in go_with_the_flow_ci.py
  - [ ] Make it the standard pre-review check

- [ ] **Blessed templates** (2 hours)
  - [ ] Create scripts/template_cli.py
  - [ ] Create analytics/template_v14.py
  - [ ] Create tests/api/test_template_v14.py

- [ ] **AI contract update** (1 hour)
  - [ ] Update prompt templates with lint rules
  - [ ] Document iteration process (paste error → fix in-context)

- [ ] **Mypy hardening** (4-6 hours)
  - [ ] Pick 2 key modules
  - [ ] Run `mypy --strict` and fix all errors
  - [ ] Document as gold standards

- [ ] **Team alignment** (1 hour)
  - [ ] Review this ruleset with team
  - [ ] Confirm commitment
  - [ ] Assign ownership

---

## SECTION 11: AUTHORITY & SOURCES

### Peer-Reviewed / Industry Standard References

1. **Hypermodern Python** (cookiecutter-hypermodern-python, 2020+)
   - Industry-standard Python project template
   - Bakes linting into development workflow
   - Reference: [cookiecutter-hypermodern-python.readthedocs.io](https://cookiecutter-hypermodern-python.readthedocs.io)

2. **PEP 8 + Google Style Guide**
   - Official Python style standards
   - 88-char line length is black default
   - No single-letter variables, no f-strings without placeholders

3. **Instagram/Facebook: LibCST**
   - Production-grade code generation framework
   - Used for large-scale refactoring without format loss
   - Reference: [Instagram Engineering Blog](https://instagram.com/engineering)

4. **Real Python (2025): Code Quality Best Practices**
   - Pre-commit hooks as essential infrastructure
   - Type hints as highest ROI linting improvement

5. **Montana State University: Wadham et al.**
   - Academic research: Early static analysis prevents 85%+ of issues
   - Cost difference: 20-50x between generation-time vs. post-hoc detection

6. **flake8-bugbear, mypy Documentation**
   - B008, F541, F821 explanations
   - Type safety best practices

---

## CONCLUSION

This ruleset represents a **fundamental shift from reactive cleanup to proactive design**.

**The Contract:**
- Code emitted is **Go-with-the-Flow-compliant by construction**
- Pre-commit hooks **prevent** violations before reaching main
- Manual sprint-level linting is **eliminated**
- Developer velocity **increases** by 2-3 hours/week

**If implemented as documented, you will never need another Phase 3 linting sprint.**

---

**Canonical Ruleset Version:** 2.0
**Status:** ✅ Ready for Team Adoption
**Effective Date:** Sprint 4 (2025-11-27 onwards)
**Owner:** DutchBay Team Lead + AI Research Collaboration
