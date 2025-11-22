from pathlib import Path
from glob import glob

import dutchbay_v13.cli as cli

def test_cli_scenarios_direct(tmp_path: Path):
    scen = tmp_path / "scen"; scen.mkdir()
    out  = tmp_path / "out";  out.mkdir()

    # minimal override; our relaxed validator accepts this key
    (scen / "demo.yaml").write_text("tariff_usd_per_kwh: 0.12\n", encoding="utf-8")

    # run CLI main in-process so coverage sees imports
    argv = [
        "--mode","scenarios",
        "--scenarios", str(scen),
        "--outputs-dir", str(out),
        "--format","both",
        "--save-annual",
    ]
    try:
        rc = cli.main(argv)
    except SystemExit as e:
        rc = e.code

    assert rc == 0

    # artifacts should exist and be non-empty
    j = glob(str(out / "scenario_*_results_*.jsonl"))
    c = glob(str(out / "scenario_*_results_*.csv"))
    a = glob(str(out / "scenario_*_annual_*.csv"))
    assert j and c and a
    assert Path(j[0]).stat().st_size > 0
    assert Path(c[0]).stat().st_size > 0
    assert Path(a[0]).stat().st_size > 0
