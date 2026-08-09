"""Tests for the async job runner (orchestration; ERA5 step injected)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import pandas as pd
import pytest

import app.jobs.runner as runner_mod
from app.api.responses import WindAssessment
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
        turbine_model="iea_reference_10mw",
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


def test_marks_scenario_screening(monkeypatch: pytest.MonkeyPatch) -> None:
    """#996: the async location assessment is declared SCREENING-grade, which drives
    the service seam to adopt the fresh CF (physical-only) and skip the frozen-bankable
    reconciliation, so a fresh P-level never collides with the committed lender P50."""
    captured: Dict[str, Any] = {}

    def _spy(scenario: Any, _wind_export: Any, **_kwargs: Any) -> Dict[str, Any]:
        captured["scenario"] = scenario
        return _CANNED_RESULT

    monkeypatch.setattr(runner_mod, "run_integrated_case", _spy)
    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)
    assert captured["scenario"]["run"]["mode"] == "screening"


def test_p75_assessment_does_not_collide_with_frozen_p50() -> None:
    """#996 (the reported failure): a fresh P75 whose capacity factor differs from the
    lender-case base's frozen 0.332 runs clean end-to-end through the REAL service seam
    — no WindAdapterDriftError, no AepReconciliationError — because the assessment is
    screening-grade (overwrite the fresh CF, physical-only, skip the frozen-bankable
    reconciliation). Before #996 this job failed at one of those two guards."""
    fresh_p75_export = {
        "scenario": "P75",
        "annual_generation_mwh": 300_000.0,
        "capacity_factor_percent": 22.8,  # far from the frozen 33.2% -> old code raised
        "revenue_annual_usd": 20_000_000.0,
        "revenue_cumulative_usd": 400_000_000.0,
        "project_capacity_mw": 150.0,
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10_000.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.3,
        "exchange_rate_lkr_usd": 300.0,
    }

    def _assessment(_req: WindJobRequest, progress: Any) -> Mapping[str, Any]:
        progress(1, "assess")
        return fresh_p75_export

    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_assessment)
    rec = store.get("j1")
    assert rec is not None
    # No frozen-P50 collision: the job SUCCEEDS (it used to fail at the guard).
    assert rec.state is JobState.SUCCEEDED, rec.error
    assert rec.result is not None and "kpis" in rec.result


# --------------------------------------------------------------------------- #
# #974: the async wind path DERIVES capacity / CF from the turbine layout + p_level
# and the screening seam OVERWRITES the client's submitted values. Two guarantees:
# (1) the exact #974 case (a capacity AND a CF mismatch) runs clean through the REAL
# seam; (2) the supersession is SURFACED in the assessment provenance, not silent.
# --------------------------------------------------------------------------- #
def test_capacity_and_cf_mismatch_runs_clean_and_surfaces_supersession() -> None:
    """#974 exact case, end-to-end through the REAL service seam.

    The client submits 150 MW / CF 0.339 (``_request``), but the screening assessment
    derives a different physical basis — 159.57 MW nameplate (15 × the iea_reference_10mw
    rated power) and a P75 CF of 0.228. Pre-#997 this tripped the CESSPIT-strict adapter
    drift guard (0.5%); now the derived values overwrite the submission and the job runs
    clean. The reconciliation note records the supersession so the overwrite is explicit,
    not silent (#974).
    """
    export = {
        "scenario": "P75",
        "annual_generation_mwh": 300_000.0,
        "capacity_factor_percent": 22.8,  # != client 33.9% (P50-ish) -> superseded
        "revenue_annual_usd": 20_000_000.0,
        "revenue_cumulative_usd": 400_000_000.0,
        "project_capacity_mw": 159.57,  # 15 × iea_reference_10mw nameplate != client 150
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10_638.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.3,
        "exchange_rate_lkr_usd": 300.0,
    }
    wa = WindAssessment(
        p_levels_gwh={"P75": 300.0},
        net_capacity_factor={"P75": 0.228},
        provenance={"grade": "screening", "selected_p_level": "P75"},
        site={"name": "Dutch Bay"},
    )

    def _assessment(_req: WindJobRequest, progress: Any) -> runner_mod.AssessmentResult:
        progress(1, "assess")
        return runner_mod.AssessmentResult(export=export, wind_assessment=wa)

    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_assessment)
    rec = store.get("j1")
    assert rec is not None
    # (1) The capacity + CF mismatch runs clean through the real seam (it used to fail).
    assert rec.state is JobState.SUCCEEDED, rec.error
    assert rec.result is not None and "kpis" in rec.result
    # (2) The supersession is surfaced in the assessment provenance.
    recon = rec.result["wind_assessment"]["provenance"]["input_reconciliation"]
    assert recon["capacity_mw"]["submitted"] == pytest.approx(150.0)
    assert recon["capacity_mw"]["used"] == pytest.approx(159.57)
    assert recon["capacity_mw"]["superseded"] is True
    assert recon["capacity_factor"]["submitted"] == pytest.approx(0.339)
    assert recon["capacity_factor"]["used"] == pytest.approx(0.228)
    assert recon["capacity_factor"]["superseded"] is True


def _request_no_capacity() -> WindJobRequest:
    """A #1023 async request whose embedded inputs OMIT capacity_mw / capacity_factor."""
    return WindJobRequest(
        inputs=WindFarmInputs(
            site_name="Dutch Bay",
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
    )


def test_omitted_capacity_derives_and_succeeds_through_real_seam() -> None:
    """#1023 end-to-end: a client that OMITS capacity_mw / capacity_factor runs clean through
    the REAL service seam — the screening export fills the physical basis — and the
    reconciliation note surfaces both fields as derived_only (never a supersession)."""
    req = _request_no_capacity()
    assert req.inputs.capacity_mw is None and req.inputs.capacity_factor is None
    export = {
        "scenario": "P75",
        "annual_generation_mwh": 300_000.0,
        "capacity_factor_percent": 22.8,
        "revenue_annual_usd": 20_000_000.0,
        "revenue_cumulative_usd": 400_000_000.0,
        "project_capacity_mw": 159.57,  # 15 × iea_reference_10mw nameplate
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10_638.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.3,
        "exchange_rate_lkr_usd": 300.0,
    }
    wa = WindAssessment(
        p_levels_gwh={"P75": 300.0},
        net_capacity_factor={"P75": 0.228},
        provenance={"grade": "screening", "selected_p_level": "P75"},
        site={"name": "Dutch Bay"},
    )

    def _assessment(_req: WindJobRequest, progress: Any) -> runner_mod.AssessmentResult:
        progress(1, "assess")
        return runner_mod.AssessmentResult(export=export, wind_assessment=wa)

    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", req, store, assessment_fn=_assessment)
    rec = store.get("j1")
    assert rec is not None
    # The omitted capacity / CF do not block the job: derived + succeeds through the real seam.
    assert rec.state is JobState.SUCCEEDED, rec.error
    assert rec.result is not None and "kpis" in rec.result
    # The supersession note records the derived-only basis for both omitted fields.
    recon = rec.result["wind_assessment"]["provenance"]["input_reconciliation"]
    assert recon["capacity_mw"]["submitted"] is None
    assert recon["capacity_mw"]["used"] == pytest.approx(159.57)
    assert recon["capacity_mw"]["derived_only"] is True
    assert recon["capacity_mw"]["superseded"] is False
    assert recon["capacity_factor"]["submitted"] is None
    assert recon["capacity_factor"]["used"] == pytest.approx(0.228)
    assert recon["capacity_factor"]["derived_only"] is True


def test_input_reconciliation_flags_material_supersession() -> None:
    """The note carries submitted, used, drift, and the superseded flag per field."""
    export = {"project_capacity_mw": 159.57, "capacity_factor_percent": 22.8}
    recon = runner_mod._input_reconciliation(150.0, 0.339, export)
    assert recon is not None
    assert recon["capacity_mw"]["drift_pct"] == pytest.approx(6.38, abs=0.01)
    assert recon["capacity_mw"]["superseded"] is True
    assert recon["capacity_factor"]["used"] == pytest.approx(0.228)
    assert recon["capacity_factor"]["superseded"] is True
    assert "num_turbines" in recon["basis"]


def test_input_reconciliation_not_superseded_within_tolerance() -> None:
    """A submission that agrees with the derived basis (< 0.5% drift) is not superseded."""
    export = {"project_capacity_mw": 150.3, "capacity_factor_percent": 33.9}
    recon = runner_mod._input_reconciliation(150.0, 0.339, export)
    assert recon is not None
    assert recon["capacity_mw"]["drift_pct"] == pytest.approx(0.2, abs=0.01)
    assert recon["capacity_mw"]["superseded"] is False
    assert recon["capacity_factor"]["superseded"] is False


def test_input_reconciliation_none_for_bare_export() -> None:
    """A bare / legacy export with no derived physical keys yields no note (no crash)."""
    assert runner_mod._input_reconciliation(150.0, 0.339, {"scenario": "P75"}) is None


def test_input_reconciliation_derived_only_when_submission_omitted() -> None:
    """#1023: when the client OMITS a field it was derived, not superseded — the note records
    it as derived_only with the used value surfaced and no drift/supersession."""
    export = {"project_capacity_mw": 159.57, "capacity_factor_percent": 22.8}
    recon = runner_mod._input_reconciliation(None, None, export)
    assert recon is not None
    for field in ("capacity_mw", "capacity_factor"):
        assert recon[field]["submitted"] is None
        assert recon[field]["drift_pct"] is None
        assert recon[field]["superseded"] is False
        assert recon[field]["derived_only"] is True
    assert recon["capacity_mw"]["used"] == pytest.approx(159.57)
    assert recon["capacity_factor"]["used"] == pytest.approx(0.228)


def test_input_reconciliation_mixed_omitted_and_submitted() -> None:
    """A submission may omit ONE field: capacity omitted (derived_only) while a submitted CF
    is still reconciled against the derived value."""
    export = {"project_capacity_mw": 159.57, "capacity_factor_percent": 22.8}
    recon = runner_mod._input_reconciliation(None, 0.339, export)
    assert recon is not None
    assert recon["capacity_mw"]["submitted"] is None
    assert recon["capacity_mw"]["derived_only"] is True
    # The submitted CF is reconciled as before (drift + supersession), no derived_only flag.
    assert recon["capacity_factor"]["submitted"] == pytest.approx(0.339)
    assert recon["capacity_factor"]["superseded"] is True
    assert "derived_only" not in recon["capacity_factor"]


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
    _stub_era5_retrieval(monkeypatch)

    steps: List[Tuple[int, str]] = []
    export = runner_mod.default_assessment(
        _request(), lambda step, msg: steps.append((step, msg))
    )

    assert (
        export.export["annual_generation_mwh"] == 1.0
    )  # AssessmentResult.export (#993)
    assert seen["cache_dir"].name == "cache" and seen["output_dir"].name == "output"
    # same ephemeral workspace, both cleaned up after the assessment returns
    assert seen["cache_dir"].parent == seen["output_dir"].parent
    assert not seen["cache_dir"].exists() and not seen["output_dir"].exists()
    assert [s for s, _ in steps] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# #965: default_assessment fetches the CDS ARCO single-point TIMESERIES product
# (era5_retrieval), not the legacy gridded fetcher whose full-year AREA request
# CDS rejects as "too large", and injects the finished hub-height series into
# WindPipeline. Proved with fakes — no [wind] toolchain, no network.
# --------------------------------------------------------------------------- #
def _stub_era5_retrieval(monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    """Replace the three CDS-bound era5_retrieval functions with fakes; return the
    synthetic hub-height series the fake ``build_hub_height_series`` yields."""
    import wind_resource.era5_retrieval as era5

    idx = pd.date_range("2023-01-01", periods=24, freq="h", name="timestamp")
    series = pd.DataFrame({"ws_119m": [8.0 + (i % 3) for i in range(24)]}, index=idx)

    def _fake_retrieve(cfg: Any) -> Path:
        # Must NOT touch cdsapi/network; assert the config carries the site identity.
        assert cfg.turbine_model == "iea_reference_10mw"
        assert cfg.latitude == pytest.approx(8.33)
        return Path("/tmp/does-not-exist.nc")

    def _fake_build(nc_path: Path, cfg: Any) -> pd.DataFrame:
        return series

    def _fake_coverage(s: pd.DataFrame, cfg: Any) -> Dict[str, Any]:
        return {"actual_hours": len(s), "coverage_complete": False}

    monkeypatch.setattr(era5, "retrieve_era5_timeseries", _fake_retrieve)
    monkeypatch.setattr(era5, "build_hub_height_series", _fake_build)
    monkeypatch.setattr(era5, "validate_coverage", _fake_coverage)
    return series


def test_default_assessment_injects_timeseries_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ERA5 timeseries series is forwarded to WindPipeline as ``hub_height_series``
    (Steps 1-2 skipped) and the cashflow export is returned (#965)."""
    import sys
    import types

    forwarded: Dict[str, Any] = {}

    class _FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            Path(kwargs["cache_dir"]).mkdir(parents=True, exist_ok=True)
            Path(kwargs["output_dir"]).mkdir(parents=True, exist_ok=True)

        def run_complete_assessment(self, **kwargs: Any) -> None:
            forwarded["hub_height_series"] = kwargs.get("hub_height_series")
            forwarded["start_date"] = kwargs.get("start_date")

        def export_for_cashflow_model(self, *, scenario: str) -> Mapping[str, Any]:
            return {"scenario": scenario, "annual_generation_mwh": 42.0}

    fake_mod = types.ModuleType("wind_resource.wind_pipeline")
    fake_mod.WindPipeline = _FakePipeline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wind_resource.wind_pipeline", fake_mod)
    series = _stub_era5_retrieval(monkeypatch)

    export = runner_mod.default_assessment(_request(), lambda step, msg: None)

    assert (
        export.export["annual_generation_mwh"] == 42.0
    )  # AssessmentResult.export (#993)
    # The exact series built from the ERA5 TIMESERIES product was injected.
    assert forwarded["hub_height_series"] is series
    assert forwarded["start_date"] == "2014-12-01"


# --------------------------------------------------------------------------- #
# #993: deterministic Weibull screening path (no ERA5) + #994 shear override.
# --------------------------------------------------------------------------- #
def _weibull_request() -> WindJobRequest:
    """A resource_mode='weibull' request (DutchBay ERA5-fitted A/k, at hub height)."""
    return _request().model_copy(
        update={"resource_mode": "weibull", "weibull_a": 8.199, "weibull_k": 2.665}
    )


def test_weibull_screening_series_recovers_ak() -> None:
    """The inverse-CDF quantile lattice is a faithful, RNG-free Weibull(A,k): the SAME
    scipy MLE the assessment path uses recovers (A, k) to well under 0.5%."""
    from scipy.stats import weibull_min

    df = runner_mod._weibull_screening_series(8.199, 2.665, 119.0)
    assert list(df.columns) == ["ws_119m"] and df.index.name == "timestamp"
    assert len(df) == 8760 and bool((df["ws_119m"] > 0).all())
    k, _loc, a = weibull_min.fit(df["ws_119m"].to_numpy(), floc=0)
    assert abs(a - 8.199) / 8.199 < 0.005
    assert abs(k - 2.665) / 2.665 < 0.005


def test_weibull_job_uses_synthetic_series_no_era5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resource_mode='weibull' builds a synthetic hub-height Weibull series and feeds the
    SAME pipeline — with NO ERA5 fetch (#993)."""
    import sys
    import types

    forwarded: Dict[str, Any] = {}

    class _FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            Path(kwargs["cache_dir"]).mkdir(parents=True, exist_ok=True)
            Path(kwargs["output_dir"]).mkdir(parents=True, exist_ok=True)

        def run_complete_assessment(self, **kwargs: Any) -> None:
            forwarded["hub_height_series"] = kwargs.get("hub_height_series")

        def export_for_cashflow_model(self, *, scenario: str) -> Mapping[str, Any]:
            return {"scenario": scenario, "annual_generation_mwh": 5.0}

    fake_mod = types.ModuleType("wind_resource.wind_pipeline")
    fake_mod.WindPipeline = _FakePipeline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wind_resource.wind_pipeline", fake_mod)

    # Any ERA5 fetch on this path is a bug — make it explode if reached.
    import wind_resource.era5_retrieval as era5

    def _boom(*_a: Any, **_k: Any) -> Path:
        raise AssertionError("ERA5 fetch must not run on the weibull screening path")

    monkeypatch.setattr(era5, "retrieve_era5_timeseries", _boom)

    export = runner_mod.default_assessment(_weibull_request(), lambda step, msg: None)

    assert (
        export.export["annual_generation_mwh"] == 5.0
    )  # AssessmentResult.export (#993)
    series = forwarded["hub_height_series"]
    assert list(series.columns) == ["ws_119m"]  # matches hub_height_m=119
    assert series.index.name == "timestamp"
    assert len(series) == 8760 and bool((series["ws_119m"] > 0).all())


def test_era5_job_wires_shear_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """#994: a request shear_exponent reaches ERA5RequestConfig.shear_exponent_override
    (which genuinely replaces the per-hour alpha), rather than being silently dropped.
    """
    import sys
    import types

    captured: Dict[str, Any] = {}

    class _FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            Path(kwargs["cache_dir"]).mkdir(parents=True, exist_ok=True)
            Path(kwargs["output_dir"]).mkdir(parents=True, exist_ok=True)

        def run_complete_assessment(self, **kwargs: Any) -> None:
            return None

        def export_for_cashflow_model(self, *, scenario: str) -> Mapping[str, Any]:
            return {"scenario": scenario, "annual_generation_mwh": 1.0}

    fake_mod = types.ModuleType("wind_resource.wind_pipeline")
    fake_mod.WindPipeline = _FakePipeline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wind_resource.wind_pipeline", fake_mod)

    _stub_era5_retrieval(monkeypatch)  # fakes build/validate/retrieve (no network)

    import wind_resource.era5_retrieval as era5

    def _cap_retrieve(cfg: Any) -> Path:
        captured["shear_override"] = cfg.shear_exponent_override
        return Path("/tmp/does-not-exist.nc")

    monkeypatch.setattr(era5, "retrieve_era5_timeseries", _cap_retrieve)

    req = _request().model_copy(update={"shear_exponent": 0.25})
    runner_mod.default_assessment(req, lambda step, msg: None)
    assert captured["shear_override"] == 0.25


# --------------------------------------------------------------------------- #
# #993: the full wind assessment (all P50/P75/P90 + provenance) on CaseResult.
# --------------------------------------------------------------------------- #
def test_build_wind_assessment_projects_full_results() -> None:
    """_build_wind_assessment reads the documented result paths and marks screening-grade,
    degrading missing keys to empty rather than raising."""
    fr = {
        "metadata": {
            "version": "v15.3.0",
            "location": {"name": "DB", "lat": 8.3, "lon": 79.7},
            "data_period": {
                "start_date": "2014",
                "end_date": "2025",
                "data_points": 96000,
            },
        },
        "wind_data": {"mean_ws": 8.1},
        "statistical_analysis": {"weibull": {"scale_c": 8.2, "shape_k": 2.66}},
        "energy_production": {
            "net_aep": {
                "net_aep_p50_mwh": 464300.0,
                "net_aep_p75_mwh": 440000.0,
                "net_aep_p90_mwh": 404400.0,
                "capacity_factor_net_p50": 0.354,
                "capacity_factor_net_p75": 0.336,
                "capacity_factor_net_p90": 0.309,
                "pvalue_method": "iec_61400_15_2",
                "uncertainty_sigma_1yr_pct": 6.0,
            }
        },
    }
    wa = runner_mod._build_wind_assessment(fr, "P75")
    assert wa.p_levels_gwh == {"P50": 464.3, "P75": 440.0, "P90": 404.4}
    assert wa.net_capacity_factor == {"P50": 0.354, "P75": 0.336, "P90": 0.309}
    assert wa.provenance["grade"] == "screening"  # #961: never bankable
    assert wa.provenance["engine_version"] == "v15.3.0"
    assert wa.provenance["selected_p_level"] == "P75"
    assert wa.site == {"name": "DB", "lat": 8.3, "lon": 79.7}
    assert wa.wind_stats["weibull_a"] == 8.2 and wa.wind_stats["weibull_k"] == 2.66
    assert runner_mod._build_wind_assessment({}, "P50").p_levels_gwh == {}  # degrades


# --------------------------------------------------------------------------- #
# #996 D4-wire: the STRICT, VALIDATED ResourceAssessment on the assessment path.
# --------------------------------------------------------------------------- #
# capacity_factor_net_pXX is a PERCENT in the pipeline result (energy_calculator);
# each net AEP (MWh) is consistent with capacity_mw * 8760 * CF/100.
_RA_FULL_RESULTS: Dict[str, Any] = {
    "metadata": {
        "version": "v15.3.0",
        "configuration": {
            "num_turbines": 15,
            "total_capacity_mw": 159.6,
            "turbine_model": "iea_reference_10mw",
        },
    },
    "energy_production": {
        "net_aep": {
            "net_aep_p50_mwh": 506110.0,  # 0.362 * 159.6 * 8760
            "net_aep_p75_mwh": 472556.0,  # 0.338 * 159.6 * 8760
            "net_aep_p90_mwh": 441798.0,  # 0.316 * 159.6 * 8760
            "capacity_factor_net_p50": 36.2,  # PERCENT
            "capacity_factor_net_p75": 33.8,
            "capacity_factor_net_p90": 31.6,
        }
    },
}


def test_build_resource_assessment_validates_full_results() -> None:
    """_build_resource_assessment projects the strict contract: MWh->GWh, percent CF
    ->decimal, and passes the AEP-identity + P90<=P75<=P50 checks on construction."""
    ra = runner_mod._build_resource_assessment(_RA_FULL_RESULTS, "P75")
    assert ra is not None  # complete data => a validated assessment, never None
    assert ra.capacity_mw == 159.6 and ra.n_turbines == 15
    assert ra.net_aep_p50_gwh == pytest.approx(506.110)  # MWh -> GWh
    assert ra.net_aep_p90_gwh == pytest.approx(441.798)
    assert ra.capacity_factor_p50 == pytest.approx(0.362)  # percent -> decimal
    assert ra.selected_p_level == "P75"
    assert ra.report_grade == "screening"  # #961: never bankable
    assert ra.p90_p50_ratio == pytest.approx(441798.0 / 506110.0)


@pytest.mark.parametrize("p_level", ["P50", "P75", "P90"])
def test_build_resource_assessment_selects_p_level(p_level: str) -> None:
    ra = runner_mod._build_resource_assessment(_RA_FULL_RESULTS, p_level)
    assert ra is not None
    assert ra.selected_p_level == p_level


def test_build_resource_assessment_fails_loud_on_inconsistent() -> None:
    """A capacity factor that contradicts the net AEP fails the identity guard."""
    from analytics.resource_contracts import ResourceAssessmentError

    bad = {
        "metadata": _RA_FULL_RESULTS["metadata"],
        "energy_production": {
            "net_aep": {
                **_RA_FULL_RESULTS["energy_production"]["net_aep"],
                "capacity_factor_net_p50": 60.0,  # implies ~838 GWh, not 506
            }
        },
    }
    with pytest.raises(ResourceAssessmentError, match="AEP identity"):
        runner_mod._build_resource_assessment(bad, "P50")


def test_default_assessment_weibull_produces_valid_resource_assessment() -> None:
    """End-to-end (no network): the deterministic Weibull assessment yields a VALID
    ResourceAssessment on real pipeline output. Because the pipeline derives CF from AEP,
    the AEP-identity here is definitional — this test proves the PROJECTION (MWh->GWh and
    percent->decimal units) round-trips and the P90<=P75<=P50 monotonicity holds live.
    (test_build_resource_assessment_fails_loud_on_inconsistent exercises the identity
    raise itself on an independently-inconsistent triple.)"""
    req = _request().model_copy(
        update={
            "resource_mode": "weibull",
            "weibull_a": 8.199,
            "weibull_k": 2.665,
            "p_level": "P90",
        }
    )
    result = runner_mod.default_assessment(req, lambda step, msg: None)
    ra = result.resource_assessment
    assert ra is not None
    assert ra.selected_p_level == "P90"
    assert ra.report_grade == "screening"
    # Monotone and physically sensible for a ~160 MW farm.
    assert ra.net_aep_p50_gwh > ra.net_aep_p75_gwh > ra.net_aep_p90_gwh > 0.0
    assert 0.0 < ra.capacity_factor_p90 < ra.capacity_factor_p50 < 1.0
    assert 0.5 < ra.p90_p50_ratio < 1.0  # downside ratio the debt slice will consume


# --------------------------------------------------------------------------- #
# #996 D5: inject the active P90/P50 so downside-debt sizing uses the assessment.
# --------------------------------------------------------------------------- #
def _active_ra() -> Any:
    """A screening assessment with net AEP P50=500 / P90=400 GWh -> a downside ratio
    (0.80) distinct from the frozen lender base (404.4/464.3 = 0.871). CFs are kept
    identity-consistent for a 150 MW farm so the contract validates."""
    from analytics.resource_contracts import ResourceAssessment

    return ResourceAssessment(
        capacity_mw=150.0,
        n_turbines=15,
        net_aep_p50_gwh=500.0,
        net_aep_p75_gwh=450.0,
        net_aep_p90_gwh=400.0,
        capacity_factor_p50=0.3805,
        capacity_factor_p75=0.3425,
        capacity_factor_p90=0.3044,
        selected_p_level="P75",
        report_grade="screening",
    )


def test_apply_active_resource_basis_injects_and_preserves() -> None:
    scenario = {
        "expected_results": {
            "net_aep_p50_gwh": 464.3,
            "net_aep_p90_gwh": 404.4,
            "capacity_factor": 0.332,
        }
    }
    out = runner_mod.apply_active_resource_basis(scenario, _active_ra())
    assert out["expected_results"]["net_aep_p50_gwh"] == 500.0  # injected
    assert out["expected_results"]["net_aep_p90_gwh"] == 400.0
    assert out["expected_results"]["capacity_factor"] == 0.332  # other keys preserved
    # The original scenario is not mutated (injection returns a copy).
    assert scenario["expected_results"]["net_aep_p50_gwh"] == 464.3


def test_apply_active_resource_basis_none_is_noop() -> None:
    scenario = {"expected_results": {"net_aep_p50_gwh": 464.3}}
    assert runner_mod.apply_active_resource_basis(scenario, None) is scenario


def test_injected_active_basis_drives_downside_debt_ratio() -> None:
    """The core D5 wiring: after injection, finance's _resolve_downside_ratio reads the
    ACTIVE P90/P50 (0.80), not the frozen lender base (0.871)."""
    from finance.debt_v14 import _resolve_downside_ratio

    config = {"expected_results": {"net_aep_p50_gwh": 464.3, "net_aep_p90_gwh": 404.4}}
    fin = {"downside_aep_source": "p90"}  # the default
    frozen_ratio, frozen_src = _resolve_downside_ratio(config, fin)
    assert frozen_src == "p90_aep"
    assert frozen_ratio == pytest.approx(404.4 / 464.3)

    active_cfg = runner_mod.apply_active_resource_basis(config, _active_ra())
    active_ratio, active_src = _resolve_downside_ratio(active_cfg, fin)
    assert active_src == "p90_aep"
    assert active_ratio == pytest.approx(400.0 / 500.0)  # 0.80 — the ACTIVE ratio
    assert active_ratio != pytest.approx(frozen_ratio)  # differs from the frozen base


def test_injected_active_basis_changes_solved_downside_gearing() -> None:
    """End-to-end: injecting the active net AEP changes the P90-BOUND gearing SOLVE, not
    just the ratio helper. bind_downside is forced on (no committed async variant binds
    downside — this demonstrates the mechanism the screening path wires): a harsher active
    P90/P50 (0.80) deleverages more than the frozen lender base (404.4/464.3 = 0.871).
    """
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.resource_contracts import ResourceAssessment
    from analytics.scenario_loader import load_scenario_config

    lender = str(
        Path(__file__).resolve().parents[2]
        / "scenarios"
        / "dutchbay_lendercase_2025Q4.yaml"
    )
    base = dict(load_scenario_config(lender))
    base["Financing_Terms"] = {
        **base["Financing_Terms"],
        "bind_downside": True,
        "target_dscr_p90": 1.20,
    }

    def _dual(cfg: Dict[str, Any]) -> Dict[str, Any]:
        r = run_v14_pipeline(config=cfg)
        return (r.get("debt_result") or {}).get("dual_dscr") or {}

    frozen = _dual(base)
    assert frozen["downside_source"] == "p90_aep"
    assert frozen["downside_ratio"] == pytest.approx(404.4 / 464.3, abs=0.001)  # 0.871

    # A HARSHER active downside (P90/P50 = 0.80): net AEP P50=464.3 / P90=371.44 GWh,
    # CFs kept identity-consistent for a 150 MW farm so the contract validates.
    active_ra = ResourceAssessment(
        capacity_mw=150.0,
        n_turbines=15,
        net_aep_p50_gwh=464.3,
        net_aep_p75_gwh=417.0,
        net_aep_p90_gwh=371.44,
        capacity_factor_p50=0.3533,
        capacity_factor_p75=0.3174,
        capacity_factor_p90=0.2827,
        selected_p_level="P75",
        report_grade="screening",
    )
    active = _dual(runner_mod.apply_active_resource_basis(base, active_ra))
    assert active["downside_ratio"] == pytest.approx(371.44 / 464.3, abs=0.001)  # 0.80
    # The gearing SOLVE (not just the helper) responds: harsher downside => less debt.
    assert active["solved_gearing_p90"] < frozen["solved_gearing_p90"]


def test_run_wind_job_surfaces_wind_assessment(monkeypatch: pytest.MonkeyPatch) -> None:
    """An AssessmentResult carrying a WindAssessment surfaces the full block on the stored
    CaseResult (#993)."""
    from app.api.responses import WindAssessment
    from app.jobs.runner import AssessmentResult

    monkeypatch.setattr(
        runner_mod, "run_integrated_case", lambda *a, **k: _CANNED_RESULT
    )
    wa = WindAssessment(
        p_levels_gwh={"P50": 464.3, "P75": 440.0, "P90": 404.4},
        provenance={"grade": "screening"},
    )

    def _assessment_with_block(_req: WindJobRequest, progress: Any) -> AssessmentResult:
        progress(1, "assess")
        return AssessmentResult(export=_FAKE_EXPORT, wind_assessment=wa)

    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_assessment_with_block)
    rec = store.get("j1")
    assert rec is not None and rec.state is JobState.SUCCEEDED, (
        rec.error if rec else None
    )
    assert rec.result is not None
    out = rec.result["wind_assessment"]
    assert out is not None
    assert out["p_levels_gwh"] == {"P50": 464.3, "P75": 440.0, "P90": 404.4}
    assert out["provenance"]["grade"] == "screening"


def test_run_wind_job_legacy_mapping_export_has_no_assessment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward-compat: a fake returning a bare export mapping still works, with
    wind_assessment=None on the result (#993)."""
    monkeypatch.setattr(
        runner_mod, "run_integrated_case", lambda *a, **k: _CANNED_RESULT
    )
    store = InMemoryJobStore()
    _seed_queued(store)
    run_wind_job("j1", _request(), store, assessment_fn=_good_assessment)  # -> Mapping
    rec = store.get("j1")
    assert rec is not None and rec.state is JobState.SUCCEEDED
    assert rec.result is not None and rec.result["wind_assessment"] is None
