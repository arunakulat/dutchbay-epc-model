# Integration Test Suite - DutchBay EPC Model v14

## Overview

Comprehensive integration tests validating cross-module interactions and end-to-end pipeline flows for the DutchBay 150MW wind farm financial model.

**Purpose**: Verify that all modules integrate correctly with NO REGRESSIONS and meet production performance benchmarks.

---

## Test Structure

### 📦 Test Modules (6 dolphins)

1. **`test_degradation_flow.py`** - Degradation integration
   - Configuration → Cashflow → Monte Carlo → Sensitivity
   - Year-over-year degradation calculations
   - 26 tests, ~5 seconds

2. **`test_dual_dscr_integration.py`** - Dual DSCR debt sizing
   - CFADS P50/P99 construction with degradation
   - Conservative sizing logic
   - Binding constraint detection
   - 18 tests, ~3 seconds

3. **`test_monte_carlo_integration.py`** - Monte Carlo with performance
   - 4-variable stochastic model (revenue, cost, FX, degradation)
   - Correlation structure validation
   - NPV/IRR distribution outputs
   - Performance benchmarks
   - 24 tests, ~20 seconds (with slow tests)

4. **`test_pipeline_end_to_end.py`** - Complete pipeline
   - Wind → Cashflow → Debt → MC → Sensitivity
   - Data flow validation
   - Output completeness
   - Regression pins
   - 20 tests, ~30 seconds (with slow tests)

5. **`conftest.py`** - Shared fixtures
   - DutchBay 150MW realistic configuration
   - Wind assessment mock data
   - Performance benchmarks

6. **`__init__.py`** - Package initialization

**Total**: ~88 integration tests

---

## Running Tests

### Quick Run (Fast Tests Only)
```bash
# Run all fast integration tests (< 10s)
pytest tests/integration/ -v

# Run specific test module
pytest tests/integration/test_degradation_flow.py -v
```

### Full Run (Including Slow Tests)
```bash
# Run all integration tests including performance benchmarks
pytest tests/integration/ -v -m "slow or not slow"

# Run only slow tests
pytest tests/integration/ -v -m "slow"
```

### Performance Tests Only
```bash
# Run only performance benchmarks
pytest tests/integration/ -v -m "performance"
```

### With Coverage
```bash
# Generate coverage report
pytest tests/integration/ --cov=analytics --cov=finance --cov-report=html
```

---

## Performance Benchmarks

### Target Performance (from `conftest.py`)

| Component | Target Time | Status |
|-----------|-------------|--------|
| Wind Assessment | < 5s | ✅ Mock |
| Cashflow Model | < 2s | ✅ |
| Monte Carlo 1K | < 10s | ✅ |
| Monte Carlo 10K | < 60s | ✅ |
| Sensitivity Analysis | < 30s | ✅ |
| **Full Pipeline** | **< 60s** | **✅** |

### Performance Monitoring

```bash
# Run with timing
pytest tests/integration/test_monte_carlo_integration.py -v --durations=10

# Profile specific test
pytest tests/integration/test_pipeline_end_to_end.py::TestPipelinePerformance -v --profile
```

---

## Framework Compliance

### TEST-01: Regression Pins
All integration tests include regression pins for:
- Degradation impact magnitude (10-12% over 20 years)
- DSCR reduction when P99 binds (5-15%)
- NPV/IRR distribution ranges
- Debt sizing capacity (50-75% of CAPEX)

### CASPER: Tail-Risk Validation
- P99 DSCR constraint binding conditions
- Degradation P90/P99 scenarios
- Monte Carlo percentile distributions
- Stress case validation

### NO REGRESSION Rule
- All tests verify existing behavior unchanged
- New functionality tested additively
- No modifications to production code during testing

### Performance: Production Targets
- Full pipeline < 60 seconds
- Monte Carlo 10K < 60 seconds
- Enables real-time lender presentations

---

## Test Fixtures

### `dutchbay_base_config`
Realistic DutchBay 150MW configuration:
- 50 x Vestas V150-3.0MW turbines
- Mannar region, Sri Lanka
- $200M CAPEX
- 0.6%/year degradation
- 20-year PPA at $50/MWh

### `wind_assessment_mock_results`
Mock wind assessment outputs:
- P50 AEP: 400 GWh/year
- P75 AEP: 380 GWh/year
- P90 AEP: 360 GWh/year
- P99 AEP: 340 GWh/year

### `performance_benchmarks`
Time limits for each pipeline component.

---

## CI/CD Integration

### GitHub Actions
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/integration/ -v --junitxml=integration-results.xml
      - uses: actions/upload-artifact@v3
        with:
          name: integration-results
          path: integration-results.xml
```

### Pre-Commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/integration/ -v -m "not slow"
if [ $? -ne 0 ]; then
    echo "Integration tests failed. Commit aborted."
    exit 1
fi
```

---

## Troubleshooting

### Import Errors
```
ImportError: cannot import name 'MonteCarloEngine'
```
**Solution**: Ensure you're running from repository root:
```bash
cd /path/to/dutchbay-epc-model
pytest tests/integration/ -v
```

### Slow Test Performance
```
test_10k_iterations_performance took 75s (target: 60s)
```
**Solution**: 
- Check system load
- Run with `--tb=short` for faster feedback
- Consider Numba JIT optimization (future enhancement)

### Fixture Not Found
```
fixture 'dutchbay_base_config' not found
```
**Solution**: Ensure `conftest.py` is in `tests/integration/` directory.

### Pytest Not Finding Tests
```bash
# Verify test discovery
pytest --collect-only tests/integration/

# Should show ~88 tests collected
```

---

## Test Development Guidelines

### Adding New Integration Tests

1. **Create focused test module** (dolphin-sized)
   - Single integration concern
   - Clear test class structure
   - Docstrings for every test

2. **Use existing fixtures**
   - `dutchbay_base_config` for realistic parameters
   - `performance_benchmarks` for time limits
   - Add new fixtures to `conftest.py` if needed

3. **Follow naming convention**
   - `test_<module>_integration.py` for module tests
   - `test_<feature>_flow.py` for data flow tests
   - `TestClassName` for test classes
   - `test_descriptive_name` for test methods

4. **Mark slow tests**
   ```python
   @pytest.mark.slow
   def test_10k_iterations(self):
       # Long-running test
       pass
   ```

5. **Include regression pins**
   ```python
   def test_expected_output_range(self):
       result = function_under_test()
       assert 20.0 < result < 80.0, (
           f"Expected 20-80 range, got {result}"
       )
   ```

6. **Commit incrementally** (small dolphins!)
   - One test module per commit
   - Clear commit messages
   - Build progressively

---

## Test Coverage

### Current Coverage
- Degradation flow: ✅ Complete
- Dual DSCR integration: ✅ Complete
- Monte Carlo: ✅ Complete
- End-to-end pipeline: ✅ Complete

### Future Enhancements
- [ ] Tax optimization integration
- [ ] Refinancing timing integration
- [ ] Stress test scenarios
- [ ] Multi-scenario comparison
- [ ] Parallel execution optimization

---

## Production Readiness Checklist

- [x] All fast tests pass (< 10s)
- [x] All slow tests pass (< 60s total)
- [x] Performance benchmarks met
- [x] NO REGRESSIONS verified
- [x] Regression pins established
- [x] Framework compliance (TEST-01, CASPER)
- [x] CI/CD integration ready
- [x] Documentation complete

**Status**: ✅ **PRODUCTION READY**

---

## Contact

**Questions or Issues?**
- Check test output for specific failures
- Review framework compliance (GWTF, CASPER, CESSPIT)
- Ensure all dependencies installed: `pip install -r requirements.txt`

**Integration Test Suite Version**: 1.0
**Last Updated**: December 21, 2025
**Branch**: `feature/add-finance-contracts-pydantic-v2-20251219`
