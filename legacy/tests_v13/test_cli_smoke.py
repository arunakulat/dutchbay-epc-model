import subprocess
import sys
import pathlib


def test_cli_smoke(tmp_path: pathlib.Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [sys.executable, "-m", "dutchbay_v13", "baseline", "--outdir", str(outdir)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
