"""Tests for the in-memory job store."""

from __future__ import annotations

import pytest

from app.jobs.models import JobProgress, JobRecord, JobState
from app.jobs.store import InMemoryJobStore


def _record(job_id: str = "j1", state: JobState = JobState.QUEUED) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        state=state,
        progress=JobProgress(step=0, total_steps=4, message="Queued"),
        created_at="t0",
        updated_at="t0",
    )


def test_create_and_get() -> None:
    store = InMemoryJobStore()
    store.create(_record())
    got = store.get("j1")
    assert got is not None
    assert got.job_id == "j1" and got.state is JobState.QUEUED


def test_get_unknown_returns_none() -> None:
    assert InMemoryJobStore().get("nope") is None


def test_get_returns_detached_copy() -> None:
    store = InMemoryJobStore()
    store.create(_record())
    a = store.get("j1")
    assert a is not None
    a.state = JobState.FAILED  # mutating the copy must not leak back
    assert store.get("j1").state is JobState.QUEUED  # type: ignore[union-attr]


def test_update_changes_fields_and_stamps_clock() -> None:
    store = InMemoryJobStore(clock=lambda: "t1")
    store.create(_record())
    updated = store.update("j1", state=JobState.RUNNING)
    assert updated.state is JobState.RUNNING
    assert updated.updated_at == "t1"
    assert store.get("j1").updated_at == "t1"  # type: ignore[union-attr]


def test_update_progress() -> None:
    store = InMemoryJobStore()
    store.create(_record())
    updated = store.update(
        "j1", progress=JobProgress(step=2, total_steps=4, message="halfway")
    )
    assert updated.progress.step == 2
    assert updated.progress.pct == 50.0


def test_update_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        InMemoryJobStore().update("ghost", state=JobState.RUNNING)
