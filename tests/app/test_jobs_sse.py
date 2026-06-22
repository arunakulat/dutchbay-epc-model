"""Tests for the SSE progress stream (driven without real time)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, List, Optional

from app.jobs.models import JobProgress, JobRecord, JobState
from app.jobs.sse import format_sse, job_event_stream
from app.jobs.store import InMemoryJobStore


def _collect(agen: AsyncIterator[str]) -> List[str]:
    async def _run() -> List[str]:
        return [frame async for frame in agen]

    return asyncio.run(_run())


def _record(state: JobState, step: int, message: str) -> JobRecord:
    return JobRecord(
        job_id="j1",
        state=state,
        progress=JobProgress(step=step, total_steps=4, message=message),
        created_at="t0",
        updated_at="t0",
    )


def test_format_sse_frame() -> None:
    frame = format_sse("progress", {"a": 1})
    assert frame == 'event: progress\ndata: {"a": 1}\n\n'


def test_unknown_job_yields_error_frame() -> None:
    frames = _collect(job_event_stream(InMemoryJobStore(), "ghost"))
    assert len(frames) == 1
    assert frames[0].startswith("event: error")
    assert "unknown job" in frames[0]


def test_terminal_job_emits_progress_then_terminal() -> None:
    store = InMemoryJobStore()
    store.create(_record(JobState.SUCCEEDED, 4, "Complete"))
    frames = _collect(job_event_stream(store, "j1"))
    assert [f.split("\n", 1)[0] for f in frames] == [
        "event: progress",
        "event: succeeded",
    ]
    # The terminal frame carries the full record.
    payload = json.loads(frames[1].split("data: ", 1)[1])
    assert payload["state"] == "succeeded"


def test_failed_terminal_event_name() -> None:
    store = InMemoryJobStore()
    store.create(_record(JobState.FAILED, 1, "boom"))
    frames = _collect(job_event_stream(store, "j1"))
    assert frames[-1].startswith("event: failed")


class _SeqStore:
    """A fake store whose ``get`` walks a fixed sequence of records."""

    def __init__(self, records: List[JobRecord]) -> None:
        self._records = records
        self._i = 0

    def get(self, _job_id: str) -> Optional[JobRecord]:
        rec = self._records[min(self._i, len(self._records) - 1)]
        self._i += 1
        return rec

    def create(self, record: JobRecord) -> None:  # pragma: no cover - unused
        ...

    def update(self, job_id: str, **changes: Any) -> JobRecord:  # pragma: no cover
        ...


def test_progress_dedup_and_sleep_between_polls() -> None:
    sleeps: List[float] = []

    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)

    store = _SeqStore(
        [
            _record(JobState.RUNNING, 1, "working"),
            _record(JobState.RUNNING, 1, "working"),  # unchanged -> no new frame
            _record(JobState.SUCCEEDED, 4, "Complete"),
        ]
    )
    frames = _collect(
        job_event_stream(store, "j1", poll_interval=0.1, sleep=_sleep)
    )
    kinds = [f.split("\n", 1)[0] for f in frames]
    # running emitted once (dedup), then succeeded progress + terminal.
    assert kinds == ["event: progress", "event: progress", "event: succeeded"]
    assert sleeps == [0.1, 0.1]  # slept between the three polls
