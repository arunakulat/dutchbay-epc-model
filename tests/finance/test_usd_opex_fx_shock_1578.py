"""An FX override reaches a USD opex share that has its own FX path (#1578 L-12).

A scenario may translate the USD share of its opex on its own parametric path
(``opex.currency_split.usd_lkr_depreciation_pct``) while the model FX curve is held flat
as a constant-LKR reporting rate. Before this change an override of ``fx`` (an FX stress
or a Monte Carlo drift draw) moved the model curve but never that path, so the stress
understated the FX risk on the USD share (#1557 DOM-4).

The Python override gateways now record the base ``fx`` block beside the path when an
override moved ``fx`` (``with_usd_opex_fx_reference``). When the override changed the
model curve's shape (its path relative to its own spot), the stressed model curve REPLACES
the USD share's own path, so a drift of x runs the share at x, not at x on top of the
authored rate (owner ruling, 2026-11-15). An override that names a drift key is a stress
whatever its value, even the authored drift, so there is no jump at that boundary (owner
ruling, 2026-11-16). A spot-only or curve-neutral change keeps the own path, which
already anchors on the merged spot. Nothing here names a site: the
fixture is a committed scenario with its inputs moved by the test.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest
import yaml

from analytics import evaluate_scenario as evaluate_scenario_gateway
from analytics.evaluation_v14 import (
    evaluate_scenario_from_dict,
    evaluate_with_overrides,
)
from analytics.scenario_loader import load_scenario_config
from finance.capex_price_basis import apply_capex_price_basis
from finance.cashflow_v14 import _prepare_cashflow_context
from finance.cashflow_v14_params import (
    FX_DRIFT_KEYS,
    USD_FX_DRIFT_OVERRIDE,
    USD_FX_REFERENCE,
    _resolve_opex_currency_split,
    with_usd_opex_fx_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"


def _cfg() -> Dict[str, Any]:
    data = yaml.safe_load(WIND.read_text())
    assert isinstance(data, dict)
    # #1899: as the pipeline evaluates it, with the declared capex price date applied.
    return apply_capex_price_basis(data)


def _split(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cast(Dict[str, Any], cfg["opex"]["currency_split"])


def _paths(cfg: Dict[str, Any]) -> tuple[List[float], List[float]]:
    """Return ``(model FX curve, USD opex FX path)`` as the engine resolves them."""
    ctx = _prepare_cashflow_context(cfg, None, None, None)
    params, curve = ctx[0], ctx[1]
    path = params["opex_usd_fx_path"]
    assert path is not None
    return list(curve), list(path)


def _with_fx(cfg: Dict[str, Any], **fx: Any) -> Dict[str, Any]:
    """Merge ``fx`` overrides as a gateway does, passing them to the helper."""
    out = copy.deepcopy(cfg)
    out["fx"].update(fx)
    return with_usd_opex_fx_reference(cfg, out, {"fx": dict(fx)})


def _with_fx_shape_only(cfg: Dict[str, Any], **fx: Any) -> Dict[str, Any]:
    """The same merge with no overrides passed: only the shape comparison applies."""
    out = copy.deepcopy(cfg)
    out["fx"].update(fx)
    return with_usd_opex_fx_reference(cfg, out)


# --------------------------------------------------------------------------- helper


def test_fixture_has_its_own_usd_path_and_a_flat_model_curve() -> None:
    cfg = _cfg()
    assert _split(cfg)["usd_lkr_depreciation_pct"] is not None
    assert float(cfg["fx"]["annual_depr"]) == 0.0
    assert USD_FX_REFERENCE not in _split(cfg)


def test_helper_leaves_config_alone_when_fx_did_not_change() -> None:
    base = _cfg()
    merged = copy.deepcopy(base)
    merged["opex"]["usd_per_year"] = 600000
    assert with_usd_opex_fx_reference(base, merged) is merged


def test_helper_leaves_config_alone_without_an_own_usd_path() -> None:
    base = _cfg()
    del base["opex"]["currency_split"]["usd_lkr_depreciation_pct"]
    merged = copy.deepcopy(base)
    merged["fx"]["annual_depr"] = 0.05
    assert with_usd_opex_fx_reference(base, merged) is merged

    no_split = _cfg()
    del no_split["opex"]["currency_split"]
    merged = copy.deepcopy(no_split)
    merged["fx"]["annual_depr"] = 0.05
    assert with_usd_opex_fx_reference(no_split, merged) is merged


def test_helper_pins_the_base_fx_block_without_mutating_either_input() -> None:
    base = _cfg()
    base_before = copy.deepcopy(base)
    merged = copy.deepcopy(base)
    merged["fx"]["annual_depr"] = 0.05
    merged_before = copy.deepcopy(merged)

    out = with_usd_opex_fx_reference(base, merged)

    assert out is not merged
    assert _split(out)[USD_FX_REFERENCE] == base["fx"]
    assert _split(out)[USD_FX_REFERENCE] is not base["fx"]
    assert base == base_before
    assert merged == merged_before
    assert out["fx"]["annual_depr"] == 0.05


def test_helper_keeps_a_reference_already_set() -> None:
    base = _cfg()
    merged = copy.deepcopy(base)
    merged["fx"]["annual_depr"] = 0.05
    own = {"start_lkr_per_usd": 300.0, "annual_depr": 0.01}
    _split(merged)[USD_FX_REFERENCE] = own
    assert with_usd_opex_fx_reference(base, merged) is merged


def test_helper_marks_a_drift_override_equal_to_the_authored_drift() -> None:
    """Any drift override is a stress: the authored value still sets the flag."""
    base = _cfg()
    overrides = {"fx": {"annual_depr": float(base["fx"]["annual_depr"])}}
    merged = copy.deepcopy(base)
    merged["fx"].update(overrides["fx"])
    assert merged["fx"] == base["fx"]

    out = with_usd_opex_fx_reference(base, merged, overrides)

    assert out is not merged
    assert _split(out)[USD_FX_REFERENCE] == base["fx"]
    assert _split(out)[USD_FX_DRIFT_OVERRIDE] is True
    assert USD_FX_DRIFT_OVERRIDE not in _split(merged)


_DRIFT_KEYS_LITERAL = [
    "annual_depr",
    "annual_depr_pct",
    "depr_pct",
    "curve",
    "curve_lkr_per_usd",
]


def test_drift_key_set_is_pinned() -> None:
    assert FX_DRIFT_KEYS == frozenset(_DRIFT_KEYS_LITERAL)


def _fx_reading(key: str) -> Dict[str, Any]:
    """A base fx block whose curve reads ``key``, at the wind spot and 0%/yr."""
    spot = float(_cfg()["fx"]["start_lkr_per_usd"])
    if key in ("curve", "curve_lkr_per_usd"):
        return {key: [spot] * 60}
    return {"start_lkr_per_usd": spot, key: 0.0}


@pytest.mark.parametrize("key", _DRIFT_KEYS_LITERAL)
def test_helper_marks_every_drift_key(key: str) -> None:
    base = _cfg()
    base["fx"] = _fx_reading(key)
    value = base["fx"][key]
    out = with_usd_opex_fx_reference(base, copy.deepcopy(base), {"fx": {key: value}})
    assert _split(out)[USD_FX_DRIFT_OVERRIDE] is True


@pytest.mark.parametrize(
    "authored, override, reads",
    [
        # The committed wind block authors annual_depr: 0.0, which the curve reads first.
        ({}, {"annual_depr_pct": 3.0}, "fx.annual_depr"),
        ({}, {"depr_pct": 3.0}, "fx.annual_depr"),
        # An explicit curve list wins over every parametric key.
        ({"curve": [333.79] * 60}, {"annual_depr": 0.03}, "fx.curve"),
        ({"curve_lkr_per_usd": [333.79] * 60}, {"annual_depr_pct": 3.0}, "fx.curve"),
        # annual_depr_pct, when truthy, is read before depr_pct.
        (
            {"annual_depr": None, "annual_depr_pct": 2.0},
            {"depr_pct": 3.0},
            "fx.annual_depr_pct",
        ),
    ],
)
def test_helper_refuses_a_drift_override_the_curve_does_not_read(
    authored: Dict[str, Any], override: Dict[str, Any], reads: str
) -> None:
    """A shadowed drift key would not move the curve, yet would replace the path."""
    base = _cfg()
    base["fx"].update(authored)
    merged = copy.deepcopy(base)
    merged["fx"].update(override)
    with pytest.raises(ValueError, match=reads.replace(".", r"\.")):
        with_usd_opex_fx_reference(base, merged, {"fx": override})


def test_gateway_refuses_a_percent_form_stress_beside_annual_depr() -> None:
    with pytest.raises(ValueError, match=r"fx\.annual_depr_pct"):
        evaluate_with_overrides(WIND, {"fx.annual_depr_pct": 3.0})


def test_percent_form_stress_runs_at_the_stated_drift_when_it_is_read() -> None:
    """Without annual_depr, fx.annual_depr_pct = 3 is the same stress as 3%/yr."""
    base = _cfg()
    del base["fx"]["annual_depr"]
    curve_pct, path_pct = _paths(_with_fx(base, annual_depr_pct=3.0))
    curve_dec, path_dec = _paths(_with_fx(base, annual_depr=0.03))
    assert path_pct == curve_pct
    for i, (a, b) in enumerate(zip(path_pct, path_dec, strict=True)):
        assert a == pytest.approx(b, rel=1e-12), i


def test_helper_does_not_mark_a_spot_or_curve_neutral_override() -> None:
    base = _cfg()
    for fx in ({"start_lkr_per_usd": 340.0}, {"uncertainty_pct": 0.07}):
        merged = copy.deepcopy(base)
        merged["fx"].update(fx)
        out = with_usd_opex_fx_reference(base, merged, {"fx": fx})
        assert USD_FX_REFERENCE in _split(out)
        assert USD_FX_DRIFT_OVERRIDE not in _split(out)
    # Overrides outside ``fx`` leave the config alone.
    merged = copy.deepcopy(base)
    assert (
        with_usd_opex_fx_reference(base, merged, {"opex": {"usd_per_year": 1}})
        is merged
    )


# ------------------------------------------------------------------------- resolver


def test_resolver_returns_a_copy_of_the_reference() -> None:
    cfg = _cfg()
    ref = {"start_lkr_per_usd": 333.79, "annual_depr": 0.0}
    _split(cfg)[USD_FX_REFERENCE] = ref
    split = _resolve_opex_currency_split(cfg)
    assert split is not None
    assert split.usd_fx_reference == ref
    assert split.usd_fx_reference is not ref


def test_resolver_reads_the_drift_override_flag() -> None:
    cfg = _cfg()
    split = _resolve_opex_currency_split(cfg)
    assert split is not None and split.usd_fx_drift_override is False
    _split(cfg)[USD_FX_REFERENCE] = {"start_lkr_per_usd": 333.79, "annual_depr": 0.0}
    _split(cfg)[USD_FX_DRIFT_OVERRIDE] = True
    split = _resolve_opex_currency_split(cfg)
    assert split is not None and split.usd_fx_drift_override is True


@pytest.mark.parametrize(
    "with_reference, flag, message",
    [
        (True, "yes", "must be true or false"),
        (True, 1, "must be true or false"),
        (False, True, "applies only beside usd_fx_reference"),
    ],
)
def test_resolver_refuses_a_malformed_drift_override_flag(
    with_reference: bool, flag: Any, message: str
) -> None:
    cfg = _cfg()
    if with_reference:
        _split(cfg)[USD_FX_REFERENCE] = {
            "start_lkr_per_usd": 333.79,
            "annual_depr": 0.0,
        }
    _split(cfg)[USD_FX_DRIFT_OVERRIDE] = flag
    with pytest.raises(ValueError, match=message):
        _resolve_opex_currency_split(cfg)


def test_resolver_has_no_reference_for_an_authored_scenario() -> None:
    split = _resolve_opex_currency_split(_cfg())
    assert split is not None
    assert split.usd_fx_reference is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda s: s.update({USD_FX_REFERENCE: [333.79]}), "must be an fx mapping"),
        (
            lambda s: s.update({USD_FX_REFERENCE: {"annual_depr": 0.0}}),
            "financial-close spot",
        ),
        (
            lambda s: (
                s.pop("usd_lkr_depreciation_pct"),
                s.update({USD_FX_REFERENCE: {"start_lkr_per_usd": 333.79}}),
            ),
            "applies only when the USD share has its own FX path",
        ),
    ],
)
def test_resolver_refuses_a_malformed_reference(mutate: Any, message: str) -> None:
    cfg = _cfg()
    mutate(_split(cfg))
    with pytest.raises(ValueError, match=message):
        _resolve_opex_currency_split(cfg)


# --------------------------------------------------------------------------- engine


def test_drift_override_replaces_the_own_path_with_the_stressed_curve() -> None:
    base = _cfg()
    curve0, path0 = _paths(base)
    curve1, path1 = _paths(_with_fx(base, annual_depr=0.03))

    assert curve1 != curve0
    assert path1 == curve1
    # Closed form: the financial-close spot advanced at the drawn drift through the
    # construction year and every operating year, not at 2.44% on top of it.
    spot = float(base["fx"]["start_lkr_per_usd"])
    for i, p1 in enumerate(path1):
        assert p1 == pytest.approx(spot * 1.03 ** (1 + i), rel=1e-12), i
    # 3% is above the authored 2.44%/yr PPP rate, so the path ends above the authored
    # one by the rate gap alone, compounded over the construction and operating years.
    assert path1[-1] / path0[-1] == pytest.approx(
        (1.03 / (1.05 / 1.025)) ** len(path0), rel=1e-12
    )


def test_drift_below_the_ppp_rate_lowers_the_usd_path() -> None:
    """A replacement, not an increment: a 1% drift runs the share below its 2.44% path."""
    base = _cfg()
    _, path0 = _paths(base)
    curve1, path1 = _paths(_with_fx(base, annual_depr=0.01))
    assert path1 == curve1
    assert all(p1 < p0 for p1, p0 in zip(path1, path0, strict=True))


def test_per_year_drift_list_replaces_the_own_path() -> None:
    base = _cfg()
    years = len(_paths(base)[1]) + 10
    curve1, path1 = _paths(_with_fx(base, annual_depr=[0.02] * years))
    assert path1 == curve1


def test_spot_and_drift_together_use_the_stressed_curve_once() -> None:
    """A calibrated Monte Carlo draw moves both; the spot enters once, via the curve."""
    base = _cfg()
    spot0 = float(base["fx"]["start_lkr_per_usd"])
    curve1, path1 = _paths(
        _with_fx(base, start_lkr_per_usd=spot0 * 1.1, annual_depr=0.05)
    )
    assert path1 == curve1
    assert path1[0] == pytest.approx(spot0 * 1.1 * 1.05, rel=1e-12)


def test_spot_only_override_keeps_the_own_path_on_the_new_spot() -> None:
    base = _cfg()
    _, path0 = _paths(base)
    spot0 = float(base["fx"]["start_lkr_per_usd"])
    shocked = _with_fx(base, start_lkr_per_usd=spot0 * 1.1)
    assert USD_FX_REFERENCE in _split(shocked)
    _, path1 = _paths(shocked)
    # The path anchors on the merged spot once; the curve's shape is unchanged.
    for i, (p0, p1) in enumerate(zip(path0, path1, strict=True)):
        assert p1 == pytest.approx(p0 * 1.1, rel=1e-12), i


def test_fx_change_that_leaves_the_curve_alone_is_byte_identical() -> None:
    base = _cfg()
    shocked = _with_fx(base, uncertainty_pct=0.07)
    assert USD_FX_REFERENCE in _split(shocked)
    assert _paths(shocked) == _paths(base)


def _non_flat(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    out["fx"]["annual_depr"] = 0.0317
    return out


def test_non_flat_base_curve_spot_only_and_curve_neutral_keep_the_own_path() -> None:
    """The construction offset and the spot normalisation, on a curve that is not flat."""
    base = _non_flat(_cfg())
    _, path0 = _paths(base)
    spot0 = float(base["fx"]["start_lkr_per_usd"])
    _, path_spot = _paths(_with_fx(base, start_lkr_per_usd=spot0 * 1.1))
    for i, (p0, p1) in enumerate(zip(path0, path_spot, strict=True)):
        assert p1 == pytest.approx(p0 * 1.1, rel=1e-12), i
    assert _paths(_with_fx(base, uncertainty_pct=0.07)) == _paths(base)


def test_non_flat_base_curve_drift_override_uses_the_stressed_curve() -> None:
    base = _non_flat(_cfg())
    curve1, path1 = _paths(_with_fx(base, annual_depr=0.05))
    assert path1 == curve1
    spot = float(base["fx"]["start_lkr_per_usd"])
    # One construction period: year 1 is the spot advanced one step at the drawn rate.
    assert path1[0] == pytest.approx(spot * 1.05, rel=1e-12)


def test_drift_flag_path_is_year_aligned_on_a_non_flat_base_curve() -> None:
    """Closed form through the flag branch: no shift of the curve by a year."""
    base = _non_flat(_cfg())
    spot = float(base["fx"]["start_lkr_per_usd"])
    for drift in (0.0317, 0.03):
        out = _with_fx(base, annual_depr=drift)
        assert _split(out)[USD_FX_DRIFT_OVERRIDE] is True
        curve1, path1 = _paths(out)
        assert path1 == curve1
        for i, p1 in enumerate(path1):
            assert p1 == pytest.approx(spot * (1 + drift) ** (1 + i), rel=1e-12), i


def test_shape_branch_alone_replaces_the_path_on_a_drift() -> None:
    """Without overrides passed (no flag), a changed shape still replaces the path."""
    base = _cfg()
    out = _with_fx_shape_only(base, annual_depr=0.03)
    assert USD_FX_DRIFT_OVERRIDE not in _split(out)
    curve1, path1 = _paths(out)
    assert path1 == curve1
    # The comparison tolerance is tight (relative 1e-12): a 1e-9/yr drift is a change
    # of shape and replaces the path, while float noise in a spot rescaling is not.
    near_curve, near_path = _paths(_with_fx_shape_only(base, annual_depr=1e-9))
    assert near_path == near_curve


def test_without_an_own_path_the_reference_is_never_set_and_model_curve_rules() -> None:
    base = _cfg()
    del _split(base)["usd_lkr_depreciation_pct"]
    shocked = _with_fx(base, annual_depr=0.03)
    assert USD_FX_REFERENCE not in _split(shocked)
    ctx = _prepare_cashflow_context(shocked, None, None, None)
    assert ctx[0]["opex_usd_fx_path"] is None


# ------------------------------------------------------------------------- gateways


def _full(overrides: Dict[str, Any]) -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        evaluate_with_overrides(WIND, overrides, return_full_result=True),
    )


def _opex_rows(result: Dict[str, Any]) -> List[float]:
    rows = result["annual_rows"]
    return [float(r["opex_lkr"]) for r in rows]


def test_every_override_gateway_moves_the_usd_opex_under_an_fx_drift() -> None:
    base_rows = _opex_rows(_full({}))
    full = _full({"fx.annual_depr": 0.03})
    shocked_rows = _opex_rows(full)
    assert all(s > b for s, b in zip(shocked_rows, base_rows, strict=True))

    cfg = load_scenario_config(WIND)
    kpis_base = evaluate_scenario_from_dict(cfg, {})
    kpis_dict = evaluate_scenario_from_dict(cfg, {"fx.annual_depr": 0.03})
    assert kpis_dict["project_irr"] == pytest.approx(
        full["kpis"]["project_irr"], abs=1e-12
    )
    assert kpis_dict["project_irr"] < kpis_base["project_irr"]

    kpis_path = evaluate_scenario_gateway.evaluate_with_overrides(
        WIND, {"fx.annual_depr": 0.03}
    )
    assert kpis_path["project_irr"] == pytest.approx(
        full["kpis"]["project_irr"], abs=1e-12
    )


def test_drift_override_at_the_authored_drift_has_no_jump() -> None:
    """Owner ruling 2026-11-16: a 0% override (the model curve's own drift) is a stress.

    It takes the model curve like any other drift, so it sits next to a near-0% drift
    rather than jumping back to the 2.44%/yr own path of the base case.
    """
    base = _full({})
    zero = _full({"fx.annual_depr": 0.0})
    near = _full({"fx.annual_depr": 1e-9})

    zero_rows, near_rows = _opex_rows(zero), _opex_rows(near)
    for i, (z, n) in enumerate(zip(zero_rows, near_rows, strict=True)):
        assert z == pytest.approx(n, rel=1e-7), i
    assert zero["kpis"]["project_irr"] == pytest.approx(
        near["kpis"]["project_irr"], abs=1e-6
    )
    assert zero["kpis"]["equity_irr"] == pytest.approx(
        near["kpis"]["equity_irr"], abs=1e-6
    )
    # Both are off the base case: the base runs the USD share at 2.44%/yr.
    assert zero_rows[-1] < _opex_rows(base)[-1]
    assert zero["kpis"]["project_irr"] > base["kpis"]["project_irr"]

    # The other two gateways agree.
    cfg = load_scenario_config(WIND)
    kpis_dict = evaluate_scenario_from_dict(cfg, {"fx.annual_depr": 0.0})
    kpis_path = evaluate_scenario_gateway.evaluate_with_overrides(
        WIND, {"fx.annual_depr": 0.0}
    )
    for kpis in (kpis_dict, kpis_path):
        assert kpis["project_irr"] == pytest.approx(
            zero["kpis"]["project_irr"], abs=1e-12
        )


def test_drift_override_at_the_authored_drift_uses_the_model_curve() -> None:
    """Scalar or per-year, an override at the authored drift replaces the own path."""
    base = _cfg()
    curve0, path0 = _paths(base)
    years = len(path0) + 10
    for value in (float(base["fx"]["annual_depr"]), [0.0] * years):
        merged = copy.deepcopy(base)
        merged["fx"]["annual_depr"] = value
        out = with_usd_opex_fx_reference(base, merged, {"fx": {"annual_depr": value}})
        curve1, path1 = _paths(out)
        assert curve1 == curve0
        assert path1 == curve1
        assert path1 != path0


def test_gateway_without_fx_overrides_is_byte_identical() -> None:
    base = _full({})
    other = _full({"fx.uncertainty_pct": 0.07})
    assert repr(_opex_rows(other)) == repr(_opex_rows(base))
    assert repr(other["kpis"]) == repr(base["kpis"])


# ------------------------------------------------------------------ calibrated MC


def test_calibrated_drift_driver_runs_beside_an_own_usd_path() -> None:
    """Its nominal drift replaces the own path (no double count), so it is not refused."""
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
    assert engine._fx_drive_drift is True
