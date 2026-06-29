"""HTTP surface for the asynchronous live-ERA5 job path.

* ``POST /jobs``              — enqueue a job (returns 202 + a ``JobAccepted`` handle).
* ``GET  /jobs/{id}``         — poll the job record (404 if unknown).
* ``GET  /jobs/{id}/events``  — SSE stream of progress until terminal/timeout.

The store is resolved through the :func:`get_store` dependency — the single
injection seam. Tests override it via ``app.dependency_overrides``; the durable
cross-process path replaces the default with a ``RedisJobStore``. The enqueue
handler only orchestrates: it creates a queued record and schedules
:func:`~app.jobs.runner.run_wind_job` via FastAPI ``BackgroundTasks`` (both the
in-process and the future arq paths drive the same ``run_wind_job``).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.auth import get_current_subject
from app.jobs.models import JobRecord, JobState, WindJobRequest, utc_now_iso
from app.jobs.runner import new_queued_record, run_wind_job
from app.jobs.sse import job_event_stream
from app.jobs.store import InMemoryJobStore, JobStore

router = APIRouter(prefix="/jobs", tags=["jobs"])

#: Process-default store. ``get_store`` is the injection seam: override it via
#: ``app.dependency_overrides[get_store]`` (tests) or point it at a RedisJobStore
#: for the durable, cross-process path — endpoints never reference it directly.
_default_store: JobStore = InMemoryJobStore()


def get_store() -> JobStore:
    """FastAPI dependency yielding the active job store (override to swap)."""
    return _default_store


class JobAccepted(BaseModel):
    """The handle returned when a job is queued."""

    job_id: str
    state: JobState
    status_url: str
    events_url: str


def _new_job_id() -> str:
    return uuid.uuid4().hex


@router.post("", status_code=202, response_model=JobAccepted)
def enqueue_job(
    request: WindJobRequest,
    background: BackgroundTasks,
    store: JobStore = Depends(get_store),
    subject: str = Depends(get_current_subject),
) -> JobAccepted:
    """Queue an async live-ERA5 finance job and schedule it to run.

    The job is bound to the authenticated ``subject`` so only its owner can later
    read it (per-client isolation).
    """
    job_id = _new_job_id()
    store.create(
        JobRecord(**new_queued_record(job_id, now=utc_now_iso(), owner=subject))
    )
    background.add_task(run_wind_job, job_id, request, store)
    return JobAccepted(
        job_id=job_id,
        state=JobState.QUEUED,
        status_url=f"/jobs/{job_id}",
        events_url=f"/jobs/{job_id}/events",
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
    store: JobStore = Depends(get_store),
    subject: str = Depends(get_current_subject),
) -> JobRecord:
    """Return the current state of a job the caller owns (404 otherwise)."""
    return _owned_record_or_404(store, job_id, subject)


@router.get("/{job_id}/events")
def job_events(
    job_id: str,
    request: Request,
    store: JobStore = Depends(get_store),
    subject: str = Depends(get_current_subject),
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
