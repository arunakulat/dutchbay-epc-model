"""Follow-ups to the USD opex FX drift step (#1578 L-12, after #1730).

Carried from the #1730 reviews (#1578 issuecomment-6897369179 and
issuecomment-6901889800, and issuecomment-6893178345 N-4):

* the shape comparison is held by tests whose drift is not above the base curve in
  every year (three mutants survived: first year only, last year only, rises only);
* a spot-only override beside an explicit curve is not read as a drift;
* a drift stress on a key the curve does not read is refused for every scenario,
  not only those with a USD path;
* the reference keys are gateway-only, so a scenario cannot author them;
* the code fallback ``DEFAULT_ENGINE_PATH_STATUS`` is pinned;
* the calibrated drift driver is held by one real trial, not a constructor flag.

A drift that starts late replaces the USD path from its first drifted year only, the
earlier years keep the own path, and the drift carries on from the own path's level
(owner rulings, 2026-11-16 14:28Z and 14:47Z). That rule is pinned in
``test_fx_drift_late_start_1578.py``; the late-drift test below holds it too.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from finance.capex_price_basis import apply_capex_price_basis
from finance.cashflow_v14 import _prepare_cashflow_context
from finance.cashflow_v14_params import (
    USD_FX_DRIFT_OVERRIDE,
    USD_FX_REFERENCE,
    refuse_authored_usd_fx_reference,
    with_usd_opex_fx_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _cfg(path: Path = WIND) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    # #1899: as the pipeline evaluates it, with the declared capex price date applied.
    return apply_capex_price_basis(data)


def _split(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cast(Dict[str, Any], cfg["opex"]["currency_split"])


def _paths(cfg: Dict[str, Any]) -> tuple[List[float], List[float]]:
    """Return ``(model FX curve, USD opex FX path)`` as the engine resolves them."""
    params, curve = _prepare_cashflow_context(cfg, None, None, None)[:2]
    path = params["opex_usd_fx_path"]
    assert path is not None
    return list(curve), list(path)


def _shape_only(cfg: Dict[str, Any], **fx: Any) -> Dict[str, Any]:
    """Merge ``fx`` without passing overrides, so only the shape comparison decides."""
    out = copy.deepcopy(cfg)
    out["fx"].update(fx)
    result = with_usd_opex_fx_reference(cfg, out)
    assert USD_FX_DRIFT_OVERRIDE not in _split(result)
    return result


def _with_fx(cfg: Dict[str, Any], **fx: Any) -> Dict[str, Any]:
    """Merge ``fx`` as a gateway does, passing the overrides."""
    out = copy.deepcopy(cfg)
    out["fx"].update(fx)
    return with_usd_opex_fx_reference(cfg, out, {"fx": dict(fx)})


# ------------------------------------------------- shape comparison: three mutants


def test_drift_only_in_later_years_replaces_the_path_there() -> None:
    """Flat for eleven operating years, then 5%/yr (kills 'first year only')."""
    base = _cfg()
    years = len(_paths(base)[1])
    drift = [0.0] * 11 + [0.05] * (years + 10)
    curve, path = _paths(_shape_only(base, annual_depr=drift))
    _, own = _paths(base)
    assert curve[0] == curve[10]  # the model curve is still flat in year 11
    first = 11  # the first operating year whose curve departs from the flat base
    assert curve[first] != curve[0]
    assert path[:first] == own[:first]  # the years before it keep the own path
    for i in range(first, years):  # carried on from the own level (2026-11-16 14:47Z)
        want = own[first - 1] * curve[i] / curve[first - 1]
        assert path[i] == pytest.approx(want, rel=1e-12), i
        assert path[i] != own[i], i


def test_drift_only_in_early_years_replaces_the_path_there() -> None:
    """A 5% move in year 1 that reverses in year 2 (kills 'last year only')."""
    base = _cfg()
    years = len(_paths(base)[1])
    drift = [0.05, -0.05 / 1.05] + [0.0] * (years + 10)
    curve, path = _paths(_shape_only(base, annual_depr=drift))
    curve0, own = _paths(base)
    assert curve[-1] == pytest.approx(curve0[-1], rel=1e-12)  # the end is unmoved
    assert curve[0] != pytest.approx(curve0[0], rel=1e-6)
    assert path[0] == curve[0]
    assert path[0] != own[0]


@pytest.mark.parametrize(
    "authored, stressed", [(0.0, -0.02), (0.0317, 0.01)], ids=["flat", "non_flat"]
)
def test_drift_below_the_base_curve_replaces_the_path(
    authored: float, stressed: float
) -> None:
    """A stress below the base curve is a stress too (kills 'rises only')."""
    base = _cfg()
    base["fx"]["annual_depr"] = authored
    curve0, own = _paths(base)
    curve, path = _paths(_shape_only(base, annual_depr=stressed))
    assert all(c < c0 for c, c0 in zip(curve, curve0, strict=True))
    assert path == curve
    assert path != own


# ------------------------------------------- spot-only override beside a curve list


def _explicit_curve(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    spot = float(out["fx"]["start_lkr_per_usd"])
    out["fx"]["curve"] = [spot * 1.01**i for i in range(1, 41)]
    return out


def test_spot_only_override_beside_an_explicit_curve_keeps_the_own_path() -> None:
    """The curve list does not scale with the spot, so its shape moves; it is no drift."""
    base = _explicit_curve(_cfg())
    curve0, own = _paths(base)
    spot0 = float(base["fx"]["start_lkr_per_usd"])
    shocked = _with_fx(base, start_lkr_per_usd=spot0 * 1.1)
    assert USD_FX_REFERENCE in _split(shocked)
    assert USD_FX_DRIFT_OVERRIDE not in _split(shocked)
    curve1, path1 = _paths(shocked)
    assert curve1 == curve0
    for i, (p0, p1) in enumerate(zip(own, path1, strict=True)):
        assert p1 == pytest.approx(p0 * 1.1, rel=1e-12), i


def test_a_moved_explicit_curve_still_replaces_the_own_path() -> None:
    """Control: a different curve list, compared by shape alone, replaces the path."""
    base = _explicit_curve(_cfg())
    spot = float(base["fx"]["start_lkr_per_usd"])
    moved = [spot * 1.04**i for i in range(1, 41)]
    curve1, path1 = _paths(_shape_only(base, curve=moved))
    assert path1 == curve1
    assert path1[0] == pytest.approx(spot * 1.04, rel=1e-12)


# ------------------------------------------------ shadowed stress, any scenario


def test_shadowed_percent_stress_is_refused_without_a_usd_path() -> None:
    """On a scenario with no USD path, fx.annual_depr_pct beside annual_depr is refused."""
    base = _cfg(LENDER)
    split = (base.get("opex") or {}).get("currency_split") or {}
    assert split.get("usd_lkr_depreciation_pct") is None
    merged = copy.deepcopy(base)
    merged["fx"]["annual_depr_pct"] = 3.0
    with pytest.raises(ValueError, match=r"fx\.annual_depr_pct.*fx\.annual_depr"):
        with_usd_opex_fx_reference(base, merged, {"fx": {"annual_depr_pct": 3.0}})
    with pytest.raises(ValueError, match=r"fx\.annual_depr_pct"):
        evaluate_with_overrides(LENDER, {"fx.annual_depr_pct": 3.0})


def test_read_drift_key_without_a_usd_path_is_unchanged() -> None:
    """Control: the key the curve reads passes, and the config comes back as is."""
    base = _cfg(LENDER)
    merged = copy.deepcopy(base)
    merged["fx"]["annual_depr"] = 0.03
    out = with_usd_opex_fx_reference(base, merged, {"fx": {"annual_depr": 0.03}})
    assert out is merged


# ------------------------------------------------- reference keys are gateway-only


@pytest.mark.parametrize(
    "key, value",
    [(USD_FX_REFERENCE, {"start_lkr_per_usd": 300.0}), (USD_FX_DRIFT_OVERRIDE, True)],
)
def test_scenario_cannot_author_a_gateway_key(
    tmp_path: Path, key: str, value: Any
) -> None:
    cfg = _cfg()
    _split(cfg)[key] = value
    authored = tmp_path / "authored.yaml"
    authored.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match=rf"opex\.currency_split\.{key}.*gateways"):
        load_scenario_config(authored)
    with pytest.raises(ValueError, match=rf"<inline>: opex\.currency_split\.{key}"):
        refuse_authored_usd_fx_reference(cfg, "<inline>")


def test_committed_scenarios_and_gateway_output_are_accepted() -> None:
    """A loaded scenario passes; the gateway's own output is not re-checked at load."""
    cfg = load_scenario_config(WIND)
    refuse_authored_usd_fx_reference(cfg, str(WIND))
    stressed = _with_fx(cfg, annual_depr=0.03)
    assert _split(stressed)[USD_FX_DRIFT_OVERRIDE] is True
    assert evaluate_with_overrides(raw_config=stressed, overrides={})


# ------------------------------------------------------------ code fallback pin


def test_engine_path_status_code_fallback_is_pinned() -> None:
    """The fallback matches the committed YAML value, which is the one that runs."""
    from analytics.finance.blue_whale_fx_tenor_screening import (
        DEFAULT_ENGINE_PATH_STATUS,
    )

    conf = yaml.safe_load(
        (REPO_ROOT / "conf" / "blue_whale_fx_tenor_screening.yaml").read_text()
    )
    assert DEFAULT_ENGINE_PATH_STATUS == "delivered_bw5_l12_d2"
    assert conf["engine_path_status"] == DEFAULT_ENGINE_PATH_STATUS


# ------------------------------------------------------- calibrated MC, one trial


def test_calibrated_drift_driver_trial_runs_the_gateway_drift_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One trial reproduces the gateway's result for the same spot and drift draw."""
    from analytics.mc.engine import MonteCarloEngine

    cfg = load_scenario_config(WIND)
    cfg["monte_carlo"] = {
        "parameters": [
            {"name": "fx.start_lkr_per_usd", "distribution": "fx_calibrated"}
        ],
        "fx_calibration": {
            "frequency": "weekly",
            "horizon_years": 1.0,
            "drive_drift": True,
        },
        "allow_toy_fallback": False,
    }
    engine = MonteCarloEngine(cfg, seed=1)
    drawn: List[Dict[str, Any]] = []
    original = engine._apply_fx_calibration

    def _capture(overrides: Dict[str, Any], row: Any) -> Dict[str, Any]:
        out = original(overrides, row)
        drawn.append(copy.deepcopy(out))
        return out

    monkeypatch.setattr(engine, "_apply_fx_calibration", _capture)
    result = engine.run(n_trials=1)

    assert len(drawn) == 1
    fx = drawn[0]["fx"]
    assert fx["annual_depr"] == engine._fx_sampler.drift
    assert fx["annual_depr"] != cfg["fx"]["annual_depr"]
    want = evaluate_with_overrides(
        WIND,
        {
            "fx.start_lkr_per_usd": fx["start_lkr_per_usd"],
            "fx.annual_depr": fx["annual_depr"],
        },
    )
    trial_irr = result.trials["project_irr"][0]
    assert trial_irr == pytest.approx(want["project_irr"], abs=1e-12)
    # Without the drift step the USD share would stay on its own path: a different IRR.
    base = load_scenario_config(WIND)
    own_path = copy.deepcopy(base)
    own_path["fx"]["start_lkr_per_usd"] = fx["start_lkr_per_usd"]
    own_path["fx"]["annual_depr"] = fx["annual_depr"]
    unstepped = evaluate_with_overrides(raw_config=own_path, overrides={})
    assert unstepped["project_irr"] != pytest.approx(trial_irr, abs=1e-9)
