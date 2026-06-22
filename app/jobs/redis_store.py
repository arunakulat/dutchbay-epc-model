"""A durable, cross-process :class:`~app.jobs.store.JobStore` backed by Redis.

The in-memory store cannot share state across processes, so the arq worker and the
API need a shared backend to report status. ``RedisJobStore`` implements the same
``JobStore`` protocol, serialising each record as JSON under a namespaced key.

It takes an injected **synchronous** Redis client (duck-typed: ``get``/``set``), so
it carries no hard dependency on ``redis`` at import time and is unit-testable with
a tiny fake client. The actual ``redis`` package ships in the optional ``[jobs]``
extra. ``update`` is a read-modify-write; that is safe here because, during a job's
lifetime, only its single worker writes (the API only reads).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.jobs.models import JobRecord, utc_now_iso


class RedisLike:
    """Structural type documenting the sync client methods used (get/set)."""

    def get(self, key: str) -> Any: ...  # pragma: no cover - typing shim
    def set(self, key: str, value: str) -> Any: ...  # pragma: no cover - typing shim


class RedisJobStore:
    """JSON-serialising JobStore over a synchronous Redis client."""

    def __init__(
        self,
        client: RedisLike,
        *,
        namespace: str = "dutchbay:job",
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._client = client
        self._namespace = namespace
        self._clock = clock

    def _key(self, job_id: str) -> str:
        return f"{self._namespace}:{job_id}"

    @staticmethod
    def _decode(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        return raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)

    def create(self, record: JobRecord) -> None:
        self._client.set(self._key(record.job_id), record.model_dump_json())

    def get(self, job_id: str) -> Optional[JobRecord]:
        raw = self._decode(self._client.get(self._key(job_id)))
        return JobRecord.model_validate_json(raw) if raw is not None else None

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        raw = self._decode(self._client.get(self._key(job_id)))
        if raw is None:
            raise KeyError(job_id)
        record = JobRecord.model_validate_json(raw)
        updated = record.model_copy(update={**changes, "updated_at": self._clock()})
        self._client.set(self._key(job_id), updated.model_dump_json())
        return updated
