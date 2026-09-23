"""#663 — job-backend gate: memory (default, byte-identical) vs redis (durable, gated).

The Redis/arq round-trip itself needs the optional ``[jobs]`` extra + a live Redis, so it
cannot be CI-verified; these tests pin the parts that CAN be: the default backend is
``memory`` (the pre-#663 in-process path), and the ``redis`` backend fails LOUD (CASPER)
rather than silently when the extra is absent.
"""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

import app.api.jobs_router as jr
from app.jobs.config import JOBS_BACKEND, JOBS_QUEUE, JOBS_REDIS_URL
from app.jobs.store import InMemoryJobStore


def test_default_backend_is_memory() -> None:
    """The default (no env override) is the in-process path — byte-identical to pre-#663."""
    assert JOBS_BACKEND == "memory"


def test_build_default_store_memory_is_inmemory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Memory storage remains available with both optional jobs imports blocked."""
    monkeypatch.setitem(sys.modules, "arq", None)
    monkeypatch.setitem(sys.modules, "redis", None)
    assert isinstance(jr._build_default_store(), InMemoryJobStore)


def test_get_store_is_lazily_cached() -> None:
    """get_store builds once and returns the same instance thereafter."""
    jr._default_store = None  # reset the module cache for a deterministic check
    first = jr.get_store()
    assert first is jr.get_store()
    assert isinstance(first, InMemoryJobStore)


@pytest.fixture(params=["arq", "redis"])
def missing_jobs_dependency(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Block one jobs import while making its companion independently available."""
    missing = str(request.param)
    for name in ("arq", "redis"):
        monkeypatch.setitem(
            sys.modules, name, None if name == missing else ModuleType(name)
        )
    return missing


def _assert_jobs_dependency_error(error: RuntimeError, missing: str) -> None:
    """Require installation guidance and the original missing-module cause."""
    assert "[jobs] extra" in str(error)
    assert "pip install -e '.[jobs]'" in str(error)
    assert isinstance(error.__cause__, ModuleNotFoundError)
    assert error.__cause__.name == missing
    assert "None in sys.modules" in str(error.__cause__)


def test_redis_backend_fails_loud_without_jobs_extra(
    monkeypatch: pytest.MonkeyPatch, missing_jobs_dependency: str
) -> None:
    """Redis storage fails at the real call-time guard for either missing import."""
    monkeypatch.setattr(jr, "JOBS_BACKEND", "redis")
    with pytest.raises(RuntimeError) as exc_info:
        jr._build_default_store()
    _assert_jobs_dependency_error(exc_info.value, missing_jobs_dependency)


def test_require_jobs_extra_message_is_actionable(missing_jobs_dependency: str) -> None:
    """The real guard identifies either missing dependency with actionable guidance."""
    with pytest.raises(RuntimeError) as exc_info:
        jr._require_jobs_extra()
    _assert_jobs_dependency_error(exc_info.value, missing_jobs_dependency)


def test_require_jobs_extra_accepts_available_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both available import seams make the guard a no-op without live Redis."""
    for name in ("arq", "redis"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    jr._require_jobs_extra()


def test_config_redis_defaults() -> None:
    assert JOBS_REDIS_URL.startswith("redis://")
    assert JOBS_QUEUE == "dutchbay:wind_jobs"
