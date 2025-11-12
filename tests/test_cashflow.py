from pathlib import Path
from glob import glob
from dutchbay_v13.scenario_runner import run_dir

def test_cashflow_scenario_smoke(tmp_path: Path):
    scen = tmp_path / "scen"; scen.mkdir()
    out  = tmp_path / "out";  out.mkdir()

    # Canonical LKR tariff key; no USD artifacts.
    (scen / "cf.yaml").write_text("tariff_lkr_per_kwh: 36.0\n", encoding="utf-8")

    rc = run_dir(str(scen), str(out), mode="irr", format="both", save_annual=True)
    assert rc == 0

    # Results (JSONL + CSV)
    j = glob(str(out / "scenario_cf_results_*.jsonl"))
    c = glob(str(out / "scenario_cf_results_*.csv"))
    assert len(j) == 1 and len(c) == 1

    # Annual CSV must exist and use the runner's header
    a = glob(str(out / "scenario_cf_annual_*.csv"))
    assert len(a) == 1
    head = Path(a[0]).read_text(encoding="utf-8").splitlines()[0]
    assert head.strip() == "year,cashflow"

    # JSONL content sanity
    line = Path(j[0]).read_text(encoding="utf-8").splitlines()[0]
    import json
    row = json.loads(line)
    for key in ("name", "mode", "equity_irr", "project_irr", "npv"):
        assert key in row
    assert row["name"] == "cf"
