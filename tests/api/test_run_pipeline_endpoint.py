"""Tests for the FastAPI /run-pipeline endpoint (api.pipeline_api).

These call the endpoint FUNCTION directly (run_pipeline(RunPipelineRequest(...))) rather
than going through Starlette's TestClient, which would require httpx2 (not a project dep)
— so they run anywhere the finance suite runs. The HTTP wiring itself (router mounted on
the app, live 200) is verified manually; this locks the request/response contract and the
serialisation of KPIs + sculpted debt + AEP.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.pipeline_api import RunPipelineRequest, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_run_pipeline_returns_full_report() -> None:
    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))

    # KPIs reproduce the canonical lender case (FX 333.79 + fitted Weibull).
    assert resp.kpis.project_irr == pytest.approx(0.0543, abs=0.005)
    assert resp.kpis.equity_irr == pytest.approx(0.0145, abs=0.005)
    assert resp.kpis.project_npv_usd is not None
    assert resp.kpis.min_dscr == pytest.approx(1.30, abs=0.02)

    # AEP (bankable, from the committed summary).
    assert resp.aep.net_p50_gwh == pytest.approx(473.8, abs=0.5)
    assert resp.aep.net_p90_gwh == pytest.approx(412.7, abs=1.0)
    assert resp.aep.capacity_factor == pytest.approx(0.339, abs=0.005)

    # Sculpted debt: DSCR-bound, three tranches, a per-period schedule.
    assert resp.debt.debt_total_usd == pytest.approx(100.1e6, rel=0.02)
    assert resp.debt.gearing == pytest.approx(0.6275, abs=0.01)
    assert resp.debt.binding_constraint == "P50"
    assert set(resp.debt.tranches) == {"lkr", "usd", "dfi"}
    assert resp.debt.tranches["usd"].principal_usd > 0
    assert len(resp.debt.schedule) > 15  # full project timeline
    assert all(row.year >= 1 for row in resp.debt.schedule)


def test_overrides_change_economics() -> None:
    """Dotted-key overrides flow into the run — a lower tariff lowers the IRR."""
    base = run_pipeline(RunPipelineRequest(config_path=LENDER))
    cut = run_pipeline(
        RunPipelineRequest(config_path=LENDER, overrides={"tariff.lkr_per_kwh": 16.69})
    )
    assert cut.kpis.project_irr is not None and base.kpis.project_irr is not None
    assert cut.kpis.project_irr < base.kpis.project_irr  # 5c/kWh is worse than 6.1c


def test_inline_config_runs() -> None:
    """A full inline config (no path) runs the same engine."""
    from analytics.scenario_loader import load_scenario_config

    cfg = dict(load_scenario_config(LENDER))
    resp = run_pipeline(RunPipelineRequest(config=cfg))
    assert resp.kpis.project_irr == pytest.approx(0.0543, abs=0.005)
    assert resp.config_path is None


def test_requires_exactly_one_source() -> None:
    with pytest.raises(ValidationError):
        RunPipelineRequest()  # neither
    with pytest.raises(ValidationError):
        RunPipelineRequest(config_path=LENDER, config={"x": 1})  # both


def test_bad_config_path_raises_http_400() -> None:
    with pytest.raises(HTTPException) as exc:
        run_pipeline(RunPipelineRequest(config_path="scenarios/does_not_exist.yaml"))
    assert exc.value.status_code == 400
