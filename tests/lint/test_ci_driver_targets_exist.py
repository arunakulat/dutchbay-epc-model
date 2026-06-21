"""CESSPIT / ARCH guard: the go_with_the_flow CI driver must stay self-consistent.

Two latent failures in scripts/go_with_the_flow_ci.py motivated this guard (audit,
2026-06-21):

1. FAST_PYTEST_TARGETS listed ``tests/api/test_scenario_manager_smoke.py``, which never
   existed on disk. Pytest treats a missing path argument as a usage error (exit code 4),
   so ``python scripts/go_with_the_flow_ci.py --fast`` aborted before running ANY test —
   a silently-broken local fast lane. Remote CI was unaffected (the GitHub ``fastlane``
   job runs ``pytest tests/`` directly, NOT this driver), which is exactly why CI stayed
   green and hid the rot. Its subject, analytics/scenario_manager.py, was itself orphaned
   dead code (zero importers) and was deleted alongside the dead CI entry.

2. A stray bare ``EOF`` heredoc terminator sat at module top level, so *importing* the
   driver raised ``NameError: name 'EOF' is not defined``. It survived only because the
   script runs as ``__main__`` and ``app()`` sys.exits before reaching that line.

This guard fails loud on both classes: the driver must import cleanly, and every path in
its tool-target tuples must resolve on disk.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "scripts" / "go_with_the_flow_ci.py"


def _load_driver():
    """Import the CI driver from its file path (scripts/ is not a package).

    ``exec_module`` runs the module body; a top-level ``NameError`` (e.g. the stray
    ``EOF``) surfaces here. ``app()`` is guarded by ``if __name__ == "__main__"`` so the
    import has no CLI side effects.
    """
    spec = importlib.util.spec_from_file_location("gwtf_ci_driver", DRIVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_driver_imports_cleanly() -> None:
    """The driver must import without raising (catches the stray-``EOF`` NameError class)."""
    assert DRIVER.exists(), f"CI driver missing: {DRIVER}"
    module = _load_driver()
    assert hasattr(module, "FAST_PYTEST_TARGETS")


# Each attribute is a tuple of repo-relative paths the driver hands to a tool
# (pytest / black / isort / compileall / mypy) or reads for the artifact. A non-existent
# entry silently breaks the corresponding lane, so all must resolve on disk.
_PATH_TUPLE_ATTRS = (
    "FAST_PYTEST_TARGETS",
    "FULL_PYTEST_TARGETS",
    "BLACK_TARGETS",
    "ISORT_TARGETS",
    "COMPILE_TARGETS",
    "MYPY_TARGETS",
    "ARTIFACT_MODULES",
)


@pytest.mark.parametrize("attr", _PATH_TUPLE_ATTRS)
def test_all_ci_target_paths_exist(attr: str) -> None:
    module = _load_driver()
    targets = getattr(module, attr)
    missing = [t for t in targets if not (REPO_ROOT / t).exists()]
    assert not missing, (
        f"{attr} references path(s) that do not exist on disk: {missing}. "
        "A missing target silently breaks its CI lane (pytest exits 4 on a missing path; "
        "black/mypy/compileall error). Remove the dead entry or restore the file."
    )


def test_fast_pytest_targets_collect_tests() -> None:
    """Every --fast target must actually COLLECT tests — existence alone is too weak.

    The lane pointed for a long time at four targets that all collected ZERO tests (one
    path was missing; three were 4-line quarantine tombstones). Each existed on disk, so a
    path-existence check passed while ``--fast`` still aborted with pytest's no-tests exit
    code. This guard runs ``pytest --collect-only`` per target and fails if any collects
    nothing (pytest returncode 5).
    """
    module = _load_driver()
    empty = []
    for target in module.FAST_PYTEST_TARGETS:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", target, "--collect-only", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        # pytest exit 5 == "no tests collected"; 0 == collected at least one.
        if proc.returncode != 0:
            empty.append(f"{target} (pytest --collect-only rc={proc.returncode})")
    assert not empty, (
        "FAST_PYTEST_TARGETS contains target(s) that collect ZERO tests — `--fast` would "
        "abort with pytest's no-tests-collected exit code:\n  " + "\n  ".join(empty)
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
