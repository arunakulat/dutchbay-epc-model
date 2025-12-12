# SPRINT 4 IMPLEMENTATION ROADMAP
## Turning Gold Standard Ruleset Into Practice
**Timeline:** 1 Sprint (5 days) | **Effort:** 18 hours | **Outcome:** Emit-clean by construction

---

## OVERVIEW

This sprint executes the Gold Standard Ruleset (GO_WITH_THE_FLOW_GOLD_STANDARD.md) in concrete, measurable chunks.

**Success Criteria:**
- ✅ Pre-commit hooks installed and enforced for all developers
- ✅ Fast-lane CI validation available and documented
- ✅ Blessed templates created and adopted
- ✅ First 2 modules mypy-strict (gold standards)
- ✅ Team alignment meeting: ruleset reviewed, commitments made
- ✅ Zero new violations reach main branch

---

## DAY 1: PRE-COMMIT INFRASTRUCTURE (3 hours)

### Task 1.1: Create `.pre-commit-config.yaml` (45 min)

**File location:** `/.pre-commit-config.yaml` (repo root)

**Copy from Gold Standard Ruleset Section 4.1** – the full YAML config with:
- black (line-length=88)
- isort (black profile)
- flake8 (E/F/W/B codes, 88-char limit)
- mypy (strict, analytics/finance only)
- pre-commit-hooks (check-yaml, trailing-whitespace, etc.)

**Action:**
```bash
# Create file from template
cat > .pre-commit-config.yaml << 'EOF'
# [Paste config from Gold Standard Section 4.1]
EOF

# Verify syntax
pre-commit validate-config
```

---

### Task 1.2: Add pre-commit init to go_with_the_flow_ci.py (1 hour)

**Objective:** One-liner for developers to set up hooks.

**Code to add:**
```python
import subprocess

def init_git_hooks() -> None:
    """Initialize pre-commit hooks for the repository."""
    print("📋 Installing pre-commit hooks...")
    result = subprocess.run(
        ["pre-commit", "install"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("✅ Pre-commit hooks installed successfully")
    else:
        print(f"❌ Failed to install hooks: {result.stderr}")
        raise RuntimeError("pre-commit setup failed")

# Add to main CLI:
if __name__ == "__main__":
    parser.add_argument(
        "--init-hooks",
        action="store_true",
        help="Initialize pre-commit hooks (one-time setup)"
    )
    # Then: if args.init_hooks: init_git_hooks()
```

**Verification:**
```bash
python scripts/go_with_the_flow_ci.py --init-hooks
# Output: ✅ Pre-commit hooks installed successfully
```

---

### Task 1.3: Team Setup & Documentation (1.15 hours)

**Action:**
1. Update CONTRIBUTING.md:
   ```markdown
   ## Development Setup

   1. Clone repo
   2. Create venv: `python -m venv .venv && source .venv/bin/activate`
   3. Install dependencies: `pip install -e ".[dev]"`
   4. Initialize git hooks: `python scripts/go_with_the_flow_ci.py --init-hooks`
   5. Run fast validation: `python scripts/go_with_the_flow_ci.py --fast`

   **Important:** Pre-commit hooks will block commits with lint violations.
   This is intentional. Fix violations or redesign code.
   ```

2. Create HOOK_TROUBLESHOOTING.md (short FAQ):
   ```markdown
   # Pre-Commit Hooks FAQ

   Q: My commit was blocked. What now?
   A: Read the error message. Fix the code. Run `git add` again. Retry commit.

   Q: I need to bypass hooks (emergency only).
   A: `git commit --no-verify` (but this is a red flag for review).

   Q: Which files do hooks check?
   A: Only staged files (git add). Unstaged changes not checked.
   ```

---

## DAY 2: FAST-LANE CI VALIDATION (3.5 hours)

### Task 2.1: Implement `--fast` flag in go_with_the_flow_ci.py (2 hours)

**Objective:** Developers run `--fast --files <list>` before pushing.

**Code to add:**
```python
import argparse

def run_fast_validation(files: str) -> bool:
    """
    Run fast validation on specific files.

    files: comma-separated list (e.g. "analytics/foo.py,finance/bar.py")
    """
    file_list = [f.strip() for f in files.split(",")]

    print("🚀 Go-with-the-Flow FAST VALIDATION")
    print(f"Files: {', '.join(file_list)}\n")

    # 1. Black
    print("1️⃣  black --check ...")
    result = subprocess.run(
        ["black", "--check"] + file_list,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ black failed:\n{result.stdout}")
        return False
    print("✅ black: PASS\n")

    # 2. isort
    print("2️⃣  isort --check --profile black ...")
    result = subprocess.run(
        ["isort", "--check", "--profile", "black"] + file_list,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ isort failed:\n{result.stdout}")
        return False
    print("✅ isort: PASS\n")

    # 3. compileall (all analytics/finance)
    print("3️⃣  compileall on analytics/ and finance/ ...")
    for module in ["analytics", "finance"]:
        result = subprocess.run(
            ["python", "-m", "compileall", module],
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"❌ compileall failed on {module}")
            return False
    print("✅ compileall: PASS\n")

    # 4. Targeted pytest (if any test files)
    test_files = [f for f in file_list if f.startswith("tests/")]
    if test_files:
        print("4️⃣  pytest on changed tests ...")
        result = subprocess.run(
            ["pytest", "-v", "--tb=short"] + test_files,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"❌ pytest failed:\n{result.stdout}")
            return False
        print("✅ pytest: PASS\n")
    else:
        print("4️⃣  pytest: skipped (no test files changed)\n")

    # 5. mypy on changed source
    source_files = [f for f in file_list if f.startswith("analytics/") or f.startswith("finance/")]
    if source_files:
        print("5️⃣  mypy ...")
        result = subprocess.run(
            ["mypy", "--strict", "--ignore-missing-imports"] + source_files,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"⚠️  mypy warnings:\n{result.stdout}")
            # Don't fail on mypy; just warn
        else:
            print("✅ mypy: PASS\n")

    print("=" * 60)
    print("✅ ALL CHECKS PASSED - Ready for review!")
    print("=" * 60)
    return True

# Add CLI flag:
if __name__ == "__main__":
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run fast validation on specific files"
    )
    parser.add_argument(
        "--files",
        type=str,
        help="Comma-separated file list (e.g., 'analytics/foo.py,finance/bar.py')"
    )

    args = parser.parse_args()

    if args.fast:
        if not args.files:
            print("❌ --fast requires --files")
            sys.exit(1)
        success = run_fast_validation(args.files)
        sys.exit(0 if success else 1)
```

**Test:**
```bash
# Create a test file with a violation
echo 'x = 1' > analytics/test_violation.py

# Run fast check (should fail)
python scripts/go_with_the_flow_ci.py --fast --files analytics/test_violation.py

# Output should show which checks failed
```

---

### Task 2.2: Document workflow (1.5 hours)

**Create:** `docs/DEVELOPER_WORKFLOW.md`

```markdown
# Developer Workflow

## Before Pushing Code

### Step 1: Run Fast Validation
```bash
python scripts/go_with_the_flow_ci.py --fast --files analytics/foo.py,finance/bar.py
```

### Step 2: Review Output
- ✅ All checks passed? → Proceed to Step 3
- ❌ Some checks failed? → Fix issues, run again

### Step 3: Git Commit
```bash
git add analytics/foo.py finance/bar.py
git commit -m "feat: implement scenario discounting"
```

Pre-commit hooks will run automatically. If they pass, commit succeeds.
If they fail, fix the issues and retry.

### Step 4: Push & PR
```bash
git push origin feature/scenario-discounting
```

Open PR. CI pipeline runs (regression detection only, not violation fixing).

---

## Tips

**Q: What if I'm blocked by pre-commit?**
A: Read the error message. It tells you exactly what's wrong. Fix the code.
   - Black complaints: usually auto-fixable with `black <file>`
   - isort complaints: usually auto-fixable with `isort --profile black <file>`
   - flake8 complaints: design issue, must fix by hand
   - mypy complaints: add types or `# type: ignore` with reason

**Q: What if I need to bypass pre-commit (emergency)?**
A: `git commit --no-verify` (but this is a red flag for code review)

**Q: Can I commit something that doesn't pass --fast?**
A: No. The pre-commit hook will block it. Fix the code first.

---

## Common Failures

| Error | Fix |
|-------|-----|
| `black: line too long (102 chars)` | Rephrase or split line |
| `isort: imports out of order` | `isort --profile black <file>` |
| `flake8: F541 f-string has no placeholder` | Remove f-prefix or add placeholder |
| `mypy: Name is not defined` | Add type annotation |

---

See: GO_WITH_THE_FLOW_GOLD_STANDARD.md for full rules.
```

---

## DAY 3: BLESSED TEMPLATES (3 hours)

### Task 3.1: Create Template Files (2 hours)

**Location:** `scripts/templates/` (new directory)

**File 1: `scripts/templates/template_cli.py`**
- Copy from Gold Standard Section 5.1
- Add comments explaining each section
- Ready for copy-paste

**File 2: `analytics/template_v14.py`**
- Copy from Gold Standard Section 5.2
- Add comments
- Ready for copy-paste

**File 3: `tests/api/test_template_v14.py`**
- Copy from Gold Standard Section 5.3
- Add comments
- Ready for copy-paste

**Action:**
```bash
mkdir -p scripts/templates tests/templates

# Copy templates (content in Gold Standard Section 5)
cp <template_cli> scripts/templates/
cp <template_v14> analytics/templates/
cp <test_template> tests/templates/
```

---

### Task 3.2: Create TEMPLATES.md Guide (1 hour)

**File:** `docs/USING_TEMPLATES.md`

```markdown
# Using Blessed Templates

When starting a new module, CLI script, or test, start from these templates.
They're pre-configured for Go-with-the-Flow compliance.

## CLI Script Template
**When:** Building a new scripts/*.py utility
**Location:** `scripts/templates/template_cli.py`
**Copy:** `cp scripts/templates/template_cli.py scripts/my_new_script.py`
**Checklist:**
- [ ] Rename main() function to your use case
- [ ] Update docstring
- [ ] Add args via typer.Option/Argument
- [ ] Implement logic in main()

## Analytics Module Template
**When:** Building a new analytics/*.py module
**Location:** `analytics/templates/template_v14.py`
**Copy:** `cp analytics/templates/template_v14.py analytics/my_analysis.py`
**Checklist:**
- [ ] Update docstring
- [ ] Replace AnalysisConfig with your dataclass
- [ ] Implement run_analysis() or equivalent
- [ ] Add helper functions (private, _*) as needed
- [ ] All public functions fully typed

## Test Module Template
**When:** Writing tests for analytics/finance modules
**Location:** `tests/templates/test_template_v14.py`
**Copy:** `cp tests/templates/test_template_v14.py tests/api/test_my_feature.py`
**Checklist:**
- [ ] Update imports to match your module
- [ ] Add test classes (TestMyFeature)
- [ ] Use parametrize for variations
- [ ] Full type hints on test functions

---

## Why Templates Matter

Each template is **already Go-with-the-Flow-compliant**. When you start from
one, your code will pass pre-commit on first try (or close to it).

Templates demonstrate:
- ✅ Correct line breaks (≤88 chars)
- ✅ Proper type annotations
- ✅ Safe Typer patterns (no B008)
- ✅ Docstring formatting rules
- ✅ Import organization
```

---

## DAY 4: MYPY HARDENING (4 hours)

### Task 4.1: Make 2 Modules Mypy-Strict (3.5 hours)

**Choose modules:**
1. `analytics/scenario_analytics.py` (high-impact, orchestrator)
2. `finance/cashflow_v14.py` (core financial logic)

**Process per module:**

```bash
# 1. Check current mypy status
mypy --strict analytics/scenario_analytics.py

# 2. Count errors
# Output: "Found 42 errors in 1 file" (example)

# 3. Fix errors:
# For each error:
#   - Read error message carefully
#   - Add type annotation, or
#   - Add # type: ignore with reason (if legitimate)
#   - Rerun mypy

# 4. Iterate until:
mypy --strict analytics/scenario_analytics.py
# Output: "Success: no issues found in 1 file"

# 5. Add to pyproject.toml:
# [tool.mypy]
# files = ["analytics/scenario_analytics.py", "finance/cashflow_v14.py"]
# strict = true
```

**Expected time per module:** ~1.5-2 hours (depends on existing type coverage)

---

### Task 4.2: Document as Gold Standards (0.5 hours)

**Create:** `docs/MYPY_GOLD_STANDARDS.md`

```markdown
# MyPy Gold Standard Modules

These modules are fully type-annotated under `mypy --strict` and serve as
templates for new code.

## Gold Standard Modules
- analytics/scenario_analytics.py
- finance/cashflow_v14.py

## What "Gold Standard" Means
- 100% type-annotated (no Any, no implicit Optional)
- Zero # type: ignore (unless thoroughly justified)
- Passes mypy --strict with zero warnings
- Demonstrates best practices for:
  - Function argument types
  - Return type annotations
  - Dataclass typing
  - Generic types (List, Dict, Optional)

## When to Reference
- Writing new analytics/finance modules
- Wondering "how should I type this?"
- Reviewing code in those modules

## Future Path
All new code in analytics/ and finance/ should match this standard.
Legacy code gradually migrated during refactors.
```

---

## DAY 5: TEAM ALIGNMENT & LAUNCH (3 hours)

### Task 5.1: Team Meeting (1.5 hours)

**Agenda:**
1. Review GO_WITH_THE_FLOW_GOLD_STANDARD.md (30 min)
   - Philosophy: emit-clean by construction
   - Definition of Done checklist
   - Banned patterns

2. Walkthrough: Developer Workflow (30 min)
   - Show: `python scripts/go_with_the_flow_ci.py --fast --files ...`
   - Show: Pre-commit hook preventing bad commits
   - Show: Template usage

3. Q&A and commitments (30 min)
   - Address concerns
   - Get team buy-in
   - Assign ownership (who maintains templates? ruleset?)

---

### Task 5.2: Publish Documentation (1 hour)

**Checklist:**
- [ ] GO_WITH_THE_FLOW_GOLD_STANDARD.md → repo root or docs/
- [ ] DEVELOPER_WORKFLOW.md → docs/
- [ ] USING_TEMPLATES.md → docs/
- [ ] MYPY_GOLD_STANDARDS.md → docs/
- [ ] HOOK_TROUBLESHOOTING.md → docs/
- [ ] Update CONTRIBUTING.md with "Development Setup" section
- [ ] Link all docs from README.md

---

### Task 5.3: Verify Setup (0.5 hours)

**For each developer (or testing):**
```bash
# 1. Clone repo fresh
git clone https://github.com/arunakulat/dutchbay-epc-model.git
cd dutchbay-epc-model

# 2. Setup
python scripts/go_with_the_flow_ci.py --init-hooks

# 3. Test fast validation
python scripts/go_with_the_flow_ci.py --fast --files analytics/fx/processor.py

# 4. Try committing bad code (should fail)
echo 'x = 1' >> analytics/test_bad.py
git add analytics/test_bad.py
git commit -m "test"  # Should be blocked

# 5. Remove bad code, commit clean code (should pass)
git restore analytics/test_bad.py
git commit -m "cleanup"  # Should succeed
```

---

## SPRINT 4 SUMMARY

| Day | Task | Time | Output |
|-----|------|------|--------|
| 1 | Pre-commit setup | 3h | .pre-commit-config.yaml, go_with_the_flow init-hooks |
| 2 | Fast-lane CI | 3.5h | --fast --files flag, DEVELOPER_WORKFLOW.md |
| 3 | Templates | 3h | template_cli.py, template_v14.py, test_template_v14.py, USING_TEMPLATES.md |
| 4 | MyPy hardening | 4h | 2 modules mypy-strict, MYPY_GOLD_STANDARDS.md |
| 5 | Team alignment | 3h | Team meeting, documentation published, setup verified |
| **TOTAL** | | **16.5h** | **Emit-clean infrastructure ready** |

---

## SUCCESS CRITERIA (End of Sprint 4)

- ✅ Pre-commit hooks installed & enforced for all developers
- ✅ `python scripts/go_with_the_flow_ci.py --fast --files <list>` works
- ✅ Blessed templates available and documented
- ✅ 2 modules mypy-strict (gold standards)
- ✅ All documentation published and linked
- ✅ Team trained and committed
- ✅ **Zero new violations reach main branch**

---

## SPRINT 5+ EXPECTATIONS

With this infrastructure in place:

**New Code:**
- All new modules start from blessed templates
- Developer runs `--fast` before push (catches issues locally)
- Pre-commit hook blocks violations (zero reach main)
- CI runs regression detection only (fast, focused)

**Result:**
- No more Phase 2/3 linting sprints
- 2-3 hours/week recovered per developer
- Code review focused on logic, not formatting
- Velocity increases

---

**Sprint 4: READY TO EXECUTE** ✅
