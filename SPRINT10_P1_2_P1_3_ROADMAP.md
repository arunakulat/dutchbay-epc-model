# Sprint 10 Extended: P1.2 & P1.3 Optimization Roadmap

**Status**: Ready to Implement

**Timeline**: ~90 minutes total

---

## P1.2: Skip CSV Writes Optimization

**Objective**: Avoid I/O overhead during tests by skipping CSV/JSONL output

### Changes Required

**File**: `analytics/monte_carlo_v14.py`

**Approach 1: Function Parameter** (Recommended)

Add `write_output=False` parameter to control output:

```python
def _run_single_iteration(
    base_config_path: str | Path,
    scenario: Any,
    sample: Mapping[str, float],
    write_output: bool = True,  # NEW: Skip I/O when False
) -> dict[str, float] | None:
```

Then in iteration logic:

```python
    # Only write if explicitly requested (skip by default in tests)
    if write_output:
        write_csv(result)
        write_jsonl(result)
```

**Approach 2: Environment Variable** (Alternative)

```python
import os
WRITE_OUTPUT = os.getenv('MC_WRITE_OUTPUT', 'false').lower() == 'true'

if WRITE_OUTPUT:
    write_csv(result)
    write_jsonl(result)
```

### Where Output Writes Happen

Search for:
- `write_csv` calls
- `write_jsonl` calls  
- `.to_csv` calls
- File write operations

Typically in aggregation or iteration worker.

### Expected Impact

- **Current (P1.1)**: 40s
- **After P1.2**: 28-32s (20-30% reduction)
- **Risk**: LOW (I/O-only, no computation changes)

---

## P1.3: Parallel Iteration with Thread Pool

**Objective**: Run independent iterations in parallel threads with thread-safe RNG

### Changes Required

**File**: `analytics/monte_carlo_v14.py`

**Approach**: Replace multiprocessing.Pool with ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor
import threading

# Thread-safe counter for seeding
_iteration_counter = 0
_iteration_lock = threading.Lock()

def _run_serial_iterations(
    base_config_path: str,
    scenario: MonteCarloScenario,
    samples: list[dict[str, Any]],
    n_threads: int = 4,  # NEW: Use threads instead of processes
) -> list[dict[str, float] | None]:
    """
    Run Monte Carlo iterations in parallel using ThreadPoolExecutor.
    """
    def iteration_worker(iteration_idx: int, sample: dict[str, Any]):
        # Thread-safe RNG seeding
        rng = np.random.RandomState(seed=iteration_idx + 12345)
        return _run_single_iteration(base_config_path, scenario, sample)
    
    results = []
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [
            executor.submit(iteration_worker, idx, sample)
            for idx, sample in enumerate(samples)
        ]
        for future in futures:
            results.append(future.result())
    
    return results
```

### Thread-Safety Considerations

**Critical**: Ensure no global RNG state

```python
# ✓ GOOD: Thread-local RNG
rng = np.random.RandomState(seed=iteration_idx)

# ✗ BAD: Global RNG (will cause race conditions)
global_rng = np.random.default_rng()
```

### Determinism Verification

After implementation:

```bash
# Run test 3 times, should be identical
for i in {1..3}; do
  pytest tests/api/test_monte_carlo_regression_toy.py -v
done

# Compare outputs
diff <(pytest ... | grep -E "IRR|DSCR") \
     <(pytest ... | grep -E "IRR|DSCR")
# Should have no diff
```

### Expected Impact

- **Current (P1.2)**: 28-32s
- **After P1.3**: 20s (30-50% reduction on 4-core machine)
- **Risk**: MEDIUM (requires thread safety verification)

---

## Implementation Sequence

### Phase 1: P1.2 (30 minutes)

1. **Add parameter** (5 min)
   - Add `write_output=False` to function signature
   - Add conditional write logic

2. **Test** (10 min)
   - Run: `pytest tests/api/test_monte_carlo_regression_toy.py -v`
   - Expected: ~32-35s (should be noticeably faster)

3. **Verify** (5 min)
   - Check CSV/JSONL not written in test mode
   - Confirm no import errors

4. **Commit** (10 min)
   ```bash
   git add analytics/monte_carlo_v14.py
   git commit -m "Sprint 10 P1.2: Skip CSV writes during tests - 20-30% speedup"
   git push origin main
   ```

### Phase 2: P1.3 (45 minutes)

1. **Import ThreadPoolExecutor** (5 min)
   ```python
   from concurrent.futures import ThreadPoolExecutor
   import threading
   ```

2. **Implement thread-safe iteration** (15 min)
   - Add thread-local RNG seeding
   - Replace multiprocessing with ThreadPoolExecutor
   - Preserve result order

3. **Test determinism** (15 min)
   ```bash
   # Run 3 consecutive times
   for i in {1..3}; do
     pytest tests/api/test_monte_carlo_regression_toy.py -v > run$i.txt
   done
   
   # Compare
   diff run1.txt run2.txt && diff run2.txt run3.txt && echo "✅ Deterministic"
   ```

4. **Commit** (10 min)
   ```bash
   git add analytics/monte_carlo_v14.py
   git commit -m "Sprint 10 P1.3: Parallel iteration with ThreadPoolExecutor - 30-50% speedup"
   git push origin main
   ```

---

## Success Criteria

### P1.2
- ✅ CSV/JSONL writes skipped during tests
- ✅ Tests pass (no failures)
- ✅ Runtime: 28-32s (20-30% reduction from P1.1 baseline of 40s)
- ✅ Backward compatible (write_output defaults to True)

### P1.3
- ✅ Tests pass (no failures)
- ✅ Runtime: ~20s (30-50% reduction from P1.2 baseline of 32s)
- ✅ Deterministic (3 consecutive runs produce identical results)
- ✅ No race conditions or thread-safety issues
- ✅ All iterations complete successfully

### Overall (All Phases)
- ✅ Baseline: 54.82s
- ✅ P1.1 (Config caching): 40s (27% ↓)
- ✅ P1.2 (Skip CSV): 32s (20% ↓)
- ✅ P1.3 (Threading): 20s (37% ↓)
- ✅ **Total: 63% speedup** (54.82s → 20s)

---

## Risk Assessment

### P1.2: LOW RISK
- I/O-only optimization
- No computation changes
- Easy to revert if issues
- Backward compatible by default

### P1.3: MEDIUM RISK
- Requires thread-safety verification
- RNG seeding must be deterministic
- Monitor for race conditions
- Test thoroughly before merging

---

## Rollback Plan

If either optimization causes issues:

```bash
# Revert to P1.1 (working state)
git revert HEAD~1
git push origin main

# Or revert to pre-optimization
git reset --hard 45d6c83  # P1.1 commit
git push -f origin main
```

---

## Next Steps

1. Review this roadmap
2. Decide: Apply both P1.2 & P1.3 now or defer?
3. If yes:
   - Start with P1.2 (low risk)
   - Test thoroughly
   - Commit to main
   - Then apply P1.3
   - Run determinism tests

4. If no:
   - Keep this roadmap for future sprint
   - P1.1 is already merged and working

---

**Ready to continue? Proceed with P1.2 implementation.**

