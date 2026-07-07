"""Server-rendered HTMX wizard frontend (the ``#843`` backend-for-frontend layer).

This package is the human-facing web UI for the DutchBay EPC model, served *inside*
the existing FastAPI application (:mod:`app.api.main`) — no Node build, no separate
single-page-app deployment. It is a thin **backend-for-frontend** (BFF): HTMX over
Jinja2 templates, whose routes reuse the *same* in-process functions the versioned
``/v1`` JSON API calls, so there is zero duplicated finance or authentication logic
(Dolphin / CCCDIR).

Modules:

* :mod:`app.web.auth_cookie` — the cookie-based session gate. A signed ``HS256`` JWT
  (minted by :func:`app.api.auth.login_for_access_token`) is stored in an ``httpOnly``
  cookie so the token never reaches page JavaScript; the :func:`require_web_user`
  dependency validates it by *reusing* :func:`app.api.auth.decode_token` (no
  re-implemented crypto).
* :mod:`app.web.routes` — the :class:`fastapi.APIRouter` mounted at the application
  root (no ``/v1`` prefix): the login/logout flow and the multi-step wizard, whose
  "Run" and download actions delegate to :func:`app.api.main.build_case_surface` and
  the report/workbook builders via :func:`fastapi.concurrency.run_in_threadpool`.

Templates live in ``app/web/templates`` and static assets in ``app/web/static``; both
are resolved relative to this package so they are working-directory independent. The
Jinja2 environment forces ``autoescape`` on — user-supplied fields (site name,
location) are always HTML-escaped (no injection).
"""

from __future__ import annotations
