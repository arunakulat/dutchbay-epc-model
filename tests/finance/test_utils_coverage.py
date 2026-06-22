"""Coverage tests for ``finance.utils`` — pure finance helper utilities.

These three helpers underpin config parsing across the engine, so the tests
exercise every branch with deterministic, edge-case inputs and assert real
relationships rather than memorised values:

  * ``get_nested`` — happy-path traversal, the missing-key default, the
    "intermediate value is not a dict" early return, and the ``is`` identity
    semantics around the sentinel default.
  * ``as_float`` — ``None`` passthrough, successful int/str coercion, and the
    ``ValueError``/``TypeError`` fallback.
  * ``as_int`` — ``None`` passthrough, successful str/float truncation, and the
    ``ValueError``/``TypeError`` fallback.

No economic magic numbers: every expectation is a structural property of the
helper (identity, equality with a value computed in-test, or the documented
default contract).
"""

from __future__ import annotations

from finance.utils import as_float, as_int, get_nested


def test_get_nested_happy_path() -> None:
    d = {"a": {"b": {"c": 42}}}
    assert get_nested(d, ["a", "b", "c"]) == 42


def test_get_nested_empty_path_returns_root() -> None:
    d = {"a": 1}
    assert get_nested(d, []) is d


def test_get_nested_missing_key_returns_default() -> None:
    d = {"a": {"b": 1}}
    sentinel = object()
    assert get_nested(d, ["a", "x"], default=sentinel) is sentinel


def test_get_nested_default_none_when_key_absent() -> None:
    assert get_nested({"a": 1}, ["missing"]) is None


def test_get_nested_intermediate_not_dict_returns_default() -> None:
    # Line 11: result becomes a non-dict (int) before the path is exhausted,
    # so the next iteration hits the ``not isinstance(result, dict)`` guard.
    d = {"a": 5}
    sentinel = object()
    assert get_nested(d, ["a", "b"], default=sentinel) is sentinel


def test_get_nested_top_level_not_dict_returns_default() -> None:
    sentinel = object()
    assert get_nested("not-a-dict", ["a"], default=sentinel) is sentinel  # type: ignore[arg-type]


def test_get_nested_value_equal_to_default_short_circuits() -> None:
    # When the fetched value *is* the default sentinel, traversal stops and the
    # default is returned (the ``result is default`` branch on line 13-14).
    d = {"a": {"b": 1}}
    out = get_nested(d, ["a", "missing", "deeper"], default=None)
    assert out is None


def test_as_float_none_returns_default() -> None:
    assert as_float(None) is None
    sentinel = 3.5
    assert as_float(None, default=sentinel) == sentinel


def test_as_float_converts_int_and_string() -> None:
    assert as_float(7) == 7.0
    assert as_float("2.5") == 2.5


def test_as_float_value_error_returns_default() -> None:
    assert as_float("not-a-number", default=-1.0) == -1.0


def test_as_float_type_error_returns_default() -> None:
    # A list cannot be coerced to float -> TypeError -> default.
    assert as_float([1, 2], default=0.0) == 0.0


def test_as_int_none_returns_default() -> None:
    # Line 30-31: None short-circuits to the supplied default.
    assert as_int(None) is None
    assert as_int(None, default=9) == 9


def test_as_int_converts_string_and_truncates_float() -> None:
    # Lines 32-33: successful coercion via the try-body.
    assert as_int("12") == 12
    assert as_int(3.9) == 3  # int() truncates toward zero


def test_as_int_value_error_returns_default() -> None:
    # Lines 34-35: ValueError caught, default returned.
    assert as_int("not-an-int", default=-5) == -5


def test_as_int_type_error_returns_default() -> None:
    # Lines 34-35: TypeError caught (dict has no int conversion), default returned.
    assert as_int({"k": "v"}, default=0) == 0


def test_as_int_default_none_on_failure() -> None:
    assert as_int("xyz") is None
