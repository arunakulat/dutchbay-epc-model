#!/usr/bin/env python
"""Test suite for EPC AEP resource loader with provenance tracking.

Tests manifest validation, SHA-256 checksums, source type detection,
and provenance chain integrity.

Run:
    pytest tests/analytics/test_aep_loader.py -v --cov=analytics.loader.aep_loader

Coverage Target: >90%
Test Count: 18 test cases

Context:
    Sprint 17 - Issues #17 + #18: AEP Loader + Provenance Chain
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from analytics.loader.aep_loader import (
    APPROVED_SOURCES,
    IEC_STANDARDS,
    compute_checksum_sha256,
    create_aep_summary_template,
    export_provenance_report,
    load_aep_from_summary,
    validate_source_manifest,
)


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_aep_summary_dict():
    """Create mock AEP summary dictionary."""
    return {
        "capacity_factor": 0.375,
        "net_site_aep_gwh": 485.32,
        "gross_aep_gwh": 562.15,
        "n_turbines": 23,
        "rated_power_kw": 6500,
        "hub_height_m": 150,
        "source_id": "ECMWF_ERA5_2020_2024_DUTCHBAY",
        "source_type": "ECMWF",
        "derived_from": [
            "OEM_ENVISION_EN171_65_PC",
            "ERA5_WIND_RESOURCE"
        ],
        "losses": {
            "wake_loss_pct": 8.0,
            "availability_pct": 97.0,
            "electrical_loss_pct": 2.0,
        },
    }


@pytest.fixture
def mock_aep_summary_json(mock_aep_summary_dict, tmp_path):
    """Create mock AEP summary JSON file."""
    json_path = tmp_path / "aep_summary_test.json"
    with open(json_path, "w") as f:
        json.dump(mock_aep_summary_dict, f, indent=2)
    return json_path


@pytest.fixture
def mock_aep_summary_csv(mock_aep_summary_dict, tmp_path):
    """Create mock AEP summary CSV file."""
    csv_path = tmp_path / "aep_summary_test.csv"
    df = pd.DataFrame([mock_aep_summary_dict])
    df.to_csv(csv_path, index=False)
    return csv_path


# ═════════════════════════════════════════════════════════════════════════════
# MANIFEST VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_validate_approved_source():
    """Test validation of approved source IDs."""
    assert validate_source_manifest("OEM_ENVISION_EN171_65_PC") is True
    assert validate_source_manifest("ECMWF_ERA5_2020_2024_DUTCHBAY") is True
    assert validate_source_manifest("NREL_WTK_SRI_LANKA_2020_2024") is True


def test_validate_unapproved_source():
    """Test rejection of unapproved source IDs."""
    assert validate_source_manifest("UNKNOWN_SOURCE_123") is False
    assert validate_source_manifest("RANDOM_DATA") is False


def test_validate_custom_manifest():
    """Test validation against custom manifest."""
    custom_manifest = {
        "CUSTOM_SOURCE_A": {"type": "CUSTOM", "iec_standard": "61400-12-1:2022"},
        "CUSTOM_SOURCE_B": {"type": "CUSTOM", "iec_standard": "61400-15-1:2025"},
    }
    
    assert validate_source_manifest("CUSTOM_SOURCE_A", manifest=custom_manifest) is True
    assert validate_source_manifest("OEM_ENVISION_EN171_65_PC", manifest=custom_manifest) is False


def test_approved_sources_structure():
    """Test that APPROVED_SOURCES has correct structure."""
    assert len(APPROVED_SOURCES) >= 3
    
    for source_id, source_meta in APPROVED_SOURCES.items():
        assert "type" in source_meta
        assert "description" in source_meta
        assert "iec_standard" in source_meta
        
        # IEC standard should be valid
        assert source_meta["iec_standard"] in IEC_STANDARDS


# ═════════════════════════════════════════════════════════════════════════════
# CHECKSUM TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_compute_checksum():
    """Test SHA-256 checksum computation."""
    data = {"aep_gwh": 485.32, "capacity_factor": 0.375}
    checksum = compute_checksum_sha256(data)
    
    # SHA-256 produces 64-character hex string
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


def test_checksum_deterministic():
    """Test that checksum is deterministic (same input = same output)."""
    data = {"aep_gwh": 485.32, "capacity_factor": 0.375}
    checksum1 = compute_checksum_sha256(data)
    checksum2 = compute_checksum_sha256(data)
    
    assert checksum1 == checksum2


def test_checksum_changes_with_data():
    """Test that checksum changes when data changes."""
    data1 = {"aep_gwh": 485.32, "capacity_factor": 0.375}
    data2 = {"aep_gwh": 485.33, "capacity_factor": 0.375}  # Slight change
    
    checksum1 = compute_checksum_sha256(data1)
    checksum2 = compute_checksum_sha256(data2)
    
    assert checksum1 != checksum2


# ═════════════════════════════════════════════════════════════════════════════
# AEP LOADING TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_load_aep_from_json(mock_aep_summary_json):
    """Test loading AEP data from JSON file."""
    aep_data = load_aep_from_summary(
        path=str(mock_aep_summary_json),
        validate_manifest=True
    )
    
    # Check required fields
    assert aep_data["net_site_aep_gwh"] == 485.32
    assert aep_data["capacity_factor"] == 0.375
    assert aep_data["n_turbines"] == 23
    assert aep_data["rated_power_kw"] == 6500
    assert aep_data["hub_height_m"] == 150
    assert aep_data["source_id"] == "ECMWF_ERA5_2020_2024_DUTCHBAY"
    assert aep_data["source_type"] == "ECMWF"


def test_load_aep_from_csv(mock_aep_summary_csv):
    """Test loading AEP data from CSV file."""
    aep_data = load_aep_from_summary(
        path=str(mock_aep_summary_csv),
        validate_manifest=True
    )
    
    assert aep_data["net_site_aep_gwh"] == 485.32
    assert aep_data["capacity_factor"] == 0.375


def test_load_aep_provenance_included(mock_aep_summary_json):
    """Test that provenance metadata is included."""
    aep_data = load_aep_from_summary(
        path=str(mock_aep_summary_json),
        validate_manifest=True
    )
    
    assert "provenance" in aep_data
    provenance = aep_data["provenance"]
    
    assert "aep_source_id" in provenance
    assert "derived_from" in provenance
    assert "iec_standard_version" in provenance
    assert "validation_date" in provenance
    assert "checksum_sha256" in provenance
    
    # Checksum should be 64-char SHA-256
    assert len(provenance["checksum_sha256"]) == 64


def test_load_aep_optional_fields(mock_aep_summary_json):
    """Test that optional fields are loaded when present."""
    aep_data = load_aep_from_summary(
        path=str(mock_aep_summary_json),
        validate_manifest=True
    )
    
    assert "gross_aep_gwh" in aep_data
    assert aep_data["gross_aep_gwh"] == 562.15
    
    assert "losses" in aep_data
    assert aep_data["losses"]["wake_loss_pct"] == 8.0


def test_load_aep_missing_file():
    """Test error when file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_aep_from_summary(path="nonexistent_file.json")


def test_load_aep_unsupported_format(tmp_path):
    """Test error with unsupported file format."""
    bad_file = tmp_path / "aep_summary.txt"
    bad_file.write_text("some text")
    
    with pytest.raises(ValueError, match="Unsupported file format"):
        load_aep_from_summary(path=str(bad_file))


def test_load_aep_missing_required_fields(tmp_path):
    """Test error when required fields are missing."""
    incomplete_data = {
        "capacity_factor": 0.375,
        # Missing net_site_aep_gwh and other required fields
    }
    
    json_path = tmp_path / "incomplete.json"
    with open(json_path, "w") as f:
        json.dump(incomplete_data, f)
    
    with pytest.raises(ValueError, match="Missing required fields"):
        load_aep_from_summary(path=str(json_path))


def test_load_aep_invalid_source_id(tmp_path):
    """Test error when source_id not in manifest."""
    invalid_data = {
        "capacity_factor": 0.375,
        "net_site_aep_gwh": 485.32,
        "n_turbines": 23,
        "rated_power_kw": 6500,
        "source_id": "INVALID_SOURCE_XYZ",
        "source_type": "UNKNOWN",
    }
    
    json_path = tmp_path / "invalid_source.json"
    with open(json_path, "w") as f:
        json.dump(invalid_data, f)
    
    with pytest.raises(KeyError, match="not in approved manifest"):
        load_aep_from_summary(path=str(json_path), validate_manifest=True)


def test_load_aep_skip_validation(tmp_path):
    """Test loading with manifest validation disabled."""
    invalid_data = {
        "capacity_factor": 0.375,
        "net_site_aep_gwh": 485.32,
        "n_turbines": 23,
        "rated_power_kw": 6500,
        "source_id": "INVALID_SOURCE_XYZ",
        "source_type": "UNKNOWN",
    }
    
    json_path = tmp_path / "invalid_source.json"
    with open(json_path, "w") as f:
        json.dump(invalid_data, f)
    
    # Should succeed when validation disabled
    aep_data = load_aep_from_summary(path=str(json_path), validate_manifest=False)
    assert aep_data["source_id"] == "INVALID_SOURCE_XYZ"


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_create_aep_summary_template():
    """Test AEP summary template creation."""
    template = create_aep_summary_template()
    
    # Check required fields exist
    assert "capacity_factor" in template
    assert "net_site_aep_gwh" in template
    assert "n_turbines" in template
    assert "rated_power_kw" in template
    assert "source_id" in template
    assert "source_type" in template
    
    # Check optional fields
    assert "losses" in template
    assert "derived_from" in template


# ═════════════════════════════════════════════════════════════════════════════
# PROVENANCE REPORT TESTS
# ═════════════════════════════════════════════════════════════════════════════


def test_export_provenance_report_json(mock_aep_summary_json, tmp_path):
    """Test provenance report export to JSON."""
    aep_data = load_aep_from_summary(str(mock_aep_summary_json))
    
    report_path = tmp_path / "provenance_report.json"
    export_provenance_report(aep_data, str(report_path))
    
    assert report_path.exists()
    
    # Load and validate report
    with open(report_path) as f:
        report = json.load(f)
    
    assert "aep_source_id" in report
    assert "checksum_sha256" in report


def test_export_provenance_report_markdown(mock_aep_summary_json, tmp_path):
    """Test provenance report export to Markdown."""
    aep_data = load_aep_from_summary(str(mock_aep_summary_json))
    
    report_path = tmp_path / "provenance_report.md"
    export_provenance_report(aep_data, str(report_path))
    
    assert report_path.exists()
    
    # Check Markdown content
    content = report_path.read_text()
    assert "# AEP Provenance Report" in content
    assert "Net AEP" in content
    assert "Capacity Factor" in content
    assert "Checksum (SHA-256)" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=analytics.loader.aep_loader"])
