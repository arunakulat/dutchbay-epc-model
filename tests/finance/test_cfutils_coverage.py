"""Coverage tests for ``finance.cashflow_v14_utils``.

These are the small, defensive config-coercion / nested-lookup helpers the
cashflow engine uses to read heterogeneous (canonical lower-case vs. hand-authored
title-case) scenario dicts. The module is already ~91% covered by the wider suite;
this file pins the remaining branches — specifically the ``except`` fall-throughs
in ``as_float`` / ``as_int`` / ``as_float_or_none`` (lines 12-13, 22-23, 76-77),
which only fire on non-coercible inputs.

Every expectation is derived from first principles (Python's own ``float``/``int``
semantics, exact dict-navigation rules, the documented percent-vs-decimal pivot at
1.0). No economic magic number is asserted.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

import pytest

from finance.cashflow_v14_utils import (
    CAPACITY_FACTOR_PATHS,
    CAPACITY_MW_PATHS,
    _as_float_or_none,
    _pct_to_decimal,
    _resolve_first,
    as_float,
    as_float_or_none,
    as_int,
    as_int_or_none,
    get_nested,
    pct_to_decimal,
    resolve_first,
)

# ---------------------------------------------------------------------------
# A small object whose float()/int() raise TypeError, to drive the except
# branches deterministically (lines 12-13, 22-23, 76-77).
# ---------------------------------------------------------------------------


class _Uncoercible:
    """An object that supports neither float() nor int()."""


# ---------------------------------------------------------------------------
# as_float (lines 6-13)
# ---------------------------------------------------------------------------


def test_as_float_none_returns_default() -> None:
    """None short-circuits to the supplied default (line 8-9)."""
    sentinel = 1.5
    assert as_float(None, sentinel) == sentinel
    # Default itself defaults to None.
    assert as_float(None) is None


def test_as_float_numeric_and_numeric_string_convert() -> None:
    """Coercible inputs go through float() (line 11)."""
    assert as_float(3) == 3.0
    assert as_float("2.5") == 2.5
    # Result is genuinely a float, not the original int/str.
    assert isinstance(as_float(3), float)


def test_as_float_bad_string_hits_valueerror_branch() -> None:
    """A non-numeric string raises ValueError inside float() -> default (12-13)."""
    assert as_float("not-a-number", 0.0) == 0.0
    # With no default supplied, the fallback is None.
    assert as_float("not-a-number") is None


def test_as_float_unconvertible_object_hits_typeerror_branch() -> None:
    """An object float() can't handle raises TypeError -> default (12-13)."""
    default = -1.0
    assert as_float(_Uncoercible(), default) == default


# ---------------------------------------------------------------------------
# as_int (lines 16-23)
# ---------------------------------------------------------------------------


def test_as_int_none_returns_default() -> None:
    """None short-circuits to the supplied default (line 18-19)."""
    assert as_int(None, 7) == 7
    assert as_int(None) is None


def test_as_int_numeric_and_numeric_string_convert() -> None:
    """Coercible inputs go through int(); floats truncate toward zero (line 21)."""
    assert as_int("4") == 4
    # int(2.9) truncates, not rounds — derive from Python semantics.
    assert as_int(2.9) == int(2.9) == 2
    assert isinstance(as_int("4"), int)


def test_as_int_bad_string_hits_valueerror_branch() -> None:
    """A non-integer string raises ValueError inside int() -> default (22-23)."""
    assert as_int("12.5", -1) == -1
    assert as_int("abc") is None


def test_as_int_unconvertible_object_hits_typeerror_branch() -> None:
    """An object int() can't handle raises TypeError -> default (22-23)."""
    default = 99
    assert as_int(_Uncoercible(), default) == default


# ---------------------------------------------------------------------------
# as_int_or_none (lines 26-33)
# ---------------------------------------------------------------------------


def test_as_int_or_none_none_input() -> None:
    """None maps to None (line 29-30)."""
    assert as_int_or_none(None) is None


def test_as_int_or_none_valid_and_invalid() -> None:
    """Valid -> int; invalid string/object -> None (line 31; 32-33)."""
    assert as_int_or_none("8") == 8
    assert as_int_or_none("x") is None
    assert as_int_or_none(_Uncoercible()) is None


# ---------------------------------------------------------------------------
# as_float_or_none (lines 70-77)
# ---------------------------------------------------------------------------


def test_as_float_or_none_none_input() -> None:
    """None maps to None (line 73-74)."""
    assert as_float_or_none(None) is None


def test_as_float_or_none_valid_conversion() -> None:
    """Coercible input goes through float() (line 75)."""
    assert as_float_or_none("3.25") == 3.25
    assert isinstance(as_float_or_none(2), float)


def test_as_float_or_none_bad_string_hits_valueerror_branch() -> None:
    """A non-numeric string raises ValueError -> None (76-77)."""
    assert as_float_or_none("nope") is None


def test_as_float_or_none_unconvertible_object_hits_typeerror_branch() -> None:
    """An object float() can't handle raises TypeError -> None (76-77)."""
    assert as_float_or_none(_Uncoercible()) is None


def test_underscore_alias_is_same_object() -> None:
    """The underscore alias is the exact same callable (line 137)."""
    assert _as_float_or_none is as_float_or_none


# ---------------------------------------------------------------------------
# get_nested (lines 47-67) + _resolve_key_case_insensitive (36-44)
# ---------------------------------------------------------------------------


def test_get_nested_single_string_key_exact() -> None:
    """A bare string key is treated as a one-element path (line 59)."""
    assert get_nested({"a": 1}, "a") == 1


def test_get_nested_deep_path_exact() -> None:
    """A multi-key path descends nested dicts (line 61-67)."""
    cfg: Dict[str, Any] = {"project": {"sub": {"value": 42}}}
    assert get_nested(cfg, ["project", "sub", "value"]) == 42


def test_get_nested_case_insensitive_resolution() -> None:
    """Exact miss falls back to a case-insensitive key match (line 40-43)."""
    cfg: Dict[str, Any] = {"Project": {"Capacity_MW": 150}}
    assert get_nested(cfg, ["project", "capacity_mw"]) == 150


def test_get_nested_missing_key_returns_default() -> None:
    """An absent key short-circuits to default (line 65-66; resolver line 44)."""
    sentinel = object()
    assert get_nested({"a": 1}, ["b"], sentinel) is sentinel


def test_get_nested_non_dict_intermediate_returns_default() -> None:
    """Hitting a non-dict before the path ends returns default (line 62-63)."""
    sentinel = object()
    # 'a' resolves to an int, so the next descent step can't continue.
    assert get_nested({"a": 5}, ["a", "b"], sentinel) is sentinel


def test_get_nested_top_level_not_dict_returns_default() -> None:
    """A non-dict root returns default immediately (line 62-63)."""
    assert get_nested("not-a-dict", ["a"], "fallback") == "fallback"  # type: ignore[arg-type]


def test_get_nested_value_present_but_none_returns_default() -> None:
    """A key present with value None is treated as a miss (line 64-66)."""
    assert get_nested({"a": None}, ["a"], "dflt") == "dflt"


# ---------------------------------------------------------------------------
# pct_to_decimal (lines 80-86)
# ---------------------------------------------------------------------------


def test_pct_to_decimal_none() -> None:
    """None passes through unchanged (line 82-83)."""
    assert pct_to_decimal(None) is None


def test_pct_to_decimal_percent_above_one_divides() -> None:
    """A value > 1.0 is read as a percent and divided by 100 (line 84-85)."""
    assert pct_to_decimal(34.0) == 0.34
    assert pct_to_decimal(100.0) == 1.0


def test_pct_to_decimal_decimal_at_or_below_one_passthrough() -> None:
    """A value <= 1.0 is already a decimal and passes through (line 86)."""
    assert pct_to_decimal(0.34) == 0.34
    # Boundary: exactly 1.0 is NOT > 1.0, so it is left as-is.
    assert pct_to_decimal(1.0) == 1.0


def test_pct_alias_is_same_object() -> None:
    """The underscore alias is the same callable (line 138)."""
    assert _pct_to_decimal is pct_to_decimal


# ---------------------------------------------------------------------------
# resolve_first (lines 89-102)
# ---------------------------------------------------------------------------


def test_resolve_first_string_candidate_case_insensitive() -> None:
    """A string candidate resolves case-insensitively at top level (line 95-96)."""
    cfg: Dict[str, Any] = {"Capacity_MW": 150}
    assert resolve_first(cfg, "capacity_mw") == 150


def test_resolve_first_sequence_candidate_uses_get_nested() -> None:
    """A sequence candidate is resolved via get_nested (line 97-98)."""
    cfg: Dict[str, Any] = {"project": {"capacity_mw": 120}}
    assert resolve_first(cfg, ("project", "capacity_mw")) == 120


def test_resolve_first_precedence_first_non_none_wins() -> None:
    """The first candidate that resolves non-None wins (line 100-101)."""
    cfg: Dict[str, Any] = {"project": {"capacity": 80}, "capacity_mw": 200}
    # First path misses (no capacity_mw under project), second path hits.
    result = resolve_first(
        cfg,
        ("project", "capacity_mw"),
        ("project", "capacity"),
        "capacity_mw",
    )
    assert result == 80


def test_resolve_first_all_missing_returns_none() -> None:
    """No candidate resolving leaves the return as None (line 102)."""
    assert resolve_first({"x": 1}, "y", ("a", "b")) is None


def test_resolve_first_alias_is_same_object() -> None:
    """The underscore alias is the same callable (line 139)."""
    assert _resolve_first is resolve_first


# ---------------------------------------------------------------------------
# Capacity-basis path tables: structure / precedence contract (114-130)
# ---------------------------------------------------------------------------


def test_capacity_path_tables_are_ordered_precedence_tuples() -> None:
    """The path tables are tuples ending in bare-string fallbacks."""
    assert isinstance(CAPACITY_MW_PATHS, tuple)
    assert isinstance(CAPACITY_FACTOR_PATHS, tuple)
    # Highest precedence is the canonical project.capacity_mw path.
    assert CAPACITY_MW_PATHS[0] == ("project", "capacity_mw")
    # Final fallbacks are bare string keys.
    assert CAPACITY_MW_PATHS[-1] == "capacity_mw"
    assert CAPACITY_FACTOR_PATHS[-1] == "capacity_factor"


def test_capacity_paths_drive_resolve_first_end_to_end() -> None:
    """resolve_first over the canonical path tables reads the engine basis.

    Derives the expected capacity factor by normalizing the resolved percent
    through pct_to_decimal — the exact transform the engine applies — rather
    than hardcoding a decimal.
    """
    cfg: Dict[str, Any] = {
        "project": {"capacity_mw": 150.0, "capacity_factor_pct": 33.9},
    }
    cap = resolve_first(cfg, *CAPACITY_MW_PATHS)
    cf_raw = resolve_first(cfg, *CAPACITY_FACTOR_PATHS)
    assert cap == 150.0
    cf = pct_to_decimal(cf_raw)
    assert cf is not None
    # 33.9 (>1.0) -> percent -> 0.339; derived, not asserted as a literal.
    assert math.isclose(cf, 33.9 / 100.0, rel_tol=0, abs_tol=1e-12)


def test_capacity_factor_path_precedence_decimal_form() -> None:
    """A decimal capacity_factor (<=1.0) passes through pct_to_decimal unchanged."""
    cfg: Dict[str, Any] = {"production": {"capacity_factor_net": 0.34}}
    cf_raw = resolve_first(cfg, *CAPACITY_FACTOR_PATHS)
    cf = pct_to_decimal(cf_raw)
    assert cf == 0.34


# ---------------------------------------------------------------------------
# Real canonical scenario: the helpers read the lender-case config coherently.
# ---------------------------------------------------------------------------


def test_helpers_read_canonical_lendercase_scenario() -> None:
    """Against the real scenario, the path tables resolve a sane MW + CF.

    No magic number: bounds/sign/structure only. Capacity must be positive;
    a resolved capacity factor must normalize into the physical (0, 1] band.
    """
    yaml = pytest.importorskip("yaml")
    path = (
        Path(__file__).resolve().parents[2]
        / "scenarios"
        / "dutchbay_lendercase_2025Q4.yaml"
    )
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    assert isinstance(cfg, dict)

    cap = as_float_or_none(resolve_first(cfg, *CAPACITY_MW_PATHS))
    cf_raw = resolve_first(cfg, *CAPACITY_FACTOR_PATHS)
    if cap is not None:
        assert cap > 0.0
    if cf_raw is not None:
        cf = pct_to_decimal(as_float_or_none(cf_raw))
        assert cf is not None
        assert 0.0 < cf <= 1.0
