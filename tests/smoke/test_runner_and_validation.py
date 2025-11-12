import os
from pathlib import Path
import yaml

import pytest

from dutchbay_v13.scenario_runner import run_dir

MINIMAL_GOOD = {
    "project": {"capacity_mw": 150, "timeline": {"lifetime_years": 25}},
    "tariff": {"usd_per_kwh": 0.203},
    "availability_pct": 95,
    "loss_factor": 0.06,
    "capex": {"usd_per_mw": 1_500_000, "floor_per_mw": 1_000_000},
    "opex": {"usd_per_year": 600_000, "floor_usd_per_year": 300_000},
    # financing block optional; keep empty here to test equity-only path
}

def _write_yaml(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p

def test_run_dir_writes_outputs_csv(tmp_path: Path, monkeypatch):
    # relaxed by default (env not set)
    cfg = _write_yaml(tmp_path, "case.yaml", MINIMAL_GOOD)
    outdir = tmp_path / "outputs"
    res = run_dir(cfg, outdir, mode="irr", fmt="csv", save_annual=True)
    # summary file should exist
    produced = list(outdir.glob("*_results_*.csv"))
    assert produced, "expected a results CSV to be written"
    # annual file should exist if runner returns annual rows
    annuals = list(outdir.glob("*_annual_*.csv"))
    # allow either (some configs may not emit annuals); no hard assert here

def test_strict_rejects_unknown_key(tmp_path: Path, monkeypatch):
    bad = dict(MINIMAL_GOOD)
    bad["unknown_key"] = 1
    cfg = _write_yaml(tmp_path, "bad.yaml", bad)
    monkeypatch.setenv("VALIDATION_MODE", "strict")
    with pytest.raises(SystemExit):
        run_dir(cfg, tmp_path / "o", mode="irr", fmt="csv", save_annual=False)

def test_relaxed_allows_metadata(tmp_path: Path, monkeypatch):
    ok = dict(MINIMAL_GOOD)
    ok["notes"] = "harmless"
    cfg = _write_yaml(tmp_path, "ok.yaml", ok)
    monkeypatch.delenv("VALIDATION_MODE", raising=False)  # relaxed default
    res = run_dir(cfg, tmp_path / "o", mode="irr", fmt="jsonl", save_annual=False)
    assert res.summary.get("equity_irr") is not None

    