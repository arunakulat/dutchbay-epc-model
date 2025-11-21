"""
Tests for finance.utils helpers:

- get_nested for normal and missing paths.
- as_float / as_int conversion and fallbacks.
"""

from finance.utils import get_nested, as_float, as_int


def test_get_nested_happy_path_and_missing():
    data = {
        "level1": {
            "level2": {
                "value": 42,
            },
        },
    }

    assert get_nested(data, ["level1", "level2", "value"]) == 42
    assert get_nested(data, ["level1", "missing"], default="x") == "x"
    # Non-dict along the path should trigger default
    assert get_nested({"a": 1}, ["a", "b"], default="y") == "y"


def test_as_float_success_and_failure():
    assert as_float("3.14", default=None) == 3.14
    assert as_float(2, default=None) == 2.0
    # Failures and None use the default
    assert as_float("not-a-number", default=0.5) == 0.5
    assert as_float(None, default=1.23) == 1.23


def test_as_int_success_and_failure():
    assert as_int("10", default=None) == 10
    assert as_int(7, default=None) == 7
    # Failures and None use the default
    assert as_int("bad", default=-1) == -1
    assert as_int(None, default=99) == 99
