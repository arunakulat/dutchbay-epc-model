#!/usr/bin/env python
"""Tests for the AEP-summary builder — the two-stage power-curve gap closure.

Covers the curve-selection identifier guard (config slug <-> manifest source_id
<-> store), the one-call summary regeneration (reproduces the canonical 402.6),
and the write/reload round-trip into the AEP loader.

Context:
    Sprint 11 follow-up — power-curve sourcing wiring (#181 thread).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from analytics.loader.aep_loader import load_aep_from_summary
from analytics.wind.aep_summary_builder import (
    build_aep_summary_from_config,
    validate_curve_selection,
    write_aep_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture
def cfg() -> dict:
    return yaml.safe_load(LENDER_CONFIG.read_text())


# ── identifier guard ──────────────────────────────────────────────────────────


def test_lender_curve_selection_valid(cfg: dict) -> None:
    sel = validate_curve_selection(cfg)
    assert sel == {
        "source_id": "OEM_ENVISION_EN171_65_PC",
        "curve_key": "envision_en171_6p5",
        "source_type": "OEM",
    }


def test_curve_key_mismatch_raises(cfg: dict) -> None:
    bad = copy.deepcopy(cfg)
    bad["resource"]["power_curve"]["curve_key"] = "vestas_v150_5p6"  # != manifest
    with pytest.raises(ValueError, match="identifier mismatch"):
        validate_curve_selection(bad)


def test_missing_curve_key_raises(cfg: dict) -> None:
    bad = copy.deepcopy(cfg)
    del bad["resource"]["power_curve"]["curve_key"]
    with pytest.raises(ValueError, match="missing resource.power_curve.curve_key"):
        validate_curve_selection(bad)


def test_unknown_source_raises(cfg: dict) -> None:
    bad = copy.deepcopy(cfg)
    bad["resource"]["power_curve"]["source_id"] = "NOT_A_SOURCE"
    with pytest.raises(KeyError):
        validate_curve_selection(bad)


# ── regeneration ──────────────────────────────────────────────────────────────


def test_regen_reproduces_canonical(cfg: dict) -> None:
    summary = build_aep_summary_from_config(cfg)
    assert summary["net_site_aep_gwh"] == pytest.approx(402.6, abs=0.5)
    assert summary["gross_aep_gwh"] == pytest.approx(459.5, abs=1.0)
    assert summary["capacity_factor"] == pytest.approx(0.307, abs=0.002)
    assert summary["power_curve_key"] == "envision_en171_6p5"
    assert summary["source_id"] == "OEM_ENVISION_EN171_65_PC"
    assert summary["provenance"]["aep"]["is_placeholder"] is False


def test_regen_summary_is_loader_compatible(cfg: dict, tmp_path: Path) -> None:
    """The regenerated summary round-trips through the AEP loader."""
    out = write_aep_summary(cfg, str(tmp_path / "regen_summary.json"))
    assert out.exists()
    loaded = load_aep_from_summary(str(out), validate_manifest=True)
    assert loaded["net_site_aep_gwh"] == pytest.approx(402.6, abs=0.5)
    assert loaded["power_curve_key"] == "envision_en171_6p5"
    assert "aep" in loaded["provenance"]
