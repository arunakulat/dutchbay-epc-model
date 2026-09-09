"""Compare the listing adapter with the existing windpowerlib 0.2.2 contract.

The packaged-table oracle calls the unmodified installed public function. Synthetic
cases retain its original selection/merge/fill expressions as a reference. Only
that reference may emit the known warning; every candidate call treats it as an
error. No installed package, global pandas option or warning filter is changed.
"""

from __future__ import annotations

import sys
import warnings
from itertools import product
from types import ModuleType

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from wind_resource.power_curve_sourcing import list_oedb_turbines

from .test_power_curve_sourcing import _require_optional_package


def _legacy_filter(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep the installed 0.2.2 filtered branch as the synthetic reference."""
    cp_curves = raw.loc[raw["has_cp_curve"].fillna(False)][
        ["manufacturer", "turbine_type", "has_cp_curve"]
    ]
    power_curves = raw.loc[raw["has_power_curve"].fillna(False)][
        ["manufacturer", "turbine_type", "has_power_curve"]
    ]
    return pd.merge(power_curves, cp_curves, how="outer", sort=True).fillna(False)


def _raw() -> pd.DataFrame:
    """Three overlapping duplicate keys yield four merged contributions."""
    return pd.DataFrame(
        {
            "manufacturer": ["Z", "A", "A", "A"],
            "turbine_type": ["z", "a", "a", "a"],
            "has_power_curve": [True, True, False, True],
            "has_cp_curve": [False, False, True, True],
        }
    )


def _stub_raw(monkeypatch: pytest.MonkeyPatch, raw: pd.DataFrame) -> None:
    """Substitute a local module at the adapter's public dependency boundary."""
    stub = ModuleType("windpowerlib")

    def get_types(*, print_out: bool, filter_: bool) -> pd.DataFrame:
        assert print_out is False
        assert filter_ is False
        return raw.copy(deep=True)

    monkeypatch.setattr(stub, "get_turbine_types", get_types, raising=False)
    monkeypatch.setitem(sys.modules, "windpowerlib", stub)


def _candidate(manufacturer: str | None = None) -> pd.DataFrame:
    """Make any candidate FutureWarning fail the compatibility check."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        return list_oedb_turbines(manufacturer)


@pytest.mark.parametrize(
    "manufacturer", [None, "", "ENERCON", "Enercon|Vestas", "no-match"]
)
def test_packaged_table_matches_installed_oracle(manufacturer: str | None) -> None:
    """Exact public-oracle equality includes ordering, index, columns and dtypes."""
    _require_optional_package("windpowerlib")
    from windpowerlib import get_turbine_types

    with warnings.catch_warnings(record=True) as emitted:
        warnings.filterwarnings("always", message="Downcasting object dtype arrays")
        expected = get_turbine_types(print_out=False)
    assert all(
        issubclass(w.category, FutureWarning)
        and str(w.message).startswith("Downcasting object dtype arrays")
        for w in emitted
    )
    if manufacturer:
        expected = expected[
            expected["manufacturer"]
            .astype(str)
            .str.contains(manufacturer, case=False, na=False)
        ]
    assert_frame_equal(_candidate(manufacturer), expected, check_exact=True)


def _synthetic_cases() -> list[pd.DataFrame]:
    """Bound flags, missing labels, explicit dtypes, emptiness and merge overlap."""
    cases: list[pd.DataFrame] = []
    for flags in product(product([False, True], repeat=2), repeat=4):
        frame = _raw()
        frame["has_power_curve"] = [p for p, _ in flags]
        frame["has_cp_curve"] = [c for _, c in flags]
        cases.append(frame)
    for manufacturer, turbine in product([None, np.nan, pd.NA, "label", ""], repeat=2):
        frame = _raw()
        frame.loc[1:3, "manufacturer"] = manufacturer
        frame.loc[1:3, "turbine_type"] = turbine
        cases.append(frame)
    for power, cp in product(
        [True, False, None, np.nan, pd.NA, 0, 1, 2, "True", "False", "invalid"],
        repeat=2,
    ):
        frame = _raw().astype({"has_power_curve": object, "has_cp_curve": object})
        frame.loc[1, "has_power_curve"] = power
        frame.loc[2, "has_cp_curve"] = cp
        cases.append(frame)
    for dtype in ("bool", "boolean", "object"):
        cases.append(_raw().astype({"has_power_curve": dtype, "has_cp_curve": dtype}))
    cases.append(_raw().iloc[:0])
    all_missing = _raw()
    all_missing[["manufacturer", "turbine_type"]] = None
    cases.append(all_missing)
    return cases


@pytest.mark.parametrize("raw", _synthetic_cases(), ids=lambda frame: str(frame.shape))
def test_synthetic_matches_legacy_outcome(
    monkeypatch: pytest.MonkeyPatch, raw: pd.DataFrame
) -> None:
    """Preserve successful tables and malformed flag errors without coercing bool."""
    _stub_raw(monkeypatch, raw)
    expected_error: KeyError | ValueError | TypeError | None
    with warnings.catch_warnings(record=True):
        warnings.filterwarnings("always", message="Downcasting object dtype arrays")
        try:
            expected = _legacy_filter(raw)
        except (KeyError, ValueError, TypeError) as exc:
            expected_error = exc
        else:
            expected_error = None
    if expected_error is not None:
        with pytest.raises(type(expected_error)) as raised:
            _candidate()
        assert str(raised.value) == str(expected_error)
    else:
        assert_frame_equal(_candidate(), expected, check_exact=True)


def test_duplicate_merge_contributions_and_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An independently constructed five-row oracle rejects a plain row filter."""
    raw = _raw()
    raw.index = pd.Index([8, 6, 4, 2], name="source_row")
    _stub_raw(monkeypatch, raw)
    expected = pd.DataFrame(
        {
            "manufacturer": ["A", "A", "A", "A", "Z"],
            "turbine_type": ["a", "a", "a", "a", "z"],
            "has_power_curve": [True] * 5,
            "has_cp_curve": [True, True, True, True, False],
        }
    )
    assert_frame_equal(_candidate(), expected, check_exact=True)
    shortcut = raw.loc[raw["has_power_curve"] | raw["has_cp_curve"]]
    assert len(shortcut) == 4
    with pytest.raises(AssertionError):
        assert_frame_equal(shortcut, expected, check_exact=True)


@pytest.mark.parametrize("defect", ["flag", "contribution", "order", "dtype"])
def test_exact_oracle_rejects_corruption(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    """Observe the equality oracle fail between two real candidate controls."""
    _stub_raw(monkeypatch, _raw())
    expected = _candidate()
    altered = expected.copy()
    if defect == "flag":
        altered.loc[0, "has_power_curve"] = False
    elif defect == "contribution":
        altered = altered.iloc[1:].reset_index(drop=True)
    elif defect == "order":
        altered = altered.iloc[::-1].reset_index(drop=True)
    else:
        altered["has_power_curve"] = altered["has_power_curve"].astype(object)
    with pytest.raises(AssertionError):
        assert_frame_equal(altered, expected, check_exact=True)
    assert_frame_equal(_candidate(), expected, check_exact=True)
