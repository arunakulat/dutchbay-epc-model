import math

from src.metrics_v14 import (
    calculate_dscr_series,
    calculate_llcr,
    calculate_plcr,
)


def test_calculate_dscr_series_only_for_operational_years():
    years = [-2, -1, 0, 1, 2]
    cfads = [-50.0, -30.0, 0.0, 20.0, 20.0]
    debt_service = [0.0, 0.0, 0.0, 10.0, 5.0]

    dscr = calculate_dscr_series(cfads, debt_service, years)

    assert len(dscr) == len(years)
    assert dscr[0] == 0.0
    assert dscr[1] == 0.0
    assert dscr[2] == 0.0
    assert math.isclose(dscr[3], 2.0, rel_tol=1e-9)
    assert math.isclose(dscr[4], 4.0, rel_tol=1e-9)


def test_calculate_llcr_basic():
    years = [-2, -1, 0, 1, 2, 3]
    # Larger CFADS so that discounted CFADS comfortably cover the 100 principal
    cfads = [0.0, 0.0, 0.0, 50.0, 60.0, 70.0]
    outstanding_debt = [0.0, 0.0, 100.0, 90.0, 70.0, 50.0]

    llcr = calculate_llcr(
        cfads=cfads,
        outstanding_debt=outstanding_debt,
        discount_rate=0.1,
        years=years,
    )

    assert llcr > 0
    # Now discounted CFADS should exceed the 100 principal
    assert llcr > 1.0


def test_calculate_plcr_basic():
    years = [-2, -1, 0, 1, 2, 3, 4]
    cfads = [0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0]

    plcr = calculate_plcr(
        cfads=cfads,
        project_discount_rate=0.1,
        total_debt=25.0,
        years=years,
    )

    assert plcr > 0
    assert plcr > 1.0

    