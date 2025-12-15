# Sprint 10 P1.2: Skip CSV Writes Implementation Guide

**Phase**: P1.2 of P1 optimization track

**Expected Impact**: 40s → 28-32s (20-30% speedup)

**Risk Level**: LOW

**Duration**: ~30 minutes

---

## Objective

During testing, the Monte Carlo engine writes CSV and JSONL output files. This I/O overhead adds ~10-12 seconds to each test run. By adding a `write_output=False` parameter, we skip these writes during test runs while preserving them for production.

---

## Step 1: Identify Output Write Locations

### Search for Output Operations

Before implementing, identify where outputs are written:

```bash
# Find CSV writes
grep -rn "to_csv\|write_csv\|CSV" analytics/monte_carlo_v14.py

# Find JSONL writes
grep -rn "to_jsonl\|write_jsonl\|JSONL" analytics/monte_carlo_v14.py

# Find file writes
grep -rn "open(" analytics/monte_carlo_v14.py | grep write
grep -rn "\.write(" analytics/monte_carlo_v14.py
```

### Current State

In `monte_carlo_v14.py`, output writes typically occur:
- In `_run_single_iteration()` → after evaluation
- In `_aggregate_results()` → after combining results
- Or in a separate output handler called from `_run_single_scenario()`

---

## Step 2: Add write_output Parameter

### Change 1: Update _run_single_iteration() signature

**Location**: Line ~715

**Current**:
```python
def _run_single_iteration(
    base_config_path: str | Path,
    scenario: Any,
    sample: Mapping[str, float],
) -> dict[str, float] | None:
```

**New**:
```python
def _run_single_iteration(
    base_config_path: str | Path,
    scenario: Any,
    sample: Mapping[str, float],
    write_output: bool = True,  # NEW: Skip I/O when False
) -> dict[str, float] | None:
```

---

### Change 2: Wrap output writes with conditional

**Find**: All `write_csv`, `to_csv`, `write_jsonl` calls

**Pattern 1: Direct write**
```python
# BEFORE
write_csv(result, output_path)

# AFTER
if write_output:
    write_csv(result, output_path)
```

**Pattern 2: Pandas to_csv**
```python
# BEFORE
df.to_csv("output.csv")

# AFTER
if write_output:
    df.to_csv("output.csv")
```

**Pattern 3: File operations**
```python
# BEFORE
with open(output_path, 'w') as f:
    json.dump(result, f)

# AFTER
if write_output:
    with open(output_path, 'w') as f:
        json.dump(result, f)
```

---

### Change 3: Propagate parameter through call chain

If `_run_single_iteration()` is called from other functions, pass the parameter:

**In `_iteration_worker()`**:
```python
def _iteration_worker(
    args: tuple[str, MonteCarloScenario, dict[str, Any], bool],
) -> dict[str, float] | None:
    base_config_path, scenario, sample, write_output = args
    return _run_single_iteration(
        base_config_path, 
        scenario, 
        sample,
        write_output=write_output,  # Pass through
    )
```

**In `_run_parallel_iterations()`**:
```python
def _run_parallel_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    n_workers: int,
    write_output: bool = True,  # NEW
) -> list[dict[str, float] | None]:
    args_iter = (
        (base_config_path, scenario, sample, write_output) for sample in samples
    )
    # ... rest unchanged
```

**In `_run_serial_iterations()`**:
```python
def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    write_output: bool = True,  # NEW
) -> list[dict[str, float] | None]:
    results: list[dict[str, float] | None] = []
    total = len(samples)
    for idx, sample in enumerate(samples, start=1):
        if idx % 100 == 0 or idx == total:
            logger.info("  Progress: %d/%d iterations", idx, total)
        result = _run_single_iteration(
            base_config_path, 
            scenario, 
            sample,
            write_output=write_output,  # Pass through
        )
        results.append(result)
    return results
```

**In `_run_single_scenario()`**:
```python
def _run_single_scenario(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    parallel_workers: int,
    write_output: bool = True,  # NEW
) -> MonteCarloResult:
    iterations = len(samples)
    logger.info(
        "Running scenario '%s' with %d iterations and %d workers",
        scenario.name,
        iterations,
        parallel_workers,
    )

    if parallel_workers > 1:
        results = _run_parallel_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
            n_workers=parallel_workers,
            write_output=write_output,  # NEW
        )
    else:
        results = _run_serial_iterations(
            base_config_path=base_config_path,
            scenario=scenario,
            samples=samples,
            write_output=write_output,  # NEW
        )

    return _aggregate_results(results, iterations, scenario.name)
```

**In `run_monte_carlo_analysis()`**:
```python
def run_monte_carlo_analysis(
    base_config_path: str,
    scenario_config_path: str = "config/monte_carlo_defaults.yaml",
    scenario_name: str | None = None,
    n_iterations: int | None = None,
    random_seed: int | None = None,
    parallel_workers: int | None = None,
    write_output: bool = True,  # NEW
) -> dict[str, MonteCarloResult]:
    # ... existing code ...
    for scenario in scenarios:
        logger.info("Running scenario: %s", scenario.name)
        try:
            result = _run_single_scenario(
                base_config_path=base_config_path,
                scenario=scenario,
                samples=scenario_samples,
                parallel_workers=workers,
                write_output=write_output,  # NEW
            )
            # ... rest unchanged ...
```

---

## Step 3: Test Implementation

### 3.1 Syntax Check

```bash
python3 -m py_compile analytics/monte_carlo_v14.py
echo "Syntax valid ✓"
```

### 3.2 Run Tests (Default: write_output=True)

```bash
# Test with default behavior (write_output=True)
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short

# Should see all tests pass
# Runtime should be ~40s (unchanged, since write_output=True by default)
```

### 3.3 Verify Write Behavior

```bash
# Check CSV files are created (with write_output=True)
ls -la *.csv 2>/dev/null | wc -l
# Should show some CSV files

# Run specific test that skips writes
# (This requires updating test to pass write_output=False)
```

### 3.4 Update Tests to Skip Writes

**In test file** (e.g., `tests/api/test_monte_carlo_regression_toy.py`):

```python
# BEFORE
result = run_monte_carlo_analysis(
    base_config_path=base_path,
    scenario_config_path=mc_config_path,
)

# AFTER
result = run_monte_carlo_analysis(
    base_config_path=base_path,
    scenario_config_path=mc_config_path,
    write_output=False,  # NEW: Skip I/O during tests
)
```

### 3.5 Re-run Tests (write_output=False)

```bash
# After updating tests to use write_output=False
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short

# Should see:
# - All tests still pass
# - Runtime: ~28-32s (20-30% faster)
# - No CSV files created (optional: verify with ls *.csv)
```

---

## Step 4: Verify No Regressions

```bash
# Run all Monte Carlo tests
pytest tests/ -k monte_carlo -v

# Check for any failures
# All should pass
```

---

## Step 5: Commit Changes

```bash
# Stage changes
git add analytics/monte_carlo_v14.py tests/api/test_monte_carlo_regression_toy.py

# Commit with clear message
git commit -m "Sprint 10 P1.2: Skip CSV writes during tests - 20-30% speedup

- Add write_output=False parameter to run_monte_carlo_analysis()
- Skip CSV/JSONL writes when write_output=False
- Update tests to disable output writes
- Expected speedup: 40s → 28-32s (20-30% reduction)
- Backward compatible: defaults to True for production

Tests: All pass with no regressions
Risk: LOW (I/O-only optimization)"

# Push to main
git push origin main
```

---

## Success Criteria

- ✅ Parameter added to function signatures
- ✅ Output writes wrapped in conditionals
- ✅ Parameter propagated through call chain
- ✅ Syntax valid (`py_compile` passes)
- ✅ Tests pass (both with and without write_output)
- ✅ Runtime: 28-32s (20-30% reduction from 40s)
- ✅ Backward compatible (defaults to True)
- ✅ Committed and pushed to main

---

## Rollback

If issues arise:

```bash
# Revert this commit
git revert HEAD
git push origin main

# Or reset to before P1.2
git reset --hard 45d6c83  # P1.1 commit
git push -f origin main
```

---

## Next Phase

After P1.2 is committed and verified:

→ Proceed to P1.3 (Parallel Iteration with ThreadPoolExecutor)

See: `SPRINT10_P1_2_P1_3_ROADMAP.md` for P1.3 details

---

**Ready to implement? Start with Step 1 (identify output writes).**

