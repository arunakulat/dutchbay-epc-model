"""Operational knobs for the async job path (CCCDIR: env-overridable defaults).

These are deployment/operational limits — record retention, Redis TTL, SSE stream
lifetime — not finance inputs, so they read from the environment with documented
defaults rather than living in a scenario/report YAML. Every consumer also takes
the value as an explicit parameter (defaulting to these), so tests stay
deterministic without touching the environment.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    """Read an int from the environment, falling back to ``default``."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    """Read a float from the environment, falling back to ``default``."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


#: Max job records retained in the in-memory store; terminal jobs evict first.
MAX_RETAINED_JOBS = _int_env("DUTCHBAY_JOBS_MAX_RETAINED", 1000)

#: TTL (seconds) applied to Redis job records; 0 disables expiry.
JOB_TTL_SECONDS = _int_env("DUTCHBAY_JOBS_TTL_SECONDS", 86_400)

#: Max SSE polls before a stream self-closes (× poll interval = max lifetime).
SSE_MAX_POLLS = _int_env("DUTCHBAY_SSE_MAX_POLLS", 600)

#: Seconds between SSE polls while a job is non-terminal.
SSE_POLL_INTERVAL_SECONDS = _float_env("DUTCHBAY_SSE_POLL_INTERVAL", 0.5)


def _str_env(name: str, default: str) -> str:
    """Read a string from the environment, falling back to ``default``."""
    raw = os.environ.get(name)
    return raw if raw is not None and raw != "" else default


#: Job backend selector (#663 cutover). ``"memory"`` (default) is the in-process
#: ``BackgroundTasks`` + ``InMemoryJobStore`` path — complete, tested, byte-identical
#: to pre-#663. ``"redis"`` is the durable, cross-process path: the API enqueues onto
#: the arq queue and reads status from a shared ``RedisJobStore`` the worker writes.
#: Redis is an EXPLICIT opt-in (the URL below has a localhost default, so it must NOT
#: gate the cutover on its own) and requires the optional ``[jobs]`` extra + a live
#: Redis, so it cannot be CI-verified — hence the default stays ``"memory"``.
JOBS_BACKEND = _str_env("DUTCHBAY_JOBS_BACKEND", "memory").strip().lower()

#: Redis DSN for the durable job path (shared by the arq worker + the API). Only
#: consulted when ``JOBS_BACKEND == "redis"``.
JOBS_REDIS_URL = _str_env("DUTCHBAY_REDIS_URL", "redis://localhost:6379")

#: Named arq queue the API produces to and the worker consumes from.
JOBS_QUEUE = _str_env("DUTCHBAY_JOBS_QUEUE", "dutchbay:wind_jobs")
