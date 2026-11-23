"""The Monte Carlo samples FX depreciation from a sourced band (#1898, #924 study O-7).

Before #1898 no committed Monte Carlo block sampled FX depreciation, so every risk run held
the main FX driver fixed. Each scenario now samples the rate its own FX risk runs through:

- the DutchBay lender case (LKR revenue, USD debt) samples ``fx.annual_depr``, the model
  curve's drift;
- Blue Whale wind is LKR funded and keeps its flat reporting rate (owner, 2026-10-28), so it
  samples only the LKR depreciation of its USD opex share,
  ``opex.currency_split.usd_lkr_depreciation_pct`` (owner ruling, 2026-11-22 10:38Z).

These tests check that the engine refuses an unsourced FX depreciation band and a drift
draw a calibrated FX driver would overwrite; that each band is what its cited source gives,
re-derived from the BIS vintage; and that each trial's draw reaches the cash flows: equity
NPV falls strictly as the draw rises, and the full trial outputs differ from a control run
whose band is collapsed onto the base (non-vacuity), which reproduces the deterministic case.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

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
BW_WIND = REPO / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
LENDER_PARAM = "fx.annual_depr"
BW_PARAM = "opex.currency_split.usd_lkr_depreciation_pct"
N_TRIALS = 8
Z95 = 1.959963984540054


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _load(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def _param(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    params: List[Dict[str, Any]] = [
        p for p in cfg["monte_carlo"]["parameters"] if p["name"] == name
    ]
    assert len(params) == 1, f"the scenario samples {name} exactly once"
    return params[0]


def _only(cfg: Dict[str, Any], name: str, low: float, high: float) -> Dict[str, Any]:
    """The scenario sampling ``name`` alone, without the fixed-debt stress."""
    out = copy.deepcopy(cfg)
    out["monte_carlo"]["parameters"] = [dict(_param(out, name), low=low, high=high)]
    out["monte_carlo"].pop("correlation", None)
    out["monte_carlo"]["fixed_debt_stress"] = False
    return out


def _dig(mapping: Any, dotted: str) -> Any:
    for key in dotted.split("."):
        if not isinstance(mapping, dict) or key not in mapping:
            return None
        mapping = mapping[key]
    return mapping


def _run_spying(
    cfg: Dict[str, Any], name: str, monkeypatch: pytest.MonkeyPatch
) -> Tuple[Any, List[float], List[Any]]:
    """Run the engine; record each trial's draw of ``name`` and its ``fx`` override."""
    drawn: List[float] = []
    fx_overrides: List[Any] = []
    real = mc_engine.evaluate_with_overrides

    def spy(*args: Any, **kwargs: Any) -> Any:
        overrides = kwargs.get("overrides") or {}
        value = _dig(overrides, name)
        if value is not None:
            drawn.append(float(value))
            fx_overrides.append(overrides.get("fx"))
        return real(*args, **kwargs)

    monkeypatch.setattr(mc_engine, "evaluate_with_overrides", spy)
    result = MonteCarloEngine(cfg, seed=42).run(n_trials=N_TRIALS)
    return result, drawn, fx_overrides


def _trials_sha256(result: Any) -> str:
    text = json.dumps(result.trials, sort_keys=True, default=repr)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bw_ppp_pct(cfg: Dict[str, Any]) -> float:
    split = cfg["opex"]["currency_split"]
    assert split["usd_lkr_depreciation_pct"] == "relative_ppp"
    lkr = float(split["lkr_escalation_pct"]) / 100.0
    usd = float(split["usd_escalation_pct"]) / 100.0
    return ((1.0 + lkr) / (1.0 + usd) - 1.0) * 100.0


# --- refusals ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,name", [(LENDER, LENDER_PARAM), (BW_WIND, BW_PARAM)], ids=["lender", "bw"]
)
@pytest.mark.parametrize("source", [None, "", "   ", 3])
def test_unsourced_depreciation_band_is_refused(
    path: Path, name: str, source: Any
) -> None:
    cfg = _load(path)
    param = _param(cfg, name)
    if source is None:
        param.pop("source")
    else:
        param["source"] = source
    with pytest.raises(
        MonteCarloConfigError, match="must declare a non-empty 'source'"
    ):
        MonteCarloEngine(cfg, seed=1)


def test_sampled_drift_beside_a_drift_driving_calibrated_fx_is_refused() -> None:
    cfg = _load(LENDER)
    for p in cfg["monte_carlo"]["parameters"]:
        if p["name"] == "fx.start_lkr_per_usd":
            p["distribution"] = "fx_calibrated"
    with pytest.raises(MonteCarloConfigError, match="would be overwritten"):
        MonteCarloEngine(cfg, seed=1)
    cfg["monte_carlo"]["fx_calibration"] = {"drive_drift": False}
    engine = MonteCarloEngine(cfg, seed=1)
    assert LENDER_PARAM in engine._param_names


# --- each band is its source ------------------------------------------------------------


def test_lender_band_is_the_cited_bis_interval() -> None:
    cfg = _load(LENDER)
    param = _param(cfg, LENDER_PARAM)
    assert "long_run_depreciation_band" in param["source"]
    assert param["distribution"] == "normal"
    band = long_run_depreciation_band(resolve_fx_history(cfg))
    assert round(band["low"], 4) == param["low"]
    assert round(band["high"], 4) == param["high"]
    # The band is centred on the scenario's own deterministic drift.
    assert round(band["annual_depr"], 4) == cfg["fx"]["annual_depr"]
    assert param["low"] < cfg["fx"]["annual_depr"] < param["high"]


def test_blue_whale_band_is_ppp_with_the_bis_half_width() -> None:
    cfg = _load(BW_WIND)
    param = _param(cfg, BW_PARAM)
    assert "long_run_depreciation_band" in param["source"]
    assert param["distribution"] == "normal"
    band = long_run_depreciation_band(resolve_fx_history(cfg))
    base = _bw_ppp_pct(cfg)
    half = (1.0 + base / 100.0) * Z95 * band["sigma_annual"]
    half = half / math.sqrt(band["usable_years"]) * 100.0
    assert round(base - half, 4) == param["low"]
    assert round(base + half, 4) == param["high"]
    # The reporting rate stays flat and is not sampled (owner, 2026-10-28 and 2026-11-22).
    assert cfg["fx"]["annual_depr"] == 0.0
    names = [p["name"] for p in cfg["monte_carlo"]["parameters"]]
    assert LENDER_PARAM not in names


def test_band_helper_matches_the_calibrated_drift() -> None:
    from analytics.fx.fx_calibration import calibrate_from_config

    cfg = _load(LENDER)
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


@pytest.mark.parametrize(
    "path,name", [(LENDER, LENDER_PARAM), (BW_WIND, BW_PARAM)], ids=["lender", "bw"]
)
def test_drawn_depreciation_reaches_the_cash_flows(
    path: Path, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _load(path)
    param = _param(cfg, name)
    result, drawn, fx_overrides = _run_spying(
        _only(cfg, name, param["low"], param["high"]), name, monkeypatch
    )
    assert len(drawn) == N_TRIALS
    assert len(set(drawn)) == N_TRIALS, "every trial draws its own depreciation"
    equity_npv = result.trials["equity_npv"]
    assert len(equity_npv) == N_TRIALS and None not in equity_npv
    # More depreciation, lower equity NPV: strictly decreasing, rank for rank.
    order = np.argsort(drawn)
    ranked = [equity_npv[i] for i in order]
    assert all(b < a for a, b in zip(ranked, ranked[1:], strict=False))
    if name == BW_PARAM:
        # The USD share's draw never touches the flat reporting curve.
        assert all(fx is None for fx in fx_overrides)


@pytest.mark.parametrize(
    "path,name", [(LENDER, LENDER_PARAM), (BW_WIND, BW_PARAM)], ids=["lender", "bw"]
)
def test_non_vacuity_control_collapsed_band(
    path: Path, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _load(path)
    param = _param(cfg, name)
    base = float(cfg["fx"]["annual_depr"]) if name == LENDER_PARAM else _bw_ppp_pct(cfg)
    sampled, _, _ = _run_spying(
        _only(cfg, name, param["low"], param["high"]), name, monkeypatch
    )
    control, drawn, _ = _run_spying(_only(cfg, name, base, base), name, monkeypatch)
    # The control draws the base in every trial and reproduces the deterministic case.
    assert drawn and set(drawn) == {base}
    deterministic = evaluate_with_overrides(raw_config=cfg, overrides={})
    assert control.trials["equity_npv"] == pytest.approx(
        [deterministic["equity_npv"]] * N_TRIALS, rel=1e-12
    )
    # The sampled run's full trial outputs differ from the control's.
    assert _trials_sha256(sampled) != _trials_sha256(control)
