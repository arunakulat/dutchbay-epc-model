"""Asynchronous live-ERA5 job path: enqueue, run, and stream progress.

The slow ERA5 → finance chain runs as a background job with a pollable record and
an SSE progress stream. Orchestration reuses the canonical ``WindPipeline`` and the
``run_integrated_case`` service seam (Dolphin — no duplicated logic). The default
store is in-process; :class:`~app.jobs.redis_store.RedisJobStore` + ``app.jobs.worker``
(the optional ``[jobs]`` extra) provide the durable arq + Redis upgrade.

``app.jobs.worker`` is intentionally not re-exported here: it imports ``arq`` and is
loaded only by the arq CLI.
"""

from __future__ import annotations

from app.jobs.analysis_runner import (
    ANALYSIS_TOTAL_STEPS,
    default_analysis,
    run_analysis_job,
)
from app.jobs.models import (
    AnalysisJobRequest,
    JobProgress,
    JobRecord,
    JobState,
    WindJobRequest,
    utc_now_iso,
)
from app.jobs.redis_store import RedisJobStore
from app.jobs.runner import TOTAL_STEPS, default_assessment, run_wind_job
from app.jobs.sse import format_sse, job_event_stream
from app.jobs.store import InMemoryJobStore, JobStore

__all__ = [
    "AnalysisJobRequest",
    "JobProgress",
    "JobRecord",
    "JobState",
    "WindJobRequest",
    "utc_now_iso",
    "InMemoryJobStore",
    "JobStore",
    "RedisJobStore",
    "TOTAL_STEPS",
    "ANALYSIS_TOTAL_STEPS",
    "default_assessment",
    "default_analysis",
    "run_wind_job",
    "run_analysis_job",
    "format_sse",
    "job_event_stream",
]
