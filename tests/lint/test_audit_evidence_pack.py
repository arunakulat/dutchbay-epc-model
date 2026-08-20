"""Repository gate for the August 2026 controlled audit successor pack."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "scripts"
    / "validate_published_pack.py"
)


def test_controlled_audit_successor_pack_is_internally_valid() -> None:
    """The published pack must remain manifest-complete and explicitly on HOLD."""
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"status": "PASS"' in completed.stdout
    assert '"release_status": "HOLD"' in completed.stdout
