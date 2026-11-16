"""The lender report's yield-reconciliation table (#1768).

The report restates the pipeline result's ``yield_reconciliation`` record; it recomputes
nothing. A report built without a run result omits the table, so legacy callers render as
before.
"""

from __future__ import annotations

import json
from pathlib import Path
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
    # The status is a real <strong> element, never its escaped markup shown as text.
    assert "Status: <strong>reconciled</strong>." in html
    assert "&lt;strong&gt;" not in html
    assert (
        "The fail-loud reconciliation gate ran on this configuration and passed. "
        "Tolerance 2.00%." in html
    )
    assert "not a yield basis" in html  # the caveat line under the table
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
    assert "Tolerance 5.00% (audited override of the default)." in html


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
    assert "reported here rather than refused." in html
    assert record["reason"] in html
    assert "Status: <strong>not applicable</strong>." in html


def test_report_escapes_the_record_text() -> None:
    record = _record(351.0)
    record["reason"] = "<script>x</script>"
    ctx = build_report_context(
        _case(),
        generated_at=GENERATED_AT,
        run_result={"yield_reconciliation": record},
    )
    html = render_report_html(ctx)
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;." in html


def test_report_shows_the_p90_row(tmp_path: Path) -> None:
    summary = tmp_path / "aep_summary.json"
    summary.write_text(
        json.dumps(
            {"net_site_aep_gwh": 350.4, "exceedance": {"net_aep_p90_1yr_gwh": 300.0}}
        )
    )
    record = _record(
        351.0,
        resource={"aep_summary_path": str(summary)},
        expected_results={"net_aep_p50_gwh": 351.0, "net_aep_p90_gwh": 301.5},
    )
    ctx = build_report_context(
        _case(),
        generated_at=GENERATED_AT,
        run_result={"yield_reconciliation": record},
    )
    block = ctx.yield_reconciliation
    assert block is not None
    p90_rows = [row for row in block.rows if row.check == "P90"]
    (p90,) = p90_rows
    assert p90.source == f"{summary}:exceedance.net_aep_p90_1yr_gwh"
    assert p90.reference_gwh == 300.0
    assert p90.compared_gwh == 301.5
    assert p90.deviation_pct == record["p90"]["deviation_pct"]
    assert p90.within_tolerance is True
    html = render_report_html(ctx)
    assert "<td>P90</td>" in html
    assert "+0.50%" in html
