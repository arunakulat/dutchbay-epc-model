from pathlib import Path
import subprocess
import sys


def test_utopia_ranked_and_report(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    # produce pareto artifacts
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "optimize",
        "--pareto",
        "--grid-dr",
        "0.6:0.7:0.1",
        "--grid-tenor",
        "10:10:1",
        "--grid-grace",
        "0:0:1",
        "--outdir",
        str(outdir),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    assert (outdir / "pareto_utopia_ranked.csv").exists()

    # also make a tornado run then build a report
    r2 = subprocess.run(
        [sys.executable, "-m", "dutchbay_v13", "sensitivity", "--outdir", str(outdir)],
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0
    # explicit report mode
    r3 = subprocess.run(
        [sys.executable, "-m", "dutchbay_v13", "report", "--outdir", str(outdir)],
        capture_output=True,
        text=True,
    )
    assert r3.returncode == 0
    assert (outdir / "report.html").exists()
