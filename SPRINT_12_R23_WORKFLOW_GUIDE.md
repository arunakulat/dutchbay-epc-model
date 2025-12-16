# Sprint 12: Monte Carlo Implementation - R23 Workflow Guide

**Status:** 🚀 Branch `feature/sprint12-monte-carlo` ACTIVE  
**Date:** December 17, 2025, 00:34 IST  
**Rule:** R23 - Branch-based development with full CI gate  
**Committer:** Will follow R23 workflow for all commits

---

## 📋 R23 Workflow Checklist

Follow this checklist for EVERY commit:

```
☐ Branch created:           git checkout -b feature/sprint12-monte-carlo
☐ Local development done:   make changes
☐ Pytest green:             pytest ✅
☐ Mypy green:               mypy . ✅
☐ Pre-commit passed:        git commit (hooks run automatically)
☐ Pushed to feature branch: git push origin feature/sprint12-monte-carlo
☐ PR opened on GitHub:      Waiting for CI
☐ CI gate passed:           pytest + mypy + linting all ✅
☐ Reviewed & merged:        Branch merged to main
☐ Branch deleted locally:   git branch -d feature/sprint12-monte-carlo
☐ Branch deleted remotely:  git push origin --delete feature/sprint12-monte-carlo
☐ Local synced:             git pull origin main
☐ Final local test:         pytest (sanity check) ✅
```

---

## 🎯 Sprint 12 Monte Carlo Objectives

### Phase 1: Core Implementation (This Branch)
1. ✅ **Refinancing Module** - Mid-life debt restructuring
2. ✅ **Equity Distribution Module** - Post-payoff cash distribution
3. 🔄 **Monte Carlo Engine** - 100K iteration stochastic analysis
4. 🔄 **Stress Testing** - 6 variant scenarios
5. 🔄 **Risk Reporting** - VaR, CVaR, percentiles

### Phase 2: Integration & Testing
- Deterministic baseline validation
- Monte Carlo convergence tests
- Stress test covenant breach probability
- Lender submission readiness

---

## 📁 Key Files to Work On

```
DutchBay_EPC_Model/
├── finance/
│   ├── refinancing_v14_hydra.py        ← Module 1: Refinancing
│   ├── equity_distribution_v14_hydra.py ← Module 2: Equity Distributions
│   └── debt_v14.py                      ← Already done
│
├── analytics/
│   └── monte_carlo_v14.py               ← Module 3: Monte Carlo Engine
│
├── scripts/
│   └── run_full_pipeline_sprint12.py    ← Master CLI entry point
│
├── config/
│   ├── monte_carlo_regression_production.yaml
│   ├── dutchbay_lendercase_2025Q4.yaml
│   └── scenarios/stress_tests/
│       ├── stress_tariff_minus_20.yaml
│       ├── stress_capex_plus_20.yaml
│       ├── stress_opex_inflation_2pct.yaml
│       ├── stress_fx_depr_50pct.yaml
│       ├── stress_capacity_minus_10.yaml
│       └── stress_combined_worst.yaml
│
└── tests/
    ├── api/test_refinancing_v14.py
    ├── api/test_equity_distribution_v14.py
    ├── api/test_monte_carlo_v14.py
    └── api/test_stress_tests_v14.py
```

---

## 🛠️ Local Setup (5 minutes)

```bash
# 1. Navigate to repo
cd ~/path/to/DutchBay_EPC_Model

# 2. Activate venv
source .venv311/bin/activate

# 3. Verify you're on the feature branch
git status
# Should show: On branch feature/sprint12-monte-carlo

# 4. Pull any latest changes from main (in case team pushed)
git fetch origin main

# 5. Bootstrap the project
python dutchbay_bootstrap.py
# Expected output: All checks green ✅
```

---

## 🧪 Testing Strategy

### Before Commit

```bash
# 1. Run pytest (all tests)
pytest
# Status: must be green ✅

# 2. Run mypy (type checking)
mypy .
# Status: must be clean ✅

# 3. Pre-commit hooks (automatic on git commit)
# Check:
#   - black (formatting)
#   - ruff (linting)
#   - isort (import sorting)
#   - mypy (typing)
#   - file checks
```

### Focused Testing (During Development)

```bash
# Test specific module only
pytest tests/api/test_refinancing_v14.py -v
pytest tests/api/test_equity_distribution_v14.py -v
pytest tests/api/test_monte_carlo_v14.py -v

# Skip coverage for faster iteration
pytest tests/api/test_refinancing_v14.py --no-cov

# Run with print output (debugging)
pytest tests/api/test_monte_carlo_v14.py -s
```

### Integration Tests

```bash
# Test full pipeline (includes refinancing + equity + MC)
python scripts/run_full_pipeline_sprint12.py --config scenarios/dutchbay_lendercase_2025Q4.yaml --n-iterations 100 --write-output false
# Expected: Completes in <10s with 100 iterations, shows results
```

---

## 📝 Commit Message Format (R18 - Descriptive commits)

All commits must follow:
```
type: brief summary

Optional body with details and test status.
```

**Types:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

**Examples:**
```bash
git commit -m "feat: implement refinancing module with trigger logic

- Added RefinancingCalculator class
- Implements mid-life debt restructuring at Year 8
- Tests: test_refinancing_v14.py (8 tests green)
- Mypy: clean

Issue: #42"

git commit -m "test: add regression pins for equity distribution

- Added test_equity_distribution_v14_regression.py
- Pins cumulative distributions at $45.8M
- Pins equity IRR at 19.8%
- Tests: all green ✅"

git commit -m "chore: add Monte Carlo config templates

- Added monte_carlo_regression_production.yaml
- Added 6 stress test configs
- No logic changes, ready for implementation"
```

---

## 🔄 Git Workflow - Step by Step

### You Are Here ✅

```bash
Step 1: Branch created
✅ git checkout -b feature/sprint12-monte-carlo
✅ Branch now active at commit 3886d9e1d024 (R23 rule added)
```

### For Each Feature/Fix

```bash
# Step 2: Make changes
vim finance/refinancing_v14_hydra.py   # Edit code

# Step 3: Test locally
pytest tests/api/test_refinancing_v14.py --no-cov  # ✅ Green
mypy finance/refinancing_v14_hydra.py              # ✅ Clean

# Step 4: Commit with R18 format
git add finance/refinancing_v14_hydra.py
git commit -m "feat: implement refinancing calculator

- Added RefinancingCalculator with mid-life restructuring
- Tests pass (8 green)
- Mypy clean"
# Pre-commit hooks run automatically

# Step 5: Push to feature branch
git push origin feature/sprint12-monte-carlo
```

### Once Feature Complete

```bash
# Step 6: Open PR on GitHub (you'll see link in terminal)
# Copy the URL and click to open PR
# Add description: what changed, why, test status

# Step 7: Wait for CI (GitHub Actions)
# - pytest runs on all tests
# - mypy runs on all modules
# - linting checks (black, ruff, isort)
# - Status shows in PR

# Step 8: Approve & Merge (when CI green)
# Click "Merge pull request" in GitHub
# Choose "Squash and merge" for clean history

# Step 9: Delete branch (local + remote)
git branch -d feature/sprint12-monte-carlo
git push origin --delete feature/sprint12-monte-carlo

# Step 10: Sync local to main
git pull origin main

# Step 11: Final sanity check
pytest tests/api/test_refinancing_v14.py --no-cov  # ✅ Still green
```

---

## 📊 Expected Deliverables (This Branch)

After all commits merged and R23 workflow complete:

### 1. Refinancing Module
- ✅ File: `finance/refinancing_v14_hydra.py`
- ✅ Tests: `tests/api/test_refinancing_v14.py`
- ✅ Integration: Works with `run_full_pipeline_sprint12.py`
- ✅ Config: YAML-driven via Hydra

### 2. Equity Distribution Module
- ✅ File: `finance/equity_distribution_v14_hydra.py`
- ✅ Tests: `tests/api/test_equity_distribution_v14.py`
- ✅ Integration: Triggered post-debt-payoff
- ✅ Config: YAML-driven via Hydra

### 3. Monte Carlo Engine
- ✅ File: `analytics/monte_carlo_v14.py`
- ✅ Tests: `tests/api/test_monte_carlo_v14.py`
- ✅ LHS sampling: Latin Hypercube Sampling
- ✅ Risk metrics: VaR, CVaR, percentiles
- ✅ Stress tests: 6 scenarios x N iterations

### 4. Pipeline CLI
- ✅ File: `scripts/run_full_pipeline_sprint12.py`
- ✅ Entry point: Hydra-based, config-first
- ✅ Outputs: JSON, CSV, JSONL
- ✅ Lender-ready: Summary tables + risk metrics

### 5. Configuration Files
- ✅ `config/monte_carlo_regression_production.yaml`
- ✅ `config/dutchbay_lendercase_2025Q4.yaml` (updated)
- ✅ 6 stress test configs in `config/scenarios/stress_tests/`

### 6. Documentation
- ✅ Module docstrings (Google-style)
- ✅ Type hints on all public APIs
- ✅ Integration examples in docstrings
- ✅ This workflow guide (SPRINT_12_R23_WORKFLOW_GUIDE.md)

---

## 🚨 Critical Rules (R23 Enforcement)

### ❌ Never Do This

```bash
# ❌ DO NOT commit directly to main
git checkout main
git add .
git commit -m "quick fix"  # BLOCKED by branch protection

# ❌ DO NOT skip tests before pushing
git push origin feature/...  # Without pytest ✅

# ❌ DO NOT merge without CI passing
# GitHub will block merge if CI fails

# ❌ DO NOT force-push
git push --force origin feature/...  # Never!

# ❌ DO NOT leave branches orphaned
# Always delete after merging
```

### ✅ Always Do This

```bash
# ✅ Always create branch first
git checkout -b feature/descriptive-name

# ✅ Always test before pushing
pytest && mypy .  # Green ✅

# ✅ Always use descriptive commits (R18)
git commit -m "feat: what changed

Why and test status."

# ✅ Always wait for CI
# GitHub CI must pass before merging

# ✅ Always clean up branches
git branch -d feature/...
git push origin --delete feature/...

# ✅ Always sync main after merge
git pull origin main
```

---

## 📞 Troubleshooting

### Pytest fails locally but passes on CI

```bash
# 1. Clean cache
rm -rf .pytest_cache __pycache__ .mypy_cache

# 2. Reinstall dependencies
pip install -e . --force-reinstall

# 3. Run pytest again
pytest
```

### Mypy complains but code works

```bash
# 1. Check for Any types
mypy . --warn-unused-ignores

# 2. Add type hints to function
def calculate_irr(cashflows: list[float]) -> float | None:
    ...

# 3. Re-run
mypy .
```

### Pre-commit hook fails

```bash
# Pre-commit failures are hints, not blockers
# Fix the issues:

# Black formatting:
black .

# Ruff linting:
ruff check --fix .

# isort imports:
isort .

# Re-commit
git add .
git commit -m "..."
```

### Can't push to feature branch

```bash
# Ensure you're on the right branch
git branch
# Should show: * feature/sprint12-monte-carlo

# Verify remote exists
git remote -v
# Should show origin pointing to dutchbay-epc-model

# Try push again
git push origin feature/sprint12-monte-carlo
```

---

## 🎓 Learning Resources

### Git + R23 Workflow
- `git checkout -b` - Create branch
- `git push origin <branch>` - Push feature branch
- `git branch -d <branch>` - Delete local branch
- `git push origin --delete <branch>` - Delete remote branch

### Testing
- `pytest tests/api/` - Run API tests
- `pytest --no-cov` - Skip coverage (faster)
- `pytest -s` - Show print output
- `pytest -v` - Verbose output

### Type Checking
- `mypy .` - Check all modules
- `mypy finance/` - Check specific directory
- `mypy --strict .` - Strict mode (use for new code)

### Pre-commit
- Automatic on `git commit`
- Runs: black, ruff, isort, mypy, file checks
- If fails, fix and re-commit

---

## ✅ Ready to Start

**Your branch:** `feature/sprint12-monte-carlo`  
**Current commit:** 3886d9e1d024  
**Rule enforcement:** R23 active  
**Your mission:** Implement Monte Carlo modules with full test coverage

```bash
# You are here:
# 🟢 Branch created
# 🟡 Development phase begins
# ⚪ Testing phase
# ⚪ Pushing & CI
# ⚪ Merge & cleanup

# Next: Start with refinancing module
# cd DutchBay_EPC_Model && source .venv311/bin/activate
# Begin editing finance/refinancing_v14_hydra.py
```

---

**Last Updated:** December 17, 2025, 00:34 IST  
**Branch Status:** 🟢 ACTIVE  
**R23 Compliance:** ✅ Full
