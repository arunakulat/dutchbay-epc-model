"""Regression tests for Sprint 18B equity distribution production path.

These tests exercise the canonical payload-facing API without running the full
wind/cashflow/debt stack. The pipeline itself wires this function after
cashflow and debt have produced the canonical v14 payload shape.
"""

from __future__ import annotations

from finance.equity_distribution_v14_hydra import (
    calculate_equity_distribution_from_pipeline,
)
from finance.equity import calculate_equity_distribution_from_pipeline as exported_calc


def test_equity_distribution_from_canonical_payload_computes_metrics() -> None:
    """Canonical payload in, equity schedule and metrics out."""
    config = {
        "scenario_name": "equity_payload_base",
        "finance": {"capex_total_usd": 100_000_000.0},
        "equity_distribution": {
            "min_reserve_months": 6,
            "min_dscr_threshold": 1.20,
            "distribution_sweep_pct": 100.0,
            "holdback_pct": 0.0,
            "discount_rate": 0.10,
        },
    }
    annual_rows = [
        {"year": 1, "cf_pre_debt": 18_000_000.0, "debt_service_total": 8_000_000.0},
        {"year": 2, "cf_pre_debt": 20_000_000.0, "debt_service_total": 8_000_000.0},
        {"year": 3, "cf_pre_debt": 22_000_000.0, "debt_service_total": 8_000_000.0},
    ]
    debt_result = {
        "debt_total": 60_000_000.0,
        "debt_service_total": [8_000_000.0, 8_000_000.0, 8_000_000.0],
        "debt_outstanding": [60_000_000.0, 45_000_000.0, 30_000_000.0],
    }

    result = calculate_equity_distribution_from_pipeline(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        kpis={},
    )

    assert result["success"] is True
    assert result["status"] == "computed"
    assert result["scenario_name"] == "equity_payload_base"
    assert result["equity_summary"]["equity_investment_usd"] == 40_000_000.0
    assert result["equity_summary"]["equity_investment_source"] == "capex_less_debt"
    assert result["equity_summary"]["total_equity_distributed_usd"] == 32_000_000.0
    assert result["equity_summary"]["equity_multiple"] == 0.8
    assert result["annual_distributions"][0]["reserve_funded_usd"] == 4_000_000.0
    assert result["annual_distributions"][0]["equity_distribution_usd"] == 6_000_000.0
    assert result["annual_distributions"][1]["equity_distribution_usd"] == 12_000_000.0
    assert result["annual_distributions"][2]["equity_distribution_usd"] == 14_000_000.0
    assert result["metadata"]["computed_from"] == "canonical_v14_pipeline"


def test_equity_distribution_locks_when_dscr_breaches_threshold() -> None:
    """Distribution must be blocked in years that breach DSCR floor."""
    config = {
        "scenario_name": "equity_payload_lockup",
        "finance": {"capex_total_usd": 100_000_000.0},
        "equity_distribution": {
            "min_reserve_months": 0,
            "min_dscr_threshold": 1.30,
            "distribution_sweep_pct": 100.0,
        },
    }
    annual_rows = [
        {"year": 1, "cf_pre_debt": 10_000_000.0, "debt_service_total": 9_000_000.0},
        {"year": 2, "cf_pre_debt": 15_000_000.0, "debt_service_total": 9_000_000.0},
    ]
    debt_result = {
        "debt_total": 60_000_000.0,
        "debt_service_total": [9_000_000.0, 9_000_000.0],
    }

    result = calculate_equity_distribution_from_pipeline(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        kpis={},
    )

    assert result["success"] is True
    assert result["annual_distributions"][0]["covenant_locked"] is True
    assert result["annual_distributions"][0]["equity_distribution_usd"] == 0.0
    assert result["annual_distributions"][1]["covenant_locked"] is False
    assert result["annual_distributions"][1]["equity_distribution_usd"] == 6_000_000.0
    assert result["equity_summary"]["covenant_locked_years"] == 1


def test_equity_distribution_public_package_export() -> None:
    """finance.equity must expose the production distribution API."""
    assert exported_calc is calculate_equity_distribution_from_pipeline
