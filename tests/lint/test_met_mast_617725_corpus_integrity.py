"""Integrity guards for the met-mast 617725 public/private evidence boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "docs" / "source_materials" / "met_mast_617725_2025"
MANIFEST = PACKAGE / "MANIFEST.sha256"
PRIVATE_SOURCE_MANIFEST = PACKAGE / "PRIVATE_SOURCE_MANIFEST.sha256"
PRIVATE_REPOSITORY = "arunakulat/DutchBay_RAG"
PRIVATE_COMMIT = "52ae2fecb05f84497a68d00affbd95f4b0c18986"
PRIVATE_SOURCE_PATH = "corpus/met_mast_617725_2025/raw/617725数据导出.txt"
SOURCE_SHA256 = "a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46"


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
        f"./{path.relative_to(PACKAGE).as_posix()}"
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


def test_reproducer_requires_an_explicit_private_source() -> None:
    """Do not silently embed a host path or fall back to a public raw copy."""
    script = (
        PACKAGE / "registers" / "analyze_met_mast_617725_2026-09-22.py"
    ).read_text(encoding="utf-8")

    assert 'SOURCE_ENV = "DUTCHBAY_MET_MAST_617725_SOURCE"' in script
    assert "resolve_source_path()" in script
    assert 'ROOT / "raw"' not in script
    assert "/Users/aruna/Downloads/dutchbay-rag" not in script
