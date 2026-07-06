"""Tests for the async jobs router (endpoint functions called directly)."""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

import app.api.jobs_router as jr
from app.jobs.models import JobState, WindJobRequest
from app.jobs.store import InMemoryJobStore
from app.models.inputs import WindFarmInputs


def _request() -> WindJobRequest:
    return WindJobRequest(
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
        turbine_model="IEA-10MW",
        num_turbines=15,
        hub_height_m=119.0,
    )


class _FakeRequest:
    """Minimal stand-in for a Starlette Request.

    Only ``is_disconnected`` is used by ``job_events``; it deliberately has no
    ``url_for``, so ``enqueue_job``'s URL builder takes its fallback branch and yields
    the router-prefix-relative ``/jobs/{id}`` paths (asserted below)."""

    async def is_disconnected(self) -> bool:  # pragma: no cover - not awaited here
        return False


def test_get_store_returns_default() -> None:
    assert jr.get_store() is jr._default_store


def test_enqueue_creates_queued_record_and_schedules_task() -> None:
    store = InMemoryJobStore()
    background = BackgroundTasks()
    accepted = jr.enqueue_job(
        _request(), background, _FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    assert accepted.state is JobState.QUEUED
    assert accepted.status_url == f"/jobs/{accepted.job_id}"
    assert accepted.events_url == f"/jobs/{accepted.job_id}/events"
    # A background task was scheduled (NOT executed here -> no real ERA5).
    assert len(background.tasks) == 1
    # The injected store holds the queued record, bound to the authenticated owner.
    record = store.get(accepted.job_id)
    assert record is not None and record.state is JobState.QUEUED
    assert record.owner == "u1"


def test_get_job_found() -> None:
    store = InMemoryJobStore()
    background = BackgroundTasks()
    accepted = jr.enqueue_job(
        _request(), background, _FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    record = jr.get_job(accepted.job_id, store=store, subject="u1")
    assert record.job_id == accepted.job_id


def test_get_job_unknown_404() -> None:
    with pytest.raises(HTTPException) as exc:
        jr.get_job("does-not-exist", store=InMemoryJobStore(), subject="u1")
    assert exc.value.status_code == 404


def test_get_job_other_owner_404() -> None:
    """A different subject cannot read another client's job (non-leaking 404)."""
    store = InMemoryJobStore()
    accepted = jr.enqueue_job(
        _request(), BackgroundTasks(), _FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    with pytest.raises(HTTPException) as exc:
        jr.get_job(accepted.job_id, store=store, subject="u2")
    assert exc.value.status_code == 404
    # The 404 detail must not differ from the unknown-id case (no existence leak).
    assert exc.value.detail == f"unknown job: {accepted.job_id}"


def test_job_events_returns_sse_stream() -> None:
    store = InMemoryJobStore()
    accepted = jr.enqueue_job(
        _request(), BackgroundTasks(), _FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    resp = jr.job_events(
        accepted.job_id, request=_FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    assert isinstance(resp, StreamingResponse)
    assert resp.media_type == "text/event-stream"


def test_job_events_unknown_404() -> None:
    with pytest.raises(HTTPException) as exc:
        jr.job_events(
            "ghost", request=_FakeRequest(), store=InMemoryJobStore(), subject="u1"  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


def test_job_events_other_owner_404() -> None:
    """Ownership is enforced before any SSE stream opens (non-leaking 404)."""
    store = InMemoryJobStore()
    accepted = jr.enqueue_job(
        _request(), BackgroundTasks(), _FakeRequest(), store=store, subject="u1"  # type: ignore[arg-type]
    )
    with pytest.raises(HTTPException) as exc:
        jr.job_events(
            accepted.job_id, request=_FakeRequest(), store=store, subject="u2"  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404
