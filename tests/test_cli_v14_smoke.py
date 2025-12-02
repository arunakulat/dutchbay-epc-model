#!/usr/bin/env python3
"""Smoke test for run_full_pipeline_v14.py CLI."""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "run_full_pipeline_v14.py"
LENDERCASE_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_cli_v14_pipeline_invocation():
    assert SCRIPT.exists(), f"Pipeline script not found: {SCRIPT}"
    assert LENDERCASE_CONFIG.exists(), f"Missing lendercase config: {LENDERCASE_CONFIG}"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            f"config={LENDERCASE_CONFIG}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert (
        result.returncode == 0
    ), f"CLI failed:\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
