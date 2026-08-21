"""Advisory grid-screening report emitter (#884, D8) — tests.

The emitter (``app.reports.grid_screening_emit``) is the opt-in, batch-path caller that composes
the in-house design-stage grid screens and renders a STANDALONE advisory HTML report. These tests
pin the load-bearing #884 guarantees:

  * build success from a scenario with an enabled grid study — the core SCR + reactive screens run
    (via the D3 gateway's closed-form fallback, so no [grid] extra is required in CI);
  * the UN-SUPPRESSIBLE caveat: the SCREENING-not-bankable + EMT-gap caveat and the real #868
    CEB/NSO tender evidence are present in EVERY rendered report and cannot be removed by config;
  * the EMT-confirmation stamp appears when the screened SCR is marginal (< threshold);
  * fail-loud (CESSPIT) on a missing grid block or study_enabled != true (the caller opted in);
  * graceful CASPER degradation: extended screens that need an absent [grid] engine / a missing
    config block downgrade to an honest 'not run' state SURFACED in the report, never a crash;
  * provenance is SURFACED: the resolved [grid] pin set + the available-vs-degraded engine state
    (dependency reproducibility) and the verification-discipline statement;
  * the latency guard (#645): the grid screens must never be reachable from the sync HTTP route;
  * the cardinal rule: the emitter never reconciles a grid number to a finance KPI, and enabling
    the report writes only an advisory artifact (proved byte-identical at the pipeline level in
    tests/integration).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import pytest
import yaml

from analytics.contracts_v14 import (
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    CurtailmentShareResult,
)
from analytics.grid.qsts_evidence import QSTSEvidenceError
from app.reports import grid_screening_emit as gse
from app.reports.grid_screening_emit import (
    EMT_CONFIRMATION_STAMP,
    GRID_EXTRA_PINS,
    MANDATORY_SCREENING_CAVEAT,
    SYNTHETIC_CURTAILMENT_WARNING,
    build_grid_screening_model,
    emit_grid_screening_report_from_pipeline,
    render_grid_screening_html,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _grid_block(*, study_enabled: bool = True) -> Dict[str, Any]:
    """A minimal single-tech grid block the closed-form screens can consume (no [grid] extra)."""
    return {
        "study_enabled": study_enabled,
        "allow_unvalidated_grid": True,
        "poc_voltage_kv": 33.0,
        "source_fault_level_mva": 900.0,
        "source_rx": 0.083,
        "connection_r_ohm": 0.6,
        "connection_x_ohm": 6.0,
        "plant_rating_mva": 159.6,
        "poc": {"bus_name": "Test 220kV", "nominal_kv": 33.0, "plant_rated_mva": 159.6},
        "thevenin": {
            "short_circuit_mva_min": 700.0,
            "short_circuit_mva_max": 1100.0,
            "x_r": 12.0,
            "assumption_basis": "screening_estimate",
        },
        "scr": {"gfl_min": 3.0, "gfl_comfortable": 5.0},
        "gridcode": {
            "pf_range": [-0.95, 0.95],
            "voltage_control_mode": "voltage_droop",
            "lvrt_hvrt_envelope": "ceb_grid_code_2023",
            "rc_k_factor": 2.0,
            "freq_ride_through": "47.5-51.5Hz continuous",
        },
    }


def _scenario(*, study_enabled: bool = True) -> Dict[str, Any]:
    return {
        "scenario_name": "test_grid",
        "grid": _grid_block(study_enabled=study_enabled),
    }


def _write_scenario(tmp_path: Path, cfg: Mapping[str, Any]) -> Path:
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(dict(cfg)), encoding="utf-8")
    return path


# ── build success ──────────────────────────────────────────────────────────


def test_build_model_runs_core_screens() -> None:
    """The core SCR + reactive screens run (closed-form fallback needs no [grid] extra)."""
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    # SCR / band / recommendation are populated from the min-case closed-form screen.
    assert isinstance(model.study.strength.scr, float)
    assert model.study.strength.scr_band in {"weak", "moderate", "strong"}
    assert model.study.strength.gfl_gfm_recommendation
    # Advisory, always — the cardinal rule.
    assert model.study.strength.bankable is False
    assert model.study.bankable is False
    assert model.poc_bus_name == "Test 220kV"


def test_render_html_carries_core_and_provenance_sections() -> None:
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    html = render_grid_screening_html(model)
    # Core SCR + reactive section headers.
    assert "Grid strength (SCR @ POC)" in html
    assert "Reactive capability" in html
    # Provenance sections.
    assert "dependency resolution" in html
    assert "verification discipline" in html


# ── UN-SUPPRESSIBLE caveat + EMT gap + tender evidence ───────────────────────


def test_caveat_is_present_and_unsuppressible() -> None:
    """The SCREENING-not-bankable + EMT-gap caveat + tender evidence appear in EVERY report.

    There is no config field that removes them — they are module constants baked structurally
    into the model + template. This test would fail if a future change made them optional.
    """
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    html = render_grid_screening_html(model)
    assert "SCREENING / DESIGN-STAGE ONLY" in html
    assert MANDATORY_SCREENING_CAVEAT.split("—")[0].strip() in html
    assert "EMT GAP" in html
    assert "RMS / positive-sequence" in html
    # Real #868 CEB/NSO tender evidence — the EMT boundary is EVIDENCED, not abstract.
    assert "2025/003/C" in html
    assert "2026/001/C" in html
    assert "PSCAD/EMTDC" in html


def test_caveat_survives_a_config_that_tries_to_disable_it() -> None:
    """A scenario cannot turn off the caveat via config — it is not config-driven."""
    cfg = _scenario()
    # Hostile config keys that must have NO effect on the un-suppressible caveat.
    cfg["grid"]["suppress_caveat"] = True
    cfg["grid"]["bankable"] = True
    cfg["emit_grid_screen_caveat"] = False
    model = build_grid_screening_model(
        cfg, scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    html = render_grid_screening_html(model)
    assert "SCREENING / DESIGN-STAGE ONLY" in html
    assert model.study.strength.bankable is False  # never flipped by config


def test_emt_stamp_present_when_scr_marginal() -> None:
    """A marginal SCR (< threshold) stamps 'EMT confirmation required' un-suppressibly.

    A very weak connection impedance drives the closed-form SCR below the threshold.
    """
    cfg = _scenario()
    # A high connection reactance → low fault level at POC → marginal SCR.
    cfg["grid"]["connection_x_ohm"] = 50.0
    cfg["grid"]["source_fault_level_mva"] = 200.0
    model = build_grid_screening_model(
        cfg, scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    assert model.emt_confirmation_required is True
    html = render_grid_screening_html(model)
    assert "EMT CONFIRMATION REQUIRED" in EMT_CONFIRMATION_STAMP
    assert "EMT CONFIRMATION REQUIRED" in html


# ── fail-loud (CESSPIT) ──────────────────────────────────────────────────────


def test_missing_grid_block_fails_loud() -> None:
    with pytest.raises(ValueError, match="grid"):
        build_grid_screening_model(
            {"scenario_name": "no_grid"},
            scenario_variant="test",
            generated_at="2020-01-01T00:00:00",
        )


def test_study_disabled_fails_loud() -> None:
    with pytest.raises(ValueError, match="study_enabled"):
        build_grid_screening_model(
            _scenario(study_enabled=False),
            scenario_variant="test",
            generated_at="2020-01-01T00:00:00",
        )


# ── graceful CASPER degradation ──────────────────────────────────────────────


def test_extended_screens_degrade_gracefully_single_tech() -> None:
    """A single-tech scenario (no resources/ppc/qsts blocks) degrades the hybrid screens.

    They must downgrade to an honest 'not run' state SURFACED in degraded_screens, never crash.
    """
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    # The hybrid POC + freq-response screens need multi-tech / ppc blocks that a single-tech
    # scenario lacks → surfaced as degraded, not a crash.
    assert model.poc_envelope is None
    assert model.freq_response is None
    assert "poc_envelope" in model.degraded_screens
    assert "freq_response" in model.degraded_screens
    # The surfaced reason is a non-empty human string.
    assert model.degraded_screens["poc_envelope"]


def test_degraded_screens_surfaced_in_html() -> None:
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    html = render_grid_screening_html(model)
    if model.degraded_screens:
        assert "did not run" in html


def test_executed_synthetic_curtailment_is_presented_with_structural_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#923-E presents a counterfactual without promoting its evidence grade."""
    import analytics.grid.curtailment_qsts as cq

    synthetic = CurtailmentShareResult(
        ran=True,
        feeder_source="/generated/issue923_placeholder.dss",
        feeder_input_kind="synthetic_placeholder",
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
        source_manifest_sha256="a" * 64,
        export_cap_mw=100.0,
        gross_energy_mwh=1_000.0,
        self_curtailed_energy_mwh=80.0,
        limitations=("Generated for software testing; replace with CEB/engineer data.",),
    )
    monkeypatch.setattr(cq, "run_qsts_curtailment", lambda _cfg: synthetic)

    model = build_grid_screening_model(
        _scenario(),
        scenario_variant="synthetic-test",
        generated_at="2020-01-01T00:00:00",
    )
    html = render_grid_screening_html(model)

    assert model.curtailment is synthetic
    assert "curtailment" not in model.degraded_screens
    assert SYNTHETIC_CURTAILMENT_WARNING in html
    assert (
        SYNTHETIC_CURTAILMENT_WARNING
        == "based on synthetic data - non-bankable - only for process provenance purposes"
    )
    assert "SYNTHETIC COUNTERFACTUAL" in html
    assert "not the CEB Kalpitiya/Puttalam feeder" in html
    assert "Canonical-finance eligible?</td><td>NO" in html
    assert "Site-representative?</td><td>NO" in html
    assert "Bankable?</td><td>NO" in html
    assert "a" * 64 in html
    assert "Generated for software testing; replace with CEB/engineer data." in html
    assert "/generated/issue923_placeholder.dss" in html
    assert "Self-curtailed net (MWh, modelled counterfactual)" in html
    assert "Self-curtailed net (MWh, site-modelled loss)" not in html
    assert "Counterfactual only" in html


def test_synthetic_warning_cannot_be_suppressed_by_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hostile report config cannot remove the generated-input warning."""
    import analytics.grid.curtailment_qsts as cq

    synthetic = CurtailmentShareResult(
        ran=True,
        feeder_source="/generated/issue923_placeholder.dss",
        feeder_input_kind="test_fixture",
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
        export_cap_mw=100.0,
        gross_energy_mwh=1_000.0,
        self_curtailed_energy_mwh=80.0,
    )
    monkeypatch.setattr(cq, "run_qsts_curtailment", lambda _cfg: synthetic)
    cfg = _scenario()
    cfg["grid"]["suppress_synthetic_warning"] = True
    cfg["grid"]["qsts_output_is_bankable"] = True

    html = render_grid_screening_html(
        build_grid_screening_model(
            cfg,
            scenario_variant="hostile-synthetic-test",
            generated_at="2020-01-01T00:00:00",
        )
    )

    assert SYNTHETIC_CURTAILMENT_WARNING in html
    assert "Canonical-finance eligible?</td><td>NO" in html


# ── provenance surfaced (dependency reproducibility + verification) ──────────


def test_engine_status_probes_grid_extra_pins() -> None:
    """The provenance surfaces every [grid] pin with its available-vs-degraded state."""
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    probed = {e.distribution for e in model.engine_status}
    assert probed == {dist for dist, _ in GRID_EXTRA_PINS}
    # Each carries the resolved pin and an availability flag (bool).
    for e in model.engine_status:
        assert e.pin
        assert isinstance(e.available, bool)


def test_pin_set_and_available_state_rendered() -> None:
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    html = render_grid_screening_html(model)
    # The resolved pin set is surfaced (dependency reproducibility). Assert against the pins the
    # emitter actually resolved rather than against literals: this test previously hard-coded
    # ``==3.3.0``, which locked in the very drift it was meant to surface — the project declared
    # ``>=3.5,<4`` throughout. Autoescape is on (a hostile bus name must be escaped), so ``>``
    # renders as ``&gt;``.
    from markupsafe import escape

    assert gse.GRID_EXTRA_PINS, "the emitter must resolve a pin set to surface"
    for distribution, pin in gse.GRID_EXTRA_PINS:
        assert distribution in html
        assert str(escape(pin)) in html, f"{distribution} pin {pin!r} not surfaced"
    # The available-vs-degraded wording is present (CASPER state surfaced).
    assert "available" in html or "degraded" in html


def test_degraded_engine_state_when_grid_extra_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When importlib.metadata cannot find an engine, it is surfaced as DEGRADED (absent)."""
    import importlib.metadata as md

    def _always_missing(name: str) -> str:
        raise md.PackageNotFoundError(name)

    monkeypatch.setattr(gse.importlib_metadata, "version", _always_missing)
    statuses = gse._probe_engine_status()
    assert all(s.available is False for s in statuses)
    assert all(s.resolved_version is None for s in statuses)


# ── full emitter writes a report ─────────────────────────────────────────────


def test_emit_writes_standalone_report(tmp_path: Path) -> None:
    scenario = _write_scenario(tmp_path, _scenario())
    result = {"kpis": {"project_irr": 0.0145}}  # accepted for parity, NOT consumed for grid data
    out_html = tmp_path / "grid_screening_report.html"
    written = emit_grid_screening_report_from_pipeline(
        result, scenario, out_html, generated_at="2020-01-01T00:00:00"
    )
    assert written == out_html and out_html.exists()
    html = out_html.read_text(encoding="utf-8")
    assert "SCREENING / DESIGN-STAGE ONLY" in html
    assert "Grid Interconnection SCREENING" in html


def test_emit_generated_at_defaults_to_now(tmp_path: Path) -> None:
    """Omitting generated_at stamps a wall-clock at the production edge (not in the pure builder)."""
    scenario = _write_scenario(tmp_path, _scenario())
    out_html = tmp_path / "r.html"
    emit_grid_screening_report_from_pipeline({}, scenario, out_html)
    assert out_html.exists()


def test_emit_routes_synthetic_qsts_to_segregated_output_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generated result cannot occupy the caller's ordinary report directory."""
    import analytics.grid.curtailment_qsts as cq

    synthetic = CurtailmentShareResult(
        ran=True,
        feeder_source="/fixtures/process-only.dss",
        feeder_input_kind="test_fixture",
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
        export_cap_mw=100.0,
        gross_energy_mwh=100.0,
        self_curtailed_energy_mwh=5.0,
    )
    monkeypatch.setattr(cq, "run_qsts_curtailment", lambda _cfg: synthetic)
    scenario = _write_scenario(tmp_path, _scenario())
    requested = tmp_path / "grid_screening_report.html"

    written = emit_grid_screening_report_from_pipeline({}, scenario, requested)

    assert written == tmp_path / QSTS_SYNTHETIC_OUTPUT_CLASS / requested.name
    assert written.exists()
    assert not requested.exists()
    assert SYNTHETIC_CURTAILMENT_WARNING in written.read_text(encoding="utf-8")


def test_emit_refuses_synthetic_output_with_lender_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import analytics.grid.curtailment_qsts as cq

    synthetic = CurtailmentShareResult(
        ran=True,
        feeder_source="/fixtures/process-only.dss",
        feeder_input_kind="test_fixture",
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
    )
    monkeypatch.setattr(cq, "run_qsts_curtailment", lambda _cfg: synthetic)
    scenario = _write_scenario(tmp_path, _scenario())

    with pytest.raises(ValueError, match="prohibited.*lender"):
        emit_grid_screening_report_from_pipeline({}, scenario, tmp_path / "lender_report.html")


def test_evidence_control_failure_is_not_casper_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identity substitution is a hard refusal, unlike an optional-engine outage."""
    import analytics.grid.curtailment_qsts as cq

    def _identity_failure(_cfg: Mapping[str, Any]) -> CurtailmentShareResult:
        raise QSTSEvidenceError("substituted evidence")

    monkeypatch.setattr(cq, "run_qsts_curtailment", _identity_failure)
    with pytest.raises(QSTSEvidenceError, match="substituted evidence"):
        build_grid_screening_model(
            _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
        )


# ── latency guard (#645) ─────────────────────────────────────────────────────


# ── CASPER: each screen's degradation catch-block (monkeypatch-to-raise) ─────


def test_all_extended_screens_degrade_when_engines_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When each extended screen raises, it degrades to None with a surfaced note — no crash.

    This exercises the CASPER catch-block of every extended screen (harmonics / ride-through /
    poc-envelope / freq-response / curtailment), proving a mid-screen failure never crashes the
    emitter and is always surfaced honestly.
    """
    import analytics.grid.curtailment_qsts as cq
    import analytics.grid.harmonics as harmonics_mod
    import analytics.grid.hybrid.frequency_response as freq_mod
    import analytics.grid.hybrid.poc_aggregation as poc_mod
    import analytics.grid.ride_through as rt_mod

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("simulated engine failure")

    monkeypatch.setattr(harmonics_mod, "screen_harmonics", _boom)
    monkeypatch.setattr(rt_mod, "run_ride_through_suite", _boom)
    monkeypatch.setattr(poc_mod, "aggregate_poc_capability", _boom)
    monkeypatch.setattr(freq_mod, "run_hybrid_frequency_response", _boom)
    monkeypatch.setattr(cq, "run_qsts_curtailment", _boom)

    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    # Core screens still ran; every extended screen degraded to None, surfaced with a reason.
    assert model.study is not None
    assert model.harmonics is None
    assert model.ride_through == ()
    assert model.poc_envelope is None
    assert model.freq_response is None
    assert model.curtailment is None
    for name in (
        "harmonics",
        "ride_through",
        "poc_envelope",
        "freq_response",
        "curtailment",
    ):
        assert name in model.degraded_screens
        assert "simulated engine failure" in model.degraded_screens[name]
    # The report still renders (degradation surfaced, not a crash).
    html = render_grid_screening_html(model)
    assert "SCREENING / DESIGN-STAGE ONLY" in html


def test_ride_through_success_path_sorts_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the ride-through suite returns cases, they are surfaced sorted by kind (success path)."""
    from analytics.contracts_v14 import RideThroughResult

    # Mirror the REAL run_ride_through_suite signature (*, run_dynamics, fixture_path,
    # **case_kwargs) — it takes NO `grid` kwarg (the envelope is fixture-sourced), so the
    # screen must not forward one. (The prior fake required `grid`, encoding the bug.)
    def _fake_suite(*, run_dynamics, **case_kwargs):  # noqa: ANN003, ANN202
        return {
            "lvrt": RideThroughResult.from_case(case="lvrt", ran=True, converged=True),
            "hvrt": RideThroughResult.from_case(case="hvrt", ran=True, converged=True),
            "frequency": RideThroughResult.from_case(case="frequency", ran=True, converged=True),
        }

    import analytics.grid.ride_through as rt_mod

    monkeypatch.setattr(rt_mod, "run_ride_through_suite", _fake_suite)
    model = build_grid_screening_model(
        _scenario(), scenario_variant="test", generated_at="2020-01-01T00:00:00"
    )
    assert [rt.case for rt in model.ride_through] == ["frequency", "hvrt", "lvrt"]
    assert "ride_through" not in model.degraded_screens
    html = render_grid_screening_html(model)
    assert "Ride-through" in html


def test_engine_status_available_when_version_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When importlib.metadata resolves a version, the engine is surfaced as AVAILABLE."""
    monkeypatch.setattr(gse.importlib_metadata, "version", lambda name: "9.9.9")
    statuses = gse._probe_engine_status()
    assert statuses
    assert all(s.available is True for s in statuses)
    assert all(s.resolved_version == "9.9.9" for s in statuses)


def test_fmt_renders_bool_and_string_and_none() -> None:
    """The formatter renders bool→yes/no, passes strings through, and em-dashes None."""
    assert gse._fmt(True) == "yes"
    assert gse._fmt(False) == "no"
    assert gse._fmt("iec60909_min") == "iec60909_min"
    assert gse._fmt(None) == "—"
    assert gse._fmt(1.5, digits=1) == "1.5"


def test_verdict_tristate() -> None:
    assert gse._verdict(True) == "within limits"
    assert gse._verdict(False) == "BREACH"
    assert gse._verdict(None) == "not run"


def test_sync_api_route_is_not_modified_by_this_slice() -> None:
    """The grid screens must never be reachable from the synchronous HTTP route (#645).

    The heavy screens (pandapower / ANDES / OpenDSS) are batch-path only; wiring them into
    ``app/api/main.py`` would reintroduce the latency the #645 ledger forbids.
    """
    main_src = (REPO_ROOT / "app" / "api" / "main.py").read_text(encoding="utf-8")
    assert "grid_screening_emit" not in main_src
    assert "grid_screening_report" not in main_src


# ── dependency-provenance drift guard ────────────────────────────────────────


def test_grid_extra_pins_are_read_from_distribution_metadata() -> None:
    """The surfaced pins must come from the installed distribution, not a hand-kept copy."""
    from app.ops.extras import declared_extras

    declared = declared_extras().get("grid")
    if not declared:  # bare source checkout — the fallback path is exercised below instead
        pytest.skip("project not installed as distribution metadata")
    surfaced = {dist for dist, _ in gse.GRID_EXTRA_PINS}
    assert surfaced == {gse._split_requirement(r)[0] for r in declared}


def test_grid_extra_pins_fallback_matches_declared_metadata() -> None:
    """The static fallback must not drift from pyproject.

    This is the guard for the bug this replaced: the table read ``pandapower ==3.3.0`` while the
    project declared ``>=3.5,<4``, so the report surfaced a false pin as provenance. Comparison
    is on the SET of specifier clauses because metadata normalises their order.
    """
    from app.ops.extras import declared_extras

    declared = declared_extras().get("grid")
    if not declared:
        pytest.skip("project not installed as distribution metadata")

    def clauses(spec: str) -> set[str]:
        return {c.strip() for c in spec.split(",") if c.strip()}

    from_metadata = {
        name: clauses(spec) for name, spec in (gse._split_requirement(r) for r in declared) if name
    }
    for name, spec in gse.GRID_EXTRA_PINS_FALLBACK:
        assert name in from_metadata, f"fallback lists {name}, pyproject does not"
        assert clauses(spec) == from_metadata[name], (
            f"fallback pin for {name} is {spec!r} but pyproject declares "
            f"{','.join(sorted(from_metadata[name]))!r}"
        )


def test_grid_pins_degrade_to_the_fallback_without_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CASPER: an uninstalled source tree still renders a report, using the fallback."""
    import app.ops.extras as ops_extras

    monkeypatch.setattr(ops_extras, "declared_extras", lambda *a, **k: {})
    assert gse._grid_extra_pins() == gse.GRID_EXTRA_PINS_FALLBACK
