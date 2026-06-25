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
from analytics.aep_provenance import AepProvenanceError
from analytics.aep_reconciliation import AepReconciliationError
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
        # The real 15 x 10.64 MW nameplate (not the round "150 MW" label): 159.6 x 0.339
        # x 8.760 = 473.9 GWh reconciles with the lendercase frozen AEP (473.8), so the
        # service-seam reconciliation guard passes.
        "capacity_mw": 159.6,
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
    assert "/jobs" in spec_paths  # async live-ERA5 path (PR E)
    assert "/jobs/{job_id}" in spec_paths
    assert "/jobs/{job_id}/events" in spec_paths
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


@pytest.mark.parametrize(
    "error_factory",
    [
        lambda: AepReconciliationError("capacity*CF diverges from bankable AEP by >2%"),
        lambda: AepProvenanceError("power-curve source not in APPROVED_SOURCES"),
    ],
)
def test_run_case_maps_engine_integrity_errors_to_400(
    monkeypatch: pytest.MonkeyPatch, error_factory: Any
) -> None:
    """A wizard capacity/CF edit beyond the AEP-reconciliation tolerance (or an
    unapproved provenance) raises AepReconciliationError / AepProvenanceError inside
    run_finance_case. These subclass ValueError but NOT ConfigValidationError, so before
    the fix they propagated uncaught -> HTTP 500; now they map to a graceful 400."""

    def _boom(*_a: Any, **_k: Any) -> Dict[str, Any]:
        raise error_factory()

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


def test_http_smoke_jobs_if_httpx_available(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    import app.api.jobs_router as jr
    from fastapi.testclient import TestClient

    from app.jobs.store import InMemoryJobStore

    # Stub the runner so the TestClient's background task does NOT hit real ERA5.
    monkeypatch.setattr(jr, "run_wind_job", lambda *a, **k: None)
    # Override the store dependency (proves the DI seam is real and swappable).
    custom_store = InMemoryJobStore()
    app.dependency_overrides[jr.get_store] = lambda: custom_store
    try:
        client = TestClient(app)
        body = {
            "inputs": _valid_kwargs(),
            "site_lat": 8.33,
            "site_lon": 79.76,
            "turbine_model": "IEA-10MW",
            "num_turbines": 15,
            "hub_height_m": 119.0,
        }
        accepted = client.post("/jobs", json=body)
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]

        got = client.get(f"/jobs/{job_id}")
        assert got.status_code == 200
        assert got.json()["job_id"] == job_id

        assert client.get("/jobs/unknown-id").status_code == 404
        # The injected store — not the module default — received the job.
        assert custom_store.get(job_id) is not None
    finally:
        app.dependency_overrides.clear()
