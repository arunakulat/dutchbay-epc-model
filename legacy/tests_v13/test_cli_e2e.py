import json
from pathlib import Path
import subprocess
import sys

def test_cli_e2e(tmp_path: Path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "project:\n"
        "  capacity_mw: 150\n"
        "  timeline: { lifetime_years: 25 }\n"
        "capex: { usd_total: 225000000 }\n"
        "Financing_Terms:\n"
        "  debt_ratio: 0.0\n"
        "metrics: { npv_discount_rate: 0.12 }\n",
        encoding="utf-8",
    )
    outdir = tmp_path / "out"
    outdir.mkdir(parents=True, exist_ok=True)

    subprocess.check_call(
        [sys.executable, "-m", "dutchbay_v13", "--mode", "irr", "--config", str(cfg), "--out", str(outdir)]
    )
    summary_path = outdir / "summary.json"
    assert summary_path.exists(), "CLI should emit summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "npv_12" in summary
