"""Gated import smoke for the deferred async arq worker (``app.jobs.worker``).

The arq + Redis worker is built and unit-tested (``RedisJobStore`` is covered against a fake
client) but is NOT wired to the HTTP API — the live ``POST /jobs`` path runs in-process via
``BackgroundTasks`` against ``InMemoryJobStore`` (see ``docs/WEB_SERVICE_ROADMAP.md``, "Current
status of the async path"). This test guards the worker module against bit-rot: when the optional
``[jobs]`` extra is installed it must import and expose a well-formed arq ``WorkerSettings``. It is
skipped (like the ``[report]`` / ``[solar]`` suites) when arq / redis are absent.
"""

from __future__ import annotations

import pytest

pytest.importorskip("arq")
pytest.importorskip("redis")


def test_worker_settings_are_well_formed() -> None:
    from app.jobs import worker

    ws = worker.WorkerSettings
    # The single async task is registered for arq discovery...
    assert worker.run_wind_assessment_task in ws.functions
    # ...and the discovery attributes the arq CLI reads are present and well-typed.
    assert callable(ws.on_startup)
    assert ws.queue_name == worker.JOBS_QUEUE
    assert ws.redis_settings is not None
