"""Contract tests for the within-year event calendar (:mod:`finance.event_calendar_v14`).

A3 dolphin (b) of #1395. A2 spreads every annual flow by one within-year profile, which
smooths a discrete payment's dip away. The calendar places a declared item on its
declared sub-periods instead. Four properties carry the weight here:

1. Default-off. No committed scenario declares a calendar, an absent calendar resolves
   to ``None``, and pre-flight passes the shape every scenario ships. The annual canon
   cannot move by shipping the module.
2. The dip is real. On the live committed BESS case, augmentation placed in Q1 of its
   year lands there in full, and that quarter's CFADS falls by the difference between
   the placed and the profile-spread payment.
3. Reconciliation survives the move. Every placed and re-derived flow still sums back to
   the annual engine's figure within A2's 1-ULP bound, every untouched key is
   byte-identical to A2's output, and the per-period CFADS identities hold.
4. Dates are declared, never assumed. A calendar on the annual grid, an unknown or
   unmodelled kind (``working_capital``), and malformed periods or weights are refused,
   at the resolver and through the full v14 pre-flight.
"""

from __future__ import annotations

import glob
import math
from typing import Any, Dict, List

import pytest
import yaml

from analytics.config_schema import get_required_fields
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.event_calendar_v14 import (
    EVENT_CALENDAR_KEY,
    EVENT_KINDS,
    EventCalendar,
    apply_event_calendar,
    build_bridge_service_events,
    resolve_event_calendar,
)
from finance.period_grid_v14 import ANNUAL, PeriodGrid, aggregate_flows_to_annual
from finance.subannual_rows_v14 import (
    FLOW_KEYS,
    RECONCILIATION_ULP_TOLERANCE,
    build_subannual_rows,
)

QUARTERLY = PeriodGrid(resolution="quarterly", periods_per_year=4)
SEASONAL = (0.35, 0.15, 0.15, 0.35)

BESS_CASE = "scenarios/ceb_bess_10mw_capacity_charge.yaml"
LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"

#: Every key the calendar writes. Any other key must come through A2 unchanged.
WRITTEN_KEYS = frozenset(
    {
        "tax_lkr",
        "bess_augmentation_capex_lkr",
        "posttax_cfads_lkr",
        "cfads_final_lkr",
        "cfads_risk_adjusted_lkr",
        "cfads_usd",
    }
)


def _calendar_config(calendar: Any) -> Dict[str, Any]:
    return {"cashflow": {"resolution": "quarterly", "event_calendar": calendar}}


def _resolve(calendar: Any, grid: PeriodGrid = QUARTERLY) -> EventCalendar | None:
    return resolve_event_calendar(_calendar_config(calendar), grid)


def _annual_rows(path: str) -> List[Dict[str, Any]]:
    from finance.cashflow_v14 import build_annual_rows

    with open(path) as handle:
        return build_annual_rows(yaml.safe_load(handle))


@pytest.fixture(scope="module")
def bess_annual_rows() -> List[Dict[str, Any]]:
    return _annual_rows(BESS_CASE)


@pytest.fixture(scope="module")
def lender_annual_rows() -> List[Dict[str, Any]]:
    return _annual_rows(LENDER_CASE)


def _assert_reconciles(
    rows: List[Dict[str, float]], annual: List[Dict[str, Any]], grid: PeriodGrid
) -> None:
    for key in sorted(FLOW_KEYS & set(annual[0])):
        reaggregated = aggregate_flows_to_annual([row[key] for row in rows], grid)
        for year_index, (got, row) in enumerate(zip(reaggregated, annual, strict=True)):
            want = float(row[key])
            slack = RECONCILIATION_ULP_TOLERANCE * math.ulp(want)
            assert (
                abs(got - want) <= slack
            ), f"{key} year {year_index + 1}: re-aggregated {got!r} vs annual {want!r}"


def _assert_identities(rows: List[Dict[str, float]], per_year: int) -> None:
    """The CFADS identities hold on every non-closing period.

    The closing period carries the year's residual, so it is held to reconciliation
    instead; the earlier periods are computed and must satisfy the identities exactly.
    """
    for index, row in enumerate(rows):
        if index % per_year == per_year - 1:
            continue
        assert row["posttax_cfads_lkr"] == row["pretax_cfads_lkr"] - row["tax_lkr"]
        assert row["cfads_final_lkr"] == (
            row["posttax_cfads_lkr"]
            - row["risk_haircut_amount_lkr"]
            - row["bess_augmentation_capex_lkr"]
        )
        assert row["cfads_risk_adjusted_lkr"] == row["cfads_final_lkr"]


# ---------------------------------------------------------------------------
# Default-off
# ---------------------------------------------------------------------------


def test_no_config_or_no_calendar_resolves_to_none() -> None:
    assert resolve_event_calendar(None, QUARTERLY) is None
    assert resolve_event_calendar({}, QUARTERLY) is None
    assert resolve_event_calendar({"cashflow": {}}, QUARTERLY) is None
    assert resolve_event_calendar({"cashflow": {}}, ANNUAL) is None


def test_no_committed_scenario_declares_a_calendar() -> None:
    """The default-off claim, read from the scenarios rather than asserted."""
    paths = sorted(glob.glob("scenarios/*.yaml"))
    assert len(paths) == 37  # guards the glob; update when a scenario is added
    declaring = []
    for path in paths:
        with open(path) as handle:
            # Some example scenarios carry more than one YAML document; read them all.
            documents = list(yaml.safe_load_all(handle))
        for config in documents:
            cashflow = config.get("cashflow") if isinstance(config, dict) else None
            if isinstance(cashflow, dict) and "event_calendar" in cashflow:
                declaring.append(path)
    assert declaring == []


def test_an_empty_calendar_changes_nothing(bess_annual_rows) -> None:
    calendar = _resolve({})
    assert calendar is not None and calendar.placements == {}
    rows = build_subannual_rows(bess_annual_rows, QUARTERLY, SEASONAL)
    assert apply_event_calendar(rows, bess_annual_rows, calendar) == rows


# ---------------------------------------------------------------------------
# The placement on the live committed cases
# ---------------------------------------------------------------------------


def test_bess_augmentation_lands_in_its_declared_quarter(bess_annual_rows) -> None:
    """The headline: a discrete payment shows as a discrete dip, not a smoothed one."""
    annual = bess_annual_rows
    aug_years = [
        i for i, row in enumerate(annual) if row["bess_augmentation_capex_lkr"]
    ]
    assert aug_years, "the committed BESS case must carry an augmentation payment"

    profile_rows = build_subannual_rows(annual, QUARTERLY, SEASONAL)
    calendar = _resolve({"bess_augmentation_capex": {"periods": [1]}})
    assert calendar is not None
    placed = apply_event_calendar(profile_rows, annual, calendar)

    for year_index in aug_years:
        payment = float(annual[year_index]["bess_augmentation_capex_lkr"])
        start = year_index * 4
        q1_profile, q1_placed = profile_rows[start], placed[start]
        assert q1_placed["bess_augmentation_capex_lkr"] == payment
        for quarter in range(1, 4):
            assert placed[start + quarter]["bess_augmentation_capex_lkr"] == 0.0
        # Q1 CFADS falls by the part of the payment the profile had spread elsewhere.
        moved = payment - q1_profile["bess_augmentation_capex_lkr"]
        assert q1_placed["cfads_final_lkr"] == pytest.approx(
            q1_profile["cfads_final_lkr"] - moved, rel=1e-12
        )
        assert q1_placed["cfads_final_lkr"] < q1_profile["cfads_final_lkr"]

    _assert_reconciles(placed, annual, QUARTERLY)
    _assert_identities(placed, 4)


def test_untouched_keys_are_identical_to_a2(bess_annual_rows) -> None:
    profile_rows = build_subannual_rows(bess_annual_rows, QUARTERLY, SEASONAL)
    calendar = _resolve(
        {
            "bess_augmentation_capex": {"periods": [1]},
            "tax": {"periods": [2, 4], "weights": [0.25, 0.75]},
        }
    )
    assert calendar is not None
    placed = apply_event_calendar(profile_rows, bess_annual_rows, calendar)
    assert len(placed) == len(profile_rows)
    for before, after in zip(profile_rows, placed, strict=True):
        assert set(before) == set(after)
        for key in set(before) - WRITTEN_KEYS:
            assert after[key] == before[key], key


def test_lendercase_tax_installments_reconcile(lender_annual_rows) -> None:
    annual = lender_annual_rows
    assert any(float(row["tax_lkr"]) for row in annual), "lendercase must pay tax"

    profile_rows = build_subannual_rows(annual, QUARTERLY, SEASONAL)
    calendar = _resolve({"tax": {"periods": [2, 4], "weights": [0.4, 0.6]}})
    assert calendar is not None
    placed = apply_event_calendar(profile_rows, annual, calendar)

    for year_index, row in enumerate(annual):
        tax = [placed[year_index * 4 + q]["tax_lkr"] for q in range(4)]
        assert tax[0] == 0.0 and tax[2] == 0.0
        assert tax[1] == float(row["tax_lkr"]) * 0.4
        # Taxable income still accrues on the profile: earned through the year.
        for quarter in range(4):
            index = year_index * 4 + quarter
            assert (
                placed[index]["taxable_income_lkr"]
                == profile_rows[index]["taxable_income_lkr"]
            )

    _assert_reconciles(placed, annual, QUARTERLY)
    _assert_identities(placed, 4)


def test_cfads_usd_keeps_the_years_own_conversion(lender_annual_rows) -> None:
    """Moving LKR between quarters moves USD at the year's own factor."""
    annual = lender_annual_rows
    profile_rows = build_subannual_rows(annual, QUARTERLY, SEASONAL)
    calendar = _resolve({"tax": {"periods": [4]}})
    assert calendar is not None
    placed = apply_event_calendar(profile_rows, annual, calendar)
    for year_index, row in enumerate(annual):
        lkr = float(row["cfads_final_lkr"])
        if lkr == 0.0:
            continue
        factor = float(row["cfads_usd"]) / lkr
        for quarter in range(3):
            got = placed[year_index * 4 + quarter]
            assert got["cfads_usd"] == got["cfads_final_lkr"] * factor


def test_bridge_service_events_sum_to_the_bridge_period() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    result = run_v14_pipeline(config=LENDER_CASE, validation_mode="strict")
    debt = result["debt_result"]
    bridge = debt["cfads_bridge_debt_period"]
    assert bridge is not None, "the lendercase timeline carries a bridge period"
    service = float(debt["debt_service_total"][bridge])
    interest = float(debt["interest_total"][bridge])
    assert service > 0.0

    calendar = _resolve({"bridge_service": {"periods": [1, 3], "weights": [0.5, 0.5]}})
    assert calendar is not None
    events = build_bridge_service_events(debt, calendar)
    assert [event["period_in_year"] for event in events] == [0.0, 1.0, 2.0, 3.0]
    assert all(event["year"] == 1.0 for event in events)
    assert events[1]["debt_service_usd"] == 0.0
    assert events[3]["debt_service_usd"] == 0.0

    for key, want in (
        ("debt_service_usd", service),
        ("interest_usd", interest),
        ("principal_usd", service - interest),
    ):
        got = math.fsum(event[key] for event in events)
        assert abs(got - want) <= RECONCILIATION_ULP_TOLERANCE * math.ulp(want), key
    for event in events[:-1]:
        assert (
            event["interest_usd"] + event["principal_usd"] == event["debt_service_usd"]
        )


def test_bridge_events_are_empty_unless_declared_and_present() -> None:
    debt = {"cfads_bridge_debt_period": None}
    declared = _resolve({"bridge_service": {"periods": [1]}})
    undeclared = _resolve({"tax": {"periods": [1]}})
    assert declared is not None and undeclared is not None
    assert build_bridge_service_events(debt, declared) == []
    assert (
        build_bridge_service_events({"cfads_bridge_debt_period": 2}, undeclared) == []
    )


def test_a_row_count_that_is_not_whole_years_is_refused(bess_annual_rows) -> None:
    rows = build_subannual_rows(bess_annual_rows, QUARTERLY)
    calendar = _resolve({"tax": {"periods": [1]}})
    assert calendar is not None
    with pytest.raises(ValueError, match="do not describe the same years"):
        apply_event_calendar(rows[:-1], bess_annual_rows, calendar)


# ---------------------------------------------------------------------------
# Refusals at the resolver
# ---------------------------------------------------------------------------


def test_default_weights_are_equal_over_the_declared_periods() -> None:
    calendar = _resolve({"tax": {"periods": [2, 4]}})
    assert calendar is not None
    assert calendar.placements["tax"] == (0.0, 0.5, 0.0, 0.5)
    assert calendar.placed_row_keys == {"tax_lkr": (0.0, 0.5, 0.0, 0.5)}


def test_every_row_key_kind_places_an_annual_flow() -> None:
    for kind, row_key in EVENT_KINDS.items():
        if row_key is not None:
            assert row_key in FLOW_KEYS, kind


def test_a_calendar_on_the_annual_grid_is_refused() -> None:
    with pytest.raises(ValueError, match="annual"):
        resolve_event_calendar(
            {"cashflow": {"event_calendar": {"tax": {"periods": [1]}}}}, ANNUAL
        )


def test_working_capital_is_refused_as_not_modelled() -> None:
    with pytest.raises(ValueError, match="not modelled.*FRAMEWORK-02"):
        _resolve({"working_capital": {"periods": [1]}})


@pytest.mark.parametrize(
    ("calendar", "match"),
    [
        (["tax"], "must be a mapping of event kind"),
        ({"vat": {"periods": [1]}}, "not a known event kind"),
        ({"tax": [1, 2]}, "must be a mapping with 'periods'"),
        ({"tax": {"periods": [1], "dates": ["2027-03-31"]}}, "unknown field"),
        ({"tax": {}}, "non-empty list"),
        ({"tax": {"periods": []}}, "non-empty list"),
        ({"tax": {"periods": "1"}}, "non-empty list"),
        ({"tax": {"periods": [0]}}, "whole numbers from 1 to 4"),
        ({"tax": {"periods": [5]}}, "whole numbers from 1 to 4"),
        ({"tax": {"periods": [1.0]}}, "whole numbers from 1 to 4"),
        ({"tax": {"periods": [True]}}, "whole numbers from 1 to 4"),
        ({"tax": {"periods": [2, 2]}}, "more than once"),
        ({"tax": {"periods": [1, 2], "weights": [1.0]}}, "weights"),
        ({"tax": {"periods": [1, 2], "weights": [0.6, 0.6]}}, "weights"),
        ({"tax": {"periods": [1, 2], "weights": [1.5, -0.5]}}, "weights"),
    ],
)
def test_malformed_calendars_are_refused(calendar: Any, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _resolve(calendar)


# ---------------------------------------------------------------------------
# Pre-flight and the field spec
# ---------------------------------------------------------------------------


def _preflight_config(cashflow: Dict[str, Any]) -> Dict[str, Any]:
    from tests.finance.test_f03_preflight_period_fields import _valid_config

    config = _valid_config()
    config["cashflow"] = cashflow
    return config


def test_preflight_passes_a_well_formed_calendar() -> None:
    config = _preflight_config(
        {
            "resolution": "quarterly",
            "event_calendar": {
                "bess_augmentation_capex": {"periods": [1]},
                "tax": {"periods": [2, 4], "weights": [0.5, 0.5]},
                "bridge_service": {"periods": [1, 2, 3, 4]},
            },
        }
    )
    validate_config_for_v14(config, "<test>", ["cashflow", "debt"])


@pytest.mark.parametrize(
    "cashflow",
    [
        {"event_calendar": {"tax": {"periods": [1]}}},
        {"resolution": "quarterly", "event_calendar": {"working_capital": {}}},
        {"resolution": "quarterly", "event_calendar": {"tax": {"periods": [9]}}},
    ],
    ids=["annual-grid", "working-capital", "period-out-of-range"],
)
def test_preflight_refuses_a_bad_calendar(cashflow: Dict[str, Any]) -> None:
    with pytest.raises(ConfigValidationError, match=EVENT_CALENDAR_KEY):
        validate_config_for_v14(_preflight_config(cashflow), "<test>", ["cashflow"])


def test_a_bad_profile_does_not_hide_a_bad_calendar() -> None:
    config = _preflight_config(
        {
            "resolution": "quarterly",
            "within_year_profile": [0.5, 0.5],
            "event_calendar": {"working_capital": {"periods": [1]}},
        }
    )
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(config, "<test>", ["cashflow"])
    message = str(excinfo.value)
    assert "within_year_profile" in message
    assert "working_capital" in message


def test_the_calendar_is_registered_at_its_resolvers_path_without_a_validator() -> None:
    import finance.cashflow_v14  # noqa: F401  (import side effect registers the specs)

    specs = {spec.name: spec for spec in get_required_fields("cashflow")}
    spec = specs["cashflow_event_calendar"]
    assert {".".join(path) for path in spec.paths} == {EVENT_CALENDAR_KEY}
    assert spec.required is False
    assert spec.validator is None
    assert spec.description
