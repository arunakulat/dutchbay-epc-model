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

import ast
import re
import tomllib
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import pytest
import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

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


def _collectable_test_names(source: str) -> set[str]:
    """Approximate pytest's collectable module/class test-function namespace."""
    tree = ast.parse(source)
    names: set[str] = set()
    disabled_functions = {
        node.targets[0].value.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and node.targets[0].attr == "__test__"
        and isinstance(node.targets[0].value, ast.Name)
        and isinstance(node.value, ast.Constant)
        and node.value.value is False
    }
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_") and node.name not in disabled_functions:
                names.add(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            special_methods = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            explicitly_disabled = any(
                isinstance(child, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__test__"
                    for target in child.targets
                )
                and isinstance(child.value, ast.Constant)
                and child.value.value is False
                for child in node.body
            )
            if explicitly_disabled or {"__init__", "__new__"} & special_methods:
                continue
            for child in node.body:
                if isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and child.name.startswith("test_"):
                    names.add(child.name)
    return names


def _missing_control_citations(module_source: str, test_source: str) -> set[str]:
    cited = set(re.findall(r"\btest_[A-Za-z0-9_]+\b", module_source))
    return cited - _collectable_test_names(test_source)


def _parse_strict_pin_declarations(
    declarations: Sequence[str],
) -> dict[str, frozenset[str]]:
    """Independent PEP 508 oracle for a lossless simple pin table."""
    parsed: dict[str, frozenset[str]] = {}
    for declaration in declarations:
        try:
            requirement = Requirement(declaration)
        except InvalidRequirement as exc:
            raise ValueError(f"unparseable declaration: {declaration!r}") from exc
        if requirement.extras:
            raise ValueError(f"dependency extras are unsupported: {declaration!r}")
        if requirement.marker is not None:
            raise ValueError(f"requirement markers are unsupported: {declaration!r}")
        if requirement.url is not None:
            raise ValueError(
                f"direct URL requirements are unsupported: {declaration!r}"
            )
        name = canonicalize_name(requirement.name)
        if name in parsed:
            raise ValueError(f"duplicate normalized dependency: {name!r}")
        parsed[name] = frozenset(str(item) for item in requirement.specifier)
    return parsed


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
        limitations=(
            "Generated for software testing; replace with CEB/engineer data.",
        ),
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
    # emitter actually resolved rather than against literals: this test previously hard-coded a
    # stale exact pin, which locked in the very drift it was meant to surface. Autoescape is on,
    # so ``>``
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
    result = {
        "kpis": {"project_irr": 0.0145}
    }  # accepted for parity, NOT consumed for grid data
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
        emit_grid_screening_report_from_pipeline(
            {}, scenario, tmp_path / "lender_report.html"
        )


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
            "frequency": RideThroughResult.from_case(
                case="frequency", ran=True, converged=True
            ),
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


def test_every_control_the_module_cites_by_name_exists() -> None:
    """A docstring citing a control nobody can grep for is not a citation.

    ``grid_screening_emit`` pointed at ``test_grid_extra_pins_match_declared_metadata`` as the
    thing holding its fallback to the declared value. No such name has ever existed: the
    control is real but spelled ``..._fallback_matches_...``, so a reader following the
    reference to check the claim found nothing and had to take it on trust.

    Both sides are derived -- the citations by scanning the module's own source, the
    definitions by walking this file's AST -- so neither can be satisfied by restating it.
    """
    module_source = Path(gse.__file__).read_text(encoding="utf-8")
    cited = set(re.findall(r"\btest_[A-Za-z0-9_]+\b", module_source))
    test_source = Path(__file__).read_text(encoding="utf-8")
    defined = _collectable_test_names(test_source)

    module = Path(gse.__file__).name
    assert cited, f"{module} cites no control by name; this guard has gone blind"
    missing = sorted(cited - defined)
    assert not missing, (
        f"{module} cites controls that are not defined in "
        f"{Path(__file__).name}: {missing}"
    )


def test_control_citation_guard_rejects_nested_noncollectable_and_typo_names() -> None:
    """Nested functions and methods on non-Test classes cannot satisfy a citation."""
    hostile_tests = """
def helper():
    def test_shadowed_control():
        pass

class Controls:
    def test_noncollectable_method(self):
        pass

class TestCollected:
    def test_real_control(self):
        pass

class TestDisabled:
    __test__ = False
    def test_disabled_method(self):
        pass

class TestConstructor:
    def __init__(self):
        pass
    def test_constructor_method(self):
        pass
"""
    cited = (
        "test_shadowed_control test_noncollectable_method test_real_control test_typoo "
        "test_disabled_method test_constructor_method"
    )
    assert _missing_control_citations(cited, hostile_tests) == {
        "test_shadowed_control",
        "test_noncollectable_method",
        "test_typoo",
        "test_disabled_method",
        "test_constructor_method",
    }


def test_grid_extra_pins_are_read_from_what_the_tree_declares() -> None:
    """The surfaced pins must come from the executing tree, not a hand-kept copy.

    ``declared_extras`` reads the governing ``pyproject.toml`` first and installed metadata
    only behind it, so a bare source checkout resolves here rather than skipping.
    """
    from app.ops.extras import declared_extras

    declared = declared_extras().get("grid")
    # Neither artifact declares [grid] — the fallback path is exercised below instead.
    if not declared:
        pytest.skip("no [grid] extra in pyproject or in distribution metadata")
    surfaced = {dist for dist, _ in gse.GRID_EXTRA_PINS}
    assert surfaced == {gse._split_requirement(r)[0] for r in declared}


def test_grid_extra_pins_fallback_matches_what_pyproject_declares() -> None:
    """The static fallback must not drift from pyproject.

    This is the guard for the bug this replaced: the table carried a stale exact pin while the
    project declared a compatible range, so the report surfaced false provenance. Comparison
    is on the SET of specifier clauses, not the string: pyproject answers first and returns its
    own text verbatim, but the metadata path behind it re-orders clauses (``>=70,<71`` comes
    back as ``<71,>=70``), so a string compare would pass or fail on which artifact answered.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        raw_grid_requirements = tomllib.load(handle)["project"][
            "optional-dependencies"
        ]["grid"]

    pyproject_pins = _parse_strict_pin_declarations(raw_grid_requirements)
    fallback_declarations = [
        f"{name}{spec}" for name, spec in gse.GRID_EXTRA_PINS_FALLBACK
    ]
    fallback_pins = _parse_strict_pin_declarations(fallback_declarations)
    assert fallback_pins == pyproject_pins
    assert gse.GRID_DEPENDENCY_PROVENANCE.source is gse.DependencySpecSource.PYPROJECT
    assert (
        gse.GRID_DEPENDENCY_PROVENANCE.status is gse.DependencyResolutionStatus.RESOLVED
    )


@pytest.mark.parametrize(
    "declarations,diagnostic",
    [
        (("!!!",), "unparseable"),
        (("Panda_Power>=3", "panda-power<4"), "duplicate normalized"),
        (("pandapower[control]>=3",), "dependency extras"),
        (("pandapower>=3; python_version >= '3.12'",), "requirement markers"),
        (("pandapower @ https://example.invalid/p.whl",), "direct URL"),
    ],
)
def test_independent_pin_oracle_rejects_lossy_or_ambiguous_declarations(
    declarations: tuple[str, ...], diagnostic: str
) -> None:
    with pytest.raises(ValueError, match=diagnostic):
        _parse_strict_pin_declarations(declarations)


def test_valid_pep508_whitespace_is_semantically_equal_and_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PEP 508 whitespace around a comma is valid and must not create false drift."""
    import app.ops.extras as ops_extras

    declarations = (
        "pandapower>=3.5, <4",
        "andes>=2.0",
        "opendssdirect.py>=0.9.4",
    )
    fallback_declarations = tuple(
        f"{name}{spec}" for name, spec in gse.GRID_EXTRA_PINS_FALLBACK
    )
    assert _parse_strict_pin_declarations(
        declarations
    ) == _parse_strict_pin_declarations(fallback_declarations)

    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(
            extras={"grid": declarations}, spec_source="pyproject"
        ),
    )
    pins, provenance = gse._resolve_grid_extra_pins()
    assert _parse_strict_pin_declarations(
        tuple(f"{name}{spec}" for name, spec in pins)
    ) == _parse_strict_pin_declarations(fallback_declarations)
    assert provenance.status is gse.DependencyResolutionStatus.RESOLVED


def test_grid_pins_degrade_to_the_fallback_without_any_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CASPER: a tree that declares nothing resolvable still renders a report.

    Not an uninstalled checkout — that still carries the ``pyproject.toml`` that answers. This
    is the case where neither artifact yields a ``[grid]`` extra.
    """
    import app.ops.extras as ops_extras

    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(extras={}, spec_source="none"),
    )
    pins, provenance = gse._resolve_grid_extra_pins()
    assert pins == gse.GRID_EXTRA_PINS_FALLBACK
    assert provenance.source is gse.DependencySpecSource.STATIC_FALLBACK
    assert provenance.status is gse.DependencyResolutionStatus.FALLBACK


def test_split_requirement_handles_extras_and_garbage() -> None:
    """The requirement parser's edge cases: an extras group, and an unparseable string."""
    assert gse._split_requirement("redis[hiredis]<6,>=5") == ("redis", "<6,>=5")
    assert gse._split_requirement("pandapower<4,>=3.5") == ("pandapower", "<4,>=3.5")
    assert gse._split_requirement("bare") == ("bare", "")
    assert gse._split_requirement("!!!") == (None, "")


def test_grid_pins_degrade_to_the_fallback_when_resolution_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lookup failure cannot masquerade as resolved lender provenance."""
    import app.ops.extras as ops_extras

    def boom(*_a: object, **_k: object) -> dict:
        raise RuntimeError("declaration unreadable")

    monkeypatch.setattr(ops_extras, "resolve_declared_extras", boom)
    with pytest.raises(gse.GridDependencyProvenanceError) as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.source is gse.DependencySpecSource.UNKNOWN
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED


def test_grid_pins_reject_unparseable_and_duplicate_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ops.extras as ops_extras

    for declarations in (
        ("!!!", "andes>=2.0", "opendssdirect.py>=0.9.4"),
        (123, "andes>=2.0", "opendssdirect.py>=0.9.4"),
        ("pandapower>=3.5,<4", "Panda_Power>=3.5,<4", "andes>=2.0"),
    ):
        monkeypatch.setattr(
            ops_extras,
            "resolve_declared_extras",
            lambda *a, _d=declarations, **k: ops_extras.ExtraDeclarations(
                extras={"grid": _d}, spec_source="pyproject"
            ),
        )
        with pytest.raises(gse.GridDependencyProvenanceError) as caught:
            gse._resolve_grid_extra_pins()
        assert (
            caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED
        )


def test_grid_pins_reject_hostile_declaration_only_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An extra declaration cannot ride the lender pin table without fallback review."""
    import app.ops.extras as ops_extras

    declarations = (
        "pandapower>=3.5,<4",
        "andes>=2.0",
        "opendssdirect.py>=0.9.4",
        "declaration-only-payload>=1",
    )
    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(
            extras={"grid": declarations}, spec_source="pyproject"
        ),
    )
    with pytest.raises(gse.GridDependencyProvenanceError) as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.PARTIAL
    assert "declaration-only-payload" in str(caught.value)


def test_grid_pins_reject_explicit_empty_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit empty [grid] is partial, not an absent-source fallback."""
    import app.ops.extras as ops_extras

    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(
            extras={"grid": ()}, spec_source="pyproject"
        ),
    )
    with pytest.raises(gse.GridDependencyProvenanceError) as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.source is gse.DependencySpecSource.PYPROJECT
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.PARTIAL


@pytest.mark.parametrize(
    "hostile_requirement,dimension",
    [
        ("pandapower[control]>=3.5,<4", "extras"),
        ("pandapower>=3.5,<4; python_version >= '3.12'", "markers"),
        ("pandapower @ https://example.invalid/pandapower.whl", "direct URL"),
    ],
)
def test_grid_pins_reject_lossy_pep508_dimensions(
    monkeypatch: pytest.MonkeyPatch,
    hostile_requirement: str,
    dimension: str,
) -> None:
    """Extras, markers and URLs cannot be stripped from surfaced provenance."""
    import app.ops.extras as ops_extras

    declarations = (
        hostile_requirement,
        "andes>=2.0",
        "opendssdirect.py>=0.9.4",
    )
    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(
            extras={"grid": declarations}, spec_source="pyproject"
        ),
    )
    with pytest.raises(gse.GridDependencyProvenanceError) as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED
    assert dimension in str(caught.value)


def test_grid_pin_resolution_observes_declarations_and_source_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source changing after the first read cannot relabel the observed declaration."""
    import app.ops.extras as ops_extras

    pyproject_calls = 0
    metadata_calls = 0
    declarations = {
        "grid": (
            "pandapower>=3.5,<4",
            "andes>=2.0",
            "opendssdirect.py>=0.9.4",
        )
    }

    def changing_pyproject(
        _distribution: str,
    ) -> tuple[Mapping[str, tuple[str, ...]] | None, str | None]:
        nonlocal pyproject_calls
        pyproject_calls += 1
        return (declarations, None) if pyproject_calls == 1 else (None, None)

    def hostile_metadata(
        _distribution: str,
    ) -> tuple[Mapping[str, tuple[str, ...]], str | None]:
        nonlocal metadata_calls
        metadata_calls += 1
        return {"grid": ("substituted>=9",)}, None

    monkeypatch.setattr(ops_extras, "_read_pyproject_extras", changing_pyproject)
    monkeypatch.setattr(ops_extras, "_read_metadata_extras", hostile_metadata)
    pins, provenance = gse._resolve_grid_extra_pins()
    assert pins == tuple(gse.GRID_EXTRA_PINS_FALLBACK)
    assert provenance.source is gse.DependencySpecSource.PYPROJECT
    assert pyproject_calls == 1
    assert metadata_calls == 0


def test_pyproject_marker_survives_source_read_and_fails_lender_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The actual pyproject reader must not erase a marker before strict resolution."""
    import app.ops.extras as ops_extras

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "dutchbay-epc-model"\n'
        "[project.optional-dependencies]\ngrid = ["
        "\"pandapower>=3.5,<4; python_version >= '3.12'\", "
        '"andes>=2.0", "opendssdirect.py>=0.9.4"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", pyproject)

    observation = ops_extras.resolve_declared_extras()
    assert "; python_version" in observation.extras["grid"][0]
    with pytest.raises(gse.GridDependencyProvenanceError, match="markers"):
        gse._resolve_grid_extra_pins()


def test_metadata_compound_marker_retains_complete_marker_and_fails_lender_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A compound selector is retained whole so association cannot erase semantics."""
    import app.ops.extras as ops_extras

    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", tmp_path / "missing.toml")
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            'pandapower>=3.5,<4; python_version >= "3.12" and extra == "grid"',
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.extras["grid"][0].endswith(
        '; python_version >= "3.12" and extra == "grid"'
    )
    with pytest.raises(gse.GridDependencyProvenanceError, match="markers"):
        gse._resolve_grid_extra_pins()


@pytest.mark.parametrize("toml_value", ["[]", '""', "0", "false"])
def test_present_falsy_optional_dependencies_is_malformed_not_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, toml_value: str
) -> None:
    """A present non-table value cannot be laundered into an absent declaration."""
    import app.ops.extras as ops_extras

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "dutchbay-epc-model"\n'
        f"optional-dependencies = {toml_value}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", pyproject)
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            'pandapower>=3.5,<4; extra == "grid"',
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.resolution_error is not None
    assert "optional-dependencies must be a table" in observation.resolution_error
    with pytest.raises(gse.GridDependencyProvenanceError, match="degraded") as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED


@pytest.mark.parametrize(
    "toml_name",
    ["0", "false", "[]", '""', '"   "', '"bad name"', '"bad!name"'],
    ids=[
        "integer",
        "boolean",
        "array",
        "empty",
        "whitespace",
        "embedded-space",
        "invalid-punctuation",
    ],
)
def test_invalid_governing_project_name_blocks_trusted_metadata_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, toml_name: str
) -> None:
    """A present invalid project identity is malformed, not a foreign-project absence."""
    import app.ops.extras as ops_extras

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        f"[project]\nname = {toml_name}\n"
        '[project.optional-dependencies]\ngrid = ["hostile>=9"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", pyproject)
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            'pandapower>=3.5,<4; extra == "grid"',
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.resolution_error is not None
    assert "project.name must be a non-empty valid distribution-name string" in (
        observation.resolution_error
    )
    with pytest.raises(gse.GridDependencyProvenanceError, match="degraded") as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED


def test_valid_foreign_project_name_is_absence_and_allows_metadata_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A standards-valid different project is ordinary source absence, not corruption."""
    import app.ops.extras as ops_extras

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "somebody-elses-project"\n'
        '[project.optional-dependencies]\ngrid = ["hostile>=9"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", pyproject)
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            'pandapower>=3.5,<4; extra == "grid"',
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.resolution_error is None
    assert all("hostile" not in item for item in observation.extras["grid"])
    _pins, provenance = gse._resolve_grid_extra_pins()
    assert provenance.source is gse.DependencySpecSource.METADATA
    assert provenance.status is gse.DependencyResolutionStatus.RESOLVED


def test_metadata_simple_parenthesized_equality_is_the_only_stripped_selector(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Packaging-normalized parentheses around one equality remain a safe association."""
    import app.ops.extras as ops_extras

    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", tmp_path / "missing.toml")
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            'pandapower>=3.5,<4; (extra == "grid")',
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.resolution_error is None
    assert observation.extras["grid"][0] == "pandapower>=3.5,<4"
    _pins, provenance = gse._resolve_grid_extra_pins()
    assert provenance.source is gse.DependencySpecSource.METADATA
    assert provenance.status is gse.DependencyResolutionStatus.RESOLVED


@pytest.mark.parametrize(
    "marker",
    [
        'extra == "grid" and extra == "other"',
        'extra == "grid" and extra == "grid"',
        'extra == "grid" or extra == "other"',
        '(extra == "grid" and python_version >= "3.12")',
    ],
    ids=[
        "distinct-conjunction",
        "repeated-selector",
        "pure-disjunction",
        "nested-compound",
    ],
)
def test_metadata_compound_extra_associations_remain_complete_and_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, marker: str
) -> None:
    """No compound equality expression is simplified during metadata grouping."""
    import app.ops.extras as ops_extras

    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", tmp_path / "missing.toml")
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            f"pandapower>=3.5,<4; {marker}",
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    declaration = next(
        item for item in observation.extras["grid"] if item.startswith("pandapower")
    )
    assert ";" in declaration
    assert "extra" in declaration
    with pytest.raises(gse.GridDependencyProvenanceError, match="markers") as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED


@pytest.mark.parametrize(
    "marker",
    ['extra in "grid"', 'extra not in "grid"', 'extra != "grid"'],
    ids=["in", "not-in", "not-equal"],
)
def test_metadata_unsupported_extra_association_records_resolution_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, marker: str
) -> None:
    """An unsupported extra operator cannot disappear into an incomplete grid declaration."""
    import app.ops.extras as ops_extras

    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", tmp_path / "missing.toml")
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            f"pandapower>=3.5,<4; {marker}",
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.resolution_error is not None
    assert (
        "unsupported metadata extra association marker" in observation.resolution_error
    )
    with pytest.raises(gse.GridDependencyProvenanceError, match="degraded") as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED


def test_malformed_pyproject_cannot_hide_behind_valid_metadata_for_lender_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.ops.extras as ops_extras

    malformed = tmp_path / "pyproject.toml"
    malformed.write_text("not valid TOML ===\n", encoding="utf-8")
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", malformed)
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        lambda _distribution: [
            'pandapower>=3.5,<4; extra == "grid"',
            'andes>=2.0; extra == "grid"',
            'opendssdirect.py>=0.9.4; extra == "grid"',
        ],
    )

    with pytest.raises(gse.GridDependencyProvenanceError, match="degraded") as caught:
        gse._resolve_grid_extra_pins()
    assert caught.value.provenance.status is gse.DependencyResolutionStatus.MALFORMED


def test_realistic_other_extras_without_grid_uses_labelled_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.ops.extras as ops_extras

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "dutchbay-epc-model"\n'
        '[project.optional-dependencies]\nreport = ["jinja2>=3.1"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", pyproject)

    pins, provenance = gse._resolve_grid_extra_pins()
    assert pins == gse.GRID_EXTRA_PINS_FALLBACK
    assert provenance.source is gse.DependencySpecSource.STATIC_FALLBACK
    assert provenance.status is gse.DependencyResolutionStatus.FALLBACK


def test_render_surfaces_dependency_source_and_status() -> None:
    model = build_grid_screening_model(
        _scenario(), scenario_variant="provenance", generated_at="2026-09-14T00:00:00Z"
    )
    html = render_grid_screening_html(model)
    assert "Declaration source:" in html
    assert f">{model.dependency_provenance.source.value}<" in html
    assert f">{model.dependency_provenance.status.value}<" in html
    assert model.dependency_provenance.detail in html
