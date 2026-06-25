"""Regression: toy-fallback usage must be visible, not silent (monte-carlo-6).

The MC engine substitutes deterministic toy KPIs when a trial's real v14
evaluation raises. That is a sanctioned smoke-test mechanism, but it used to be
silent (logged at DEBUG, indistinguishable in the result), so an all-failing
production run reported success_rate=100% with fabricated KPIs. The engine now
tags toy trials and aggregate_trials surfaces ``metadata['toy_fallback_count']``,
so a degenerate run is detectable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.mc.engine import run_monte_carlo_analysis

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_canonical_scenario_uses_no_toy_fallback() -> None:
    """A real run on the canonical scenario must not touch the toy path."""
    base = yaml.safe_load(LENDER.read_text(encoding="utf-8"))
    result = run_monte_carlo_analysis(base_config=base, n_trials=12, seed=42)
    assert result.metadata["toy_fallback_count"] == 0
    assert result.failed_iterations == 0
    assert result.success_rate() == 100.0


def test_degenerate_all_toy_run_is_detectable() -> None:
    """A config that can't satisfy the v14 schema falls entirely to toy — and
    that is now surfaced via toy_fallback_count == n_trials, instead of being a
    silent success."""
    # The param name must RESOLVE (capex.usd_total exists) so the engine doesn't reject it
    # up-front (round-3 guard); the rest of the config is schema-incomplete, so every trial's
    # real v14 eval fails and falls to toy — which is what this test detects.
    minimal = {
        "capex": {"usd_total": 100.0},
        "monte_carlo": {"parameters": [{"name": "capex.usd_total", "low": 80, "high": 120}]},
    }
    result = run_monte_carlo_analysis(base_config=minimal, n_trials=8, seed=1)
    assert result.metadata["toy_fallback_count"] == 8


# --------------------------------------------------------------------------- #
# CLI status no longer hardcoded "success" (Wave-2 fix)
# --------------------------------------------------------------------------- #
from analytics.cli.cli_monte_carlo_hydra import _derive_run_status  # noqa: E402


def test_cli_status_degenerate_when_all_toy() -> None:
    """All trials toy (no real eval) -> degenerate, never a clean success."""
    assert _derive_run_status(iterations=200, failed_iterations=0, toy_fallback_count=200) == "degenerate"


def test_cli_status_degraded_when_some_toy_or_failed() -> None:
    assert _derive_run_status(iterations=200, failed_iterations=0, toy_fallback_count=5) == "degraded"
    assert _derive_run_status(iterations=200, failed_iterations=3, toy_fallback_count=0) == "degraded"


def test_cli_status_success_only_when_all_real() -> None:
    assert _derive_run_status(iterations=200, failed_iterations=0, toy_fallback_count=0) == "success"


def test_mc_warns_on_non_resolving_parameter_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A monte_carlo.parameters name that does not resolve to a real config path is a likely
    dead key -> trials fall to the toy metric and the risk distribution is degenerate. The MC
    engine now WARNS (round-3 fix), so the previously-silent degeneracy is visible. (Not a
    hard raise: non-dotted aliases are an accepted legacy input that the toy_fallback_count
    already surfaces.)"""
    import logging

    from analytics.mc.engine import MonteCarloEngine

    cfg = {
        "fx": {"start_lkr_per_usd": 333.79},
        "monte_carlo": {"parameters": [{"name": "not.a.real.key", "low": 0.1, "high": 0.2}]},
    }
    with caplog.at_level(logging.WARNING, logger="analytics.mc.engine"):
        MonteCarloEngine(base_config=cfg)  # constructs (no raise)
    assert "does not resolve" in caplog.text
