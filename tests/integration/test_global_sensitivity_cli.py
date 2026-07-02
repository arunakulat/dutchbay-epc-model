"""CLI argument-parsing tests for ``scripts/run_global_sensitivity.py`` (#617).

Focused on the ``--optimal-trajectories`` knob's Morris-only guard: it is a Morris
sampling enhancement (SALib's optimal-trajectory subset selection), so combining it with
``--method sobol`` must fail loud (argparse ``error`` → ``SystemExit(2)``), not silently
ignore the flag. The knob itself is exercised end-to-end against SALib in
``tests/analytics/test_global_sa.py``; here we only need the thin CLI parse layer, so no
SALib import is required.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _load_cli():
    """Import the script as a module (it lives in scripts/, not an installed pkg)."""
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    spec = importlib.util.spec_from_file_location(
        "run_global_sensitivity", _REPO / "scripts" / "run_global_sensitivity.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_optimal_trajectories_parsed_on_morris_path() -> None:
    cli = _load_cli()
    args = cli._parse_args(
        [
            "--config",
            "x.yaml",
            "--method",
            "morris",
            "--n",
            "100",
            "--optimal-trajectories",
            "10",
        ]
    )
    assert args.method == "morris"
    assert args.optimal_trajectories == 10


def test_optimal_trajectories_default_none() -> None:
    """Omitting the flag leaves it None — the byte-identical vanilla Morris path."""
    cli = _load_cli()
    args = cli._parse_args(["--config", "x.yaml", "--method", "morris"])
    assert args.optimal_trajectories is None


def test_optimal_trajectories_rejected_with_sobol() -> None:
    """--optimal-trajectories is Morris-only; combining it with --method sobol is a
    fail-loud usage error (argparse error -> SystemExit(2)), not a silent no-op."""
    cli = _load_cli()
    with pytest.raises(SystemExit) as exc:
        cli._parse_args(
            ["--config", "x.yaml", "--method", "sobol", "--optimal-trajectories", "10"]
        )
    assert exc.value.code == 2
