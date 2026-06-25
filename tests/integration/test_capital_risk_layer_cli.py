"""The capital-risk-layer CLI wires the (previously orphaned) module to a live entrypoint.

Wave-2 #22: analytics/capital_risk_layer_v14 was reachable only from its own unit test. The
thin CLI scripts/run_capital_risk_layer.py makes it invocable; this test runs it end-to-end
on the canonical scenario (small sample count) and pins the JSON contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_capital_risk_layer import default_drivers, main

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_default_drivers_derived_from_scenario() -> None:
    drivers = default_drivers(LENDER)
    assert set(drivers) == {"project.capacity_factor", "tariff.lkr_per_kwh", "capex.usd_total"}
    for spec in drivers.values():
        assert spec["mean"] > 0.0 and spec["std"] > 0.0


def test_cli_runs_and_emits_capital_risk_layer(capsys: pytest.CaptureFixture[str]) -> None:
    # 20 is the module's documented minimum for a stable 95% VaR/CVaR tail.
    rc = main(["--config", LENDER, "--n-samples", "20", "--seed", "7"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    crl = payload["capital_risk_layer"]
    assert crl["n_samples"] == 20
    assert set(crl["dscr"]) == {"min", "p5", "p50", "prob_breach"}
    assert crl["equity_irr_var_cvar"] is not None  # VaR/CVaR computed
    assert payload["drivers"]  # echoes the (derived) driver set
