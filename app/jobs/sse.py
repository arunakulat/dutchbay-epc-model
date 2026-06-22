"""Server-Sent Events stream for job progress.

A one-way HTTP stream (per the deep-research recommendation — SSE over WebSockets
for this push-only case) that emits a frame whenever a job's state or progress
changes, then a terminal frame and closes. The poll loop reads the
:class:`~app.jobs.store.JobStore`; ``sleep`` is injectable so tests drive it
deterministically without real time.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping

from app.jobs.models import TERMINAL_STATES
from app.jobs.store import JobStore

#: ``(seconds) -> awaitable`` — the inter-poll delay, injectable for tests.
SleepFn = Callable[[float], Awaitable[None]]


def format_sse(event: str, data: Mapping[str, Any]) -> str:
    """Format one SSE frame (``event:`` + JSON ``data:`` + blank line)."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def job_event_stream(
    store: JobStore,
    job_id: str,
    *,
    poll_interval: float = 0.5,
    sleep: SleepFn = asyncio.sleep,
) -> AsyncIterator[str]:
    """Yield SSE frames for a job until it reaches a terminal state.

    Emits a ``progress`` frame on every observed change, a final frame named for
    the terminal state (``succeeded`` / ``failed``), then stops. An unknown job
    yields a single ``error`` frame and stops.

    Args:
        store: The job store to poll.
        job_id: The job to follow.
        poll_interval: Seconds between polls while the job is non-terminal.
        sleep: Awaitable delay (injectable).

    Yields:
        SSE-formatted strings.
    """
    last_signature: Any = None
    while True:
        record = store.get(job_id)
        if record is None:
            yield format_sse("error", {"detail": f"unknown job: {job_id}"})
            return
        signature = (record.state.value, record.progress.step, record.progress.message)
        if signature != last_signature:
            yield format_sse("progress", record.model_dump(mode="json"))
            last_signature = signature
        if record.state in TERMINAL_STATES:
            yield format_sse(record.state.value, record.model_dump(mode="json"))
            return
        await sleep(poll_interval)
