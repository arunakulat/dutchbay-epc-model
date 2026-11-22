"""Offtaker receivables lag, dolphin 2 of #1893 (``cashflow.monthly.receivable_days``).

What is asserted
----------------
* the key is opt-in: absent or 0, every annual row builder returns the same rows, byte
  for byte, with no ``receivables_change_lkr`` key;
* a malformed lag is refused, at call time and at v14 pre-flight;
* with a lag, the annual change is the movement in the month-end balance, the year-1
  build is the trailing lag of the first year's last-month revenue, and the changes
  telescope to zero over the life because the last balance is collected;
* the lag is a working-capital movement: EBITDA and tax do not move, CFADS moves by
  exactly the change, and USD CFADS moves by the change at the year's own factor;
* the three annual builders agree, and the monthly cascade reconciles to them.

The lender case is used as an input fixture with the lag switched on here; its
committed YAML declares no lag.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.cashflow_v14 import (
    build_annual_cfads,
    build_annual_rows,
    build_annual_rows_efficient,
)
from finance.monthly_cascade_v14 import (
    LINE_BASIS,
    MONTHS_PER_YEAR,
    RECEIVABLES_KEY,
    RECONCILIATION_REL_TOLERANCE,
    build_monthly_cascade,
    operating_month_weights,
    receivables_balances,
    resolve_monthly_spec,
)

LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"
SHAPE = [0.06, 0.05, 0.05, 0.05, 0.10, 0.12, 0.13, 0.12, 0.10, 0.08, 0.07, 0.07]


def _with_monthly(config: Dict[str, Any], node: Any) -> Dict[str, Any]:
    cfg = copy.deepcopy(config)
    cashflow = dict(cfg.get("cashflow") or {})
    cashflow["monthly"] = node
    cfg["cashflow"] = cashflow
    return cfg


@pytest.fixture(scope="module")
def lender_config() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(LENDER_CASE)))


@pytest.fixture(scope="module")
def lagged_config(lender_config: Dict[str, Any]) -> Dict[str, Any]:
    return _with_monthly(
        lender_config, {"cod_month": 1, "energy_shape": SHAPE, "receivable_days": 30}
    )


@pytest.fixture(scope="module")
def base_rows(lender_config: Dict[str, Any]) -> List[Dict[str, float]]:
    return build_annual_rows(copy.deepcopy(lender_config))


@pytest.fixture(scope="module")
def lagged_rows(lagged_config: Dict[str, Any]) -> List[Dict[str, float]]:
    return build_annual_rows(copy.deepcopy(lagged_config))


# --- opt-in and validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "node", [None, {"cod_month": 1, "energy_shape": SHAPE}, {"receivable_days": 0}]
)
def test_no_lag_leaves_every_builder_byte_identical(
    lender_config, base_rows, node
) -> None:
    cfg = lender_config if node is None else _with_monthly(lender_config, node)
    assert build_annual_rows(copy.deepcopy(cfg)) == base_rows
    assert build_annual_rows_efficient(
        copy.deepcopy(cfg)
    ) == build_annual_rows_efficient(copy.deepcopy(lender_config))
    assert build_annual_cfads(copy.deepcopy(cfg)) == build_annual_cfads(
        copy.deepcopy(lender_config)
    )
    assert all(RECEIVABLES_KEY not in row for row in base_rows)


@pytest.mark.parametrize(
    "days, match",
    [
        (True, "whole number"),
        (30.0, "whole number"),
        ("30", "whole number"),
        (-1, "0-365"),
        (366, "0-365"),
    ],
)
def test_malformed_lag_is_refused(lender_config, days, match) -> None:
    cfg = _with_monthly(lender_config, {"receivable_days": days})
    with pytest.raises(ValueError, match=match):
        resolve_monthly_spec(cfg)
    with pytest.raises(ConfigValidationError, match="receivable_days"):
        validate_config_for_v14(cfg, "<test>", ["cashflow", "debt"])


# --- the balance and its changes -------------------------------------------------------


def test_changes_are_the_balance_movements_and_telescope_to_zero(
    lagged_config, lagged_rows
) -> None:
    spec = resolve_monthly_spec(lagged_config)
    balances = receivables_balances(lagged_rows, spec)
    assert len(balances) == MONTHS_PER_YEAR * len(lagged_rows)
    year_end = [
        balances[(y + 1) * MONTHS_PER_YEAR - 1] for y in range(len(lagged_rows))
    ]
    previous = 0.0
    for row, closing in zip(lagged_rows, year_end, strict=True):
        assert row[RECEIVABLES_KEY] == pytest.approx(closing - previous, rel=1e-12)
        previous = closing
    assert year_end[-1] == 0.0
    total = math.fsum(row[RECEIVABLES_KEY] for row in lagged_rows)
    scale = abs(lagged_rows[0][RECEIVABLES_KEY])
    assert abs(total) <= 1e-9 * scale
    # The build is cash tied up at the start, released at the end.
    assert lagged_rows[0][RECEIVABLES_KEY] > 0.0
    assert lagged_rows[-1][RECEIVABLES_KEY] < 0.0


def test_year_one_build_is_thirty_days_of_the_last_months_revenue(
    lagged_config, lagged_rows
) -> None:
    """Independent arithmetic: December (31 days) carries 30/31 of its revenue unpaid."""
    spec = resolve_monthly_spec(lagged_config)
    energy_w, time_w, _, _ = operating_month_weights(spec)
    first = lagged_rows[0]
    december = (
        first["generation_revenue_lkr"] * energy_w[11]
        + first["bess_revenue_lkr"] * time_w[11]
    )
    assert time_w[11] * 365.0 == pytest.approx(31.0)
    assert first[RECEIVABLES_KEY] == pytest.approx(december * 30.0 / 31.0, rel=1e-12)


def test_a_lag_longer_than_a_month_walks_back_into_earlier_months(
    lender_config, base_rows
) -> None:
    cfg = _with_monthly(lender_config, {"cod_month": 1, "receivable_days": 45})
    spec = resolve_monthly_spec(cfg)
    energy_w, time_w, _, _ = operating_month_weights(spec)
    first = base_rows[0]

    def month(k: int) -> float:
        return (
            first["generation_revenue_lkr"] * energy_w[k]
            + first["bess_revenue_lkr"] * time_w[k]
        )

    # 31 days of December plus 14 of November's 30.
    want = month(11) + month(10) * 14.0 / 30.0
    assert receivables_balances(base_rows, spec)[11] == pytest.approx(want, rel=1e-12)


def test_nothing_is_owed_before_cod(lender_config, base_rows) -> None:
    cfg = _with_monthly(lender_config, {"cod_month": 1, "receivable_days": 365})
    balances = receivables_balances(base_rows, resolve_monthly_spec(cfg))
    first = base_rows[0]
    year_one = first["generation_revenue_lkr"] + first["bess_revenue_lkr"]
    # At the end of month 1 only January has been invoiced.
    assert balances[0] < year_one / 6.0
    assert balances[11] == pytest.approx(year_one, rel=1e-12)


# --- where the change lands ------------------------------------------------------------


def test_lag_moves_cfads_by_the_change_and_nothing_above_it(
    base_rows, lagged_rows
) -> None:
    for base, lag in zip(base_rows, lagged_rows, strict=True):
        for key in ("revenue_lkr", "ebitda_lkr", "taxable_income_lkr", "tax_lkr"):
            assert lag[key] == base[key], key
        change = lag[RECEIVABLES_KEY]
        assert lag["cfads_final_lkr"] == pytest.approx(
            base["cfads_final_lkr"] - change, rel=1e-12, abs=1e-6
        )
        assert lag["cfads_risk_adjusted_lkr"] == lag["cfads_final_lkr"]
        # No hedge on the lender case, so the USD view is the change at spot.
        assert lag["cfads_usd"] == pytest.approx(
            base["cfads_usd"] - change / base["fx_rate"], rel=1e-12, abs=1e-9
        )


def test_the_three_builders_agree(lagged_config, lagged_rows) -> None:
    efficient = build_annual_rows_efficient(copy.deepcopy(lagged_config))
    cfads = build_annual_cfads(copy.deepcopy(lagged_config))
    for row, fast, value in zip(lagged_rows, efficient, cfads, strict=True):
        assert fast[RECEIVABLES_KEY] == pytest.approx(row[RECEIVABLES_KEY], rel=1e-12)
        assert fast["cfads_final_lkr"] == pytest.approx(
            row["cfads_final_lkr"], rel=1e-12
        )
        assert value == pytest.approx(row["cfads_final_lkr"], rel=1e-12)


def test_monthly_cascade_reconciles_with_the_lag(lagged_config, lagged_rows) -> None:
    cascade = build_monthly_cascade(copy.deepcopy(lagged_config))
    for y, annual in enumerate(cascade.annual_rows):
        months = cascade.rows[y * MONTHS_PER_YEAR : (y + 1) * MONTHS_PER_YEAR]
        scale = max(abs(annual["revenue_lkr"]), 1.0)
        for line in LINE_BASIS:
            total = math.fsum(m[line] for m in months)
            tol = RECONCILIATION_REL_TOLERANCE * max(scale, abs(annual[line]))
            assert abs(total - annual[line]) <= tol, (y, line)
    # Year 1: the whole build sits in the months, and the first month's CFADS carries
    # its own month's build, not an even twelfth of the year's.
    first = cascade.rows[:MONTHS_PER_YEAR]
    assert first[0][RECEIVABLES_KEY] > first[1][RECEIVABLES_KEY]
    assert first[0][RECEIVABLES_KEY] > lagged_rows[0][RECEIVABLES_KEY] / 2.0


def test_quarterly_event_calendar_keeps_the_receivables_change(lagged_rows) -> None:
    """On a quarterly grid the calendar re-derives CFADS; the change must stay in it."""
    from finance.event_calendar_v14 import apply_event_calendar, resolve_event_calendar
    from finance.period_grid_v14 import resolve_period_grid
    from finance.subannual_rows_v14 import build_subannual_rows

    grid = resolve_period_grid({"cashflow": {"resolution": "quarterly"}})
    calendar = resolve_event_calendar({"cashflow": {"resolution": "quarterly"}}, grid)
    assert calendar is not None
    placed = apply_event_calendar(
        build_subannual_rows(lagged_rows, grid), lagged_rows, calendar
    )
    first_year = placed[:4]
    for row in first_year[:-1]:  # the closing quarter carries the rounding residual
        want = (
            row["posttax_cfads_lkr"]
            - row["risk_haircut_amount_lkr"]
            - row["bess_augmentation_capex_lkr"]
            - row[RECEIVABLES_KEY]
        )
        assert row["cfads_final_lkr"] == pytest.approx(want, rel=1e-12, abs=1e-6)
    assert math.fsum(r["cfads_final_lkr"] for r in first_year) == pytest.approx(
        lagged_rows[0]["cfads_final_lkr"], rel=1e-12
    )
