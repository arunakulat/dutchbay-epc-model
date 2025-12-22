# Analytics Package Restructuring - Migration Plan

**Status**: Phase 0 Complete ✅ | Priority 1 Complete ✅ | Priorities 2-5 Pending ⏳  
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

**Progress**: ✅ Phase 0 complete | ✅ MC consolidation complete | ✅ Priority 1 (CASPER) complete

---

## Current State

```
analytics/
├── casper_v14.py (SHIM → casper/casper_v14.py) ✅
├── casper_payload.py (SHIM → casper/casper_payload.py) ✅
├── kpi_normalizer.py (SHIM → casper/kpi_normalizer.py) ✅
├── fx_integration.py
├── wind_integration.py
├── cli_monte_carlo_hydra.py
├── cli_sensitivity_hydra.py
├── monte_carlo_v14.py (SHIM → mc/engine.py) ✅
├── monte_carlo_correlation.py (SHIM → mc/correlation.py) ✅
├── correlation_engine.py (SHIM → mc/correlation.py) ✅
├── [50+ other modules]
├── mc/                   ✅ COMPLETE
│   ├── engine.py
│   ├── correlation.py
│   ├── samplers.py
│   ├── degradation.py
│   ├── aggregate.py
│   └── exports.py
└── casper/                ✅ COMPLETE
    ├── casper_v14.py
    ├── casper_payload.py
    └── kpi_normalizer.py
```

---

## Target State

```
analytics/
├── core/                  # Core metrics & calculations
│   ├── __init__.py ✅
│   ├── returns.py          ⏳
│   ├── risk_metrics.py     ⏳
│   ├── parameter_solvers.py ⏳
│   └── config_schema.py    ⏳
│
├── casper/                # CASPER payload generation
│   ├── __init__.py ✅
│   ├── casper_v14.py       ✅
│   ├── casper_payload.py   ✅
│   └── kpi_normalizer.py   ✅
│
├── fx/                    # FX integration
│   ├── __init__.py ✅
│   └── fx_integration.py   ⏳
│
├── wind/                  # Wind analytics
│   ├── __init__.py ✅
│   ├── wind_integration.py ⏳
│   └── pipeline_aep_v14.py ⏳
│
├── mc/                    # Monte Carlo (COMPLETE ✅)
│   ├── __init__.py ✅
│   ├── engine.py           ✅
│   ├── correlation.py      ✅
│   ├── samplers.py         ✅
│   ├── degradation.py      ✅
│   ├── aggregate.py        ✅
│   └── exports.py          ✅
│
├── cli/                   # CLI entrypoints
│   ├── __init__.py ✅
│   ├── cli_monte_carlo_hydra.py  ⏳
│   └── cli_sensitivity_hydra.py  ⏳
│
└── [legacy shims for backward compatibility]
    ├── casper_v14.py → casper/casper_v14.py      ✅
    ├── casper_payload.py → casper/casper_payload.py ✅
    ├── kpi_normalizer.py → casper/kpi_normalizer.py ✅
    ├── monte_carlo_v14.py → mc/engine.py           ✅
    ├── monte_carlo_correlation.py → mc/correlation.py ✅
    └── correlation_engine.py → mc/correlation.py   ✅

analysis_tools/            # Research helpers (outside production)
├── __init__.py ✅
└── fx_correlation_analyzer.py  ⏳
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

## Phase 1-3: File Migrations

### Priority 1: CASPER Modules ✅ COMPLETE

**Status**: ✅ Complete  
**Commit**: `5c44342` - "feat: Priority 1 - Complete CASPER module migration (Phases 1-3)"

**Files Moved** (Phase 1):
```bash
analytics/casper_v14.py → analytics/casper/casper_v14.py       (~3.6KB)
analytics/casper_payload.py → analytics/casper/casper_payload.py (~12.6KB)
analytics/kpi_normalizer.py → analytics/casper/kpi_normalizer.py (~13.9KB)
```

**Shims Created** (Phase 2):
```python
# analytics/casper_v14.py
from analytics.casper.casper_v14 import *  # noqa

# analytics/casper_payload.py  
from analytics.casper.casper_payload import *  # noqa

# analytics/kpi_normalizer.py
from analytics.casper.kpi_normalizer import *  # noqa
```

**Imports Updated** (Phase 3):
```python
# analytics/casper/casper_v14.py (line 6)
# OLD: from analytics.casper_payload import build_casper_payload
# NEW: from analytics.casper.casper_payload import build_casper_payload

# analytics/casper/__init__.py - Complete public API
from analytics.casper.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.casper.casper_payload import build_casper_payload, CASPER_CONTRACT_VERSION
from analytics.casper.kpi_normalizer import normalize_kpis_by_capacity, ...
```

**Impact**:
- ✅ 3 files moved (~30KB code organized)
- ✅ 3 backward compat shims created
- ✅ Clean CASPER subsystem boundary
- ✅ Clear ownership (analytics.casper.*)
- ✅ 100% backward compatibility

**Verification**:
```python
# New imports (preferred)
from analytics.casper import (
    evaluate_with_casper_tail_risk_and_payload,
    build_casper_payload,
    normalize_kpis_by_capacity,
)

# Old imports (still work via shims)
from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.casper_payload import build_casper_payload
from analytics.kpi_normalizer import normalize_kpis_by_capacity
```

---

### Priority 2: CLI Modules ⏳ PENDING

**Status**: ⏳ Planning  
**Strategy**: Same pattern as Priority 1

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
- 3 files to move
- ~14KB code to organize
- 3 shims to create

---

### Priority 3: FX Module ⏳ PENDING

**Status**: ⏳ Planning  

**Move**:
```bash
git mv analytics/fx_integration.py analytics/fx/fx_integration.py
```

**Rationale**:
- Single-file module
- Clean FX subsystem
- Minimal dependencies

**Impact**:
- 1 file to move
- ~4KB code to organize
- 1 shim to create

---

### Priority 4: Wind Modules ⏳ PENDING

**Status**: ⏳ Planning  

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
- 2 files to move
- ~24KB code to organize
- 2 shims to create

---

### Priority 5: Core Metrics ⏳ PENDING

**Status**: ⏳ Planning (Lower Priority)

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
- 4 files to move
- ~67KB code to organize
- 4 shims to create

---

## Migration Strategy

### Principles

1. **Gradual**: Move modules in priority order
2. **Testable**: Each phase has verification steps
3. **Reversible**: Shims allow rollback
4. **Safe**: No main branch commits (GWTF R25)

### Execution Steps (Priority 1 Pattern - Proven ✅)

1. **Phase 1**: Move files to new package
2. **Phase 2**: Create backward compat shims
3. **Phase 3**: Update internal imports
4. **Verify**: Run test suite
5. **Document**: Update migration plan
6. **Repeat**: Move next priority group

### Verification Checklist

After each migration batch:

```bash
# 1. Import tests (new paths)
python -c "from analytics.casper import evaluate_with_casper_tail_risk_and_payload; print('✅ New imports OK')"

# 2. Import tests (old paths via shims)
python -c "from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload; print('✅ Shim works')"

# 3. Unit tests
pytest tests/analytics_layer/test_casper_v14.py -v
pytest tests/analytics_layer/test_mc_integration.py -v

# 4. Integration tests
pytest tests/integration/ -v

# 5. Type checking
mypy analytics/casper/ --strict

# 6. Lint
ruff check analytics/casper/
```

---

## Risk Assessment

### Low Risk ✅
- ✅ MC package (Phase 4-5): Complete and tested
- ✅ Phase 0: Package structure created
- ✅ Priority 1 (CASPER): Complete and verified

### Medium Risk ⚠️
- ⚠️ Priority 2 (CLI): Hydra entrypoints, need careful shim handling
- ⚠️ Priority 3 (FX): Clean module, low dependencies
- ⚠️ Priority 4 (Wind): Well-isolated but AEP dependencies

### High Risk ⛔
- ⛔ Priority 5 (Core): Widely imported across codebase
- ⛔ Pipeline modules: Complex dependency graphs

### Mitigation
- ✅ Proven pattern from Priority 1
- Start with low/medium risk modules
- Comprehensive shim coverage
- Incremental testing after each move
- Keep feature branch separate (GWTF R25)

---

## Success Criteria

### Priority 1 (CASPER) ✅ ACHIEVED
- [x] All 3 CASPER files moved
- [x] All 3 shims created and tested
- [x] Internal imports updated
- [x] Public API exports complete
- [x] Backward compatibility verified
- [x] Documentation updated

### Priorities 2-5 Success Criteria
- [ ] All priority files moved
- [ ] All shims created and tested
- [ ] All internal imports updated
- [ ] Test suite passes 100%
- [ ] Documentation updated
- [ ] Migration verified in feature branch

### Final Success (All Priorities)
- [ ] All 60+ analytics files organized
- [ ] Zero import errors
- [ ] Zero test failures
- [ ] Clean mypy/ruff checks
- [ ] Backward compatibility verified
- [ ] GWTF workflows validated

---

## Current Status Summary

| Phase/Priority | Status | Files | Complexity | Impact |
|----------------|--------|-------|------------|--------|
| **Phase 0** | ✅ Complete | 6 __init__.py | Low | Foundation |
| **Phase 4-5 (MC)** | ✅ Complete | 6 modules + 3 shims | Medium | 776 lines cleaned |
| **Priority 1 (CASPER)** | ✅ Complete | 3 files + 3 shims | Medium | ~30KB organized |
| **Priority 2 (CLI)** | ⏳ Planning | 3 files | Medium | ~14KB to organize |
| **Priority 3 (FX)** | ⏳ Planning | 1 file | Low | ~4KB to organize |
| **Priority 4 (Wind)** | ⏳ Planning | 2 files | Medium | ~24KB to organize |
| **Priority 5 (Core)** | ⏳ Planning | 4 files | High | ~67KB to organize |

**Total Progress**: Phase 0 + MC + Priority 1 complete = **Foundation + 2 subsystems ✅**

---

## Next Steps

1. **Immediate**: Test Priority 1 in GWTF workflows
2. **Short-term**: Implement Priority 2 (CLI) using proven pattern
3. **Medium-term**: Complete Priorities 3-4 (FX, Wind)
4. **Long-term**: Core metrics migration (Priority 5)

---

## Pattern Template (for Priorities 2-5)

Based on successful Priority 1 execution:

```bash
# PHASE 1: Move files
analytics/MODULE.py → analytics/PACKAGE/MODULE.py

# PHASE 2: Create shim
cat > analytics/MODULE.py << 'EOF'
# BACKWARD COMPATIBILITY SHIM
from analytics.PACKAGE.MODULE import *  # noqa
EOF

# PHASE 3: Update imports
# In analytics/PACKAGE/MODULE.py:
# - Update internal imports to new paths
# - Update analytics/PACKAGE/__init__.py with exports

# VERIFY
python -c "from analytics.PACKAGE import FUNCTION"
python -c "from analytics.MODULE import FUNCTION"  # shim
pytest tests/analytics_layer/test_MODULE.py -v
```

---

## References

- **Patch Plan**: Original comprehensive restructuring specification
- **GWTF R25**: No main branch commits rule
- **CASPER Contract**: `docs/api_contract_casper_result_v1.md`
- **MC Package**: `analytics/mc/` (complete reference implementation)
- **Priority 1**: `analytics/casper/` (proven migration pattern)

---

**Document Status**: Living document, updated as migration progresses  
**Last Updated**: December 23, 2025, 4:52 AM IST (Priority 1 complete)  
**Next Review**: After Priority 2 completion
