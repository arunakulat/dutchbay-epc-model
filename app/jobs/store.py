"""Job-record stores: an in-process default and a pluggable seam for Redis.

``JobStore`` is the abstraction the runner, the API, and the SSE stream depend
on. ``InMemoryJobStore`` is the default — sufficient for the single-process
``BackgroundTasks`` path and fully testable. A durable, cross-process
``RedisJobStore`` (optional ``[jobs]`` extra) implements the same protocol for the
arq worker; the seam means neither the runner nor the API changes when swapping
backends (Dolphin: one orchestration, swappable persistence).
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional, Protocol

from app.jobs.models import JobRecord, utc_now_iso


class JobStore(Protocol):
    """Persistence seam for job records (thread-safe; returns detached copies)."""

    def create(self, record: JobRecord) -> None:
        """Insert a new job record."""
        ...

    def get(self, job_id: str) -> Optional[JobRecord]:
        """Return a copy of the record, or ``None`` if unknown."""
        ...

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        """Apply field changes (stamping ``updated_at``); return the new record.

        Raises ``KeyError`` if the job is unknown.
        """
        ...


class InMemoryJobStore:
    """A thread-safe, in-process :class:`JobStore` backed by a dict.

    Reads and writes are guarded by a lock and return deep copies, so a caller
    can never mutate stored state by reference. The clock is injectable for
    deterministic tests (CASPER).
    """

    def __init__(self, *, clock: Callable[[], str] = utc_now_iso) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def create(self, record: JobRecord) -> None:
        with self._lock:
            self._jobs[record.job_id] = record.model_copy(deep=True)

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            record = self._jobs.get(job_id)
            return record.model_copy(deep=True) if record is not None else None

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            updated = record.model_copy(update={**changes, "updated_at": self._clock()})
            self._jobs[job_id] = updated
            return updated.model_copy(deep=True)
