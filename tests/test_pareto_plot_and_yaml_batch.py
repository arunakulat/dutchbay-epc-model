from pathlib import Path
import subprocess
import sys


def test_pareto_plot_and_yaml_batch(tmp_path: Path):
    outdir = tmp_path / "o"
    outdir.mkdir()
    # simple single-grid run (pareto.png expected)
    r = subprocess.run(
        [
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
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert (outdir / "pareto.png").exists()

    # YAML batch run with two grids
    grid_yaml = tmp_path / "grids.yaml"
    grid_yaml.write_text(
        """grids:
  - name: G1
    grid_dr: 0.55:0.60:0.05
    grid_tenor: 10:11:1
    grid_grace: 0:1:1
  - name: G2
    grid_dr: [0.6, 0.65]
    grid_tenor: [10, 12]
    grid_grace: [0, 1]
""",
        encoding="utf-8",
    )
    outdir2 = tmp_path / "o2"
    outdir2.mkdir()
    r2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "dutchbay_v13",
            "optimize",
            "--pareto",
            "--grid-file",
            str(grid_yaml),
            "--outdir",
            str(outdir2),
        ],
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0
    # renamed outputs for G1/G2
    assert (outdir2 / "pareto_frontier_G1.csv").exists()
    assert (outdir2 / "pareto_frontier_G2.csv").exists()
    assert (outdir2 / "pareto_G1.png").exists()
    assert (outdir2 / "pareto_G2.png").exists()
    assert (outdir2 / "pareto_summary.json").exists()
