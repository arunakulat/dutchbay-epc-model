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
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional

from app.jobs.config import SSE_MAX_POLLS, SSE_POLL_INTERVAL_SECONDS
from app.jobs.models import TERMINAL_STATES
from app.jobs.store import JobStore

#: ``(seconds) -> awaitable`` — the inter-poll delay, injectable for tests.
SleepFn = Callable[[float], Awaitable[None]]

#: ``() -> awaitable[bool]`` — client-disconnect probe (e.g. ``Request.is_disconnected``).
DisconnectFn = Callable[[], Awaitable[bool]]


def format_sse(event: str, data: Mapping[str, Any]) -> str:
    """Format one SSE frame (``event:`` + JSON ``data:`` + blank line)."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def job_event_stream(
    store: JobStore,
    job_id: str,
    *,
    poll_interval: float = SSE_POLL_INTERVAL_SECONDS,
    max_polls: int = SSE_MAX_POLLS,
    sleep: SleepFn = asyncio.sleep,
    is_disconnected: Optional[DisconnectFn] = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for a job until it terminates, times out, or disconnects.

    Emits a ``progress`` frame on every observed change and a final frame named for
    the terminal state (``succeeded`` / ``failed``). Self-closes after ``max_polls``
    non-terminal polls (a ``timeout`` frame, so a stuck job cannot busy-poll
    forever), stops silently if the client disconnects, and yields a single
    ``error`` frame for an unknown job.

    Args:
        store: The job store to poll.
        job_id: The job to follow.
        poll_interval: Seconds between polls while the job is non-terminal.
        max_polls: Hard cap on non-terminal polls before the stream self-closes.
        sleep: Awaitable delay (injectable).
        is_disconnected: Optional probe; when it returns ``True`` the stream stops.

    Yields:
        SSE-formatted strings.
    """
    last_signature: Any = None
    polls = 0
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
        polls += 1
        if polls >= max_polls:
            yield format_sse(
                "timeout",
                {"detail": "stream timed out; poll GET /jobs/{id}", "job_id": job_id},
            )
            return
        if is_disconnected is not None and await is_disconnected():
            return
        await sleep(poll_interval)
