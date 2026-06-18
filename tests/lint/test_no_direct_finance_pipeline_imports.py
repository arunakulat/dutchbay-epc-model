"""CCCDIR boundary guard: analytics layer must not bypass the evaluation gateway.

Issue #36 (CCCDIR boundary enforcement).

Boundary rule
-------------
Analytics-layer modules (everything under ``analytics/``) must NOT import
``finance.*`` or ``analytics.pipeline_*`` **directly** at module scope.
Scenario evaluation is routed through the single gateway:

    analytics.evaluation_v14.evaluate_with_overrides(...)

The gateway and the pipeline modules themselves form the allowed boundary,
so they are exempt. A small, explicit ALLOWLIST captures the modules that
predate this guard; each entry is documented as either a permanent
low-level finance adapter or a tracked TODO-to-refactor.

Why this matters
----------------
Without the boundary, any analytics helper can reach straight into
``finance.debt_v14`` / ``finance.cashflow_v14`` / a ``pipeline_*`` engine,
producing a tangle of cross-layer calls that drift out of sync with the
gateway's normalisation contract. Routing through ``evaluate_with_overrides``
keeps one path in and one KPI shape out.

Scope (deliberate)
------------------
This guard inspects **module-level** import statements only (the same surface
the naive rule flags). Function-scoped / lazy imports are out of scope; the
one current lazy carve-out (``analytics/fx_sensitivity_real.py`` importing
``analytics.pipeline_analytics_v14`` inside a method) is noted below but not
enforced here, to keep the rule deterministic and the allowlist honest.

Run:
    pytest tests/lint/test_no_direct_finance_pipeline_imports.py -v

GWTF / CCCDIR:
    - CCCDIR: Clear cross-layer boundary; analytics depends on the gateway,
      not on finance internals or pipeline engines.
    - CST-01: LibCST static inspection (no runtime import of the target).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

import libcst as cst
import pytest

# ═════════════════════════════════════════════════════════════════════════════
# Boundary configuration
# ═════════════════════════════════════════════════════════════════════════════

# Repository root (tests/lint/ -> tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = REPO_ROOT / "analytics"

# Top-level package prefixes that an analytics module may not import directly.
# A module name "matches" if it equals the prefix or starts with "<prefix>.".
FORBIDDEN_FINANCE_PREFIX = "finance"
FORBIDDEN_PIPELINE_PREFIX = "analytics.pipeline_"

# The gateway every analytics consumer should route through instead.
GATEWAY = "analytics.evaluation_v14.evaluate_with_overrides"

# Files that ARE the boundary and are therefore exempt from the rule.
# Stored as repo-relative POSIX paths.
EXEMPT_FILES: Set[str] = {
    # The gateway itself: it legitimately drives the pipeline + finance engines.
    "analytics/evaluation_v14.py",
}

# Pipeline modules (analytics/pipeline_*.py) are the allowed boundary layer:
# they are *expected* to import finance.* and to be the thing the gateway calls.
# They are exempt by the filename pattern check below, not by name listing.


# ═════════════════════════════════════════════════════════════════════════════
# ALLOWLIST — the 7 pre-existing violators (issue #36)
# ═════════════════════════════════════════════════════════════════════════════
#
# Key   : repo-relative POSIX path of the analytics module.
# Value : one-line rationale (kept for the failure message / audit trail).
#
# Classification:
#   [PERMANENT] — legitimate low-level finance adapter. These modules SHOULD
#                 depend on finance.* directly; they are the thin seam that
#                 the rest of analytics consumes instead of reaching into
#                 finance themselves. Keeping them on the allowlist is the
#                 intended end-state, not debt.
#   [TODO]      — a real layering violation. Should eventually route through
#                 the gateway (or move the finance call behind a core adapter)
#                 and then be removed from this allowlist.
#
ALLOWLIST: dict[str, str] = {
    # --- [PERMANENT] analytics.core.* low-level finance adapters -------------
    "analytics/core/metrics.py": (
        "[PERMANENT] Canonical KPI engine; delegates NPV/IRR to finance.irr "
        "(R7 single source of truth). This IS the finance adapter for KPIs."
    ),
    "analytics/core/returns.py": (
        "[PERMANENT] Project/equity returns adapter; delegates IRR/NPV to "
        "finance.irr by design (R7). Thin wrapper, not a layering breach."
    ),
    "analytics/core/epc_helper.py": (
        "[PERMANENT] 6-line re-export shim for finance.epc_helper_v14 EPC "
        "breakdown helpers; exists precisely to give analytics one import seam."
    ),
    # --- [TODO] real layering violations to refactor toward the gateway -----
    "analytics/dscr_sensitivity.py": (
        "[TODO #36] Imports finance.debt_v14.size_debt_with_dual_dscr directly "
        "for dual-DSCR debt sizing. Should call debt sizing via a core adapter "
        "or the gateway. Tracked refactor."
    ),
    "analytics/evaluate_scenario.py": (
        "[TODO #36] Legacy coordinator that calls "
        "analytics.pipeline_v14_enhanced.run_v14_pipeline directly. Superseded "
        "by analytics.evaluation_v14; callers should migrate then delete this."
    ),
    "analytics/scenario_analytics.py": (
        "[TODO #36] Batch orchestrator importing finance.cashflow_v14 + "
        "finance.debt_v14 directly per scenario. Should batch over the gateway "
        "(evaluate_with_overrides) instead of driving engines itself."
    ),
    "analytics/stress_tests_v14.py": (
        "[TODO #36] Imports finance.irr (irr, npv) directly for stress NPV/IRR "
        "(R7). Borderline: could route through analytics.core.metrics/returns "
        "to drop the direct finance dependency. Tracked."
    ),
}

# Files that contain a forbidden import only at function scope (lazy import),
# which this module-level guard intentionally does NOT flag. Documented here so
# the carve-out is visible and reviewable, NOT enforced:
#   analytics/fx_sensitivity_real.py
#       -> `from analytics.pipeline_analytics_v14 import ...` inside a method.


# ═════════════════════════════════════════════════════════════════════════════
# LibCST module-level import collector
# ═════════════════════════════════════════════════════════════════════════════


class _ModuleLevelImportCollector(cst.CSTVisitor):
    """Collect imported module names from MODULE-LEVEL statements only.

    Both ``import a.b.c`` and ``from a.b import name`` forms are captured.
    Imports nested inside functions, methods, or conditionals are ignored:
    we never descend into ``FunctionDef`` bodies, so only top-level (and
    class-body) imports are recorded.
    """

    def __init__(self) -> None:
        self.imported_modules: List[str] = []

    # Do not descend into function/method bodies: keep scope to module level.
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        return False

    @staticmethod
    def _dotted_name(node: cst.BaseExpression) -> str:
        """Flatten a Name/Attribute node into a dotted module string."""
        parts: List[str] = []
        current: cst.BaseExpression | None = node
        while current is not None:
            if isinstance(current, cst.Name):
                parts.insert(0, current.value)
                break
            if isinstance(current, cst.Attribute):
                parts.insert(0, current.attr.value)
                current = current.value
            else:
                break
        return ".".join(parts)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = self._dotted_name(alias.name)
            if name:
                self.imported_modules.append(name)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        # Skip relative imports (from . import x) — node.module is None there.
        if node.module is None:
            return
        name = self._dotted_name(node.module)
        if name:
            self.imported_modules.append(name)


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


def _is_forbidden(module_name: str) -> bool:
    """Return True if ``module_name`` is a forbidden finance/pipeline import."""
    if module_name == FORBIDDEN_FINANCE_PREFIX or module_name.startswith(
        FORBIDDEN_FINANCE_PREFIX + "."
    ):
        return True
    if module_name.startswith(FORBIDDEN_PIPELINE_PREFIX):
        return True
    return False


def _rel_posix(path: Path) -> str:
    """Repo-relative POSIX path for use as an allowlist / exempt key."""
    return path.relative_to(REPO_ROOT).as_posix()


def _is_exempt(rel_path: str) -> bool:
    """Gateway and pipeline_* modules are the allowed boundary, so exempt."""
    if rel_path in EXEMPT_FILES:
        return True
    # analytics/pipeline_*.py — the pipeline modules themselves.
    name = rel_path.rsplit("/", 1)[-1]
    return rel_path.startswith("analytics/") and name.startswith("pipeline_")


def _analytics_py_files() -> List[Path]:
    """All Python files under analytics/, excluding caches."""
    files = [
        p
        for p in ANALYTICS_DIR.rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    return sorted(files)


def _forbidden_imports_in(path: Path) -> List[str]:
    """Return the module-level forbidden imports found in ``path`` (may be [])."""
    source = path.read_text(encoding="utf-8")
    try:
        module = cst.parse_module(source)
    except Exception as exc:  # pragma: no cover - parse failure is a hard error
        pytest.fail(f"LibCST failed to parse {_rel_posix(path)}: {exc}")
    collector = _ModuleLevelImportCollector()
    module.visit(collector)
    return [m for m in collector.imported_modules if _is_forbidden(m)]


# Pre-compute the full violation map once at collection time so each test
# (and each parametrized case) reads from the same source of truth.
def _scan_violations() -> dict[str, List[str]]:
    """Map repo-relative path -> list of forbidden module-level imports."""
    violations: dict[str, List[str]] = {}
    for path in _analytics_py_files():
        rel = _rel_posix(path)
        if _is_exempt(rel):
            continue
        forbidden = _forbidden_imports_in(path)
        if forbidden:
            violations[rel] = forbidden
    return violations


_VIOLATIONS: dict[str, List[str]] = _scan_violations()


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


def test_no_unlisted_direct_finance_or_pipeline_imports() -> None:
    """No analytics module may import finance.* / pipeline_* unless allowlisted.

    PASSES today: every current violator is in ALLOWLIST (or is an exempt
    boundary module). FAILS the moment a NEW analytics module adds a direct
    module-level ``import finance...`` / ``import analytics.pipeline_...``,
    because that file will not be in ALLOWLIST.
    """
    unlisted: List[Tuple[str, List[str]]] = [
        (rel, mods)
        for rel, mods in sorted(_VIOLATIONS.items())
        if rel not in ALLOWLIST
    ]

    assert not unlisted, (
        "CCCDIR boundary violation (issue #36): analytics module(s) import "
        "finance.* or analytics.pipeline_* directly at module level without an "
        "allowlist entry.\n\n"
        + "\n".join(
            f"  {rel}: {', '.join(mods)}" for rel, mods in unlisted
        )
        + "\n\nFix: route scenario evaluation through the gateway\n"
        f"  {GATEWAY}\n"
        "instead of importing finance/pipeline internals. If this is a genuine "
        "low-level finance adapter (e.g. under analytics/core/), add it to "
        "ALLOWLIST in this file with a [PERMANENT] rationale."
    )


def test_allowlist_has_no_stale_entries() -> None:
    """Every ALLOWLIST entry must still exist and still actually violate.

    Keeps the allowlist from rotting: once a [TODO] module is refactored to
    route through the gateway (and no longer imports finance/pipeline), its
    allowlist entry must be removed or this test fails.
    """
    stale: List[str] = []
    for rel in sorted(ALLOWLIST):
        path = REPO_ROOT / rel
        if not path.exists():
            stale.append(f"{rel} (file no longer exists)")
            continue
        if rel not in _VIOLATIONS:
            stale.append(f"{rel} (no longer imports finance/pipeline directly)")

    assert not stale, (
        "Stale ALLOWLIST entries in test_no_direct_finance_pipeline_imports.py "
        "(remove them — the boundary debt is paid off):\n"
        + "\n".join(f"  {s}" for s in stale)
    )


def test_gateway_and_pipeline_modules_are_exempt() -> None:
    """Sanity: the gateway and pipeline_* modules are treated as exempt.

    Guards against an accidental change that would start flagging the boundary
    modules themselves (which are *supposed* to import finance/pipeline).
    """
    assert _is_exempt("analytics/evaluation_v14.py")
    assert _is_exempt("analytics/pipeline_v14.py")
    assert _is_exempt("analytics/pipeline_v14_enhanced.py")
    # A normal analytics module is NOT exempt.
    assert not _is_exempt("analytics/scenario_analytics.py")


@pytest.mark.parametrize("rel_path", sorted(ALLOWLIST))
def test_allowlisted_files_exist(rel_path: str) -> None:
    """Each allowlisted path must point at a real file (typo guard)."""
    assert (REPO_ROOT / rel_path).exists(), (
        f"ALLOWLIST references a missing file: {rel_path}. "
        "Fix the path or remove the entry."
    )


def test_forbidden_matcher_semantics() -> None:
    """Unit-level checks on the forbidden-import matcher (no I/O)."""
    # finance.* is forbidden (exact and dotted).
    assert _is_forbidden("finance")
    assert _is_forbidden("finance.irr")
    assert _is_forbidden("finance.debt_v14")
    # analytics.pipeline_* is forbidden.
    assert _is_forbidden("analytics.pipeline_v14_enhanced")
    assert _is_forbidden("analytics.pipeline_analytics_v14")
    # The gateway and ordinary analytics modules are NOT forbidden.
    assert not _is_forbidden("analytics.evaluation_v14")
    assert not _is_forbidden("analytics.scenario_loader")
    assert not _is_forbidden("analytics.core.metrics")
    # A package that merely starts with "finance" letters is not finance.*.
    assert not _is_forbidden("financemodel")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
