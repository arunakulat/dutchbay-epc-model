"""Both DSRA month figures are published as assumptions, with the key that set them (#920).

Owner ruling on #920 (2026-11-15): keep the reserve at 6 months of debt service as a
labelled assumption until a term sheet sets it. The model holds two month figures:

- ``Financing_Terms`` DSRA months, in ``debt_result["funding"]``. They size the reserve
  funded at financial close, and only when ``Financing_Terms.dsra.fund_at_close`` is on.
  ``dsra_target_governs`` says which.
- ``min_reserve_months`` in the equity waterfall. It sizes the reserve built from operating
  cash, in every mode. ``equity_summary`` carries its source and basis.

Each source names the key that set the figure. The waterfall's figure is still labelled
``code_default`` when its 6-month fallback sets it. The funding months have no code default
since #1429 (D08): a scenario that declares none, or whose winning key is null or not a
number, is refused naming the key. Changing the governing key moves both the label and the
figure; no figure moves on committed scenarios.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

LENDER = str(
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)
_BASIS = "assumption_no_term_sheet"


def _run(
    dsra: Optional[Dict[str, Any]] = None,
    reserves: Any = "keep",
    equity: Optional[Dict[str, Any]] = None,
    **fin: Any,
) -> Dict[str, Any]:
    cfg = dict(load_scenario_config(LENDER))
    terms = {**cfg["Financing_Terms"], **fin}
    if reserves != "keep":
        terms["reserves"] = reserves
    if dsra is not None:
        terms["dsra"] = dsra
    cfg["Financing_Terms"] = terms
    if equity is not None:
        cfg["equity"] = equity
    return dict(run_v14_pipeline(config=copy.deepcopy(cfg)))


def _funding(**kwargs: Any) -> Dict[str, Any]:
    return dict(_run(**kwargs)["debt_result"]["funding"])


def _summary(result: Dict[str, Any]) -> Dict[str, Any]:
    return dict(result["equity_distribution"]["equity_summary"])


def _equity_figures(result: Dict[str, Any]) -> str:
    """The equity results, without the run's own config echo or timings."""
    return json.dumps(
        {
            "kpis": result["kpis"],
            "rows": result["equity_distribution"]["annual_distributions"],
        },
        sort_keys=True,
        default=str,
    )


@pytest.fixture(scope="module")
def baseline() -> Dict[str, Any]:
    return _run()


def test_lender_case_labels_both_month_figures(baseline: Dict[str, Any]) -> None:
    funding = baseline["debt_result"]["funding"]
    assert funding["dsra_target_months"] == pytest.approx(6.0)
    assert funding["dsra_target_basis"] == _BASIS
    assert funding["dsra_target_source"] == "Financing_Terms.reserves.dsra_months"
    # fund_at_close is off, so the funding months size nothing.
    assert funding["fund_at_close"] is False
    assert funding["initial_dsra_usd"] == 0
    assert (
        funding["dsra_target_governs"]
        == "nothing_reserve_sized_by_equity_min_reserve_months"
    )
    # The reserve the waterfall builds is sized by an engine default no scenario authors.
    summary = _summary(baseline)
    assert summary["min_reserve_months"] == 6
    assert summary["min_reserve_months_source"] == "code_default"
    assert summary["min_reserve_months_basis"] == _BASIS


@pytest.mark.parametrize(
    ("kwargs", "source", "months"),
    [
        (
            {"dsra": {"target_months": 3}, "dsra_months": 9},
            "Financing_Terms.dsra.target_months",
            3.0,
        ),
        ({"dsra_months": 9}, "Financing_Terms.dsra_months", 9.0),
    ],
    ids=["dsra-block", "legacy-key"],
)
def test_funding_source_is_the_key_that_set_the_months(
    kwargs: Dict[str, Any], source: str, months: float
) -> None:
    funding = _funding(**kwargs)
    assert funding["dsra_target_source"] == source
    assert funding["dsra_target_months"] == pytest.approx(months)
    assert funding["dsra_target_basis"] == _BASIS


@pytest.mark.parametrize(
    ("kwargs", "path"),
    [
        # No key declares the months: there is no 6-month code default (#1429, D08).
        ({"reserves": {}}, "Financing_Terms.reserves.dsra_months"),
        # A present null shadows the rungs below it and is refused naming that key.
        (
            {"dsra": {"target_months": None}, "dsra_months": 9},
            "Financing_Terms.dsra.target_months",
        ),
        (
            {"dsra_months": None, "reserves": {"dsra_months": 9}},
            "Financing_Terms.dsra_months",
        ),
        # A value that is not a number is refused too.
        ({"reserves": {"dsra_months": "six"}}, "Financing_Terms.reserves.dsra_months"),
    ],
    ids=["absent", "null-target-shadows", "null-legacy-shadows", "non-numeric"],
)
def test_funding_months_without_a_number_are_refused_naming_the_key(
    kwargs: Dict[str, Any], path: str
) -> None:
    with pytest.raises(Exception, match=rf"{path.replace('.', '[.]')} is required"):
        _run(**kwargs)


def test_funding_months_move_nothing_while_fund_at_close_is_off(
    baseline: Dict[str, Any],
) -> None:
    """The label and the funding figure move together; the cash flows do not."""
    changed = _run(reserves={"dsra_months": 3})
    funding = changed["debt_result"]["funding"]
    assert funding["dsra_target_months"] == pytest.approx(3.0)
    assert funding["dsra_target_source"] == "Financing_Terms.reserves.dsra_months"
    assert _equity_figures(changed) == _equity_figures(baseline)


def test_waterfall_months_move_the_reserve_and_their_label(
    baseline: Dict[str, Any],
) -> None:
    """The governing key: its label and the equity figures move together."""
    changed = _run(equity={"min_reserve_months": 3})
    summary = _summary(changed)
    assert summary["min_reserve_months"] == 3
    assert summary["min_reserve_months_source"] == "equity.min_reserve_months"
    assert summary["min_reserve_months_basis"] == _BASIS
    assert _equity_figures(changed) != _equity_figures(baseline)
    assert changed["kpis"]["equity_npv"] != pytest.approx(
        baseline["kpis"]["equity_npv"], rel=0, abs=1.0
    )
    # The funding block is untouched by the waterfall's key.
    assert changed["debt_result"]["funding"] == baseline["debt_result"]["funding"]


@pytest.mark.parametrize("value", [None, "six"])
def test_waterfall_fallback_is_labelled_code_default(value: Any) -> None:
    summary = _summary(_run(equity={"min_reserve_months": value}))
    assert summary["min_reserve_months"] == 6
    assert summary["min_reserve_months_source"] == "code_default"


def test_funding_months_govern_the_at_close_reserve_when_fund_at_close_is_on() -> None:
    six = _funding(dsra={"fund_at_close": True}, reserves={"dsra_months": 6})
    three = _funding(dsra={"fund_at_close": True}, reserves={"dsra_months": 3})
    for funding in (six, three):
        assert funding["dsra_target_governs"] == "initial_dsra_at_close"
        assert funding["dsra_target_source"] == "Financing_Terms.reserves.dsra_months"
    assert six["initial_dsra_usd"] > 0
    assert three["initial_dsra_usd"] == pytest.approx(
        six["initial_dsra_usd"] / 2.0, rel=1e-6
    )
