"""HTMX wizard routes — the ``#843`` backend-for-frontend, mounted at the app root.

This :class:`fastapi.APIRouter` is the human-facing web UI: a cookie-authenticated login
flow and a four-step wind-farm case wizard. Every compute action **reuses the exact
in-process functions the versioned ``/v1`` JSON API calls** — :func:`build_case_surface`
for the on-page results, and :func:`run_case_report_html` / :func:`run_case_report_pdf` /
:func:`run_case_workbook` for the downloads — so there is zero duplicated finance logic
(Dolphin / CCCDIR). The finance engine is never touched here; this module only maps a
submitted HTML form to :class:`app.models.inputs.WindFarmInputs` and renders the result.

Route surface (all at the application root, *no* ``/v1`` prefix — the versioned data API
owns ``/v1``; this is the UI):

======================  =========================================================
``GET  /``              ``303`` redirect to ``/wizard``.
``GET  /login``         The login page (already-authed visitors are sent to ``/wizard``).
``POST /login``         Authenticate; on success set the session cookie + ``303`` to
                        ``/wizard``; on failure re-render the login page with a ``401``
                        banner and *no* cookie.
``POST /logout``        Clear the session cookie + ``303`` to ``/login``.
``GET  /wizard``        The multi-step wizard page (cookie-auth).
``POST /wizard/run``    Parse the form → run the case → render the results *fragment*
                        (cookie-auth). Bad user input renders the error fragment, never
                        a ``500``.
``POST /wizard/report.{html,pdf,xlsx}``
                        Re-run statelessly and stream the corresponding artifact
                        (cookie-auth).
======================  =========================================================

**Form parsing without ``python-multipart``.** The strict ``requirements.txt`` lock does
not include ``python-multipart``, and Starlette's ``request.form()`` hard-requires it even
for ``application/x-www-form-urlencoded`` bodies. Rather than add a dependency (which would
also disturb the ``pip-audit`` gate), this module parses the urlencoded body itself with
the stdlib (:func:`urllib.parse.parse_qsl`) — the same "stdlib-only, no new dependency"
discipline :mod:`app.api.auth` already follows. Empty-string fields (an HTML form submits
``debt_ratio=`` for a blank optional) are dropped so Pydantic applies the field default or
``None`` instead of failing to coerce ``""`` to a number.

**Autoescaping.** The Jinja2 environment is built with ``autoescape=True`` set explicitly
(a ``.j2`` extension defeats ``select_autoescape``; the report renderer once shipped that
gap). User-supplied fields — the site name and location — are therefore always HTML-escaped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from analytics.aep_provenance import AepProvenanceError
from analytics.aep_reconciliation import AepReconciliationError
from analytics.schema_guard import ConfigValidationError
from app.api.auth import AuthError, login_for_access_token
from app.models.inputs import WindFarmInputs
from app.web.auth_cookie import (
    clear_session_cookie,
    require_web_user,
    set_session_cookie,
)

# NOTE on the deliberately *lazy* import of the case-run functions
# (``build_case_surface`` / ``run_case_report_html`` / ``run_case_report_pdf`` /
# ``run_case_workbook``): they live in :mod:`app.api.main`, which in turn imports *this*
# module at the bottom of its file to mount the wizard router. Importing them here at module
# top-level would form an import cycle that breaks whenever ``app.web.routes`` is imported
# before ``app.api.main`` (e.g. a test importing the router directly). Resolving them inside
# each handler — after both modules are fully initialised at request time — keeps the reuse
# (one finance path, no forked logic; Dolphin/CCCDIR) without the fragile cycle. See
# :func:`_case_runners`.


def _case_runners() -> Any:
    """Return the :mod:`app.api.main` module, imported lazily to avoid an import cycle.

    :mod:`app.api.main` imports this module to mount the wizard router, so a top-level
    import back into it would be circular. Deferring the import to call time (both modules
    are fully loaded by the time a request runs) lets the handlers reuse the canonical
    case-run functions — :func:`app.api.main.build_case_surface`,
    :func:`app.api.main.run_case_report_html`, :func:`app.api.main.run_case_report_pdf`, and
    :func:`app.api.main.run_case_workbook` — without duplicating any of them.

    Returns:
        The imported :mod:`app.api.main` module.
    """
    import app.api.main as case_api

    return case_api


# --------------------------------------------------------------------------- #
# Template environment (autoescape forced ON — user input is HTML-escaped).
# --------------------------------------------------------------------------- #
#: Directory of the wizard's Jinja2 templates, resolved relative to this file so it is
#: independent of the process working directory.
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

#: The Jinja2 template registry. Constructed as :class:`fastapi.templating.Jinja2Templates`
#: (per the #843 design) with autoescaping *explicitly* enabled on the underlying
#: environment: a ``.j2`` filename would otherwise slip past ``select_autoescape`` and leave
#: ``site_name`` / ``location`` un-escaped (the exact XSS gap the report renderer once had).
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
templates.env.autoescape = True
templates.env.trim_blocks = True
templates.env.lstrip_blocks = True

router = APIRouter(tags=["web"])

#: HTTP 422 (Unprocessable Content) for a bad-input error fragment. Kept as the integer
#: literal — matching :mod:`api.pipeline_api` — because Starlette has deprecated its
#: ``HTTP_422_UNPROCESSABLE_ENTITY`` name (accessing the constant emits a deprecation
#: warning), and the numeric code is stable regardless of the constant's churn.
_HTTP_422_UNPROCESSABLE = 422


# --------------------------------------------------------------------------- #
# Rendering + form-parsing helpers.
# --------------------------------------------------------------------------- #
def _render(template_name: str, **context: Any) -> str:
    """Render a wizard template to a string through the autoescaping environment.

    Rendering goes via ``templates.env`` directly (rather than
    :meth:`Jinja2Templates.TemplateResponse`) so no ``request`` object has to thread
    through the template context; the caller wraps the returned string in the response
    type it needs (a full :class:`HTMLResponse` page or an HTMX fragment).

    Args:
        template_name: The template file name within ``app/web/templates``.
        **context: Template variables (all string-valued user input is auto-escaped).

    Returns:
        The rendered HTML as a string.
    """
    return templates.env.get_template(template_name).render(**context)


async def _parse_form(request: Request) -> Dict[str, str]:
    """Parse an ``application/x-www-form-urlencoded`` request body with the stdlib.

    Reads the raw body and decodes it with :func:`urllib.parse.parse_qsl` — avoiding
    Starlette's ``request.form()`` (which requires the un-vendored ``python-multipart``).
    Empty-string values are *dropped*: an HTML form posts ``debt_ratio=`` for a blank
    optional number, and forwarding ``""`` would make Pydantic raise "unable to parse
    string as a number" instead of applying the field's default/``None``. Fields the user
    genuinely left blank thus fall back to their model default; a truly missing *required*
    field still fails validation and routes to the error fragment.

    Args:
        request: The incoming ``POST`` whose body carries the urlencoded form.

    Returns:
        A ``{field: value}`` mapping with empty values omitted. On a duplicated key the
        last value wins (standard HTML form semantics).
    """
    raw = await request.body()
    pairs = parse_qsl(raw.decode("utf-8"), keep_blank_values=True)
    return {key: value for key, value in pairs if value != ""}


#: Fields the SYNC wizard must carry. ``capacity_mw`` / ``capacity_factor`` are Optional on
#: :class:`WindFarmInputs` only so the ASYNC live-ERA5 path (#1023) may derive them from the
#: turbine layout + p_level; the sync wizard re-derives nothing, so it still requires both.
_SYNC_REQUIRED_FIELDS = ("capacity_mw", "capacity_factor")


def _inputs_from_form(form: Dict[str, str]) -> WindFarmInputs:
    """Validate a parsed form mapping into a :class:`WindFarmInputs`.

    Pydantic coerces the string form values to the model's typed fields (e.g. ``"150"`` →
    ``150.0``) and enforces every physical constraint; a malformed submission raises
    :class:`pydantic.ValidationError`, which the caller turns into the error fragment.

    ``capacity_mw`` / ``capacity_factor`` are Optional on the model so the async wind path
    (#1023) can OMIT them (they are derived from ``num_turbines × turbine nameplate`` and the
    selected ``p_level`` and then overwritten by the screening seam, #997). The SYNC wizard
    derives nothing, so both stay **required here** — an omission is rejected with the exact
    same ``pydantic.ValidationError`` (``type='missing'``) shape the route already normalises
    into per-field error rows. This keeps the sync contract unweakened by the async change.

    Args:
        form: The ``{field: value}`` mapping from :func:`_parse_form`.

    Returns:
        The validated wizard inputs.

    Raises:
        ValidationError: If any field is missing, mistyped, or out of range — including a
            sync-required capacity / capacity factor omitted from the form.
    """
    inputs = WindFarmInputs.model_validate(form)
    missing = [name for name in _SYNC_REQUIRED_FIELDS if getattr(inputs, name) is None]
    if missing:
        raise ValidationError.from_exception_data(
            WindFarmInputs.__name__,
            [{"type": "missing", "loc": (name,), "input": form} for name in missing],
        )
    return inputs


def _field_error_fragment(
    field_errors: list[Dict[str, str]], *, status_code: int
) -> HTMLResponse:
    """Render the ``_error`` fragment from per-field validation errors.

    Shows only the field location and human-readable message from each Pydantic error —
    never a traceback or internal detail — via the template's ``field_errors`` block.
    Returned with a client-error status (``422``) so the response is honest, while HTMX
    still swaps the fragment into ``#results`` (htmx swaps on non-2xx too).

    Args:
        field_errors: Normalised ``{"field": ..., "message": ...}`` rows to display.
        status_code: The HTTP status for the response (``422`` for bad input).

    Returns:
        The rendered error fragment as an :class:`HTMLResponse`.
    """
    return HTMLResponse(
        content=_render("_error.html.j2", field_errors=field_errors),
        status_code=status_code,
    )


def _message_error_fragment(message: str, *, status_code: int) -> HTMLResponse:
    """Render the ``_error`` fragment from a single domain-error summary line.

    Used for an engine integrity rejection (a scenario the finance engine refuses), which
    surfaces as one contract message rather than per-field errors. Fed to the template's
    ``message`` block.

    Args:
        message: The sanitised summary line to display.
        status_code: The HTTP status for the response (``422`` for bad input).

    Returns:
        The rendered error fragment as an :class:`HTMLResponse`.
    """
    return HTMLResponse(
        content=_render("_error.html.j2", message=message),
        status_code=status_code,
    )


def _normalise_validation_error(exc: ValidationError) -> list[Dict[str, str]]:
    """Reduce a :class:`pydantic.ValidationError` to safe ``{field, message}`` rows.

    Args:
        exc: The validation error raised while building :class:`WindFarmInputs`.

    Returns:
        One row per underlying error, each with a dotted field path and the message.
    """
    rows: list[Dict[str, str]] = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", ())) or "(form)"
        rows.append(
            {"field": location, "message": str(err.get("msg", "invalid value"))}
        )
    return rows


async def _inputs_or_error(
    request: Request,
) -> tuple[Optional[WindFarmInputs], Optional[HTMLResponse]]:
    """Parse + validate the request form, returning either the inputs or an error fragment.

    Centralises the "parse the form, and on bad input hand back the ``_error`` fragment
    instead of a ``500``" contract shared by ``/wizard/run`` and the three download routes.

    Args:
        request: The incoming ``POST`` carrying the wizard form.

    Returns:
        ``(inputs, None)`` when the form validates, or ``(None, error_response)`` when it
        does not (the caller returns the error response as-is).
    """
    form = await _parse_form(request)
    try:
        return _inputs_from_form(form), None
    except ValidationError as exc:
        return None, _field_error_fragment(
            _normalise_validation_error(exc),
            status_code=_HTTP_422_UNPROCESSABLE,
        )


# --------------------------------------------------------------------------- #
# Login / logout.
# --------------------------------------------------------------------------- #
@router.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    """Redirect the site root to the wizard (which itself gates on the session cookie)."""
    return RedirectResponse(url="/wizard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request) -> Response:
    """Render the login page, or bounce an already-authenticated visitor to the wizard.

    If a valid session cookie is already present there is no reason to show the form, so
    the visitor is redirected straight to ``/wizard``. The cookie check reuses
    :func:`require_web_user` semantics but must not itself redirect *here* (an invalid
    cookie should render the login form, not loop), so it is called defensively.

    Args:
        request: The incoming request (its cookies decide authed-vs-anonymous).

    Returns:
        A ``303`` redirect to ``/wizard`` when already authed, else the login page.
    """
    if _has_valid_session(request):
        return RedirectResponse(url="/wizard", status_code=status.HTTP_303_SEE_OTHER)
    return HTMLResponse(content=_render("login.html.j2", error=None))


@router.post("/login", include_in_schema=False)
async def login_submit(request: Request) -> Response:
    """Authenticate submitted credentials; set the session cookie on success.

    On valid credentials, mint a JWT via :func:`app.api.auth.login_for_access_token`
    (reused — no auth logic here), attach it as the ``httpOnly`` session cookie, and
    ``303``-redirect to ``/wizard``. On bad credentials, re-render the login page with an
    error banner and a ``401`` status, and set *no* cookie. A ``500`` from an unconfigured
    signing secret propagates unchanged (fail-closed).

    Args:
        request: The incoming ``POST`` carrying ``username`` and ``password``.

    Returns:
        A ``303`` redirect (success, with the cookie) or the ``401`` login page (failure).
    """
    form = await _parse_form(request)
    username = form.get("username", "")
    password = form.get("password", "")
    try:
        token = login_for_access_token(username, password)
    except AuthError:
        # Defensive: login_for_access_token raises HTTPException(401), not AuthError, but a
        # future refactor could surface AuthError — treat both as a failed login, not a 500.
        return _login_failure()
    except (
        Exception
    ) as exc:  # noqa: BLE001 — narrow immediately below; re-raise otherwise.
        if _is_bad_credentials(exc):
            return _login_failure()
        raise
    response = RedirectResponse(url="/wizard", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, token)
    return response


@router.post("/logout", include_in_schema=False)
def logout() -> Response:
    """Clear the session cookie and redirect to the login page."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response


# --------------------------------------------------------------------------- #
# Wizard page + run + downloads (all cookie-gated via require_web_user).
# --------------------------------------------------------------------------- #
@router.get("/wizard", response_class=HTMLResponse, include_in_schema=False)
def wizard_page(subject: str = Depends(require_web_user)) -> HTMLResponse:
    """Render the multi-step wizard (the DutchBay lender-case defaults are baked in).

    Gated by the session cookie via ``Depends(require_web_user)`` — an unauthenticated
    visitor is redirected to ``/login`` before the handler runs. The page carries an empty
    ``#results`` container that the "Run" button's ``hx-post="/wizard/run"`` fills in place.
    The template hard-codes the pre-filled default field values, so no context is needed.

    Args:
        subject: The authenticated subject, injected by :func:`require_web_user`.

    Returns:
        The wizard page as an :class:`HTMLResponse`.
    """
    return HTMLResponse(content=_render("wizard.html.j2"))


@router.post("/wizard/run", include_in_schema=False)
async def wizard_run(
    request: Request, subject: str = Depends(require_web_user)
) -> HTMLResponse:
    """Run a case from the submitted form and render the results *fragment*.

    The wizard's Run button posts here with ``hx-target="#results"
    hx-swap="innerHTML"``. The form is parsed and validated into
    :class:`WindFarmInputs`; the case is projected via :func:`build_case_surface` (the same
    function ``POST /v1/cases/surface`` uses) off the event loop with
    :func:`run_in_threadpool`; and the ``_results`` fragment is returned. Any bad-input
    failure renders the ``_error`` fragment with a client-error status, never a ``500``:

    * Pydantic :class:`ValidationError` (handled in :func:`_inputs_or_error`), and
    * an engine integrity rejection — :class:`ConfigValidationError` /
      :class:`AepReconciliationError` / :class:`AepProvenanceError`. ``build_case_surface``
      already *wraps* these as an ``HTTPException(400, "Invalid scenario: …")`` (its
      ``/v1`` contract), so both the wrapped ``400`` and the bare exception types are
      caught here and re-rendered as the ``_error`` fragment (a JSON ``400`` swapped into
      ``#results`` would be poor UX).

    Args:
        request: The (authenticated) ``POST`` carrying the wizard form.
        subject: The authenticated subject, injected by :func:`require_web_user`.

    Returns:
        The ``_results`` fragment on success, or the ``_error`` fragment on bad input.
    """
    inputs, error = await _inputs_or_error(request)
    if error is not None:
        return error
    assert inputs is not None  # narrowed by the error branch above (mypy aid).
    try:
        surface = await run_in_threadpool(_case_runners().build_case_surface, inputs)
    except (
        ConfigValidationError,
        AepReconciliationError,
        AepProvenanceError,
    ) as exc:
        # Defensive: build_case_surface currently wraps these as HTTPException(400) (caught
        # below), but a future refactor could let a bare engine error through — treat it as
        # bad input either way, never a 500.
        return _engine_error_fragment(exc)
    except HTTPException as exc:
        # The bad-scenario 400 (and any 422) that build_case_surface raises for an engine
        # rejection is user-fixable input — render the error fragment. A non-input failure
        # (e.g. a 503 capacity-shed, or a 500 misconfiguration) is re-raised unchanged so it
        # keeps its real HTTP semantics rather than masquerading as a validation error.
        if exc.status_code in (
            status.HTTP_400_BAD_REQUEST,
            _HTTP_422_UNPROCESSABLE,
        ):
            return _http_error_fragment(exc)
        raise
    # The template consumes ``surface`` (the CaseSurface) for the KPIs/charts and the raw
    # ``inputs`` model for the hidden download fields (its ``hidden_inputs`` macro reads the
    # attributes and their ``is not none`` state directly). Bar widths are computed inside
    # the template, so nothing else is passed.
    return HTMLResponse(
        content=_render("_results.html.j2", surface=surface, inputs=inputs)
    )


@router.post("/wizard/report.html", include_in_schema=False)
async def wizard_report_html(
    request: Request, subject: str = Depends(require_web_user)
) -> Response:
    """Re-run statelessly and return the full HTML report (opened in a new tab).

    Reuses :func:`run_case_report_html`. Bad user input renders the ``_error`` fragment
    rather than erroring, matching ``/wizard/run``.

    Args:
        request: The (authenticated) ``POST`` carrying the same submitted inputs.
        subject: The authenticated subject, injected by :func:`require_web_user`.

    Returns:
        The HTML report, or the ``_error`` fragment on bad input.
    """
    inputs, error = await _inputs_or_error(request)
    if error is not None:
        return error
    assert inputs is not None
    return await run_in_threadpool(_case_runners().run_case_report_html, inputs)


@router.post("/wizard/report.pdf", include_in_schema=False)
async def wizard_report_pdf(
    request: Request, subject: str = Depends(require_web_user)
) -> Response:
    """Re-run statelessly and return the PDF report.

    Reuses :func:`run_case_report_pdf` (which itself returns a ``503`` when the optional
    WeasyPrint backend is absent). Bad user input renders the ``_error`` fragment.

    Args:
        request: The (authenticated) ``POST`` carrying the same submitted inputs.
        subject: The authenticated subject, injected by :func:`require_web_user`.

    Returns:
        The PDF report, or the ``_error`` fragment on bad input.
    """
    inputs, error = await _inputs_or_error(request)
    if error is not None:
        return error
    assert inputs is not None
    return await run_in_threadpool(_case_runners().run_case_report_pdf, inputs)


@router.post("/wizard/report.xlsx", include_in_schema=False)
async def wizard_report_xlsx(
    request: Request, subject: str = Depends(require_web_user)
) -> Response:
    """Re-run statelessly and return the executive workbook (.xlsx).

    Reuses :func:`run_case_workbook`. Bad user input renders the ``_error`` fragment.

    Args:
        request: The (authenticated) ``POST`` carrying the same submitted inputs.
        subject: The authenticated subject, injected by :func:`require_web_user`.

    Returns:
        The workbook, or the ``_error`` fragment on bad input.
    """
    inputs, error = await _inputs_or_error(request)
    if error is not None:
        return error
    assert inputs is not None
    return await run_in_threadpool(_case_runners().run_case_workbook, inputs)


# --------------------------------------------------------------------------- #
# Auth helpers (reuse app.web.auth_cookie / app.api.auth — no forked logic).
# --------------------------------------------------------------------------- #
def _has_valid_session(request: Request) -> bool:
    """Return whether the request carries a valid session cookie (no redirect raised).

    Used by the login page to decide whether to bounce an already-authed visitor to the
    wizard. A ``500`` from an unconfigured secret is *not* swallowed — that must still
    surface — but an ordinary "no/invalid cookie" is reported as ``False`` so the login
    form renders instead of redirect-looping.

    Args:
        request: The incoming request to inspect.

    Returns:
        ``True`` iff :func:`require_web_user` accepts the cookie.
    """
    try:
        require_web_user(request)
        return True
    except (
        Exception
    ) as exc:  # noqa: BLE001 — re-raise a misconfiguration, else "not authed".
        if _is_server_misconfig(exc):
            raise
        return False


def _login_failure() -> HTMLResponse:
    """Render the login page with an error banner and a ``401`` status (no cookie set)."""
    return HTMLResponse(
        content=_render("login.html.j2", error="Incorrect username or password."),
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


def _is_bad_credentials(exc: Exception) -> bool:
    """Return whether ``exc`` is the ``401`` bad-credentials failure (vs a ``500``).

    :func:`app.api.auth.login_for_access_token` raises ``HTTPException(401)`` for bad
    credentials and ``HTTPException(500)`` (via ``_jwt_secret``) for an unconfigured secret.
    Only the former should become the re-rendered login page; a ``500`` must propagate.

    Args:
        exc: The exception raised by the login attempt.

    Returns:
        ``True`` for a ``401`` credentials failure, ``False`` otherwise.
    """
    return getattr(exc, "status_code", None) == status.HTTP_401_UNAUTHORIZED


def _is_server_misconfig(exc: Exception) -> bool:
    """Return whether ``exc`` is a ``500`` server-misconfiguration (must not be swallowed)."""
    return getattr(exc, "status_code", None) == status.HTTP_500_INTERNAL_SERVER_ERROR


def _engine_error_fragment(exc: Exception) -> HTMLResponse:
    """Render the ``_error`` fragment for an engine integrity rejection (bad scenario).

    :class:`ConfigValidationError` / :class:`AepReconciliationError` /
    :class:`AepProvenanceError` mean the user's edits produced a scenario the engine
    refuses (e.g. a capacity/CF change beyond the AEP reconciliation tolerance). That is
    bad *input*, so it renders the error fragment (as a single summary ``message``) with a
    ``422`` — never a ``500``.

    Args:
        exc: The engine rejection to surface.

    Returns:
        The ``_error`` fragment as an :class:`HTMLResponse`.
    """
    return _message_error_fragment(str(exc), status_code=_HTTP_422_UNPROCESSABLE)


def _http_error_fragment(exc: HTTPException) -> HTMLResponse:
    """Render the ``_error`` fragment from a bad-input :class:`fastapi.HTTPException`.

    ``build_case_surface`` reports an engine-rejected scenario as an
    ``HTTPException(400, "Invalid scenario: …")``. That ``detail`` is already a sanitised,
    human-readable string (no traceback), so it is shown as the fragment's summary
    ``message``. The fragment carries the exception's own status code (``400``/``422``).

    Args:
        exc: The bad-input HTTP exception raised by the reused case-run function.

    Returns:
        The ``_error`` fragment as an :class:`HTMLResponse`.
    """
    detail = exc.detail if isinstance(exc.detail, str) else "The scenario was rejected."
    return _message_error_fragment(detail, status_code=exc.status_code)
