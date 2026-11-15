"""The lender case's Monte Carlo never substitutes toy KPIs for a failed trial (#962).

Owner ruling on #962 item 1 (2026-11-15): lender runs turn the toy fallback off. The
lender case declares ``monte_carlo.allow_toy_fallback: false``, so a trial whose full
v14 evaluation raises stops the run instead of reporting fabricated KPIs. A healthy run
is unchanged, because no trial falls back.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

import analytics.mc.engine as mc_engine
from analytics.mc.engine import run_monte_carlo_analysis

_SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def _lender() -> Dict[str, Any]:
    return copy.deepcopy(yaml.safe_load(_SCENARIO.read_text(encoding="utf-8")))


def test_lender_case_declares_the_fallback_off() -> None:
    assert _lender()["monte_carlo"]["allow_toy_fallback"] is False


def test_healthy_lender_run_reports_the_fallback_off_and_unused() -> None:
    logging.disable(logging.WARNING)
    try:
        result = run_monte_carlo_analysis(base_config=_lender(), n_trials=4, seed=42)
    finally:
        logging.disable(logging.NOTSET)
    assert result.metadata["allow_toy_fallback"] is False
    assert result.metadata["toy_fallback_count"] == 0
    assert result.failed_iterations == 0


def test_a_failed_lender_trial_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative control: on main this run substitutes a toy trial and returns."""

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated trial failure")

    monkeypatch.setattr(mc_engine, "evaluate_with_overrides", _boom)
    logging.disable(logging.WARNING)
    try:
        with pytest.raises(RuntimeError, match="toy-metric fallback is disabled"):
            run_monte_carlo_analysis(base_config=_lender(), n_trials=2, seed=1)
    finally:
        logging.disable(logging.NOTSET)
