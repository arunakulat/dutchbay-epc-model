"""#843 — fast unit/behaviour tests for the wizard backend (complements ``test_web_wizard``).

``tests/app/test_web_wizard.py`` (Author B) drives the wizard end-to-end against the *real*
finance engine (its run/download tests are ``slow``). This module fills the gaps that suite
does not cover, and does so *fast* by stubbing the reused case-run functions on
:mod:`app.api.main` (which the wizard routes resolve at call time), so none of these tests
run the ~26 s engine:

* the :mod:`app.web.auth_cookie` transport in isolation — cookie attributes (incl.
  ``Secure`` only in production) and the fail-closed :func:`require_web_user` redirect
  *shapes* (an ``HX-Redirect`` header for htmx vs a ``303`` for a plain navigation), proving
  the JWT validation is *reused*, not re-implemented;
* the results fragment on a canned surface — every supplementary block present (charts +
  capital risk) and, separately, every block ``None`` (the "not computed" degradation);
* the engine-rejection path — ``build_case_surface`` wraps a bad scenario as an
  ``HTTPException(400)``, which the wizard re-renders as the ``_error`` fragment (not raw
  JSON, never a 500);
* the additive-wiring guarantees — ``/static`` is mounted and the existing ``/v1`` +
  ``/health`` surface is untouched.

HTTP smoke is gated behind ``importorskip('httpx')`` (matching the sibling suites).
"""

from __future__ import annotations

from typing import Any, Dict, Iterator

import pytest

from app.api.surface import (
    ArtifactLinks,
    CapitalRiskMetric,
    CapitalRiskSurface,
    CaseSurface,
    GlobalSaBar,
    GlobalSaChart,
    KpiCard,
    TornadoBar,
    TornadoChart,
)
from app.web.auth_cookie import COOKIE_NAME

_SECRET = "web-routes-unit-signing-secret-0123456789"
_USERNAME = "analyst"
_PASSWORD = "correct horse battery staple"


# --------------------------------------------------------------------------- #
# Fixtures / helpers.
# --------------------------------------------------------------------------- #
@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a signing secret + one known user in the permissive dev posture."""
    from app.api.auth import hash_password

    monkeypatch.delenv("DUTCHBAY_ENV", raising=False)
    monkeypatch.delenv("DUTCHBAY_JWT_ISSUER", raising=False)
    monkeypatch.delenv("DUTCHBAY_JWT_AUDIENCE", raising=False)
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    monkeypatch.setenv("DUTCHBAY_API_USERS", f"{_USERNAME}:{hash_password(_PASSWORD)}")


def _canned_surface(**overrides: Any) -> CaseSurface:
    """A fully-populated :class:`CaseSurface` (one of every block) built without the engine."""
    base: Dict[str, Any] = {
        "status": "success",
        "scenario_variant": "lendercase",
        "site_name": "Dutch Bay",
        "report_grade": "B",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "kpi_cards": [
            KpiCard(
                key="project_irr",
                label="Project IRR (nominal)",
                value=0.0145,
                display="1.46%",
            ),
            KpiCard(key="min_dscr", label="Min DSCR", value=1.2857, display="1.29x"),
        ],
        "tornado": TornadoChart(
            metric="project_irr",
            bars=[
                TornadoBar(
                    label="PPA price",
                    base=0.0145,
                    low_case=0.01,
                    high_case=0.02,
                    impact_abs=0.01,
                ),
                TornadoBar(
                    label="Capex",
                    base=0.0145,
                    low_case=0.012,
                    high_case=0.017,
                    impact_abs=0.005,
                ),
            ],
        ),
        "global_sa_morris": GlobalSaChart(
            method="morris",
            metric="project_irr",
            n_runs=40,
            bars=[
                GlobalSaBar(name="ppa_price", mu_star=0.02, sigma=0.005),
                GlobalSaBar(name="capex", mu_star=0.01, sigma=0.004),
            ],
        ),
        "global_sa_pawn": GlobalSaChart(
            method="pawn",
            metric="project_irr",
            n_runs=40,
            bars=[GlobalSaBar(name="ppa_price", median_ks=0.3, ks_cv=0.1)],
        ),
        "capital_risk": CapitalRiskSurface(
            scenario="lendercase",
            model_version="v15.3.0",
            method="monte_carlo",
            n_trials=1000,
            dscr_breach_probability=0.05,
            llcr_breach_probability=0.02,
            plcr_breach_probability=0.01,
            dscr_floor=1.2,
            llcr_floor=1.3,
            plcr_floor=1.4,
            probability_below_hurdle=0.6,
            target_equity_irr=0.12,
            metrics=[
                CapitalRiskMetric(
                    metric="equity_irr",
                    unit="pct",
                    mean=-0.058,
                    var=-0.09,
                    cvar=-0.11,
                    var_label="VaR(95)",
                    cvar_label="CVaR(95)",
                )
            ],
            npv_distribution_filename="npv_dist.png",
        ),
        "artifacts": ArtifactLinks(),
    }
    base.update(overrides)
    return CaseSurface(**base)


@pytest.fixture()
def client(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """A :class:`TestClient` with the engine + artifact builders stubbed (fast)."""
    pytest.importorskip("httpx")
    from fastapi.responses import HTMLResponse, Response
    from fastapi.testclient import TestClient

    import app.api.main as api_main

    monkeypatch.setattr(
        api_main, "build_case_surface", lambda _inputs: _canned_surface()
    )
    monkeypatch.setattr(
        api_main,
        "run_case_report_html",
        lambda _inputs: HTMLResponse(content="<html><body>report</body></html>"),
    )
    monkeypatch.setattr(
        api_main,
        "run_case_report_pdf",
        lambda _inputs: Response(
            content=b"%PDF-1.7 stub",
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="r.pdf"'},
        ),
    )
    monkeypatch.setattr(
        api_main,
        "run_case_workbook",
        lambda _inputs: Response(
            content=b"PK\x03\x04stub",
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": 'attachment; filename="w.xlsx"'},
        ),
    )
    with TestClient(api_main.app) as test_client:
        yield test_client


def _login(client: Any) -> None:
    resp = client.post(
        "/login",
        data={"username": _USERNAME, "password": _PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert COOKIE_NAME in resp.cookies


def _full_form(**overrides: str) -> Dict[str, str]:
    form: Dict[str, str] = {
        "scenario_variant": "lendercase",
        "site_name": "Dutch Bay",
        "location": "Kalpitiya, Sri Lanka",
        "capacity_mw": "150",
        "capacity_factor": "0.35",
        "project_life_years": "25",
        "cod_year": "2027",
        "num_turbines": "15",
        "hub_height_m": "120",
        "ppa_price_lkr_per_kwh": "22",
        "ppa_term_years": "20",
        "capex_total_usd": "167860000",
        "opex_annual_usd": "6000000",
        "fx_start_lkr_per_usd": "333.79",
    }
    form.update(overrides)
    return form


def _make_request(headers: Dict[str, str], cookies: Dict[str, str]) -> Any:
    from starlette.requests import Request

    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_str.encode()))
    scope = {"type": "http", "method": "GET", "headers": raw_headers}
    return Request(scope)


# --------------------------------------------------------------------------- #
# Cookie transport (app.web.auth_cookie) — no HTTP client.
# --------------------------------------------------------------------------- #
def test_set_session_cookie_dev_attributes(auth_env: None) -> None:
    """Dev cookie: httpOnly + SameSite=Lax + NOT Secure (works over http://localhost)."""
    from fastapi import Response

    from app.web.auth_cookie import COOKIE_MAX_AGE_SECONDS, set_session_cookie

    response = Response()
    set_session_cookie(response, "the.jwt.value")
    header = response.headers["set-cookie"]
    assert f"{COOKIE_NAME}=the.jwt.value" in header
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()
    assert "secure" not in header.lower()
    assert f"Max-Age={COOKIE_MAX_AGE_SECONDS}" in header
    assert "Path=/" in header


def test_set_session_cookie_secure_in_production(
    auth_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production cookie is marked ``Secure`` (never sent over cleartext)."""
    from fastapi import Response

    from app.web.auth_cookie import set_session_cookie

    monkeypatch.setenv("DUTCHBAY_ENV", "production")
    response = Response()
    set_session_cookie(response, "the.jwt.value")
    assert "secure" in response.headers["set-cookie"].lower()


def test_clear_session_cookie_expires(auth_env: None) -> None:
    from fastapi import Response

    from app.web.auth_cookie import clear_session_cookie

    response = Response()
    clear_session_cookie(response)
    header = response.headers["set-cookie"].lower()
    assert f"{COOKIE_NAME.lower()}=" in header
    assert "max-age=0" in header or "expires=" in header


def test_require_web_user_accepts_valid_cookie(auth_env: None) -> None:
    """A valid token resolves to its subject via the reused decoder."""
    from app.api.auth import create_access_token
    from app.web.auth_cookie import require_web_user

    token = create_access_token(_USERNAME, secret=_SECRET)
    assert require_web_user(_make_request({}, {COOKIE_NAME: token})) == _USERNAME


def test_require_web_user_plain_nav_redirects_303(auth_env: None) -> None:
    from fastapi import HTTPException

    from app.web.auth_cookie import require_web_user

    with pytest.raises(HTTPException) as excinfo:
        require_web_user(_make_request({}, {}))
    assert excinfo.value.status_code == 303
    assert (excinfo.value.headers or {}).get("Location") == "/login"


def test_require_web_user_htmx_sets_hx_redirect(auth_env: None) -> None:
    from fastapi import HTTPException

    from app.web.auth_cookie import require_web_user

    with pytest.raises(HTTPException) as excinfo:
        require_web_user(_make_request({"HX-Request": "true"}, {}))
    assert excinfo.value.status_code == 401
    assert (excinfo.value.headers or {}).get("HX-Redirect") == "/login"


def test_require_web_user_rejects_forged_token(auth_env: None) -> None:
    """A token signed with the wrong secret is rejected (redirected), not trusted."""
    from fastapi import HTTPException

    from app.api.auth import create_access_token
    from app.web.auth_cookie import require_web_user

    forged = create_access_token(_USERNAME, secret="a-different-secret-value")
    with pytest.raises(HTTPException) as excinfo:
        require_web_user(_make_request({}, {COOKIE_NAME: forged}))
    assert excinfo.value.status_code == 303


def test_require_web_user_rejects_expired_token(auth_env: None) -> None:
    """An expired token is rejected (redirected)."""
    from fastapi import HTTPException

    from app.api.auth import create_access_token
    from app.web.auth_cookie import require_web_user

    # Minted far in the past with a tiny TTL → already expired at validation time.
    expired = create_access_token(_USERNAME, secret=_SECRET, expires_in=1, now=1000)
    with pytest.raises(HTTPException) as excinfo:
        require_web_user(_make_request({}, {COOKIE_NAME: expired}))
    assert excinfo.value.status_code == 303


# --------------------------------------------------------------------------- #
# Redirect-shape distinction on the gated routes (HTTP).
# --------------------------------------------------------------------------- #
def test_wizard_unauth_plain_nav_303(client: Any) -> None:
    resp = client.get("/wizard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_wizard_unauth_htmx_hx_redirect(client: Any) -> None:
    resp = client.get("/wizard", headers={"HX-Request": "true"}, follow_redirects=False)
    assert resp.status_code == 401
    assert resp.headers.get("HX-Redirect") == "/login"


def test_run_unauth_htmx_hx_redirect_no_compute(client: Any) -> None:
    """The run route gates before any compute: no cookie + htmx → HX-Redirect."""
    resp = client.post("/wizard/run", data=_full_form(), headers={"HX-Request": "true"})
    assert resp.status_code == 401
    assert resp.headers.get("HX-Redirect") == "/login"


def test_authed_login_page_bounces_to_wizard(client: Any) -> None:
    _login(client)
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/wizard"


# --------------------------------------------------------------------------- #
# Results fragment on a canned surface (fast).
# --------------------------------------------------------------------------- #
def test_run_renders_full_results_fragment(client: Any) -> None:
    _login(client)
    resp = client.post("/wizard/run", data=_full_form(), headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.text
    assert "<html" not in body.lower()  # a fragment, not a page
    assert "results-panel" in body
    assert "1.46%" in body and "1.29x" in body  # KPI display strings verbatim
    assert "Sensitivity tornado" in body
    assert "Global sensitivity — Morris" in body
    assert "Capital risk (Monte Carlo)" in body
    # Download forms carry the exact submission as hidden fields.
    assert 'name="scenario_variant" value="lendercase"' in body
    assert 'action="/wizard/report.html"' in body
    assert 'target="_blank"' in body


def test_run_none_blocks_render_not_computed(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every omitted supplementary block renders a graceful "not computed" note."""
    import app.api.main as api_main

    monkeypatch.setattr(
        api_main,
        "build_case_surface",
        lambda _inputs: _canned_surface(
            tornado=None,
            global_sa_morris=None,
            global_sa_pawn=None,
            capital_risk=None,
        ),
    )
    _login(client)
    resp = client.post("/wizard/run", data=_full_form(), headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert resp.text.count("Not computed for this run") == 4


def test_run_validation_error_fragment_422(client: Any) -> None:
    _login(client)
    resp = client.post(
        "/wizard/run",
        data=_full_form(capacity_factor="5", capacity_mw="-1"),
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 422
    assert "Could not run the case" in resp.text
    assert "Traceback" not in resp.text


def test_run_rejects_missing_capacity_sync(client: Any) -> None:
    """#1023: capacity_mw / capacity_factor are Optional on the model only so the ASYNC path
    can derive them; the SYNC wizard must still REQUIRE them. A submission omitting both is
    rejected as a 422 error fragment (never silently run with a derived-away basis)."""
    _login(client)
    form = _full_form()
    del form["capacity_mw"]
    del form["capacity_factor"]
    resp = client.post("/wizard/run", data=form, headers={"HX-Request": "true"})
    assert resp.status_code == 422
    assert "Could not run the case" in resp.text
    # The per-field error names the missing sync-required fields.
    assert "capacity_mw" in resp.text
    assert "capacity_factor" in resp.text
    assert "Traceback" not in resp.text


def test_run_rejects_blank_capacity_sync(client: Any) -> None:
    """A blank capacity field (HTML posts ``capacity_mw=``, which the form parser drops) is
    treated as omitted and rejected on the sync wizard, same as a fully absent field."""
    _login(client)
    resp = client.post(
        "/wizard/run",
        data=_full_form(capacity_mw="", capacity_factor=""),
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 422
    assert "capacity_mw" in resp.text and "capacity_factor" in resp.text


def test_run_engine_rejection_renders_error_fragment(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An engine 400 (bad scenario) is re-rendered as the error fragment, not raw JSON/500."""
    from fastapi import HTTPException

    import app.api.main as api_main

    def _reject(_inputs: Any) -> Any:
        raise HTTPException(status_code=400, detail="Invalid scenario: AEP mismatch")

    monkeypatch.setattr(api_main, "build_case_surface", _reject)
    _login(client)
    resp = client.post("/wizard/run", data=_full_form(), headers={"HX-Request": "true"})
    assert resp.status_code == 400
    body = resp.text
    assert "Could not run the case" in body
    assert "AEP mismatch" in body
    assert not body.strip().startswith("{")  # not a raw JSON error body
    assert "Traceback" not in body


def test_run_escapes_user_input_xss(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.main as api_main

    xss = "<script>alert('xss')</script>"
    monkeypatch.setattr(
        api_main, "build_case_surface", lambda _inputs: _canned_surface(site_name=xss)
    )
    _login(client)
    resp = client.post(
        "/wizard/run", data=_full_form(site_name=xss), headers={"HX-Request": "true"}
    )
    assert resp.status_code == 200
    assert "<script>alert('xss')</script>" not in resp.text
    assert "&lt;script&gt;" in resp.text


# --------------------------------------------------------------------------- #
# Download routes (fast; artifact builders stubbed).
# --------------------------------------------------------------------------- #
def test_download_pdf(client: Any) -> None:
    _login(client)
    resp = client.post("/wizard/report.pdf", data=_full_form())
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert "attachment" in resp.headers["content-disposition"]


def test_download_validation_error_graceful(client: Any) -> None:
    _login(client)
    resp = client.post("/wizard/report.pdf", data={"site_name": ""})
    assert resp.status_code == 422
    assert "Could not run the case" in resp.text


def test_downloads_require_auth(client: Any) -> None:
    for path in ("/wizard/report.html", "/wizard/report.pdf", "/wizard/report.xlsx"):
        resp = client.post(path, data=_full_form(), follow_redirects=False)
        assert resp.status_code in (303, 401), f"{path} -> {resp.status_code}"


# --------------------------------------------------------------------------- #
# Additive wiring: /static mounted; /v1 + /health untouched.
# --------------------------------------------------------------------------- #
def test_static_mount_registered() -> None:
    from starlette.routing import Mount

    from app.api.main import app

    mounts = [r for r in app.routes if isinstance(r, Mount) and r.path == "/static"]
    assert mounts, "expected a /static StaticFiles mount"
    assert mounts[0].name == "static"


def test_health_unchanged(client: Any) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_v1_surface_still_requires_bearer(client: Any) -> None:
    """The wizard's cookie gate must not have loosened the /v1 bearer requirement."""
    resp = client.post("/v1/cases/surface", json={"site_name": "x"})
    assert resp.status_code == 401
