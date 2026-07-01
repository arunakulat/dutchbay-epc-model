"""Coverage tests for analytics.sensitivity.validation.

Exercises the parameter-range QA checker end to end:

  * ``_nested_override`` for both the single-segment and multi-segment
    dotted-key cases (asserting the produced nested-dict shape).
  * ``validate_parameter_ranges`` across every branch of its sweep loop:
      - the ``pct is None`` skip (absolute-mode bound) ``continue`` path,
      - the in-range success path (no row emitted),
      - the out-of-range path for a negative metric (``met < 0``),
      - the out-of-range path for an implausibly high metric (``met > 0.5``),
      - the ``except Exception`` path (an ``error`` row is emitted),
      - the empty-input path (an empty frame with no columns).

``evaluate_with_overrides`` is imported lazily inside the function, so we
patch it at its definition site (``analytics.evaluate_scenario``) with a
deterministic stub keyed off the override value. No network, cdsapi, or
matplotlib is touched. Assertions check the real returned-frame contents
and the documented override math, not import smoke.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity.validation import (
    _nested_override,
    validate_parameter_ranges,
)


def _param(
    *,
    name: str = "project.capacity_factor",
    base_value: float = 100.0,
    low_pct: float | None = -10.0,
    high_pct: float | None = 10.0,
) -> ParameterRangeConfig:
    return ParameterRangeConfig(
        variable_name=name,
        base_value=base_value,
        low_pct=low_pct,
        high_pct=high_pct,
        label=name,
    )


def test_nested_override_single_segment() -> None:
    out = _nested_override("opex_annual", 42.0)
    assert out == {"opex_annual": 42.0}


def test_nested_override_multi_segment() -> None:
    out = _nested_override("project.financial.tariff", 7.5)
    assert out == {"project": {"financial": {"tariff": 7.5}}}


def test_all_points_in_range_returns_empty_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, Any]] = []

    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        captured.append(ovr)
        return {"project_irr": 0.10}

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    df = validate_parameter_ranges("ignored.yaml", [_param()])

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    # Both sweep points evaluated: base 100 -> 90.0 (low) and 110.0 (high).
    assert len(captured) == 2
    assert captured[0]["project"]["capacity_factor"] == pytest.approx(90.0)
    assert captured[1]["project"]["capacity_factor"] == pytest.approx(110.0)


def test_negative_metric_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        return {"project_irr": -0.05}

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    df = validate_parameter_ranges("ignored.yaml", [_param()])

    # Both low and high sweeps are out of range -> two flagged rows.
    assert len(df) == 2
    assert set(df["var"]) == {"project.capacity_factor"}
    assert set(df["output"]) == {-0.05}
    assert sorted(df["pct"].tolist()) == [-10.0, 10.0]
    assert sorted(df["input"].tolist()) == pytest.approx([90.0, 110.0])


def test_high_metric_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        return {"project_irr": 0.95}  # > 0.5 -> implausible IRR

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    df = validate_parameter_ranges("ignored.yaml", [_param()])

    assert len(df) == 2
    assert set(df["output"]) == {0.95}
    assert "error" not in df.columns


def test_exception_path_records_error_row(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    df = validate_parameter_ranges("ignored.yaml", [_param()])

    assert len(df) == 2
    assert "error" in df.columns
    assert set(df["error"]) == {"pipeline blew up"}
    # The error rows carry the swept input, not an output metric.
    assert sorted(df["input"].tolist()) == pytest.approx([90.0, 110.0])


def test_none_pct_points_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append(ovr)
        return {"project_irr": 0.10}

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    # Absolute-mode bound: low_pct present, high_pct None -> only one eval.
    param = _param(low_pct=-20.0, high_pct=None)
    df = validate_parameter_ranges("ignored.yaml", [param])

    assert df.empty
    assert calls == [{"project": {"capacity_factor": 80.0}}]


def test_both_pct_none_evaluates_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        raise AssertionError("evaluate_with_overrides should not be called")

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    param = _param(low_pct=None, high_pct=None)
    df = validate_parameter_ranges("ignored.yaml", [param])

    assert df.empty


def test_custom_metric_key_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_eval(path: str, ovr: dict[str, Any], **_: Any) -> dict[str, Any]:
        # project_irr is fine, but the custom metric is out of range.
        return {"project_irr": 0.10, "equity_irr": -0.30}

    monkeypatch.setattr(
        "analytics.evaluate_scenario.evaluate_with_overrides", fake_eval
    )

    df = validate_parameter_ranges("ignored.yaml", [_param()], metric="equity_irr")

    assert len(df) == 2
    assert set(df["output"]) == {-0.30}


def test_empty_parameters_returns_empty_frame() -> None:
    df = validate_parameter_ranges("ignored.yaml", [])
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == []
