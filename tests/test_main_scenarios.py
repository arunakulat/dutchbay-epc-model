import subprocess
import sys


def test_main_scenarios_jsonl(tmp_path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "dutchbay_v13",
            "scenarios",
            "--format",
            "jsonl",
            "--outdir",
            str(outdir),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert any(p.suffix == ".jsonl" for p in outdir.iterdir())
