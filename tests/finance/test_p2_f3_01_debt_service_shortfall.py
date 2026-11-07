"""P2-F3-01 (#1398): a debt-service shortfall is carried and disclosed, never clamped.

The equity waterfall used to compute ``cf_after_debt = max(0, cfads - service - wht)``, so
a year whose CFADS could not meet scheduled debt service cost equity nothing: the gap was
simply dropped. These tests pin the replacement treatment, in its fixed order:

1. a DSRA draw, up to the reserve balance;
2. cash the SPV already holds for the sponsor (lockup-trapped, then retained);
3. a sponsor cure, a negative equity cash flow in the shortfall year.

Every expected value is derived from the inputs inside the test. The conservation test is
the oracle a reintroduced clamp fails: with no taxes on distributions, every dollar of
CFADS less debt service must reach (or come from) equity over the schedule's life.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    build_equity_distribution_schedule,
    calculate_equity_distribution_from_pipeline,
)


def _rows(pairs: List[tuple[float, float]]) -> List[Dict[str, Any]]:
    return [
        {"year": i + 1, "cf_pre_debt": cf, "debt_service_total": ds}
        for i, (cf, ds) in enumerate(pairs)
    ]


def _schedule(pairs: List[tuple[float, float]], **cfg: Any) -> List[Dict[str, Any]]:
    config = EquityDistributionConfig(**cfg)
    return build_equity_distribution_schedule(
        annual_rows=_rows(pairs), debt_result={}, distribution_config=config
    )


def test_unreserved_shortfall_is_a_sponsor_cure() -> None:
    """With no reserve and no SPV cash, the whole gap is a negative equity cash flow."""
    cf, ds = 3.0e6, 5.0e6
    row = _schedule([(cf, ds)], min_dscr_threshold=0.0, min_reserve_months=0)[0]
    shortfall = ds - cf
    assert row["cf_after_debt_usd"] == pytest.approx(cf - ds)
    assert row["debt_service_shortfall_usd"] == pytest.approx(shortfall)
    assert row["dsra_draw_usd"] == 0.0
    assert row["spv_cash_applied_usd"] == 0.0
    assert row["sponsor_cure_usd"] == pytest.approx(shortfall)
    assert row["equity_distribution_usd"] == pytest.approx(-shortfall)


def test_dsra_is_drawn_before_the_sponsor_is_called() -> None:
    """A reserve built in year 1 meets the year-2 gap first; only the rest is a cure."""
    ds = 4.0e6
    months = 6
    reserve = ds * months / 12.0  # built in full from year-1 cash
    cf2 = ds - 3.0e6  # year-2 shortfall of 3.0M, larger than the 2.0M reserve
    schedule = _schedule(
        [(10.0e6, ds), (cf2, ds)],
        min_dscr_threshold=0.0,
        min_reserve_months=months,
    )
    assert schedule[0]["reserve_balance_usd"] == pytest.approx(reserve)
    year2 = schedule[1]
    shortfall = ds - cf2
    assert year2["debt_service_shortfall_usd"] == pytest.approx(shortfall)
    assert year2["dsra_draw_usd"] == pytest.approx(reserve)
    assert year2["sponsor_cure_usd"] == pytest.approx(shortfall - reserve)
    # No cash is left to rebuild the reserve in the shortfall year itself.
    assert year2["reserve_funded_usd"] == 0.0
    assert year2["reserve_balance_usd"] == pytest.approx(0.0)
    assert year2["equity_distribution_usd"] == pytest.approx(-(shortfall - reserve))


def test_small_shortfall_is_met_entirely_from_the_dsra() -> None:
    """A gap the reserve can cover costs the sponsor nothing new that year."""
    ds = 4.0e6
    reserve = ds * 6 / 12.0
    gap = 0.5e6
    # A third year keeps year 2 clear of the terminal reserve release.
    schedule = _schedule(
        [(10.0e6, ds), (ds - gap, ds), (10.0e6, ds)],
        min_dscr_threshold=0.0,
        min_reserve_months=6,
    )
    year2 = schedule[1]
    assert year2["dsra_draw_usd"] == pytest.approx(gap)
    assert year2["sponsor_cure_usd"] == 0.0
    assert year2["equity_distribution_usd"] == pytest.approx(0.0)
    assert year2["reserve_balance_usd"] == pytest.approx(reserve - gap)


def test_lockup_trapped_cash_is_applied_before_a_cure() -> None:
    """Cash trapped by an earlier lockup sits in the SPV and meets the gap before a cure."""
    ds = 5.0e6
    cf1 = ds * 1.1  # DSCR 1.10 < 1.30 covenant: year 1 locks, its surplus is trapped
    trapped = cf1 - ds
    cf2 = ds - 2.0 * trapped  # year-2 gap is twice the trapped cash
    schedule = _schedule(
        [(cf1, ds), (cf2, ds)],
        min_dscr_threshold=1.30,
        min_reserve_months=0,
    )
    assert schedule[0]["covenant_locked"] is True
    assert schedule[0]["retained_cash_usd"] == pytest.approx(trapped)
    year2 = schedule[1]
    assert year2["spv_cash_applied_usd"] == pytest.approx(trapped)
    assert year2["sponsor_cure_usd"] == pytest.approx(trapped)
    assert year2["equity_distribution_usd"] == pytest.approx(-trapped)
    # The trapped cash was spent on debt service, so nothing is left to release at the end.
    assert year2["terminal_release_usd"] == 0.0


def test_shortfall_conserves_cash_across_the_schedule() -> None:
    """Oracle: equity's total net cash equals total CFADS less total debt service.

    A clamp breaks this exactly by the clamped amount: the shortfall year contributes zero
    instead of its negative cash, so equity would receive more than the project generated.
    """
    pairs = [(10.0e6, 4.0e6), (1.0e6, 4.0e6), (2.5e6, 4.0e6), (9.0e6, 4.0e6)]
    schedule = _schedule(pairs, min_dscr_threshold=1.30, min_reserve_months=6)
    total_equity = sum(row["equity_distribution_usd"] for row in schedule)
    total_net_cash = sum(cf - ds for cf, ds in pairs)
    assert total_equity == pytest.approx(total_net_cash)
    total_shortfall = sum(max(0.0, ds - cf) for cf, ds in pairs)
    assert sum(row["debt_service_shortfall_usd"] for row in schedule) == pytest.approx(
        total_shortfall
    )
    funded = sum(
        row["dsra_draw_usd"] + row["spv_cash_applied_usd"] + row["sponsor_cure_usd"]
        for row in schedule
    )
    assert funded == pytest.approx(total_shortfall)


def test_covered_years_are_untouched() -> None:
    """A schedule with no shortfall reports zero on every new field."""
    schedule = _schedule([(10.0e6, 4.0e6)] * 3, min_dscr_threshold=1.30)
    for row in schedule:
        assert row["debt_service_shortfall_usd"] == 0.0
        assert row["dsra_draw_usd"] == 0.0
        assert row["spv_cash_applied_usd"] == 0.0
        assert row["sponsor_cure_usd"] == 0.0
        assert row["cf_after_debt_usd"] == pytest.approx(6.0e6)


def test_summary_discloses_the_shortfall() -> None:
    """The equity summary counts shortfall years and totals each funding source."""
    config = {
        "equity_distribution": {
            "scenario_name": "shortfall-case",
            "equity_investment_usd": 30.0e6,
            "min_dscr_threshold": 0.0,
            "min_reserve_months": 6,
        }
    }
    pairs = [(10.0e6, 4.0e6), (1.0e6, 4.0e6), (10.0e6, 4.0e6)]
    result = calculate_equity_distribution_from_pipeline(
        config=config, annual_rows=_rows(pairs), debt_result={}
    )
    summary = result["equity_summary"]
    rows = result["annual_distributions"]
    assert summary["debt_service_shortfall_years"] == 1
    assert summary["total_debt_service_shortfall_usd"] == pytest.approx(3.0e6)
    assert summary["total_dsra_draw_usd"] == pytest.approx(
        sum(r["dsra_draw_usd"] for r in rows)
    )
    assert summary["total_sponsor_cure_usd"] == pytest.approx(
        sum(r["sponsor_cure_usd"] for r in rows)
    )
    assert (
        summary["total_dsra_draw_usd"]
        + summary["total_spv_cash_applied_usd"]
        + summary["total_sponsor_cure_usd"]
    ) == pytest.approx(summary["total_debt_service_shortfall_usd"])
