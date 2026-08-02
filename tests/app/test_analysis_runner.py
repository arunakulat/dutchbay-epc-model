"""Tests for the async analysis runner (orchestration; engine + assessment injected).

The lifecycle mirrors ``run_wind_job`` and is proved without the heavy analysis engines,
the ``[wind]`` toolchain, or a network fetch — the assessment and analysis steps are
both injected, and the screening-seam builder is exercised with a spy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

import pytest

import app.jobs.analysis_runner as ar
from analytics.contracts_v14 import ParameterRangeConfig
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
# default_analysis: tornado branch uses canonical drivers over the assessed case.
# --------------------------------------------------------------------------- #
def test_default_analysis_tornado_runs_engine_and_wraps_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}
    parameter = ParameterRangeConfig(
        variable_name="project.capacity_factor",
        base_value=0.228,
        low_pct=-10.0,
        high_pct=10.0,
        label="Capacity Factor",
    )

    class _FakeSuite:
        def model_dump(self) -> Dict[str, Any]:
            return {
                "metric": "project_npv",
                "tornado_results": [{"metric_name": "Capacity Factor"}],
                "metadata": {"flat_metric": False},
            }

    def _parameters_spy(config: Mapping[str, Any]) -> List[ParameterRangeConfig]:
        captured["parameter_config"] = config
        return [parameter]

    def _engine_spy(
        *,
        base_config: Mapping[str, Any],
        parameters: Any,
        metric_keys: Any,
        **_kwargs: Any,
    ) -> _FakeSuite:
        captured["base_config"] = base_config
        captured["parameters"] = parameters
        captured["metric_keys"] = metric_keys
        return _FakeSuite()

    monkeypatch.setattr(ar, "_default_parameters", _parameters_spy)
    monkeypatch.setattr(ar, "run_sensitivity_analysis", _engine_spy)
    assessed = {"project": {"capacity_factor": 0.228}}
    steps: List[Tuple[int, str]] = []

    out = default_analysis(
        _request(analysis_type="tornado", metric="project_npv"),
        assessed,
        lambda step, message: steps.append((step, message)),
    )

    assert captured["parameter_config"] is assessed
    assert captured["base_config"] is assessed
    assert captured["parameters"] == [parameter]
    assert captured["metric_keys"] == ["project_npv"]
    assert out["analysis_type"] == "tornado"
    assert out["metric"] == "project_npv"
    assert out["scenario_variant"] == "lendercase"
    assert out["engine_result"]["tornado_results"][0]["metric_name"] == (
        "Capacity Factor"
    )
    assert (ANALYSIS_TOTAL_STEPS - 1) in [step for step, _ in steps]


def test_default_analysis_tornado_rejects_empty_driver_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail before engine evaluation rather than returning a successful empty chart."""
    monkeypatch.setattr(ar, "_default_parameters", lambda _config: [])

    def _must_not_run(**_kwargs: Any) -> None:
        raise AssertionError("sensitivity engine must not run without drivers")

    monkeypatch.setattr(ar, "run_sensitivity_analysis", _must_not_run)
    with pytest.raises(ValueError, match="no default sensitivity drivers"):
        default_analysis(
            _request(analysis_type="tornado"),
            {"project": {}},
            lambda _step, _message: None,
        )


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


# --------------------------------------------------------------------------- #
# Integration guard #3 (tornado, end-to-end real engine): the REAL
# _build_assessed_scenario seam + REAL _default_parameters + REAL
# run_sensitivity_analysis run over the assessed lendercase for each supported
# metric — the tornado counterpart to the two MC real-engine guards above. Locks
# the PR-B2 invariants the spy tests cannot: that the canonical driver library
# resolves a non-empty, non-flat driver set against a real screening-mode assessed
# scenario, that the in-memory engine consumes the fresh CF without tripping the
# #996 reconciliation, and that a real SensitivitySuite.model_dump() is JSON-safe
# through the AnalysisResult envelope. A regression in _DEFAULT_DRIVERS, the config
# schema, or the strict-resolve path would fail here rather than shipping green.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("metric", ["project_irr", "equity_irr", "project_npv"])
def test_tornado_real_engine_over_assessed_lendercase(metric: str) -> None:
    export = {
        "scenario": "P75",
        "annual_generation_mwh": 300_000.0,
        "capacity_factor_percent": 22.8,  # fresh screening CF, far from the form's 0.339
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
    # #993: tornado sweeps the FRESH assessed CF (0.228), not the stale form 0.339.
    assert assessed["project"]["capacity_factor"] == pytest.approx(0.228)

    out = default_analysis(
        _request(analysis_type="tornado", metric=metric),
        assessed,
        lambda _step, _message: None,
    )
    engine_result = out["engine_result"]
    assert out["analysis_type"] == "tornado" and out["metric"] == metric
    assert engine_result["metric"] == metric
    # The full canonical driver library resolves over lendercase (6 pct + 1 absolute).
    assert len(engine_result["tornado_results"]) >= 7
    # A supported metric is genuinely sensitive — never a silent all-flat table.
    assert engine_result["metadata"].get("flat_metric") is False


# --------------------------------------------------------------------------- #
# default_analysis: morris branch — the #996-safe in-memory wiring (build_problem
# from the assessed drivers + a raw_config evaluator, never a config_path).
# --------------------------------------------------------------------------- #
def test_default_analysis_morris_wires_in_memory_and_wraps_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}

    def _build_problem_spy(config_path: Any, params: Any = None) -> str:
        captured["bp_params"] = params
        return "PROBLEM_SENTINEL"

    def _run_morris_spy(
        *,
        metrics: Any,
        n_trajectories: int,
        seed: int,
        problem: Any,
        evaluate_fn: Any,
        **_kw: Any,
    ) -> Dict[str, Any]:
        captured["metrics"] = metrics
        captured["n_trajectories"] = n_trajectories
        captured["seed"] = seed
        captured["problem"] = problem
        captured["evaluate_fn"] = evaluate_fn
        return {"method": "morris", "n_runs": 42, "metrics": {metrics[0]: {}}}

    def _eval_spy(
        *, config_path: Any, raw_config: Any, overrides: Any
    ) -> Dict[str, Any]:
        captured["eval_config_path"] = config_path
        captured["eval_raw_config"] = raw_config
        captured["eval_overrides"] = overrides
        return {"kpis": {}}

    monkeypatch.setattr(ar, "build_problem", _build_problem_spy)
    monkeypatch.setattr(ar, "run_morris", _run_morris_spy)
    monkeypatch.setattr(ar, "evaluate_with_overrides", _eval_spy)

    assessed = {
        "monte_carlo": {
            "parameters": [
                {"name": "capex.usd_total", "low": 1.0, "high": 2.0},
                {"name": "opex.usd_per_year", "low": 1.0, "high": 2.0},
            ]
        }
    }
    steps: List[Tuple[int, str]] = []
    out = default_analysis(
        _request(
            analysis_type="morris", metric="project_npv", n_trajectories=12, seed=9
        ),
        assessed,
        lambda step, message: steps.append((step, message)),
    )

    # build_problem got the assessed drivers (params -> no config-file load).
    assert captured["bp_params"] == assessed["monte_carlo"]["parameters"]
    # run_morris got the built problem + the requested knobs.
    assert captured["problem"] == "PROBLEM_SENTINEL"
    assert captured["metrics"] == ["project_npv"]
    assert captured["n_trajectories"] == 12 and captured["seed"] == 9
    # The evaluator is #996-safe: raw_config=assessed, config_path=None (bypasses
    # load_scenario_config and its frozen-bankable reconciliation).
    captured["evaluate_fn"]({"capex.usd_total": 1.5})
    assert captured["eval_config_path"] is None
    assert captured["eval_raw_config"] is assessed
    assert captured["eval_overrides"] == {"capex.usd_total": 1.5}  # sweep row forwarded
    # Envelope carries the run_morris dict verbatim.
    assert out["analysis_type"] == "morris" and out["metric"] == "project_npv"
    assert out["scenario_variant"] == "lendercase"
    assert out["engine_result"]["method"] == "morris"
    assert out["engine_result"]["n_runs"] == 42
    assert (ANALYSIS_TOTAL_STEPS - 1) in [step for step, _ in steps]


# --------------------------------------------------------------------------- #
# Integration guard #4 (morris, end-to-end real engine): real assessed seam + real
# build_problem + real run_morris (SALib) over the assessed lendercase for each
# metric. Locks the #996-safe in-memory wiring — reaching a result at all (no
# AepReconciliationError on the fresh CF) is the invariant the path-based sweep
# would violate. Skips cleanly where SALib is absent (the repo's global-SA pattern).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("metric", ["project_irr", "equity_irr", "project_npv"])
def test_morris_real_engine_over_assessed_lendercase(metric: str) -> None:
    pytest.importorskip("SALib")  # optional-at-call dependency (CASPER); skip if absent
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
    # #993: morris sweeps the FRESH assessed CF (0.228). Reaching a result below (no
    # AepReconciliationError) proves the in-memory path bypasses the #996 reconciliation
    # a path-based run_morris(config_path) would trip on this screening scenario.
    assert assessed["project"]["capacity_factor"] == pytest.approx(0.228)

    out = default_analysis(
        _request(analysis_type="morris", metric=metric, n_trajectories=6),
        assessed,
        lambda _step, _message: None,
    )
    engine_result = out["engine_result"]
    assert out["analysis_type"] == "morris" and out["metric"] == metric
    assert engine_result["method"] == "morris"
    per_metric = engine_result["metrics"][metric]
    # All 6 committed lendercase drivers are swept (>=2 required by build_problem).
    assert len(per_metric.get("drivers") or {}) >= 2
    assert per_metric.get("flat_metric") is False
    assert per_metric.get("nan_poisoned") is False
    # The verbatim run_morris dict (embeds the SALib problem + engine indices) must be
    # JSON-safe for JobRecord.result — lock it (it carries numpy-derived floats).
    import json

    json.dumps(out)


def test_default_analysis_morris_fails_loud_on_too_few_drivers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scenario with <2 sweepable drivers must fail loud (build_problem) BEFORE the
    engine runs — the morris counterpart to the tornado empty-driver guard (CESSPIT)."""

    def _build_problem_raises(config_path: Any, params: Any = None) -> Any:
        raise ValueError("Global SA needs >=2 sweepable drivers (got 1)")

    def _run_morris_must_not_run(**_kw: Any) -> Any:
        raise AssertionError(
            "run_morris must not run when build_problem rejects drivers"
        )

    monkeypatch.setattr(ar, "build_problem", _build_problem_raises)
    monkeypatch.setattr(ar, "run_morris", _run_morris_must_not_run)
    with pytest.raises(ValueError, match=">=2 sweepable drivers"):
        default_analysis(
            _request(analysis_type="morris"),
            {"monte_carlo": {"parameters": [{"name": "capex.usd_total"}]}},
            lambda _step, _message: None,
        )
