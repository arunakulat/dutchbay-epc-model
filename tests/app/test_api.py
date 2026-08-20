"""Tests for the unified FastAPI app (app.api.main).

The endpoint functions are exercised directly (no httpx dependency needed); a
``TestClient`` HTTP smoke is gated behind ``importorskip('httpx')`` per the repo
convention. Asserts wiring + the fail-loud 400 path, not economic magic numbers.
"""

from __future__ import annotations

import asyncio
import threading
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
    readiness,
    run_case,
    run_case_report_html,
    run_case_report_pdf,
)
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.renderer import ReportDependencyError
from app.reports.report_model import ReportContext, build_report_context


def _valid_kwargs(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "site_name": "DutchBay",
        # The real 15 x 10.64 MW nameplate (not the round "150 MW" label): 159.6 x 0.332
        # x 8.760 = 464.2 GWh reconciles with the lendercase frozen AEP (464.3, post the
        # 2% pre-construction P50 over-prediction haircut), so the service-seam
        # reconciliation guard passes.
        "capacity_mw": 159.6,
        "capacity_factor": 0.332,
        "project_life_years": 20,
        "ppa_price_lkr_per_kwh": 20.30,
        "ppa_term_years": 20,
        "capex_total_usd": 159_600_000.0,
        "opex_annual_usd": 5_000_000.0,
        "fx_start_lkr_per_usd": 333.79,
    }
    base.update(overrides)
    return base


def _known_report_context(*, site_name: str = "ReportSite") -> ReportContext:
    """Build a deterministic renderer/transport context without running finance."""
    inputs = WindFarmInputs(**_valid_kwargs(site_name=site_name))
    case = CaseResult(
        status="success",
        scenario_variant=inputs.scenario_variant,
        kpis={
            "project_irr": 0.0422,
            "equity_irr": -0.0246,
            "project_npv": -57_994_285.93,
            "min_dscr": 1.30,
            "discount_rate_used": 0.0854,
            "balloon_pct": 0.3467,
        },
        run_manifest=None,
    )
    return build_report_context(
        case,
        generated_at="2026-08-20T00:00:00+00:00",
        inputs=inputs,
    )


# --------------------------------------------------------------------------- #
# App composition
# --------------------------------------------------------------------------- #
def test_app_exposes_expected_routes() -> None:
    # The OpenAPI schema flattens included routers (the pipeline router is nested).
    spec_paths = set(app.openapi()["paths"])
    # #841 contract freeze: the whole client-data surface is version-pinned under /v1;
    # only the infra /health probe is unversioned.
    assert "/health" in spec_paths
    assert (
        "/health/readiness" in spec_paths
    )  # #995 readiness diagnostic (unversioned infra)
    assert "/v1/cases" in spec_paths
    assert "/v1/run-pipeline" in spec_paths  # included from api.pipeline_api.router
    assert "/v1/cases/report.html" in spec_paths
    assert "/v1/cases/report.pdf" in spec_paths
    assert "/v1/jobs" in spec_paths  # async live-ERA5 path (PR E)
    assert "/v1/jobs/{job_id}" in spec_paths
    assert "/v1/jobs/{job_id}/events" in spec_paths
    # the sensitivity surface is now composed as gated routes (no longer a mounted
    # sub-app), so its endpoints appear in the parent OpenAPI schema.
    assert "/v1/sensitivity/run-pipeline" in spec_paths
    assert "/v1/sensitivity/run-tornado/" in spec_paths
    # the pre-freeze unprefixed public paths are GONE — /v1 is the single surface.
    assert "/cases" not in spec_paths
    assert "/jobs" not in spec_paths


def test_health() -> None:
    # The exact /health body (incl. contract_version, #841) is pinned in
    # test_api_contract.py; here just smoke the liveness status.
    assert health()["status"] == "ok"


# --------------------------------------------------------------------------- #
# readiness diagnostic (#995): reports CDS config PRESENCE, never a value
# --------------------------------------------------------------------------- #
def test_readiness_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both CDS keys set (non-blank) -> every check True and ``ready`` is True."""
    monkeypatch.setenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    monkeypatch.setenv("CDSAPI_KEY", "super-secret-token-value")
    body = readiness()
    assert body["status"] == "ok"
    assert body["ready"] is True
    assert body["checks"] == {"cdsapi_url": True, "cdsapi_key": True}


def test_readiness_missing_key_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL present but credential absent -> not ready, and the missing check is False."""
    monkeypatch.setenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    monkeypatch.delenv("CDSAPI_KEY", raising=False)
    body = readiness()
    assert body["ready"] is False
    assert body["checks"] == {"cdsapi_url": True, "cdsapi_key": False}


def test_readiness_blank_value_counts_as_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A set-but-blank var must not read as configured (guards a whitespace-only secret)."""
    monkeypatch.setenv("CDSAPI_URL", "   ")
    monkeypatch.setenv("CDSAPI_KEY", "")
    body = readiness()
    assert body["ready"] is False
    assert body["checks"] == {"cdsapi_url": False, "cdsapi_key": False}


def test_readiness_never_echoes_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe must report booleans only — no secret (or URL) value ever appears."""
    secret = "TOP-SECRET-CDS-TOKEN"
    url = "https://cds.climate.copernicus.eu/api"
    monkeypatch.setenv("CDSAPI_URL", url)
    monkeypatch.setenv("CDSAPI_KEY", secret)
    serialized = repr(readiness())
    assert secret not in serialized
    assert url not in serialized


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
def test_run_case_report_html_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _known_report_context()
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: context)
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


def test_run_case_report_pdf_503_without_weasyprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _known_report_context()
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: context)

    def _missing_backend(_context: ReportContext) -> bytes:
        raise ReportDependencyError(
            "PDF rendering requires WeasyPrint; install the report extra"
        )

    monkeypatch.setattr(api_main, "render_report_pdf", _missing_backend)
    with pytest.raises(HTTPException) as exc:
        run_case_report_pdf(WindFarmInputs(**_valid_kwargs()))
    assert exc.value.status_code == 503
    assert "WeasyPrint" in str(exc.value.detail)


def test_run_case_report_pdf_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cover response assembly without rerunning finance/sensitivity or the PDF backend.
    context = _known_report_context()
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: context)
    monkeypatch.setattr(api_main, "render_report_pdf", lambda _ctx: b"%PDF-1.7 stub")
    resp = run_case_report_pdf(WindFarmInputs(**_valid_kwargs()))
    assert resp.media_type == "application/pdf"
    assert resp.body == b"%PDF-1.7 stub"
    assert "attachment; filename=" in resp.headers["content-disposition"]
    assert "lendercase" in resp.headers["content-disposition"]


# --------------------------------------------------------------------------- #
# RPT-9: download-filename sanitisation + synchronous-route timeout
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("lendercase", "lendercase"),  # the normal constrained variant is untouched
        ("base case", "base_case"),
        ('a"b', "a_b"),  # quote would break the quoted-string header
        ("a/b\\c", "a_b_c"),  # path separators
        ("evil\r\nSet-Cookie: x", "evil_Set-Cookie_x"),  # CR/LF header injection
        ("...", "report"),  # nothing printable survives -> fallback
        ("", "report"),
        ("好", "report"),  # non-ASCII collapses then strips to empty -> fallback
    ],
)
def test_sanitise_filename_component(raw: str, expected: str) -> None:
    assert api_main._sanitise_filename_component(raw) == expected


def test_pdf_content_disposition_has_no_header_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even a crafted variant reaching the context yields a header with no CR/LF or quote."""
    monkeypatch.setattr(api_main, "render_report_pdf", lambda _ctx: b"%PDF-1.7 stub")

    class _Ctx:
        scenario_variant = 'x"\r\nSet-Cookie: y'

    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: _Ctx())
    resp = run_case_report_pdf(WindFarmInputs(**_valid_kwargs()))
    cd = resp.headers["content-disposition"]
    assert "\r" not in cd and "\n" not in cd and '"y' not in cd
    assert cd == 'attachment; filename="dutchbay_x_Set-Cookie_y_report.pdf"'


def test_run_with_timeout_passes_through_result() -> None:
    assert asyncio.run(api_main._run_with_timeout(lambda: 42, timeout=5.0)) == 42


def test_run_with_timeout_raises_504_on_slow_compute() -> None:
    release = threading.Event()

    def _slow() -> int:
        release.wait(2.0)  # block the worker thread deterministically
        return 1

    async def _scenario() -> HTTPException:
        try:
            with pytest.raises(HTTPException) as exc:
                await api_main._run_with_timeout(_slow, timeout=0.01)
            return exc.value
        finally:
            release.set()  # let the orphaned worker thread finish promptly

    err = asyncio.run(_scenario())
    assert err.status_code == 504
    assert "time limit" in str(err.detail)


def test_run_with_timeout_propagates_inner_http_exception() -> None:
    """A fail-loud 400 from the wrapped core must not be masked as a 504."""

    def _boom() -> int:
        raise HTTPException(status_code=400, detail="bad")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_main._run_with_timeout(_boom, timeout=5.0))
    assert exc.value.status_code == 400


def test_run_with_timeout_sheds_load_when_at_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every compute slot is occupied, a new request is shed with 503 (not queued)."""

    async def _scenario() -> int:
        sem = asyncio.Semaphore(1)
        await sem.acquire()  # occupy the only slot (stands in for an in-flight compute)
        monkeypatch.setattr(api_main, "_get_compute_semaphore", lambda: sem)
        with pytest.raises(HTTPException) as exc:
            await api_main._run_with_timeout(lambda: 1, timeout=5.0)
        return exc.value.status_code

    assert asyncio.run(_scenario()) == 503


def test_timed_out_compute_keeps_its_slot_until_the_thread_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A compute that exceeds the timeout still holds its concurrency slot until the
    (uncancellable) worker thread actually finishes — the backpressure property a bare
    ``wait_for`` would defeat by releasing the limiter token on cancellation."""

    async def _scenario() -> None:
        sem = asyncio.Semaphore(1)
        monkeypatch.setattr(api_main, "_get_compute_semaphore", lambda: sem)
        release = threading.Event()

        def _slow() -> int:
            release.wait(2.0)
            return 1

        try:
            with pytest.raises(HTTPException) as exc:
                await api_main._run_with_timeout(_slow, timeout=0.05)
            assert exc.value.status_code == 504
            # The orphaned (timed-out) compute still occupies the only slot:
            assert sem.locked() is True
        finally:
            release.set()  # let the worker thread finish so the slot can release
        for _ in range(100):  # allow the shielded task to run its release
            if not sem.locked():
                break
            await asyncio.sleep(0.02)
        assert sem.locked() is False

    asyncio.run(_scenario())


def test_operation_ids_are_pinned() -> None:
    """The /cases* operationIds are pinned, so the API contract is stable across renames."""
    paths = app.openapi()["paths"]
    assert paths["/v1/cases"]["post"]["operationId"] == "run_case"
    assert (
        paths["/v1/cases/report.html"]["post"]["operationId"] == "run_case_report_html"
    )
    assert paths["/v1/cases/report.pdf"]["post"]["operationId"] == "run_case_report_pdf"


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
    assert result.kpis == {
        "project_irr": pytest.approx(0.05),
        "min_dscr": pytest.approx(1.3),
    }
    assert (
        "label" not in result.kpis and "flag" not in result.kpis
    )  # str / bool dropped
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

    from app.api.auth import get_current_subject

    # Auth is exercised end-to-end in test_auth.py; here we override the dependency
    # so the smoke stays focused on the case-running behaviour.
    app.dependency_overrides[get_current_subject] = lambda: "smoke-user"
    try:
        client = TestClient(app)
        assert client.get("/health").json()["status"] == "ok"

        ok = client.post("/v1/cases", json=_valid_kwargs())
        assert ok.status_code == 200
        assert "project_irr" in ok.json()["kpis"]

        # malformed body -> FastAPI 422
        assert client.post("/v1/cases", json={"site_name": ""}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_http_smoke_readiness_is_unauthenticated_and_200() -> None:
    """#995 AC3, over HTTP: the readiness diagnostic is reachable WITHOUT a bearer token
    and always answers 200 with a boolean body. Deliberately sets NO auth override — if the
    route ever picked up ``Depends(get_current_subject)`` or got swept under the /v1 gate this
    would flip to 401/403, and if it became a gate (non-200 when unconfigured) it would fail
    here. This is the security-relevant property that the direct-call tests can't observe.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    client = TestClient(app)  # no dependency_overrides -> real (absent) auth
    resp = client.get("/health/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["ready"], bool)
    assert set(body["checks"]) == {"cdsapi_url", "cdsapi_key"}
    assert all(isinstance(v, bool) for v in body["checks"].values())


def test_http_smoke_jobs_if_httpx_available(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.api.jobs_router as jr
    from app.api.auth import get_current_subject
    from app.jobs.store import InMemoryJobStore

    # Stub the runner so the TestClient's background task does NOT hit real ERA5.
    monkeypatch.setattr(jr, "run_wind_job", lambda *a, **k: None)
    # Override the store dependency (proves the DI seam is real and swappable).
    custom_store = InMemoryJobStore()
    app.dependency_overrides[jr.get_store] = lambda: custom_store
    # Override auth (the owner-isolation path is covered in test_auth.py).
    app.dependency_overrides[get_current_subject] = lambda: "smoke-user"
    try:
        client = TestClient(app)
        body = {
            "inputs": _valid_kwargs(),
            "site_lat": 8.33,
            "site_lon": 79.76,
            "turbine_model": "iea_reference_10mw",
            "num_turbines": 15,
            "hub_height_m": 119.0,
        }
        accepted = client.post("/v1/jobs", json=body)
        assert accepted.status_code == 202
        payload = accepted.json()
        job_id = payload["job_id"]
        # #841: the returned handle URLs carry the /v1 prefix (url_for-derived).
        assert payload["status_url"].endswith(f"/v1/jobs/{job_id}")
        assert payload["events_url"].endswith(f"/v1/jobs/{job_id}/events")

        got = client.get(f"/v1/jobs/{job_id}")
        assert got.status_code == 200
        assert got.json()["job_id"] == job_id

        assert client.get("/v1/jobs/unknown-id").status_code == 404
        # The injected store — not the module default — received the job.
        assert custom_store.get(job_id) is not None
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Auth gate on the compute surfaces (regression for the pre-fix anonymous hole)
# --------------------------------------------------------------------------- #
def test_compute_routes_require_auth_when_no_token() -> None:
    """/run-pipeline and /sensitivity/* return full lender KPIs + confined file
    reads, so — like /cases — they must reject an unauthenticated request with 401.
    Regression: these were anonymously reachable while mounted/ungated."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    client = TestClient(app)  # no dependency override -> no bearer token presented
    assert client.post("/v1/run-pipeline", json={"config_path": "x"}).status_code == 401
    assert (
        client.post(
            "/v1/sensitivity/run-pipeline", json={"config_path": "x"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/sensitivity/run-tornado/",
            json={"config_path": "x", "parameters": []},
        ).status_code
        == 401
    )


def test_compute_routes_pass_auth_gate_with_token() -> None:
    """With the auth dependency satisfied, the request reaches the handler: a bad
    config_path yields the handler's own 4xx (not the 401 gate), proving the token
    was accepted rather than the route being blanket-open or blanket-closed."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.auth import get_current_subject

    app.dependency_overrides[get_current_subject] = lambda: "smoke-user"
    try:
        client = TestClient(app)
        r = client.post("/v1/run-pipeline", json={"config_path": "does_not_exist.yaml"})
        assert r.status_code != 401  # gate passed; handler ran (and 400'd on bad path)
    finally:
        app.dependency_overrides.clear()
