"""Monthly CFADS cascade, dolphin 1 (``finance.monthly_cascade_v14``).

What is asserted
----------------
* ``cashflow.monthly`` is opt-in, and every malformed value is refused, at call time and
  at v14 pre-flight, naming the config path;
* the calendar shape and day counts are rotated so operating month 1 is ``cod_month``;
* on the committed lender case, every line of every year adds back to the annual
  engine, on the project basis and on the levered coverage basis the facility is sized
  on (#1397);
* one month's CFADS reproduces from an independent hand-written cascade, so the module
  is checked against arithmetic it does not share;
* a seasonal shape gives seasonal CFADS: the low-energy month has the lowest CFADS;
* the reconciliation guard is a control, not decoration: break one line and it fires.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List

import pytest

from analytics.pipeline_v14_enhanced import _size_debt_on_levered_cfads
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance import monthly_cascade_v14 as mc
from finance.cashflow_v14 import build_annual_rows
from finance.monthly_cascade_v14 import (
    COVENANT_USE,
    LINE_BASIS,
    MONTHLY_KEY,
    MONTHS_PER_YEAR,
    RECONCILIATION_REL_TOLERANCE,
    MonthlySpec,
    build_monthly_cascade,
    operating_month_weights,
    resolve_monthly_spec,
)

LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"

# An illustrative calendar shape (January first) with a pronounced mid-year peak. It is
# a test fixture, not any site's resource.
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
def seasonal(lender_config: Dict[str, Any]) -> mc.MonthlyCascade:
    return build_monthly_cascade(
        _with_monthly(lender_config, {"cod_month": 7, "energy_shape": SHAPE})
    )


# --- configuration -------------------------------------------------------------------


def test_absent_node_is_none_and_the_build_refuses(lender_config) -> None:
    assert resolve_monthly_spec(lender_config) is None
    assert resolve_monthly_spec(None) is None
    with pytest.raises(ValueError, match="opt-in"):
        build_monthly_cascade(copy.deepcopy(lender_config))


def test_empty_node_is_accepted_with_both_defaults_named() -> None:
    spec = resolve_monthly_spec({"cashflow": {"monthly": {}}})
    assert spec == MonthlySpec(cod_month=None, energy_shape=None)
    energy, time, calendar, assumptions = operating_month_weights(spec)
    assert energy == time == tuple(1.0 / 12 for _ in range(12))
    assert calendar == (None,) * 12
    assert any("cod_month not declared" in a for a in assumptions)
    assert any("energy_shape not declared" in a for a in assumptions)


@pytest.mark.parametrize(
    ("node", "match"),
    [
        (["cod_month", 7], "must be a mapping"),
        ({"cod_month": 7, "energy_profile": SHAPE}, "unknown key"),
        ({"cod_month": 0}, "1-12"),
        ({"cod_month": 13}, "1-12"),
        ({"cod_month": True}, "whole calendar month"),
        ({"cod_month": 7.0}, "whole calendar month"),
        ({"cod_month": "July"}, "whole calendar month"),
        ({"energy_shape": SHAPE}, "needs"),
        ({"cod_month": 7, "energy_shape": SHAPE[:11]}, "12 periods"),
        ({"cod_month": 7, "energy_shape": [1.0 / 12] * 11 + [0.2]}, "sum to"),
        ({"cod_month": 7, "energy_shape": [-0.1, 0.2] + [0.09] * 10}, ">= 0"),
        ({"cod_month": 7, "energy_shape": [math.nan] + [1.0 / 11] * 11}, "finite"),
    ],
)
def test_malformed_node_is_refused(node: Any, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        resolve_monthly_spec({"cashflow": {"monthly": node}})


def test_preflight_accepts_a_valid_node_and_refuses_a_bad_one(lender_config) -> None:
    good = _with_monthly(lender_config, {"cod_month": 7, "energy_shape": SHAPE})
    validate_config_for_v14(good, "<test>", ["cashflow", "debt"])
    bad = _with_monthly(lender_config, {"cod_month": 13})
    with pytest.raises(ConfigValidationError, match=MONTHLY_KEY):
        validate_config_for_v14(bad, "<test>", ["cashflow", "debt"])


def test_shape_and_days_rotate_to_the_cod_month() -> None:
    spec = MonthlySpec(cod_month=7, energy_shape=tuple(SHAPE))
    energy, time, calendar, assumptions = operating_month_weights(spec)
    assert calendar == (7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6)
    assert energy == tuple(SHAPE[6:] + SHAPE[:6])
    assert time[0] == 31 / 365 and time[7] == 28 / 365  # July, then February
    assert math.isclose(math.fsum(time), 1.0, abs_tol=1e-15)
    assert not any("cod_month" in a for a in assumptions)


# --- the cascade on the committed lender case ----------------------------------------


def _assert_reconciles(cascade: mc.MonthlyCascade) -> int:
    checked = 0
    assert len(cascade.rows) == MONTHS_PER_YEAR * len(cascade.annual_rows)
    for y, annual in enumerate(cascade.annual_rows):
        months = cascade.rows[y * 12 : (y + 1) * 12]
        assert [m["month_in_year"] for m in months] == list(range(1, 13))
        assert months[-1]["is_year_end"] == 1.0
        scale = max(abs(annual["revenue_lkr"]), 1.0)
        for line in LINE_BASIS:
            # A line the annual engine does not carry (the receivables change with
            # no lag set) must be zero in every month.
            expected = float(annual.get(line, 0.0))
            total = math.fsum(m[line] for m in months)
            tol = RECONCILIATION_REL_TOLERANCE * max(scale, abs(expected))
            assert abs(total - expected) <= tol, (y, line, total, expected)
            checked += 1
    return checked


def test_every_line_of_every_year_reconciles(seasonal) -> None:
    checked = _assert_reconciles(seasonal)
    assert checked == len(LINE_BASIS) * len(seasonal.annual_rows)
    assert checked >= 400  # 21 lines x 20 years on the lender case


def test_reconciles_on_the_levered_coverage_basis(lender_config) -> None:
    """The basis the facility is sized on (#1397): levered-tax rows."""
    _, sizing_rows, _ = _size_debt_on_levered_cfads(
        copy.deepcopy(lender_config),
        build_annual_rows=build_annual_rows,
        forbid_toy_fallback=False,
    )
    cascade = build_monthly_cascade(
        _with_monthly(lender_config, {"cod_month": 1, "energy_shape": SHAPE}),
        interest_expense_series=[r["interest_expense_lkr"] for r in sizing_rows],
    )
    for annual, sized in zip(cascade.annual_rows, sizing_rows, strict=True):
        assert annual["cfads_usd"] == sized["cfads_usd"]
    _assert_reconciles(cascade)


def test_one_month_reproduces_from_an_independent_cascade(
    lender_config, seasonal
) -> None:
    """Year 3, operating month 8 (February), rebuilt by hand from the annual inputs."""
    y, k = 2, 7
    a = seasonal.annual_rows[y]
    row = seasonal.rows[y * 12 + k]
    w_energy = SHAPE[1]  # February
    w_days = 28 / 365
    tariff = a["generation_revenue_lkr"] / a["net_kwh"]
    revenue = a["net_kwh"] * w_energy * tariff + a["bess_revenue_lkr"] * w_days
    stat_rate = a["total_statutory_deductions_lkr"] / a["revenue_lkr"]
    ebitda = (
        revenue * (1.0 - stat_rate) - (a["opex_lkr"] + a["senior_fee_lkr"]) * w_days
    )
    posttax = ebitda - a["tax_lkr"] * w_days
    assert a["posttax_cfads_lkr"] >= 0.0
    cfads_lkr = (
        posttax * (1.0 - a["risk_haircut_pct"])
        - a["bess_augmentation_capex_lkr"] * w_days
    )
    assert row["calendar_month"] == 2
    assert math.isclose(row["net_kwh"], a["net_kwh"] * w_energy, rel_tol=1e-12)
    assert math.isclose(row["revenue_lkr"], revenue, rel_tol=1e-12)
    assert math.isclose(row["cfads_final_lkr"], cfads_lkr, rel_tol=1e-9)
    assert math.isclose(row["cfads_usd"], cfads_lkr / a["fx_rate"], rel_tol=1e-9)


def test_seasonal_shape_gives_seasonal_cfads(seasonal) -> None:
    year1 = seasonal.rows[:12]
    lowest = min(year1, key=lambda r: r["cfads_usd"])
    highest = max(year1, key=lambda r: r["cfads_usd"])
    # The shape's low months are Feb-Apr at 5% and its peak is July at 13%.
    assert lowest["calendar_month"] in {2, 3, 4}
    assert highest["calendar_month"] == 7
    assert lowest["cfads_usd"] < seasonal.annual_rows[0]["cfads_usd"] / 12
    assert highest["cfads_usd"] > 2 * lowest["cfads_usd"]


def test_output_carries_its_basis_and_the_f5_hold(seasonal) -> None:
    assert seasonal.covenant_use == COVENANT_USE
    assert "F-5" in COVENANT_USE
    assert seasonal.line_basis["cfads_final_lkr"] == "computed"
    assert seasonal.line_basis["tax_lkr"] == "allocated"
    assert any("dolphin 2" in a for a in seasonal.assumptions)


def test_zero_weight_month_carries_no_residual(lender_config) -> None:
    shape: List[float] = [0.0] * 12
    shape[2], shape[5], shape[8] = 0.3, 0.3, 0.4  # March, June, September; rest zero
    cascade = build_monthly_cascade(
        _with_monthly(lender_config, {"cod_month": 1, "energy_shape": shape})
    )
    for row in cascade.rows:
        if shape[row["calendar_month"] - 1] == 0.0:
            assert row["net_kwh"] == 0.0
            assert row["generation_revenue_lkr"] == 0.0


# --- the guard is a control ----------------------------------------------------------


def test_reconciliation_guard_fires_when_a_line_is_broken(
    lender_config, monkeypatch
) -> None:
    real = mc._calculate_statutory_deductions

    def skewed(revenue, a, b, c):  # one extra rupee of levy per month
        out = dict(real(revenue, a, b, c))
        out["social_services_levy"] += 1.0
        out["total_statutory_deductions"] += 1.0
        return out

    monkeypatch.setattr(mc, "_calculate_statutory_deductions", skewed)
    with pytest.raises(ValueError, match="must reconcile"):
        build_monthly_cascade(_with_monthly(lender_config, {"cod_month": 7}))


def test_tariff_guard_fires_when_the_tariff_differs(lender_config, monkeypatch) -> None:
    monkeypatch.setattr(
        mc, "tariff_lkr_per_kwh_for_year", lambda base, idx, year: base * 1.01
    )
    with pytest.raises(ValueError, match="different tariff"):
        build_monthly_cascade(_with_monthly(lender_config, {"cod_month": 7}))


def test_a_directly_built_spec_with_a_shape_and_no_cod_month_is_refused() -> None:
    with pytest.raises(ValueError, match="cod_month"):
        operating_month_weights(MonthlySpec(cod_month=None, energy_shape=tuple(SHAPE)))


# --- lines the lender case leaves at zero (#1894 review notes) -----------------------
#
# The lender case carries no senior fee, BESS revenue, augmentation capex or FX hedge,
# and its statutory rates are zero, so a mis-spread of any of those lines adds back to
# the year and passes every test above. These fixtures switch each one on.

HYBRID_BESS = "scenarios/dutchbay_hybrid_bess_2025Q4.yaml"
BESS_ONLY = "scenarios/ceb_bess_10mw_capacity_charge.yaml"
_DAYS_FROM_APRIL = [30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28, 31]  # Apr..Mar


def _hybrid_with_every_line() -> tuple[mc.MonthlyCascade, List[float]]:
    """Hybrid BESS scenario with statutory rates, an FX hedge and a senior fee on."""
    cfg = copy.deepcopy(dict(load_scenario_config(HYBRID_BESS)))
    cfg["statutory"] = {
        **cfg["statutory"],
        "success_fee_pct": 0.01,
        "env_surcharge_pct": 0.0025,
        "social_services_levy_pct": 0.02,
    }
    cfg["fx"] = {**(cfg.get("fx") or {}), "hedge_ratio": 0.5, "spread_bps": 50}
    fee = [1.0e8 * (1.0 - i / 25.0) for i in range(20)]
    cascade = build_monthly_cascade(
        _with_monthly(cfg, {"cod_month": 4, "energy_shape": SHAPE}),
        senior_fee_lkr_series=fee,
    )
    return cascade, fee


@pytest.fixture(scope="module")
def hybrid() -> tuple[mc.MonthlyCascade, List[float]]:
    return _hybrid_with_every_line()


def test_fixture_exercises_the_lines_the_lender_case_leaves_at_zero(hybrid) -> None:
    cascade, _ = hybrid
    year8 = cascade.annual_rows[7]
    for line in (
        "bess_revenue_lkr",
        "generation_revenue_lkr",
        "tax_lkr",
        "senior_fee_lkr",
        "success_fee_lkr",
        "env_surcharge_lkr",
        "social_levy_lkr",
    ):
        assert year8[line] > 0.0, line
    # A hedge makes USD CFADS differ from LKR CFADS / spot.
    assert year8["cfads_usd"] != year8["cfads_final_lkr"] / year8["fx_rate"]
    _assert_reconciles(cascade)


def test_hand_cascade_with_tax_bess_fee_levies_and_hedge(hybrid) -> None:
    """Year 8, operating month 11 (February), rebuilt by hand."""
    cascade, fee = hybrid
    y, k = 7, 10
    a = cascade.annual_rows[y]
    row = cascade.rows[y * 12 + k]
    assert row["calendar_month"] == 2
    w_energy = SHAPE[1]
    w_days = _DAYS_FROM_APRIL[k] / 365
    tariff = a["generation_revenue_lkr"] / a["net_kwh"]
    gen = a["net_kwh"] * w_energy * tariff
    bess = a["bess_revenue_lkr"] * w_days  # a capacity charge accrues by days
    revenue = gen + bess
    levies = revenue * (0.01 + 0.0025 + 0.02)
    assert math.isclose(
        a["total_statutory_deductions_lkr"], a["revenue_lkr"] * 0.0325, rel_tol=1e-12
    )
    ebitda = revenue - levies - a["opex_lkr"] * w_days - fee[y] * w_days
    posttax = ebitda - a["tax_lkr"] * w_days  # tax is spread by days, not by energy
    assert a["posttax_cfads_lkr"] >= 0.0
    cfads_lkr = posttax * (1.0 - a["risk_haircut_pct"])
    usd_per_lkr = a["cfads_usd"] / a["cfads_final_lkr"]  # the year's hedged rate
    assert math.isclose(row["bess_revenue_lkr"], bess, rel_tol=1e-12)
    assert math.isclose(row["senior_fee_lkr"], fee[y] * w_days, rel_tol=1e-12)
    assert math.isclose(row["tax_lkr"], a["tax_lkr"] * w_days, rel_tol=1e-12)
    assert math.isclose(row["total_statutory_deductions_lkr"], levies, rel_tol=1e-12)
    assert math.isclose(row["cfads_final_lkr"], cfads_lkr, rel_tol=1e-9)
    assert math.isclose(row["cfads_usd"], cfads_lkr * usd_per_lkr, rel_tol=1e-9)


def test_augmentation_capex_is_deducted_by_days() -> None:
    cfg = copy.deepcopy(dict(load_scenario_config(BESS_ONLY)))
    # A seasonal energy shape, so a spread by energy instead of by days would show.
    cascade = build_monthly_cascade(
        _with_monthly(cfg, {"cod_month": 4, "energy_shape": SHAPE})
    )
    y = 9  # the scenario's augmentation year
    a = cascade.annual_rows[y]
    assert a["bess_augmentation_capex_lkr"] > 0.0
    for k in (0, 10):
        row = cascade.rows[y * 12 + k]
        w_days = _DAYS_FROM_APRIL[k] / 365
        aug = a["bess_augmentation_capex_lkr"] * w_days
        assert math.isclose(row["bess_augmentation_capex_lkr"], aug, rel_tol=1e-12)
        factor = 1.0 - a["risk_haircut_pct"]
        assert math.isclose(
            row["cfads_final_lkr"],
            row["posttax_cfads_lkr"] * factor - aug,
            rel_tol=1e-9,
        )


# --- the reconciliation guard's tolerance and reach ----------------------------------


def _skew(monkeypatch, *, year: int, line: str, amount) -> None:
    """Add ``amount(annual)`` to ``line`` in month 1 of operating ``year``."""
    real = mc._cascade_year

    def skewed(annual, **kwargs):
        months = real(annual, **kwargs)
        if int(annual["year"]) == year:
            months[0] = {**months[0], line: months[0][line] + amount(annual)}
        return months

    monkeypatch.setattr(mc, "_cascade_year", skewed)


def test_guard_fires_at_a_tenth_of_a_rupee_per_billion(
    lender_config, monkeypatch
) -> None:
    """A 1e-11 share of revenue is ten times the tolerance; a looser one would pass it."""
    _skew(
        monkeypatch,
        year=1,
        line="cfads_final_lkr",
        amount=lambda a: 1e-11 * a["revenue_lkr"],
    )
    with pytest.raises(ValueError, match="cfads_final_lkr"):
        build_monthly_cascade(_with_monthly(lender_config, {"cod_month": 7}))


def test_guard_scales_the_usd_tolerance_by_fx(lender_config, monkeypatch) -> None:
    """Ten times the USD tolerance, which an unscaled (LKR) tolerance would absorb."""
    _skew(
        monkeypatch,
        year=1,
        line="cfads_usd",
        amount=lambda a: 10
        * RECONCILIATION_REL_TOLERANCE
        * a["revenue_lkr"]
        / a["fx_rate"],
    )
    with pytest.raises(ValueError, match="cfads_usd"):
        build_monthly_cascade(_with_monthly(lender_config, {"cod_month": 7}))


def test_guard_checks_every_year_not_only_the_first(lender_config, monkeypatch) -> None:
    _skew(
        monkeypatch, year=17, line="tax_lkr", amount=lambda a: 1e-6 * a["revenue_lkr"]
    )
    with pytest.raises(ValueError, match="Operating year 17"):
        build_monthly_cascade(_with_monthly(lender_config, {"cod_month": 7}))


# --- where the rounding residual goes -------------------------------------------------


def test_residual_closes_on_the_last_positive_weight_month() -> None:
    """A value whose thirds do not add back exactly (see the accuracy note on
    ``finance.subannual_rows_v14.allocate_flow``, whose closing-residual rule ``_split``
    follows): the residual must land on a positive-weight month, never a zero one."""
    weights = [0.0, 0.0, 1 / 3, 0.0, 1 / 3, 0.0, 0.0, 0.0, 1 / 3, 0.0, 0.0, 0.0]
    value = 7_321_208.521842453
    parts = mc._split(value, weights)
    assert [p for p, w in zip(parts, weights, strict=True) if w == 0.0] == [0.0] * 9
    assert abs(math.fsum(parts) - value) <= math.ulp(value)


def test_residual_absorbs_a_shape_that_sums_just_short_of_one(lender_config) -> None:
    """A shape inside the 1e-9 sum tolerance still yields months that add back."""
    shape = list(SHAPE)
    shape[-1] -= 4e-10
    cascade = build_monthly_cascade(
        _with_monthly(lender_config, {"cod_month": 7, "energy_shape": shape})
    )
    for y, annual in enumerate(cascade.annual_rows):
        total = math.fsum(r["net_kwh"] for r in cascade.rows[y * 12 : (y + 1) * 12])
        assert abs(total - annual["net_kwh"]) <= 2 * math.ulp(annual["net_kwh"])
