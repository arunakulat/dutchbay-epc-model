# E402 Lint Warnings - Deferred (Import Ordering)

**Status:** RESOLVED (2026-07-07, #921) — the register's recommended Option 3 (file-level suppression) was adopted repo-wide; `ruff check --select E402 .` now reports **0**. See the Resolution note below. The original register is retained for history.
**Priority:** Low (cosmetic)
**Created:** 2025-12-24 (Sprint 18 Dolphin #10)
**Affected Files (historical):** 72 instances across 23 files → now 0

---

## Resolution (2026-07-07, issue #921)

This deferral is closed. The register's own recommendation — **Option 3 (suppression)** — was carried out during the ruff lint-stack consolidation (#610 / #545): the affected `analytics/mc/*`, `analytics/sensitivity/*`, and legacy `*_v14` shim modules carry a top-of-file `# ruff: noqa: E402` directive (77 such suppressions across the tree). That is the correct treatment because their late imports are intentional — documentation-first modules, and deprecation-warning shims whose imports must follow the `warnings.warn`. The one remaining unsuppressed case, `scripts/run_tornado_from_cli.py` (imports that intentionally follow a `sys.path` repo-root bootstrap), was suppressed the same way under #921.

**Verification:** `ruff check --select E402 .` → 0 across `analytics`, `finance`, `app`, `api`, `scripts`; the default `ruff check .` gate is clean. E402 is not an enforced blocking rule, and no import was reordered (which would have broken the bootstrap / deprecation-warning ordering). KPI-neutral.

The original 2025-12 register follows unchanged for historical reference.

---

## Overview

The remaining 72 E402 warnings (`Module level import not at top of file`) are due to docstrings and comments appearing before import statements. This is a **style preference**, not a functionality issue.

**Why deferred:**
1. Code works perfectly as-is
2. Imports are logically grouped
3. Docstrings provide valuable context
4. Fixing requires moving imports above docstrings (PEP 8 strict)
5. Would reduce code readability for marginal lint improvement

---

## Affected Modules

### Monte Carlo Package (`analytics/mc/`)
- `aggregate.py` (3 instances)
- `correlation.py` (3 instances)
- `degradation.py` (1 instance)
- `engine.py` (10 instances)
- `exports.py` (4 instances)
- `samplers.py` (2 instances)

### Sensitivity Package (`analytics/sensitivity/`)
- `adapters.py` (2 instances)
- `dscr.py` (4 instances)
- `engine.py` (6 instances)
- `export.py` (2 instances)
- `heatmap.py` (2 instances)
- `optimizer.py` (4 instances)
- `tail_risk.py` (4 instances)
- `tax.py` (4 instances)
- `viz.py` (1 instance)

### Legacy Shim Files (Deprecation Warnings)
- `sensitivity_dscr_v14.py` (2 instances)
- `sensitivity_export.py` (2 instances)
- `sensitivity_heatmap.py` (2 instances)
- `sensitivity_tail_risk.py` (2 instances)
- `sensitivity_v14.py` (2 instances)
- `tax_sensitivity_v14.py` (3 instances)

### Other
- `finance/irr/__init__.py` (1 instance)

---

## Example Pattern

**Current (E402 warning):**
```python
"""Module docstring explaining what this does.

Detailed explanation with examples.
"""

from typing import Any  # E402: Import not at top
import numpy as np     # E402: Import not at top
```

**PEP 8 Strict (no warning):**
```python
from typing import Any
import numpy as np

"""Module docstring explaining what this does.

Detailed explanation with examples.
"""
```

**Trade-off:** Moving imports above docstrings breaks the natural flow where docstring introduces the module, then imports show dependencies.

---

## Why This Pattern Exists

### Intentional Design Choice
These files were written with **documentation-first** philosophy:
1. Module docstring explains purpose
2. Then imports show what the module needs
3. Then implementation

### Legacy Shim Files
Files like `sensitivity_dscr_v14.py` intentionally have deprecation warnings at the top:
```python
"""Legacy module (deprecated)."""

import warnings

warnings.warn(
    "This module is deprecated...",
    DeprecationWarning,
    stacklevel=2,
)

from analytics.sensitivity.dscr import *  # E402
```

Moving imports above the warning would defeat the purpose.

---

## Fix Strategy (If Needed)

### Option 1: Auto-fix with `ruff` (Recommended)
```bash
# Use unsafe fixes to move imports
ruff check --fix --unsafe-fixes analytics/mc/ analytics/sensitivity/
```

### Option 2: Manual Refactor (Sprint 19+)
1. Move all imports to top (above docstrings)
2. Keep module docstring immediately after imports
3. Verify no import order dependencies broken

### Option 3: Suppress E402 for These Files
Add to `pyproject.toml`:
```toml
[tool.ruff.lint.per-file-ignores]
"analytics/mc/*.py" = ["E402"]
"analytics/sensitivity/*.py" = ["E402"]
"analytics/*_v14.py" = ["E402"]  # Legacy shims
```

---

## Decision Log

### Sprint 18 Dolphin Strategy
- Fixed all **functional** lint issues (F841, F401, F405)
- Code imports work correctly
- Deferred E402 as **cosmetic only**
- Documented pattern for future reference

### Recommendation
**Option 3 (suppression) preferred** because:
1. Docstring-first is clearer for developers
2. E402 does not indicate bugs, just style preference
3. Frees up lint focus for real issues
4. Legacy shims need warnings before imports

---

## Impact Assessment

| Aspect | Status |
|--------|--------|
| **Functionality** | No impact - code works |
| **Type Safety** | No impact - mypy passes |
| **Import Resolution** | No impact - all imports resolve |
| **Documentation** | Better with current pattern |
| **PEP 8 Strict** | Violates import-first convention |
| **Readability** | Better with docstring-first |

---

## Related Files

- [Sprint 18 Implementation Plan](SPRINT_18_IMPLEMENTATION_PLAN.md)
- [Missing Functions](MISSING_FUNCTIONS_SPRINT_18.md)
- [GWTF Compliance](compliance/GWTF_COMPLIANCE.md)

---

## Conclusion

**E402 warnings are cosmetic and do not block:**
- PR #58 merge
- Production deployment
- CI pipeline
- Future development

**If team prefers PEP 8 strict:** Run `ruff check --fix --unsafe-fixes` in Sprint 19.

**Current recommendation:** Suppress E402 for these modules in `pyproject.toml` to reduce noise.

---

**Maintained by:** DutchBay EPC Model Team
**Review Cadence:** Sprint planning (if needed)
**Last Reviewed:** Sprint 18 (2025-12-24)
**Dolphins Involved:** #10c (Documentation)
