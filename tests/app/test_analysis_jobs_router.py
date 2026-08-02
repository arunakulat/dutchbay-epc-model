"""Tests for the async analysis-jobs router endpoint (#993 PR-B1/PR-B2).

Endpoint functions are called directly. The analysis job reuses the shared status/SSE
routes and per-owner isolation; only the enqueue handler and the redis fail-loud guard
are new here.
"""

from __future__ import annotations

from typing import Literal

import pytest
from fastapi import BackgroundTasks, HTTPException

import app.api.jobs_router as jr
from app.jobs.analysis_runner import ANALYSIS_TOTAL_STEPS
from app.jobs.models import AnalysisJobRequest, JobRecord, JobState, WindJobRequest
from app.jobs.store import InMemoryJobStore
from app.models.inputs import WindFarmInputs


def _request(
    analysis_type: Literal["mc", "tornado"] = "mc",
) -> AnalysisJobRequest:
    return AnalysisJobRequest(
        analysis_type=analysis_type,
        n_trials=200,
        wind=WindJobRequest(
            inputs=WindFarmInputs(
                site_name="Dutch Bay",
                capacity_mw=150.0,
                capacity_factor=0.339,
                project_life_years=20,
                ppa_price_lkr_per_kwh=26.0,
                ppa_term_years=20,
                capex_total_usd=195_000_000,
                opex_annual_usd=6_000_000,
                fx_start_lkr_per_usd=333.79,
            ),
            site_lat=8.33,
            site_lon=79.76,
            turbine_model="iea_reference_10mw",
            num_turbines=15,
            hub_height_m=119.0,
            resource_mode="weibull",
            weibull_a=8.199,
            weibull_k=2.665,
        ),
    )


class _FakeRequest:
    """Minimal Starlette-Request stand-in (no url_for -> the URL builder falls back to
    router-prefix-relative paths, matching the wind-job router tests)."""

    async def is_disconnected(self) -> bool:  # pragma: no cover - not awaited here
        return False


class _SpyStore(InMemoryJobStore):
    def __init__(self) -> None:
        super().__init__()
        self.created = 0

    def create(self, record: JobRecord) -> JobRecord:
        self.created += 1
        return super().create(record)


def test_enqueue_analysis_creates_queued_record_and_schedules_task() -> None:
    store = InMemoryJobStore()
    background = BackgroundTasks()
    accepted = jr.enqueue_analysis_job(
        _request(),
        background,
        _FakeRequest(),
        store=store,
        subject="u1",  # type: ignore[arg-type]
    )
    assert accepted.state is JobState.QUEUED
    assert accepted.status_url == f"/jobs/{accepted.job_id}"
    assert accepted.events_url == f"/jobs/{accepted.job_id}/events"
    # A background task is scheduled (NOT executed here -> no engine run).
    assert len(background.tasks) == 1
    record = store.get(accepted.job_id)
    assert record is not None and record.state is JobState.QUEUED
    assert record.owner == "u1"
    # The queued record advertises the analysis step budget, not the wind one.
    assert record.progress.total_steps == ANALYSIS_TOTAL_STEPS


def test_enqueue_tornado_preserves_analysis_type_in_scheduled_task() -> None:
    """The shared endpoint queues the PR-B2 request without coercing it to MC."""
    store = InMemoryJobStore()
    background = BackgroundTasks()
    accepted = jr.enqueue_analysis_job(
        _request("tornado"),
        background,
        _FakeRequest(),
        store=store,
        subject="u1",  # type: ignore[arg-type]
    )

    assert accepted.state is JobState.QUEUED
    assert len(background.tasks) == 1
    scheduled_request = background.tasks[0].args[1]
    assert isinstance(scheduled_request, AnalysisJobRequest)
    assert scheduled_request.analysis_type == "tornado"


def test_enqueued_analysis_job_readable_via_shared_status_route() -> None:
    """The shared GET /jobs/{id} serves an analysis job to its owner (type-agnostic)."""
    store = InMemoryJobStore()
    accepted = jr.enqueue_analysis_job(
        _request(),
        BackgroundTasks(),
        _FakeRequest(),
        store=store,
        subject="u1",  # type: ignore[arg-type]
    )
    record = jr.get_job(accepted.job_id, store=store, subject="u1")
    assert record.job_id == accepted.job_id


def test_analysis_job_other_owner_404() -> None:
    """A different subject cannot read another client's analysis job (non-leaking 404)."""
    store = InMemoryJobStore()
    accepted = jr.enqueue_analysis_job(
        _request(),
        BackgroundTasks(),
        _FakeRequest(),
        store=store,
        subject="u1",  # type: ignore[arg-type]
    )
    with pytest.raises(HTTPException) as exc:
        jr.get_job(accepted.job_id, store=store, subject="u2")
    assert exc.value.status_code == 404
    assert exc.value.detail == f"unknown job: {accepted.job_id}"


def test_enqueue_analysis_redis_backend_enqueues_to_arq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR-B-redis: on the redis backend the analysis job is CREATED and produced onto the
    arq queue (parity with the wind path) — no longer 501'd, and not run via
    BackgroundTasks. The arq producer is faked so no live Redis is needed."""
    monkeypatch.setattr(jr, "JOBS_BACKEND", "redis")
    calls: list[tuple[str, AnalysisJobRequest]] = []

    async def _fake_enqueue(job_id: str, request: AnalysisJobRequest) -> None:
        calls.append((job_id, request))

    monkeypatch.setattr(jr, "_enqueue_analysis_to_arq", _fake_enqueue)
    store = _SpyStore()
    background = BackgroundTasks()
    req = _request()
    accepted = jr.enqueue_analysis_job(
        req, background, _FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    assert accepted.state is JobState.QUEUED
    # The queued record IS created (unlike the old 501 path)...
    assert store.created == 1
    record = store.get(accepted.job_id)
    assert record is not None and record.owner == "u1"
    # ...produced onto the arq queue, NOT scheduled via BackgroundTasks.
    assert len(background.tasks) == 0
    assert calls == [(accepted.job_id, req)]
