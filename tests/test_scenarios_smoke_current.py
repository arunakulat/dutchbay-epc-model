from pathlib import Path
from glob import glob

# Import the runner directly so coverage can track imports
from dutchbay_v13.scenario_runner import run_dir

def test_scenarios_emits_csv_and_jsonl(tmp_path: Path):
    inp = tmp_path / "in"; inp.mkdir()
    out = tmp_path / "o";  out.mkdir()

    # minimal override; validator is relaxed to allow this key
    (inp / "demo.yaml").write_text("tariff_usd_per_kwh: 0.12\n", encoding="utf-8")

    # run via direct call (gets coverage)
    res = run_dir(str(inp), str(out), mode="irr", format="both", save_annual=True)
    assert res is not None  # dataframe or list — we only care it ran

    # artifacts should exist and be non-empty
    j = glob(str(out / "scenario_*_results_*.jsonl"))
    c = glob(str(out / "scenario_*_results_*.csv"))
    a = glob(str(out / "scenario_*_annual_*.csv"))
    assert j and c, "results jsonl/csv missing"
    assert a, "annual csv missing when --save-annual was used"
    assert Path(j[0]).stat().st_size > 0
    assert Path(c[0]).stat().st_size > 0
    assert Path(a[0]).stat().st_size > 0
