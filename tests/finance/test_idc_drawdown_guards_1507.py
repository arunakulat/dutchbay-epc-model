"""Regression tests for construction drawdown sum-to-1 and IDC period guards (#1507)."""

from __future__ import annotations

import pytest

from finance.debt_v14 import (
    apply_debt_layer,
    calculate_construction_drawdowns,
    calculate_idc,
)


def _base_config(
    *, construction_periods: int, schedule: list[float], draws: list[float]
) -> dict:
    return {
        "capex": {"usd_total": 1_000_000.0},
        "Financing_Terms": {
            "construction_periods": construction_periods,
            "construction_schedule": schedule,
            "debt_drawdown_pct": draws,
            "debt_ratio": 0.50,
            "tenor_years": 5,
            "rates": {"usd_nominal": 0.10},
            "mix": {"usd_commercial_min": 1.0},
        },
    }


def test_calculate_construction_drawdowns_refuses_non_unit_sum_or_short_draws() -> None:
    with pytest.raises(ValueError, match="sums to 0.800000"):
        calculate_construction_drawdowns(100.0, [40.0, 60.0], [0.4, 0.4])

    with pytest.raises(ValueError, match="has only 1 entry"):
        calculate_construction_drawdowns(100.0, [40.0, 60.0], [1.0])

    with pytest.raises(ValueError, match="sums to 0.500000"):
        calculate_construction_drawdowns(100.0, [50.0, 50.0], [0.25, 0.25])


def test_calculate_idc_refuses_construction_periods_exceeding_draw_schedule() -> None:
    drawn = calculate_construction_drawdowns(100.0, [40.0, 60.0], [0.5, 0.5])
    with pytest.raises(ValueError, match="exceeds debt_drawn_schedule length"):
        calculate_idc(drawn, 0.10, 3)

    idc_list, total = calculate_idc(drawn, 0.10, 2)
    assert idc_list == pytest.approx([5.0, 10.5])
    assert total == pytest.approx(15.5)


def test_apply_debt_layer_refuses_explicit_underdrawn_or_short_schedule() -> None:
    cfg_short_sched = _base_config(
        construction_periods=3, schedule=[40.0, 60.0], draws=[0.4, 0.4, 0.2]
    )
    with pytest.raises(ValueError, match="fewer than construction_periods = 3"):
        apply_debt_layer(cfg_short_sched, annual_rows=[])

    cfg_bad_sum = _base_config(
        construction_periods=2, schedule=[40.0, 60.0], draws=[0.4, 0.4]
    )
    with pytest.raises(ValueError, match="sums to 0.800000"):
        apply_debt_layer(cfg_bad_sum, annual_rows=[])

    cfg_valid = _base_config(
        construction_periods=3, schedule=[30.0, 30.0, 40.0], draws=[0.5, 0.5, 0.0]
    )
    res = apply_debt_layer(cfg_valid, annual_rows=[])
    assert res["total_idc_capitalized"] == pytest.approx(
        (0.5 * 500_000.0) * 0.10
        + ((500_000.0 + 25_000.0) * 0.10)
        + ((500_000.0 + 25_000.0 + 52_500.0) * 0.10)
    )


def test_refuses_negative_or_non_finite_drawdown_fractions() -> None:
    for bad_draws in ([-0.5, 1.5], [1.2, -0.2], [float("nan"), 1.0]):
        with pytest.raises(ValueError, match="finite non-negative"):
            calculate_construction_drawdowns(100.0, [50.0, 50.0], bad_draws)

        cfg_bad_neg = _base_config(
            construction_periods=2, schedule=[50.0, 50.0], draws=bad_draws
        )
        with pytest.raises(ValueError, match="finite non-negative"):
            apply_debt_layer(cfg_bad_neg, annual_rows=[])
