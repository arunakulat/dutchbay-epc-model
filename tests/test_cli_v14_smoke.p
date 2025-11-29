
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "run_full_pipeline_v14.py"
SCENARIO = REPO_ROOT / "scenarios" / "example_a.yaml"

#!/usr/bin/env python3
"""
Smoke test for the v14 CLI entrypoint (run_full_pipeline_v14.py).

This test ensures that:

- The Hydra-based CLI runs without error for a simple scenario.
- The output is valid JSON.
- The JSON contains a 'kpis' dict with 'project_npv' present.
"""

@pytest.mark.smoke
def test_v14_cli_smoke_example_a() -> None:
    """Run the v14 CLI against scenarios/example_a.yaml and validate basic output."""

    assert SCRIPT.exists(), f"CLI script not found: {SCRIPT}"
    assert SCENARIO.exists(), f"Scenario file not found: {SCENARIO}"

    cmd = [
        sys.executable,
        str(SCRIPT),
        f"config={SCENARIO}",
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        msg = (
            "v14 CLI exited with non-zero status.\n\n"
            f"CMD: {' '.join(cmd)}\n"
            f"RETURN CODE: {proc.returncode}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )
        pytest.fail(msg)

    stdout = proc.stdout.strip()
    assert stdout, "CLI produced no output on stdout"

    # stdout may contain logging + JSON; extract the JSON block
    json_text = None
    try:
        # Fast path: try to parse the whole thing
        json_text = stdout
        data = json.loads(json_text)
    except json.JSONDecodeError:
        # Fallback: extract from first '{' to last '}' in stdout
        if "{" in stdout and "}" in stdout:
            start = stdout.find("{")
            end = stdout.rfind("}") + 1
            json_text = stdout[start:end]
            data = json.loads(json_text)
        else:
            raise AssertionError(
                "CLI stdout did not contain valid JSON.\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{proc.stderr}\n"
            )

    assert isinstance(data, dict), "Top-level JSON from CLI must be an object"

    assert "kpis" in data, "Expected 'kpis' key in CLI JSON output"
    assert isinstance(data["kpis"], dict), "'kpis' must be a dict"
    assert "project_npv" in data["kpis"], "Expected 'kpis.project_npv' in CLI output"
