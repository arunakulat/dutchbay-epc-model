"""#1457: an undefined KPI at one driver point is recorded as undefined, not a crash.

``evaluate_with_overrides`` drops a KPI the pipeline left as ``None`` (#1436: equity IRR
with no solving rate), so the sweep sees no key. ``_extract_scalar_metric`` raised
``KeyError`` on that and one point ended the whole tornado, and with it the web
``/analysis`` job. The engine now records the point as ``nan``, flags it in metadata, logs
the driver and the value it took, and never substitutes 0.0 (#782: a 0.0 IRR reads as
break-even).

These tests replace the evaluator so each case is exact. The real-engine reproduction is
``tests/app/test_analysis_tornado_undefined_metric.py``.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Mapping

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.sensitivity import engine
from analytics.sensitivity.engine import (
    SensitivityRunConfig,
    build_one_way_sensitivity_suite,
    run_sensitivity_analysis,
)

_CONFIG: Dict[str, Any] = {"capex": {"usd_total": 100.0}, "tariff": {"lkr": 20.0}}
_METRIC = "equity_irr"


def _param(path: str, label: str, base: float) -> ParameterRangeConfig:
    """A +/-10% driver in absolute mode, so each case value is exact."""
    return ParameterRangeConfig(
        variable_name=path,
        base_value=base,
        low_value=base * 0.9,
        high_value=base + base / 10.0,
        label=label,
    )


_CAPEX = _param("capex.usd_total", "CAPEX", 100.0)  # cases 100, 90, 110
_TARIFF = _param("tariff.lkr", "Tariff", 20.0)  # cases 20, 18, 22


def _stub(
    monkeypatch: pytest.MonkeyPatch, *, undefined_at: set[tuple[str, float] | None]
) -> None:
    """Evaluator: the metric is linear in each override, and absent at ``undefined_at``.

    ``None`` in ``undefined_at`` stands for the base evaluation (no overrides).
    """

    def _evaluate(
        *, config_path: Any, raw_config: Any, overrides: Mapping[str, float]
    ) -> Dict[str, Any]:
        point = next(iter(overrides.items()), None)
        if point in undefined_at:
            return {"project_irr": 0.05}  # the swept metric is dropped
        value = 0.10
        if point is not None:
            key, x = point
            value += (x - (100.0 if key == "capex.usd_total" else 20.0)) / 1000.0
        return {_METRIC: value, "project_irr": 0.05}

    monkeypatch.setattr(engine, "evaluate_with_overrides", _evaluate)


def _is_nan(value: float | None) -> bool:
    """A recorded ``nan``: not ``None``, and certainly not a substituted 0.0."""
    return value is not None and math.isnan(value)


def _bar(suite: SensitivitySuite, label: str) -> Any:
    return next(t for t in suite.tornado_results if t.label == label)


def test_undefined_driver_point_is_nan_and_flagged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _stub(monkeypatch, undefined_at={("capex.usd_total", 110.0)})
    with caplog.at_level(logging.WARNING, logger=engine.__name__):
        suite = run_sensitivity_analysis(
            base_config=_CONFIG, parameters=[_CAPEX, _TARIFF], metric_keys=[_METRIC]
        )

    capex = _bar(suite, "CAPEX")
    shock = capex.shock_results[0]
    assert shock.low_case == pytest.approx(0.09)
    assert math.isnan(shock.high_case)  # never a fabricated 0.0
    assert math.isnan(capex.impact_abs)
    assert capex.metadata["undefined_cases"] == ["CAPEX=high"]
    assert capex.base_metric == pytest.approx(0.10)

    tariff = _bar(suite, "Tariff")
    assert tariff.impact_abs == pytest.approx(0.004)
    assert "undefined_cases" not in tariff.metadata

    assert suite.metadata["undefined_base"] is False
    assert suite.metadata["undefined_points"] == 1
    assert suite.metadata["undefined_drivers"] == ["CAPEX"]
    assert suite.metadata["flat_metric"] is False
    # The log names the metric, the driver case and the value it took.
    assert any(
        "equity_irr" in r.getMessage()
        and "CAPEX=high" in r.getMessage()
        and "capex.usd_total=110.0" in r.getMessage()
        for r in caplog.records
    )


def test_undefined_base_is_reported_not_flat_or_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, undefined_at={None})
    suite = run_sensitivity_analysis(
        base_config=_CONFIG, parameters=[_CAPEX, _TARIFF], metric_keys=[_METRIC]
    )
    assert suite.metadata["undefined_base"] is True
    assert suite.metadata["undefined_points"] == 1
    assert suite.metadata["undefined_drivers"] == []
    for tornado in suite.tornado_results:
        assert math.isnan(tornado.base_metric)
        assert _is_nan(tornado.shock_results[0].base_case)
        # The swing is high minus low, which the base does not enter.
        assert math.isfinite(tornado.impact_abs) and tornado.impact_abs > 0.0
    assert suite.metadata["flat_metric"] is False


def test_one_way_suite_records_an_undefined_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, undefined_at={None, ("capex.usd_total", 90.0)})
    suite = build_one_way_sensitivity_suite(
        base_config=_CONFIG, parameter=_CAPEX, metric_key=_METRIC
    )
    tornado = suite.tornado_results[0]
    assert math.isnan(tornado.base_metric)
    assert _is_nan(tornado.shock_results[0].low_case)
    assert tornado.shock_results[0].high_case == pytest.approx(0.11)
    assert tornado.metadata["undefined_cases"] == ["CAPEX=low"]
    assert suite.metadata["undefined_base"] is True
    assert suite.metadata["undefined_points"] == 2
    assert suite.metadata["undefined_drivers"] == ["CAPEX"]


def test_metric_undefined_everywhere_raises_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No evaluation defines it: there is no tornado, and a typo looks exactly like this."""
    every_point: set[tuple[str, float] | None] = {None}
    for p in (_CAPEX, _TARIFF):
        for x in (p.base_value, p.low_value, p.high_value):
            assert x is not None
            every_point.add((p.variable_name, x))
    _stub(monkeypatch, undefined_at=every_point)
    with pytest.raises(ValueError, match="undefined at every one of 7 evaluations"):
        run_sensitivity_analysis(
            base_config=_CONFIG, parameters=[_CAPEX, _TARIFF], metric_keys=[_METRIC]
        )
    suite = run_sensitivity_analysis(
        base_config=_CONFIG,
        parameters=[_CAPEX, _TARIFF],
        metric_keys=[_METRIC],
        run_cfg=SensitivityRunConfig(strict=False),
    )
    assert suite.metadata["undefined_points"] == 7
    assert suite.metadata["undefined_drivers"] == ["CAPEX", "Tariff"]


def test_flatness_ignores_undefined_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``nan`` bar first in line must not decide (or hide) the flat-metric flag."""
    _stub(monkeypatch, undefined_at={("capex.usd_total", 90.0)})
    suite = run_sensitivity_analysis(
        base_config=_CONFIG, parameters=[_CAPEX, _TARIFF], metric_keys=[_METRIC]
    )
    assert suite.metadata["flat_metric"] is False  # Tariff moves 0.004

    def _flat(**_kw: Any) -> Dict[str, Any]:
        overrides = _kw["overrides"]
        if overrides.get("capex.usd_total") == 90.0:
            return {}
        return {_METRIC: 0.10}

    monkeypatch.setattr(engine, "evaluate_with_overrides", _flat)
    suite = run_sensitivity_analysis(
        base_config=_CONFIG, parameters=[_CAPEX, _TARIFF], metric_keys=[_METRIC]
    )
    assert suite.metadata["flat_metric"] is True  # the one defined bar is flat
    assert suite.metadata["undefined_drivers"] == ["CAPEX"]


def test_defined_sweep_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, undefined_at=set())
    suite = run_sensitivity_analysis(
        base_config=_CONFIG, parameters=[_CAPEX, _TARIFF], metric_keys=[_METRIC]
    )
    assert [t.impact_abs for t in suite.tornado_results] == pytest.approx([0.02, 0.004])
    assert suite.metadata["undefined_points"] == 0
    assert suite.metadata["undefined_base"] is False
    assert suite.metadata["undefined_drivers"] == []
    assert all("undefined_cases" not in t.metadata for t in suite.tornado_results)
