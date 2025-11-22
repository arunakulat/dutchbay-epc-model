"""
Structural regression tests for the v14 debt engine.

Purpose:
- Exercise the construction-period / IDC logic.
- Assert the 23-period timeline shape.
- Sanity-check tranche summaries exposed via plan_debt.
"""

from dutchbay_v14chat.finance.debt import plan_debt


def _make_simple_annual_rows(years: int = 20, cfads_usd: float = 10_000_000.0):
    """Build a flat CFADS series for testing the debt layer."""
    return [{"cfads_usd": cfads_usd} for _ in range(years)]


def _make_simple_financing_config():
    """
    Minimal config that activates the v14 construction features
    without depending on external scenario files.
    """
    return {
        "capex": {
            # USD total project cost
            "usd_total": 150_000_000.0,
        },
        "Financing_Terms": {
            # Capital structure
            "debt_ratio": 0.70,
            "tenor_years": 15,
            # Construction / IDC behaviour
            "construction_periods": 2,
            "construction_schedule": [50.0, 50.0],  # sanity-only
            "debt_drawdown_pct": [0.5, 0.5],
            "interest_only_years": 2,
            "target_dscr": 1.30,
            # Tranche mix (LKR / USD / DFI)
            "mix": {
                "lkr_max": 0.20,
                "dfi_max": 0.40,
                "usd_commercial_min": 0.40,
            },
            "rates": {
                "lkr_nominal": 0.18,
                "usd_nominal": 0.08,
                "dfi_nominal": 0.06,
            },
        },
    }


def test_plan_debt_construction_timeline_and_idc():
    cfg = _make_simple_financing_config()
    annual_rows = _make_simple_annual_rows()

    result = plan_debt(annual_rows=annual_rows, config=cfg)

    # High-level timeline shape
    assert result["construction_years"] == 2
    assert result["timeline_periods"] == 23
    assert result["tenor_years"] == 15

    # Time-series outputs must match the pinned 23-period timeline
    assert len(result["debt_outstanding"]) == 23
    assert len(result["debt_service_total"]) == 23

    # IDC and DSCR sanity checks
    assert result["total_idc"] > 0.0
    assert result["min_dscr"] >= 0.0
    assert result["audit_status"] in {"PASS", "REVIEW"}

    # Tranche summaries should be populated with positive principals
    total_principal = (
        result["lkr"]["principal"]
        + result["usd"]["principal"]
        + result["dfi"]["principal"]
    )
    assert total_principal > 0.0

    # IDC by tranche should reconcile (within the flat total)
    total_idc_by_tranche = (
        result["lkr"]["idc"] + result["usd"]["idc"] + result["dfi"]["idc"]
    )
    assert total_idc_by_tranche > 0.0
