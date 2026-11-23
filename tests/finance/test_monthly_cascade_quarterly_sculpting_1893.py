"""Quarterly debt sculpting on the monthly CFADS cascade (#1893, dolphin 3).

Covers:
1. Closed-form quarterly sculpting & DSCR identity across quarterly, semi-annual,
   annual, and cross-year-end instalment dates (with an independent oracle);
2. Responsiveness checks: seasonal CFADS shifts, true-length bridge vs 1.0-year
   interest, time-weighted senior fee accrual on falling balances, and month-level
   adverse risk haircut (`month_adverse`) when a negative month sits inside a
   positive year;
3. CESSPIT strict schema and cross-field refusals at pre-flight and call time;
4. Default-off invariance on ``dutchbay_lendercase_2025Q4.yaml``, opt-in end-to-end
   pipeline comparison, and explicit F-5 non-reliance disclaimers.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.debt.schedules import Tranche
from finance.debt_v14 import apply_debt_layer, plan_debt
from finance.monthly_cascade_v14 import (
    HAIRCUT_RULE_MONTH_ADVERSE,
    HAIRCUT_RULE_YEAR_SIGN,
    MONTHS_PER_YEAR,
    build_monthly_cascade,
    build_monthly_cascade_from_annual_rows,
    resolve_monthly_spec,
)
from finance.quarterly_sculpting_v14 import (
    COVENANT_USE,
    build_quarterly_sculpted_schedule,
    is_quarterly_sculpting_enabled,
    true_bridge_length_years,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"
EXPECTED_KPIS_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "finance" / "lendercase_expected_kpis.json"
)
SEASONAL_SHAPE = [
    0.06,
    0.05,
    0.05,
    0.05,
    0.10,
    0.12,
    0.13,
    0.12,
    0.10,
    0.08,
    0.07,
    0.07,
]
ALT_SEASONAL_SHAPE = [
    0.13,
    0.12,
    0.10,
    0.08,
    0.07,
    0.07,
    0.06,
    0.05,
    0.05,
    0.05,
    0.10,
    0.12,
]


def _with_monthly(config: Dict[str, Any], node: Any) -> Dict[str, Any]:
    cfg = copy.deepcopy(config)
    cashflow = dict(cfg.get("cashflow") or {})
    cashflow["monthly"] = node
    cfg["cashflow"] = cashflow
    return cfg


def _synthetic_config(
    *,
    tenor_years: int = 4,
    years_io: int = 0,
    debt_ratio: float = 0.40,
    target_dscr: float = 1.30,
    rate: float = 0.08,
    guarantee_fee: float = 0.01,
    pri_fee: float = 0.01,
    risk_haircut_pct: float = 0.0,
    cod_month: int | None = None,
    energy_shape: List[float] | None = None,
    instalment_quarters: List[int] | None = None,
    bridge_months: int | None = 0,
    amortization_style: str = "auto",
) -> Dict[str, Any]:
    monthly: Dict[str, Any] = {
        "quarterly_sculpting": {
            "enabled": True,
            **(
                {"instalment_quarters": instalment_quarters}
                if instalment_quarters is not None
                else {}
            ),
            **({"bridge_months": bridge_months} if bridge_months is not None else {}),
        }
    }
    if cod_month is not None:
        monthly["cod_month"] = cod_month
    if energy_shape is not None:
        monthly["energy_shape"] = energy_shape

    return {
        "project": {
            "name": "Quarterly Sculpt Test",
            "capacity_mw": 100.0,
            "capacity_factor": 0.40,
            "degradation": 0.0,
            "life_years": tenor_years + 2,
            "grid_loss_pct": 0.0,
            "jurisdiction": "Sri Lanka",
        },
        "tariff": {"lkr_per_kwh": 20.0, "tariff_type": "fixed"},
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.0},
        "capex": {"usd_total": 100_000_000.0},
        "opex": {"usd_per_year": 2_000_000.0, "escalation_pct": 0.0},
        "tax": {
            "corporate_tax_rate": 0.0,
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 5,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_multiple": 1.0,
            "loss_carryforward_years": 6,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 0,
            "wht_on_interest_to_nonresidents": 0.0,
            "wht_on_interest_enabled": False,
            "wht_gross_up": False,
            "interest_deductibility": False,
        },
        "statutory": {
            "success_fee_pct": 0.0,
            "env_surcharge_pct": 0.0,
            "social_services_levy_pct": 0.0,
        },
        "risk_adjustment": {"cfads_haircut_pct": risk_haircut_pct},
        "timeline": {"construction_years": 0, "ops_years": tenor_years + 2},
        "constraints": {"max_balloon_pct": 1.0},
        "Financing_Terms": {
            "construction_periods": 0,
            "debt_ratio": debt_ratio,
            "debt_sizing": "fixed",
            "tenor_years": tenor_years,
            "interest_only_years": years_io,
            "amortization_style": amortization_style,
            "target_dscr": target_dscr,
            "balloon_treatment": "bullet",
            "mix": {"usd_commercial_min": 1.0},
            "rates": {"usd_nominal": rate},
            "fees": {
                "guarantee_fee_pct_per_year": guarantee_fee,
                "pri_premium_pct_per_year": pri_fee,
            },
            "reserves": {"dsra_months": 6},
        },
        "cashflow": {"monthly": monthly},
    }


@pytest.fixture(scope="module")
def lender_config() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(LENDER_CASE)))


# --- 1. Closed-form quarterly sculpting & independent oracle ---------------------------


def test_closed_form_quarterly_sculpting_matches_independent_oracle() -> None:
    """Every binding sculpted quarter satisfies (CFADS_q - fee_q) / DS_q == target_dscr
    and matches an independent quarter-by-quarter calculation."""
    target_dscr = 1.35
    rate = 0.08
    fee_rate = 0.02
    cfg = _synthetic_config(
        tenor_years=4,
        years_io=0,
        debt_ratio=0.30,
        target_dscr=target_dscr,
        rate=rate,
        guarantee_fee=0.01,
        pri_fee=0.01,
        cod_month=1,
        energy_shape=SEASONAL_SHAPE,
        instalment_quarters=[1, 2, 3, 4],
        bridge_months=0,
    )
    rows = build_annual_rows(cfg)
    tranches = {"USD": Tranche("USD", rate, 30_000_000.0, 0)}
    qs = build_quarterly_sculpted_schedule(
        config=cfg,
        annual_rows=rows,
        tranches=tranches,
        tenor_years=4,
        years_io=0,
        target_dscr=target_dscr,
        senior_fee_rate=fee_rate,
    )

    assert qs.bridge_period is None
    assert len(qs.operating_quarters) == 16

    # Independent hand oracle over all 16 quarters
    cascade = build_monthly_cascade(cfg)
    bal = 30_000_000.0
    tw_fee_oracle = 0.0
    for y in range(4):
        for q in range(4):
            row = qs.operating_quarters[y * 4 + q]
            months = cascade.rows[y * 12 + q * 3 : y * 12 + (q + 1) * 3]
            dt_q = math.fsum(cascade.time_weights[q * 3 : (q + 1) * 3])
            cf_q = math.fsum(m["cfads_usd"] for m in months)
            fee_q = fee_rate * dt_q * bal
            tw_fee_oracle += fee_q
            int_q = bal * rate * dt_q
            target_ds = (cf_q - fee_q) / target_dscr
            princ_q = min(bal, max(0.0, target_ds - int_q))
            ds_q = int_q + princ_q
            bal = max(0.0, bal - princ_q)

            assert row["period_length_years"] == pytest.approx(dt_q, rel=1e-12)
            assert row["cfads_usd"] == pytest.approx(cf_q, rel=1e-12)
            assert row["senior_fee_usd"] == pytest.approx(fee_q, rel=1e-12)
            assert row["interest_paid_usd"] == pytest.approx(int_q, rel=1e-12)
            assert row["principal_paid_usd"] == pytest.approx(princ_q, rel=1e-12)
            assert row["debt_service_usd"] == pytest.approx(ds_q, rel=1e-12)
            assert row["closing_balance_usd"] == pytest.approx(bal, rel=1e-12)
            if bal > 0.0:
                assert row["dscr"] == pytest.approx(target_dscr, rel=1e-12)
                assert row["calculation_quarters"] == 1

    assert qs.time_weighted_senior_fee_total_usd == pytest.approx(
        tw_fee_oracle, rel=1e-12
    )
    assert qs.balloon_remaining_usd == pytest.approx(bal, rel=1e-12)


@pytest.mark.parametrize(
    ("instalment_quarters", "expected_calc_q"),
    [
        ([2, 4], 2),
        ([4], 4),
    ],
)
def test_non_quarterly_instalment_dates_accumulate_calculation_periods(
    instalment_quarters: List[int], expected_calc_q: int
) -> None:
    """Semi-annual [2, 4] and annual [4] instalments hold principal constant between
    dates, accumulate CFADS/fee/interest over the calculation period, and hit target_dscr.
    """
    target_dscr = 1.30
    cfg = _synthetic_config(
        tenor_years=3,
        debt_ratio=0.20,
        target_dscr=target_dscr,
        rate=0.06,
        guarantee_fee=0.01,
        pri_fee=0.005,
        cod_month=1,
        energy_shape=SEASONAL_SHAPE,
        instalment_quarters=instalment_quarters,
        bridge_months=0,
    )
    rows = build_annual_rows(cfg)
    tranches = {"USD": Tranche("USD", 0.06, 20_000_000.0, 0)}
    qs = build_quarterly_sculpted_schedule(
        config=cfg,
        annual_rows=rows,
        tranches=tranches,
        tenor_years=3,
        years_io=0,
        target_dscr=target_dscr,
        senior_fee_rate=0.015,
    )

    inst_set = set(instalment_quarters)
    for row in qs.operating_quarters:
        if row["quarter_in_year"] not in inst_set:
            assert not row["is_instalment"]
            assert row["debt_service_usd"] == 0.0
            assert row["interest_paid_usd"] == 0.0
            assert row["principal_paid_usd"] == 0.0
            assert row["dscr"] is None
            assert row["calculation_quarters"] is None
            assert row["closing_balance_usd"] == row["opening_balance_usd"]
        else:
            assert row["is_instalment"]
            assert row["calculation_quarters"] == expected_calc_q
            if row["closing_balance_usd"] > 0.0:
                assert row["dscr"] == pytest.approx(target_dscr, rel=1e-12)


def test_cross_year_end_instalment_schedule_carries_window_cleanly() -> None:
    """Instalments on [1, 3] carry Q4's CFADS, fee and accrued interest across year-end
    into the next year's Q1 (calculation_quarters == 2)."""
    cfg = _synthetic_config(
        tenor_years=3,
        debt_ratio=0.20,
        target_dscr=1.30,
        instalment_quarters=[1, 3],
        bridge_months=0,
    )
    rows = build_annual_rows(cfg)
    tranches = {"USD": Tranche("USD", 0.08, 20_000_000.0, 0)}
    qs = build_quarterly_sculpted_schedule(
        config=cfg,
        annual_rows=rows,
        tranches=tranches,
        tenor_years=3,
        years_io=0,
        target_dscr=1.30,
        senior_fee_rate=0.02,
    )
    # Year 1 Q1 covers only 1 quarter (since COD), while Year 2 Q1 covers Y1 Q4 + Y2 Q1.
    y1_q1 = qs.operating_quarters[0]
    y2_q1 = qs.operating_quarters[4]
    assert y1_q1["calculation_quarters"] == 1
    assert y2_q1["calculation_quarters"] == 2
    assert y2_q1["dscr"] == pytest.approx(1.30, rel=1e-12)


# --- 2. Responsiveness checks ----------------------------------------------------------


def test_seasonal_shift_moves_quarterly_debt_service_proportionally() -> None:
    """Shifting seasonal CFADS from H2 to H1 moves Q1/Q3 debt service proportionally
    while preserving the target_dscr identity on every binding quarter."""
    cfg_a = _synthetic_config(
        tenor_years=4,
        debt_ratio=0.25,
        target_dscr=1.30,
        guarantee_fee=0.0,
        pri_fee=0.0,
        cod_month=1,
        energy_shape=SEASONAL_SHAPE,
        bridge_months=0,
    )
    cfg_b = _synthetic_config(
        tenor_years=4,
        debt_ratio=0.25,
        target_dscr=1.30,
        guarantee_fee=0.0,
        pri_fee=0.0,
        cod_month=1,
        energy_shape=ALT_SEASONAL_SHAPE,
        bridge_months=0,
    )
    res_a = plan_debt(annual_rows=build_annual_rows(cfg_a), config=cfg_a)[
        "quarterly_sculpting"
    ]
    res_b = plan_debt(annual_rows=build_annual_rows(cfg_b), config=cfg_b)[
        "quarterly_sculpting"
    ]

    qa = res_a["operating_quarters"]
    qb = res_b["operating_quarters"]
    # Year 1: Q1 shape weight rises from 0.16 (SEASONAL_SHAPE) to 0.35 (ALT_SEASONAL_SHAPE)
    assert qb[0]["debt_service_usd"] > 2.0 * qa[0]["debt_service_usd"]
    # Year 1 Q3 shape weight falls from 0.35 to 0.16
    assert qb[2]["debt_service_usd"] < 0.5 * qa[2]["debt_service_usd"]
    # Both schedules keep DSCR pinned to target_dscr
    for row in qa + qb:
        if row["closing_balance_usd"] > 0.0:
            assert row["dscr"] == pytest.approx(1.30, rel=1e-12)


def test_true_length_bridge_scales_interest_by_bridge_duration() -> None:
    """True-length bridge charges bal * rate * dt_bridge rather than a full 1.0 year."""
    rate = 0.08
    principal = 30_000_000.0
    cfg_6m = _synthetic_config(
        tenor_years=4,
        years_io=1,
        debt_ratio=0.30,
        rate=rate,
        guarantee_fee=0.0,
        pri_fee=0.0,
        bridge_months=6,
    )
    cfg_3m = _synthetic_config(
        tenor_years=4,
        years_io=1,
        debt_ratio=0.30,
        rate=rate,
        guarantee_fee=0.0,
        pri_fee=0.0,
        bridge_months=3,
    )
    cfg_0m = _synthetic_config(
        tenor_years=4,
        years_io=1,
        debt_ratio=0.30,
        rate=rate,
        guarantee_fee=0.0,
        pri_fee=0.0,
        bridge_months=0,
    )
    cfg_cal = _synthetic_config(
        tenor_years=4,
        years_io=1,
        debt_ratio=0.30,
        rate=rate,
        guarantee_fee=0.0,
        pri_fee=0.0,
        cod_month=7,
        bridge_months=6,
    )

    d6 = plan_debt(annual_rows=build_annual_rows(cfg_6m), config=cfg_6m)
    d3 = plan_debt(annual_rows=build_annual_rows(cfg_3m), config=cfg_3m)
    d0 = plan_debt(annual_rows=build_annual_rows(cfg_0m), config=cfg_0m)
    dc = plan_debt(annual_rows=build_annual_rows(cfg_cal), config=cfg_cal)

    b6 = d6["quarterly_sculpting"]["bridge_period"]
    b3 = d3["quarterly_sculpting"]["bridge_period"]
    bc = dc["quarterly_sculpting"]["bridge_period"]

    full_year_interest = principal * rate
    assert b6["period_length_years"] == pytest.approx(0.5, rel=1e-12)
    assert b6["interest_paid_usd"] == pytest.approx(0.5 * full_year_interest, rel=1e-12)
    assert b6["cfads_usd"] == pytest.approx(
        0.5 * build_annual_rows(cfg_6m)[0]["cfads_usd"], rel=1e-12
    )

    assert b3["period_length_years"] == pytest.approx(0.25, rel=1e-12)
    assert b3["interest_paid_usd"] == pytest.approx(
        0.25 * full_year_interest, rel=1e-12
    )
    assert b3["interest_paid_usd"] == pytest.approx(
        0.5 * b6["interest_paid_usd"], rel=1e-12
    )

    # Calendar bridge before July is Jan..Jun = 181 days / 365
    assert bc["period_length_years"] == pytest.approx(181.0 / 365.0, rel=1e-12)
    assert bc["interest_paid_usd"] == pytest.approx(
        (181.0 / 365.0) * full_year_interest, rel=1e-12
    )

    # 0-month bridge omits the bridge completely
    assert d0["quarterly_sculpting"]["bridge_period"] is None
    assert d0["bridge_debt_period"] is None


def test_time_weighted_senior_fee_is_below_opening_balance_annual_fee() -> None:
    """Accruing senior fee quarterly on falling balances produces strictly less total
    fee than charging rate * opening_balance at the start of each year, and earlier
    repayment ([1,2,3,4] vs [2,4]) lowers the time-weighted balance further."""
    cfg_q = _synthetic_config(
        tenor_years=4,
        years_io=0,
        debt_ratio=0.35,
        guarantee_fee=0.01,
        pri_fee=0.01,
        instalment_quarters=[1, 2, 3, 4],
        bridge_months=0,
    )
    cfg_sa = _synthetic_config(
        tenor_years=4,
        years_io=0,
        debt_ratio=0.35,
        guarantee_fee=0.01,
        pri_fee=0.01,
        instalment_quarters=[2, 4],
        bridge_months=0,
    )
    dq = plan_debt(annual_rows=build_annual_rows(cfg_q), config=cfg_q)
    dsa = plan_debt(annual_rows=build_annual_rows(cfg_sa), config=cfg_sa)

    fee_rate = 0.02
    naive_opening_fee_q = fee_rate * sum(
        dq["debt_outstanding"][m["debt_period"]]
        for m in dq["annual_row_debt_period_map"][:4]
    )
    tw_fee_q = dq["quarterly_sculpting"]["time_weighted_senior_fee_total_usd"]
    tw_fee_sa = dsa["quarterly_sculpting"]["time_weighted_senior_fee_total_usd"]

    assert tw_fee_q < naive_opening_fee_q
    # Quarterly amortisation reduces balance in Q1 and Q3 before semi-annual [2, 4] does.
    assert tw_fee_q < tw_fee_sa


def test_negative_month_haircut_rule_month_adverse_vs_year_sign(
    lender_config: Dict[str, Any],
) -> None:
    """When a year is net positive but carries a negative month, ``month_adverse``
    stresses the negative month further negative (``posttax * (1 + h)``) rather than
    attenuating it toward zero (``posttax * (1 - h)``), and records the exact excess."""
    # Sparse shape puts zero generation in 9 months -> negative EBITDA/posttax in those months
    sparse_shape = [0.0] * 12
    sparse_shape[0], sparse_shape[5], sparse_shape[6] = 0.30, 0.35, 0.35

    cfg_year_sign = _with_monthly(
        lender_config,
        {
            "cod_month": 1,
            "energy_shape": sparse_shape,
            "risk_haircut_rule": HAIRCUT_RULE_YEAR_SIGN,
        },
    )
    cfg_month_adv = _with_monthly(
        lender_config,
        {
            "cod_month": 1,
            "energy_shape": sparse_shape,
            "risk_haircut_rule": HAIRCUT_RULE_MONTH_ADVERSE,
        },
    )
    c_year = build_monthly_cascade(copy.deepcopy(cfg_year_sign))
    c_adv = build_monthly_cascade(copy.deepcopy(cfg_month_adv))

    assert c_year.risk_haircut_rule == HAIRCUT_RULE_YEAR_SIGN
    assert c_adv.risk_haircut_rule == HAIRCUT_RULE_MONTH_ADVERSE
    assert c_adv.annual_rows[0]["posttax_cfads_lkr"] > 0.0
    h = c_adv.annual_rows[0]["risk_haircut_pct"]
    assert h > 0.0

    # February (index 1) has zero generation and positive fixed opex -> negative posttax
    feb_year = c_year.rows[1]
    feb_adv = c_adv.rows[1]
    assert feb_adv["posttax_cfads_lkr"] < 0.0
    assert feb_year["posttax_cfads_lkr"] == pytest.approx(
        feb_adv["posttax_cfads_lkr"], rel=1e-12
    )
    # Year-sign rule attenuates negative month toward zero; month-adverse stresses downward
    assert feb_year["cfads_final_lkr"] == pytest.approx(
        feb_year["posttax_cfads_lkr"] * (1.0 - h), rel=1e-12
    )
    assert feb_adv["cfads_final_lkr"] == pytest.approx(
        feb_adv["posttax_cfads_lkr"] * (1.0 + h), rel=1e-12
    )
    assert feb_adv["cfads_final_lkr"] < feb_year["cfads_final_lkr"]

    # Exact mixed-sign excess equals 2 * h * sum(-posttax_m for posttax_m < 0)
    neg_sum = math.fsum(
        -r["posttax_cfads_lkr"] for r in c_adv.rows[:12] if r["posttax_cfads_lkr"] < 0.0
    )
    assert c_adv.mixed_sign_haircut_excess_lkr[0] == pytest.approx(
        2.0 * h * neg_sum, rel=1e-12
    )
    assert math.fsum(r["cfads_final_lkr"] for r in c_adv.rows[:12]) == pytest.approx(
        c_adv.annual_rows[0]["cfads_final_lkr"]
        - c_adv.mixed_sign_haircut_excess_lkr[0],
        rel=1e-12,
    )


# --- 3. CESSPIT strict schema & cross-field refusals -----------------------------------


@pytest.mark.parametrize(
    ("node", "match"),
    [
        ({"risk_haircut_rule": 123}, "risk_haircut_rule"),
        ({"risk_haircut_rule": "flat"}, "risk_haircut_rule"),
        ({"quarterly_sculpting": True}, "must be a mapping"),
        ({"quarterly_sculpting": {"enabled": True, "unknown_key": 1}}, "unknown key"),
        ({"quarterly_sculpting": {"enabled": "yes"}}, "boolean"),
        ({"quarterly_sculpting": {"enabled": 1}}, "boolean"),
        (
            {"quarterly_sculpting": {"enabled": True, "instalment_quarters": []}},
            "non-empty",
        ),
        ({"quarterly_sculpting": {"enabled": True, "instalment_quarters": [0]}}, "1-4"),
        ({"quarterly_sculpting": {"enabled": True, "instalment_quarters": [5]}}, "1-4"),
        (
            {"quarterly_sculpting": {"enabled": True, "instalment_quarters": [True]}},
            "whole quarters",
        ),
        (
            {"quarterly_sculpting": {"enabled": True, "instalment_quarters": [2, 2]}},
            "strictly ascending",
        ),
        (
            {"quarterly_sculpting": {"enabled": True, "instalment_quarters": [4, 2]}},
            "strictly ascending",
        ),
        ({"quarterly_sculpting": {"enabled": True, "bridge_months": -1}}, "0-11"),
        ({"quarterly_sculpting": {"enabled": True, "bridge_months": 12}}, "0-11"),
        (
            {"quarterly_sculpting": {"enabled": True, "bridge_months": 6.0}},
            "whole number",
        ),
        (
            {"quarterly_sculpting": {"enabled": True, "bridge_months": True}},
            "whole number",
        ),
        (
            {
                "risk_haircut_rule": "year_sign",
                "quarterly_sculpting": {"enabled": True},
            },
            "month_adverse",
        ),
    ],
)
def test_cesspit_refuses_malformed_dolphin3_config(
    lender_config: Dict[str, Any], node: Any, match: str
) -> None:
    cfg = _with_monthly(lender_config, node)
    with pytest.raises(ValueError, match=match):
        resolve_monthly_spec(cfg)
    with pytest.raises(ConfigValidationError, match=match):
        validate_config_for_v14(cfg, "<test>", ["cashflow", "debt"])


def test_refuses_annuity_style_with_quarterly_sculpting() -> None:
    cfg = _synthetic_config(amortization_style="annuity")
    rows = build_annual_rows(cfg)
    with pytest.raises(ValueError, match="sculpted amortization_style"):
        apply_debt_layer(params=cfg, annual_rows=rows)


def test_refuses_double_counted_senior_fee_in_quarterly_sculpting() -> None:
    cfg = _synthetic_config(guarantee_fee=0.01, pri_fee=0.0)
    rows = build_annual_rows(cfg, senior_fee_lkr_series=[100_000.0] * 6)
    tranches = {"USD": Tranche("USD", 0.08, 10_000_000.0, 0)}
    with pytest.raises(ValueError, match="double-count"):
        build_quarterly_sculpted_schedule(
            config=cfg,
            annual_rows=rows,
            tranches=tranches,
            tenor_years=4,
            years_io=0,
            target_dscr=1.30,
            senior_fee_rate=0.01,
        )


def test_refuses_stub_annual_rows_in_cascade_from_annual_rows(
    lender_config: Dict[str, Any],
) -> None:
    cfg = _with_monthly(lender_config, {"cod_month": 7})
    with pytest.raises(ValueError, match="missing required monthly-cascade field"):
        build_monthly_cascade_from_annual_rows(cfg, [{"year": 1, "cfads_usd": 100.0}])


# --- 4. Default-off invariance, lendercase opt-in & F-5 non-reliance -------------------


def test_default_off_leaves_lendercase_unchanged_and_opt_in_runs_end_to_end(
    lender_config: Dict[str, Any],
) -> None:
    """Committed lender case has quarterly sculpting OFF and reproduces golden KPIs.
    Opting in runs through the full v14 pipeline with explicit F-5 non-reliance."""
    assert is_quarterly_sculpting_enabled(lender_config) is False
    expected = json.loads(EXPECTED_KPIS_PATH.read_text(encoding="utf-8"))
    base = run_v14_pipeline(config=copy.deepcopy(lender_config))
    assert "quarterly_sculpting" not in base["debt_result"]
    assert base["kpis"]["min_dscr"] == pytest.approx(expected["min_dscr"], abs=1e-4)
    assert base["kpis"]["max_debt_usd"] > 0.0

    # Opt-in seasonal quarterly sculpting on the lender case
    opt_cfg = _with_monthly(
        lender_config,
        {
            "cod_month": 7,
            "energy_shape": SEASONAL_SHAPE,
            "quarterly_sculpting": {"enabled": True},
        },
    )
    assert is_quarterly_sculpting_enabled(opt_cfg) is True
    opt = run_v14_pipeline(config=opt_cfg)
    qs = opt["debt_result"]["quarterly_sculpting"]

    # F-5 non-reliance stays explicit
    assert qs["covenant_use"] == COVENANT_USE
    assert "Not a lender representation" in qs["covenant_use"]
    assert "F-5 stays in force" in qs["covenant_use"]

    # Quarterly DSCR beside annual covenant dscr_by_year
    assert qs["risk_haircut_rule"] == HAIRCUT_RULE_MONTH_ADVERSE
    assert qs["quarterly_dscr_min"] >= 1.30 - 1e-6
    assert qs["annual_covenant_dscr_min"] >= 1.30 - 1e-6
    assert opt["kpis"]["min_dscr"] >= 1.30 - 1e-6
    assert (
        qs["annual_covenant_dscr_by_year"].keys()
        == opt["debt_result"]["dscr_by_year"].keys()
    )
    for y_key, qs_val in qs["annual_covenant_dscr_by_year"].items():
        opt_val = opt["debt_result"]["dscr_by_year"][y_key]
        if qs_val is None:
            assert opt_val is None
        else:
            assert qs_val == pytest.approx(opt_val, rel=1e-12)
    assert qs["bridge_period"]["period_length_years"] == pytest.approx(
        181.0 / 365.0, rel=1e-12
    )
    assert qs["time_weighted_senior_fee_total_usd"] == pytest.approx(
        sum(opt["debt_result"]["senior_fee_usd"][:18]), rel=1e-12
    )

    # Verify true_bridge_length_years directly when cod_month is None
    spec_no_cod = resolve_monthly_spec(
        {"cashflow": {"monthly": {"quarterly_sculpting": {"enabled": True}}}}
    )
    assert spec_no_cod is not None
    assert true_bridge_length_years(spec_no_cod, 6) == pytest.approx(0.5, rel=1e-12)
    assert true_bridge_length_years(spec_no_cod, 0) == 0.0
