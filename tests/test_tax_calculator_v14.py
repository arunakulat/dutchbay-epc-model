from src.tax_calculator_v14 import (
    TaxScenario,
    build_depreciation_schedule,
    calculate_tax_series,
)


def test_build_depreciation_schedule_straight_line():
    scenario = TaxScenario(
        corporate_rate=0.3,
        tax_holiday_years=5,
        tax_holiday_start_year=1,
        depreciation_method="straight_line",
        depreciation_years=10,
    )

    dep = build_depreciation_schedule(
        asset_value=100_000_000,
        operations_years=20,
        scenario=scenario,
    )

    assert len(dep) == 20
    assert dep[0] > 0.0
    assert all(d > 0.0 for d in dep[:10])
    assert all(d == 0.0 for d in dep[10:])


def test_build_depreciation_schedule_accelerated():
    scenario = TaxScenario(
        corporate_rate=0.3,
        tax_holiday_years=5,
        tax_holiday_start_year=1,
        depreciation_method="accelerated",
        depreciation_years=10,
        accelerated_factor=1.5,
    )

    dep = build_depreciation_schedule(
        asset_value=100_000_000,
        operations_years=20,
        scenario=scenario,
    )

    assert len(dep) == 20
    # Depreciation should start high and then decline / go to zero
    assert dep[0] > dep[5] or dep[5] == 0.0
    assert abs(sum(dep) - 100_000_000) < 1e-2


def test_calculate_tax_series_with_holiday_and_losses():
    years = [-2, -1, 0, 1, 2, 3, 4, 5, 6]

    # Simple EBIT profile: zero during construction and COD, then 10, 10, 10, 10, 10
    ebit = [0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    depreciation = [0.0] * len(ebit)

    scenario = TaxScenario(
        corporate_rate=0.3,
        tax_holiday_years=3,
        tax_holiday_start_year=1,
        depreciation_method="straight_line",
        depreciation_years=10,
    )

    tax = calculate_tax_series(
        ebit=ebit,
        depreciation=depreciation,
        scenario=scenario,
        years=years,
    )

    assert len(tax) == len(ebit)

    # No tax in construction years and COD
    assert all(t == 0.0 for t in tax[:3])

    # First 3 operational years (1,2,3) are holiday => no tax
    idx_y1 = years.index(1)
    idx_y3 = years.index(3)
    assert all(t == 0.0 for t in tax[idx_y1 : idx_y3 + 1])

    # After holiday, tax should be positive
    idx_y4 = years.index(4)
    assert tax[idx_y4] > 0

    