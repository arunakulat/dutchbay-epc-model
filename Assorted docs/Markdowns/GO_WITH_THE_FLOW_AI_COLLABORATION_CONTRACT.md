# GO-WITH-THE-FLOW AI COLLABORATION CONTRACT
## Implicit Standards for Code Generation
**Status:** ✅ Canonical Amendment | **Date:** 2025-11-27 | **Effective:** Immediately

---

## PREAMBLE

When any team member (human or AI) is asked to produce code and the request includes the phrase **"Go with the Flow"** (or variants: "go with the flow", "Go-with-the-Flow ruleset"), this automatically invokes the complete set of standards in this contract.

**No exceptions. No opt-outs. No future cleanup.**

Code emitted under this contract must be **production-ready and Go-with-the-Flow-compliant on first generation**.

---

## SECTION 1: THE MAGIC PHRASE

### What Triggers This Contract

Any of the following trigger automatic application of all standards below:

- ✅ "Go with the Flow"
- ✅ "go with the flow"
- ✅ "Go-with-the-Flow ruleset"
- ✅ "Go-with-the-Flow compliant"
- ✅ References to `GO_WITH_THE_FLOW_GOLD_STANDARD.md`

When you see it in a code request → **all sections below apply automatically**.

---

## SECTION 2: FORMATTING & LINT CONTRACT (AUTOMATIC)

### 2.1 Line Length (Mandatory)

- ✅ **All lines ≤ 88 characters**, including:
  - Code statements
  - Docstrings (no single-line docstrings >88 chars)
  - Logging/error messages
  - Comments
  - Type hints

**Mechanism:** If a line wants to exceed 88 chars, restructure, don't defer:
```python
# ❌ DON'T leave for later cleanup
logger.info("This is a very long message that someone will complain about later")

# ✅ DO restructure at generation time
logger.info(
    "This is a very long message that "
    "someone will not complain about"
)
```

---

### 2.2 Lint Scope (Mandatory)

Code is written to pass on **first generation**:

| Tool | Scope | Note |
|------|-------|------|
| **black** | Entire file | Line-length=88, project config |
| **isort** | All imports | --profile black (black-compatible) |
| **flake8** | E4/E7/E9, F4/F8, B00x | Bugbear included |
| **E501/B950** | Line length | ≤ 88 chars enforced |
| **F541** | f-strings | No empty f-strings (e.g., f"text") |
| **B008** | Typer defaults | No function calls in defaults |
| **F821** | Undefined names | Either defined or # noqa: F821 + registry |
| **mypy** | Type checking | Strict on analytics/finance |

**No violations. Zero.**

---

### 2.3 Banned Patterns (Hard Rules)

These **never appear** in new code:

| Pattern | Why | Example of Fix |
|---------|-----|-----------------|
| Unused imports | Dead code | Remove it |
| Unused variables | Signals incomplete refactor | Remove or use `_var` |
| Single-letter vars: `l`, `O`, `I` | Confused with 1, 0 | Use `left`, `zero`, `index` |
| f-strings with no placeholders | Pointless | Use plain string or add placeholder |
| Function calls in Typer defaults | B008: evaluated at import time | Use module constant instead |
| Undefined name references | F821: crashes at runtime | Define it or use stub |

---

## SECTION 3: TYPES & V14 CONTRACTS (AUTOMATIC)

### 3.1 Use v14 Contracts

For **any code touching analytics/finance**:

- ✅ Reuse existing v14 contracts/types:
  - `TornadoResult`, `MultiMetricTornadoResult` (sensitivity)
  - `calculate_scenario_kpis()` interface
  - Cashflow/Debt/Equity v14 dataclasses
  - WACC v14 contracts

- ❌ **Never invent** ad-hoc dict shapes or random dataclasses when contracts exist

**Example:**
```python
# ❌ DON'T invent new types
def analyze(scenario: dict) -> dict:
    return {"npv": 100, "metrics": {...}}

# ✅ DO use v14 contracts
from analytics.core.metrics import ScenarioKPIs

def analyze(scenario: dict) -> ScenarioKPIs:
    return ScenarioKPIs(npv=100, metrics={...})
```

---

### 3.2 Full Type Annotations

- ✅ **All public functions/classes fully typed**:
  - Function arguments: complete type hints
  - Return types: never omitted
  - Dataclass fields: typed
  - Generic types: spelled out (List[T], Dict[K, V], Optional[T])

- ✅ **Assume mypy --strict is running**:
  - No `Any` shortcuts
  - No implicit Optional
  - No untyped function definitions
  - If `# type: ignore` is needed, it must have a short justification comment

**Example:**
```python
# ❌ DON'T skip types
def calculate_npv(cashflows, rate):
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))

# ✅ DO fully type
def calculate_npv(
    cashflows: List[float],
    rate: float,
) -> float:
    """Calculate NPV of cashflows."""
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))
```

---

## SECTION 4: STRUCTURAL RULES (AUTOMATIC)

### 4.1 No Top-Level Side Effects

- ✅ Only side effects allowed:
  ```python
  if __name__ == "__main__":
      main()
  ```

- ❌ **Never** execute code at module import time (except config loading)

---

### 4.2 CLI / Typer Code

- ✅ **Module-level constants for Typer defaults** (no B008):
  ```python
  DEFAULT_OUTPUT = Path.cwd() / "output"

  @app.command()
  def main(output: Path = typer.Option(DEFAULT_OUTPUT)):
      ...
  ```

- ✅ **Entry point via main() or Typer app** (import-safe for `compileall`)

- ❌ **Never** put business logic directly in CLI command decorator

---

### 4.3 No Ghost Functions

- ✅ If a function is not used yet:
  - Make it a documented stub: `raise NotImplementedError("future feature")`
  - Or don't include it
  - Or wrap with `# pragma: no cover` + comment

- ❌ **Never** leave undefined references or mysterious unused functions

---

## SECTION 5: AI COLLABORATION CONTRACT

### 5.1 Emit With Pipeline in Mind

When generating code, AI assumes:

1. **Pipeline:** black → isort → compileall → pytest → mypy → JSON export
2. **Goal:** Code walks through pipeline without drama
3. **Outcome:** First generation is merge-ready

---

### 5.2 Error Handling Protocol

If code still fails lint/mypy after generation:

**Step 1: You paste exact error**
```
flake8: E501 line too long (95 > 88 characters)
mypy: error: Name "Cashflow" is not defined [name-defined]
```

**Step 2: AI treats as generation bug**
- Not "cleanup work for your team"
- Not "you'll fix it later"
- **AI's responsibility to patch**

**Step 3: AI produces fix that:**
- ✅ Maintains 88-char rule
- ✅ Preserves banned-pattern avoidance
- ✅ Doesn't introduce new violations elsewhere
- ✅ Uses Python scripts (not sed/awk) for bulk changes

---

### 5.3 Multi-File Fixes

For repetitive fixes across files, AI uses DutchBay pattern:

```bash
# 1. gather-violations.py → extract context
# 2. Targeted fix script (per code family)
# 3. Run via go_with_the_flow_ci.py
```

**Not:** Manual one-off edits repeated across 20 files

---

### 5.4 Default to Templates

When generating new code:

| Type | Template |
|------|----------|
| **CLI script** | `scripts/templates/template_cli.py` |
| **Analytics module** | `analytics/templates/template_v14.py` |
| **Test module** | `tests/templates/test_template_v14.py` |

AI thinks in template terms, not from scratch.

---

## SECTION 6: THE IMPLICIT FLOW

When you say **"Go with the Flow"** in a code request, this happens automatically:

```
Your Request: "Go with the Flow: implement XYZ feature"
                          ↓
AI applies Sections 1–5 implicitly:
  - Lines ≤ 88 chars
  - Full type hints
  - flake8/mypy clean on first gen
  - Use v14 contracts
  - No side effects
  - Module-level constants
  - No ghost functions
  - Assume strict mypy
  - Template-first thinking
                          ↓
Code emitted:
  ✅ Passes black, isort, flake8, mypy
  ✅ Ready to merge
  ✅ No post-hoc cleanup needed
```

---

## SECTION 7: UPDATES TO GOLD STANDARD

### 7.1 Amendment to GO_WITH_THE_FLOW_GOLD_STANDARD.md

Add this section after Section 1 (Definition of Done):

```markdown
## SECTION 1.5: AI Code Generation (Implicit Contract)

When requesting code with "Go with the Flow", all standards in
SECTIONS 1–6 of this ruleset are automatically applied by the AI:

- Line length ≤ 88 chars (all contexts)
- black/isort/flake8/mypy clean on first generation
- Full type annotations
- v14 contracts for analytics/finance
- No banned patterns (F541, B008, F821, etc.)
- Structural safety (no side effects, templates-first)

The AI does not emit violations; they are design bugs.
If violations occur, they are treated as generation errors, not cleanup work.

See: GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md for details.
```

---

### 7.2 Reference in CONTRIBUTING.md

Add to developer instructions:

```markdown
## Requesting Code from AI / Assistants

When asking for code generation, use the phrase "Go with the Flow"
to invoke automatic compliance with the Gold Standard Ruleset.

Example:
```
"Go with the Flow: Create a Typer CLI that validates scenario JSON files."
```

This automatically means:
- Lines ≤ 88 chars (all contexts)
- black/isort/flake8/mypy clean on first generation
- Full type hints
- v14 contracts (analytics/finance)
- No unused imports, no B008, no F541, no F821
- Template-first thinking

See: GO_WITH_THE_FLOW_GOLD_STANDARD.md + GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md
```

---

## SECTION 8: ENFORCEMENT

### Team Checklist

- [ ] All team members aware of "Go with the Flow" phrase
- [ ] "Go with the Flow" in prompts = automatic compliance (no negotiation)
- [ ] AI errors treated as generation bugs, not cleanup tasks
- [ ] Code reviews check: "Is this Go-with-the-Flow compliant?" (not formatting debates)
- [ ] Templates referenced in all new code requests

### Metrics

| Metric | Target |
|--------|--------|
| Lint violations in generated code | 0 (zero) |
| Time spent on post-generation cleanup | 0 minutes per sprint |
| Code passing first generation | 100% |
| Pre-commit hook blocks | 0 (violations prevented before commit) |

---

## SECTION 9: EXAMPLES

### Example 1: CLI Script Request

**Your request:**
```
Go with the Flow: Create a Typer CLI that exports scenario metrics to JSON.
Should accept --scenario-path, --output-dir, --format (json/csv).
```

**AI response (implicit behavior):**
- ✅ Uses template_cli.py structure
- ✅ All lines ≤ 88 chars
- ✅ Module-level constants for defaults (no B008)
- ✅ Full type hints on all args/returns
- ✅ main() entry point
- ✅ No side effects at module level
- ✅ Ready to merge first try

---

### Example 2: Analytics Module Request

**Your request:**
```
Go with the Flow: Create sensitivity analysis runner for tornado charts.
Should accept scenarios dict, return TornadoResult.
```

**AI response (implicit behavior):**
- ✅ Uses template_v14.py structure
- ✅ All lines ≤ 88 chars
- ✅ Returns TornadoResult (v14 contract, not custom dict)
- ✅ Full type hints including dataclass types
- ✅ mypy --strict compliant
- ✅ No unused imports
- ✅ Ready to merge first try

---

### Example 3: Error Scenario

**Your message:**
```
Got mypy error on the code you generated:

analytics/my_module.py:42: error:
"TornadoResult" has no attribute "low_metric" [attr-defined]
```

**AI response (implicit behavior):**
- ✅ Acknowledges: this is a generation bug, not your cleanup work
- ✅ Checks actual TornadoResult definition
- ✅ Produces corrected code that:
  - Uses correct attribute names
  - Maintains 88-char rule
  - Maintains all other standards
- ✅ Provides patch (not "go fix it manually")

---

## CONCLUSION

**"Go with the Flow" is now the canonical shorthand** for:

> "Emit code that is black/isort/flake8/mypy-clean on first generation,
> with full type hints, v14 contracts, no banned patterns, and template-first structure.
> Post-hoc cleanup is a failure mode, not a normal step."

This contract is:
- ✅ Non-negotiable
- ✅ Enforceable
- ✅ Measurable
- ✅ Automatic upon invocation

**Effective immediately. Applies to all future code generation requests.**

---

**Contract Version:** 1.0
**Status:** ✅ Canonical & Binding
**Owner:** DutchBay Team
**Authority:** GO_WITH_THE_FLOW_GOLD_STANDARD.md + SPRINT_4_ROADMAP.md
**Effective Date:** 2025-11-27 onwards
