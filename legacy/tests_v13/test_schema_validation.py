import pytest
from pathlib import Path
from dutchbay_v13.scenario_runner import run_dir


def test_range_violation(tmp_path: Path):
    scen_dir = tmp_path / "scen"
    scen_dir.mkdir()
    # cf_p50 out of bounds
    (scen_dir / "bad.yaml").write_text("cf_p50: 0.80\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        run_dir(str(scen_dir), str(tmp_path / "out"))
    assert "cf_p50" in str(e.value) and "outside allowed range" in str(e.value)


def test_composite_violation(tmp_path: Path):
    scen_dir = tmp_path / "scen"
    scen_dir.mkdir()
    # opex splits don't sum to ~1
    (scen_dir / "bad.yaml").write_text(
        "opex_split_usd: 0.9\nopex_split_lkr: 0.2\n", encoding="utf-8"
    )
    with pytest.raises(ValueError) as e:
        run_dir(str(scen_dir), str(tmp_path / "out"))
    assert "sum to 1.0" in str(e.value)
