"""Tests for the unified FastAPI app (app.api.main).

The endpoint functions are exercised directly (no httpx dependency needed); a
``TestClient`` HTTP smoke is gated behind ``importorskip('httpx')`` per the repo
convention. Asserts wiring + the fail-loud 400 path, not economic magic numbers.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi import HTTPException

import app.api.main as api_main
from analytics.schema_guard import ConfigValidationError
from app.api.main import (
    app,
    health,
    run_case,
    run_case_report_html,
    run_case_report_pdf,
)
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs


def _valid_kwargs(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "site_name": "DutchBay",
        "capacity_mw": 150.0,
        "capacity_factor": 0.339,
        "project_life_years": 20,
        "ppa_price_lkr_per_kwh": 20.30,
        "ppa_term_years": 20,
        "capex_total_usd": 159_600_000.0,
        "opex_annual_usd": 5_000_000.0,
        "fx_start_lkr_per_usd": 333.79,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# App composition
# --------------------------------------------------------------------------- #
def test_app_exposes_expected_routes() -> None:
    # The OpenAPI schema flattens included routers (the pipeline router is nested).
    spec_paths = set(app.openapi()["paths"])
    assert "/cases" in spec_paths
    assert "/health" in spec_paths
    assert "/run-pipeline" in spec_paths  # included from api.pipeline_api.router
    assert "/cases/report.html" in spec_paths
    assert "/cases/report.pdf" in spec_paths
    # the sensitivity sub-app is mounted as a sub-application
    assert any(getattr(r, "path", "") == "/sensitivity" for r in app.routes)


def test_health() -> None:
    assert health() == {"status": "ok"}


# --------------------------------------------------------------------------- #
# run_case (called directly)
# --------------------------------------------------------------------------- #
def test_run_case_returns_lender_kpis() -> None:
    result = run_case(WindFarmInputs(**_valid_kwargs()))
    assert isinstance(result, CaseResult)
    assert result.status == "success"
    assert result.scenario_variant == "lendercase"
    assert {"project_irr", "equity_irr", "min_dscr"} <= set(result.kpis)


def test_run_case_maps_engine_validation_error_to_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: Any, **_k: Any) -> Dict[str, Any]:
        raise ConfigValidationError("missing required field xyz")

    # The endpoint catches ConfigValidationError -> HTTP 400 (fail-loud, graceful).
    monkeypatch.setattr(api_main, "run_finance_case", _boom)
    with pytest.raises(HTTPException) as exc:
        run_case(WindFarmInputs(**_valid_kwargs()))
    assert exc.value.status_code == 400
    assert "Invalid scenario" in str(exc.value.detail)


# --------------------------------------------------------------------------- #
# Report routes (called directly)
# --------------------------------------------------------------------------- #
def test_run_case_report_html_renders() -> None:
    resp = run_case_report_html(WindFarmInputs(**_valid_kwargs(site_name="ReportSite")))
    assert resp.status_code == 200
    assert resp.media_type == "text/html"
    body = resp.body.decode("utf-8")
    assert "ReportSite" in body
    assert "Executive Summary" in body


def test_run_case_report_html_maps_validation_error_to_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: Any, **_k: Any) -> Dict[str, Any]:
        raise ConfigValidationError("bad scenario")

    monkeypatch.setattr(api_main, "run_finance_case", _boom)
    with pytest.raises(HTTPException) as exc:
        run_case_report_html(WindFarmInputs(**_valid_kwargs()))
    assert exc.value.status_code == 400


def test_run_case_report_pdf_503_without_weasyprint() -> None:
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        with pytest.raises(HTTPException) as exc:
            run_case_report_pdf(WindFarmInputs(**_valid_kwargs()))
        assert exc.value.status_code == 503
        assert "WeasyPrint" in str(exc.value.detail)
    else:  # pragma: no cover - only when the optional extra is installed
        resp = run_case_report_pdf(WindFarmInputs(**_valid_kwargs()))
        assert resp.media_type == "application/pdf"


def test_run_case_report_pdf_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cover the Response assembly without requiring WeasyPrint: stub the renderer.
    monkeypatch.setattr(api_main, "render_report_pdf", lambda _ctx: b"%PDF-1.7 stub")
    resp = run_case_report_pdf(WindFarmInputs(**_valid_kwargs()))
    assert resp.media_type == "application/pdf"
    assert resp.body == b"%PDF-1.7 stub"
    assert "attachment; filename=" in resp.headers["content-disposition"]
    assert "lendercase" in resp.headers["content-disposition"]


# --------------------------------------------------------------------------- #
# CaseResult projection
# --------------------------------------------------------------------------- #
def test_case_result_projection_filters_non_numeric() -> None:
    result = CaseResult.from_pipeline_result(
        {
            "status": "success",
            "kpis": {"project_irr": 0.05, "min_dscr": 1.3, "label": "x", "flag": True},
            "run_manifest": {"commit": "abc123"},
        },
        scenario_variant="basecase",
    )
    assert result.status == "success"
    assert result.scenario_variant == "basecase"
    assert result.kpis == {"project_irr": pytest.approx(0.05), "min_dscr": pytest.approx(1.3)}
    assert "label" not in result.kpis and "flag" not in result.kpis  # str / bool dropped
    assert result.run_manifest == {"commit": "abc123"}


def test_case_result_handles_missing_manifest() -> None:
    result = CaseResult.from_pipeline_result(
        {"status": "success", "kpis": {}}, scenario_variant="lendercase"
    )
    assert result.run_manifest is None
    assert result.kpis == {}


# --------------------------------------------------------------------------- #
# HTTP smoke (gated on httpx)
# --------------------------------------------------------------------------- #
def test_http_smoke_if_httpx_available() -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}

    ok = client.post("/cases", json=_valid_kwargs())
    assert ok.status_code == 200
    assert "project_irr" in ok.json()["kpis"]

    # malformed body -> FastAPI 422
    assert client.post("/cases", json={"site_name": ""}).status_code == 422
