"""Follow-ups from the two review lanes on #1860, the #1429 D08/D09 slice (#1862).

- A-1 / DOM-3: ``dsra.fund_at_close`` is read from the same financing section as the DSRA
  months, so on the simple ``financing:`` or ``debt:`` schema it is honoured, not ignored.
- DOM-2: the two required terms are range-checked. The balloon limit is a fraction between
  0 and 1 (``10`` is refused, not read as 1000%); the DSRA months may not be negative.
- A-2: the engine reads the ``constraints`` section in any case. The test pins that read.
- DOM-4: the lender report reads ``constraints`` as the engine does, so a scenario keyed
  ``Constraints:`` has its own limits tested by the report as well as by the engine.

The financing questionnaire's new balloon-ceiling row (DOM-5) is checked with the other
rows in ``tests/analysis_tools/test_financing_questionnaire.py``. Every committed engine
scenario declares a limit of 0.10 or 0.15 and 6 DSRA months, inside the new bounds, so no
figure moves (``test_every_engine_scenario_declares_both_terms``).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, Optional

import pytest

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from app.reports.report_config import Covenants
from app.reports.report_model import _lookup_key_as_engine, _scenario_covenants
from finance.debt.helpers import _lookup_case_insensitive
from finance.debt_v14 import (
    plan_debt,
    resolve_dsra_target_months,
    resolve_max_balloon_pct,
)
from tests.finance.test_debt_covenant_terms_required_1429 import (
    _lender,
    _rows,
    _synthetic,
)


def _preflight(config: Dict[str, Any]) -> None:
    validate_config_for_v14(config, "case", ["cashflow", "debt"])


def _terms(config: Dict[str, Any], section: Optional[str]) -> Dict[str, Any]:
    return config if section is None else config[section]


# --- A-1 / DOM-3: fund_at_close from the section the months come from --------------------


@pytest.mark.parametrize("section", ["Financing_Terms", "financing", "debt", None])
def test_fund_at_close_is_honoured_in_every_financing_section(
    section: Optional[str],
) -> None:
    off = plan_debt(annual_rows=_rows(), config=_synthetic(section))["funding"]
    assert off["fund_at_close"] is False
    assert off["initial_dsra_usd"] == 0

    config = _synthetic(section)
    _terms(config, section)["dsra"] = {"fund_at_close": True}
    on = plan_debt(annual_rows=_rows(), config=config)["funding"]
    assert on["fund_at_close"] is True
    assert on["dsra_target_governs"] == "initial_dsra_at_close"
    assert on["initial_dsra_usd"] > 0
    # Equity funds the reserve at close, so sources still equal uses.
    sources_and_uses = on["sources_and_uses"]
    assert sources_and_uses["uses"]["initial_dsra_usd"] == on["initial_dsra_usd"]
    assert sources_and_uses["balanced"] is True


def test_fund_at_close_and_months_come_from_one_section() -> None:
    """A flag in a section the engine does not read for terms is not picked up."""
    config = _synthetic("debt")
    config["Financing_Terms"] = {}  # empty, so the engine reads ``debt``
    config["financing_unused"] = {"dsra": {"fund_at_close": True}}
    funding = plan_debt(annual_rows=_rows(), config=config)["funding"]
    assert funding["dsra_target_source"] == "debt.dsra_months"
    assert funding["fund_at_close"] is False


def test_the_at_close_reserve_on_the_debt_schema_uses_its_declared_months() -> None:
    six = _synthetic("debt", dsra={"fund_at_close": True})
    three = _synthetic("debt", dsra={"fund_at_close": True}, dsra_months=3)
    six_dsra = plan_debt(annual_rows=_rows(), config=six)["funding"]["initial_dsra_usd"]
    three_dsra = plan_debt(annual_rows=_rows(), config=three)["funding"][
        "initial_dsra_usd"
    ]
    assert three_dsra == pytest.approx(six_dsra / 2.0, rel=1e-6)


# --- DOM-2: range checks --------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.01, 1.01, 10, 10.0], ids=str)
def test_a_balloon_limit_outside_zero_to_one_is_refused(bad: Any) -> None:
    config = _lender()
    config["constraints"]["max_balloon_pct"] = bad
    with pytest.raises(
        ValueError, match=r"^constraints\.max_balloon_pct must be between 0 and 1"
    ):
        resolve_max_balloon_pct(config)
    with pytest.raises(ConfigValidationError, match=r"constraints\.max_balloon_pct"):
        _preflight(config)
    engine = _synthetic()
    engine["constraints"]["max_balloon_pct"] = bad
    with pytest.raises(ValueError, match=r"constraints\.max_balloon_pct must be"):
        plan_debt(annual_rows=_rows(), config=engine)


@pytest.mark.parametrize("edge", [0, 0.0, 1, 1.0], ids=str)
def test_a_balloon_limit_at_either_bound_is_accepted(edge: Any) -> None:
    config = _lender()
    config["constraints"]["max_balloon_pct"] = edge
    assert resolve_max_balloon_pct(config) == float(edge)
    _preflight(config)


@pytest.mark.parametrize(
    ("section", "path"),
    [
        ("Financing_Terms", "Financing_Terms.dsra_months"),
        ("debt", "debt.dsra_months"),
    ],
)
def test_negative_dsra_months_are_refused(section: str, path: str) -> None:
    config = _synthetic(section, dsra_months=-1)
    with pytest.raises(
        ValueError, match=rf"^{path.replace('.', '[.]')} must be at least 0"
    ):
        resolve_dsra_target_months(config)
    with pytest.raises(ValueError, match=rf"{path.replace('.', '[.]')} must be"):
        plan_debt(annual_rows=_rows(), config=config)


def test_negative_authored_dsra_months_are_refused_by_preflight() -> None:
    config = _lender()
    config["Financing_Terms"]["reserves"]["dsra_months"] = -6
    with pytest.raises(
        ConfigValidationError, match=r"Financing_Terms\.reserves\.dsra_months must be"
    ):
        _preflight(config)


def test_zero_dsra_months_are_accepted() -> None:
    config = _lender()
    config["Financing_Terms"]["reserves"]["dsra_months"] = 0
    assert resolve_dsra_target_months(config) == (
        0.0,
        "Financing_Terms.reserves.dsra_months",
    )
    _preflight(config)


def test_every_other_required_term_keeps_its_unbounded_check() -> None:
    """The bounds apply to the two #1860 terms only: a debt ratio above 1 still reads as
    a percentage on the ``debt_pct`` path, exactly as before."""
    config = _synthetic("Financing_Terms")
    del config["Financing_Terms"]["debt_ratio"]
    config["Financing_Terms"]["debt_pct"] = 70
    debt = plan_debt(annual_rows=_rows(), config=config)
    assert debt["debt_total"] > 0


# --- A-2: the constraints section in any case -----------------------------------------


@pytest.mark.parametrize("name", ["constraints", "Constraints", "CONSTRAINTS"])
def test_the_engine_reads_the_constraints_section_in_any_case(name: str) -> None:
    config = _synthetic()
    del config["constraints"]
    config[name] = {"max_balloon_pct": 0.25}
    assert resolve_max_balloon_pct(config) == pytest.approx(0.25)
    assert plan_debt(annual_rows=_rows(), config=config)[
        "max_balloon_pct"
    ] == pytest.approx(0.25)


# --- DOM-4: the report reads constraints as the engine does ---------------------------


def _defaults() -> Covenants:
    return Covenants(
        min_dscr_floor=1.2,
        min_dscr_target=1.35,
        max_balloon_pct=0.40,
    )


@pytest.mark.parametrize("name", ["constraints", "Constraints", "CONSTRAINTS"])
def test_the_report_tests_the_scenarios_limits_whatever_the_section_case(
    name: str,
) -> None:
    covenants = _scenario_covenants(
        _defaults(), {name: {"min_dscr_covenant": 1.3, "max_balloon_pct": 0.1}}
    )
    assert covenants.max_balloon_pct == pytest.approx(0.1)
    assert covenants.max_balloon_pct_source == "scenario"
    assert covenants.min_dscr_floor == pytest.approx(1.3)
    assert covenants.min_dscr_floor_source == "scenario"


def test_the_report_and_engine_agree_on_a_capitalised_section() -> None:
    """The failure the review found: the engine tested the scenario's limit, the report
    its own 0.40 default."""
    config = _synthetic()
    config["Constraints"] = config.pop("constraints")
    engine_limit = plan_debt(annual_rows=_rows(), config=config)["max_balloon_pct"]
    report_limit = _scenario_covenants(_defaults(), config).max_balloon_pct
    assert report_limit == pytest.approx(engine_limit)


def test_the_report_reads_each_key_as_the_engine_does() -> None:
    """``min_dscr_covenant`` in any case (as the equity lock-up reads it); the balloon
    limit only under its exact key (as the debt engine reads it)."""
    covenants = _scenario_covenants(
        _defaults(),
        {"constraints": {"MIN_DSCR_COVENANT": 1.3, "MAX_BALLOON_PCT": 0.1}},
    )
    assert covenants.min_dscr_floor == pytest.approx(1.3)
    assert covenants.max_balloon_pct == pytest.approx(0.40)
    assert covenants.max_balloon_pct_source != "scenario"


_LOOKUP_CASES: list[tuple[Mapping[str, Any], str]] = [
    ({"constraints": 1}, "constraints"),
    ({"Constraints": 2}, "constraints"),
    ({"CONSTRAINTS": 3, "constraints": 4}, "constraints"),
    ({"Constraints": 5, "CONSTRAINTS": 6}, "constraints"),
    ({"constraints": None, "Constraints": 7}, "constraints"),
    ({}, "constraints"),
    ({1: "x"}, "1"),
]


@pytest.mark.parametrize(("mapping", "key"), _LOOKUP_CASES)
def test_the_report_lookup_is_the_engines(mapping: Mapping[str, Any], key: str) -> None:
    """The report restates the engine's lookup (no finance import from app/); pin them."""
    assert _lookup_key_as_engine(copy.deepcopy(dict(mapping)), key) == (
        _lookup_case_insensitive(copy.deepcopy(dict(mapping)), key)
    )
