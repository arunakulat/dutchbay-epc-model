"""End-to-end tests for the #843 HTMX wizard frontend (app.web).

The wizard is a server-rendered, cookie-authenticated HTMX layer mounted at the
root of the existing FastAPI app (``app.api.main.app``). These tests drive it
through :class:`fastapi.testclient.TestClient` (httpx-backed) and assert the
route contract in the #843 spec:

* the cookie-based login / logout flow (a JWT in an ``HttpOnly`` cookie named
  ``dutchbay_session``);
* the cookie-auth gate on the wizard pages (no cookie ⇒ redirect to ``/login``);
* that ``POST /wizard/run`` actually invokes the *same* in-process
  :func:`app.api.main.build_case_surface` the ``/v1`` API uses (proved by a KPI
  label the real surface produces appearing in the rendered fragment);
* graceful degradation on bad user input — a rejected scenario renders an error
  fragment, never a 500;
* the XSS defence — a ``<script>`` payload in ``site_name`` is auto-escaped, so
  the raw tag never reaches the response body;
* the stateless workbook download re-runs the case and returns an ``.xlsx``.

Auth configuration is read from the environment on *every* call
(:mod:`app.api.auth`), so setting ``DUTCHBAY_JWT_SECRET`` / ``DUTCHBAY_API_USERS``
in the fixture (and leaving ``DUTCHBAY_ENV`` unset for the permissive dev posture)
is sufficient — no dependency overrides are needed. ``TestClient`` follows
redirects by default and persists cookies in its jar, so the 3xx assertions pass
``follow_redirects=False`` explicitly and the login cookie carries across calls.

The finance-touching routes (``/wizard/run``, ``/wizard/report.xlsx``) run the
real ~30 s lender case; those tests are marked ``slow`` (deselect with
``-m 'not slow'``) per the repo convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

# The whole suite drives the app over HTTP; skip cleanly if httpx is absent.
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402  (after importorskip)

from app.api.auth import hash_password  # noqa: E402
from app.api.main import app  # noqa: E402

#: The repository root (``tests/app/test_web_wizard.py`` → ``parents[2]``). Committed
#: scenarios declare their bankable-AEP artifact with a repo-root-relative path
#: (e.g. ``scenarios/aep_summary_dutchbay_10mw.json``) that the engine resolves against
#: the current working directory, so a finance run only succeeds when cwd is the repo
#: root. The ``_run_from_repo_root`` autouse fixture pins it so the run tests are
#: independent of where pytest was launched.
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The web session cookie the wizard sets (see ``app.web.auth_cookie``).
_SESSION_COOKIE = "dutchbay_session"
#: Test credentials provisioned into ``DUTCHBAY_API_USERS`` by the fixture.
_TEST_USER = "wizard"
_TEST_PASSWORD = "pw-123"
#: A >= 32-char signing secret. ``DUTCHBAY_ENV`` is left unset (dev posture), so a
#: short secret would be accepted, but the spec asks for a >= 32-char one.
_TEST_SECRET = "wizard-test-signing-secret-0123456789"


def _prefilled_form(**overrides: Any) -> Dict[str, Any]:
    """Return the wizard's prefilled DutchBay lendercase defaults as form data.

    These are the values the wizard ships pre-populated so a user can click *Run*
    immediately. They are verified to reconcile with the frozen lendercase AEP, so
    :func:`app.api.main.build_case_surface` completes (``status == "success"``)
    rather than raising the reconciliation guard.

    Args:
        **overrides: Fields to override on the base prefilled set (e.g. an invalid
            ``capacity_mw`` for the graceful-degradation test).

    Returns:
        A ``{field: value}`` mapping suitable for ``TestClient.post(..., data=...)``.
    """
    form: Dict[str, Any] = {
        "scenario_variant": "lendercase",
        "site_name": "Dutch Bay",
        "capacity_mw": 150,
        "capacity_factor": 0.35,
        "project_life_years": 25,
        "ppa_price_lkr_per_kwh": 22,
        "ppa_term_years": 20,
        "capex_total_usd": 167_860_000,
        "opex_annual_usd": 6_000_000,
        "fx_start_lkr_per_usd": 333.79,
    }
    form.update(overrides)
    return form


@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the working directory to the repo root for every test in this module.

    The wizard's finance routes run the real lender case, which resolves the scenario's
    bankable-AEP artifact via a repo-root-relative path against the process cwd. Without
    this, a run launched from another directory fails the AEP-provenance guard with a
    spurious ``400``. ``monkeypatch.chdir`` restores the original cwd after each test.
    """
    monkeypatch.chdir(_REPO_ROOT)


@pytest.fixture()
def web_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A ``TestClient`` with a single wizard user configured, dev auth posture.

    Provisions ``DUTCHBAY_JWT_SECRET`` and a one-user ``DUTCHBAY_API_USERS`` map
    (``wizard`` / ``pw-123``, PBKDF2-hashed via the app's own
    :func:`app.api.auth.hash_password`) and leaves ``DUTCHBAY_ENV`` unset so the
    permissive development posture is in effect (short secrets / no mandatory
    issuer-audience). Because auth reads the environment on every call, these
    ``setenv`` calls fully configure the surface.

    Returns:
        An unauthenticated client (no session cookie yet). Use
        :func:`_login` to obtain an authenticated client that carries the cookie.
    """
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setenv(
        "DUTCHBAY_API_USERS", f"{_TEST_USER}:{hash_password(_TEST_PASSWORD)}"
    )
    monkeypatch.delenv("DUTCHBAY_ENV", raising=False)
    return TestClient(app)


def _login(client: TestClient) -> TestClient:
    """Log the client in and return it with the session cookie in its jar.

    Posts valid credentials to ``/login`` without following the success redirect,
    asserts the ``303 -> /wizard`` + ``Set-Cookie`` handshake, and leaves the
    persisted ``dutchbay_session`` cookie on the client for subsequent requests.

    Args:
        client: An unauthenticated :class:`TestClient` (from :func:`web_client`).

    Returns:
        The same client, now authenticated (its cookie jar holds the session).
    """
    resp = client.post(
        "/login",
        data={"username": _TEST_USER, "password": _TEST_PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/wizard"
    assert _SESSION_COOKIE in client.cookies
    return client


# --------------------------------------------------------------------------- #
# Login page + authentication flow
# --------------------------------------------------------------------------- #
def test_get_login_renders_password_field(web_client: TestClient) -> None:
    """``GET /login`` returns the login page with a password input."""
    resp = web_client.get("/login")
    assert resp.status_code == 200
    assert 'type="password"' in resp.text


def test_login_success_sets_httponly_session_cookie(web_client: TestClient) -> None:
    """Valid credentials ⇒ 303 to /wizard and an HttpOnly session cookie is set."""
    resp = web_client.post(
        "/login",
        data={"username": _TEST_USER, "password": _TEST_PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/wizard"

    # The Set-Cookie header must name the session cookie and mark it HttpOnly so
    # the JWT is never reachable from JavaScript (the whole point of cookie auth).
    set_cookie = resp.headers["set-cookie"]
    assert _SESSION_COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()
    # TestClient persists the cookie in its jar for subsequent requests.
    assert _SESSION_COOKIE in web_client.cookies


def test_login_wrong_password_sets_no_cookie(web_client: TestClient) -> None:
    """Bad credentials ⇒ not authenticated and no session cookie is issued."""
    resp = web_client.post(
        "/login",
        data={"username": _TEST_USER, "password": "wrong-password"},
        follow_redirects=False,
    )
    # Re-render (401) rather than a redirect — and crucially, no cookie is set,
    # so a failed login cannot leave a partial/authenticated session behind.
    assert resp.status_code == 401
    assert _SESSION_COOKIE not in resp.headers.get("set-cookie", "")
    assert _SESSION_COOKIE not in web_client.cookies


def test_logout_clears_session_cookie(web_client: TestClient) -> None:
    """``POST /logout`` ⇒ 303 to /login and the session cookie is cleared."""
    client = _login(web_client)
    resp = client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    # The cookie is deleted (expired), so it no longer rides subsequent requests.
    assert _SESSION_COOKIE not in client.cookies


# --------------------------------------------------------------------------- #
# Cookie-auth gate on the wizard pages
# --------------------------------------------------------------------------- #
def test_get_wizard_without_cookie_redirects_to_login(web_client: TestClient) -> None:
    """``GET /wizard`` with no session cookie ⇒ a redirect to /login (303)."""
    # A fresh client (no login performed) has no session cookie.
    web_client.cookies.clear()
    resp = web_client.get("/wizard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_get_wizard_with_cookie_renders_form(web_client: TestClient) -> None:
    """``GET /wizard`` with a valid cookie ⇒ 200 and the multi-step form."""
    client = _login(web_client)
    resp = client.get("/wizard")
    assert resp.status_code == 200
    # The capacity input is one of the wizard's Step-1 fields; its presence proves
    # the form (not a redirect / login page) was rendered.
    assert 'name="capacity_mw"' in resp.text


# --------------------------------------------------------------------------- #
# POST /wizard/run — reuses the real build_case_surface (Dolphin: no duplicate
# finance logic). These run the full ~30 s lender case -> marked slow.
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_wizard_run_renders_results_fragment_with_kpi(web_client: TestClient) -> None:
    """A valid run returns 200 and a fragment carrying a real surface KPI label.

    The lendercase surface emits KPI cards labelled e.g. "Project IRR (nominal)",
    "Equity IRR" and "Minimum DSCR"; both "IRR" and "DSCR" substrings therefore
    appear only if :func:`app.api.main.build_case_surface` actually ran and its
    cards were rendered — the proof that the wizard reuses the /v1 compute path.
    """
    client = _login(web_client)
    resp = client.post("/wizard/run", data=_prefilled_form())
    assert resp.status_code == 200
    body = resp.text
    assert "IRR" in body
    assert "DSCR" in body


@pytest.mark.slow
def test_wizard_run_invalid_input_renders_error_not_500(
    web_client: TestClient,
) -> None:
    """An invalid field ⇒ an error fragment (200/422), never a 500.

    ``capacity_mw = -5`` fails the ``gt=0`` constraint, so parsing the form into
    :class:`app.models.inputs.WindFarmInputs` raises a Pydantic ``ValidationError``.
    The route must catch it and render ``_error.html.j2`` — a graceful client-error
    fragment — rather than letting it surface as an uncaught 500 (CASPER).
    """
    client = _login(web_client)
    resp = client.post("/wizard/run", data=_prefilled_form(capacity_mw="-5"))
    # Never a server error for bad *user* input.
    assert resp.status_code != 500
    assert resp.status_code in (200, 422)
    # The rendered fragment names the offending field; a stack trace must not leak.
    body = resp.text
    assert "capacity_mw" in body
    assert "Traceback" not in body


@pytest.mark.slow
def test_wizard_run_escapes_script_in_site_name(web_client: TestClient) -> None:
    """XSS: a ``<script>`` payload in ``site_name`` is auto-escaped in the output.

    ``site_name`` is free user text that satisfies the model constraints, so the
    case runs and the value is echoed back in the results fragment. Jinja2
    autoescaping (explicitly forced on for the ``.j2`` templates) must neutralise
    it, so the raw ``<script>alert(1)</script>`` tag never appears in the body.
    """
    client = _login(web_client)
    resp = client.post(
        "/wizard/run",
        data=_prefilled_form(site_name="<script>alert(1)</script>"),
    )
    assert resp.status_code == 200
    # The raw, unescaped tag must be absent (it would be HTML-entity-escaped).
    assert "<script>alert(1)</script>" not in resp.text


# --------------------------------------------------------------------------- #
# Artifact download — the stateless workbook re-run.
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_wizard_report_xlsx_returns_workbook(web_client: TestClient) -> None:
    """``POST /wizard/report.xlsx`` with valid inputs ⇒ 200 and an .xlsx payload.

    Proves the download route is cookie-authenticated (not a 401) and re-runs the
    case statelessly, returning the Office Open XML spreadsheet content type.
    """
    client = _login(web_client)
    resp = client.post("/wizard/report.xlsx", data=_prefilled_form())
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert (
        "spreadsheetml.sheet" in content_type
        or "application/vnd.openxmlformats" in content_type
    )
