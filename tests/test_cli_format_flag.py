from pathlib import Path
import subprocess
import sys


def test_scenarios_format_jsonl_only(tmp_path: Path):
    # Run CLI scenarios with jsonl only and ensure CSV aggregate isn't written
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "scenarios",
        "--format",
        "jsonl",
        "--outdir",
        str(outdir),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    # check files
    jsonls = list(outdir.glob("scenario_*_results_*.jsonl"))
    csvs = list(outdir.glob("scenario_*_results_*.csv"))
    assert len(jsonls) >= 1
    assert len(csvs) == 0


def test_scenarios_format_csv_only(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13",
        "scenarios",
        "--format",
        "csv",
        "--outdir",
        str(outdir),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0
    csvs = list(outdir.glob("scenario_*_results_*.csv"))
    jsonls = list(outdir.glob("scenario_*_results_*.jsonl"))
    assert len(csvs) >= 1
    assert len(jsonls) == 0
