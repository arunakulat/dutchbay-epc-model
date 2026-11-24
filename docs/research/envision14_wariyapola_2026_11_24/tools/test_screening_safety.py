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
        for i in range(45):
            speed = 3.0 + i * 0.5
            writer.writerow(
                {
                    "wind_speed_ms": speed,
                    "power_kw": 10500.0
                    * min(((speed - 3.0) / 12.0) ** 3, 1.0)
                    * factor,
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
    assert len(ws) == 45
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


def test_scr_and_transformer_n_minus_one_do_not_imply_deliverability() -> None:
    import json

    package = Path(__file__).resolve().parents[1]
    data = json.loads((package / "results/grid_10_case_screening.json").read_text())
    assert data["status"] == "ILLUSTRATIVE_NON_BANKABLE"
    assert len(data["cases"]) == 10
    both = next(
        x
        for x in data["cases"]
        if x["source_fault_level_mva_SCREENING_ASSUMPTION"] == 900
        and x["circuits"] == 2
    )
    single = next(
        x
        for x in data["cases"]
        if x["source_fault_level_mva_SCREENING_ASSUMPTION"] == 900
        and x["circuits"] == 1
    )
    assert 4.83 < both["scr"] < 4.85
    assert 3.99 < single["scr"] < 4.01
    # 90 MVA surviving transformer cannot export 133 MW, even at unity PF.
    assert (133 - 90) / 133 > 0.32
    assert "NOT MODELLED" in data["transformer_n_minus_one"]
    assert data["transformer_impedance"].startswith("UNMODELLED")


def test_screening_p90_ratio_explicitly_excludes_farm_wake_uncertainty() -> None:
    import json

    package = Path(__file__).resolve().parents[1]
    data = json.loads((package / "results/finance_screening_hold.json").read_text())
    p50_like = data["conditional_2pct_haircut_screen_gwh_NOT_P50"]
    p90_like = data["illustrative_uncertainty_ratio_transfer_gwh_NOT_P90"]
    ratio = 1 - 1.2816 * 0.13155678505693409
    assert abs(p50_like - data["screening_net_gwh"] * 0.98) < 1e-9
    assert abs(p90_like - p50_like * ratio) < 1e-9
    assert data["finance_KPIs_promoted"] is False
    assert (
        "farm wake" in data["illustrative_ratio_derivation"]["excluded_uncertainties"]
    )


def test_rose_stress_not_a_confidence_interval() -> None:
    import json

    package = Path(__file__).resolve().parents[1]
    data = json.loads((package / "results/wind_robustness_screening.json").read_text())
    rotated = [x for x in data["cases"] if "_rose_" in x["case"]]
    assert len(rotated) == 2
    energies = [x["net_screening_gwh"] for x in rotated]
    assert min(energies) < data["baseline_screening_net_gwh"] < max(energies)
    assert data["review_status"] == "NOT_ACCEPTED"
    assert "non-probabilistic" in data["scope"]


def test_revised_envision_config_not_eia_approved_or_CP_complete() -> None:
    import csv

    package = Path(__file__).resolve().parents[1]
    with (package / "evidence/CP_feasibility_33_EIA_crosswalk.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 33
    assert all(
        "NOT ASSESSED" in row["revised_project_status"]
        for row in rows
        if row["type"] == "feasibility_section"
    )
    assert all(
        "NO CLOSE" in row["revised_project_status"]
        for row in rows
        if row["type"] == "condition_precedent"
    )
    assert all(not row["completion_status"].startswith("VERIFIED") for row in rows)
