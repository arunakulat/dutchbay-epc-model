"""HTTP security-response hardening for the web surface (CASPER / #944).

A pure-ASGI middleware that stamps a fixed set of security headers on **every** HTTP
response and — in a production posture (:func:`app.api.auth._is_production`, the
``DUTCHBAY_ENV`` switch #858 added) — takes the interactive API docs offline.

Why a pure-ASGI middleware (not :class:`starlette.middleware.base.BaseHTTPMiddleware`):
the job-progress endpoint streams Server-Sent Events (``StreamingResponse``); a
middleware that buffered the body to mutate it would defeat that stream. This one only
rewrites the ``http.response.start`` message's header block, so a streaming body passes
through untouched.

Header posture
--------------
* ``X-Content-Type-Options: nosniff`` — never MIME-sniff a response body.
* ``X-Frame-Options: DENY`` **and** the CSP ``frame-ancestors 'none'`` directive —
  belt-and-braces clickjacking defence (the legacy header for old engines, the CSP
  directive for modern ones).
* ``Referrer-Policy: no-referrer`` — never leak an internal URL in the ``Referer``.
* ``Content-Security-Policy`` — a minimal policy for the HTMX wizard: same-origin by
  default, with ``'unsafe-inline'`` still permitted for scripts **and** styles because
  the wizard ships an inline bootstrap ``<script>`` (``base.html.j2`` /
  ``wizard.html.j2``) and inline ``style="width:…%"`` progress bars
  (``_results.html.j2``). Tightening this to a nonce/hash allow-list is a documented
  follow-up (it means threading a per-request nonce through every template), not a
  silent expansion of this change.
* ``Strict-Transport-Security`` — emitted **only** in the production posture. In dev the
  app is reached over plain ``http://localhost`` and an HSTS pin there is a footgun;
  #858's switch is exactly the production gate, reused here (not re-derived) so the two
  stay in lockstep.

Docs posture (#944 decision)
----------------------------
For a B2B tool the least-surprising posture is: keep the interactive Swagger UI + raw
OpenAPI schema in *development* (they are genuinely useful locally), but serve ``404``
for ``/docs``, ``/redoc`` and ``/openapi.json`` in *production*. The route descriptions
embed internal engineering notes (issue refs, backend implementation detail) — a pure
recon surface with no benefit to an integrating client, who consumes the frozen ``/v1``
contract (with its pinned ``operation_id``\\ s), not Swagger. ``404`` (rather than
``401``) is deliberate: the surface simply looks absent, leaking nothing about what
sits behind it. The gate is docs-only — ``/health`` and every ``/v1`` route are
untouched.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.auth import _is_production

#: Minimal CSP for the HTMX wizard. ``default-src 'self'`` locks fetch/connect/font/etc.
#: to same-origin; ``script-src``/``style-src`` additionally permit ``'unsafe-inline'``
#: (see the module docstring for why); ``img-src`` permits ``data:`` for embedded chart
#: images. ``frame-ancestors``, ``base-uri``, ``form-action`` and ``object-src`` do NOT
#: fall back to ``default-src``, so each is stated explicitly.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

#: Always-on security headers (independent of deployment posture). Keys are lower-cased
#: because that is how they are written into the raw ASGI header list.
_STATIC_SECURITY_HEADERS: dict[str, str] = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "content-security-policy": _CONTENT_SECURITY_POLICY,
}

#: HSTS value emitted only in the production posture (2 years + subdomains). Deliberately
#: NOT part of :data:`_STATIC_SECURITY_HEADERS` so dev never pins ``http://localhost``.
_HSTS_VALUE = "max-age=63072000; includeSubDomains"

#: The interactive-docs + raw-schema paths taken offline (404) in the production posture.
_PRODUCTION_DISABLED_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware: stamp security headers; gate the docs in production.

    Header injection touches only the ``http.response.start`` message, so it is safe on
    streaming responses (the SSE job-events endpoint). The production docs gate
    short-circuits before routing with a plain ``404``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # WebSocket / lifespan scopes carry no response headers to stamp.
            await self.app(scope, receive, send)
            return

        # Resolve the posture ONCE per request (a single, consistent read) — reusing the
        # exact #858 switch so headers + docs gate never disagree with the auth layer.
        production = _is_production()

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _STATIC_SECURITY_HEADERS.items():
                    headers[name] = value
                if production:
                    headers["strict-transport-security"] = _HSTS_VALUE
            await send(message)

        if production and scope.get("path") in _PRODUCTION_DISABLED_PATHS:
            # Docs/OpenAPI are disabled in production — look simply absent, not gated.
            # Route through the wrapper so even this 404 carries the security headers
            # (the "every HTTP response" contract holds).
            await PlainTextResponse("Not Found", status_code=404)(
                scope, receive, send_with_security_headers
            )
            return

        await self.app(scope, receive, send_with_security_headers)
