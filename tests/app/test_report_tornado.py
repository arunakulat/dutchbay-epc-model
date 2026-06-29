"""Tests for the report sensitivity-tornado adapter (RPT-1).

The canonical sweep engine is injected as a fake so these never run the real
multi-shock pipeline — they exercise this adapter's temp-file handling, row
mapping, widest-first sorting, and the best-effort failure degradation.
"""

from __future__ import annotations

from typing import Any

from analytics.contracts_v14 import SensitivitySuite, ShockResult, TornadoResult
from app.services.report_tornado import TornadoBlock, compute_report_tornado

_SCENARIO = {"project": {"name": "test"}, "finance": {"capex_total_usd": 1.0}}


def _suite_with_two_drivers() -> SensitivitySuite:
    return SensitivitySuite(
        tornado_results=[
            TornadoResult(
                metric_name="project_irr",
                base_metric=0.0116,
                impact_abs=0.0064,  # narrower swing
                shock_results=[
                    ShockResult(
                        label="Corporate Tax Rate",
                        low_case=0.0147,
                        high_case=0.0083,
                        base_case=0.0116,
                        impact_abs=0.0064,
                    )
                ],
            ),
            TornadoResult(
                metric_name="project_irr",
                base_metric=0.0116,
                impact_abs=0.0280,  # wider swing
                shock_results=[
                    ShockResult(
                        variable_name="tariff",
                        label="Tariff",
                        low_case=-0.0031,
                        high_case=0.0249,
                        base_case=0.0116,
                        impact_abs=0.0280,
                    )
                ],
            ),
        ]
    )


def test_compute_tornado_maps_and_sorts_widest_first() -> None:
    block = compute_report_tornado(
        _SCENARIO, runner=lambda _path, *, metric: _suite_with_two_drivers()
    )
    assert isinstance(block, TornadoBlock)
    assert block.metric == "project_irr"
    # Sorted by |swing| descending: Tariff (0.0280) before Corporate Tax Rate (0.0064).
    assert [r.label for r in block.rows] == ["Tariff", "Corporate Tax Rate"]
    top = block.rows[0]
    assert top.base == 0.0116
    assert top.low_case == -0.0031 and top.high_case == 0.0249
    assert top.impact_abs == 0.0280


def test_compute_tornado_returns_none_when_runner_raises() -> None:
    # Best-effort: a sweep failure must degrade to None, not propagate (CASPER).
    def _boom(_path: str, *, metric: str) -> SensitivitySuite:
        raise RuntimeError("sweep blew up")

    assert compute_report_tornado(_SCENARIO, runner=_boom) is None


def test_compute_tornado_returns_none_when_no_drivers() -> None:
    block = compute_report_tornado(
        _SCENARIO, runner=lambda _path, *, metric: SensitivitySuite(tornado_results=[])
    )
    assert block is None


def test_compute_tornado_skips_unlabelled_drivers() -> None:
    suite = SensitivitySuite(
        tornado_results=[
            TornadoResult(
                metric_name="", base_metric=0.0, impact_abs=0.0, shock_results=[]
            )
        ]
    )
    # The single driver has no label/metric_name -> dropped -> no rows -> None.
    assert compute_report_tornado(_SCENARIO, runner=lambda _p, *, metric: suite) is None


def test_compute_tornado_honours_metric_argument() -> None:
    captured: dict[str, Any] = {}

    def _runner(_path: str, *, metric: str) -> SensitivitySuite:
        captured["metric"] = metric
        return _suite_with_two_drivers()

    block = compute_report_tornado(_SCENARIO, metric="equity_irr", runner=_runner)
    assert captured["metric"] == "equity_irr"
    assert block is not None and block.metric == "equity_irr"
