"""Pin the multi-root equity IRR caveat on Blue Whale solar + BESS (#1578 L-13)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from finance.equity_v14 import count_cashflow_sign_changes, equity_irr_ranks_reliably
from finance.irr import irr

REPO_ROOT = Path(__file__).resolve().parents[2]
BLUE_WHALE_SOLAR_BESS = (
    REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
)


def test_blue_whale_solar_bess_flags_multi_sign_change_equity_irr(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Blue Whale solar + BESS flips cashflow sign twice and clears equity_irr_ranks_reliably."""
    with caplog.at_level(
        logging.WARNING, logger="finance.equity_distribution_v14_hydra"
    ):
        result = evaluate_with_overrides(
            str(BLUE_WHALE_SOLAR_BESS), overrides={}, return_full_result=True
        )

    equity = result["equity_distribution"]
    summary = equity["equity_summary"]
    cashflows = equity["equity_cashflows_usd"]
    sign_changes = count_cashflow_sign_changes(cashflows)

    assert sign_changes == 2
    assert summary["equity_cashflow_sign_changes"] == sign_changes
    assert summary["equity_irr_ranks_reliably"] is False
    assert summary["equity_irr"] == pytest.approx(irr(cashflows), abs=1e-12)
    assert result["kpis"]["equity_irr"] == summary["equity_irr"]
    assert any(
        "change sign" in record.getMessage() and "#1456" in record.getMessage()
        for record in caplog.records
    )


def test_single_sign_change_series_still_ranks_reliably() -> None:
    """Responsiveness guard: a conventional project stream keeps the ranking flag True."""
    conventional = [-100.0, 30.0, 35.0, 40.0, 45.0]
    assert count_cashflow_sign_changes(conventional) == 1
    assert equity_irr_ranks_reliably(conventional) is True
