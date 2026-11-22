"""The distribution lock-up also tests the refinanced balloon tranche (#1779).

Balloon service sits outside the scheduled DSCR (#1396), so a year that services only a
refinanced balloon tranche has no scheduled DSCR and the lock-up never tested it. Equity
was paid in years the tranche's own coverage was below the covenant, and the sponsor was
called for cash in the years after.

The lock-up now tests the tranche's published coverage (``debt_result.refinance
.coverage_by_period``) against the scenario's lock-up threshold, with the tolerance the
scheduled test uses, in each year the tranche is serviced. Cash a breach year traps meets
the next refinance shortfall before any sponsor call, and what is left is released by the
same cure as any trapped cash: the next year that is not locked.

``TEST-01`` oracles that did not originate in this change: the debt engine's published
tranche coverage and period map, and the same scenario run with its lock-up switched off
(``equity_distribution.min_dscr_threshold: 0``), which reproduces the behaviour before the
fix: the issue's figures for years 15 to 17.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import yaml

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    build_equity_distribution_schedule,
)

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
LEAN = SCENARIOS / "dutchbay_capex_sinohydro_lean_2025Q4.yaml"
EIA = SCENARIOS / "dutchbay_capex_eia_prudent_2025Q4.yaml"
LENDER = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"
REFINANCE_YEARS = (15, 16, 17)
TOL = 0.01


def _config(path: Path, lockup: Optional[float] = None) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    if lockup is not None:
        section = dict(data.get("equity_distribution") or {})
        section["min_dscr_threshold"] = lockup
        data["equity_distribution"] = section
    return data


def _run(path: Path, tmp: Path, lockup: Optional[float] = None) -> Dict[str, Any]:
    if lockup is None:
        return run_v14_pipeline(str(path))
    out = tmp / f"{path.stem}_lockup_{lockup}.yaml"
    out.write_text(yaml.safe_dump(_config(path, lockup), sort_keys=False), "utf-8")
    return run_v14_pipeline(str(out))


def _by_year(run: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    rows = run["equity_distribution"]["annual_distributions"]
    return {int(row["year"]): row for row in rows}


def _published_coverage(run: Dict[str, Any]) -> Dict[int, float]:
    """The debt engine's tranche coverage, keyed by the annual row's year."""
    debt = run["debt_result"]
    by_period = {
        int(item["period"]): float(item["coverage"])
        for item in debt["refinance"]["coverage_by_period"]
    }
    rows = run["equity_distribution"]["annual_distributions"]
    out = {}
    for index, mapping in enumerate(debt["annual_row_debt_period_map"]):
        period = int(mapping["debt_period"])
        if period in by_period:
            out[int(rows[index]["year"])] = by_period[period]
    return out


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Dict[str, Any]]:
    tmp = tmp_path_factory.mktemp("f9")
    return {
        "lean": _run(LEAN, tmp),
        "lean_off": _run(LEAN, tmp, lockup=0.0),
        "eia": _run(EIA, tmp),
        "eia_off": _run(EIA, tmp, lockup=0.0),
        "lean_090": _run(LEAN, tmp, lockup=0.90),
        "lender": _run(LENDER, tmp),
    }


# ── The tranche is tested, against the lock-up threshold ───────────────────────────


@pytest.mark.parametrize("name", ["lean", "eia", "lender"])
def test_each_row_carries_the_published_tranche_coverage(
    name: str, runs: Dict[str, Dict[str, Any]]
) -> None:
    run = runs[name]
    published = _published_coverage(run)
    assert sorted(published) == list(REFINANCE_YEARS)
    for year, row in _by_year(run).items():
        if year in published:
            assert row["refinance_coverage"] == pytest.approx(
                published[year], rel=0, abs=0
            )
        else:
            assert row["refinance_coverage"] is None
            assert row["refinance_tranche_locked"] is False


@pytest.mark.parametrize(
    ("name", "locked"),
    [
        # Covered 0.97x, 0.87x and 0.78x: every refinance year breaches 1.30x.
        ("lean", {15: True, 16: True, 17: True}),
        # Covered 1.45x and 1.32x in years 15 and 16 (the controls: they meet 1.30x),
        # then 1.18x. Before #1874 dropped revenue SSCL: 1.33x, 1.20x and 1.08x.
        ("eia", {15: False, 16: False, 17: True}),
        # Covered 0.42x, 0.37x and 0.33x.
        ("lender", {15: True, 16: True, 17: True}),
    ],
)
def test_a_refinance_year_below_the_lockup_threshold_is_locked(
    name: str, locked: Dict[int, bool], runs: Dict[str, Dict[str, Any]]
) -> None:
    run = runs[name]
    threshold = run["equity_distribution"]["equity_summary"]["min_dscr_threshold"]
    assert threshold == pytest.approx(1.30)
    rows = _by_year(run)
    for year, expected in locked.items():
        row = rows[year]
        # Balloon service is outside the scheduled DSCR, so only the tranche can lock.
        assert row["dscr"] is None
        assert (row["refinance_coverage"] < threshold) is expected
        assert row["refinance_tranche_locked"] is expected, year
        assert row["covenant_locked"] is expected, year


def test_the_tranche_is_tested_against_the_lockup_threshold_not_the_floor(
    runs: Dict[str, Dict[str, Any]],
) -> None:
    """A 0.90x lock-up locks years 16 and 17 (0.87x, 0.78x) but not year 15 (0.97x).

    The refinance coverage floor stays 1.30x, so a year locked at 0.97x would mean the
    floor, not the lock-up threshold, decided it. Until #1874 dropped revenue SSCL this
    case was the EIA-prudent variant at 1.10x; its year 17 now covers 1.18x, so no year
    falls between a lower threshold and the floor with one below it.
    """
    run = runs["lean_090"]
    assert run["debt_result"]["refinance"]["coverage_floor"] == pytest.approx(1.30)
    rows = _by_year(run)
    assert [rows[y]["covenant_locked"] for y in REFINANCE_YEARS] == [False, True, True]


def test_lockup_switched_off_reproduces_the_issue_figures(
    runs: Dict[str, Dict[str, Any]],
) -> None:
    """The control the issue's table was taken from: no lock-up, equity paid in breach.

    Re-pinned by #1874 (revenue SSCL dropped): the issue's figures were lean
    1,793,706 / -363,215 / -836,168 and EIA 2,713,499 / 625,373 / 244,359.
    """
    lean = _by_year(runs["lean_off"])
    eia = _by_year(runs["eia_off"])
    assert [round(lean[y]["equity_distribution_usd"]) for y in REFINANCE_YEARS] == [
        1_640_302,
        -638_455,
        -1_131_846,
    ]
    assert [round(eia[y]["equity_distribution_usd"]) for y in REFINANCE_YEARS] == [
        3_053_159,
        910_139,
        526_105,
    ]
    for rows in (lean, eia):
        assert not any(rows[y]["covenant_locked"] for y in REFINANCE_YEARS)


# ── Trapped cash meets later calls, and the rest is released on cure ───────────────


def test_trapped_cash_meets_the_later_refinance_shortfalls_before_a_sponsor_call(
    runs: Dict[str, Dict[str, Any]],
) -> None:
    on = _by_year(runs["lean"])
    off = _by_year(runs["lean_off"])
    trapped = on[15]["retained_cash_usd"]
    assert trapped > 0.0
    assert on[15]["equity_distribution_usd"] == 0.0
    for year in (16, 17):
        # Without the lock-up the sponsor met this shortfall; now year 15's cash does.
        call = -off[year]["equity_distribution_usd"]
        assert call > 0.0
        assert on[year]["spv_cash_applied_usd"] == pytest.approx(call, abs=TOL)
        assert on[year]["equity_distribution_usd"] == pytest.approx(0.0, abs=TOL)
        assert on[year]["sponsor_cure_usd"] == pytest.approx(0.0, abs=TOL)


def _pre_wht(row: Dict[str, Any]) -> float:
    return float(row["equity_distribution_usd"] + row["wht_on_dividends_usd"])


@pytest.mark.parametrize(
    ("name", "off_name"), [("lean", "lean_off"), ("eia", "eia_off")]
)
def test_what_is_left_is_released_in_the_first_year_not_locked(
    name: str, off_name: str, runs: Dict[str, Dict[str, Any]]
) -> None:
    on = _by_year(runs[name])
    off = _by_year(runs[off_name])
    left = sum(
        on[y]["retained_cash_usd"] - on[y]["spv_cash_applied_usd"]
        for y in REFINANCE_YEARS
        if on[y]["covenant_locked"]
    )
    assert left > 0.0
    assert on[18]["covenant_locked"] is False
    assert _pre_wht(on[18]) - _pre_wht(off[18]) == pytest.approx(left, abs=TOL)
    # Every later year is untouched.
    for year in on:
        if year > 18:
            assert on[year]["equity_distribution_usd"] == pytest.approx(
                off[year]["equity_distribution_usd"], abs=TOL
            )


def test_the_lender_case_still_calls_the_sponsor_in_its_refinance_years(
    runs: Dict[str, Dict[str, Any]],
) -> None:
    """Locked, but no trapped cash is left by year 15, so its calls stand (the issue's note)."""
    rows = _by_year(runs["lender"])
    for year in REFINANCE_YEARS:
        assert rows[year]["covenant_locked"] is True
        assert rows[year]["equity_distribution_usd"] < 0.0
        assert rows[year]["spv_cash_applied_usd"] == pytest.approx(0.0, abs=TOL)


# ── The schedule, on synthetic inputs ──────────────────────────────────────────────


def _schedule(
    coverage: Optional[float],
    treatment: str = "refinance",
    threshold: float = 1.30,
    balloon: float = 0.0,
) -> Dict[str, Any]:
    rows = [
        {
            "year": 1,
            "cfads_usd": 1_000_000.0,
            "debt_service_usd": 0.0,
            "balloon_resolution": balloon,
        }
    ]
    debt: Dict[str, Any] = {
        "balloon_treatment": treatment,
        "annual_row_debt_period_map": [{"annual_row_index": 0, "debt_period": 3}],
        "dscr_series": [None, None, None, None],
        "balloon_resolution": [0.0, 0.0, 0.0, 0.0],
        "debt_outstanding": [0.0, 0.0, 0.0, 0.0],
    }
    if coverage is not None:
        debt["refinance"] = {
            "coverage_by_period": [{"period": 3, "coverage": coverage}],
        }
    config = EquityDistributionConfig(
        min_dscr_threshold=threshold, min_reserve_months=0
    )
    (row,) = build_equity_distribution_schedule(
        annual_rows=rows, debt_result=copy.deepcopy(debt), distribution_config=config
    )
    return row


def test_coverage_at_the_threshold_meets_it() -> None:
    """The scheduled test's tolerance applies: a tranche sculpted to 1.30x is not a breach."""
    assert _schedule(1.30)["refinance_tranche_locked"] is False
    assert _schedule(1.30 - 1e-12)["refinance_tranche_locked"] is False
    assert _schedule(1.29)["refinance_tranche_locked"] is True


def test_no_published_coverage_and_a_zero_threshold_never_lock() -> None:
    assert _schedule(None)["refinance_tranche_locked"] is False
    # A zero threshold switches the lock-up off, even for a tranche the year cannot cover.
    assert _schedule(-0.5, threshold=0.0)["refinance_tranche_locked"] is False


@pytest.mark.parametrize(
    ("treatment", "paid"), [("refinance", -0.005), ("cash_sweep", 0.0)]
)
def test_the_sweep_rounding_allowance_stays_a_cash_sweep_rule(
    treatment: str, paid: float
) -> None:
    """A refinance shortfall of half a cent is a sponsor call, as it was before.

    Only a cash sweep is settled by the pipeline to USD 0.01, so only there is a shortfall
    that small the settlement's rounding rather than a cash call.
    """
    row = _schedule(2.0, treatment=treatment, balloon=1_000_000.005)
    assert row["equity_distribution_usd"] == pytest.approx(paid, abs=1e-9)


def _spend_order_schedule(balloon: float, treatment: str) -> list[Dict[str, Any]]:
    """Five years: year 1 pays out with a 50% holdback (retentions 50); years 2 and 3 are
    tranche-locked (year 2 traps its 40); year 3 pays the balloon from no CFADS."""
    coverage = {2: 1.0, 3: 1.0}
    cfads = [100.0, 40.0, 0.0, 0.0, 0.0]
    rows = [
        {
            "year": year,
            "cfads_usd": cfads[year - 1],
            "debt_service_usd": 0.0,
            "balloon_resolution": balloon if year == 3 else 0.0,
        }
        for year in range(1, 6)
    ]
    debt: Dict[str, Any] = {
        "balloon_treatment": treatment,
        "annual_row_debt_period_map": [
            {"annual_row_index": i, "debt_period": i + 3} for i in range(5)
        ],
        "dscr_series": [None] * 8,
        "balloon_resolution": [0.0] * 8,
        "debt_outstanding": [0.0] * 8,
        "refinance": {
            "coverage_by_period": [
                {"period": year + 2, "coverage": cov} for year, cov in coverage.items()
            ]
        },
    }
    config = EquityDistributionConfig(
        min_dscr_threshold=1.30, min_reserve_months=0, holdback_pct=50.0
    )
    return build_equity_distribution_schedule(
        annual_rows=rows, debt_result=debt, distribution_config=config
    )


def test_a_refinance_shortfall_takes_trapped_cash_then_retentions_then_the_sponsor() -> (
    None
):
    """The spend order on a refinance: lockup-trapped cash, then retentions, then a call.

    A shortfall of 60 takes the 40 trapped in year 2 first and then 20 of year 1's 50 of
    retentions, so nothing is left trapped for the cure in year 4 and the 30 of retentions
    left is released at the horizon. Retentions first would leave 30 trapped and release it
    in year 4. A shortfall of 120 takes all 90 and calls the sponsor for the other 30.
    """
    rows = _spend_order_schedule(60.0, "refinance")
    assert [r["covenant_locked"] for r in rows] == [False, True, True, False, False]
    assert rows[2]["spv_cash_applied_usd"] == pytest.approx(60.0, abs=1e-9)
    assert rows[2]["equity_distribution_usd"] == pytest.approx(0.0, abs=1e-9)
    assert rows[3]["equity_distribution_usd"] == pytest.approx(0.0, abs=1e-9)
    assert rows[4]["terminal_release_usd"] == pytest.approx(30.0, abs=1e-9)
    assert rows[4]["equity_distribution_usd"] == pytest.approx(30.0, abs=1e-9)

    rows = _spend_order_schedule(120.0, "refinance")
    assert rows[2]["spv_cash_applied_usd"] == pytest.approx(90.0, abs=1e-9)
    assert rows[2]["equity_distribution_usd"] == pytest.approx(-30.0, abs=1e-9)
    assert rows[4]["terminal_release_usd"] == pytest.approx(0.0, abs=1e-9)


def test_a_bullet_shortfall_is_still_a_sponsor_call() -> None:
    """Only a sweep and a refinance draw on SPV-held cash; a bullet still calls the sponsor."""
    rows = _spend_order_schedule(60.0, "bullet")
    assert rows[2]["spv_cash_applied_usd"] == pytest.approx(0.0, abs=1e-9)
    assert rows[2]["equity_distribution_usd"] == pytest.approx(-60.0, abs=1e-9)
