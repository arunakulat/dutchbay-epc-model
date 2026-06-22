"""Edge/error-path coverage for the api serialisation helpers.

These exercise the defensive branches of the pure helpers in api/pipeline_api.py
(override merging, lenient float coercion, capacity fallbacks, capex/AEP
extraction guards) plus the sensitivity adapter's path-traversal rejection — the
paths the happy-path API tests don't reach.
"""

from __future__ import annotations

import pytest

from api.pipeline_api import (
    _apply_overrides,
    _at,
    _capacity_mw,
    _extract_aep,
    _extract_cost,
    _f,
)


# --------------------------------------------------------------------------- #
# _apply_overrides
# --------------------------------------------------------------------------- #
def test_apply_overrides_creates_missing_nested_dicts() -> None:
    out = _apply_overrides({}, {"a.b.c": 7})
    assert out == {"a": {"b": {"c": 7}}}


def test_apply_overrides_replaces_non_dict_intermediate() -> None:
    # intermediate `a` is a scalar -> must be replaced with a dict to descend.
    out = _apply_overrides({"a": 5}, {"a.b": 9})
    assert out == {"a": {"b": 9}}


def test_apply_overrides_does_not_mutate_input() -> None:
    src = {"x": {"y": 1}}
    _apply_overrides(src, {"x.y": 2})
    assert src == {"x": {"y": 1}}  # deep-copied


# --------------------------------------------------------------------------- #
# _f / _at lenient coercion
# --------------------------------------------------------------------------- #
def test_f_returns_none_for_unparseable() -> None:
    assert _f("not-a-number") is None
    assert _f(None) is None
    assert _f([1, 2]) is None


def test_f_coerces_numeric_like() -> None:
    assert _f("3.5") == pytest.approx(3.5)
    assert _f(4) == pytest.approx(4.0)


def test_at_handles_out_of_range_and_non_sequence() -> None:
    assert _at([1.0, 2.0], 5) is None
    assert _at("nope", 0) is None
    assert _at([10.0], 0) == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# _capacity_mw fallbacks
# --------------------------------------------------------------------------- #
def test_capacity_mw_from_project() -> None:
    assert _capacity_mw({"project": {"capacity_mw": 150}}) == pytest.approx(150.0)


def test_capacity_mw_from_turbine_total() -> None:
    cfg = {"resource": {"turbines": {"total_capacity_mw": 200}}}
    assert _capacity_mw(cfg) == pytest.approx(200.0)


def test_capacity_mw_from_count_times_rated() -> None:
    cfg = {"resource": {"turbines": {"count": 10, "rated_power_mw": 5}}}
    assert _capacity_mw(cfg) == pytest.approx(50.0)


def test_capacity_mw_defaults_zero() -> None:
    assert _capacity_mw({}) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# _extract_cost guards
# --------------------------------------------------------------------------- #
def test_extract_cost_empty_config_returns_blank_block() -> None:
    # _extract_capex_usd({}) raises -> the except returns an empty CostBlock.
    block = _extract_cost({})
    assert block.capex_total_usd is None


def test_extract_cost_zero_capacity_keeps_capex_only() -> None:
    block = _extract_cost({"finance": {"capex_total_usd": 100e6}})
    assert block.capex_total_usd == pytest.approx(100e6)
    assert block.capex_per_kw_usd is None  # no capacity -> no $/kW banner


def test_extract_cost_full_block_has_benchmark() -> None:
    cfg = {"finance": {"capex_total_usd": 100e6}, "project": {"capacity_mw": 50}}
    block = _extract_cost(cfg)
    assert block.capex_total_usd == pytest.approx(100e6)
    assert block.capex_per_kw_usd is not None  # 100e6 / 50_000 kW


# --------------------------------------------------------------------------- #
# _extract_aep path guard
# --------------------------------------------------------------------------- #
def test_extract_aep_unsafe_summary_path_yields_empty() -> None:
    # A traversal path is confined away -> summary is {} -> all fields None.
    cfg = {"resource": {"aep_summary_path": "../../../../etc/passwd"}}
    block = _extract_aep(cfg)
    assert block.net_p50_gwh is None
    assert block.net_p90_gwh is None


def test_extract_aep_reads_inline_wind_when_no_summary() -> None:
    cfg = {"resource": {"wind": {"aep_gwh": 470.0, "capacity_factor": 0.34}}}
    block = _extract_aep(cfg)
    assert block.net_p50_gwh == pytest.approx(470.0)
    assert block.capacity_factor == pytest.approx(0.34)


# --------------------------------------------------------------------------- #
# sensitivity adapter — path traversal is rejected loudly (HTTP 400)
# --------------------------------------------------------------------------- #
def test_run_tornado_rejects_unsafe_config_path() -> None:
    fastapi = pytest.importorskip("fastapi")
    from api.sensitivity_api import SensitivityInput, run_tornado

    payload = SensitivityInput(
        config_path="../../../../etc/passwd",
        parameters=[],
    )
    with pytest.raises(fastapi.HTTPException) as exc:
        run_tornado(payload)
    assert exc.value.status_code == 400
