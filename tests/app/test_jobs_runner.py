"""Tests for the async job runner (orchestration; ERA5 step injected)."""

from __future__ import annotations

from pathlib import Path
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
    store.create(JobRecord(**new_queued_record(job_id, now="t0", owner="u1")))


def _good_assessment(_req: WindJobRequest, progress: Any) -> Mapping[str, Any]:
    progress(1, "step one")
    progress(2, "step two")
    return _FAKE_EXPORT


def test_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runner_mod, "run_integrated_case", lambda *a, **k: _CANNED_RESULT
    )
    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)
    rec = store.get("j1")
    assert rec is not None
    assert rec.state is JobState.SUCCEEDED
    assert rec.result is not None and rec.result["kpis"][
        "project_irr"
    ] == pytest.approx(0.05)
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

    monkeypatch.setattr(
        runner_mod, "run_integrated_case", lambda *a, **k: _CANNED_RESULT
    )
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
        raise RuntimeError("secret path /etc/era5/credentials")

    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_boom)
    rec = store.get("j1")
    assert rec is not None
    assert rec.state is JobState.FAILED
    # Exception class is surfaced for triage, but the raw message (which can leak
    # internal paths/config) is NOT echoed to the client.
    assert "RuntimeError" in (rec.error or "")
    assert "secret path" not in (rec.error or "")
    assert "/etc/era5" not in (rec.error or "")


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
    kwargs = new_queued_record("abc", now="t9", owner="u1")
    assert kwargs["state"] is JobState.QUEUED
    assert kwargs["owner"] == "u1"
    assert kwargs["created_at"] == "t9" and kwargs["updated_at"] == "t9"
    assert kwargs["progress"].step == 0
    # Constructs a valid JobRecord bound to its owner.
    record = JobRecord(**kwargs)
    assert record.job_id == "abc" and record.owner == "u1"


# --------------------------------------------------------------------------- #
# #952: the wind pipeline's scratch dirs must be a writable, self-cleaning
# per-job workspace (its relative defaults raise PermissionError under the
# non-root container user before any ERA5 fetch).
# --------------------------------------------------------------------------- #
def test_ephemeral_workspace_is_writable_then_removed() -> None:
    """A real writable dir during the block (mkdir under it works), gone after."""
    with runner_mod._ephemeral_workspace() as ws:
        assert ws.is_dir()
        nested = ws / "output" / "sub"
        nested.mkdir(parents=True)  # the exact op that raised PermissionError in prod
        (nested / "probe.txt").write_text("ok")
        captured = ws
    assert not captured.exists()  # cleaned up on normal exit


def test_ephemeral_workspace_removed_on_exception() -> None:
    """Cleanup is guaranteed even when the body raises (the load-bearing guarantee)."""
    captured: Dict[str, Any] = {}
    with pytest.raises(RuntimeError):
        with runner_mod._ephemeral_workspace() as ws:
            captured["ws"] = ws
            (ws / "f").write_text("x")
            raise RuntimeError("boom")
    assert not captured["ws"].exists()


def test_default_assessment_gives_pipeline_a_writable_ephemeral_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """default_assessment hands WindPipeline writable cache/output dirs and cleans up.

    Proves the #952 fix without the ``[wind]`` toolchain or Copernicus: a fake pipeline
    injected in place of ``wind_resource.wind_pipeline.WindPipeline`` records the dirs it
    is given, mkdirs them (the op that raised PermissionError in prod), and both must be
    gone once the assessment returns.
    """
    import sys
    import types

    seen: Dict[str, Any] = {}

    class _FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            seen["cache_dir"] = Path(kwargs["cache_dir"])
            seen["output_dir"] = Path(kwargs["output_dir"])
            # the real pipeline mkdirs these in __init__ — do the same to prove writability
            seen["cache_dir"].mkdir(parents=True, exist_ok=True)
            seen["output_dir"].mkdir(parents=True, exist_ok=True)

        def run_complete_assessment(self, **kwargs: Any) -> None:
            return None

        def export_for_cashflow_model(self, *, scenario: str) -> Mapping[str, Any]:
            return {"scenario": scenario, "annual_generation_mwh": 1.0}

    fake_mod = types.ModuleType("wind_resource.wind_pipeline")
    fake_mod.WindPipeline = _FakePipeline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wind_resource.wind_pipeline", fake_mod)

    steps: List[Tuple[int, str]] = []
    export = runner_mod.default_assessment(
        _request(), lambda step, msg: steps.append((step, msg))
    )

    assert export["annual_generation_mwh"] == 1.0
    assert seen["cache_dir"].name == "cache" and seen["output_dir"].name == "output"
    # same ephemeral workspace, both cleaned up after the assessment returns
    assert seen["cache_dir"].parent == seen["output_dir"].parent
    assert not seen["cache_dir"].exists() and not seen["output_dir"].exists()
    assert [s for s, _ in steps] == [1, 2, 3]
