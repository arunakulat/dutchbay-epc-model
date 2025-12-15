# Sprint 10 P1: Monte Carlo Speed Optimization (No Architecture Churn)

## Objective
**Reduce test runtime from 54.82s → ~20s (target 60% speedup) with zero behavioral changes.**

## Current Baseline
```
[4/8] Running Monte Carlo suite (explicit files)...
9 passed in 55.48s
```

Tests:
- `test_monte_carlo_regression_toy.py` (toy scenarios, configurable iterations)
- `test_cashflow_v14.py` (full pipeline)
- `test_debt_v14_construction.py` (debt module)
- `test_covenants_v14.py` (covenant checks)

---

## Low-Risk Optimizations (No Architecture Changes)

### Optimization 1: Cache Parsed Scenario Configs
**Where:** `analytics/monte_carlo_v14.py` → `run_monte_carlo_analysis()`

**Problem:** Each test iteration reloads + parses YAML/JSON config files.

**Fix:**
```python
# Before (current)
def run_monte_carlo_analysis(base_config_path, scenario_config_path, scenario_name, n_iterations):
    for i in range(n_iterations):
        config = load_config(base_config_path)  # Reload each time!
        scenario_cfg = load_config(scenario_config_path)  # Reload each time!
        result = run_single_iteration(config, scenario_cfg)

# After (cached)
_CONFIG_CACHE = {}  # Module-level cache

def run_monte_carlo_analysis(base_config_path, scenario_config_path, scenario_name, n_iterations):
    # Load once, cache
    if base_config_path not in _CONFIG_CACHE:
        _CONFIG_CACHE[base_config_path] = load_config(base_config_path)
    if scenario_config_path not in _CONFIG_CACHE:
        _CONFIG_CACHE[scenario_config_path] = load_config(scenario_config_path)
    
    config = _CONFIG_CACHE[base_config_path]
    scenario_cfg = _CONFIG_CACHE[scenario_config_path]
    
    for i in range(n_iterations):
        result = run_single_iteration(config, scenario_cfg)  # Config already loaded
```

**Impact:** ~20-30% speedup (if load_config dominates)
**Risk:** LOW (cache invalidation only if config path changes, which it doesn't within a test)

---

### Optimization 2: Skip Default CSV/JSONL Writes
**Where:** `analytics/monte_carlo_v14.py` → iteration output logic

**Problem:** After each iteration, writes CSV/JSONL to disk (I/O overhead).

**Fix:**
```python
# Before
def run_single_iteration(config, scenario_cfg):
    result = compute_scenario(config, scenario_cfg)
    write_csv(result)   # Always writes
    write_jsonl(result) # Always writes
    return result

# After
def run_single_iteration(config, scenario_cfg, write_output=False):
    result = compute_scenario(config, scenario_cfg)
    if write_output:  # Only if explicitly requested
        write_csv(result)
        write_jsonl(result)
    return result

# In tests:
results = run_monte_carlo_analysis(
    ...,
    write_output=False  # Disable for speed, enable for debugging
)
```

**Impact:** ~10-20% speedup (depends on file size/disk speed)
**Risk:** LOW (opt-in, backward compatible)

---

### Optimization 3: Parallel Iterations (Thread-Safe)
**Where:** `analytics/monte_carlo_v14.py` → iteration loop

**Problem:** Iterations are independent; can run in parallel.

**Fix:**
```python
from concurrent.futures import ThreadPoolExecutor
import numpy as np

def run_monte_carlo_analysis(base_config_path, scenario_config_path, scenario_name, n_iterations, n_threads=4):
    # Load configs once
    config = load_config(base_config_path)
    scenario_cfg = load_config(scenario_config_path)
    
    # Thread-safe iteration
    def iteration_worker(iteration_idx):
        # Each thread gets its own RNG seed (deterministic, no global RNG)
        rng = np.random.RandomState(seed=iteration_idx + 12345)
        result = run_single_iteration(config, scenario_cfg, rng=rng)
        return result
    
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        results = list(executor.map(iteration_worker, range(n_iterations)))
    
    return aggregate_results(results)
```

**Impact:** ~30-50% speedup on multi-core (4 threads)
**Risk:** MEDIUM
- Must ensure no global RNG state
- Must ensure result aggregation is thread-safe
- Must test determinism (same seed = same results)

---

## Implementation Order (Risk ↑ Complexity)

### Phase 1: Low-Risk Quick Wins (Commit 1)
1. Add config caching (Optimization 1)
2. Add write_output flag (Optimization 2)
3. Benchmark

### Phase 2: Parallelization (Commit 2)
1. Add thread pool iteration (Optimization 3)
2. Add thread-safe RNG seeding
3. Test determinism
4. Benchmark

---

## Testing Strategy

### Baseline Capture (Before Changes)
```bash
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short
# Record: 9 passed in 55.48s
```

### Phase 1 Validation (After Optimization 1 + 2)
```bash
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short
# Target: 9 passed in ~40s (27% speedup)
```

### Phase 2 Validation (After Optimization 3)
```bash
pytest tests/api/test_monte_carlo_regression_toy.py -v --tb=short
# Target: 9 passed in ~20s (60% speedup)
```

### Determinism Check (Critical)
```bash
# Run same test 3 times, verify results are identical
for i in {1..3}; do
  pytest tests/api/test_monte_carlo_regression_toy.py::test_toycase_mc_regression -v
done
# All 3 runs must produce identical output
```

---

## Files to Modify

1. **`analytics/monte_carlo_v14.py`**
   - Add config caching (module-level dict)
   - Add `write_output` parameter
   - Add parallel iteration with ThreadPoolExecutor
   - Add thread-safe RNG seeding

2. **`tests/api/test_monte_carlo_regression_toy.py`**
   - Add timing assertions (optional, for regression detection)
   - Verify results unchanged

---

## What NOT to Do

❌ Refactor core computation logic (causes bugs)
❌ Change RNG algorithm (breaks reproducibility)
❌ Add multiprocessing (pickle overhead > benefit for small iterations)
❌ Cache results across different scenario names (breaks isolation)

---

## Success Criteria

✅ Tests pass (zero failures)
✅ Results unchanged (outputs identical pre/post)
✅ Runtime < 25s (target 20s)
✅ Deterministic (run 3x, identical results)
✅ No merge conflicts with main

---

## Timeline

- **Phase 1 (Config + Write): 30 min** → Commit + Test
- **Phase 2 (Threading): 45 min** → Commit + Determinism Test
- **Integration: 15 min** → Merge to main
- **Total: ~90 min**

---

## Decision Point

Ready to start Phase 1? (Config caching + write_output flag)

Yes → Begin P1.1 implementation
No → Document concern, defer to P2
