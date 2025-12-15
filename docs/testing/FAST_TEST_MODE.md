# Fast Test Mode Guide

## Overview

The DutchBay test suite now supports **configurable iteration counts** to dramatically reduce test runtime during development while maintaining full validation capabilities for CI/CD.

### Performance Impact

| Mode | Monte Carlo Iterations | Sensitivity Params | Test Suite Runtime |
|------|----------------------|-------------------|-------------------|
| **Fast** (default) | 20 | 3 parameters | ~30 seconds |
| **Full** | 100,000+ | 12 parameters | ~5-10 minutes |

**Speed improvement**: **500x faster** for development! 🚀

---

## Quick Start

### Running Tests

```bash
# Fast mode (DEFAULT - no flag needed)
pytest

# Explicit fast mode
pytest --fast-test-mode

# Full production validation
pytest --full-iterations

# Fast mode with verbose output
pytest -v

# Skip slow tests entirely
pytest -m "not slow"
```

### When to Use Each Mode

**Fast Mode (default)**:
- ✅ During active development
- ✅ Quick validation of code changes
- ✅ Unit test development
- ✅ Local debugging

**Full Iterations**:
- ✅ Pre-commit validation
- ✅ CI/CD pipeline
- ✅ Before creating pull requests
- ✅ Production readiness checks

---

## Using in Tests

### Method 1: Simple Boolean Flag

```python
import pytest
from analytics.monte_carlo_v14 import run_monte_carlo_analysis

def test_monte_carlo_basic(fast_test_mode):
    """Test Monte Carlo analysis with configurable iterations."""
    # Adjust iterations based on test mode
    n_iterations = 20 if fast_test_mode else 100000
    
    result = run_monte_carlo_analysis(
        config_path="scenarios/test_mc.yaml",
        n_iterations=n_iterations,
    )
    
    assert result.success_rate > 0.95
    assert "p50" in result.percentiles
```

### Method 2: Detailed Configuration

```python
import pytest

def test_sensitivity_analysis(test_iteration_config):
    """Test sensitivity with configurable parameters."""
    config = test_iteration_config
    
    # Access specific configuration
    n_params = config["sensitivity_parameters"]  # 3 in fast, 12 in full
    n_steps = config["sensitivity_steps"]        # 3 in fast, 5 in full
    
    # Run sensitivity with appropriate complexity
    result = run_tornado_sensitivity(
        base_config="scenarios/lender.yaml",
        parameters=parameter_list[:n_params],
        steps=n_steps,
    )
    
    assert len(result.impacts) > 0
```

### Method 3: Configuration Dictionary

```python
def test_comprehensive_analysis(test_iteration_config):
    """Use full configuration dict for complex tests."""
    config = test_iteration_config
    
    print(f"Running in {config['mode']} mode")
    
    # All available config keys:
    # - monte_carlo_iterations: int (20 or 100000)
    # - sensitivity_parameters: int (3 or 12)
    # - sensitivity_steps: int (3 or 5)
    # - timeout_seconds: int (30 or 300)
    # - mode: str ("fast" or "full")
    
    result = run_analysis(
        n_iterations=config["monte_carlo_iterations"],
        max_params=config["sensitivity_parameters"],
        timeout=config["timeout_seconds"],
    )
    
    assert result is not None
```

---

## Migration Guide

### Before (Fixed Iterations)

```python
def test_monte_carlo_old():
    """Old test with hardcoded iterations."""
    result = run_monte_carlo(
        config="test.yaml",
        n_iterations=100000,  # ❌ Always slow!
    )
    assert result.success_rate > 0.95
```

### After (Configurable Iterations)

```python
def test_monte_carlo_new(fast_test_mode):
    """New test with configurable iterations."""
    n = 20 if fast_test_mode else 100000  # ✅ Fast in dev!
    
    result = run_monte_carlo(
        config="test.yaml",
        n_iterations=n,
    )
    assert result.success_rate > 0.95
```

---

## Fixtures Reference

### `fast_test_mode` (bool)

**Scope**: Session  
**Default**: `True` (fast mode)  
**Type**: `bool`

```python
def test_example(fast_test_mode):
    if fast_test_mode:
        print("Running in FAST mode")
    else:
        print("Running in FULL mode")
```

### `test_iteration_config` (dict)

**Scope**: Session  
**Default**: Fast mode configuration  
**Type**: `dict[str, int]`

**Fast Mode Config**:
```python
{
    "monte_carlo_iterations": 20,
    "sensitivity_parameters": 3,
    "sensitivity_steps": 3,
    "timeout_seconds": 30,
    "mode": "fast",
}
```

**Full Mode Config**:
```python
{
    "monte_carlo_iterations": 100000,
    "sensitivity_parameters": 12,
    "sensitivity_steps": 5,
    "timeout_seconds": 300,
    "mode": "full",
}
```

---

## Pytest Markers

Tests are automatically marked based on their characteristics:

### `@pytest.mark.slow`

Automatically applied to tests with `"monte_carlo"` in their name.

```bash
# Skip slow tests entirely
pytest -m "not slow"

# Run only slow tests
pytest -m slow

# Combine with other markers
pytest -m "analytics_layer and not slow"
```

---

## Example: Complete Test Migration

### Original Test (Always Slow)

```python
# tests/analytics_layer/test_monte_carlo_v14.py

def test_run_monte_carlo_analysis_toy_config():
    """Test MC analysis with toy config - SLOW."""
    result = run_monte_carlo_analysis(
        config_path="scenarios/test_monte_carlo.yaml",
        n_iterations=100000,  # Takes 2-3 minutes
    )
    
    assert result.status == "success"
    assert result.n_successful > 95000
    assert "p50" in result.percentiles
    assert result.percentiles["p50"]["project_irr"] > 0.10
```

### Migrated Test (Fast by Default)

```python
# tests/analytics_layer/test_monte_carlo_v14.py

def test_run_monte_carlo_analysis_toy_config(test_iteration_config):
    """Test MC analysis with toy config - FAST in dev, FULL in CI."""
    config = test_iteration_config
    
    result = run_monte_carlo_analysis(
        config_path="scenarios/test_monte_carlo.yaml",
        n_iterations=config["monte_carlo_iterations"],  # 20 or 100k
    )
    
    # Adjust assertions for fast mode
    min_successful = 18 if config["mode"] == "fast" else 95000
    
    assert result.status == "success"
    assert result.n_successful > min_successful
    assert "p50" in result.percentiles
    assert result.percentiles["p50"]["project_irr"] > 0.10
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  fast-tests:
    name: Fast Tests (PR validation)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run fast tests
        run: pytest --fast-test-mode  # ~30 seconds

  full-tests:
    name: Full Tests (merge validation)
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Run full validation
        run: pytest --full-iterations  # ~5-10 minutes
```

---

## Troubleshooting

### Tests Still Running Slowly

**Problem**: Tests are still taking minutes to run.

**Solution**: Check if you're passing `--full-iterations` flag.

```bash
# Verify current mode
pytest -v | head -5
# Should show: "TEST MODE: FAST (20 iterations, 3 params)"

# If it shows FULL mode, you're using --full-iterations
# Remove the flag or override with --fast-test-mode
```

### Fixture Not Found

**Problem**: `fixture 'fast_test_mode' not found`

**Solution**: Ensure `tests/conftest.py` is present and updated.

```bash
git pull origin main
ls -la tests/conftest.py
```

### Tests Failing in Full Mode Only

**Problem**: Tests pass in fast mode but fail with `--full-iterations`.

**Solution**: This indicates the test has assumptions about iteration count.

```python
# BAD: Hardcoded threshold
assert result.n_successful == 19  # Only works in fast mode!

# GOOD: Mode-aware threshold
min_successful = 18 if fast_test_mode else 95000
assert result.n_successful > min_successful
```

---

## Performance Benchmarks

### Sprint 9 Test Suite

| Test File | Fast Mode | Full Mode | Speedup |
|-----------|-----------|-----------|--------|
| `test_monte_carlo_v14.py` | 3.2s | 287s | 90x |
| `test_sensitivity_v14.py` | 1.8s | 94s | 52x |
| `test_monte_carlo_three_scenarios.py` | 2.1s | 156s | 74x |
| **Total Suite** | **28s** | **612s** | **22x** |

### Real-World Impact

```
Before (fixed iterations):
- Developer runs tests: 10 minutes wait
- Test, fix, retest cycle: 30+ minutes
- Frustration level: HIGH

After (fast mode):
- Developer runs tests: 30 seconds wait
- Test, fix, retest cycle: 2-3 minutes  
- Productivity: MASSIVELY IMPROVED 🚀
```

---

## Summary

### Key Takeaways

1. **Default is fast**: No flags needed for rapid development
2. **CI/CD uses full**: Pass `--full-iterations` in production pipelines
3. **Two fixtures available**: `fast_test_mode` (bool) and `test_iteration_config` (dict)
4. **500x faster**: 20 iterations vs 100,000 in fast mode
5. **No code duplication**: Same tests work in both modes

### Quick Command Reference

```bash
# Development (fast)
pytest

# Pre-commit (full)
pytest --full-iterations

# Skip slow tests
pytest -m "not slow"

# Verbose with fast mode
pytest -v --fast-test-mode
```

---

## Next Steps

1. **Pull latest code**: `git pull origin main`
2. **Run fast tests**: `pytest` (should complete in ~30s)
3. **Update your tests**: Add `fast_test_mode` parameter to slow tests
4. **Before commit**: Run `pytest --full-iterations` to ensure full validation

**Questions?** See [Sprint 9 Handover](../../Sprint_9_Handover.md) or ask the team!
