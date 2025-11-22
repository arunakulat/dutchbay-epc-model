from pathlib import Path
import json
from dutchbay_v13.scenario_runner import run_matrix, run_dir


def test_matrix_writes_jsonl(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    df = run_matrix("inputs/scenario_matrix.yaml", str(outdir))
    jsonl = next(outdir.glob("scenario_matrix_results_*.jsonl"), None)
    assert jsonl and jsonl.exists()
    lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(df)
    # parse first line
    json.loads(lines[0])


def test_validator_unknown_param(tmp_path: Path):
    scen_dir = tmp_path / "scen"
    scen_dir.mkdir()
    # unknown key
    (scen_dir / "bad.yaml").write_text("not_a_param: 1\n", encoding="utf-8")
    try:
        run_dir(str(scen_dir), str(tmp_path / "out"))
        assert False, "Expected validation error"
    except ValueError as e:
        assert "Unknown parameter 'not_a_param'" in str(e)
