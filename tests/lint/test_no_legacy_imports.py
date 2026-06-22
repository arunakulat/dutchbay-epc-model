"""Lint: production code must not import the quarantined legacy trees.

Wires ``scripts/ci/check_legacy_imports.find_violations`` into the test suite (and
thus CI). The guard previously existed but was **doubly dead**: nothing invoked
it, and its repo-root was off by one directory (``parent.parent`` -> ``scripts/``),
so the scan found none of the protected dirs and passed vacuously. With the root
fixed, this test makes the quarantine boundary actually enforced.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "scripts" / "ci" / "check_legacy_imports.py"


def _load_guard():
    """Import the guard from its file path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("check_legacy_imports", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guard_scans_real_protected_dirs() -> None:
    # Root must resolve to the repo (where analytics/ and finance/ live), not scripts/.
    guard = _load_guard()
    assert (guard.REPO_ROOT / "analytics").is_dir()
    assert (guard.REPO_ROOT / "finance").is_dir()


def test_no_forbidden_legacy_imports() -> None:
    guard = _load_guard()
    violations = guard.find_violations()
    assert violations == [], "Forbidden legacy imports in production code:\n" + "\n".join(
        violations
    )
