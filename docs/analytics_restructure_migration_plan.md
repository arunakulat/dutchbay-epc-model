# Analytics Package Restructuring - Migration Plan

**Status**: Phase 0 Complete ✅ | Phases 1-3 Pending ⏳  
**Date**: December 23, 2025  
**Sprint**: 9 of Dutchbay  
**GWTF Compliance**: R25 (Feature branch only, no main commits)

---

## Executive Summary

The `analytics/` package currently contains 60+ modules in a flat structure, leading to:
- Import hell (circular dependencies, unclear boundaries)
- Duplication (3-4 Monte Carlo engines, 2 correlation modules)
- Production/research code mixing
- Unclear ownership

**Goal**: Restructure into clean subpackages while maintaining 100% backward compatibility.

---

## Current State

```
analytics/
├── casper_v14.py
├── casper_payload.py
├── kpi_normalizer.py
├── fx_integration.py
├── wind_integration.py
├── cli_monte_carlo_hydra.py
├── cli_sensitivity_hydra.py
├── monte_carlo_v14.py (SHIM → mc/engine.py)
├── monte_carlo_correlation.py (SHIM → mc/correlation.py)
├── correlation_engine.py (SHIM → mc/correlation.py)
├── [50+ other modules]
└── mc/
    ├── engine.py ✅
    ├── correlation.py ✅
    ├── samplers.py ✅
    ├── degradation.py ✅
    ├── aggregate.py ✅
    └── exports.py ✅
```

---

## Target State

```
analytics/
├── core/                  # Core metrics & calculations
│   ├── __init__.py ✅
│   ├── returns.py
│   ├── risk_metrics.py
│   ├── parameter_solvers.py
│   └── config_schema.py
│
├── casper/                # CASPER payload generation
│   ├── __init__.py ✅
│   ├── casper_v14.py
│   ├── casper_payload.py
│   └── kpi_normalizer.py
│
├── fx/                    # FX integration
│   ├── __init__.py ✅
│   └── fx_integration.py
│
├── wind/                  # Wind analytics
│   ├── __init__.py ✅
│   ├── wind_integration.py
│   └── pipeline_aep_v14.py
│
├── mc/                    # Monte Carlo (COMPLETE ✅)
│   ├── __init__.py ✅
│   ├── engine.py ✅
│   ├── correlation.py ✅
│   ├── samplers.py ✅
│   ├── degradation.py ✅
│   ├── aggregate.py ✅
│   └── exports.py ✅
│
├── cli/                   # CLI entrypoints
│   ├── __init__.py ✅
│   ├── cli_monte_carlo_hydra.py
│   └── cli_sensitivity_hydra.py
│
└── [legacy shims for backward compatibility]
    ├── casper_v14.py → casper/casper_v14.py
    ├── fx_integration.py → fx/fx_integration.py
    └── ...

analysis_tools/            # Research helpers (outside production)
├── __init__.py ✅
└── fx_correlation_analyzer.py
```

---

## Phase 0: Package Structure ✅ COMPLETE

**Status**: ✅ Complete  
**Commit**: `7047d00` - "feat: Phase 0 - Create package structure safety rails"

### Created Directories

```python
analytics/core/__init__.py      ✅
analytics/casper/__init__.py    ✅
analytics/fx/__init__.py        ✅
analytics/wind/__init__.py      ✅
analytics/cli/__init__.py       ✅
analysis_tools/__init__.py      ✅
```

### Benefits
- Safety rails prevent import errors during migration
- Clear module boundaries established
- Production vs. research separation defined

---

## Phase 1: File Moves ⏳ PENDING

**Status**: ⏳ Planning  
**Strategy**: Gradual, priority-based migration

### Priority 1: CASPER Modules (High Impact)

**Move**:
```bash
# Git operations (to preserve history)
git mv analytics/casper_v14.py analytics/casper/casper_v14.py
git mv analytics/casper_payload.py analytics/casper/casper_payload.py
git mv analytics/kpi_normalizer.py analytics/casper/kpi_normalizer.py
```

**Rationale**:
- CASPER is a well-defined subsystem
- Clear API boundary (casper_v14.evaluate_with_casper_tail_risk_and_payload)
- Limited internal dependencies

**Impact**:
- 3 files moved
- ~15KB code organized
- Clear ownership established

---

### Priority 2: CLI Modules (Medium Impact)

**Move**:
```bash
git mv analytics/cli_monte_carlo_hydra.py analytics/cli/cli_monte_carlo_hydra.py
git mv analytics/cli_sensitivity_hydra.py analytics/cli/cli_sensitivity_hydra.py
git mv analytics/cli_sensitivity.py analytics/cli/cli_sensitivity.py
```

**Rationale**:
- User-facing entrypoints
- Should be isolated from core analytics
- Clean separation of concerns

**Impact**:
- 3 files moved
- ~14KB code organized

---

### Priority 3: FX Module (Low Impact)

**Move**:
```bash
git mv analytics/fx_integration.py analytics/fx/fx_integration.py
```

**Rationale**:
- Single-file module
- Clean FX subsystem
- Minimal dependencies

**Impact**:
- 1 file moved
- ~4KB code organized

---

### Priority 4: Wind Modules (Medium Impact)

**Move**:
```bash
git mv analytics/wind_integration.py analytics/wind/wind_integration.py
git mv analytics/pipeline_aep_v14.py analytics/wind/pipeline_aep_v14.py
```

**Rationale**:
- Wind-specific analytics
- AEP loading utilities
- NetCDF handling

**Impact**:
- 2 files moved
- ~24KB code organized

---

### Priority 5: Core Metrics (Lower Priority)

**Move**:
```bash
git mv analytics/returns.py analytics/core/returns.py
git mv analytics/risk_metrics.py analytics/core/risk_metrics.py
git mv analytics/parameter_solvers.py analytics/core/parameter_solvers.py
git mv analytics/config_schema.py analytics/core/config_schema.py
```

**Rationale**:
- Foundation metrics
- Widely imported (higher risk)
- Move after higher-priority modules stabilize

**Impact**:
- 4 files moved
- ~67KB code organized

---

## Phase 2: Compatibility Shims ⏳ PENDING

**Status**: ⏳ Planning  
**Strategy**: Create shims for ALL moved files

### Shim Pattern

For each moved file, create a shim in the original location:

```python
# analytics/casper_v14.py (SHIM)

"""
BACKWARD COMPATIBILITY SHIM

This module has moved to analytics.casper.casper_v14.
This shim will be removed in v15.

Migration:
  OLD: from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
  NEW: from analytics.casper.casper_v14 import evaluate_with_casper_tail_risk_and_payload
  OR:  from analytics.casper import evaluate_with_casper_tail_risk_and_payload
"""

from analytics.casper.casper_v14 import *  # noqa

__all__ = [
    "evaluate_with_casper_tail_risk_and_payload",
]
```

### Shims Required

| Original Path | New Path | Shim Status |
|--------------|----------|-------------|
| `analytics/casper_v14.py` | `analytics/casper/casper_v14.py` | ⏳ Pending |
| `analytics/casper_payload.py` | `analytics/casper/casper_payload.py` | ⏳ Pending |
| `analytics/kpi_normalizer.py` | `analytics/casper/kpi_normalizer.py` | ⏳ Pending |
| `analytics/fx_integration.py` | `analytics/fx/fx_integration.py` | ⏳ Pending |
| `analytics/wind_integration.py` | `analytics/wind/wind_integration.py` | ⏳ Pending |
| `analytics/cli_monte_carlo_hydra.py` | `analytics/cli/cli_monte_carlo_hydra.py` | ⏳ Pending |
| `analytics/cli_sensitivity_hydra.py` | `analytics/cli/cli_sensitivity_hydra.py` | ⏳ Pending |

### Existing Shims (Phase 4-5 Complete)

| Shim | Target | Status |
|------|--------|--------|
| `analytics/monte_carlo_v14.py` | `analytics.mc.engine` | ✅ Complete |
| `analytics/monte_carlo_correlation.py` | `analytics.mc.correlation` | ✅ Complete |
| `analytics/correlation_engine.py` | `analytics.mc.correlation` | ✅ Complete |

---

## Phase 3: Import Fixes ⏳ PENDING

**Status**: ⏳ Planning  
**Strategy**: Update internal imports to use new paths

### Known Import Updates Needed

#### 1. casper_v14.py (Line 6)
```python
# OLD
from analytics import evaluation_v14
from analytics.casper_payload import build_casper_payload

# NEW
from analytics import evaluation_v14
from analytics.casper.casper_payload import build_casper_payload
```

#### 2. Update __init__.py Files

```python
# analytics/casper/__init__.py
from analytics.casper.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.casper.casper_payload import build_casper_payload
from analytics.casper.kpi_normalizer import normalize_kpis

__all__ = [
    "evaluate_with_casper_tail_risk_and_payload",
    "build_casper_payload",
    "normalize_kpis",
]
```

---

## Migration Strategy

### Principles

1. **Gradual**: Move modules in priority order
2. **Testable**: Each phase has verification steps
3. **Reversible**: Shims allow rollback
4. **Safe**: No main branch commits (GWTF R25)

### Execution Steps

1. **Phase 1**: Move Priority 1 files (CASPER)
2. **Phase 2**: Create shims for moved files
3. **Phase 3**: Update internal imports
4. **Verify**: Run test suite
5. **Repeat**: Move next priority group

### Verification Checklist

After each migration batch:

```bash
# 1. Import tests
python -c "from analytics.casper import evaluate_with_casper_tail_risk_and_payload; print('✅ New imports OK')"
python -c "from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload; print('✅ Shim works')"

# 2. Unit tests
pytest tests/analytics_layer/test_casper_v14.py -v
pytest tests/analytics_layer/test_mc_integration.py -v

# 3. Integration tests
pytest tests/integration/ -v

# 4. Type checking
mypy analytics/casper/ --strict

# 5. Lint
ruff check analytics/casper/
```

---

## Risk Assessment

### Low Risk
- ✅ MC package (Phase 4-5): Already complete and tested
- ✅ Phase 0: Package structure created, no breaking changes

### Medium Risk
- ⚠️ CASPER modules: Well-isolated but imported by GWTF workflows
- ⚠️ CLI modules: Hydra entrypoints, need careful shim handling

### High Risk
- ⛔ Core metrics (returns, risk_metrics): Widely imported
- ⛔ Pipeline modules: Complex dependency graphs

### Mitigation
- Start with low/medium risk modules
- Comprehensive shim coverage
- Incremental testing after each move
- Keep feature branch separate (GWTF R25)

---

## Success Criteria

### Phase 1-3 Complete When:
- [ ] All Priority 1-3 files moved
- [ ] All shims created and tested
- [ ] All internal imports updated
- [ ] Test suite passes 100%
- [ ] Documentation updated
- [ ] Migration verified in feature branch

### Final Success When:
- [ ] All 60+ analytics files organized
- [ ] Zero import errors
- [ ] Zero test failures
- [ ] Clean mypy/ruff checks
- [ ] Backward compatibility verified
- [ ] GWTF workflows validated

---

## Current Status Summary

| Phase | Status | Files | Complexity |
|-------|--------|-------|------------|
| **Phase 0** | ✅ Complete | 6 __init__.py | Low |
| **Phase 1** | ⏳ Planning | 10-15 moves | Medium |
| **Phase 2** | ⏳ Planning | 10-15 shims | Low |
| **Phase 3** | ⏳ Planning | ~20 import updates | Medium |
| **Phase 4-5** | ✅ Complete | MC package | Low |

---

## Next Steps

1. **Immediate**: Implement Priority 1 (CASPER moves)
2. **Short-term**: Complete Priorities 2-3 (CLI, FX)
3. **Medium-term**: Core metrics migration
4. **Long-term**: Full analytics package cleanup

---

## References

- **Patch Plan**: Original comprehensive restructuring specification
- **GWTF R25**: No main branch commits rule
- **CASPER Contract**: `docs/api_contract_casper_result_v1.md`
- **MC Package**: `analytics/mc/` (complete reference implementation)

---

**Document Status**: Living document, updated as migration progresses  
**Last Updated**: December 23, 2025, 4:47 AM IST  
**Next Review**: After Priority 1 completion
