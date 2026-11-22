"""Debt sized to the annual covenant DSCR (#1845).

Owner decision 2026-11-22: the lender case sizes its debt so the ANNUAL covenant DSCR
(``dscr_by_year``, which folds the synthetic half-year bridge's service into operating
year 1) also meets ``target_dscr``, not only each debt period's own DSCR. The switch is
``Financing_Terms.sizing_dscr_basis: annual_covenant``; absent, sizing is unchanged.

Oracles do not come from the code under test (TEST-01):

* a hand-worked one-tranche sculpt: year 1's service is CFADS / target less the folded
  bridge interest;
* the covenant years the engine publishes, checked against the target directly;
* the same scenario on the old basis, which must keep its year-1 shortfall, and an absent
  key that must equal ``period`` exactly;
* less debt on the stricter basis (the covenant set is a superset of the period set).
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from finance.debt.schedules import Tranche, _sculpted_schedule
from finance.debt.terms import SIZING_DSCR_BASES, resolve_sizing_dscr_basis

REPO = Path(__file__).resolve().parents[2]
LENDER = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
TARGET = 1.30


def test_resolver_defaults_validates_and_reads_case_insensitively() -> None:
    assert SIZING_DSCR_BASES == ("period", "annual_covenant")
    assert resolve_sizing_dscr_basis({}) == "period"
    assert resolve_sizing_dscr_basis({"Financing_Terms": {}}) == "period"
    assert (
        resolve_sizing_dscr_basis(
            {"financing_terms": {"sizing_dscr_basis": " Annual_Covenant "}}
        )
        == "annual_covenant"
    )
    with pytest.raises(ValueError, match="sizing_dscr_basis"):
        resolve_sizing_dscr_basis({"Financing_Terms": {"sizing_dscr_basis": "yearly"}})


def test_sculpt_takes_the_folded_service_out_of_the_next_period() -> None:
    # One tranche of 1000 at 10%, one interest-only period (the bridge: 100 of interest),
    # then amortising periods with CFADS 400.
    def run(folded: Any) -> Dict[str, Any]:
        return _sculpted_schedule(
            {"usd": Tranche("usd", 0.10, 1000.0, 1)},
            3,
            [200.0, 400.0, 400.0, 400.0],
            TARGET,
            folded_index=folded,
        )

    plain = run(None)["usd"]
    folded = run(0)["usd"]
    assert plain[0] == folded[0] == pytest.approx((100.0, 0.0, 100.0))
    # Period on its own: 400 / 1.3. Folded: 400 / 1.3 - 100 of bridge interest.
    assert plain[1][2] == pytest.approx(400.0 / TARGET)
    assert folded[1][2] == pytest.approx(400.0 / TARGET - 100.0)
    # The covenant year (bridge + year 1) now meets the target exactly.
    assert 400.0 / (folded[0][2] + folded[1][2]) == pytest.approx(TARGET)
    # Later periods are still sculpted on their own CFADS.
    assert folded[2][2] == pytest.approx(400.0 / TARGET)


def _lender(basis: Any) -> Dict[str, Any]:
    config = load_scenario_config(LENDER)
    fin = config["Financing_Terms"]
    if basis is None:
        fin.pop("sizing_dscr_basis", None)
    else:
        fin["sizing_dscr_basis"] = basis
    logging.disable(logging.WARNING)
    try:
        out = evaluate_with_overrides(raw_config=config, return_full_result=True)
    finally:
        logging.disable(logging.NOTSET)
    assert isinstance(out, dict)
    return out


def test_the_lender_case_declares_the_annual_covenant_basis() -> None:
    config = load_scenario_config(LENDER)
    assert resolve_sizing_dscr_basis(config) == "annual_covenant"
    assert config["Financing_Terms"]["target_dscr"] == TARGET


def test_every_covenant_year_meets_the_target_on_the_annual_basis() -> None:
    debt = _lender("annual_covenant")["debt_result"]
    years = [v for v in debt["dscr_by_year"].values() if v is not None]
    assert years, "the lender case must publish covenant years"
    assert min(years) >= TARGET - 1e-9
    assert debt["min_dscr"] == pytest.approx(TARGET, abs=1e-9)


def test_the_period_basis_keeps_the_year_one_shortfall_and_more_debt() -> None:
    period = _lender("period")
    annual = _lender("annual_covenant")
    year_one = next(iter(period["debt_result"]["dscr_by_year"].values()))
    assert year_one < TARGET - 0.01
    assert annual["kpis"]["max_debt_usd"] < period["kpis"]["max_debt_usd"]


def test_an_absent_key_is_exactly_the_period_basis() -> None:
    absent = _lender(None)
    period = _lender("period")
    assert absent["kpis"] == period["kpis"]
    assert copy.deepcopy(absent["debt_result"]["dscr_by_year"]) == (
        period["debt_result"]["dscr_by_year"]
    )
