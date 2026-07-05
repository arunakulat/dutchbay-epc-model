"""Optional arq + Redis worker for the async ERA5 job path (production scale).

The default path (``app.api.jobs_router`` + ``BackgroundTasks`` + in-memory store)
is complete and fully tested — adequate for a few known clients on one process.
For durability across restarts and horizontal scaling, this module runs the SAME
orchestration (``run_wind_job`` — Dolphin) under an arq worker, using a shared
``RedisJobStore`` so the API process can report status the worker produced.

It requires the optional ``[jobs]`` extra (``arq``, ``redis``) and a live Redis, so
it is loaded only by the ``arq`` CLI (and, when ``[jobs]`` is installed, by the gated
import-smoke ``tests/app/test_jobs_worker.py``) — never by the running app — and is
excluded from coverage (like the ERA5 ingestion path). Run with:

    pip install -e '.[jobs]'
    arq app.jobs.worker.WorkerSettings

This module is intentionally thin: the blocking job (``run_wind_job``) is offloaded
to a thread so it never stalls the arq event loop, and all job state lives in
Redis via :class:`~app.jobs.redis_store.RedisJobStore`.

NOT YET WIRED TO THE HTTP API. ``POST /jobs`` still runs via ``BackgroundTasks``
against the in-process store; nothing enqueues onto this arq queue yet. The final
cutover — the route producing to arq and ``get_store`` returning a RedisJobStore —
is a deliberate, Redis-gated follow-up (it cannot be CI-verified without a live
Redis). This worker plus :class:`RedisJobStore` are the verified building blocks
for that step; ``RedisJobStore`` is unit-tested against a fake client.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import redis as sync_redis
from arq.connections import RedisSettings

from app.jobs.config import JOBS_QUEUE, JOBS_REDIS_URL
from app.jobs.models import WindJobRequest
from app.jobs.redis_store import RedisJobStore
from app.jobs.runner import run_wind_job

#: Named queue + Redis URL are single-sourced in app.jobs.config (CCCDIR — the API
#: enqueue path and this worker MUST agree on the queue + DSN).
REDIS_URL = JOBS_REDIS_URL


async def run_wind_assessment_task(
    ctx: Dict[str, Any], job_id: str, payload: Dict[str, Any]
) -> str:
    """arq task: reconstruct the request and run the (blocking) job in a thread."""
    request = WindJobRequest.model_validate(payload)
    store: RedisJobStore = ctx["job_store"]
    await asyncio.to_thread(run_wind_job, job_id, request, store)
    return job_id


async def _on_startup(ctx: Dict[str, Any]) -> None:
    """Attach a shared RedisJobStore (sync client) to the worker context."""
    ctx["job_store"] = RedisJobStore(sync_redis.Redis.from_url(REDIS_URL))


class WorkerSettings:
    """arq worker settings (discovered by ``arq app.jobs.worker.WorkerSettings``)."""

    functions = [run_wind_assessment_task]
    on_startup = _on_startup
    queue_name = JOBS_QUEUE
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
