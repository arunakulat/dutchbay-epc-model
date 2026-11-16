"""The lender report's yield-reconciliation table (#1768).

The report restates the pipeline result's ``yield_reconciliation`` record; it recomputes
nothing. A report built without a run result omits the table, so legacy callers render as
before.
"""

from __future__ import annotations

from typing import Any, Dict

from analytics.aep_reconciliation import build_yield_reconciliation_record
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

GENERATED_AT = "2026-06-22T12:00:00+00:00"
_KPIS: Dict[str, float] = {"project_irr": 0.08, "min_dscr": 1.35}


def _case() -> CaseResult:
    return CaseResult(status="success", scenario_variant="lendercase", kpis=_KPIS)


def _record(reference_gwh: float, **extra: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "project": {"capacity_mw": 100.0, "capacity_factor": 0.4},
        "expected_results": {"net_aep_p50_gwh": reference_gwh},
    }
    cfg.update(extra)
    return build_yield_reconciliation_record(cfg, gate_applied=True)


def test_report_without_run_result_omits_the_table() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT)
    assert ctx.yield_reconciliation is None
    assert "Yield reconciliation" not in render_report_html(ctx)


def test_report_without_a_record_omits_the_table() -> None:
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, run_result={"kpis": _KPIS}
    )
    assert ctx.yield_reconciliation is None


def test_report_restates_the_record() -> None:
    record = _record(351.0)
    ctx = build_report_context(
        _case(),
        generated_at=GENERATED_AT,
        run_result={"kpis": _KPIS, "yield_reconciliation": record},
    )
    block = ctx.yield_reconciliation
    assert block is not None
    assert block.status == "reconciled"
    assert block.gate_applied is True
    assert block.tolerance_pct == record["tolerance_pct"]
    (row,) = block.rows
    assert row.check == "P50"
    assert row.source == "expected_results.net_aep_p50_gwh"
    assert row.reference_gwh == 351.0
    assert row.compared_gwh == record["implied_net_aep_gwh"]
    assert row.deviation_pct == record["p50"]["references"][0]["deviation_pct"]
    assert row.within_tolerance is True

    html = render_report_html(ctx)
    assert "Yield reconciliation" in html
    assert "The load-time gate ran on this scenario and passed." in html
    assert "351.00" in html
    assert "350.40" in html
    assert "-0.17%" in html  # (350.4 - 351) / 351 = -0.171%


def test_report_shows_an_override_and_an_out_of_tolerance_row() -> None:
    record = _record(380.0, aep_reconciliation={"tolerance_pct": 5.0})
    ctx = build_report_context(
        _case(),
        generated_at=GENERATED_AT,
        run_result={"yield_reconciliation": record},
    )
    block = ctx.yield_reconciliation
    assert block is not None
    assert block.status == "outside_tolerance"
    assert block.tolerance_overridden is True
    assert block.rows[0].within_tolerance is False
    html = render_report_html(ctx)
    assert "outside tolerance" in html
    assert "audited override of the default" in html


def test_report_shows_not_applicable_with_its_reason() -> None:
    record = build_yield_reconciliation_record(
        {"project": {"capacity_mw": 100.0, "capacity_factor": 0.4}}, gate_applied=False
    )
    ctx = build_report_context(
        _case(),
        generated_at=GENERATED_AT,
        run_result={"yield_reconciliation": record},
    )
    block = ctx.yield_reconciliation
    assert block is not None
    assert block.rows == []
    html = render_report_html(ctx)
    assert "not applicable" in html
    assert "did not run on this configuration" in html
    assert record["reason"] in html
