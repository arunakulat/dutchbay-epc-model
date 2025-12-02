#!/usr/bin/env python3
"""
Smoke test for the v14 ScenarioAnalytics Hydra CLI.

This test ensures that:

- The Hydra-based CLI runs without crashing.
- The output is valid JSON at the end of stdout.
- We get non-negative n_success / n_failed counts.
- The Excel output file is created when exports are enabled.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "run_scenario_analytics_v14.py"


def _extract_trailing_json(stdout: str) -> dict:
    """
    Extract the final JSON object from stdout.

    We assume:
    - Logging noise may contain braces (e.g. {...}) that are NOT JSON.
    - The actual JSON is printed last via json.dumps(..., indent=2),
      so it's a multi-line block at the end of stdout.
    """
    lines = stdout.splitlines()
    if not lines:
        raise AssertionError("ScenarioAnalytics CLI produced empty stdout")

    # Walk from the bottom up until we hit the line that starts the JSON object.
    json_lines = []
    seen_opening = False

    for line in reversed(lines):
        json_lines.append(line)
        if line.lstrip().startswith("{"):
            seen_opening = True
            break

    if not seen_opening:
        raise AssertionError(
            "Could not locate JSON block in ScenarioAnalytics CLI stdout.\n"
            f"STDOUT:\n{stdout}\n"
        )

    json_text = "\n".join(reversed(json_lines))

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "Failed to parse JSON block from ScenarioAnalytics CLI stdout.\n"
            f"Error: {exc}\n\n"
            f"Extracted JSON text:\n{json_text}\n\n"
            f"Full STDOUT:\n{stdout}\n"
        ) from exc


@pytest.mark.smoke
def test_scenario_analytics_cli_v14_smoke() -> None:
    """Run the v14 ScenarioAnalytics CLI and validate basic behaviour."""
    assert SCRIPT.exists(), f"ScenarioAnalytics CLI script not found: {SCRIPT}"

    cmd = [
        sys.executable,
        str(SCRIPT),
        "scenarios_dir=scenarios",
        "output=exports/v14_analytics_test.xlsx",
        "charts=false",  # keep charts off for this smoke to make it cheap
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        pytest.fail(
            "ScenarioAnalytics v14 CLI exited with non-zero status.\n\n"
            f"CMD: {' '.join(cmd)}\n"
            f"RETURN CODE: {proc.returncode}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )

    stdout = proc.stdout.strip()
    assert stdout, "ScenarioAnalytics CLI produced no stdout"

    data = _extract_trailing_json(stdout)

    assert isinstance(data, dict), "ScenarioAnalytics CLI JSON must be an object"
    assert "n_success" in data, "Expected 'n_success' in CLI JSON output"
    assert "n_failed" in data, "Expected 'n_failed' in CLI JSON output"

    assert data["n_success"] >= 0
    assert data["n_failed"] >= 0

    output_path = data.get("output_path")
    assert output_path, "Expected 'output_path' in CLI JSON output"
    out_file = REPO_ROOT / output_path
    assert out_file.exists(), f"Expected Excel output file at: {out_file}"
