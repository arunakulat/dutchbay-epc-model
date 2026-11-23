"""Independent negative controls for confidential source ingress screening."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest
from path_guard import TRUSTED_CHECKOUT, require_external_path
from reproduce_wind_screening import _load_curve
from validate_selective_eia_ocr import verify


def _test_curve(tmp_path: Path, factor: float = 1) -> Path:
    file = tmp_path / "mock_oem.csv"
    with file.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["wind_speed_ms", "power_kw", "thrust_coefficient"]
        )
        writer.writeheader()
        for i in range(1, 16):
            writer.writerow(
                {
                    "wind_speed_ms": float(i),
                    "power_kw": 10500.0 * min((i / 12.0) ** 3, 1.0) * factor,
                    "thrust_coefficient": 0.8,
                }
            )
    return file


@pytest.mark.parametrize("factor", [0.001, 1000.0, float("nan"), -1.0])
def test_wrong_curve_units_or_nan_fail_closed(tmp_path: Path, factor: float) -> None:
    with pytest.raises(ValueError):
        _load_curve(_test_curve(tmp_path, factor), 9500.0, 10500.0)


def test_valid_curve_truncates_power_but_retains_declared_ct(tmp_path: Path) -> None:
    ws, power, ct = _load_curve(_test_curve(tmp_path), 9500.0, 10500.0)
    assert len(ws) == 15
    assert max(power) == 9500.0
    assert all(math.isfinite(float(value)) for value in ct)


def test_output_guard_cannot_be_overridden_by_repo_argument(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        require_external_path(
            TRUSTED_CHECKOUT / "private_leak.json", declared_repo=tmp_path
        )


def test_output_guard_rejects_other_git_worktree(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / ".git").write_text("gitdir: deliberately_fake")
    with pytest.raises(ValueError):
        require_external_path(
            foreign / "private_leak.json", declared_repo=TRUSTED_CHECKOUT
        )


def test_output_guard_resolves_symlink(tmp_path: Path) -> None:
    public_path = TRUSTED_CHECKOUT / "docs"
    symlink = tmp_path / "via_symlink"
    symlink.symlink_to(public_path, target_is_directory=True)
    with pytest.raises(ValueError):
        require_external_path(symlink / "leak.csv", declared_repo=tmp_path / "spoof")


@pytest.mark.parametrize(
    "pages", [list(range(0, 98)), list(range(1, 98)) + [293], [1] * 98]
)
def test_ocr_invalid_page_selection_before_pdf_read(
    tmp_path: Path, pages: list[int]
) -> None:
    with pytest.raises(ValueError):
        verify(tmp_path / "missing.pdf", tmp_path / "missing_ocr.pdf", pages)
