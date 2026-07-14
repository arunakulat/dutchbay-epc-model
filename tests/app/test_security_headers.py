"""#944 — HTTP security-header + docs-posture hardening on the web surface.

Exercises :mod:`app.api.security`. The static policy constants are asserted directly, and
the wired behaviour is driven through a ``TestClient`` against the composed app
(:mod:`app.api.main`), gated on ``httpx`` to match the sibling suites. What is proven:

* the always-on security headers are stamped on responses,
* ``Strict-Transport-Security`` is emitted **only** in the production posture,
* ``/docs`` + ``/redoc`` + ``/openapi.json`` are ``404`` in production but reachable in
  development, while the app itself (``/health``) is unaffected by that gate,
* the pure-ASGI middleware injects the headers **without buffering** a streaming body,
* non-HTTP scopes pass straight through.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.api.security import (
    _CONTENT_SECURITY_POLICY,
    _HSTS_VALUE,
    _PRODUCTION_DISABLED_PATHS,
    _STATIC_SECURITY_HEADERS,
    SecurityHeadersMiddleware,
)


# --------------------------------------------------------------------------- #
# Policy constants (direct assertions — no network).
# --------------------------------------------------------------------------- #
def test_csp_pins_same_origin_defaults_and_anti_clickjacking() -> None:
    """The minimal HTMX-wizard CSP locks same-origin defaults + non-fallback directives."""
    csp = _CONTENT_SECURITY_POLICY
    assert "default-src 'self'" in csp
    # These four do NOT fall back to default-src, so each must be stated explicitly.
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    # img data: URIs are allowed (embedded chart images); external hosts are not.
    assert "img-src 'self' data:" in csp
    assert "http://" not in csp and "https://" not in csp
    # inline script/style are permitted (documented: inline bootstrap <script> +
    # style="width:…%" bars) — but only from the same origin otherwise.
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_required_static_headers_present_hsts_is_not_static() -> None:
    assert _STATIC_SECURITY_HEADERS["x-content-type-options"] == "nosniff"
    assert _STATIC_SECURITY_HEADERS["x-frame-options"] == "DENY"
    assert _STATIC_SECURITY_HEADERS["referrer-policy"] == "no-referrer"
    assert (
        _STATIC_SECURITY_HEADERS["content-security-policy"] == _CONTENT_SECURITY_POLICY
    )
    # HSTS is production-gated, so it must NOT live in the always-on set.
    assert "strict-transport-security" not in _STATIC_SECURITY_HEADERS


def test_docs_gate_targets_exactly_the_three_recon_paths() -> None:
    assert _PRODUCTION_DISABLED_PATHS == frozenset({"/docs", "/redoc", "/openapi.json"})


# --------------------------------------------------------------------------- #
# Wired behaviour through the composed app (gated on httpx).
# --------------------------------------------------------------------------- #
def test_security_headers_present_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.main import app

    monkeypatch.delenv("DUTCHBAY_ENV", raising=False)  # permissive dev posture
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in resp.headers["content-security-policy"]
    # dev never pins http://localhost with HSTS.
    assert "strict-transport-security" not in resp.headers


def test_hsts_emitted_only_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.main import app

    monkeypatch.setenv("DUTCHBAY_ENV", "production")
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.headers["strict-transport-security"] == _HSTS_VALUE
    # the always-on headers are still stamped alongside HSTS.
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]


def test_docs_reachable_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.main import app

    monkeypatch.delenv("DUTCHBAY_ENV", raising=False)
    client = TestClient(app)

    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_docs_disabled_in_production_app_unaffected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.main import app

    monkeypatch.setenv("DUTCHBAY_ENV", "production")
    client = TestClient(app)

    for path in sorted(_PRODUCTION_DISABLED_PATHS):
        assert client.get(path).status_code == 404, path
    # The gate is docs-only: the app itself keeps serving.
    assert client.get("/health").json()["status"] == "ok"


def test_headers_injected_without_buffering_streaming_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A streaming body survives intact AND the start-message headers are stamped.

    Proves the pure-ASGI design: a header-injecting middleware that buffered the body
    (e.g. a naive BaseHTTPMiddleware) would defeat the SSE job-events stream.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import StreamingResponse
    from starlette.routing import Route

    monkeypatch.delenv("DUTCHBAY_ENV", raising=False)

    expected = "".join(f"chunk{i}\n" for i in range(5))

    async def _stream(_request: object) -> StreamingResponse:
        async def _gen() -> AsyncIterator[bytes]:
            for i in range(5):
                yield f"chunk{i}\n".encode()

        return StreamingResponse(_gen(), media_type="text/plain")

    inner = Starlette(routes=[Route("/stream", _stream)])
    inner.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(inner)

    resp = client.get("/stream")
    assert resp.status_code == 200
    assert resp.text == expected  # every chunk passed through, nothing buffered/dropped
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["content-security-policy"]


def test_non_http_scope_passes_through() -> None:
    """A lifespan/websocket scope is forwarded untouched (no headers to stamp)."""
    seen: dict[str, str] = {}

    async def _inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen["type"] = scope["type"]

    mw = SecurityHeadersMiddleware(_inner)

    async def _receive() -> Message:
        return {"type": "lifespan.startup"}

    async def _send(_message: Message) -> None:
        return None

    asyncio.run(mw({"type": "lifespan"}, _receive, _send))
    assert seen["type"] == "lifespan"
