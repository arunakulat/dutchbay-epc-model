"""Operational knobs for the synchronous web routes (CCCDIR: env-overridable defaults).

These are deployment/operational limits — not finance inputs — so they read from the
environment with documented defaults rather than living in a scenario/report YAML, mirroring
:mod:`app.jobs.config`. Every consumer also takes the value as an explicit parameter
(defaulting to these), so tests stay deterministic without touching the environment.
"""

from __future__ import annotations

import os


def _float_env(name: str, default: float) -> float:
    """Read a float from the environment, falling back to ``default``."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    """Read an int from the environment, falling back to ``default``."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


#: Wall-clock ceiling (seconds) for the synchronous ``/cases*`` compute routes. Bounds the
#: client wait and frees the request on a pathological hang. Generous by default so a normal
#: run — including the report routes' tornado + Morris sweeps — never trips it. NOTE: the
#: underlying worker thread cannot be force-cancelled (see
#: :func:`app.api.main._run_with_timeout`), so the ceiling bounds the client wait, not the
#: computation itself.
SYNC_ROUTE_TIMEOUT_SECONDS = _float_env("DUTCHBAY_SYNC_ROUTE_TIMEOUT", 120.0)

#: Max concurrent synchronous ``/cases*`` computations. Because a timed-out compute keeps
#: running on its worker thread (see :func:`app.api.main._run_with_timeout`), it continues to
#: count against this bound until it actually finishes — so a slow client cannot accumulate
#: unbounded background compute (the bound a timeout alone would otherwise defeat). When every
#: slot is occupied the route sheds load with ``503`` rather than queueing. ``<= 0`` disables
#: the explicit bound (falling back to the threadpool's own limiter).
SYNC_ROUTE_MAX_CONCURRENCY = _int_env("DUTCHBAY_SYNC_ROUTE_MAX_CONCURRENCY", 8)
