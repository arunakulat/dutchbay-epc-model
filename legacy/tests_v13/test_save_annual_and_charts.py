from pathlib import Path
import subprocess
import sys


def test_scenarios_save_annual(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "scenarios",
        "--format",
        "csv",
        "--save-annual",
        "--outdir",
        str(outdir),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    annuals = list(outdir.glob("*_annual_*.csv"))
    assert len(annuals) >= 1


def test_charts_generation(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    # baseline with charts
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "baseline",
        "--outdir",
        str(outdir),
        "--charts",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    assert (outdir / "baseline_dscr.png").exists()
    assert (outdir / "baseline_equity_fcf.png").exists()
