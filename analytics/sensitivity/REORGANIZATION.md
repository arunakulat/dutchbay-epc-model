# Sensitivity Module Reorganization

**Date:** December 21, 2025  
**Sprint:** 16  
**Framework:** CCCDIR + GWTF + CESSPIT

## Overview

This document describes the reorganization of sensitivity analysis modules following CCCDIR principles (Clear, Complete, Consistent Documentation & Intelligent Reasoning) and GWTF (Go-With-The-Flow) architecture patterns.

## Rationale

### Before: Fragmented Structure

**Problems:**
- 11 sensitivity files scattered at `/analytics/` root level
- Difficult to find specific functionality (plotting? export? batch?)
- Unclear distinction between public API and internal utilities
- Duplicate files (sensitivity_tail_risk.py with/without trailing space)
- Legacy stubs (fx_sensitivity.py, sensitivity_v15.incorrectpy)

### After: Organized Structure

**Benefits:**
- ✅ Clear public API at root (sensitivity_v14.py, fx_sensitivity_real.py)
- ✅ Organized internals by purpose (visualization/, io/, analysis/, etc.)
- ✅ Easier navigation and discovery
- ✅ Better maintainability and scalability
- ✅ Framework compliant (GWTF, CCCDIR, CESSPIT)

---

## Migration Map

### Phase 1: Cleanup (COMPLETED)

| File | Action | Reason | Commit |
|------|--------|--------|--------|
| `sensitivity_tail_risk.py ` | ❌ DELETE | Duplicate with trailing space | `3dcc21a7` |
| `sensitivity/sensitivity_v15.incorrectpy` | ❌ DELETE | Incorrect version | `11c94e4c` |
| `fx_sensitivity.py` | ❌ DELETE | Legacy stub (replaced by fx_sensitivity_real.py) | `b39487b3` |

### Phase 2: Preserve Public API (NO CHANGES)

| File | Action | Reason |
|------|--------|--------|
| `sensitivity_v14.py` | ✅ KEEP AT ROOT | **Core public API** for tornado/breakeven analysis |
| `fx_sensitivity_real.py` | ✅ KEEP AT ROOT | **Core public API** for FX sensitivity analysis |
| `cli_sensitivity.py` | ✅ KEEP AT ROOT | **CLI entry point** |

### Phase 3: Organize Subfolder Structure (PENDING)

#### Current Flat Structure → New Organized Structure

```
analytics/
├── sensitivity_v14.py                 [KEEP - Core API]
├── fx_sensitivity_real.py             [KEEP - FX API]
├── cli_sensitivity.py                 [KEEP - CLI]
│
├── sensitivity_export.py              → sensitivity/io/export.py
├── sensitivity_heatmap.py             → sensitivity/visualization/heatmap.py
├── sensitivity_pareto.py              → sensitivity/analysis/pareto.py
├── sensitivity_runner.py              → sensitivity/runners/runner.py
├── sensitivity_tail_risk.py           → sensitivity/analysis/tail_risk.py
├── sensitivity_visualization.py       → sensitivity/visualization/plots.py
│
└── sensitivity/
    ├── __init__.py                    [UPDATE - expose migrated functions]
    ├── batch.py                       → runners/batch.py
    ├── config_lookup.py               → core/config_lookup.py
    ├── dashboard_demo.py              → visualization/dashboard_demo.py
    ├── docstrings.py                  → docs/docstrings.py
    ├── report.py                      → io/report.py
    ├── sensitivity_usage_readme.md    → docs/usage_readme.md
    ├── stochastic.py                  → analysis/stochastic.py
    ├── tools.py                       → core/tools.py
    └── validation.py                  → core/validation.py
```

---

## New Folder Structure

```
analytics/sensitivity/
├── __init__.py                        # Package init - re-exports for backward compat
│
├── core/                              # Core utilities
│   ├── __init__.py
│   ├── config_lookup.py              # Config parameter lookup
│   ├── tools.py                      # Utility functions
│   └── validation.py                 # Input validation
│
├── analysis/                          # Analysis modules
│   ├── __init__.py
│   ├── tail_risk.py                  # Tail risk enrichment (from root)
│   ├── pareto.py                     # Pareto analysis (from root)
│   └── stochastic.py                 # Stochastic analysis (existing)
│
├── visualization/                     # Plotting & visualization
│   ├── __init__.py
│   ├── heatmap.py                    # Heatmap plots (from root)
│   ├── plots.py                      # Tornado/spider plots (from root)
│   └── dashboard_demo.py             # Dashboard stub (existing)
│
├── io/                                # Import/export
│   ├── __init__.py
│   ├── export.py                     # Export utilities (from root)
│   └── report.py                     # Report generation (existing)
│
├── runners/                           # Batch execution
│   ├── __init__.py
│   ├── batch.py                      # Batch processing (existing)
│   └── runner.py                     # CLI runner (from root)
│
└── docs/                              # Documentation
    ├── usage_readme.md               # Usage guide (existing)
    └── docstrings.py                 # Documentation helpers (existing)
```

---

## Backward Compatibility

### Import Redirection via `__init__.py`

All existing imports will continue to work through re-exports:

```python
# analytics/sensitivity/__init__.py

# Core utilities
from analytics.sensitivity.core.config_lookup import *
from analytics.sensitivity.core.tools import *
from analytics.sensitivity.core.validation import *

# Analysis modules  
from analytics.sensitivity.analysis.tail_risk import *
from analytics.sensitivity.analysis.pareto import *
from analytics.sensitivity.analysis.stochastic import *

# Visualization
from analytics.sensitivity.visualization.heatmap import *
from analytics.sensitivity.visualization.plots import *

# IO
from analytics.sensitivity.io.export import *
from analytics.sensitivity.io.report import *

# Runners
from analytics.sensitivity.runners.batch import *
from analytics.sensitivity.runners.runner import *
```

### Migration Examples

**Old imports (still work):**
```python
from analytics.sensitivity.batch import run_batch_sensitivity
from analytics.sensitivity.report import generate_sensitivity_report
```

**New recommended imports:**
```python
from analytics.sensitivity.runners.batch import run_batch_sensitivity
from analytics.sensitivity.io.report import generate_sensitivity_report
```

---

## Benefits

### 1. Clear API Surface
- **Root level** = Public APIs used by pipeline/CASPER
- **Subfolder** = Internal utilities and specialized tools

### 2. Organized by Purpose
- Need plotting? → `sensitivity/visualization/`
- Need export? → `sensitivity/io/`  
- Need batch processing? → `sensitivity/runners/`
- Need analysis extensions? → `sensitivity/analysis/`

### 3. Scalability
- New visualization? Add to `visualization/`
- New analysis type? Add to `analysis/`
- Core API (`sensitivity_v14.py`) remains stable

### 4. Framework Compliance

| Framework | How Reorganization Helps |
|-----------|-------------------------|
| **GWTF** | Clear single entry point at root (`sensitivity_v14.py`) |
| **CESSPIT** | Single source of truth preserved, cleaner import paths |
| **CASPER** | Contract-first design unaffected, easier to find contracts |
| **CCCDIR** | Clear organization by purpose, complete documentation |

---

## Implementation Status

### Phase 1: Cleanup ✅ COMPLETE

- ✅ Removed `sensitivity_tail_risk.py ` (duplicate)
- ✅ Removed `sensitivity_v15.incorrectpy` (incorrect version)
- ✅ Removed `fx_sensitivity.py` (legacy stub)

### Phase 2: Public API Preservation ✅ COMPLETE

- ✅ `sensitivity_v14.py` remains at root
- ✅ `fx_sensitivity_real.py` remains at root
- ✅ `cli_sensitivity.py` remains at root

### Phase 3: Subfolder Reorganization 🟡 PENDING

**Status:** Documented, ready to implement

**Reason for pending:** Requires careful testing to ensure no import breakage. Recommend implementing in separate PR after Sprint 16 completion to avoid scope creep.

**Risk Level:** Low (backward compatibility maintained via `__init__.py`)

**Estimated Time:** 30-45 minutes

---

## Testing Checklist

Before declaring reorganization complete:

- [ ] All existing imports still work (via `__init__.py` re-exports)
- [ ] `sensitivity_v14.py` functions as expected
- [ ] `fx_sensitivity_real.py` functions as expected  
- [ ] CLI (`cli_sensitivity.py`) works without modification
- [ ] Test suite passes (`scripts/sprint_16_test_suite.sh`)
- [ ] Documentation updated (this file)
- [ ] No broken imports in downstream modules

---

## Rollback Plan

If issues arise:

1. **Revert cleanup commits:**
   ```bash
   git revert b39487b3  # fx_sensitivity.py deletion
   git revert 11c94e4c  # sensitivity_v15 deletion
   git revert 3dcc21a7  # duplicate tail_risk deletion
   ```

2. **Restore from backup:**
   All deleted files are preserved in git history.

3. **Minimum viable state:**
   Even with Phase 3 incomplete, the codebase is fully functional with Phase 1+2 complete.

---

## Related Documentation

- [Sprint 16 Completion Report](../../docs/sprint_16_completion.md)
- [Sensitivity Usage Guide](docs/usage_readme.md)
- [GWTF Framework Spec](../../docs/gwtf_framework.md)
- [CCCDIR Principles](../../docs/cccdir_principles.md)

---

## Conclusion

**Phase 1-2 COMPLETE**: Cleanup and public API preservation done.

**Phase 3 READY**: Subfolder reorganization documented and ready to implement in follow-up PR.

**Impact**: Zero breaking changes. Improved maintainability and clarity.

**Next Steps**: Proceed with Sprint 16 completion, implement Phase 3 in Sprint 17.

---

**Document Status:** ✅ Complete  
**Last Updated:** December 21, 2025  
**Maintained By:** Sprint 16 Engineering Team
