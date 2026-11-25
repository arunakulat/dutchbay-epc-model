"""Independent negative tests: public R3 ingress scanner fails closed."""

from __future__ import annotations

from pathlib import Path

import pytest
import verify_public_package


def test_clean_source_safe_inventory() -> None:
    record = verify_public_package.verify()
    assert record["status"] == "PASS_SAFE_INVENTORY_AND_R3_SCREENING"


@pytest.mark.parametrize(
    "relative", ["research/private_mast.bin", "raw_EIA_annex.zip", "new.pdf"]
)
def test_unlisted_private_asset_rejected(
    tmp_path: Path, monkeypatch, relative: str
) -> None:
    monkeypatch.setattr(verify_public_package, "PKG", tmp_path)
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"\x00secret raw proprietary source")
    with pytest.raises(ValueError, match="unexpected or missing package assets"):
        verify_public_package.inventory_and_privacy()


def test_exact_public_filename_with_private_path_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    # Uses an allowlisted path, so the control must catch *content*, not just
    # the filename. The bytes use a split path to avoid source-code false positives.
    monkeypatch.setattr(verify_public_package, "PKG", tmp_path)
    monkeypatch.setattr(verify_public_package, "ALLOWED", frozenset({"README.md"}))
    (tmp_path / "README.md").write_bytes(
        b"private " + b"/" + b"Volumes/Data backup/example"
    )
    with pytest.raises(ValueError, match="confidential path"):
        verify_public_package.inventory_and_privacy()
