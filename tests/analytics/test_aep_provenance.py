#!/usr/bin/env python
"""Provenance-chain enforcement tests for AEP sources (#18).

These are the lender-grade, *test-enforced* guards required by Sprint 10 #18:
- the AEP ``source_id`` in the real lender config must exist in the approved
  manifest (the build fails otherwise);
- a placeholder source (e.g. the retired extrapolated 10 MW curve) is refused
  when a certified OEM curve is available;
- every v14 output carries a standardized ``provenance.aep`` block.

Context:
    Sprint 10 - Issue #18 (Enforce AEP provenance chain in v14 outputs).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.loader.aep_loader import (
    APPROVED_SOURCES,
    assert_source_in_manifest,
    build_provenance_aep_block,
    has_certified_oem_curve,
    is_placeholder_source,
    load_aep_from_summary,
    validate_config_aep_provenance,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
MOCK_SUMMARY = REPO_ROOT / "tests" / "mocks" / "aep_summary_dutchbay.json"

CANONICAL_OEM = "OEM_ENVISION_EN171_65_PC"
PLACEHOLDER_OEM = "OEM_ENVISION_EN171_10_PC"
# The lender case now references the IEA Reference 10 MW (15 x 10 MW re-model).
CANONICAL_LENDER_SOURCE = "IEA_REFERENCE_10MW_198_PC"


@pytest.fixture
def lender_config() -> dict:
    return yaml.safe_load(LENDER_CONFIG.read_text())


# ── Manifest membership ───────────────────────────────────────────────────────


def test_assert_source_in_manifest_accepts_canonical() -> None:
    assert_source_in_manifest(CANONICAL_OEM)  # does not raise


def test_assert_source_in_manifest_rejects_unknown() -> None:
    with pytest.raises(KeyError, match="not in the approved manifest"):
        assert_source_in_manifest("NOT_A_REAL_SOURCE")


# ── Placeholder detection ─────────────────────────────────────────────────────


def test_is_placeholder_source() -> None:
    assert is_placeholder_source(PLACEHOLDER_OEM) is True
    assert is_placeholder_source(CANONICAL_OEM) is False


def test_certified_oem_curve_is_available() -> None:
    assert has_certified_oem_curve(APPROVED_SOURCES) is True


# ── provenance.aep block builder ──────────────────────────────────────────────


def test_build_provenance_aep_block_shape() -> None:
    block = build_provenance_aep_block(
        CANONICAL_OEM, derived_from=["ECMWF_ERA5_2020_2024_DUTCHBAY"]
    )
    assert block["aep_source_id"] == CANONICAL_OEM
    assert block["source_type"] == "OEM"
    assert block["derived_from"] == ["ECMWF_ERA5_2020_2024_DUTCHBAY"]
    assert block["is_placeholder"] is False
    assert "iec_standard" in block


def test_build_provenance_aep_block_unknown_raises() -> None:
    with pytest.raises(KeyError):
        build_provenance_aep_block("NOT_A_REAL_SOURCE")


# ── Config-level enforcement (the P0 guard) ───────────────────────────────────


def test_lender_config_source_is_approved(lender_config: dict) -> None:
    """The real lender config must reference an approved, non-placeholder source."""
    source_id = lender_config["resource"]["power_curve"]["source_id"]
    assert_source_in_manifest(source_id)
    assert is_placeholder_source(source_id) is False


def test_validate_config_provenance_passes_for_lender(lender_config: dict) -> None:
    block = validate_config_aep_provenance(lender_config)
    assert block["aep_source_id"] == CANONICAL_LENDER_SOURCE
    assert block["is_placeholder"] is False


def test_validate_config_provenance_rejects_unknown_source() -> None:
    cfg = {"resource": {"power_curve": {"source_id": "BOGUS_SOURCE"}}}
    with pytest.raises(KeyError):
        validate_config_aep_provenance(cfg)


def test_validate_config_provenance_requires_source() -> None:
    cfg = {"resource": {"power_curve": {}}}
    with pytest.raises(ValueError, match="missing resource.power_curve.source_id"):
        validate_config_aep_provenance(cfg)


def test_validate_config_provenance_refuses_placeholder_when_oem_available() -> None:
    cfg = {"resource": {"power_curve": {"source_id": PLACEHOLDER_OEM}}}
    with pytest.raises(ValueError, match="PLACEHOLDER"):
        validate_config_aep_provenance(cfg)


def test_validate_config_provenance_allows_placeholder_when_flagged() -> None:
    cfg = {"resource": {"power_curve": {"source_id": PLACEHOLDER_OEM}}}
    block = validate_config_aep_provenance(cfg, allow_placeholder=True)
    assert block["is_placeholder"] is True


# ── Output carries provenance.aep ─────────────────────────────────────────────


def test_loaded_summary_carries_provenance_aep_block() -> None:
    aep = load_aep_from_summary(str(MOCK_SUMMARY), validate_manifest=True)
    assert "aep" in aep["provenance"]
    block = aep["provenance"]["aep"]
    assert block["aep_source_id"] == aep["source_id"]
    assert block["is_placeholder"] is False
