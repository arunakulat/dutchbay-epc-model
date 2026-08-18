# syntax=docker/dockerfile:1
#
# DutchBay EPC model — container image for the FastAPI web surface (app.api.main:app)
# and the arq worker (app.jobs.worker.WorkerSettings). Issue #845 (deploy scaffolding).
#
# Design (matter-of-fact; see the "Assumptions" and "Limitations" notes at the foot):
#   * Multi-stage. A `builder` stage compiles the virtualenv at /opt/venv using the
#     project's two-step install strategy; the `runtime` stage carries only that venv,
#     the WeasyPrint runtime shared libraries, and the application source.
#   * Canonical source path is /app in BOTH stages. The editable install
#     (`pip install -e`) writes an editable finder that records the build-time project
#     directory; keeping that directory identical (/app) in the runtime stage is what
#     makes `import app` / `import analytics` / `import finance` resolve at run time.
#     `app/` is deliberately NOT registered in [tool.setuptools.packages.find]
#     (verified: pyproject.toml lists analytics*/finance*/api*/config*/wind_resource*/
#     solar_resource* only), so it is served from the copied source tree, not site-packages.
#   * The [grid] extra (pandapower) is intentionally omitted — heavy, and the grid
#     screening path degrades gracefully via CASPER-guarded imports (analytics.grid.*
#     _require_pandapower). See pyproject.toml [project.optional-dependencies].grid.
#
# Both process commands run from this one image; Fly / compose select which:
#   web    : uvicorn app.api.main:app --host 0.0.0.0 --port 8080   (the default CMD below)
#   worker : arq app.jobs.worker.WorkerSettings                     (override CMD)

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — builder: build the virtualenv at /opt/venv.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

# Deterministic, quiet, no stale .pyc; fail pip fast on network hiccups.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# Build toolchain + WeasyPrint's build-time dev headers. Prefer wheels for everything;
# these are the fallback for any sdist that still has to compile (e.g. a C extension
# with no bookworm/cp311 wheel). Kept out of the runtime stage entirely.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create the venv the runtime stage will copy verbatim.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV="/opt/venv"

# Modern build frontend for the editable install of a pyproject-only project.
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /app

# Dependency manifests first, so the (slow) locked install layer is cached and only
# re-runs when a manifest changes — not on every source edit.
COPY requirements.txt constraints.txt pyproject.toml ./

# Two-step install strategy (authoritative — do not reorder):
#   1) The FULL pinned lock (locked core + [api]: this lock contains fastapi/uvicorn
#      but NOT arq/redis/weasyprint/reportlab/geopandas/contextily).
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# The editable install in step 2 needs the packages it references to exist under /app
# at build time, so copy the source tree before it runs.
COPY . .

#   2) The editable project with the deploy extras — adds arq/redis (jobs),
#      weasyprint/reportlab/geopandas/contextily (report), all bounded by the same
#      constraints so nothing in the lock is silently upgraded. [grid] is excluded.
RUN pip install --no-cache-dir -c constraints.txt -e '.[api,jobs,report]'

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime: slim image with only the venv, WeasyPrint runtime libs, source.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV="/opt/venv" \
    # Belt-and-braces alongside the editable finder: guarantees `import app` (which is
    # NOT installed as a package) and the top-level engine packages resolve from /app
    # regardless of the setuptools editable-finder variant.
    PYTHONPATH="/app"

# WeasyPrint ([report] extra) runtime shared libraries only — the exact bookworm set,
# no -dev headers, no build toolchain. curl is added solely for the container
# HEALTHCHECK below. --no-install-recommends keeps the layer minimal.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libglib2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime account. A fixed high uid/gid (10001) keeps host bind-mount
# ownership predictable and avoids colliding with distro system users.
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# The prebuilt virtualenv. Owned by appuser so an in-place `pip` (if ever run) does not
# need root; the interpreter and all site-packages come from here via PATH.
COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv

# The application source, at the same /app path the editable install was built against.
# .dockerignore prunes tests/docs/caches/outputs; what remains is the runtime surface
# (app/, analytics/, finance/, api/, config/, wind_resource/, solar_resource/, conf/,
# scenarios/, constants.py, VERSION, README.md, and the manifests).
COPY --from=builder --chown=10001:10001 /app /app

USER 10001

EXPOSE 8080

# Liveness: GET /health is an UNVERSIONED infra route with no auth
# (app/api/main.py:114 -> {"status": "ok", ...}). curl -f fails non-2xx so an
# unhealthy boot is reported. Tuned for the ~1s app import + first-request warmup.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8080/health || exit 1

# Default process = the web server. Fly [processes].worker and compose override this
# with `arq app.jobs.worker.WorkerSettings`.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

# ─────────────────────────────────────────────────────────────────────────────
# Assumptions
#   * python:3.12-slim-bookworm (Debian 12). The WeasyPrint runtime library names
#     above are the bookworm package names; a different base (e.g. trixie/alpine)
#     would need a different set.
#   * requirements.txt is the full pinned lock frozen with .[dev,test,api,dashboard,
#     wind,gis]; it provides fastapi==0.139.0 / uvicorn==0.50.0 but not the [jobs]/
#     [report] packages, which step 2 adds under the same constraints.txt.
#   * The build context is the repository root and includes requirements.txt,
#     constraints.txt, pyproject.toml, and the source packages (see .dockerignore).
#
# Limitations
#   * The [grid] extra (pandapower/andes/opendssdirect.py) is not installed; grid
#     screening degrades gracefully (CASPER) rather than failing. Add a `[grid]`
#     install layer only if a bankable grid study is required in-container.
#   * The healthcheck proves the web process is live; it does not exercise auth, the
#     Redis-backed job path, or PDF rendering. The worker process publishes no port,
#     so this HEALTHCHECK is meaningful for the web process only (the compose worker
#     overrides CMD and should not inherit an HTTP healthcheck).
#   * No application secrets are baked in. DUTCHBAY_JWT_SECRET / DUTCHBAY_API_USERS /
#     DUTCHBAY_REDIS_URL must be injected at run time (Fly secrets / compose env).
# ─────────────────────────────────────────────────────────────────────────────
