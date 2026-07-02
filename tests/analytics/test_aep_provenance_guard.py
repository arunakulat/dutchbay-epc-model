#!/usr/bin/env python
"""Live AEP-provenance guard tests (analytics.aep_provenance).

The dormant lender-grade control in analytics.loader.aep_loader
(validate_config_aep_provenance) is folded into the financed path by
analytics.aep_provenance.enforce_aep_provenance, wired at scenario load
(analytics.scenario_loader) and the API boundary (api.pipeline_api). These tests pin:

- the config-first policy (config/defaults.yaml defaults.aep_provenance) + scenario
  overrides;
- enforce/skip/raise behaviour across every policy path;
- that the guard actually FIRES on the live scenario-load path (an unapproved source in
  an authored scenario fails loud), while a sourceless scenario still loads.

Context:
    Item 2 — wire the dormant AEP-provenance guard into the financed run (#18).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.aep_provenance import (
    AepProvenanceError,
    ProvenancePolicy,
    default_provenance_policy,
    enforce_aep_provenance,
    register_scenario_approved_sources,
    resolve_provenance_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
LENDER = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"
BASECASE = (
    SCENARIOS / "dutchbay_basecase_2025Q4.yaml"
)  # declares no power_curve.source_id

APPROVED_REFERENCE = "IEA_REFERENCE_10MW_198_PC"
PLACEHOLDER_OEM = "OEM_ENVISION_EN171_10_PC"


def _cfg(source_id: str | None, **provenance_block: object) -> dict:
    """Build a minimal config with an optional power-curve source + policy override."""
    cfg: dict = {"resource": {}}
    if source_id is not None:
        cfg["resource"]["power_curve"] = {"source_id": source_id}
    if provenance_block:
        cfg["aep_provenance"] = dict(provenance_block)
    return cfg


# ── Config-first policy ───────────────────────────────────────────────────────


def test_default_policy_comes_from_config() -> None:
    policy = default_provenance_policy()
    assert isinstance(policy, ProvenancePolicy)
    # Shipped defaults: enforce on, source not required, placeholders refused.
    assert policy.enforce is True
    assert policy.require_source_id is False
    assert policy.allow_placeholder is False


def test_scenario_overrides_policy_per_key() -> None:
    default = default_provenance_policy()
    resolved = resolve_provenance_policy(
        {"aep_provenance": {"allow_placeholder": True}}
    )
    assert resolved.allow_placeholder is True
    # Unspecified keys fall back to the config default.
    assert resolved.enforce is default.enforce
    assert resolved.require_source_id is default.require_source_id


def test_non_boolean_override_raises() -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        resolve_provenance_policy({"aep_provenance": {"enforce": "yes"}})


# ── enforce_aep_provenance: the policy paths ──────────────────────────────────


def test_approved_source_passes() -> None:
    enforce_aep_provenance(_cfg(APPROVED_REFERENCE), "<approved>")  # must not raise


def test_no_source_id_is_skipped_by_default() -> None:
    enforce_aep_provenance(_cfg(None), "<sourceless>")  # graceful no-op


def test_unapproved_source_raises() -> None:
    with pytest.raises(AepProvenanceError, match="not lender-grade"):
        enforce_aep_provenance(_cfg("OEM_TOTALLY_MADE_UP"), "<bad>")


def test_placeholder_refused_when_certified_oem_available() -> None:
    with pytest.raises(AepProvenanceError):
        enforce_aep_provenance(_cfg(PLACEHOLDER_OEM), "<placeholder>")


def test_allow_placeholder_override_permits_placeholder() -> None:
    enforce_aep_provenance(
        _cfg(PLACEHOLDER_OEM, allow_placeholder=True), "<placeholder-ok>"
    )  # must not raise


def test_require_source_id_rejects_sourceless_scenario() -> None:
    with pytest.raises(AepProvenanceError, match="require_source_id"):
        enforce_aep_provenance(_cfg(None, require_source_id=True), "<must-have-source>")


def test_enforce_false_is_a_total_noop() -> None:
    # Even a bogus source passes when enforcement is disabled by policy.
    enforce_aep_provenance(_cfg("OEM_TOTALLY_MADE_UP", enforce=False), "<disabled>")


# ── The guard actually fires on the LIVE scenario-load path ───────────────────


def test_real_lender_scenario_loads_clean() -> None:
    from analytics.scenario_loader import load_scenario_config

    cfg = load_scenario_config(str(LENDER))  # IEA reference source — approved
    assert cfg["resource"]["power_curve"]["source_id"] == APPROVED_REFERENCE


def test_sourceless_scenario_loads_clean() -> None:
    from analytics.scenario_loader import load_scenario_config

    load_scenario_config(str(BASECASE))  # no source_id -> graceful skip, no raise


def test_scenario_load_rejects_unapproved_source(tmp_path: Path) -> None:
    """An authored scenario naming an un-vetted curve fails loud at load (the wire-in)."""
    from analytics.scenario_loader import load_scenario_config

    base = yaml.safe_load(LENDER.read_text())
    base["resource"]["power_curve"]["source_id"] = "OEM_NOT_IN_MANIFEST"
    bad = tmp_path / "bad_source.yaml"
    bad.write_text(yaml.safe_dump(base))
    with pytest.raises(AepProvenanceError, match="not lender-grade"):
        load_scenario_config(str(bad))


# ── Malformed input fails cleanly (not an uncaught TypeError) ──────────────────


def test_non_scalar_source_id_raises_clean_error() -> None:
    """A list/dict source_id is a clean AepProvenanceError, not an unhashable TypeError."""
    with pytest.raises(AepProvenanceError, match="must be a string"):
        enforce_aep_provenance(
            _cfg(None) | {"resource": {"power_curve": {"source_id": ["x"]}}}, "<list>"
        )


# ── The guard also fires at the dict-accepting seams (API + app service) ───────
# These pin the run_pipeline / run_finance_case wire-ins so deleting either call
# (which accepts an in-memory dict that bypasses the load-time guard) fails the suite.


def test_api_boundary_rejects_unapproved_inline_source() -> None:
    from fastapi import HTTPException

    from api.pipeline_api import RunPipelineRequest, run_pipeline

    cfg = yaml.safe_load(LENDER.read_text())
    cfg["resource"]["power_curve"]["source_id"] = "OEM_NOT_IN_MANIFEST"
    with pytest.raises(HTTPException) as exc:
        run_pipeline(RunPipelineRequest(config=cfg))
    assert exc.value.status_code == 422  # config error, not a 500


def test_app_service_seam_rejects_unapproved_source() -> None:
    from app.services.pipeline_service import run_finance_case

    cfg = yaml.safe_load(LENDER.read_text())
    cfg["resource"]["power_curve"]["source_id"] = "OEM_NOT_IN_MANIFEST"
    with pytest.raises(AepProvenanceError):
        run_finance_case(cfg)


def test_app_service_seam_runs_approved_source() -> None:
    from app.services.pipeline_service import run_finance_case

    result = run_finance_case(yaml.safe_load(LENDER.read_text()))  # approved IEA source
    assert result["status"] == "success"


# ── Config-driven per-project approved-source registration (#661) ─────────────
# A project can admit its OWN vetted turbine/source from config
# (resource.power_curve.approved_sources_yaml) so the provenance guard accepts it —
# without editing the code registry. The manifest is process-global, so every test that
# registers a source snapshots/restores APPROVED_SOURCES (mirrors the aep_loader fixture).

# A project-only source_id + its metadata, absent from the built-in APPROVED_SOURCES.
PROJECT_SOURCE_ID = "OEM_PROJECTX_TESTONLY_PC"
PROJECT_SOURCE_META = {
    "type": "OEM",
    "description": "Project X vetted turbine (test-only project manifest)",
    "iec_standard": "61400-12-1:2022",
    # Points at an existing store slug so validate_curve_selection also resolves.
    "curve_key": "iea_reference_10mw",
}


@pytest.fixture
def restore_approved_sources():
    """Snapshot + restore APPROVED_SOURCES so registration tests don't leak globally."""
    import copy

    from analytics.loader import aep_loader

    snapshot = copy.deepcopy(aep_loader.APPROVED_SOURCES)
    yield
    aep_loader.APPROVED_SOURCES.clear()
    aep_loader.APPROVED_SOURCES.update(snapshot)


def _write_project_manifest(tmp_path: Path, meta: dict | None = None) -> Path:
    """Write a one-entry project approved-sources YAML and return its path."""
    manifest = {
        PROJECT_SOURCE_ID: dict(meta if meta is not None else PROJECT_SOURCE_META)
    }
    path = tmp_path / "approved_sources.yaml"
    path.write_text(yaml.safe_dump(manifest))
    return path


def test_register_widens_manifest_for_project_source(
    restore_approved_sources, tmp_path: Path
) -> None:
    """A source that lives ONLY in the project YAML is admitted before the guard runs."""
    from analytics.loader.aep_loader import validate_source_manifest

    manifest = _write_project_manifest(tmp_path)
    assert validate_source_manifest(PROJECT_SOURCE_ID) is False  # not built-in

    cfg = {
        "resource": {
            "power_curve": {
                "source_id": PROJECT_SOURCE_ID,
                # curve_key is required by validate_curve_selection (config <-> store slug);
                # it matches the registered manifest entry's curve_key below.
                "curve_key": "iea_reference_10mw",
                "approved_sources_yaml": str(manifest),
            }
        }
    }
    registered = register_scenario_approved_sources(cfg, "<project>")
    assert registered == [PROJECT_SOURCE_ID]
    assert validate_source_manifest(PROJECT_SOURCE_ID) is True

    # After registration, both live guards accept the project source.
    enforce_aep_provenance(cfg, "<project>")  # must not raise
    from analytics.wind.aep_summary_builder import validate_curve_selection

    selection = validate_curve_selection(cfg)
    assert selection["source_id"] == PROJECT_SOURCE_ID
    assert selection["curve_key"] == "iea_reference_10mw"


def test_scenario_load_admits_project_only_source(
    restore_approved_sources, tmp_path: Path
) -> None:
    """End-to-end: a scenario whose source_id exists ONLY in its project YAML loads clean.

    Before #661 this would fail loud at load (unapproved source); with the project
    manifest declared, load_scenario_config registers it first, then the guard passes.
    """
    from analytics.scenario_loader import load_scenario_config

    manifest = _write_project_manifest(tmp_path)
    base = yaml.safe_load(LENDER.read_text())
    base["resource"]["power_curve"]["source_id"] = PROJECT_SOURCE_ID
    base["resource"]["power_curve"]["curve_key"] = "iea_reference_10mw"
    # A relative path must resolve against the SCENARIO file's directory.
    base["resource"]["power_curve"]["approved_sources_yaml"] = manifest.name
    scenario = tmp_path / "project_scenario.yaml"
    scenario.write_text(yaml.safe_dump(base))

    cfg = load_scenario_config(str(scenario))  # registers then enforces — no raise
    assert cfg["resource"]["power_curve"]["source_id"] == PROJECT_SOURCE_ID


def test_double_registration_of_identical_entry_is_idempotent(
    restore_approved_sources, tmp_path: Path
) -> None:
    """Re-registering the SAME entry twice is a no-op (not an 'already registered' raise).

    The seam runs twice for a path-based API request (once in load_scenario_config, once
    at the api boundary on the same cfg); an exact-duplicate entry must not fail the
    second pass.
    """
    manifest = _write_project_manifest(tmp_path)
    cfg = {
        "resource": {
            "power_curve": {
                "source_id": PROJECT_SOURCE_ID,
                "approved_sources_yaml": str(manifest),
            }
        }
    }
    first = register_scenario_approved_sources(cfg, "<pass1>")
    second = register_scenario_approved_sources(cfg, "<pass2>")  # must not raise
    assert first == [PROJECT_SOURCE_ID]
    assert second == [PROJECT_SOURCE_ID]


def test_path_based_api_request_with_project_manifest_runs(
    restore_approved_sources, tmp_path: Path, monkeypatch
) -> None:
    """A path-based /run-pipeline request whose scenario declares a project manifest runs.

    This exercises the double-registration path in the API endpoint (load_scenario_config
    registers, then the boundary registers again on the same cfg) end-to-end — it must not
    500 on a spurious duplicate-source error.
    """
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    manifest = _write_project_manifest(tmp_path)
    base = yaml.safe_load(LENDER.read_text())
    base["resource"]["power_curve"]["source_id"] = PROJECT_SOURCE_ID
    base["resource"]["power_curve"]["curve_key"] = "iea_reference_10mw"
    base["resource"]["power_curve"]["approved_sources_yaml"] = manifest.name
    scenario = tmp_path / "project_scenario.yaml"
    scenario.write_text(yaml.safe_dump(base))

    # confined_path resolves config_path under the repo sandbox; point it at tmp_path so the
    # authored scenario + its sibling manifest are reachable for this test.
    import api.pipeline_api as api_mod

    monkeypatch.setattr(
        api_mod, "confined_path", lambda p, must_exist=True: Path(p), raising=True
    )

    from api.pipeline_api import RunPipelineResponse

    # Returning a RunPipelineResponse (rather than raising HTTPException) proves both
    # registration passes ran cleanly (no spurious 'already registered' duplicate error)
    # and the provenance guard accepted the project-only source end-to-end.
    resp = run_pipeline(RunPipelineRequest(config_path=str(scenario)))
    assert isinstance(resp, RunPipelineResponse)
    assert resp.kpis.project_irr is not None


def test_unregistered_project_source_still_fails_loud(tmp_path: Path) -> None:
    """Sanity: WITHOUT the project manifest the same source is rejected at load."""
    from analytics.scenario_loader import load_scenario_config

    base = yaml.safe_load(LENDER.read_text())
    base["resource"]["power_curve"]["source_id"] = PROJECT_SOURCE_ID
    scenario = tmp_path / "unregistered.yaml"
    scenario.write_text(yaml.safe_dump(base))
    with pytest.raises(AepProvenanceError, match="not lender-grade"):
        load_scenario_config(str(scenario))


def test_missing_manifest_fails_loud(tmp_path: Path) -> None:
    """A DECLARED but non-existent manifest must fail loud (CESSPIT — no silent skip)."""
    cfg = {
        "resource": {
            "power_curve": {
                "source_id": PROJECT_SOURCE_ID,
                "approved_sources_yaml": str(tmp_path / "does_not_exist.yaml"),
            }
        }
    }
    with pytest.raises(AepProvenanceError, match="does not resolve to a readable file"):
        register_scenario_approved_sources(cfg, "<missing>")


def test_malformed_manifest_entry_fails_loud(
    restore_approved_sources, tmp_path: Path
) -> None:
    """A manifest entry that fails the per-entry schema (unknown IEC) fails loud."""
    bad_meta = dict(PROJECT_SOURCE_META)
    bad_meta["iec_standard"] = "not-a-real-standard"
    manifest = _write_project_manifest(tmp_path, bad_meta)
    cfg = {
        "resource": {
            "power_curve": {
                "source_id": PROJECT_SOURCE_ID,
                "approved_sources_yaml": str(manifest),
            }
        }
    }
    with pytest.raises(AepProvenanceError, match="could not be loaded"):
        register_scenario_approved_sources(cfg, "<bad-entry>")


def test_project_manifest_cannot_overwrite_builtin(
    restore_approved_sources, tmp_path: Path
) -> None:
    """A project YAML that re-declares a BUILT-IN source_id is refused (no silent widen).

    Default overwrite=False means a duplicate id raises, so a project cannot weaken the
    placeholder / curve-key cross-check controls on the shipped entries.
    """
    manifest = tmp_path / "approved_sources.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                APPROVED_REFERENCE: {
                    "type": "OEM",
                    "description": "attempt to override the built-in reference",
                    "iec_standard": "61400-12-1:2022",
                }
            }
        )
    )
    cfg = {
        "resource": {
            "power_curve": {
                "source_id": APPROVED_REFERENCE,
                "approved_sources_yaml": str(manifest),
            }
        }
    }
    with pytest.raises(AepProvenanceError, match="already registered"):
        register_scenario_approved_sources(cfg, "<override-attempt>")


def test_non_string_manifest_path_raises_clean_error() -> None:
    """A non-string approved_sources_yaml is a clean AepProvenanceError."""
    cfg = {
        "resource": {
            "power_curve": {
                "source_id": PROJECT_SOURCE_ID,
                "approved_sources_yaml": ["not", "a", "string"],
            }
        }
    }
    with pytest.raises(AepProvenanceError, match="must be a string path"):
        register_scenario_approved_sources(cfg, "<list-path>")


def test_no_manifest_declared_is_noop() -> None:
    """The common case: no approved_sources_yaml key -> empty return, no mutation."""
    cfg = {"resource": {"power_curve": {"source_id": APPROVED_REFERENCE}}}
    assert register_scenario_approved_sources(cfg, "<none>") == []
