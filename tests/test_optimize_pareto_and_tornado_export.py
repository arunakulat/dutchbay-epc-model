from pathlib import Path
import subprocess
import sys


def test_optimize_pareto_outputs(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "optimize",
        "--pareto",
        "--grid-dr",
        "0.6:0.7:0.1",
        "--grid-tenor",
        "10:12:1",
        "--grid-grace",
        "0:1:1",
        "--outdir",
        str(outdir),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    assert (outdir / "pareto_frontier.csv").exists()
    assert (outdir / "pareto_frontier.json").exists()


def test_tornado_exports(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [sys.executable, "-m", "dutchbay_v13", "sensitivity", "--outdir", str(outdir)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    assert (outdir / "tornado_data.csv").exists()
    assert (outdir / "tornado_data.json").exists()
