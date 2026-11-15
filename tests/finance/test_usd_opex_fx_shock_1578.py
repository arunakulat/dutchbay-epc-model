"""An FX override reaches a USD opex share that has its own FX path (#1578 L-12).

A scenario may translate the USD share of its opex on its own parametric path
(``opex.currency_split.usd_lkr_depreciation_pct``) while the model FX curve is held flat
as a constant-LKR reporting rate. Before this change an override of ``fx`` (an FX stress
or a Monte Carlo drift draw) moved the model curve but never that path, so the stress
understated the FX risk on the USD share (#1557 DOM-4).

Every override gateway now records the base ``fx`` block beside the path when an
override moved ``fx`` (``with_usd_opex_fx_reference``). The engine then moves the path by
the model curve's per-year ratio to the reference curve, each relative to its own spot,
because the path already anchors on the merged spot. Nothing here names a site: the
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
from finance.cashflow_v14 import _prepare_cashflow_context
from finance.cashflow_v14_params import (
    USD_FX_REFERENCE,
    _resolve_opex_currency_split,
    with_usd_opex_fx_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"


def _cfg() -> Dict[str, Any]:
    data = yaml.safe_load(WIND.read_text())
    assert isinstance(data, dict)
    return data


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


# ------------------------------------------------------------------------- resolver


def test_resolver_returns_a_copy_of_the_reference() -> None:
    cfg = _cfg()
    ref = {"start_lkr_per_usd": 333.79, "annual_depr": 0.0}
    _split(cfg)[USD_FX_REFERENCE] = ref
    split = _resolve_opex_currency_split(cfg)
    assert split is not None
    assert split.usd_fx_reference == ref
    assert split.usd_fx_reference is not ref


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


def test_drift_override_moves_the_usd_path_by_the_model_curve_ratio() -> None:
    base = _cfg()
    curve0, path0 = _paths(base)
    curve1, path1 = _paths(_with_fx(base, annual_depr=0.03))

    spot = float(base["fx"]["start_lkr_per_usd"])
    assert curve1 != curve0
    for i, (p0, p1) in enumerate(zip(path0, path1, strict=True)):
        expected = p0 * (curve1[i] / spot) / (curve0[i] / spot)
        assert p1 == pytest.approx(expected, rel=1e-12), i
    # A flat base curve, so the ratio is the drawn drift through construction.
    assert path1[-1] / path0[-1] == pytest.approx(curve1[-1] / curve0[-1], rel=1e-12)
    assert path1[0] > path0[0]


def test_per_year_drift_list_reaches_the_usd_path() -> None:
    base = _cfg()
    years = len(_paths(base)[1]) + 10
    _, path0 = _paths(base)
    curve1, path1 = _paths(_with_fx(base, annual_depr=[0.02] * years))
    curve0, _ = _paths(base)
    for i in range(len(path0)):
        assert path1[i] == pytest.approx(path0[i] * curve1[i] / curve0[i], rel=1e-12), i


def test_spot_only_override_is_not_counted_twice() -> None:
    base = _cfg()
    _, path0 = _paths(base)
    spot0 = float(base["fx"]["start_lkr_per_usd"])
    shocked = _with_fx(base, start_lkr_per_usd=spot0 * 1.1)
    assert USD_FX_REFERENCE in _split(shocked)
    _, path1 = _paths(shocked)
    # The path anchors on the merged spot once; the spot-normalised ratio is 1.
    for i, (p0, p1) in enumerate(zip(path0, path1, strict=True)):
        assert p1 == pytest.approx(p0 * 1.1, rel=1e-12), i


def test_fx_change_that_leaves_the_curve_alone_is_byte_identical() -> None:
    base = _cfg()
    shocked = _with_fx(base, uncertainty_pct=0.07)
    assert USD_FX_REFERENCE in _split(shocked)
    assert _paths(shocked) == _paths(base)


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


def test_gateway_without_fx_overrides_is_byte_identical() -> None:
    base = _full({})
    other = _full({"fx.uncertainty_pct": 0.07})
    assert repr(_opex_rows(other)) == repr(_opex_rows(base))
    assert repr(other["kpis"]) == repr(base["kpis"])
