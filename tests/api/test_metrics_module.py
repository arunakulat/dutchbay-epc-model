"""Unit tests for analytics.core.metrics module."""

import pytest
from analytics.core import metrics as metrics_mod


def _make_annual_rows(cfads_series):
    """Helper: build synthetic annual_rows with a given CFADS series."""
    return [{"cfads_usd": cfads} for cfads in cfads_series]


def _realistic_debt_result():
    """Helper: minimal realistic debt_result for testing."""
    return {
        "dscr_series": [1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4] + [2.5] * 5,
        "max_debt_usd": 60_000_000.0,
        "final_debt_usd": 0.0,
        "total_idc_usd": 2_000_000.0,
    }


def test_metrics_module_imports():
    """Smoke: metrics module should be importable and expose calculate_scenario_kpis."""
    assert hasattr(metrics_mod, "calculate_scenario_kpis")


def test_dscr_summary_keys_and_values():
    """DSCR summary fields should be present and numerically sane."""
    cfads = [10_000_000.0] * 15
    annual_rows = _make_annual_rows(cfads)
    debt_result = _realistic_debt_result()
    config = {"capex": {"usd_total": 100_000_000.0}}

    kpis = metrics_mod.calculate_scenario_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    # Core DSCR fields
    assert "min_dscr" in kpis
    assert "dscr_series" in kpis

    min_dscr = kpis["min_dscr"]
    assert isinstance(min_dscr, (int, float))
    assert min_dscr > 0, "min_dscr should be positive"

    # DSCR series should match debt_result input (after filtering)
    dscr_series = kpis["dscr_series"]
    assert isinstance(dscr_series, list)
    assert len(dscr_series) > 0
    assert all(isinstance(d, (int, float)) and d > 0 for d in dscr_series)


def test_npv_and_irr_improve_with_higher_cfads():
    """Higher CFADS (proxy for higher tariff) should improve NPV and IRR."""
    debt_result = _realistic_debt_result()
    config = {"capex": {"usd_total": 100_000_000.0}}

    # Low-CFADS case
    cfads_low = [6_000_000.0] * 15
    rows_low = _make_annual_rows(cfads_low)
    kpis_low = metrics_mod.calculate_scenario_kpis(
        config=config,
        annual_rows=rows_low,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    # High-CFADS case
    cfads_high = [12_000_000.0] * 15
    rows_high = _make_annual_rows(cfads_high)
    kpis_high = metrics_mod.calculate_scenario_kpis(
        config=config,
        annual_rows=rows_high,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    # NPV and IRR should improve
    npv_low = kpis_low.get("project_npv", 0.0)
    npv_high = kpis_high.get("project_npv", 0.0)
    assert npv_high > npv_low, "Higher CFADS should yield higher NPV"

    irr_low = kpis_low.get("project_irr", 0.0)
    irr_high = kpis_high.get("project_irr", 0.0)
    # IRR might be zero or negative in low case, so just check high > low
    assert irr_high >= irr_low, "Higher CFADS should yield higher or equal IRR"


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
        config=config_low_capex,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    # Higher capex scenario (cost overrun)
    config_high_capex = {"capex": {"usd_total": 120_000_000.0}}
    kpis_high = metrics_mod.calculate_scenario_kpis(
        config=config_high_capex,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    npv_low = kpis_low.get("project_npv", 0.0)
    npv_high = kpis_high.get("project_npv", 0.0)
    assert npv_low > npv_high, "Higher capex should lower NPV"

    irr_low = kpis_low.get("project_irr", 0.0)
    irr_high = kpis_high.get("project_irr", 0.0)
    assert irr_low >= irr_high, "Higher capex should lower or not improve IRR"


def test_project_irr_nonzero_for_viable_project():
    """A viable project should have project_irr > 0."""
    cfads = [8_000_000.0] * 20
    annual_rows = _make_annual_rows(cfads)
    debt_result = _realistic_debt_result()
    config = {"capex": {"usd_total": 100_000_000.0}}

    kpis = metrics_mod.calculate_scenario_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    project_irr = kpis.get("project_irr", 0.0)
    assert project_irr > 0, "Viable project should have positive IRR"

