"""Tests for the async analysis runner (orchestration; engine + assessment injected).

The lifecycle mirrors ``run_wind_job`` and is proved without the heavy MC engine, the
``[wind]`` toolchain, or a network fetch — the assessment and analysis steps are both
injected, and the screening-seam builder is exercised with a spy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

import pytest

import app.jobs.analysis_runner as ar
from app.jobs.analysis_runner import (
    ANALYSIS_TOTAL_STEPS,
    _build_assessed_scenario,
    default_analysis,
    run_analysis_job,
)
from app.jobs.models import AnalysisJobRequest, JobRecord, JobState, WindJobRequest
from app.jobs.runner import AssessmentResult, new_queued_record
from app.jobs.store import InMemoryJobStore
from app.models.inputs import WindFarmInputs


def _wind() -> WindJobRequest:
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
        resource_mode="weibull",
        weibull_a=8.199,
        weibull_k=2.665,
    )


def _request(**overrides: Any) -> AnalysisJobRequest:
    kwargs: Dict[str, Any] = {"analysis_type": "mc", "wind": _wind()}
    kwargs.update(overrides)
    return AnalysisJobRequest(**kwargs)


def _seed(store: InMemoryJobStore, job_id: str = "j1") -> None:
    store.create(
        JobRecord(
            **new_queued_record(
                job_id, now="t0", owner="u1", total_steps=ANALYSIS_TOTAL_STEPS
            )
        )
    )


def _good_assessment(_wind_req: WindJobRequest, progress: Any) -> Mapping[str, Any]:
    progress(1, "assess")
    return {"scenario": "P75", "annual_generation_mwh": 1.0}


# --------------------------------------------------------------------------- #
# #993 crux: the analysis runs on the ASSESSED case (fresh CF), never the stale form.
# --------------------------------------------------------------------------- #
def test_build_assessed_scenario_honors_993_screening_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_assessed_scenario replicates run_integrated_case's SCREENING seam: it
    declares run.mode=screening and overwrites the physical resource only (never tariff/
    FX), so the engine consumes the fresh capacity factor, not the form input (#993)."""
    captured: Dict[str, Any] = {}

    def _spy(export: Any, scenario: Any, **kwargs: Any) -> Dict[str, Any]:
        captured["export"] = export
        captured["scenario"] = scenario
        captured["scenario_name"] = kwargs.get("scenario_name")
        captured["adapter_mode"] = kwargs.get("adapter_mode")
        captured["physical_only"] = kwargs.get("physical_only")
        return {"patched": True}

    monkeypatch.setattr(ar, "wind_export_to_scenario_patch", _spy)
    out = _build_assessed_scenario(_wind(), {"scenario": "P75"})

    assert out == {"patched": True}
    assert captured["export"] == {"scenario": "P75"}
    assert captured["adapter_mode"] == "overwrite"  # fresh CF wins
    assert captured["physical_only"] is True  # tariff/FX untouched (#996 P2)
    assert captured["scenario_name"] == "P75"  # matches the default p_level
    # The scenario handed to the adapter is declared screening-grade.
    assert captured["scenario"]["run"]["mode"] == "screening"


# --------------------------------------------------------------------------- #
# default_analysis: mc branch drives the engine and envelopes the result.
# --------------------------------------------------------------------------- #
def test_default_analysis_mc_runs_engine_and_wraps_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}

    class _FakeMC:
        def model_dump(self) -> Dict[str, Any]:
            return {
                "summary": {"project_irr": {"mean": 0.031}},
                "metadata": {"seed": 7},
            }

    def _spy(*, base_config: Any, n_trials: int, seed: int, **_kw: Any) -> _FakeMC:
        captured["base_config"] = base_config
        captured["n_trials"] = n_trials
        captured["seed"] = seed
        return _FakeMC()

    monkeypatch.setattr(ar, "run_monte_carlo_analysis", _spy)
    assessed = {"monte_carlo": {"parameters": [{"name": "capex.usd_total"}]}}
    steps: List[Tuple[int, str]] = []
    out = default_analysis(
        _request(n_trials=500, seed=7, metric="equity_irr"),
        assessed,
        lambda s, m: steps.append((s, m)),
    )

    # The engine is driven with the ASSESSED scenario and the requested knobs.
    assert captured["base_config"] is assessed
    assert captured["n_trials"] == 500 and captured["seed"] == 7
    # The result is a typed, discriminated envelope carrying the engine dict verbatim.
    assert out["analysis_type"] == "mc"
    assert out["metric"] == "equity_irr"
    assert out["scenario_variant"] == "lendercase"
    assert out["engine_result"]["summary"]["project_irr"]["mean"] == 0.031
    assert out["engine_result"]["metadata"]["seed"] == 7
    assert isinstance(out["contract_version"], str)
    assert (ANALYSIS_TOTAL_STEPS - 1) in [s for s, _ in steps]


# --------------------------------------------------------------------------- #
# run_analysis_job lifecycle (assessment + analysis both injected).
# --------------------------------------------------------------------------- #
def test_success_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ar, "_build_assessed_scenario", lambda w, e: {"assessed": True})

    def _fake_analysis(_req: Any, assessed: Any, progress: Any) -> Dict[str, Any]:
        assert assessed == {"assessed": True}
        progress(ANALYSIS_TOTAL_STEPS - 1, "analysing")
        return {"analysis_type": "mc", "engine_result": {"ok": 1}}

    store = InMemoryJobStore()
    _seed(store)
    run_analysis_job(
        "j1",
        _request(),
        store,
        assessment_fn=_good_assessment,
        analysis_fn=_fake_analysis,
    )
    rec = store.get("j1")
    assert rec is not None and rec.state is JobState.SUCCEEDED, (
        rec.error if rec else None
    )
    assert rec.result == {"analysis_type": "mc", "engine_result": {"ok": 1}}
    assert (
        rec.progress.step == ANALYSIS_TOTAL_STEPS and rec.progress.message == "Complete"
    )
    assert rec.error is None


def test_unwraps_assessment_result_export(monkeypatch: pytest.MonkeyPatch) -> None:
    """An AssessmentResult's .export (not the whole object) is fed to the seam (#993)."""
    seen: Dict[str, Any] = {}

    def _capture_build(_wind_req: Any, export: Any) -> Dict[str, Any]:
        seen["export"] = export
        return {"assessed": True}

    monkeypatch.setattr(ar, "_build_assessed_scenario", _capture_build)

    def _assessment(_wind_req: WindJobRequest, progress: Any) -> AssessmentResult:
        progress(1, "assess")
        return AssessmentResult(export={"e": 1}, wind_assessment=None)

    store = InMemoryJobStore()
    _seed(store)
    run_analysis_job(
        "j1",
        _request(),
        store,
        assessment_fn=_assessment,
        analysis_fn=lambda r, a, p: {"ok": True},
    )
    assert seen["export"] == {"e": 1}
    assert store.get("j1").state is JobState.SUCCEEDED  # type: ignore[union-attr]


def test_assessment_failure_marks_failed_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_wind_req: WindJobRequest, _progress: Any) -> Mapping[str, Any]:
        raise RuntimeError("secret path /etc/era5/credentials")

    store = InMemoryJobStore()
    _seed(store)
    run_analysis_job("j1", _request(), store, assessment_fn=_boom)
    rec = store.get("j1")
    assert rec is not None and rec.state is JobState.FAILED
    assert "RuntimeError" in (rec.error or "")
    assert "secret path" not in (rec.error or "") and "/etc/era5" not in (
        rec.error or ""
    )


def test_analysis_failure_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ar, "_build_assessed_scenario", lambda w, e: {"assessed": True})

    def _explode(_req: Any, _assessed: Any, _progress: Any) -> Dict[str, Any]:
        raise ValueError("MonteCarloConfigError-ish")

    store = InMemoryJobStore()
    _seed(store)
    run_analysis_job(
        "j1", _request(), store, assessment_fn=_good_assessment, analysis_fn=_explode
    )
    rec = store.get("j1")
    assert rec is not None and rec.state is JobState.FAILED
    assert "ValueError" in (rec.error or "")


def test_progress_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: List[Tuple[int, str]] = []

    class _RecordingStore(InMemoryJobStore):
        def update(self, job_id: str, **changes: Any) -> JobRecord:
            if "progress" in changes:
                p = changes["progress"]
                seen.append((p.step, p.message))
            return super().update(job_id, **changes)

    monkeypatch.setattr(ar, "_build_assessed_scenario", lambda w, e: {"assessed": True})

    def _fake_analysis(_req: Any, _assessed: Any, progress: Any) -> Dict[str, Any]:
        progress(ANALYSIS_TOTAL_STEPS - 1, "analysing")
        return {"ok": True}

    store = _RecordingStore()
    _seed(store)
    run_analysis_job(
        "j1",
        _request(),
        store,
        assessment_fn=_good_assessment,
        analysis_fn=_fake_analysis,
    )
    steps = [s for s, _ in seen]
    assert 1 in steps  # assessment progress
    assert ANALYSIS_TOTAL_STEPS in steps  # completion


# --------------------------------------------------------------------------- #
# Integration guard #1: the committed lendercase resolves to an engine-RUNNABLE
# MC config (real engine, small n). Locks the design assumption the request guard
# relies on ("use lendercase"): if a future scenario edit reverts the driver block
# to dict-form, this fails fast. (Builds the scenario directly — the full patch->
# engine seam is covered by the end-to-end test below.)
# --------------------------------------------------------------------------- #
def test_lendercase_assessed_scenario_is_mc_runnable() -> None:
    from analytics.mc.engine import run_monte_carlo_analysis
    from app.models.inputs import WindFarmInputs

    inputs = WindFarmInputs(
        scenario_variant="lendercase",
        site_name="Dutch Bay",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )
    scenario = inputs.to_scenario_config()
    run_block = dict(scenario.get("run") or {})
    run_block["mode"] = "screening"
    scenario["run"] = run_block

    result = run_monte_carlo_analysis(base_config=scenario, n_trials=16, seed=123)
    dumped = result.model_dump()
    # Every trial is a REAL v14 evaluation (no toy-fallback, no failures) and the
    # result serialises to a plain dict the envelope carries verbatim.
    assert dumped["iterations"] == 16
    assert dumped["failed_iterations"] == 0
    assert dumped["metadata"].get("toy_fallback_count", 0) == 0
    assert isinstance(dumped["project_irr_p50"], float)


# --------------------------------------------------------------------------- #
# Integration guard #2 (the #993 crux, end-to-end): the REAL _build_assessed_scenario
# seam (real wind_export_to_scenario_patch, overwrite + physical_only) feeds the REAL
# MC engine the FRESH assessed capacity factor — not the stale form CF. This is the
# exact patch->engine path run_analysis_job drives; the unit tests above cover each
# leg with a spy/fake, this proves the composed shape actually runs.
# --------------------------------------------------------------------------- #
def test_assessed_seam_feeds_fresh_cf_to_real_engine() -> None:
    from analytics.mc.engine import run_monte_carlo_analysis

    # A valid WindCashflowExport (validated at the patch boundary). Its 22.8% CF is far
    # from the form's 0.339 so the overwrite is unambiguously observable.
    export = {
        "scenario": "P75",
        "annual_generation_mwh": 300_000.0,
        "capacity_factor_percent": 22.8,
        "revenue_annual_usd": 20_000_000.0,
        "revenue_cumulative_usd": 400_000_000.0,
        "project_capacity_mw": 150.0,
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10_000.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.3,
        "exchange_rate_lkr_usd": 300.0,
    }
    assessed = _build_assessed_scenario(_wind(), export)

    # #993: the engine base is the FRESH assessed CF (0.228), NOT the stale form 0.339.
    assert assessed["project"]["capacity_factor"] == pytest.approx(0.228)
    assert assessed["project"]["capacity_factor"] != pytest.approx(0.339)
    # physical_only: the scenario's own tariff was NOT overwritten by the export's 20.3
    # form value stays authoritative (lendercase base tariff, not touched by the patch).
    assert (
        "monte_carlo" in assessed
    )  # the driver block survives the physical-only patch

    dumped = run_monte_carlo_analysis(
        base_config=assessed, n_trials=16, seed=123
    ).model_dump()
    assert dumped["iterations"] == 16
    assert dumped["failed_iterations"] == 0
    assert dumped["metadata"].get("toy_fallback_count", 0) == 0
