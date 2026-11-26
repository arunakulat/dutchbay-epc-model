"""Report tornado falls back to NPV when IRR does not rank or is undefined (#1819)."""

from __future__ import annotations

from typing import List, cast

from analytics.contracts_v14 import SensitivitySuite, ShockResult, TornadoResult
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context
from app.services.report_tornado import TornadoBlock, TornadoRow, compute_report_tornado

GENERATED_AT = "2026-11-25T00:00:00+00:00"
_BASE_KPIS: dict[str, float | None] = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "project_npv": -57_994_285.93,
    "min_dscr": 1.30,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}


def _suite(
    metric: str,
    *,
    ranks_reliably: bool | None = True,
    project_irr_status: str = "computed",
    defined: bool = True,
) -> SensitivitySuite:
    nan = float("nan")
    val = 1_250_000.0 if metric.endswith("_npv") else 0.025
    low = -val if defined else nan
    high = val if defined else nan
    swing = 2 * val if defined else nan
    base = 5_000_000.0 if metric.endswith("_npv") else (0.08 if defined else nan)
    base_kpis: dict[str, object] = {"project_irr_status": project_irr_status}
    if ranks_reliably is not None:
        base_kpis["equity_irr_ranks_reliably"] = ranks_reliably
    return SensitivitySuite(
        base_kpis=cast(dict[str, float], base_kpis),
        tornado_results=[
            TornadoResult(
                metric_name=metric,
                base_metric=base,
                impact_abs=swing,
                shock_results=[
                    ShockResult(
                        label="Tariff",
                        low_case=low,
                        high_case=high,
                        base_case=base,
                    )
                ],
            )
        ],
    )


def test_unreliable_equity_irr_flag_switches_tornado_to_npv() -> None:
    """Any scenario with equity_irr_ranks_reliably=False sweeps NPV instead of IRR."""
    seen_metrics: List[str] = []

    def runner(_path: str, *, metric: str) -> SensitivitySuite:
        seen_metrics.append(metric)
        if metric == "project_irr":
            return _suite("project_irr", ranks_reliably=False, defined=False)
        return _suite(metric, ranks_reliably=False, defined=True)

    block = compute_report_tornado({"project": {"name": "any-site"}}, runner=runner)
    assert block is not None
    assert seen_metrics == ["project_irr", "project_npv"]
    assert block.metric == "project_npv"
    assert block.metric_label == "Project NPV"
    assert block.is_currency is True


def test_equity_irr_switches_to_equity_npv_when_unreliable() -> None:
    seen_metrics: List[str] = []

    def runner(_path: str, *, metric: str) -> SensitivitySuite:
        seen_metrics.append(metric)
        return _suite(metric, ranks_reliably=False, defined=metric == "equity_npv")

    block = compute_report_tornado(
        {"project": {"name": "any-site"}}, metric="equity_irr", runner=runner
    )
    assert block is not None
    assert seen_metrics == ["equity_irr", "equity_npv"]
    assert block.metric == "equity_npv"
    assert block.metric_label == "Equity NPV"
    assert block.is_currency is True


def test_undefined_project_irr_everywhere_switches_to_project_npv() -> None:
    seen_metrics: List[str] = []

    def runner(_path: str, *, metric: str) -> SensitivitySuite:
        seen_metrics.append(metric)
        if metric == "project_irr":
            return _suite(
                "project_irr",
                ranks_reliably=None,
                project_irr_status="undefined",
                defined=False,
            )
        return _suite(metric, ranks_reliably=None, defined=True)

    block = compute_report_tornado({"project": {"name": "any-site"}}, runner=runner)
    assert block is not None
    assert seen_metrics == ["project_irr", "project_npv"]
    assert block.metric == "project_npv"


def test_reliable_irr_stays_on_irr() -> None:
    seen_metrics: List[str] = []

    def runner(_path: str, *, metric: str) -> SensitivitySuite:
        seen_metrics.append(metric)
        return _suite(metric, ranks_reliably=True, defined=True)

    block = compute_report_tornado({"project": {"name": "any-site"}}, runner=runner)
    assert block is not None
    assert seen_metrics == ["project_irr"]
    assert block.metric == "project_irr"
    assert block.is_currency is False


def test_currency_tornado_renders_usd_not_percentages() -> None:
    case = CaseResult(
        status="success",
        scenario_variant="solar_bess",
        kpis=_BASE_KPIS,
        run_manifest=None,
    )
    tornado = TornadoBlock(
        metric="project_npv",
        rows=[
            TornadoRow(
                label="Tariff",
                base=5_000_000.0,
                low_case=-1_250_000.0,
                high_case=11_250_000.0,
                impact_abs=12_500_000.0,
            ),
            TornadoRow(
                label="Undefined driver",
                base=5_000_000.0,
                low_case=None,
                high_case=None,
                impact_abs=None,
            ),
        ],
    )
    html = render_report_html(
        build_report_context(case, generated_at=GENERATED_AT, tornado=tornado)
    )
    section = html.split("<h2>Sensitivity Tornado", 1)[1].split("</section>", 1)[0]
    assert "&mdash; Project NPV</h2>" in section
    assert "$5,000,000" in section
    assert "-$1,250,000" in section
    assert "$11,250,000" in section
    assert "$12,500,000" in section
    assert "undefined" in section
    assert "%" not in section
