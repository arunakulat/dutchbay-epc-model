# Scenario Management Package

**Sprint 16 Reorganization** | **Status:** Phase 1 Complete

## Overview

This package consolidates scenario configuration loading, discovery, and management into a single organized location.

### Rationale for Reorganization

**Before (Fragmented):**
```
analytics/
├── scenario_loader.py          # Production loader (comprehensive)
├── scenarioloader.py           # Legacy loader (backward compat)
├── scenario_manager.py         # Discovery/batch loading
├── scenario_analytics.py       # Analytics utilities
└── evaluate_scenario.py        # Evaluation runner
```

**After (Organized):**
```
analytics/
└── scenarios/                  # 🆕 NEW PACKAGE
    ├── __init__.py             # Public API (re-exports)
    ├── README.md               # This file
    └── (files stay at root for now, backward compat)
```

---

## Public API

### Primary Loader (Production)

```python
from analytics.scenarios import load_scenario_config, ScenarioConfigError

# Load v13/v14 scenario configuration
config = load_scenario_config("scenarios/dutchbay_base.yaml")
```

**Features:**
- Supports YAML and JSON
- v13/v14 compatibility
- Strict FX validation
- Comprehensive error messages
- Meta breadcrumbs for debugging

### Legacy Loader (Backward Compatibility)

```python
from analytics.scenarios import loadscenarioconfig

# Legacy import pattern (still works)
config = loadscenarioconfig("scenarios/dutchbay_base.yaml")
```

**Note:** This is a simple YAML loader kept for backward compatibility. New code should use `load_scenario_config()`.

### Discovery and Batch Loading

```python
from analytics.scenarios import ScenarioManager

# Discover and load scenarios from directory
manager = ScenarioManager("scenarios/")

for name, config in manager.iter_scenarios():
    print(f"Processing {name}...")
    # ... run pipeline
```

**Features:**
- Directory-based discovery
- Pattern filtering
- Automatic file type detection (YAML/JSON)
- Sorted iteration

---

## Backward Compatibility

### All Old Imports Still Work

**Old way (still functional):**
```python
from analytics.scenario_loader import load_scenario_config
from analytics.scenarioloader import loadscenarioconfig
from analytics.scenario_manager import ScenarioManager
```

**New way (recommended):**
```python
from analytics.scenarios import (
    load_scenario_config,
    loadscenarioconfig,
    ScenarioManager,
)
```

Both import patterns work identically. Existing code requires **zero changes**.

---

## File Organization

### Current Structure (Phase 1)

During Phase 1, files remain at `/analytics/` root for maximum backward compatibility:

```
analytics/
├── scenario_loader.py          # ✅ Production loader
├── scenarioloader.py           # ✅ Legacy loader
├── scenario_manager.py         # ✅ Discovery manager
├── scenario_analytics.py       # ✅ Analytics utilities
├── evaluate_scenario.py        # ✅ Evaluation runner
│
└── scenarios/                  # 🆕 NEW PACKAGE (Phase 1)
    ├── __init__.py             # Re-exports for clean API
    └── README.md               # This documentation
```

### Planned Structure (Phase 2 - Future)

```
analytics/
└── scenarios/                  # Consolidated package
    ├── __init__.py             # Public API
    ├── README.md               # Documentation
    ├── loader.py               # From scenario_loader.py
    ├── loader_legacy.py        # From scenarioloader.py
    ├── manager.py              # From scenario_manager.py
    ├── analytics.py            # From scenario_analytics.py
    └── evaluator.py            # From evaluate_scenario.py
```

**Note:** Phase 2 requires careful import updates and testing. Deferred to Sprint 17.

---

## Usage Examples

### Basic Scenario Loading

```python
from analytics.scenarios import load_scenario_config
from analytics.pipeline_v14 import run_v14_pipeline

# Load configuration
config = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")

# Run pipeline
result = run_v14_pipeline(
    config=config,
    validation_mode="strict",
)

print(f"Project IRR: {result['kpis']['project_irr']:.2%}")
```

### Batch Processing Multiple Scenarios

```python
from analytics.scenarios import ScenarioManager
from analytics.pipeline_v14 import run_v14_pipeline
import pandas as pd

manager = ScenarioManager("scenarios/")
results = []

for name, config in manager.iter_scenarios():
    try:
        result = run_v14_pipeline(config=config)
        results.append({
            "scenario": name,
            "project_irr": result["kpis"]["project_irr"],
            "equity_irr": result["kpis"]["equity_irr"],
            "dscr_min": result["kpis"]["dscr_min"],
        })
    except Exception as e:
        print(f"Failed: {name} - {e}")

df = pd.DataFrame(results)
print(df)
```

### FX Configuration Validation

```python
from analytics.scenarios import load_scenario_config
from analytics.scenario_loader import _resolve_fx

# Load config
config = load_scenario_config("scenarios/dutchbay_base.yaml")

# Validate and extract FX parameters
try:
    fx_params = _resolve_fx(config)
    print(f"Start rate: {fx_params['start_lkr_per_usd']}")
    print(f"Annual depr: {fx_params['annual_depr']}")
except ValueError as e:
    print(f"FX config error: {e}")
```

---

## Migration Guide

### For Existing Code

**No changes required.** All existing imports continue to work:

```python
# These still work (old imports)
from analytics.scenario_loader import load_scenario_config
from analytics.scenarioloader import loadscenarioconfig
from analytics.scenario_manager import ScenarioManager
```

### For New Code

**Recommended:** Use the new consolidated package:

```python
# New imports (cleaner)
from analytics.scenarios import (
    load_scenario_config,
    ScenarioManager,
    ScenarioConfigError,
)
```

**Benefits:**
- Cleaner imports
- Obvious organization
- Forward-compatible with Phase 2
- Same functionality

---

## Architecture Principles

### GWTF (Go-With-The-Flow)

- **Single entry point:** `load_scenario_config()` is the canonical loader
- **Clear delegation:** Legacy loader delegates to production loader internally
- **Predictable behavior:** Same input always produces same output

### CESSPIT (Comprehensive Error Handling)

- **Fail-fast validation:** FX configs validated at load time
- **Clear error messages:** Specific guidance on what's wrong
- **Type safety:** All functions fully type-annotated

### CASPER (Contract-First)

- **Pydantic V2 ready:** Config schemas ready for future Pydantic validation
- **Frozen contracts:** Scenario configs are immutable mappings
- **Explicit APIs:** No hidden behavior or magic

### CCCDIR (Clear, Complete, Consistent Documentation)

- **Package-level docs:** This README
- **Module-level docs:** Docstrings in each file
- **Function-level docs:** Google-style docstrings throughout
- **Usage examples:** Practical code samples

---

## Testing

### Backward Compatibility Tests

```python
import pytest

def test_old_imports_still_work():
    """Verify all old import patterns continue to function."""
    # Old imports
    from analytics.scenario_loader import load_scenario_config as old_load
    from analytics.scenarioloader import loadscenarioconfig as old_legacy
    from analytics.scenario_manager import ScenarioManager as OldManager
    
    # New imports
    from analytics.scenarios import (
        load_scenario_config as new_load,
        loadscenarioconfig as new_legacy,
        ScenarioManager as NewManager,
    )
    
    # Should be same functions
    assert old_load is new_load
    assert old_legacy is new_legacy
    assert OldManager is NewManager

def test_scenario_loading():
    """Test basic scenario loading functionality."""
    from analytics.scenarios import load_scenario_config
    
    config = load_scenario_config("scenarios/test_scenario.yaml")
    
    assert isinstance(config, dict)
    assert "project" in config
    assert "finance" in config
```

### Run Tests

```bash
# From repository root
pytest tests/test_scenarios.py -v
```

---

## Related Documentation

- [Sprint 16 Completion Report](../../docs/sprint_16_completion.md)
- [Sensitivity Reorganization](../sensitivity/REORGANIZATION.md)
- [GWTF Framework](../../docs/gwtf_framework.md)
- [Pipeline Documentation](../../docs/pipeline_v14.md)

---

## Changelog

### Sprint 16 (December 21, 2025)

**Phase 1: Package Creation**
- ✅ Created `/analytics/scenarios/` package
- ✅ Added `__init__.py` with re-exports
- ✅ Documented backward compatibility
- ✅ Zero breaking changes

**Deferred to Sprint 17:**
- ⏸️ Move files into `/scenarios/` subfolder
- ⏸️ Create comprehensive test suite
- ⏸️ Add scenario validation utilities
- ⏸️ Implement scenario comparison tools

---

## Contributing

### Adding New Scenario Features

1. **Add to appropriate file** at root (for now)
2. **Re-export from** `scenarios/__init__.py`
3. **Update** this README
4. **Add tests** in `tests/test_scenarios.py`
5. **Maintain** backward compatibility

### Phase 2 Migration (Future)

When moving to Phase 2:

1. Create new files in `/scenarios/` folder
2. Update imports in `__init__.py`
3. Keep old files as deprecated stubs
4. Add deprecation warnings
5. Update all documentation
6. Run full test suite
7. Update CI/CD pipelines

---

**Document Status:** ✅ Complete  
**Last Updated:** December 21, 2025  
**Maintained By:** Sprint 16 Engineering Team
