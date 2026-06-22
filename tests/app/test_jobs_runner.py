"""Tests for the async job runner (orchestration; ERA5 step injected)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

import pytest

import app.jobs.runner as runner_mod
from app.jobs.models import JobRecord, JobState, WindJobRequest
from app.jobs.runner import TOTAL_STEPS, new_queued_record, run_wind_job
from app.jobs.store import InMemoryJobStore
from app.models.inputs import WindFarmInputs

_FAKE_EXPORT = {"scenario": "P75", "annual_generation_mwh": 473_800.0}
_CANNED_RESULT = {
    "status": "success",
    "kpis": {"project_irr": 0.05, "min_dscr": 1.30},
    "run_manifest": {"commit": "abc"},
}


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


def _seed_queued(store: InMemoryJobStore, job_id: str = "j1") -> None:
    store.create(JobRecord(**new_queued_record(job_id, now="t0")))


def _good_assessment(_req: WindJobRequest, progress: Any) -> Mapping[str, Any]:
    progress(1, "step one")
    progress(2, "step two")
    return _FAKE_EXPORT


def test_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_mod, "run_integrated_case", lambda *a, **k: _CANNED_RESULT)
    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)
    rec = store.get("j1")
    assert rec is not None
    assert rec.state is JobState.SUCCEEDED
    assert rec.result is not None and rec.result["kpis"]["project_irr"] == pytest.approx(0.05)
    assert rec.progress.step == TOTAL_STEPS and rec.progress.message == "Complete"
    assert rec.error is None


def test_passes_wind_export_and_scenario_name(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}

    def _spy(scenario: Any, wind_export: Any, **kwargs: Any) -> Dict[str, Any]:
        captured["scenario"] = scenario
        captured["wind_export"] = wind_export
        captured["scenario_name"] = kwargs.get("scenario_name")
        return _CANNED_RESULT

    monkeypatch.setattr(runner_mod, "run_integrated_case", _spy)
    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)
    assert captured["wind_export"] == _FAKE_EXPORT
    assert captured["scenario_name"] == "P75"
    assert isinstance(captured["scenario"], dict)


def test_progress_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: List[Tuple[int, str]] = []
    base_store = InMemoryJobStore()

    class _RecordingStore(InMemoryJobStore):
        def update(self, job_id: str, **changes: Any) -> JobRecord:
            if "progress" in changes:
                p = changes["progress"]
                seen.append((p.step, p.message))
            return super().update(job_id, **changes)

    monkeypatch.setattr(runner_mod, "run_integrated_case", lambda *a, **k: _CANNED_RESULT)
    store = _RecordingStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)
    steps = [s for s, _ in seen]
    assert 1 in steps and 2 in steps  # assessment progress
    assert TOTAL_STEPS - 1 in steps  # finance step
    assert TOTAL_STEPS in steps  # completion
    _ = base_store


def test_assessment_failure_marks_failed() -> None:
    def _boom(_req: WindJobRequest, _progress: Any) -> Mapping[str, Any]:
        raise RuntimeError("era5 unavailable")

    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_boom)
    rec = store.get("j1")
    assert rec is not None
    assert rec.state is JobState.FAILED
    assert "RuntimeError" in (rec.error or "")
    assert "era5 unavailable" in (rec.error or "")


def test_finance_failure_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(*_a: Any, **_k: Any) -> Dict[str, Any]:
        raise ValueError("drift too high")

    monkeypatch.setattr(runner_mod, "run_integrated_case", _explode)
    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)
    rec = store.get("j1")
    assert rec is not None and rec.state is JobState.FAILED
    assert "ValueError" in (rec.error or "")


def test_new_queued_record_shape() -> None:
    kwargs = new_queued_record("abc", now="t9")
    assert kwargs["state"] is JobState.QUEUED
    assert kwargs["created_at"] == "t9" and kwargs["updated_at"] == "t9"
    assert kwargs["progress"].step == 0
    # Constructs a valid JobRecord.
    assert JobRecord(**kwargs).job_id == "abc"
