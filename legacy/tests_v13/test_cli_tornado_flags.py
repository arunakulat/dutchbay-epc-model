from pathlib import Path
import subprocess
import sys


def test_tornado_metric_and_sort(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "sensitivity",
        "--charts",
        "--tornado-metric",
        "dscr",
        "--tornado-sort",
        "asc",
        "--outdir",
        str(outdir),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    assert (outdir / "tornado.png").exists()
