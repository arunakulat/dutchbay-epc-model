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
    resolve_provenance_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
LENDER = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"
BASECASE = SCENARIOS / "dutchbay_basecase_2025Q4.yaml"  # declares no power_curve.source_id

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
    resolved = resolve_provenance_policy({"aep_provenance": {"allow_placeholder": True}})
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
        enforce_aep_provenance(_cfg(None) | {"resource": {"power_curve": {"source_id": ["x"]}}}, "<list>")


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
