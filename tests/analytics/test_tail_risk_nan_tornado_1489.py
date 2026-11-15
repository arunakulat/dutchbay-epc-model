"""Regression tests for NaN-safe tornado tail-risk enrichment (#1489)."""

from __future__ import annotations

import math
from typing import Any, Dict

import pytest

import analytics.sensitivity.engine as engine
from analytics.contracts_v14 import (
    ParameterRangeConfig,
    SensitivitySuite,
    ShockResult,
    TornadoResult,
)
from analytics.sensitivity.tail_risk import (
    TailRiskConfig,
    _aggregate_metric_snapshot,
    _tornado_tail_stats,
)


def _nan_mixed_tornado(*, nan_first: bool) -> TornadoResult:
    nan = float("nan")
    nan_shock = ShockResult(
        label="capex_nan",
        low_case=nan,
        high_case=0.075,
        impact_abs=nan,
        metric_name="project_irr",
    )
    finite_shock = ShockResult(
        label="capex_finite",
        low_case=0.065,
        high_case=0.032,
        impact_abs=0.033,
        metric_name="project_irr",
    )
    shocks = [nan_shock, finite_shock] if nan_first else [finite_shock, nan_shock]
    return TornadoResult(
        metric_name="project_irr",
        base_metric=0.051,
        shock_results=shocks,
        label="CAPEX",
        impact_abs=nan,
    )


def test_tornado_tail_stats_filters_nan_independent_of_shock_order() -> None:
    stats_a = _tornado_tail_stats(tornado=_nan_mixed_tornado(nan_first=True))
    stats_b = _tornado_tail_stats(tornado=_nan_mixed_tornado(nan_first=False))

    for stats in (stats_a, stats_b):
        assert stats["downside"] == pytest.approx(0.032)
        assert stats["upside"] == pytest.approx(0.075)
        assert stats["worst_impact_abs"] == pytest.approx(0.033)
        assert stats["undefined"] is False


def test_tornado_tail_stats_all_nan_falls_back_to_base_and_flags_undefined() -> None:
    nan = float("nan")
    tornado = TornadoResult(
        metric_name="project_irr",
        base_metric=nan,
        shock_results=[
            ShockResult(
                label="broken",
                low_case=nan,
                high_case=nan,
                impact_abs=nan,
                metric_name="project_irr",
            )
        ],
        label="Tariff",
        impact_abs=nan,
    )
    stats = _tornado_tail_stats(tornado=tornado)
    assert math.isnan(stats["base_value"])
    assert math.isnan(stats["downside"])
    assert math.isnan(stats["upside"])
    assert math.isnan(stats["worst_impact_abs"])
    assert stats["undefined"] is True

    agg = _aggregate_metric_snapshot(
        rows=[stats, _tornado_tail_stats(tornado=_nan_mixed_tornado(nan_first=True))],
        run_cfg=TailRiskConfig(),
    )
    assert agg["downside"] == pytest.approx(0.032)
    assert agg["upside"] == pytest.approx(0.075)
    assert agg["worst_impact_abs"] == pytest.approx(0.033)
    assert agg["n_undefined_parameters"] == 1


def test_stubbed_sweep_with_nan_shocks_enriches_tail_risk_without_nan_poisoning(
    monkeypatch: Any, tmp_path: Any
) -> None:
    cfg = tmp_path / "stub_cfg.yaml"
    cfg.write_text(
        "capex: {usd_total: 100.0}\nopex: {usd_per_year: 5.0}\n", encoding="utf-8"
    )

    def _stub(
        *,
        config_path: Any = None,
        raw_config: Any = None,
        overrides: Dict[str, Any] | None = None,
        return_full_result: bool = False,
    ) -> Dict[str, Any]:
        del config_path, raw_config, return_full_result
        ov = overrides or {}
        if "capex.usd_total" in ov:
            capex = float(ov["capex.usd_total"])
            if capex > 105.0:
                return {"kpis": {}}  # high capex -> unsolvable IRR (NaN)
            if capex < 95.0:
                return {"kpis": {"project_irr": 0.08}}
        if "opex.usd_per_year" in ov:
            opex = float(ov["opex.usd_per_year"])
            if opex > 5.2:
                return {"kpis": {"project_irr": 0.04}}
            if opex < 4.8:
                return {"kpis": {"project_irr": 0.06}}
        return {"kpis": {"project_irr": 0.05}}

    monkeypatch.setattr(engine, "evaluate_with_overrides", _stub)

    run_cfg = engine.SensitivityRunConfig(
        strict=False,
        enrich_tail_risk=True,
        tail_risk=TailRiskConfig(enabled=True),
    )
    suite = engine.run_sensitivity_analysis(
        base_config={
            "capex": {"usd_total": 100.0},
            "opex": {"usd_per_year": 5.0},
        },
        base_config_path=str(cfg),
        parameters=[
            ParameterRangeConfig(
                variable_name="capex.usd_total",
                label="CAPEX",
                base_value=100.0,
                low_value=90.0,
                high_value=110.0,
            ),
            ParameterRangeConfig(
                variable_name="opex.usd_per_year",
                label="OPEX",
                base_value=5.0,
                low_value=4.5,
                high_value=5.5,
            ),
        ],
        metric_keys=["project_irr"],
        run_cfg=run_cfg,
    )

    assert isinstance(suite, SensitivitySuite)
    table = suite.metadata["tail_risk"]
    capex_row = next(r for r in table if r["parameter"] == "CAPEX")
    assert capex_row["downside"] == pytest.approx(0.08)
    assert capex_row["upside"] == pytest.approx(0.08)
    assert capex_row["undefined"] is True

    summary = suite.metadata["tail_risk_summary"]["project_irr"]
    assert summary["downside"] == pytest.approx(0.04)
    assert summary["upside"] == pytest.approx(0.08)
    assert summary["n_undefined_parameters"] == 1
