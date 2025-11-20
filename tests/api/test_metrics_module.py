import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so "analytics" is importable
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.core import metrics as metrics_mod  # type: ignore[attr-defined]


def _make_annual_rows(cfads_series):
    """
    Build a minimal annual_rows structure for metrics.calculate_scenario_kpis.

    We tag the first 3 years as 'construction' and the rest as 'ops', which
    roughly matches how most project finance models split build vs operation.
    """
    rows = []
    for idx, cf in enumerate(cfads_series, start=1):
        phase = "construction" if idx <= 3 else "ops"
        rows.append(
            {
                "year": idx,
                "phase": phase,
                "cfads_usd": cf,
            }
        )
    return rows


def _realistic_debt_result():
    """
    Synthetic but realistic-ish debt profile:

    - Total capex in tests: 80–120m USD.
    - Debt covers 60m (e.g., 60% debt, 40% equity at 100m capex).
    - Principal amortises over 10 years.
    """
    # 10 equal principal repayments totalling 60m
    principal_series = [6_000_000.0] * 10

    return {
        # Simple rising DSCR pattern – roughly what you'd see as the debt stack
        # amortises and CFADS grows with tariff / volume.
        "dscr_series": [1.1, 1.2, 1.3, 1.4, 1.5],
        # Outstanding profile: starts at 60m, drops to 0 over 10 years.
        "debt_outstanding": [
            60_000_000.0,
            54_000_000.0,
            48_000_000.0,
            42_000_000.0,
            36_000_000.0,
            30_000_000.0,
            24_000_000.0,
            18_000_000.0,
            12_000_000.0,
            6_000_000.0,
            0.0,
        ],
        "principal_series": principal_series,
        # Some IDC to keep lenders honest
        "total_idc_usd": 5_000_000.0,
    }


def test_dscr_summary_keys_and_values():
    """DSCR summary fields should be present and numerically sane."""
    cfads = [10_000_000.0] * 15
    annual_rows = _make_annual_rows(cfads)
    debt_result = _realistic_debt_result()
    config = {"capex": {"usd_total": 100_000_000.0}}

    kpis = metrics_mod.calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=config,
    )

    # Required DSCR keys are present
    for key in ("dscr_min", "dscr_max", "dscr_mean", "dscr_median"):
        assert key in kpis

    # And they reflect the synthetic dscr_series
    assert kpis["dscr_min"] == pytest.approx(1.1, rel=1e-6)
    assert kpis["dscr_max"] == pytest.approx(1.5, rel=1e-6)
    # Mean/median should land between min and max
    assert 1.1 <= kpis["dscr_mean"] <= 1.5
    assert 1.1 <= kpis["dscr_median"] <= 1.5


def test_npv_and_irr_improve_with_higher_cfads():
    """Higher CFADS (proxy for higher tariff) should improve NPV and IRR."""
    debt_result = _realistic_debt_result()
    config = {"capex": {"usd_total": 100_000_000.0}}

    # Low-CFADS case
    cfads_low = [6_000_000.0] * 15
    rows_low = _make_annual_rows(cfads_low)
    kpis_low = metrics_mod.calculate_scenario_kpis(
        annual_rows=rows_low,
        debt_result=debt_result,
        config=config,
    )

    # High-CFADS case (stronger tariff / availability)
    cfads_high = [12_000_000.0] * 15
    rows_high = _make_annual_rows(cfads_high)
    kpis_high = metrics_mod.calculate_scenario_kpis(
        annual_rows=rows_high,
        debt_result=debt_result,
        config=config,
    )

    # Sanity: both runs should produce numeric NPV and IRR
    assert isinstance(kpis_low["npv"], (int, float))
    assert isinstance(kpis_high["npv"], (int, float))
    assert isinstance(kpis_low["irr"], (int, float))
    assert isinstance(kpis_high["irr"], (int, float))

    # With higher CFADS, both NPV and IRR should be higher
    assert kpis_high["npv"] > kpis_low["npv"]
    assert kpis_high["irr"] > kpis_low["irr"]


def test_npv_and_irr_worsen_with_higher_capex():
    """
    Higher capex (with same CFADS and same debt quantum) should hurt economics.

    With debt_raised fixed and CFADS unchanged:
      - equity_investment = capex_total - debt_raised increases with capex,
      - so the IRR/NPV on equity should deteriorate.
    """
    debt_result = _realistic_debt_result()

    # Common CFADS across both cases
    cfads = [10_000_000.0] * 15
    annual_rows = _make_annual_rows(cfads)

    # Lower capex baseline (e.g. value-engineered EPC)
    config_low_capex = {"capex": {"usd_total": 80_000_000.0}}
    kpis_low = metrics_mod.calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=config_low_capex,
    )

    # Higher capex case (overruns / more expensive EPC)
    config_high_capex = {"capex": {"usd_total": 120_000_000.0}}
    kpis_high = metrics_mod.calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=config_high_capex,
    )

    # Both should still yield numeric NPV/IRR
    assert isinstance(kpis_low["npv"], (int, float))
    assert isinstance(kpis_high["npv"], (int, float))
    assert isinstance(kpis_low["irr"], (int, float))
    assert isinstance(kpis_high["irr"], (int, float))

    # Economics sanity: *both* NPV and IRR should deteriorate with higher capex
    assert kpis_high["npv"] < kpis_low["npv"]
    assert kpis_high["irr"] < kpis_low["irr"]
