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
            total = math.fsum(m[line] for m in months)
            tol = RECONCILIATION_REL_TOLERANCE * max(scale, abs(annual[line]))
            assert abs(total - annual[line]) <= tol, (y, line, total, annual[line])
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
