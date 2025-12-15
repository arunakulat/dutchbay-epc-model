# Sprint 10: End-of-Sprint Checklist

**Status**: Ready for Pull

**Date Created**: 2025-12-15

**Branch**: `sprint-10-linting-cleanup`

---

## Pre-Pull Checklist (Your Side)

- [ ] Understand what's been completed (P0: Validation)
- [ ] Understand what's staged (P1: Speed optimization)
- [ ] Decide on P1.1 application (optional)
- [ ] Allocate ~2.5 hours for full P1 if applying all three phases

---

## Pull & Review (5 minutes)

```bash
# Fetch latest
git fetch origin sprint-10-linting-cleanup
git checkout sprint-10-linting-cleanup
git pull origin sprint-10-linting-cleanup

# List artifacts
ls -la SPRINT10*.md P1_*.txt *.sh | head -20

# Read main summary
cat SPRINT10_FINAL_SUMMARY.md
```

- [ ] Pull successful
- [ ] Read SPRINT10_FINAL_SUMMARY.md
- [ ] Understand P0 (merged, complete)
- [ ] Understand P1 (staged, optional to apply)

---

## P1 Application Decision (1 minute)

**Choose one**:

### Option A: Apply P1.1 Now (Recommended)

- [ ] Apply P1.1 config caching
- [ ] Test (expect ~27% speedup)
- [ ] Commit & merge to main
- [ ] **Timeline**: ~30 minutes

```bash
# Automated
bash SPRINT10_P1_IMPLEMENTATION_SCRIPT.sh

# Test
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short

# Commit
git add analytics/monte_carlo_v14.py
git commit -m "Sprint 10 P1.1: Config caching optimization - 27% speedup"
git push origin sprint-10-linting-cleanup
```

### Option B: Skip P1 For Now (Also Valid)

- [ ] Merge branch without P1.1
- [ ] Keep documentation for future reference
- [ ] **Timeline**: ~5 minutes

```bash
git checkout main
git merge sprint-10-linting-cleanup -m "Merge Sprint 10: Validation cleanup"
```

### Option C: Apply P1.2 & P1.3 Later

- [ ] Keep branch for future sprints
- [ ] Documentation is ready
- [ ] Scripts can be extended

---

## If Choosing Option A (Apply P1.1)

### Step 1: Validate Environment (2 minutes)

```bash
# Check Python version
python3 --version  # Should be 3.11+

# Check pytest available
pytest --version

# Check file exists
test -f analytics/monte_carlo_v14.py && echo "✓ File found"

# Backup original
cp analytics/monte_carlo_v14.py analytics/monte_carlo_v14.py.backup
```

- [ ] Python 3.11+ available
- [ ] pytest available
- [ ] monte_carlo_v14.py backed up

### Step 2: Apply P1.1 (5 minutes)

```bash
# Make script executable
chmod +x SPRINT10_P1_IMPLEMENTATION_SCRIPT.sh

# Run implementation
bash SPRINT10_P1_IMPLEMENTATION_SCRIPT.sh

# Expected output:
# ✅ Added _CONFIG_CACHE dict
# ✅ Added config caching logic
# ✅ Syntax valid
# ✅ Sprint 10 P1.1 Complete
```

- [ ] Script executed
- [ ] No errors reported
- [ ] Backup created

### Step 3: Verify Changes (5 minutes)

```bash
# Check syntax
python3 -m py_compile analytics/monte_carlo_v14.py
echo "Syntax valid ✓"

# View changes (optional)
git diff analytics/monte_carlo_v14.py | head -50

# Check cache dict added
grep -n "_CONFIG_CACHE" analytics/monte_carlo_v14.py
echo "Expected: 2 matches"
```

- [ ] Syntax check passes
- [ ] _CONFIG_CACHE found (2 occurrences)
- [ ] No syntax errors

### Step 4: Run Baseline Test (30 seconds)

```bash
# Run test (without timing initially)
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short 2>&1 | head -20

# Should see: 9 passed
```

- [ ] Test command executes
- [ ] No import errors
- [ ] No test failures

### Step 5: Full Test Run (1-2 minutes)

```bash
# Time the test
time pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short

# Record runtime - should be ~40s (vs baseline 54.82s)
# If ~40s: P1.1 working ✓
# If ~55s: Cache not working, debug needed
```

- [ ] All 9 tests pass
- [ ] Runtime recorded
- [ ] Expected: ~40s (27% reduction from 54.82s baseline)

### Step 6: Verify Determinism (2 minutes)

```bash
# Run test 2 more times
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short > run1.txt
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short > run2.txt

# Compare outputs
diff run1.txt run2.txt
echo "If no diff: Determinism preserved ✓"

# Cleanup
rm run1.txt run2.txt
```

- [ ] 3 consecutive runs produce identical results
- [ ] Determinism verified

### Step 7: Commit Changes (5 minutes)

```bash
# Stage changes
git add analytics/monte_carlo_v14.py

# Show what's staged
git diff --staged | head -30

# Commit
git commit -m "Sprint 10 P1.1: Config caching optimization

- Add module-level _CONFIG_CACHE dict to avoid YAML reloads
- Cache MonteCarloConfig objects by file path
- 27% speedup: 54.82s → 40s
- Zero breaking changes, fully backward compatible
- All 9 tests pass with identical results (determinism preserved)"

# Push
git push origin sprint-10-linting-cleanup
```

- [ ] Changes staged
- [ ] Commit message written
- [ ] Changes pushed to GitHub

### Step 8: Merge to Main (5 minutes)

```bash
# Update main
git checkout main
git pull origin main

# Verify main is clean
git status

# Merge sprint-10 branch
git merge sprint-10-linting-cleanup -m "Merge Sprint 10: Validation + P1.1 optimization

Includes:
- P0: Validation suite, pipeline canonical, output cleanup, linting
- P1.1: Config caching optimization (27% speedup)

Tests: All pass with identical results
Runtim: 54.82s → 40s
Churn: Zero architecture changes"

# Push to main
git push origin main
```

- [ ] Switched to main
- [ ] main pulled from origin
- [ ] sprint-10 merged to main
- [ ] Merge pushed to origin

### Step 9: Verify Main (2 minutes)

```bash
# Check main has merge commit
git log --oneline | head -5

# Should show: Merge Sprint 10: ...

# Verify monte_carlo_v14.py in main
git show main:analytics/monte_carlo_v14.py | grep "_CONFIG_CACHE" | wc -l

# Should show: 2 matches
```

- [ ] Merge commit visible in main
- [ ] Changes present in main
- [ ] Main is up-to-date with origin

---

## Post-Merge (1 minute)

```bash
# Cleanup branch artifacts (optional)
rm -f SPRINT10*.md SPRINT10*.txt P1_*.txt SPRINT10*.sh

# Optional: Delete branch if no longer needed
git branch -D sprint-10-linting-cleanup
```

- [ ] Main is merged and clean
- [ ] Branch artifacts cleaned up
- [ ] Sprint 10 complete

---

## Troubleshooting

### Issue: "_CONFIG_CACHE not found" after script

**Solution**:
```bash
# Check file was modified
git diff analytics/monte_carlo_v14.py | grep _CONFIG_CACHE

# If not visible, run script again
bash SPRINT10_P1_IMPLEMENTATION_SCRIPT.sh
```

### Issue: Test still takes 54s (cache not working)

**Solution**:
```bash
# Check if cache logic is in place
grep -A 5 "if scenario_config_path in _CONFIG_CACHE" analytics/monte_carlo_v14.py

# If not found, revert and try manual application
cp analytics/monte_carlo_v14.py.backup analytics/monte_carlo_v14.py
cat P1_1_READY_TO_APPLY.txt
```

### Issue: Syntax errors after script

**Solution**:
```bash
# Revert to backup
cp analytics/monte_carlo_v14.py.backup analytics/monte_carlo_v14.py

# Try manual approach
cat P1_1_READY_TO_APPLY.txt
# Make edits carefully
vi analytics/monte_carlo_v14.py
python3 -m py_compile analytics/monte_carlo_v14.py
```

---

## Final Checklist

- [ ] Branch pulled
- [ ] SPRINT10_FINAL_SUMMARY.md read
- [ ] Decision made (apply P1.1 or skip)
- [ ] If P1.1 applied:
  - [ ] Changes applied successfully
  - [ ] Tests pass
  - [ ] Speedup verified (~40s)
  - [ ] Determinism verified (3 runs identical)
  - [ ] Changes committed
  - [ ] Branch merged to main
  - [ ] Main updated
- [ ] Sprint 10 complete ✅

---

## Duration Estimates

| Task | Time |
|------|------|
| Pull & Review | 5 min |
| P1.1 Application (if chosen) | 30 min |
| Testing & Verification | 5 min |
| Commit & Merge | 10 min |
| **Total (with P1.1)** | **~50 min** |
| **Total (skip P1.1)** | **~5 min** |

---

## Questions?

Refer to:
- `SPRINT10_FINAL_SUMMARY.md` - Comprehensive guide
- `SPRINT10_P1_PLAN.md` - Optimization strategy
- `P1_1_READY_TO_APPLY.txt` - Manual implementation

---

**Sprint 10 Complete ✅**

All planning, documentation, and implementation ready.
Pull branch, review, decide on P1.1 application, merge when ready.

