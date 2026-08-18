# DutchBay Web Service — Deployment Runbook

Deployment scaffolding for the DutchBay EPC model web service (issue #845; web
service roadmap #788; durable job backend #663).

This document is the operator runbook for two targets:

1. A local Docker Compose stack for development and smoke testing.
2. A production deployment to Fly.io.

It describes user-run steps only. No step in this runbook is executed by CI or by
the model; the commands below are run by the operator.

## Overview

The service is composed of three processes:

- **Web** — the FastAPI application object `app.api.main:app`, served by uvicorn on
  port 8080. It exposes the versioned client surface under `/v1` and an unversioned
  liveness probe at `GET /health` (`app/api/main.py`, `health()` at the `/health`
  route). Command:

  ```
  uvicorn app.api.main:app --host 0.0.0.0 --port 8080
  ```

- **Worker** — an arq worker that drains the async wind-assessment queue and writes
  job state to Redis (`app.jobs.worker.WorkerSettings`). It exposes no public port.
  Command:

  ```
  arq app.jobs.worker.WorkerSettings
  ```

- **Redis** — the shared job store and arq broker. Locally this is a Redis container;
  on Fly.io it is managed Redis (Upstash). The worker and the web process both connect
  to the same instance so the web process can report status the worker produced
  (`app/jobs/worker.py`, `app/jobs/redis_store.py`).

The web process is the only process that accepts inbound HTTP. The worker shares Redis
with the web process but is not reachable from the public internet.

The async job path is engaged only when `DUTCHBAY_JOBS_BACKEND=redis`; with the default
`memory` backend the API runs jobs in-process and the worker is idle (`app/jobs/config.py`,
`JOBS_BACKEND`). A deployment that serves the async ERA5 path sets the backend to `redis`
and runs the worker process.

## Local run (Docker Compose)

Prerequisites: Docker with the Compose plugin.

1. Copy the example environment file and review it:

   ```
   cp .env.example .env
   ```

   The example file carries development-posture defaults. It does not set
   `DUTCHBAY_ENV=production`, so the auth gate runs in its permissive local posture
   (`app/api/auth.py`, `_is_production()` returns `False` when `DUTCHBAY_ENV` is unset
   or not `production`/`prod`). Issuer/audience binding is not mandatory in this posture.

2. Build and start the stack:

   ```
   docker compose up --build
   ```

3. Verify liveness once the web container reports healthy:

   ```
   curl http://localhost:8080/health
   ```

   The response is `{"status":"ok","contract_version":"..."}` (`app/api/main.py`,
   `health()`).

Note on posture: the local stack is for development and smoke testing. Because
`DUTCHBAY_ENV` is not `production`, the hardened checks in `app/api/auth.py` (insecure-
secret rejection, mandatory issuer/audience) are not enforced. Do not treat the local
stack as a security-representative deployment; the production posture below is.

## Production deploy to Fly.io

Prerequisites are listed under Assumptions. Every command below is run by the operator.

1. **Initialise the app without deploying**, then review the generated `fly.toml`
   against the checked-in one:

   ```
   fly launch --no-deploy
   ```

   Confirm the process model: `[processes] web` runs the uvicorn command and `worker`
   runs the arq command; `[http_service]` attaches to `web` only, with
   `internal_port = 8080`, `force_https = true`, and a `[[http_service.checks]]` block
   that performs `GET /health`. The worker process exposes no public port.

2. **Provision managed Redis** (Upstash) and capture the DSN:

   ```
   fly redis create
   ```

   Record the connection string it prints. This DSN carries a password and is therefore
   a secret; it is supplied to the app as `DUTCHBAY_REDIS_URL` via `fly secrets set`
   (step 4), never in `fly.toml`.

3. **Mint the web-surface secrets.** From the repo root, with the inputs exported:

   ```
   DUTCHBAY_PROVISION_USER=admin \
   DUTCHBAY_PROVISION_PASSWORD='<strong-password>' \
       python scripts/provision_web_secrets.py
   ```

   The script prints a fresh `DUTCHBAY_JWT_SECRET`, the `DUTCHBAY_API_USERS` entry
   (`admin:<pbkdf2-hash>`, hashed by `app.api.auth.hash_password`), and a ready-to-run
   `fly secrets set` line. The JWT secret is shown once and is not stored by the script;
   capture it before continuing. The script reads its inputs from the environment (no
   command-line flags: R3/R4/CST-01 ban argparse/Typer/Click and `input()` in these
   paths).

4. **Set the secrets on the Fly app.** Substitute the values from steps 2 and 3. The
   values are single-quoted because the pbkdf2 hash in `DUTCHBAY_API_USERS` contains `$`
   field separators that an unquoted shell would expand (which mangles the credential map
   so every login 401s); `scripts/provision_web_secrets.py` prints the line already
   quoted. `CDSAPI_KEY` is the Copernicus CDS API token, required for the async ERA5
   retrieval path (the worker runs it under `DUTCHBAY_JOBS_BACKEND=redis`):

   ```
   fly secrets set \
     DUTCHBAY_JWT_SECRET='<value-from-step-3>' \
     DUTCHBAY_API_USERS='<value-from-step-3>' \
     DUTCHBAY_REDIS_URL='<dsn-from-step-2>' \
     CDSAPI_KEY='<copernicus-cds-api-token>'
   ```

   These four values are secrets and must never appear in `fly.toml`. Non-secret
   configuration (for example `DUTCHBAY_ENV`, `DUTCHBAY_JWT_ISSUER`,
   `DUTCHBAY_JWT_AUDIENCE`, `DUTCHBAY_JOBS_BACKEND`, and the public `CDSAPI_URL` base)
   lives in the `[env]` block of `fly.toml`. In the production posture the issuer and
   audience are mandatory: an unset `DUTCHBAY_JWT_ISSUER` or `DUTCHBAY_JWT_AUDIENCE` is
   rejected with a 500 (`app/api/auth.py`, `_jwt_issuer()` / `_jwt_audience()`), so
   confirm both are present in `[env]` before deploying.

5. **Deploy:**

   ```
   fly deploy
   ```

6. **Verify.** Confirm liveness and one authenticated call against the versioned surface:

   ```
   curl https://<app>.fly.dev/health

   TOKEN=$(curl -s -X POST https://<app>.fly.dev/v1/token \
     -H 'content-type: application/json' \
     -d '{"username":"admin","password":"<strong-password>"}' \
     | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

   curl -H "Authorization: Bearer $TOKEN" https://<app>.fly.dev/v1/...
   ```

   `/health` is unauthenticated (infra probe); every `/v1` compute route requires the
   bearer token (`app/api/main.py`, the routers are mounted with
   `Depends(get_current_subject)`).

## Staging deploy to Fly.io

Staging is a **separate** Fly app, `dutchbay-epc-model-staging`, described by the
checked-in `fly.staging.toml`. It mirrors the production topology (web + worker off one
image, `/health` check, `sin` region) and deliberately keeps the fail-closed
`DUTCHBAY_ENV="production"` auth posture — a staging app on `*.fly.dev` is a public
surface, so it should not run the relaxed off-production posture. Its JWT issuer/audience
and job queue are distinct from production (`dutchbay-epc-model-staging` /
`dutchbay-web-staging` / `dutchbay:wind_jobs_staging`) so a staging-minted token cannot be
replayed against production.

The steps mirror the production deploy, targeting the staging app with `-a` (or `-c` for
`fly deploy`). Four secrets are required — the same three web-surface secrets plus the
Copernicus CDS API token:

```
fly redis create -a dutchbay-epc-model-staging          # capture the staging DSN

DUTCHBAY_PROVISION_USER=admin \
DUTCHBAY_PROVISION_PASSWORD='<staging-password>' \
    python scripts/provision_web_secrets.py             # prints JWT secret + API_USERS

fly secrets set -a dutchbay-epc-model-staging \
  DUTCHBAY_JWT_SECRET='<value-from-script>' \
  DUTCHBAY_API_USERS='<value-from-script>' \
  DUTCHBAY_REDIS_URL='<dsn-from-fly-redis-create>' \
  CDSAPI_KEY='<copernicus-cds-api-token>'

fly deploy -c fly.staging.toml
```

The non-secret `CDSAPI_URL` base (`https://cds.climate.copernicus.eu/api`) is committed in
`fly.staging.toml`'s `[env]`; only the paired `CDSAPI_KEY` is a secret. No secret value
appears in the config file — verify with:

```
grep -E '^\s*(DUTCHBAY_JWT_SECRET|DUTCHBAY_API_USERS|DUTCHBAY_REDIS_URL|CDSAPI_KEY)\s*=' \
    fly.staging.toml   # must print nothing (these appear only in the runbook comment)
```

## Configuration reference

All sixteen environment variables the service reads. "Secret?" marks values that must
be provisioned via `fly secrets set` and never committed to `fly.toml`. Defaults are the
in-code fallbacks; a blank default means the variable has no fallback in the relevant
posture.

| Name | Purpose | Default | Secret? |
| --- | --- | --- | --- |
| `DUTCHBAY_ENV` | Deployment posture selector; `production`/`prod` engages the hardened auth posture. Unset/`development` is permissive local. Set to `production` on Fly. | unset (permissive) | No |
| `DUTCHBAY_JWT_SECRET` | HMAC signing secret for the HS256 JWTs. Required; in production a known placeholder or a secret shorter than 32 chars is rejected (500). | none (required) | Yes |
| `DUTCHBAY_API_USERS` | `user:<pbkdf2-hash>,user2:<hash>` credential map. Hashes come from `app.api.auth.hash_password`. Absent means every login is rejected. | none (empty map) | Yes |
| `DUTCHBAY_JWT_ISSUER` | `iss` binding. Mandatory in production (unset means 500); opt-in off-production. | unset | No |
| `DUTCHBAY_JWT_AUDIENCE` | `aud` binding. Mandatory in production (unset means 500); opt-in off-production. | unset | No |
| `DUTCHBAY_JOBS_BACKEND` | Job backend selector: `memory` (in-process) or `redis` (durable, cross-process). Deploy uses `redis`. | `memory` | No |
| `DUTCHBAY_REDIS_URL` | Redis DSN shared by the API and worker. On Fly this is managed Redis and carries a password. Local compose uses `redis://redis:6379`. | `redis://localhost:6379` | Yes (on Fly) |
| `DUTCHBAY_JOBS_QUEUE` | arq queue name the API produces to and the worker consumes from. | `dutchbay:wind_jobs` | No |
| `DUTCHBAY_JOBS_MAX_RETAINED` | Maximum job records retained in the in-memory store; terminal jobs evict first. | `1000` | No |
| `DUTCHBAY_JOBS_TTL_SECONDS` | TTL applied to Redis job records; `0` disables expiry. | `86400` | No |
| `DUTCHBAY_SSE_MAX_POLLS` | Maximum SSE polls before a stream self-closes (× poll interval = max lifetime). | `600` | No |
| `DUTCHBAY_SSE_POLL_INTERVAL` | Seconds between SSE polls while a job is non-terminal. | `0.5` | No |
| `DUTCHBAY_SYNC_ROUTE_TIMEOUT` | Wall-clock ceiling (seconds) for the synchronous `/cases*` compute routes. Bounds the client wait, not the computation. | `120` | No |
| `DUTCHBAY_SYNC_ROUTE_MAX_CONCURRENCY` | Maximum concurrent synchronous `/cases*` computations; excess requests are shed with 503. `<= 0` disables the explicit bound. | `8` | No |
| `CDSAPI_URL` | Copernicus CDS API base URL for ERA5 retrieval. The public base is non-secret; there is no in-code default, so it must be set for ERA5 authentication to resolve (`wind_resource/era5_retrieval.py`, `ensure_cdsapirc()`). | none (required for ERA5) | No |
| `CDSAPI_KEY` | Copernicus CDS API token paired with `CDSAPI_URL`. Never committed; provisioned via `fly secrets set`. | none (required for ERA5) | Yes |

Sources: auth variables in `app/api/auth.py`; job variables in `app/jobs/config.py`;
synchronous-route variables in `app/api/config.py`; CDS variables in
`wind_resource/era5_retrieval.py`.

## Assumptions

- The operator has a Fly.io account and `flyctl` installed and authenticated.
- Managed Redis (Upstash) provisioned via `fly redis create` is network-reachable from
  the app in the same organisation and region.
- TLS is terminated by Fly at the edge; `[http_service]` sets `force_https = true` and
  the application is served plain HTTP on the internal port 8080.
- The primary region is `sin` (Singapore), the closest Fly region to Sri Lanka, and the
  VM is sized with approximately 1 GB of memory headroom to accommodate WeasyPrint and
  geopandas.
- The container image is built from `python:3.12-slim-bookworm` and runs as a non-root
  user; the WeasyPrint runtime libraries listed in the image build are present in the
  final image.
- `DUTCHBAY_JOBS_BACKEND=redis` is set in the `fly.toml` `[env]` block so the async ERA5
  path is engaged and the worker process has work to drain.

## Limitations

- **CVE gate coverage of the extra dependencies.** The image installs the complete
  audited lock first (`pip install -r requirements.txt -c constraints.txt`) and then
  installs the project with `[api,jobs,report]`. Those retained extras—including arq,
  Redis/hiredis, WeasyPrint, reportlab, geopandas and contextily—are now members of the
  Python 3.12 lock, so the second install must not introduce an unpinned package or move
  a cleared version. The mandatory `pip-audit -r requirements.txt` gate covers their
  full locked closure.
- **The `[grid]` extra is excluded.** `pandapower` and the rest of the `[grid]` extra are
  intentionally not installed (they are heavy). Grid-screening report sections degrade
  gracefully rather than failing: the guarded imports raise no error at import time and
  the affected outputs are omitted (CASPER — clear API surfaces, optional dependencies
  fail at call time via guards, not at import). See the Provenance section.
- **Local Docker build not run in the authoring environment.** The image could not be
  built or booted where this scaffolding was authored. The `docker-build` CI workflow is
  the build-and-boot verification for the image; a green run of that workflow is the
  gate that the image builds and the web process starts and answers `/health`.
- **User-held operational concerns.** Token revocation and a `jti` denylist, the choice
  of secret store, and TLS termination are operator responsibilities and are not
  implemented in code (`app/api/auth.py` module docstring; tracked on #858). A leaked
  token remains valid until its `exp`; no code-only change revokes it.

## Provenance

Per the surface-provenance discipline, the resolution and degradation behaviour behind
the deployed image is stated explicitly rather than left implicit:

- **Dependency resolution.** The image resolves the locked pin set from
  `requirements.txt` and then the `[api,jobs,report]` extras, both under
  `constraints.txt`, so the resolved version set is pinned and reproducible from the
  committed lock and constraints. The extras layered on top of the frozen lock are the
  subject of the CVE-gate limitation above.
- **Optional capabilities and graceful degradation.** Capabilities that depend on
  optional packages are CASPER-guarded and degrade rather than crash when a package is
  absent:
  - PDF report rendering depends on WeasyPrint (the `[report]` extra). When WeasyPrint
    is not installed the PDF route surfaces a dependency error rather than failing at
    import (`app/reports/renderer.py`, `ReportDependencyError`); the HTML route is
    unaffected.
  - Location and site maps depend on geopandas and contextily (the `[report]` extra).
    When absent, `make_location_map` degrades to a coastline outline and
    `make_site_context_map` returns `False` (the figure is omitted), per the `[report]`
    extra documentation in `pyproject.toml`.
  - Grid screening depends on the `[grid]` extra, which is excluded; the grid-screening
    sections degrade gracefully as noted in Limitations.
- **Verification discipline.** The deployment artifacts are scaffolding only and do not
  touch `finance/` or `analytics/`, so the canonical finance results are unchanged
  (byte-identical) by this work. Runtime behaviour of the image is verified by the
  `docker-build` CI workflow (build plus `/health` boot check), not by a build in the
  authoring environment.
