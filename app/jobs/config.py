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
