from pathlib import Path
from glob import glob
import dutchbay_v13.cli as cli

def _run_cli(argv):
    try:
        return cli.main(argv)
    except SystemExit as e:
        return e.code

def test_scenarios_two_files(tmp_path: Path):
    scen = tmp_path / "scen"; scen.mkdir()
    out  = tmp_path / "out";  out.mkdir()

    (scen / "a.yaml").write_text("tariff_usd_per_kwh: 0.12\n", encoding="utf-8")
    (scen / "b.yaml").write_text("tariff_usd_per_kwh: 0.08\n",  encoding="utf-8")

    rc = _run_cli([
        "--mode","scenarios",
        "--scenarios", str(scen),
        "--outputs-dir", str(out),
        "--format","both",
        "--save-annual",
    ])
    assert rc == 0

    j = glob(str(out / "scenario_*_results_*.jsonl"))
    c = glob(str(out / "scenario_*_results_*.csv"))
    a = glob(str(out / "scenario_*_annual_*.csv"))
    assert len(j) >= 2 and len(c) >= 2 and len(a) >= 2

    # all artifacts non-empty
    for p in j + c + a:
        assert Path(p).stat().st_size > 0

def test_scenarios_format_switches(tmp_path: Path):
    scen = tmp_path / "scen"; scen.mkdir()
    out  = tmp_path / "out";  out.mkdir()
    (scen / "demo.yaml").write_text("tariff_usd_per_kwh: 0.10\n", encoding="utf-8")

    for fmt in ("json", "csv", "jsonl", "both"):
        out_fmt = out / fmt; out_fmt.mkdir()
        rc = _run_cli([
            "--mode","scenarios",
            "--scenarios", str(scen),
            "--outputs-dir", str(out_fmt),
            "--format", fmt,
            "--save-annual",
        ])
        assert rc == 0

        # At least one result file expected for each format; annual CSV should always appear with --save-annual
        has_any_result = any(glob(str(out_fmt / "scenario_*_results_*.jsonl"))) or any(glob(str(out_fmt / "scenario_*_results_*.csv")))
        assert has_any_result
        a = list((out_fmt).glob("scenario_*_annual_*.csv"))
        assert a and a[0].stat().st_size > 0
