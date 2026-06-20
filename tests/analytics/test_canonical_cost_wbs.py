"""Canonical CAPEX is a correct bottom-up WBS + the IRENA $/kW sanity banner.

Roadmap #3 (conservative form): the canonical breakdown is a real bottom-up work-breakdown
structure that SUMS to usd_total (replacing the prior stale decorative breakdown that
summed to $150M != the $159.6M total), guarded here. The engine still reads usd_total so
the capex-sensitivity path is unchanged. Plus the IRENA top-down sanity check.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.cost.benchmark import capex_benchmark, irena_benchmark_per_kw
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_canonical_breakdown_sums_to_total() -> None:
    cfg = load_scenario_config(LENDER)
    capex = cfg["capex"]
    line_sum = sum(v for v in capex["breakdown"].values() if isinstance(v, (int, float)))
    assert line_sum == pytest.approx(float(capex["usd_total"]), rel=0.005)  # WBS == total
    assert line_sum == pytest.approx(159_600_000, rel=1e-6)


def test_canonical_wbs_has_real_line_items() -> None:
    """The stale decorative breakdown (epc_usd lump) is gone; real WBS lines present."""
    bd = load_scenario_config(LENDER)["capex"]["breakdown"]
    assert "epc_usd" not in bd  # the old lumped decorative line
    for line in ("wtg_supply_usd", "balance_of_plant_usd", "grid_connection_usd"):
        assert line in bd and bd[line] > 0


def test_irena_benchmark_is_config_sourced() -> None:
    per_kw, year = irena_benchmark_per_kw()
    assert per_kw == pytest.approx(1041.0, abs=1.0)  # config/defaults.yaml
    assert year == 2024


def test_canonical_capex_within_irena_band() -> None:
    b = capex_benchmark(159_600_000.0, 159.6)  # $1,000/kW
    assert b["capex_per_kw_usd"] == pytest.approx(1000.0, abs=1.0)
    assert b["ratio_to_benchmark"] == pytest.approx(0.961, abs=0.01)
    assert b["within_band"] is True


def test_out_of_band_capex_is_flagged() -> None:
    b = capex_benchmark(159.6e6 * 2.5, 159.6)  # ~$2,500/kW, 2.4x the IRENA average
    assert b["within_band"] is False
    assert "OUTSIDE" in b["note"]


def test_run_pipeline_reports_cost_block() -> None:
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert resp.cost.capex_total_usd == pytest.approx(159_600_000, rel=0.001)
    assert resp.cost.capex_per_kw_usd == pytest.approx(1000.0, abs=1.0)
    assert resp.cost.within_band is True
    # economics unchanged by the structural WBS conversion
    assert resp.kpis.project_irr == pytest.approx(0.0844, abs=0.005)
