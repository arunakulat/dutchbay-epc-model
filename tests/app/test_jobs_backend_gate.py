"""#663 — job-backend gate: memory (default, byte-identical) vs redis (durable, gated).

The Redis/arq round-trip itself needs the optional ``[jobs]`` extra + a live Redis, so it
cannot be CI-verified; these tests pin the parts that CAN be: the default backend is
``memory`` (the pre-#663 in-process path), and the ``redis`` backend fails LOUD (CASPER)
rather than silently when the extra is absent.
"""

from __future__ import annotations

import pytest

import app.api.jobs_router as jr
from app.jobs.config import JOBS_BACKEND, JOBS_QUEUE, JOBS_REDIS_URL
from app.jobs.store import InMemoryJobStore


def test_default_backend_is_memory() -> None:
    """The default (no env override) is the in-process path — byte-identical to pre-#663."""
    assert JOBS_BACKEND == "memory"


def test_build_default_store_memory_is_inmemory() -> None:
    assert isinstance(jr._build_default_store(), InMemoryJobStore)


def test_get_store_is_lazily_cached() -> None:
    """get_store builds once and returns the same instance thereafter."""
    jr._default_store = None  # reset the module cache for a deterministic check
    first = jr.get_store()
    assert first is jr.get_store()
    assert isinstance(first, InMemoryJobStore)


def test_redis_backend_fails_loud_without_jobs_extra(monkeypatch) -> None:
    """With JOBS_BACKEND='redis' but the [jobs] extra absent (arq/redis not installed),
    resolving the store RAISES an actionable error rather than degrading silently."""
    pytest.importorskip  # noqa: B018 — sentinel; we assert the ABSENCE path below
    try:
        import arq  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("[jobs] extra installed — the fail-loud path is not exercised")

    monkeypatch.setattr(jr, "JOBS_BACKEND", "redis")
    with pytest.raises(RuntimeError, match=r"\[jobs\] extra"):
        jr._build_default_store()


def test_require_jobs_extra_message_is_actionable(monkeypatch) -> None:
    try:
        import arq  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="pip install"):
            jr._require_jobs_extra()
    else:
        jr._require_jobs_extra()  # installed → no-op


def test_config_redis_defaults() -> None:
    assert JOBS_REDIS_URL.startswith("redis://")
    assert JOBS_QUEUE == "dutchbay:wind_jobs"
