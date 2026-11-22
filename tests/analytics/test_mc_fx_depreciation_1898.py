"""The Monte Carlo samples FX depreciation from a sourced band (#1898, #924 study O-7).

Before #1898 no committed Monte Carlo block sampled ``fx.annual_depr``, so every risk run
held the main driver of an LKR-revenue project with USD debt fixed. These tests check that:

- the engine refuses an FX depreciation band without a ``source``, and refuses sampling
  ``fx.annual_depr`` beside a calibrated FX driver that also sets it;
- the lender case's band is what its cited source gives (re-derived from the BIS vintage);
- each trial's drawn depreciation reaches the cash flows: equity NPV falls strictly as the
  draw rises, and the full trial outputs differ from a control run whose band is collapsed
  onto the base value (non-vacuity), which in turn reproduces the deterministic case.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List

import numpy as np
import pytest
import yaml

import analytics.mc.engine as mc_engine
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.fx.fx_calibration import long_run_depreciation_band
from analytics.fx.fx_history import resolve_fx_history
from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine

REPO = Path(__file__).resolve().parents[2]
LENDER = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
N_TRIALS = 8


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _lender() -> Dict[str, Any]:
    data: Dict[str, Any] = yaml.safe_load(LENDER.read_text(encoding="utf-8"))
    return data


def _depr_param(cfg: Dict[str, Any]) -> Dict[str, Any]:
    params: List[Dict[str, Any]] = [
        p for p in cfg["monte_carlo"]["parameters"] if p["name"] == "fx.annual_depr"
    ]
    assert len(params) == 1, "the lender case samples fx.annual_depr exactly once"
    return params[0]


def _only_depr(cfg: Dict[str, Any], low: float, high: float) -> Dict[str, Any]:
    """The lender case sampling fx.annual_depr alone, without the fixed-debt stress."""
    out = copy.deepcopy(cfg)
    param = dict(_depr_param(out), low=low, high=high)
    out["monte_carlo"]["parameters"] = [param]
    out["monte_carlo"].pop("correlation", None)
    out["monte_carlo"]["fixed_debt_stress"] = False
    return out


def _run_spying(
    cfg: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, List[float]]:
    """Run the engine and record the fx.annual_depr each trial was evaluated with."""
    drawn: List[float] = []
    real = mc_engine.evaluate_with_overrides

    def spy(*args: Any, **kwargs: Any) -> Any:
        overrides = kwargs.get("overrides") or {}
        fx = overrides.get("fx") if isinstance(overrides, dict) else None
        if isinstance(fx, dict) and "annual_depr" in fx:
            drawn.append(float(fx["annual_depr"]))
        return real(*args, **kwargs)

    monkeypatch.setattr(mc_engine, "evaluate_with_overrides", spy)
    result = MonteCarloEngine(cfg, seed=42).run(n_trials=N_TRIALS)
    return result, drawn


def _trials_sha256(result: Any) -> str:
    text = json.dumps(result.trials, sort_keys=True, default=repr)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- refusals ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", [None, "", "   ", 3])
def test_unsourced_depreciation_band_is_refused(source: Any) -> None:
    cfg = _lender()
    param = _depr_param(cfg)
    if source is None:
        param.pop("source")
    else:
        param["source"] = source
    with pytest.raises(
        MonteCarloConfigError, match="must declare a non-empty 'source'"
    ):
        MonteCarloEngine(cfg, seed=1)


def test_unsourced_usd_opex_depreciation_band_is_refused() -> None:
    cfg = _lender()
    cfg["monte_carlo"]["parameters"].append(
        {
            "name": "opex.currency_split.usd_lkr_depreciation_pct",
            "low": 0.0,
            "high": 5.0,
            "distribution": "uniform",
        }
    )
    with pytest.raises(
        MonteCarloConfigError, match="must declare a non-empty 'source'"
    ):
        MonteCarloEngine(cfg, seed=1)


def test_sampled_drift_beside_a_drift_driving_calibrated_fx_is_refused() -> None:
    cfg = _lender()
    for p in cfg["monte_carlo"]["parameters"]:
        if p["name"] == "fx.start_lkr_per_usd":
            p["distribution"] = "fx_calibrated"
    with pytest.raises(MonteCarloConfigError, match="would be overwritten"):
        MonteCarloEngine(cfg, seed=1)
    cfg["monte_carlo"]["fx_calibration"] = {"drive_drift": False}
    engine = MonteCarloEngine(cfg, seed=1)
    assert "fx.annual_depr" in engine._param_names


# --- the band is its source -------------------------------------------------------------


def test_lender_band_is_the_cited_bis_interval() -> None:
    cfg = _lender()
    param = _depr_param(cfg)
    assert "long_run_depreciation_band" in param["source"]
    assert param["distribution"] == "normal"
    band = long_run_depreciation_band(resolve_fx_history(cfg))
    assert round(band["low"], 4) == param["low"]
    assert round(band["high"], 4) == param["high"]
    # The band is centred on the scenario's own deterministic drift.
    assert round(band["annual_depr"], 4) == cfg["fx"]["annual_depr"]
    assert param["low"] < cfg["fx"]["annual_depr"] < param["high"]


def test_band_helper_matches_the_calibrated_drift() -> None:
    from analytics.fx.fx_calibration import calibrate_from_config

    cfg = _lender()
    series = resolve_fx_history(cfg)
    band = long_run_depreciation_band(series)
    calibrated = calibrate_from_config(cfg, pinned_spot=cfg["fx"]["start_lkr_per_usd"])
    assert band["annual_depr"] == pytest.approx(calibrated.annual_depr, abs=1e-12)
    assert band["low"] < band["annual_depr"] < band["high"]
    assert band["high"] - band["annual_depr"] == pytest.approx(
        band["annual_depr"] - band["low"], abs=1e-12
    )
    wider = long_run_depreciation_band(series, z=3.0)
    assert wider["low"] < band["low"] and wider["high"] > band["high"]
    with pytest.raises(ValueError, match="z must be > 0"):
        long_run_depreciation_band(series, z=0.0)


# --- the draw reaches the cash flows ----------------------------------------------------


def test_drawn_depreciation_reaches_the_cash_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _lender()
    param = _depr_param(cfg)
    result, drawn = _run_spying(
        _only_depr(cfg, param["low"], param["high"]), monkeypatch
    )
    assert len(drawn) == N_TRIALS
    assert len(set(drawn)) == N_TRIALS, "every trial draws its own depreciation"
    equity_npv = result.trials["equity_npv"]
    assert len(equity_npv) == N_TRIALS and None not in equity_npv
    # More depreciation, less USD value of LKR revenue: strictly decreasing, rank for rank.
    order = np.argsort(drawn)
    ranked = [equity_npv[i] for i in order]
    assert all(b < a for a, b in zip(ranked, ranked[1:], strict=False))


def test_non_vacuity_control_collapsed_band(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _lender()
    param = _depr_param(cfg)
    base = float(cfg["fx"]["annual_depr"])
    sampled, _ = _run_spying(_only_depr(cfg, param["low"], param["high"]), monkeypatch)
    control, drawn = _run_spying(_only_depr(cfg, base, base), monkeypatch)
    # The control draws the base value in every trial and reproduces the deterministic case.
    assert drawn and set(drawn) == {base}
    deterministic = evaluate_with_overrides(raw_config=cfg, overrides={})
    assert set(control.trials["equity_npv"]) == {deterministic["equity_npv"]}
    # The sampled run's full trial outputs differ from the control's.
    assert _trials_sha256(sampled) != _trials_sha256(control)
