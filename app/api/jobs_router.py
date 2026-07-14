"""HTTP surface for the asynchronous live-ERA5 job path.

Mounted under the versioned ``/v1`` prefix by ``app.api.main`` (#841), so the live
paths are ``POST /v1/jobs`` etc. (the router itself only owns the ``/jobs`` segment):

* ``POST /jobs``              — enqueue a job (returns 202 + a ``JobAccepted`` handle
                                whose ``status_url``/``events_url`` are ``url_for``-derived,
                                so they carry the ``/v1`` mount prefix automatically).
* ``GET  /jobs/{id}``         — poll the job record (404 if unknown).
* ``GET  /jobs/{id}/events``  — SSE stream of progress until terminal/timeout.

The store is resolved through the :func:`get_store` dependency — the single
injection seam. Tests override it via ``app.dependency_overrides``; the durable
cross-process path replaces the default with a ``RedisJobStore``. The enqueue
handler only orchestrates: it creates a queued record and dispatches
:func:`~app.jobs.runner.run_wind_job` — via FastAPI ``BackgroundTasks`` on the
default ``memory`` backend, or by producing onto the arq queue on the ``redis``
backend (#663/#837). Both paths drive the same ``run_wind_job``.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.auth import get_current_subject
from app.jobs.config import JOBS_BACKEND, JOBS_QUEUE, JOBS_REDIS_URL
from app.jobs.models import JobRecord, JobState, WindJobRequest, utc_now_iso
from app.jobs.runner import new_queued_record, run_wind_job
from app.jobs.sse import job_event_stream
from app.jobs.store import InMemoryJobStore, JobStore

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _require_jobs_extra() -> None:
    """CASPER: fail loud at call-time when ``JOBS_BACKEND='redis'`` needs the optional
    ``[jobs]`` extra (arq, redis) but it is not installed — never at import time."""
    try:
        import arq  # noqa: F401
        import redis  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without [jobs]
        raise RuntimeError(
            "DUTCHBAY_JOBS_BACKEND='redis' requires the optional [jobs] extra "
            "(arq, redis) and a live Redis. Install with: pip install -e '.[jobs]'."
        ) from exc


def _build_default_store() -> JobStore:
    """Resolve the process store from ``JOBS_BACKEND`` (#663 cutover).

    ``"memory"`` (default) → :class:`InMemoryJobStore` (byte-identical to pre-#663).
    ``"redis"`` → a shared :class:`~app.jobs.redis_store.RedisJobStore` so the API
    reads the status the arq worker writes. The redis client is lazy (redis-py does
    not connect until a command is issued), so building it here does not require a
    live Redis at import.
    """
    if JOBS_BACKEND == "redis":
        _require_jobs_extra()
        import redis as sync_redis  # local import — optional [jobs] extra

        from app.jobs.redis_store import RedisJobStore

        return RedisJobStore(sync_redis.Redis.from_url(JOBS_REDIS_URL))
    return InMemoryJobStore()


#: Process store, built once on first use from ``JOBS_BACKEND``. ``get_store`` is the
#: injection seam: tests override it via ``app.dependency_overrides[get_store]``;
#: endpoints never reference the store directly.
_default_store: Optional[JobStore] = None


def get_store() -> JobStore:
    """FastAPI dependency yielding the active job store (override to swap)."""
    global _default_store
    if _default_store is None:
        _default_store = _build_default_store()
    return _default_store


async def _enqueue_to_arq(job_id: str, request: WindJobRequest) -> None:
    """Produce a job onto the arq queue the worker consumes (``redis`` backend).

    Only serializable arguments cross the queue: ``job_id`` + the request payload.
    The worker attaches its own shared ``RedisJobStore`` (``app.jobs.worker._on_startup``),
    so the store is NOT passed here. The task name + queue match the worker
    (``run_wind_assessment_task`` on :data:`JOBS_QUEUE`).
    """
    _require_jobs_extra()
    from arq import create_pool  # local import — optional [jobs] extra
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(JOBS_REDIS_URL))
    try:
        await pool.enqueue_job(
            "run_wind_assessment_task",
            job_id,
            request.model_dump(mode="json"),
            _queue_name=JOBS_QUEUE,
        )
    finally:
        await pool.close()


class JobAccepted(BaseModel):
    """The handle returned when a job is queued."""

    job_id: str
    state: JobState
    status_url: str
    events_url: str


def _new_job_id() -> str:
    return uuid.uuid4().hex


def _job_urls(http_request: Request, job_id: str) -> tuple[str, str]:
    """Build the status + events URLs for ``job_id`` from the mounted routes (#841).

    Uses ``Request.url_for`` against the NAMED routes so the paths carry whatever
    prefix this router is mounted under (``/v1``) rather than a hardcoded ``/jobs/...``
    that would go stale under versioning. Falls back to relative paths derived from the
    router's own prefix if URL resolution is unavailable (e.g. the router is exercised
    outside a real ASGI request in a unit test)."""
    try:
        status_url = str(http_request.url_for("get_job", job_id=job_id))
        events_url = str(http_request.url_for("job_events", job_id=job_id))
    except Exception:  # pragma: no cover - only outside a real request scope
        base = router.prefix
        status_url = f"{base}/{job_id}"
        events_url = f"{base}/{job_id}/events"
    return status_url, events_url


@router.post("", status_code=202, response_model=JobAccepted)
def enqueue_job(
    request: WindJobRequest,
    background: BackgroundTasks,
    http_request: Request,
    store: Annotated[JobStore, Depends(get_store)],
    subject: Annotated[str, Depends(get_current_subject)],
) -> JobAccepted:
    """Queue an async live-ERA5 finance job and schedule it to run.

    The job is bound to the authenticated ``subject`` so only its owner can later
    read it (per-client isolation). The queued record is created the same way on
    both backends; only the SCHEDULING differs (#663): the default ``memory`` backend
    runs ``run_wind_job`` in-process via ``BackgroundTasks`` (unchanged, byte-identical),
    while ``redis`` produces the job onto the arq queue for the durable, cross-process
    worker. Both drive the same ``run_wind_job`` orchestration. The route stays sync
    (FastAPI runs it in a threadpool with no running loop, so the arq enqueue — which is
    async — runs via ``asyncio.run`` on the redis branch only).
    """
    job_id = _new_job_id()
    store.create(
        JobRecord(**new_queued_record(job_id, now=utc_now_iso(), owner=subject))
    )
    if JOBS_BACKEND == "redis":
        import asyncio

        asyncio.run(_enqueue_to_arq(job_id, request))
    else:
        background.add_task(run_wind_job, job_id, request, store)
    status_url, events_url = _job_urls(http_request, job_id)
    return JobAccepted(
        job_id=job_id,
        state=JobState.QUEUED,
        status_url=status_url,
        events_url=events_url,
    )


def _owned_record_or_404(store: JobStore, job_id: str, subject: str) -> JobRecord:
    """Return the job iff it exists and ``subject`` owns it, else raise 404.

    A non-owner (and an unknown id) get the **same** 404 — the response never
    discloses that another client's job exists (non-leaking isolation).
    """
    record = store.get(job_id)
    if record is None or record.owner != subject:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return record


@router.get("/{job_id}", response_model=JobRecord)
def get_job(
    job_id: str,
    store: Annotated[JobStore, Depends(get_store)],
    subject: Annotated[str, Depends(get_current_subject)],
) -> JobRecord:
    """Return the current state of a job the caller owns (404 otherwise)."""
    return _owned_record_or_404(store, job_id, subject)


@router.get("/{job_id}/events")
def job_events(
    job_id: str,
    request: Request,
    store: Annotated[JobStore, Depends(get_store)],
    subject: Annotated[str, Depends(get_current_subject)],
) -> StreamingResponse:
    """Stream a job's progress as SSE until terminal, timeout, or disconnect.

    Ownership is checked up front: a non-owner or unknown id gets a 404 before any
    stream opens (non-leaking isolation), rather than an SSE error frame.
    """
    _owned_record_or_404(store, job_id, subject)
    return StreamingResponse(
        job_event_stream(store, job_id, is_disconnected=request.is_disconnected),
        media_type="text/event-stream",
    )
