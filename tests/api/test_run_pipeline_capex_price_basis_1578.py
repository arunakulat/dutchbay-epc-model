"""The capex price-basis disclosure reaches the API response and the rendered report (#1578).

#1578 next-20 item 5. The pipeline result carries a ``capex_price_basis`` block when a
declared ``capex.price_basis`` escalated a capex amount stated beside or instead of
``capex.usd_total`` (#1591 D-1/A-1), but ``POST /run-pipeline`` and the lender report
dropped it. The route's ``cost.capex_total_usd`` was also read from the authored config,
so a dated scenario reported the price-year total next to KPIs computed on the escalated
one.

``TEST-01`` oracles that did not originate in this change: the pipeline result's own
``capex_price_basis`` block (from ``finance.capex_price_basis.automatic_escalation``), and
the debt engine's capex resolver on the configuration the evaluation gateway prices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import pytest
import yaml

from analytics.evaluation_v14 import evaluated_scenario_config
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.storage_headline import apply_headline_storage_option
from api.pipeline_api import RunPipelineRequest, run_pipeline
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context
from finance.capex_price_basis import capex_escalation_factor
from finance.debt_v14 import _extract_capex_usd

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
UNDATED = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _wind() -> Dict[str, Any]:
    data = yaml.safe_load(WIND.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _with_finance_capex() -> Dict[str, Any]:
    """Wind stating its capex again under finance.capex_usd: escalated automatically."""
    cfg = _wind()
    cfg.setdefault("finance", {})["capex_usd"] = float(cfg["capex"]["usd_total"])
    return cfg


def test_route_carries_the_pipeline_disclosure() -> None:
    cfg = _with_finance_capex()
    expected = run_v14_pipeline(config=_with_finance_capex())["capex_price_basis"]
    resp = run_pipeline(RunPipelineRequest(config=cfg))
    assert resp.capex_price_basis is not None
    assert resp.capex_price_basis.model_dump() == expected
    assert resp.capex_price_basis.keys_at_price_year == {
        "finance.capex_usd": float(_wind()["capex"]["usd_total"])
    }


@pytest.mark.parametrize("path", [WIND, UNDATED], ids=["dated", "undated"])
def test_route_without_automatic_escalation_has_no_disclosure(path: Path) -> None:
    resp = run_pipeline(RunPipelineRequest(config_path=str(path)))
    assert resp.capex_price_basis is None
    assert "capex_price_basis" in resp.model_dump()  # the field is part of the schema


def test_route_reports_the_capex_the_engine_financed() -> None:
    """A dated scenario's cost block shows the escalated total, not the price-year one."""
    raw = _wind()
    resolved = capex_escalation_factor(raw)
    assert resolved is not None
    factor = float(resolved["factor"])
    resp = run_pipeline(RunPipelineRequest(config_path=str(WIND)))
    financed = _extract_capex_usd(evaluated_scenario_config(raw))
    assert resp.cost.capex_total_usd == pytest.approx(financed, rel=1e-12)
    assert resp.cost.capex_total_usd == pytest.approx(
        # #1823: including a declared headline battery's capex.
        float(apply_headline_storage_option(raw)["capex"]["usd_total"]) * factor,
        rel=1e-12,
    )


def test_route_cost_is_unchanged_for_an_undated_scenario() -> None:
    raw = yaml.safe_load(UNDATED.read_text(encoding="utf-8"))
    resp = run_pipeline(RunPipelineRequest(config_path=str(UNDATED)))
    assert resp.cost.capex_total_usd == pytest.approx(
        _extract_capex_usd(dict(raw)), rel=1e-12
    )


def _html(run: Mapping[str, Any], scenario_config: Mapping[str, Any]) -> str:
    context = build_report_context(
        CaseResult.from_pipeline_result(dict(run), scenario_variant="price-basis"),
        generated_at="2026-11-17T00:00:00Z",
        scenario_config=scenario_config,
        debt_result=run.get("debt_result"),
        annual_rows=run.get("annual_rows"),
        run_result=dict(run),
    )
    return render_report_html(context)


def test_report_renders_the_disclosure() -> None:
    run = run_v14_pipeline(config=_with_finance_capex())
    warning = run["capex_price_basis"]["warning"]
    html = _html(run, _with_finance_capex())
    assert "Capex price-date notice:" in html
    assert "finance.capex_usd" in html
    # The notice is the pipeline's own warning, HTML-escaped by the template.
    assert warning.split(":", 1)[0] in html


def test_report_without_the_disclosure_omits_the_notice() -> None:
    run = run_v14_pipeline(str(WIND))
    assert "capex_price_basis" not in run
    html = _html(run, _wind())
    assert "Capex price-date notice" not in html
