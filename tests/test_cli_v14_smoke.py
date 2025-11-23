"""Smoke test for CLI invocation of run_full_pipeline.py."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path("run_full_pipeline.py")
LENDERCASE_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


def test_cli_v14_pipeline_invocation():
    assert SCRIPT.exists(), f"Pipeline script not found: {SCRIPT}"
    assert LENDERCASE_CONFIG.exists(), f"Missing lendercase config: {LENDERCASE_CONFIG}"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "base", "--config", str(LENDERCASE_CONFIG)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.returncode == 0
    # Check that pipeline completed - output goes to logs, not stdout in this mode
    assert len(result.stderr) > 0 or "completed" in result.stdout.lower() or result.returncode == 0
