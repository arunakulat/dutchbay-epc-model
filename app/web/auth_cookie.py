"""Cookie-based session gate for the HTMX wizard (CASPER / CESSPIT).

The versioned JSON API (:mod:`app.api.main`) authenticates with a ``Bearer`` token in
the ``Authorization`` header, which suits a programmatic client but not a browser page:
storing a bearer token in JavaScript exposes it to XSS exfiltration. The wizard therefore
carries the *same* signed ``HS256`` JWT in an **``httpOnly``** cookie, so the token is
sent automatically by the browser yet is never readable by page scripts.

This module owns only the *cookie transport* — it deliberately re-uses the canonical
crypto and configuration from :mod:`app.api.auth` (``decode_token``, ``_jwt_secret``,
``_jwt_issuer``, ``_jwt_audience``, ``_is_production``) rather than re-implementing any
JWT logic (Dolphin: one signing/validation path, no forked copy to drift). The token is
minted elsewhere (:func:`app.api.auth.login_for_access_token`); here we merely set it,
clear it, and validate a presented one.

Security posture:

* The cookie is ``httponly`` (no JS access), ``samesite="lax"`` (sent on top-level
  navigations, not on cross-site sub-requests — a pragmatic CSRF mitigation for a
  GET-navigable login flow), and ``secure`` **only in production**
  (:func:`app.api.auth._is_production`) so local development over plain ``http://``
  still works while a real deployment refuses to send the cookie over cleartext.
* Validation is fail-closed: an absent, malformed, forged, or expired token is an
  authentication failure. On failure the dependency redirects the browser to
  ``/login`` — via an ``HX-Redirect`` response header when the request came from HTMX
  (so htmx performs a *full-page* redirect instead of swapping a 401 body into a
  fragment), or via a plain ``303`` ``Location`` redirect otherwise.
* A *server misconfiguration* (unset ``DUTCHBAY_JWT_SECRET``) still surfaces as the
  ``500`` that :func:`app.api.auth._jwt_secret` raises — that fail-closed behaviour is
  intentional and is left to propagate (an unconfigured secret must not be papered over
  as "just log in again").
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request, Response, status

from app.api.auth import (
    AuthError,
    _is_production,
    _jwt_audience,
    _jwt_issuer,
    _jwt_secret,
    decode_token,
)

#: Name of the session cookie carrying the signed JWT. Distinct from the ``Authorization``
#: header the JSON API uses, so the two surfaces never contend for the same credential slot.
COOKIE_NAME = "dutchbay_session"

#: Session cookie lifetime (seconds). Matched to the access token's own default TTL
#: (:data:`app.api.auth._DEFAULT_TOKEN_TTL_SECONDS` = 3600) so the cookie does not linger
#: in the browser past the point where the token it carries has expired anyway.
COOKIE_MAX_AGE_SECONDS = 3600

#: Cookie path — root, so the single session cookie is presented to every wizard route.
_COOKIE_PATH = "/"

#: ``SameSite`` policy for the session cookie (see the module docstring for the rationale).
#: Typed as a ``Literal`` so it satisfies ``Response.set_cookie``'s ``samesite`` parameter.
_COOKIE_SAMESITE: Literal["lax"] = "lax"

#: The HTMX request marker. htmx sets ``HX-Request: true`` on every request it issues; its
#: presence is how the gate decides between an ``HX-Redirect`` header and a ``303`` redirect.
_HX_REQUEST_HEADER = "HX-Request"

#: The response header htmx honours to perform a client-side full-page navigation.
_HX_REDIRECT_HEADER = "HX-Redirect"

#: Where an unauthenticated (or logged-out) visitor is sent.
_LOGIN_PATH = "/login"


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the signed JWT to ``response`` as the ``httpOnly`` session cookie.

    Called after a successful login. The cookie is ``httponly`` (unreadable by page
    JavaScript), ``samesite="lax"``, and ``secure`` only in a production posture
    (:func:`app.api.auth._is_production`) so the same code path works over plain
    ``http://localhost`` in development and refuses cleartext transport in production.

    Args:
        response: The outgoing response (typically the ``303`` redirect to ``/wizard``)
            to set the cookie on.
        token: The signed ``HS256`` JWT to store (produced by
            :func:`app.api.auth.login_for_access_token`).
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_is_production(),
        path=_COOKIE_PATH,
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie from the browser (logout).

    Deletes with the *same* ``path``/``samesite``/``secure`` attributes the cookie was
    set with, so the browser reliably matches and drops it (a mismatched attribute set
    can leave a "deleted" cookie stranded).

    Args:
        response: The outgoing response (typically the ``303`` redirect to ``/login``)
            to expire the cookie on.
    """
    response.delete_cookie(
        key=COOKIE_NAME,
        path=_COOKIE_PATH,
        samesite=_COOKIE_SAMESITE,
        secure=_is_production(),
    )


def _redirect_to_login(request: Request) -> HTTPException:
    """Build the "go to the login page" failure for an unauthenticated request.

    Returns an :class:`fastapi.HTTPException` shaped for how the request arrived:

    * **From htmx** (``HX-Request`` header present) — a ``401`` carrying an
      ``HX-Redirect: /login`` header. htmx intercepts this and does a *full-page*
      browser navigation to the login page, instead of swapping a ``401`` error body
      into the ``#results`` fragment target.
    * **A plain browser navigation** — a ``303 See Other`` with a ``Location: /login``
      header, so the browser simply follows the redirect to the login page.

    Args:
        request: The incoming request (inspected for the ``HX-Request`` marker).

    Returns:
        The :class:`fastapi.HTTPException` to raise from the dependency.
    """
    if request.headers.get(_HX_REQUEST_HEADER):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={_HX_REDIRECT_HEADER: _LOGIN_PATH},
        )
    return HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Not authenticated",
        headers={"Location": _LOGIN_PATH},
    )


def require_web_user(request: Request) -> str:
    """FastAPI dependency: resolve the session-cookie JWT to its subject, or redirect.

    Reads the :data:`COOKIE_NAME` cookie and validates it by *reusing*
    :func:`app.api.auth.decode_token` with the server's configured secret, issuer, and
    audience — the identical validation the JSON API's bearer path uses, so a token is
    accepted here iff it would be accepted there (no forked crypto). An absent or invalid
    token is an authentication failure that redirects the visitor to ``/login`` (an
    ``HX-Redirect`` header for htmx requests, a ``303`` otherwise; see
    :func:`_redirect_to_login`).

    Args:
        request: The incoming request, whose cookies carry the session token.

    Returns:
        The authenticated subject (the token's ``sub`` claim).

    Raises:
        HTTPException: ``401`` with an ``HX-Redirect: /login`` header (htmx requests) or
            ``303`` to ``/login`` (plain navigations) when the token is missing, malformed,
            forged, or expired. ``500`` propagates unchanged from
            :func:`app.api.auth._jwt_secret` when the signing secret is unconfigured
            (fail-closed — a server misconfiguration, not a login prompt).
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _redirect_to_login(request)
    # `_jwt_secret()` may raise HTTPException(500) when unconfigured — intentional
    # fail-closed behaviour, left to propagate rather than being masked as a login redirect.
    secret = _jwt_secret()
    try:
        return decode_token(
            token,
            secret=secret,
            issuer=_jwt_issuer(),
            audience=_jwt_audience(),
        )
    except AuthError as exc:
        raise _redirect_to_login(request) from exc
