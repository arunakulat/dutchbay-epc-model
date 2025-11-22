from pathlib import Path
from dutchbay_v13.scenario_runner import run_matrix


def test_scenario_matrix_runs(tmp_path: Path):
    matrix = Path("inputs/scenario_matrix.yaml")
    outdir = tmp_path / "o"
    outdir.mkdir()
    df = run_matrix(str(matrix), str(outdir))
    assert not df.empty
    assert {"scenario", "equity_irr", "npv_12pct", "min_dscr"}.issubset(df.columns)
