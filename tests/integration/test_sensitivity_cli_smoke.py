"""Smoke gate: the canonical sensitivity Hydra CLI must run end-to-end.

No test exercised analytics/cli/cli_sensitivity_hydra.py as a CLI, so a config
change could break it while the rest of the suite stayed green (e.g. stripping
the decorative `shocks` key tripped `OmegaConf.to_container` on the dict
default). This subprocess smoke runs the CLI on the canonical scenario and
asserts it exits 0 and reports tornado(s).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_sensitivity_hydra_cli_runs() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "analytics.cli.cli_sensitivity_hydra",
            f"config={LENDER}",
            "write_artifacts=false",
        ],
        cwd=str(REPO_ROOT),  # makes `analytics` importable + relative paths resolve
        capture_output=True,
        text=True,
        timeout=300,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"CLI exited {proc.returncode}:\n{combined[-1000:]}"
    assert "tornado(s) analyzed" in combined or '"status": "success"' in combined
