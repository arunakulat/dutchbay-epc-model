"""
Targeted tests for analytics.core.metrics:

- _summary_stats behaviour on clean and messy inputs.
- calculate_scenario_kpis CFADS + DSCR handling.
- valuation override behaviour.
- compute_kpis adapter passing through scenario_name.
"""

from typing import Any, Dict, List

import math

from analytics.core import metrics


def test_summary_stats_basic_series():
    values = [1, 2, 3, 4]
    stats = metrics._summary_stats(values)  # type: ignore[attr-defined]

    assert stats["min"] == 1
    assert stats["max"] == 4
    assert stats["mean"] == 2.5
    assert stats["median"] == 2.5


def test_summary_stats_ignores_non_finite_and_non_numeric():
    values = [1, None, "x", float("nan"), float("inf"), 5]
    stats = metrics._summary_stats(values)  # type: ignore[attr-defined]

    # Only 1 and 5 should remain
    assert stats["min"] == 1
    assert stats["max"] == 5
    assert stats["mean"] == 3.0
    assert stats["median"] == 3.0


def test_calculate_scenario_kpis_uses_annual_rows_cfads_and_cleans_dscr():
    # Annual rows with CFADS in USD
    annual_rows = [
        {"year": 1, "cfads_usd": 100.0},
        {"year": 2, "cfads_usd": 200.0},
        {"year": 3, "cfads_usd": 300.0},
    ]

    # DSCR series has some junk that should be dropped
    debt_result: Dict[str, Any] = {
        "dscr_series": [1.1, None, 0.0, float("inf"), 1.3],
        "max_debt_usd": 10_000_000,
        "final_debt_usd": 0,
        "total_idc_usd": 500_000,
        # Principal series used to derive equity investment
        "principal_series": [4_000_000, 3_000_000, 3_000_000],
    }

    config: Dict[str, Any] = {
        "capex": {"usd_total": 10_000_000},
        "name": "unit_test_scenario",
    }

    result = metrics.calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=config,
        scenario_name="unit_test_scenario",
    )

    # CFADS aggregates
    assert result["total_cfads_usd"] == 600.0
    assert result["final_cfads_usd"] == 300.0
    assert result["mean_operational_cfads_usd"] == 200.0

    # DSCR should only keep the finite, positive entries [1.1, 1.3]
    assert result["dscr_series"] == [1.1, 1.3]
    assert result["dscr_min"] == 1.1
    assert result["dscr_max"] == 1.3
    assert math.isclose(result["dscr_mean"], 1.2)
    assert math.isclose(result["dscr_median"], 1.2)

    # Valuation numbers should at least be present (we don't assert exact values)
    assert "npv" in result
    assert "irr" in result

    # Scenario name passthrough
    assert result["scenario_name"] == "unit_test_scenario"


def test_calculate_scenario_kpis_uses_valuation_override():
    # Minimal debt_result – just enough to satisfy the contract
    debt_result = {"dscr_series": [1.0, 1.1, 1.2]}

    valuation = {"npv": 1234.5, "irr": 0.1234}

    result = metrics.calculate_scenario_kpis(
        debt_result=debt_result,
        cfads_series_usd=[10.0, 20.0, 30.0],
        valuation=valuation,
    )

    # Valuation dict should be passed through as-is
    assert result["npv"] == 1234.5
    assert result["irr"] == 0.1234


def test_calculate_scenario_kpis_degenerate_cfads_when_missing_everywhere():
    """If no CFADS is provided, we fall back to a zero series sized to DSCR."""
    debt_result = {"dscr_series": [1.0, 1.1, 1.2]}

    result = metrics.calculate_scenario_kpis(
        debt_result=debt_result,
        annual_rows=None,
        cfads_series_usd=None,
    )

    # Ensure the fallback series has the right length and is all zeros
    assert result["total_cfads_usd"] == 0.0
    assert result["final_cfads_usd"] == 0.0
    assert result["mean_operational_cfads_usd"] == 0.0


def test_compute_kpis_adapter_derives_scenario_name_from_config():
    annual_rows = [{"cfads_usd": 100.0}]
    debt_result = {"dscr_series": [1.2], "principal_series": [50.0]}

    config = {"name": "adapter_case", "capex": {"usd_total": 100.0}}

    result = metrics.compute_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
    )

    # Adapter should attach scenario_name for downstream callers
    assert result["scenario_name"] == "adapter_case"
