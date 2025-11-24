# 🚀 Thread Migration Quick Start

**For immediate AI thread context restoration, use this minimal paste:**

```
Resume DutchBay EPC Model with "Go with the Flow" standards:
- YAML/config-driven, validated before execution
- Batch/CLI friendly (no hardcoded paths)
- Stateless APIs, test-first design
- Full mypy/flake8/black compliance

Full context: docs/THREAD_MIGRATION_PACKAGE.md in arunakulat/dutchbay-epc-model
```

---

## Full Documentation

For comprehensive project context, patterns, and standards:

**➡️ [Complete Thread Migration Package](docs/THREAD_MIGRATION_PACKAGE.md)**

---

## Core Principles

### "Go With The Flow" Rules
1. **Config-driven**: All parameters in YAML with validation
2. **No hardcoding**: Paths/state via arguments or env vars
3. **Reproducible**: Same inputs → same outputs
4. **Tested**: Contract tests for all analytics
5. **Type-safe**: Full mypy compliance

### Anti-Patterns to Avoid
- ❌ Hardcoded file paths
- ❌ Unvalidated configs
- ❌ Mutable global state
- ❌ Overwriting exports
- ❌ `Any` types without justification

---

## Quick Commands

```bash
# Run scenario
python analytics/run_full_pipeline.py --config scenarios/base.yaml

# Run tests
pytest tests/

# Type check
mypy analytics/ finance/

# Launch dashboard
streamlit run dashboard/streamlit_app.py
```

---

## Project Structure

```
analytics/              # Analytics modules
  foundation.py         # Base (DO NOT RENAME)
  sensitivity/
  monte_carlo/
finance/                # Financial calculations
  debt_v14.py
  equity_v14.py
  cashflow_v14.py
scenarios/              # YAML configs
exports/                # Output directory
tests/                  # Test suite
docs/                   # Documentation
```

---

## Success Checklist

- ✅ All tests pass
- ✅ Type checking clean (mypy)
- ✅ Linting clean (flake8, black)
- ✅ Results reproducible
- ✅ Outputs to exports/ with unique names
- ✅ Functions have docstrings + type hints

---

**Last Updated:** November 24, 2025  
**Version:** 1.0
