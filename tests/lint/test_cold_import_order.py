"""Standalone (cold) import-order regression.

A green test suite does NOT prove the absence of circular imports — the suite
imports modules in an order that can mask them (#233). These checks import the
module FIRST in a fresh interpreter, which is where module-load cycles bite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cold_import(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )


def test_equity_distribution_hydra_cold_import() -> None:
    """`import finance.equity_distribution_v14_hydra` must succeed standalone.

    It used to fail with a partial-init ImportError: importing it pulled in the
    analytics package, which (via the pipeline) imported back into this module.
    The back-edge in analytics.pipeline_v14_enhanced is now a lazy import.
    """
    result = _cold_import("finance.equity_distribution_v14_hydra")
    assert result.returncode == 0, f"cold import failed:\n{result.stderr}"


def test_cashflow_v14_cold_import() -> None:
    """`import finance.cashflow_v14` must succeed standalone.

    Same class as the equity case: cashflow_v14 imports analytics.config_schema,
    which pulls in the analytics package -> pipeline_v14_enhanced, which imported
    `build_annual_rows` back from cashflow_v14 mid-init. That back-edge is now a
    lazy import.
    """
    result = _cold_import("finance.cashflow_v14")
    assert result.returncode == 0, f"cold import failed:\n{result.stderr}"


def test_casper_payload_cold_import_stays_off_the_mc_engine() -> None:
    """`import analytics.casper.casper_payload` must not load the MC engine.

    The CASPER payload module reuses the engine's covenant-floor resolver via the
    deliberately dependency-light `analytics.mc.covenant` (#639) precisely so it
    does NOT pull `analytics.mc.engine` (and its full MC stack) into its import
    chain; the engine merely re-exports the resolvers (MOVE -> SHIM). This guard
    pins that boundary: if `analytics.mc.covenant` (or `analytics.mc.__init__`,
    which is lazy per PEP 562) ever grows an engine/exports import, this fails.
    """
    probe = (
        "import sys; import analytics.casper.casper_payload; "
        "assert 'analytics.mc.covenant' in sys.modules, 'covenant not imported'; "
        "leaked = [m for m in ('analytics.mc.engine', 'analytics.mc.exports') "
        "if m in sys.modules]; "
        "assert not leaked, f'MC engine leaked into casper_payload chain: {leaked}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"cold-import boundary probe failed:\n{result.stderr}"
