import json
import subprocess
import sys
import os
import pytest

from dutchbay_v13 import cli


def test_cli_runs_text():
    cfg = os.path.join(
        os.path.dirname(__file__), "..", "inputs", "full_model_variables_updated.yaml"
    )
    cmd = [sys.executable, "-m", "dutchbay_v13.cli", "--config", cfg, "--mode", "irr"]
    out = subprocess.check_output(cmd, text=True)
    assert "IRR / NPV / DSCR RESULTS" in out


def test_cli_runs_json():
    cfg = os.path.join(
        os.path.dirname(__file__), "..", "inputs", "full_model_variables_updated.yaml"
    )
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13.cli",
        "--config",
        cfg,
        "--mode",
        "irr",
        "--format",
        "json",
    ]
    out = subprocess.check_output(cmd, text=True)
    obj = json.loads(out)
    assert "equity_irr_pct" in obj and "project_irr_pct" in obj


def test_cli_invalid_mode_exits_2():
    with pytest.raises(SystemExit) as ei:
        cli.parse_args(["--mode", "nope"])
    assert ei.value.code in (1, 2)
