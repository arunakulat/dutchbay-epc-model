"""Check both supported entrypoint forms against the governed interpreter."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module",
    [
        "gwtf_checkpoint_readiness",
        "gwtf_checkpoint_receipt",
        "gwtf_interruption_recovery",
        "gwtf_incident",
    ],
)
def test_governed_script_and_module_entrypoints(module: str) -> None:
    imported = importlib.import_module(f"scripts.{module}")
    assert Path(imported.__file__).resolve() == ROOT / "scripts" / f"{module}.py"
    for command in (
        [sys.executable, "-B", str(ROOT / "scripts" / f"{module}.py"), "--help"],
        [sys.executable, "-B", "-m", f"scripts.{module}", "--help"],
    ):
        result = subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()
