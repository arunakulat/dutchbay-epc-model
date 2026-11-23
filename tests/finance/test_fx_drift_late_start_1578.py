"""A drift that starts late replaces the USD opex path from its first drifted year (#1578 L-12).

Owner rulings, 2026-11-16: when an FX drift override departs from the authored curve
only in a later year, the drift replaces the USD opex share's own FX path from that
first drifted year onward, and the years before it keep the own path (14:28Z, "Replace
from first drifted year"). From that year the stressed curve's year-on-year moves carry
on from the level the own path had reached, so the path does not step onto the model
curve (14:47Z, "Carry on from own level"). Before this change the whole path was
replaced, so a drift that started in year 11 also moved years 1 to 10 onto the model
curve.

The first drifted year is the first operating year whose model curve, relative to its
own spot, departs from the authored curve relative to its spot. The rulings already in
force are unchanged and held here as controls: a drift from year 1 (any scalar drift)
replaces the whole path (2026-11-15), and an override that names a drift key but leaves
the curve where it was authored replaces the whole path too, so there is no jump at that
boundary (2026-11-16). Nothing here names a site: the fixture is a committed scenario
with its inputs moved by the test.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from finance.capex_price_basis import apply_capex_price_basis
from finance.cashflow_v14 import _prepare_cashflow_context, build_annual_rows
from finance.cashflow_v14_params import (
    USD_FX_DRIFT_OVERRIDE,
    USD_FX_REFERENCE,
    with_usd_opex_fx_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
HORIZON = 60  # drift entries: comfortably more than construction plus operating years


def _cfg() -> Dict[str, Any]:
    data = yaml.safe_load(WIND.read_text())
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


def _with_fx(cfg: Dict[str, Any], **fx: Any) -> Dict[str, Any]:
    """Merge ``fx`` as a gateway does, passing the overrides (a named drift key)."""
    out = copy.deepcopy(cfg)
    out["fx"].update(fx)
    return with_usd_opex_fx_reference(cfg, out, {"fx": dict(fx)})


def _shape_only(cfg: Dict[str, Any], **fx: Any) -> Dict[str, Any]:
    """Merge ``fx`` without passing overrides, so only the shape comparison decides."""
    out = copy.deepcopy(cfg)
    out["fx"].update(fx)
    return with_usd_opex_fx_reference(cfg, out)


def _construction(cfg: Dict[str, Any]) -> int:
    return int(cfg["fx"].get("construction_periods") or 1)


def _late(
    cfg: Dict[str, Any], first: int, rate: float, authored: float = 0.0
) -> List[float]:
    """A per-year drift equal to ``authored`` until operating year index ``first``.

    The curve's operating year index ``i`` is period ``i + 1`` (one construction
    period), which applies the drift entries up to index ``i``.
    """
    assert _construction(cfg) == 1
    return [authored] * first + [rate] * (HORIZON - first)


def _assert_carried(
    path: List[float], own: List[float], curve: List[float], first: int
) -> None:
    """The own path before ``first``; from it, the curve's moves on the own level."""
    assert first >= 1
    assert path[:first] == own[:first]
    level, anchor = own[first - 1], curve[first - 1]
    for i in range(first, len(path)):
        assert path[i] == pytest.approx(level * curve[i] / anchor, rel=1e-12), i


def _first_departure(curve: List[float], base: List[float]) -> Optional[int]:
    """The first index where two curves on the same spot differ, independently derived."""
    for i, (c, b) in enumerate(zip(curve, base, strict=True)):
        if c != pytest.approx(b, rel=1e-12):
            return i
    return None


# --------------------------------------------------- the ruling, through a named key


@pytest.mark.parametrize("first", [1, 5, 10, 19])
def test_named_late_drift_replaces_the_path_from_its_first_drifted_year(
    first: int,
) -> None:
    base = _cfg()
    curve0, own = _paths(base)
    out = _with_fx(base, annual_depr=_late(base, first, 0.05))
    assert _split(out)[USD_FX_DRIFT_OVERRIDE] is True
    curve, path = _paths(out)
    assert _first_departure(curve, curve0) == first
    _assert_carried(path, own, curve, first)
    assert all(p != o for p, o in zip(path[first:], own[first:], strict=True))
    # Closed form: the 2.44%/yr own path (relative PPP, 1.05 / 1.025) through the
    # construction year and the undrifted years, then 5%/yr on from that level.
    spot = float(base["fx"]["start_lkr_per_usd"])
    ppp = 1.05 / 1.025
    for i in range(first, len(path)):
        want = spot * ppp**first * 1.05 ** (i - first + 1)
        assert path[i] == pytest.approx(want, rel=1e-12), i


@pytest.mark.parametrize("first", [1, 10])
def test_no_step_at_the_first_drifted_year(first: int) -> None:
    """14:47Z: the path moves into its first drifted year by the drift alone."""
    base = _cfg()
    _, own = _paths(base)
    curve, path = _paths(_with_fx(base, annual_depr=_late(base, first, 0.05)))
    assert path[first - 1] == own[first - 1]
    assert path[first] / path[first - 1] == pytest.approx(1.05, rel=1e-12)
    assert curve[first] / curve[first - 1] == pytest.approx(1.05, rel=1e-12)
    # Not onto the model curve: the flat curve sits below the own path's level there.
    assert path[first] != pytest.approx(curve[first], rel=1e-6)
    assert path[first] > curve[first]


@pytest.mark.parametrize("first", [5, 11])
def test_shape_comparison_late_drift_replaces_from_the_same_year(first: int) -> None:
    """Without overrides passed (no flag), the shape comparison gives the same split."""
    base = _cfg()
    curve0, own = _paths(base)
    out = _shape_only(base, annual_depr=_late(base, first, 0.05))
    assert USD_FX_DRIFT_OVERRIDE not in _split(out)
    curve, path = _paths(out)
    assert _first_departure(curve, curve0) == first
    _assert_carried(path, own, curve, first)


def test_late_drift_below_the_base_curve_splits_the_same_way() -> None:
    """A late fall in the rate is a drift too: the split does not depend on the sign."""
    base = _cfg()
    _, own = _paths(base)
    curve, path = _paths(_with_fx(base, annual_depr=_late(base, 8, -0.02)))
    _assert_carried(path, own, curve, 8)


def test_late_drift_on_a_non_flat_authored_curve_departs_where_the_rate_changes() -> (
    None
):
    """Authored at 3.17%/yr: an override at 3.17% for six years, then 5%, departs in year 7."""
    base = _cfg()
    base["fx"]["annual_depr"] = 0.0317
    curve0, own = _paths(base)
    curve, path = _paths(
        _with_fx(base, annual_depr=_late(base, 6, 0.05, authored=0.0317))
    )
    assert _first_departure(curve, curve0) == 6
    assert curve[:6] == pytest.approx(curve0[:6], rel=1e-12)
    _assert_carried(path, own, curve, 6)


def test_spot_with_a_late_drift_keeps_the_own_path_on_the_new_spot_until_it_drifts() -> (
    None
):
    """The departure is read relative to each curve's own spot, so a spot move is no drift."""
    base = _cfg()
    _, own = _paths(base)
    spot0 = float(base["fx"]["start_lkr_per_usd"])
    out = _with_fx(
        base, start_lkr_per_usd=spot0 * 1.1, annual_depr=_late(base, 7, 0.04)
    )
    curve, path = _paths(out)
    for i in range(7):
        assert path[i] == pytest.approx(own[i] * 1.1, rel=1e-12), i
    for i in range(7, len(path)):
        assert path[i] == pytest.approx(path[6] * curve[i] / curve[6], rel=1e-12), i


def test_explicit_curve_moved_from_a_later_year_replaces_from_there() -> None:
    """An explicit curve list that matches the authored list for nine years, then moves."""
    base = _cfg()
    spot = float(base["fx"]["start_lkr_per_usd"])
    base["fx"]["curve"] = [spot * 1.01**i for i in range(1, 41)]
    _, own = _paths(base)
    moved = list(base["fx"]["curve"])
    moved[9:] = [v * 1.2 for v in moved[9:]]
    curve, path = _paths(_with_fx(base, curve=moved))
    _assert_carried(path, own, curve, 9)


# ------------------------------------------------- the earlier rulings, as controls


def test_a_drift_from_the_first_year_still_replaces_the_whole_path() -> None:
    """2026-11-15: a scalar drift moves every year, so year 1 is the first drifted year."""
    base = _cfg()
    curve, path = _paths(_with_fx(base, annual_depr=0.03))
    assert path == curve
    curve, path = _paths(_with_fx(base, annual_depr=_late(base, 0, 0.05)))
    assert path == curve


@pytest.mark.parametrize("value", [0.0, [0.0] * HORIZON], ids=["scalar", "per_year"])
def test_named_drift_at_the_authored_curve_still_replaces_the_whole_path(
    value: Any,
) -> None:
    """2026-11-16: a named drift key is a stress whatever its value, so no jump back."""
    base = _cfg()
    curve0, _ = _paths(base)
    curve, path = _paths(_with_fx(base, annual_depr=value))
    assert curve == curve0
    assert path == curve


def test_shape_comparison_with_no_departure_keeps_the_own_path() -> None:
    """Without a named key, an unmoved curve is no stress: the own path stays whole."""
    base = _cfg()
    _, own = _paths(base)
    out = _shape_only(base, annual_depr=[0.0] * HORIZON)
    assert USD_FX_REFERENCE in _split(out)
    assert _paths(out)[1] == own


def test_authored_scenario_is_untouched() -> None:
    base = _cfg()
    assert USD_FX_REFERENCE not in _split(base)
    curve, path = _paths(base)
    assert path != curve  # the own PPP path, not the flat model curve


# ------------------------------------------------------------------ end to end


def test_engine_rows_before_the_first_drifted_year_are_the_base_rows() -> None:
    """Every annual figure before the first drifted year is the unstressed base's."""
    base = _cfg()
    first = 10
    rows0 = build_annual_rows(copy.deepcopy(base))
    rows = build_annual_rows(_with_fx(base, annual_depr=_late(base, first, 0.05)))
    assert len(rows) == len(rows0)
    for i in range(first):
        assert rows[i] == rows0[i], i
    assert rows[first] != rows0[first]


def _late_curve(cfg: Dict[str, Any], first: int, rate: float) -> List[float]:
    """An explicit operating curve: flat at the spot until index ``first``, then drifting.

    The strict gateways accept a drift stress as a scalar or as an explicit curve, not as
    a per-year ``annual_depr`` list, so this is the late drift a gateway caller can send.
    """
    spot = float(cfg["fx"]["start_lkr_per_usd"])
    return [spot] * first + [
        spot * (1 + rate) ** k for k in range(1, HORIZON - first + 1)
    ]


def test_gateway_late_curve_moves_only_the_drifted_years() -> None:
    """Through the override gateway: the result moves, via the years from the first drift."""
    first = 11
    late = _late_curve(_cfg(), first, 0.05)
    base = _cfg()
    curve0, own = _paths(base)
    curve, path = _paths(_with_fx(base, curve=late))
    assert curve[:first] == curve0[:first]
    _assert_carried(path, own, curve, first)
    unstressed = evaluate_with_overrides(WIND, {})
    stressed = evaluate_with_overrides(WIND, {"fx.curve": late})
    assert stressed["project_irr"] < unstressed["project_irr"]
