# DutchBay EPC Model → Web Service: Transformation Roadmap

> A codebase-grounded plan to expose the lender-grade finance pipeline as a web
> service (FastAPI backend + multi-step wizard) for a **small set of known
> clients** (named lenders/developers with logins; no public self-signup or
> billing). Synthesised from a verified survey of the current `main` branch, a
> multi-source best-practices research pass, and an external repository review.
>
> Status: planning. Last updated: 2026-06-22.

---

## 1. Headline

This is a **wrapper, not a rewrite** — and **less effort than a from-scratch build**,
because the backend API, the form→config bridge, and Excel reporting **already
exist** in the repo. Realistic effort for a production MVP: **~2.5–3.5 focused
sprints**.

The core pipeline runs **untouched** on the synchronous (frozen-AEP) path; the
only genuinely new infrastructure is a PDF report, a wizard frontend, an async
job path for live-ERA5 runs, simple auth, and deployment.

---

## 2. What already exists (verified on `main`)

| Layer | Status | Where |
|---|---|---|
| FastAPI app + routers | ✅ exists | `api/sensitivity_api.py` (`FastAPI` app + `POST /run-tornado/`), `api/pipeline_api.py` (`APIRouter` + `POST /run-pipeline`) |
| **Form → config bridge** | ✅ exists | `RunPipelineRequest` — accepts an inline `config` *or* a `config_path`, plus dotted-key `overrides`; structured outputs (`AepBlock`, `KpiBlock`, `DebtBlock`, `DebtScheduleRow`, `RunPipelineResponse`) |
| Synchronous compute gateway | ✅ exists | `analytics.evaluate_scenario.evaluate_with_overrides`, `analytics.pipeline_v14_enhanced.run_v14_pipeline` (~0.05s on a frozen `aep_summary`) |
| Wind → finance bridge | ✅ exists | `wind_resource/cashflow_adapter.py` `WindCashflowExport` (frozen-JSON, drift-checked) → patches `resource.wind` |
| Path-traversal hardening | ✅ exists | `api/path_safety.py` |
| Web deps | ✅ pinned | `fastapi`, `uvicorn`, `starlette`, **`Jinja2`** |
| Excel reporting | ✅ exists | `analytics/export_helpers.py` (ExcelExporter/ChartExporter), `analytics/executive_workbook.py` |
| **PDF reporting** | ❌ net-new | no `reportlab`/`weasyprint`/`fpdf` anywhere, none in requirements |
| Wizard frontend / auth / async job queue | ❌ net-new | — |

**Implication:** the proposal's "build a FastAPI wrapper + form→YAML bridge"
sprint is largely **done**. Effort shifts to the PDF report, the wizard, the
async ERA5 path, and simple auth.

---

## 3. Target architecture (dual compute path)

```
Wizard (React + TypeScript types generated from the Pydantic models)
   │  one JSON payload per page
   ▼
FastAPI app  ── OAuth2 password flow + JWT (per known client) ──┐
   ├─ POST /cases   (SYNC, frozen-AEP)  → evaluate_with_overrides → result in ~0.05s
   └─ POST /jobs    (ASYNC, live-ERA5)  → arq enqueue → returns job_id
        GET /jobs/{id}/events  (SSE progress)
        GET /jobs/{id}/report  (signed download: PDF / XLSX)
   ▼
arq worker (Redis)  → wind_resource.wind_pipeline (ERA5 → Weibull → AEP)
                    → evaluate_with_overrides
   ▼
reports/  → WeasyPrint + Jinja2 (14-page PDF) · export_helpers (XLSX)
```

The fast path needs **no queue**. The slow ERA5 path is the only one that needs
background execution + progress.

### Current status of the async path (deferred wiring)

As of this writing the async ERA5 path is **built and unit-tested but not yet wired** to the HTTP
API. Concretely:

- `app/jobs/worker.py` (the arq `WorkerSettings` + `run_wind_assessment_task`) and
  `app/jobs/redis_store.py` (`RedisJobStore`, tested against a fake client) are complete; the
  worker is import-smoke-tested under the optional `[jobs]` extra.
- The **live** `POST /jobs` path runs the same orchestration (`app.jobs.runner.run_wind_job`)
  in-process via FastAPI `BackgroundTasks` against `InMemoryJobStore`, resolved through the
  `get_store` dependency in `app/api/jobs_router.py` — adequate for a few known clients on one
  process.
- The remaining cutover — the route producing to the arq queue and `get_store` returning a
  `RedisJobStore` behind `[jobs]` — is a deliberate **Redis-gated follow-up**: it cannot be
  CI-verified without a live Redis, so it is left as a single, well-isolated switch on the verified
  building blocks rather than shipped half-tested. To enable it: install the `[jobs]` extra, run
  `arq app.jobs.worker.WorkerSettings`, and point `get_store` at a `RedisJobStore`.

This keeps `main` green and the default path fully tested, while the durable / horizontal-scale
path stays one explicit step away (see Sprint 2 below).

---

## 4. Key technical decisions (with confidence from the research pass)

1. **Form → config bridge (high):** resolve the Hydra `DictConfig` → `dict` and
   hand it straight to `evaluate_with_overrides` / the existing Pydantic models.
   **Avoid** `OmegaConf.structured` and the CLI's temp-YAML strategy on the web
   path (a CLI-ism — see `run_full_pipeline_v14.py`). If Hydra composition is
   needed, the Compose API (`initialize` + `compose`, managing `GlobalHydra`
   per-request) works inside a FastAPI handler without `@hydra.main`.
2. **Async execution (high):** fast path = synchronous; slow ERA5 path = **arq +
   Redis** (Celery is overkill for this scale; FastAPI `BackgroundTasks` is
   insufficient — no status/result tracking).
3. **Progress streaming (high):** **Server-Sent Events**, not WebSockets
   (one-way job progress over plain HTTP).
4. **Auth (high):** first-party FastAPI **OAuth2 bearer + JWT**; isolate
   jobs/results by JWT subject. No third-party IdP needed for a few known clients.
   *Delivered (#449)* with stdlib-only HMAC-SHA256 JWT + PBKDF2 (no new dependency);
   `POST /token` takes a **JSON** body rather than an OAuth2 form, so no
   `python-multipart` is pulled into the locked requirements.
5. **Frontend types (high):** generate TypeScript from the Pydantic models with
   **`pydantic-to-typescript`** so client validation mirrors the backend.
6. **Deployment (Fly security verified):** **Fly.io** — default at-rest LUKS +
   in-transit encryption, native Redis + Postgres, low-ops. (Railway/Render/AWS
   are viable but were not separately verified; revisit if requirements change.)
7. **PDF (codebase-driven):** **WeasyPrint + Jinja2** — Jinja2 is already a
   dependency and reportlab is not; render the existing result dict through HTML
   templates rather than imperative PDF drawing.
8. **Security:** HTTPS everywhere; encrypt sensitive temp files / at-rest job
   inputs (client financials); secrets via the platform's secret store.

---

## 5. Phased plan

### Sprint 0 — Stabilise (days; do first)
- One authoritative `docs/ARCHITECTURE.md`: the canonical execution map is
  `run_full_pipeline_v14.py` → `analytics.pipeline_v14_enhanced.run_v14_pipeline`
  (alias of `run_v14_pipeline_enhanced`); the legacy wind-only
  `analytics/pipeline_v14.py` is **not** canonical.
- Fix stale docs (README coverage figure ✅ done; archive sprint-retro docs).
- **Why first:** every downstream step depends on a single reliable picture.

### Sprint 1 — Service seam + sync path
- Thin `app/services/pipeline_service.py` wrapping `evaluate_with_overrides`
  (no file I/O, no subprocess, no stdout).
- A `WindFarmInputs` Pydantic model → scenario `dict`.
- Unify the two existing FastAPI surfaces under one app; expose `POST /cases`
  (synchronous, frozen-AEP).
- *Mostly assembly of parts that already exist.*

### Sprint 2 — Reports + async ERA5
- `reports/pdf_builder.py` (WeasyPrint + Jinja2) for the 14-page PDF; finish
  `executive_workbook` as the canonical XLSX surface.
- arq + Redis worker wrapping `wind_resource.wind_pipeline`; `POST /jobs` + SSE
  progress + signed report download.

### Sprint 3 — Auth + wizard + deploy
- **OAuth2 + JWT, per-client job/result isolation — DONE (#449).** Stdlib-only
  HMAC-SHA256 JWT + PBKDF2 hashing (no new dependency); `/cases*` and `/jobs*` are
  guarded by `get_current_subject`, and each `JobRecord` is bound to its JWT subject
  (non-owners get a non-leaking 404). The lower-level `/run-pipeline` and the mounted
  `/sensitivity` app are **not yet** guarded — see `app/api/auth.py` and the #449 PR.
- React wizard (5 pages: site basics → financial params → wind-data source →
  scenario toggles → confirm & run), validated with generated TS types.
- Fly.io deploy (app + Redis + Postgres for users/jobs), HTTPS, encrypted temp
  files.

---

## 6. Realistic effort

NOT "3–4 sprints from scratch." Crediting the existing FastAPI surface +
form→config bridge + Excel reporting, the genuinely-new work is: (1) the PDF
report, (2) the wizard frontend, (3) the async ERA5 job path (arq+Redis+SSE) —
slow branch only, (4) simple OAuth2+JWT auth + per-user isolation, (5) unify the
app + deploy. **~2.5–3.5 focused sprints** to a production MVP.

---

## 7. One honest caveat to surface to clients

The model's current canonical economics are **value-destructive** (project IRR
~2.75% below the ~8.10% WACC, equity IRR ~−0.5%, project NPV ≈ −$53.3M, after the
2026-06 honest re-baseline — which includes the 5.9% data-derived FX-drift re-baseline
and the M3e degradation correction:
`project.degradation` had been read as ~0%/yr and is now an honest 0.5%/yr turbine
aging). The web tool will faithfully report that. This warrants a deliberate UX
decision: show the verdict prominently vs. let clients explore scenarios that
improve it.

---

*Provenance: codebase survey of `arunakulat/dutchbay-epc-model` @ `main`
(2026-06-22) + a multi-source best-practices research pass + an external repo
review (whose architecture direction corroborated this plan, though its
module-status / wind-number / coverage specifics were a ~6-month-stale snapshot).*
