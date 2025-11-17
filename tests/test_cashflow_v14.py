from src.cashflow_v14 import (
    TimelineConfig,
    build_timeline,
    calculate_cfads_with_construction,
)


def test_build_timeline_includes_construction_cod_and_ops():
    cfg = TimelineConfig(construction_years=2, operations_years=20, include_cod_year=True)
    years = build_timeline(cfg)

    assert years[0] == -2
    assert years[1] == -1
    assert years[2] == 0
    assert years[-1] == 20
    assert len(years) == 2 + 1 + 20


def test_calculate_cfads_with_construction_shapes():
    cfg = TimelineConfig(construction_years=2, operations_years=3, include_cod_year=True)
    years = build_timeline(cfg)

    n = len(years)  # should be 6: [-2, -1, 0, 1, 2, 3]

    # Construction years: negative CFADS due to capex (simulated as zero revenue here)
    gross_revenue = [0.0, 0.0, 10.0, 12.0, 15.0, 17.0]
    opex =          [0.0, 0.0,  2.0,  3.0,  4.0,  5.0]
    tax =           [0.0, 0.0,  0.5,  0.8,  1.0,  1.1]
    debt_service =  [0.0, 0.0,  1.0,  1.2,  1.5,  1.6]

    assert len(gross_revenue) == n
    assert len(opex) == n
    assert len(tax) == n
    assert len(debt_service) == n

    cfads = calculate_cfads_with_construction(
        years=years,
        gross_revenue=gross_revenue,
        opex=opex,
        tax=tax,
        debt_service=debt_service,
    )

    assert len(cfads) == n

    # Simple check on an operational year
    # year = 1 => gross 12 - opex 3 - tax 0.8 - ds 1.2 = 7.0
    idx_year1 = years.index(1)
    assert abs(cfads[idx_year1] - 7.0) < 1e-9

    