"""Lender-run Monte Carlo settings: no toy fallback, and fixed-debt stress on (#962).

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
    # Fixed-debt stress evaluates the base case before any trial, which would raise first;
    # turn it off here so the failure reaches the per-trial fallback path under test.
    config = _lender()
    config["monte_carlo"]["fixed_debt_stress"] = False
    logging.disable(logging.WARNING)
    try:
        with pytest.raises(RuntimeError, match="toy-metric fallback is disabled"):
            run_monte_carlo_analysis(base_config=config, n_trials=2, seed=1)
    finally:
        logging.disable(logging.NOTSET)


def test_lender_case_runs_fixed_debt_stress() -> None:
    """#962 item 4 (owner ruling 2026-11-15): lender runs test fixed debt service."""
    assert _lender()["monte_carlo"]["fixed_debt_stress"] is True
    logging.disable(logging.WARNING)
    try:
        result = run_monte_carlo_analysis(base_config=_lender(), n_trials=4, seed=42)
    finally:
        logging.disable(logging.NOTSET)
    stress = result.metadata["fixed_debt_stress"]
    assert stress["n"] == 4
    assert stress["covenant"] == pytest.approx(
        _lender()["constraints"]["min_dscr_covenant"]
    )
    assert 0.0 <= stress["breach_probability"] <= 1.0


def test_fixed_debt_stress_is_metadata_only_on_the_lender_case() -> None:
    """Turning the stress on changes no summary, trial or other non-metadata field (#1724)."""
    runs = {}
    logging.disable(logging.WARNING)
    try:
        for on in (True, False):
            config = _lender()
            config["monte_carlo"]["fixed_debt_stress"] = on
            runs[on] = run_monte_carlo_analysis(
                base_config=config, n_trials=4, seed=42
            ).model_dump()
    finally:
        logging.disable(logging.NOTSET)
    meta_on, meta_off = runs[True].pop("metadata"), runs[False].pop("metadata")
    assert runs[True] == runs[False]
    assert "fixed_debt_stress" in meta_on
    assert "fixed_debt_stress" not in meta_off


# Owner ruling 2026-11-15, extended: the fallback-off ruling also covers the 5 US-cent
# variant and the Kalpitiya lender case.
_SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
_FIVE_US_CENT = _SCENARIOS / "dutchbay_lendercase_5usc_fixed_lkr.yaml"
_KALPITIYA = _SCENARIOS / "kalpitiya_lendercase_160m_fitted.yaml"


def _load(path: Path) -> Dict[str, Any]:
    return copy.deepcopy(yaml.safe_load(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "path", [_SCENARIO, _FIVE_US_CENT, _KALPITIYA], ids=lambda p: p.stem
)
def test_every_lender_case_declares_the_fallback_off(path: Path) -> None:
    assert _load(path)["monte_carlo"]["allow_toy_fallback"] is False


def test_healthy_kalpitiya_lender_run_reports_the_fallback_off_and_unused() -> None:
    logging.disable(logging.WARNING)
    try:
        result = run_monte_carlo_analysis(
            base_config=_load(_KALPITIYA), n_trials=4, seed=42
        )
    finally:
        logging.disable(logging.NOTSET)
    assert result.metadata["allow_toy_fallback"] is False
    assert result.metadata["toy_fallback_count"] == 0
    assert result.failed_iterations == 0


def test_five_us_cent_lender_run_stops_instead_of_reporting_toy_trials() -> None:
    """The variant derives CAPEX from its breakdown, so every trial refuses the sampled
    ``capex.usd_total``. With the fallback on (main), every trial was a toy trial; with it
    off, the run stops on the first failed trial.
    """
    logging.disable(logging.WARNING)
    try:
        with pytest.raises(RuntimeError, match="toy-metric fallback is disabled"):
            run_monte_carlo_analysis(
                base_config=_load(_FIVE_US_CENT), n_trials=2, seed=42
            )
    finally:
        logging.disable(logging.NOTSET)
