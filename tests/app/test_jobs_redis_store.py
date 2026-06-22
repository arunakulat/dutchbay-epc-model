"""Tests for RedisJobStore against a fake synchronous client (no real Redis)."""

from __future__ import annotations

from typing import Dict, Optional

import pytest

from app.jobs.models import JobProgress, JobRecord, JobState
from app.jobs.redis_store import RedisJobStore


class _FakeRedis:
    """A minimal dict-backed stand-in storing bytes, like redis-py."""

    def __init__(self) -> None:
        self._data: Dict[str, bytes] = {}

    def get(self, key: str) -> Optional[bytes]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value.encode("utf-8")


def _record(job_id: str = "j1", state: JobState = JobState.QUEUED) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        state=state,
        progress=JobProgress(step=0, total_steps=4, message="Queued"),
        created_at="t0",
        updated_at="t0",
    )


def test_create_get_roundtrip() -> None:
    store = RedisJobStore(_FakeRedis())
    store.create(_record())
    got = store.get("j1")
    assert got is not None
    assert got.job_id == "j1" and got.state is JobState.QUEUED


def test_namespaced_key() -> None:
    client = _FakeRedis()
    RedisJobStore(client, namespace="ns").create(_record())
    assert "ns:j1" in client._data


def test_get_unknown_returns_none() -> None:
    assert RedisJobStore(_FakeRedis()).get("nope") is None


def test_update_roundtrips_and_stamps_clock() -> None:
    store = RedisJobStore(_FakeRedis(), clock=lambda: "t5")
    store.create(_record())
    updated = store.update("j1", state=JobState.RUNNING)
    assert updated.state is JobState.RUNNING
    assert updated.updated_at == "t5"
    assert store.get("j1").state is JobState.RUNNING  # type: ignore[union-attr]


def test_update_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        RedisJobStore(_FakeRedis()).update("ghost", state=JobState.RUNNING)


def test_decodes_str_values_too() -> None:
    # A client returning str (decode_responses=True) must also work.
    class _StrRedis(_FakeRedis):
        def get(self, key: str):  # type: ignore[override]
            raw = self._data.get(key)
            return raw.decode("utf-8") if raw is not None else None

    store = RedisJobStore(_StrRedis())
    store.create(_record())
    assert store.get("j1") is not None  # type: ignore[union-attr]
