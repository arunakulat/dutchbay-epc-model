"""Coverage tests for ``finance.cashflow_v14_fx._fx_curve``.

This module builds the LKR-per-USD FX curve consumed by the cashflow engine.
Every expected value below is DERIVED from first principles inside the test
(geometric depreciation compounding, list truncation/padding semantics) rather
than asserted against an opaque economic constant. The one reference rate used
(the no-``fx``-block fallback) is read from the SAME config source of truth the
module reads (``analytics.fx.fx_fetch.default_fx_lkr_per_usd``), never a literal.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import pytest

from analytics.fx.fx_fetch import default_fx_lkr_per_usd
from finance.cashflow_v14_fx import _fx_curve


def _geom_curve(start: float, depr: float, years: int) -> List[float]:
    """Reference geometric FX curve: start, start*(1+d), start*(1+d)^2, ..."""
    out: List[float] = []
    cur = float(start)
    for _ in range(years):
        out.append(cur)
        cur *= 1.0 + depr
    return out


def _approx_eq(a: List[float], b: List[float]) -> None:
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# Case 1a: explicit curve list (lines 45-52)
# ---------------------------------------------------------------------------


def test_explicit_curve_truncated_when_longer_than_years() -> None:
    """A curve longer than the project life is truncated to exactly `years`."""
    curve = [10.0, 20.0, 30.0, 40.0]
    result = _fx_curve({"fx": {"curve": curve}}, 2)
    assert result == [10.0, 20.0]


def test_explicit_curve_padded_with_last_rate_when_shorter() -> None:
    """A curve shorter than the project life is padded with its last value."""
    result = _fx_curve({"fx": {"curve_lkr_per_usd": [10.0, 20.0]}}, 4)
    assert result == [10.0, 20.0, 20.0, 20.0]
    # Padding holds the terminal rate flat.
    assert result[-1] == result[1]


def test_explicit_curve_exact_length_returned_unchanged() -> None:
    """A curve exactly `years` long is returned as-is (boundary len == years)."""
    curve = [11.0, 22.0, 33.0]
    result = _fx_curve({"fx": {"curve": curve}}, 3)
    assert result == [11.0, 22.0, 33.0]


def test_years_clamped_to_minimum_one() -> None:
    """years < 1 is clamped to 1 so at least one rate is returned."""
    result = _fx_curve({"fx": {"curve": [50.0]}}, 0)
    assert result == [50.0]


# ---------------------------------------------------------------------------
# Case 1b: parametric start + scalar / pct depreciation (lines 55-97)
# ---------------------------------------------------------------------------


def test_parametric_scalar_decimal_depreciation_compounds() -> None:
    """Scalar `annual_depr` (decimal) compounds geometrically off `start`."""
    start, depr, years = 100.0, 0.02, 3
    result = _fx_curve(
        {"fx": {"start": start, "annual_depr": depr}},
        years,
    )
    _approx_eq(result, _geom_curve(start, depr, years))


def test_parametric_pct_depreciation_via_depr_pct_alias() -> None:
    """`depr_pct` (a percentage) is converted to a decimal before compounding."""
    start, pct, years = 100.0, 5.0, 2
    result = _fx_curve(
        {"fx": {"base": start, "depr_pct": pct}},
        years,
    )
    _approx_eq(result, _geom_curve(start, pct / 100.0, years))


def test_parametric_start_with_no_depreciation_is_flat() -> None:
    """A start value with no depreciation produces a flat curve at `start`."""
    start, years = 250.0, 4
    result = _fx_curve({"fx": {"base_rate": start}}, years)
    assert result == [start] * years


# ---------------------------------------------------------------------------
# Case 1b: parametric per-year depreciation list (lines 71-85)
# ---------------------------------------------------------------------------


def test_parametric_peryear_depr_list_applies_distinct_rates() -> None:
    """Per-year `annual_depr` list applies each year's rate in sequence."""
    start = 100.0
    rates = [0.10, 0.20, 0.05]
    result = _fx_curve(
        {"fx": {"start_lkr_per_usd": start, "annual_depr": rates}},
        3,
    )
    # Derive: level starts at start, append then step by that year's rate.
    expected: List[float] = []
    level = start
    for r in rates:
        expected.append(level)
        level *= 1.0 + r
    _approx_eq(result, expected)


def test_parametric_peryear_depr_list_padded_with_last_rate() -> None:
    """A per-year list shorter than `years` pads with its final rate."""
    start = 100.0
    rates = [0.05]
    years = 3
    result = _fx_curve(
        {"fx": {"start_lkr_per_usd": start, "annual_depr": rates}},
        years,
    )
    # Padded rates -> uniform 0.05 compounding.
    _approx_eq(result, _geom_curve(start, 0.05, years))


def test_parametric_peryear_empty_depr_list_raises() -> None:
    """An empty per-year `annual_depr` list is a schema violation."""
    with pytest.raises(ValueError, match="annual_depr list must not be empty"):
        _fx_curve(
            {"fx": {"start_lkr_per_usd": 100.0, "annual_depr": []}},
            3,
        )


# ---------------------------------------------------------------------------
# Case 1c: malformed fx block (lines 100-104)
# ---------------------------------------------------------------------------


def test_malformed_fx_block_missing_curve_and_start_raises() -> None:
    """An fx dict with neither a curve nor a start value raises ValueError."""
    with pytest.raises(ValueError, match="Invalid FX configuration"):
        _fx_curve({"fx": {"unrelated_key": 1}}, 2)


def test_empty_curve_list_falls_through_to_malformed_raise() -> None:
    """An empty curve list is falsy, so it falls through to the malformed raise."""
    with pytest.raises(ValueError, match="Invalid FX configuration"):
        _fx_curve({"fx": {"curve": []}}, 2)


# ---------------------------------------------------------------------------
# Case 2: legacy nested path reached via case-insensitive key (lines 110-138)
#
# `config.get("fx")` is an EXACT lookup, so a title/upper-case "Fx" key is NOT a
# dict to it (returns None) and Case 1 is skipped. `get_nested`, however, resolves
# keys case-insensitively, so the legacy nested branch picks the block up.
# ---------------------------------------------------------------------------


def test_nested_start_with_pct_depreciation() -> None:
    """Nested path: start + annual_depr_pct compounds after pct->decimal."""
    start, pct, years = 100.0, 5.0, 2
    result = _fx_curve(
        {"Fx": {"start_lkr_per_usd": start, "annual_depr_pct": pct}},
        years,
    )
    _approx_eq(result, _geom_curve(start, pct / 100.0, years))


def test_nested_start_with_scalar_depreciation() -> None:
    """Nested path: start + scalar decimal annual_depr compounds geometrically."""
    start, depr, years = 100.0, 0.10, 3
    result = _fx_curve(
        {"Fx": {"start_lkr_per_usd": start, "annual_depr": depr}},
        years,
    )
    _approx_eq(result, _geom_curve(start, depr, years))


def test_nested_start_with_peryear_depr_list() -> None:
    """Nested path: per-year annual_depr list applies and pads distinct rates."""
    start = 100.0
    rates = [0.10, 0.20]
    years = 3
    result = _fx_curve(
        {"Fx": {"start_lkr_per_usd": start, "annual_depr": rates}},
        years,
    )
    # Padded: last rate (0.20) repeats for the final year.
    padded = rates + [rates[-1]] * (years - len(rates))
    expected: List[float] = []
    level = start
    for r in padded:
        expected.append(level)
        level *= 1.0 + r
    _approx_eq(result, expected)


def test_nested_start_with_no_depreciation_is_flat() -> None:
    """Nested path: start without any depreciation key yields a flat curve."""
    start, years = 320.0, 3
    result = _fx_curve({"Fx": {"start_lkr_per_usd": start}}, years)
    assert result == [start] * years


def test_nested_peryear_empty_depr_list_raises() -> None:
    """Nested path: an empty per-year annual_depr list raises ValueError."""
    with pytest.raises(ValueError, match="annual_depr list must not be empty"):
        _fx_curve(
            {"Fx": {"start_lkr_per_usd": 100.0, "annual_depr": []}},
            3,
        )


# ---------------------------------------------------------------------------
# Final fallback: no fx block at all (lines 140-150)
# ---------------------------------------------------------------------------


def test_no_fx_block_falls_back_to_config_reference_rate() -> None:
    """With no fx block, the curve is a flat config-sourced reference rate.

    The expected rate is read from the SAME source of truth the module reads,
    so no FX literal is hardcoded in this test.
    """
    years = 4
    expected_rate = default_fx_lkr_per_usd()
    result = _fx_curve({}, years)
    assert result == [expected_rate] * years
    # Flat curve: every year is the identical reference rate.
    assert len(set(result)) == 1


def test_non_dict_fx_block_without_nested_start_uses_fallback() -> None:
    """A non-dict `fx` value with no resolvable nested start uses the fallback."""
    years = 2
    expected_rate = default_fx_lkr_per_usd()
    # fx is a list -> not a dict (skip Case 1); get_nested can't descend a list
    # (skip Case 2) -> final config-sourced fallback.
    config: Dict[str, Any] = {"fx": [1, 2, 3]}
    result = _fx_curve(config, years)
    assert result == [expected_rate] * years
