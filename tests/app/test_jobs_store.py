"""Tests for the in-memory job store."""

from __future__ import annotations

import pytest

from app.jobs.models import JobProgress, JobRecord, JobState
from app.jobs.store import InMemoryJobStore


def _record(job_id: str = "j1", state: JobState = JobState.QUEUED) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        owner="u1",
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


# --------------------------------------------------------------------------- #
# Bounded retention (memory-leak fix)
# --------------------------------------------------------------------------- #
def test_eviction_prefers_oldest_terminal_job() -> None:
    store = InMemoryJobStore(max_retained=2)
    store.create(_record("done", state=JobState.SUCCEEDED))  # oldest, terminal
    store.create(_record("running", state=JobState.RUNNING))
    store.create(_record("new", state=JobState.QUEUED))  # triggers eviction
    assert store.get("done") is None  # terminal evicted first
    assert store.get("running") is not None  # in-flight preserved
    assert store.get("new") is not None


def test_eviction_falls_back_to_oldest_when_none_terminal() -> None:
    store = InMemoryJobStore(max_retained=2)
    store.create(_record("a", state=JobState.RUNNING))  # oldest
    store.create(_record("b", state=JobState.RUNNING))
    store.create(_record("c", state=JobState.RUNNING))  # evicts oldest non-terminal
    assert store.get("a") is None
    assert store.get("b") is not None and store.get("c") is not None


def test_store_size_never_exceeds_cap() -> None:
    store = InMemoryJobStore(max_retained=5)
    for i in range(50):
        store.create(_record(f"j{i}", state=JobState.SUCCEEDED))
    # Only the cap's worth survive.
    survivors = sum(1 for i in range(50) if store.get(f"j{i}") is not None)
    assert survivors == 5


def test_max_retained_clamped_to_at_least_one() -> None:
    store = InMemoryJobStore(max_retained=0)
    store.create(_record("only"))
    assert store.get("only") is not None
