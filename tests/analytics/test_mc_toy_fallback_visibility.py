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
    minimal = {"monte_carlo": {"parameters": [{"name": "capex", "low": 80, "high": 120}]}}
    result = run_monte_carlo_analysis(base_config=minimal, n_trials=8, seed=1)
    assert result.metadata["toy_fallback_count"] == 8
