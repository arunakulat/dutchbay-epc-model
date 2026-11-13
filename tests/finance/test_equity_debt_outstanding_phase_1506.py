"""Regression tests for equity & API debt_outstanding phase alignment (#1506)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from api.pipeline_api import RunPipelineRequest, _extract_debt, run_pipeline
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    build_equity_distribution_schedule,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_equity_schedule_debt_outstanding_reads_mapped_period() -> None:
    """Equity rows map debt_outstanding_usd through annual_row_debt_period_map (#1506)."""
    annual_rows = [
        {"year": 1, "cfads_usd": 10.0, "debt_service_total": 4.0},
        {"year": 2, "cfads_usd": 10.0, "debt_service_total": 4.0},
    ]
    debt_result: Dict[str, Any] = {
        "debt_service_total": [0.0, 0.0, 1.0, 4.0, 4.0],
        "debt_outstanding": [50.0, 100.0, 100.0, 80.0, 60.0],
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "year": 1, "debt_period": 3},
            {"annual_row_index": 1, "year": 2, "debt_period": 4},
        ],
    }
    cfg = EquityDistributionConfig(initial_equity_investment_usd=100.0)
    sched = build_equity_distribution_schedule(
        annual_rows=annual_rows,
        debt_result=debt_result,
        distribution_config=cfg,
    )
    assert [row["debt_outstanding_usd"] for row in sched] == [80.0, 60.0]


def test_lender_case_equity_and_api_debt_outstanding_align() -> None:
    """On lender case, equity debt_outstanding_usd matches API operating rows (#1506)."""
    full = evaluate_with_overrides(str(_LENDER_CFG), return_full_result=True)
    debt = full["debt_result"]
    eq_rows = full["equity_distribution"]["annual_distributions"]
    period_map = debt["annual_row_debt_period_map"]

    assert len(eq_rows) == len(period_map)
    for eq_row, mapping in zip(eq_rows, period_map, strict=True):
        expected_bal = float(debt["debt_outstanding"][int(mapping["debt_period"])])
        assert eq_row["debt_outstanding_usd"] == pytest.approx(expected_bal)

    resp = run_pipeline(RunPipelineRequest(config_path=str(_LENDER_CFG)))
    op_rows = [r for r in resp.debt.schedule if r.phase == "operating"]
    assert len(op_rows) == len(period_map)
    assert [r.operating_year for r in op_rows] == [int(m["year"]) for m in period_map]
    for api_row, eq_row in zip(op_rows, eq_rows, strict=True):
        assert api_row.debt_outstanding_usd == pytest.approx(
            eq_row["debt_outstanding_usd"]
        )

    con_rows = [r for r in resp.debt.schedule if r.phase == "construction"]
    assert con_rows and all(r.operating_year is None for r in con_rows)


def test_extract_debt_populates_phase_metadata_when_map_present() -> None:
    block = _extract_debt(
        {
            "construction_years": 2,
            "cfads_bridge_debt_period": 2,
            "raw_dscr_series": [None, None, 2.0, 1.3],
            "debt_outstanding": [50.0, 100.0, 100.0, 80.0],
            "debt_service_total": [0.0, 0.0, 5.0, 10.0],
            "annual_row_debt_period_map": [
                {"annual_row_index": 0, "year": 1, "debt_period": 3}
            ],
        }
    )
    assert [r.phase for r in block.schedule] == [
        "construction",
        "construction",
        "bridge",
        "operating",
    ]
    assert [r.operating_year for r in block.schedule] == [None, None, None, 1]
    assert [r.debt_period for r in block.schedule] == [0, 1, 2, 3]
