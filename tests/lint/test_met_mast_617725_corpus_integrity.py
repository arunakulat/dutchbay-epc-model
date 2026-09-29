"""Integrity guards for the met-mast 617725 public/private evidence boundary."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "docs" / "source_materials" / "met_mast_617725_2025"
MANIFEST = PACKAGE / "MANIFEST.sha256"
PRIVATE_SOURCE_MANIFEST = PACKAGE / "PRIVATE_SOURCE_MANIFEST.sha256"
PRIVATE_REPOSITORY = "arunakulat/DutchBay_RAG"
PRIVATE_COMMIT = "52ae2fecb05f84497a68d00affbd95f4b0c18986"
PRIVATE_SOURCE_PATH = "corpus/met_mast_617725_2025/raw/617725数据导出.txt"
SOURCE_SHA256 = "a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46"
SOURCE_ENV = "DUTCHBAY_MET_MAST_617725_SOURCE"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Independent great-circle distance oracle for comparator regression checks."""
    radius_km = 6_371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _sha256(path: Path) -> str:
    """Return a file digest without loading a large artifact into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(path: Path) -> dict[str, str]:
    """Parse sha256sum-compatible entries while ignoring provenance comments."""
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        digest, separator, relative = line.partition("  ")
        assert separator, f"malformed manifest line in {path}: {line!r}"
        assert len(digest) == 64
        assert relative not in entries, f"duplicate manifest path: {relative}"
        entries[relative] = digest
    return entries


def test_public_manifest_is_complete_and_hash_correct() -> None:
    """Pin every public derivative and reject unrecorded package artifacts."""
    entries = _manifest_entries(MANIFEST)
    on_disk = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file() and path != MANIFEST
    }

    assert set(entries) == on_disk
    for relative, expected_digest in entries.items():
        path = PACKAGE / relative.removeprefix("./")
        assert _sha256(path) == expected_digest, relative


def test_confidential_source_is_hash_pinned_but_not_published() -> None:
    """Keep raw intervals in private RAG while retaining exact public provenance."""
    entries = _manifest_entries(PRIVATE_SOURCE_MANIFEST)
    assert entries == {PRIVATE_SOURCE_PATH: SOURCE_SHA256}
    assert not (PACKAGE / "raw").exists()

    note = PRIVATE_SOURCE_MANIFEST.read_text(encoding="utf-8")
    assert PRIVATE_REPOSITORY in note
    assert PRIVATE_COMMIT in note


def test_private_source_matches_pin_when_explicitly_available() -> None:
    """Verify private bytes locally without making them a public CI dependency."""
    raw_path = os.environ.get(SOURCE_ENV)
    if raw_path is None:
        pytest.skip(f"{SOURCE_ENV} is not configured on this host")

    source = Path(raw_path).expanduser().resolve()
    assert source.is_file(), f"private source does not exist: {source}"
    assert _sha256(source) == SOURCE_SHA256


def test_derived_metadata_binds_to_the_private_source() -> None:
    """Require both structured outputs to carry the immutable cross-repo identity."""
    extracted = PACKAGE / "extracted"
    metadata = json.loads((extracted / "source_metadata.json").read_text())
    summary = json.loads((extracted / "analysis_summary.json").read_text())

    assert metadata["schema"] == "dutchbay.epc.met_mast_source_metadata.v1"
    assert summary["schema"] == "dutchbay.epc.met_mast_analysis_summary.v1"
    assert metadata["source_sha256"] == summary["source_sha256"] == SOURCE_SHA256
    assert metadata["source_repository"] == PRIVATE_REPOSITORY
    assert metadata["source_commit"] == PRIVATE_COMMIT
    assert metadata["source_relative_path"] == PRIVATE_SOURCE_PATH
    assert summary["source_identity"]["repository"] == PRIVATE_REPOSITORY
    assert summary["source_identity"]["commit"] == PRIVATE_COMMIT
    assert summary["source_identity"]["relative_path"] == PRIVATE_SOURCE_PATH


def test_comparator_lineage_and_degree_minute_distances() -> None:
    """Pin comparator sources and independently reject decimal-degree misreading."""
    summary = json.loads((PACKAGE / "extracted" / "analysis_summary.json").read_text())
    lineage = summary["comparison_reference_lineage"]

    proposal = lineage["envision_kalpitiya_60mw_proposal"]
    assert proposal["source_commit"] == "179e43676b6e619ef6fb4d41521de6f6760f0882"
    assert proposal["source_blob_sha1"] == "b4111978fe974f08c11bf9ade2372abc63fb8b84"
    assert proposal["source_sha256"] == (
        "507ca41cbe360d43693d885920af3502e08882b2fbc5f32a18cd1c76a97c707d"
    )
    assert proposal["original_document_sha256"] == (
        "845d3df5c0310b39e42ca4ff729f3eb8c11691aa76c77f7a5416c0dc6adc6d19"
    )

    centroid = lineage["dutchbay_model_centroid"]
    assert centroid["source_commit"] == "071df78b7879af930558e211cb8112d54f690b4a"
    assert centroid["source_blob_sha1"] == "871db05fbd26400b02a413484777d588547ba400"
    assert centroid["source_sha256"] == (
        "6916e13b6f8b11bb062a81c6508edf4438a7a23d17c1372c6170888adeb0fe72"
    )

    nrel = lineage["nrel_2003_measurement_sites"]
    assert nrel["source_location"].endswith("printed page 27")
    assert nrel["source_sha256"] == (
        "be0b54d3b4af53dcb0bf00557fe8868ed13bc7e0d03a57ffb34ca461f08ab633"
    )
    expected_sites = {
        "narakkalliya": ("8 01 N", "79 43 E", 8 + 1 / 60, 79 + 43 / 60),
        "puttalam_met": ("8 02 N", "79 50 E", 8 + 2 / 60, 79 + 50 / 60),
        "karathivu": ("8 13 N", "79 48 E", 8 + 13 / 60, 79 + 48 / 60),
        "wellammalal": ("8 14 N", "79 44 E", 8 + 14 / 60, 79 + 44 / 60),
    }
    source_lat = summary["source_identity"]["coordinates"]["latitude_deg_n"]
    source_lon = summary["source_identity"]["coordinates"]["longitude_deg_e"]
    distances = summary["distance_context"]
    for site, (raw_lat, raw_lon, lat, lon) in expected_sites.items():
        record = nrel["sites"][site]
        assert record["source_lat_deg_min"] == raw_lat
        assert record["source_lon_deg_min"] == raw_lon
        assert record["latitude_deg_n"] == pytest.approx(lat)
        assert record["longitude_deg_e"] == pytest.approx(lon)
        assert distances[f"nrel_{site}_km"] == pytest.approx(
            _haversine_km(source_lat, source_lon, lat, lon), abs=1e-12
        )

    assert distances["nrel_narakkalliya_km"] == pytest.approx(4.507646354441646)
    assert distances["nrel_puttalam_met_km"] == pytest.approx(14.017744852902524)
    assert distances["nrel_karathivu_km"] == pytest.approx(20.4970629004495)
    assert distances["nrel_wellammalal_km"] == pytest.approx(19.87746913562162)


def test_reproducer_requires_an_explicit_private_source() -> None:
    """Do not silently embed a host path or fall back to a public raw copy."""
    script = (
        PACKAGE / "registers" / "analyze_met_mast_617725_2026-09-22.py"
    ).read_text(encoding="utf-8")

    assert 'SOURCE_ENV = "DUTCHBAY_MET_MAST_617725_SOURCE"' in script
    assert "resolve_source_path()" in script
    assert 'ROOT / "raw"' not in script
    assert "/Users/aruna/Downloads/dutchbay-rag" not in script
