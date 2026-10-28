"""P3-COV-05 part A (#1399): dead payment-support config is refused, and the bases are stated.

Three corrections from the controlled register's corrected claim, none of which moves a
figure:

* ``Financing_Terms.reserves.receivables_guarantee_months`` had no production consumer. It
  is refused at v14 pre-flight (``FRAMEWORK-02``: no silent dead config) and removed from
  every committed scenario.
* The committed scenarios declare a six-month DSRA target with ``fund_at_close`` off, so the
  DSRA at close is zero and the reserve is built from operating cash. ``debt_result.funding``
  and the lender report now say so rather than leaving a blank.
* ``use_revenue_guarantee`` only loads a fee into the cost of debt; no payment-support cash
  flow exists. The funding block and the report say that too.

Part B (funding form, target months, receivables support) waits on the term sheet (#920).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.schema_guard import (
    RECEIVABLES_GUARANTEE_KEY,
    _validate_no_receivables_guarantee,
    validate_config_for_v14,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _lender() -> Dict[str, Any]:
    from analytics.scenario_loader import load_scenario_config

    return copy.deepcopy(dict(load_scenario_config(str(LENDER))))


def _errors(config: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _validate_no_receivables_guarantee(config, errors)
    return errors


def test_receivables_guarantee_under_reserves_is_refused_by_path() -> None:
    config = {
        "Financing_Terms": {
            "reserves": {"dsra_months": 6, RECEIVABLES_GUARANTEE_KEY: 9}
        }
    }
    errors = _errors(config)
    assert len(errors) == 1
    assert "Financing_Terms.reserves.receivables_guarantee_months" in errors[0]
    assert "#920" in errors[0]


def test_receivables_guarantee_directly_under_financing_terms_is_refused() -> None:
    errors = _errors({"Financing_Terms": {RECEIVABLES_GUARANTEE_KEY: 9}})
    assert len(errors) == 1
    assert errors[0].startswith("Financing_Terms.receivables_guarantee_months ")


def test_a_zero_or_null_value_is_still_refused() -> None:
    """Refusal is by presence: a zero is just as unread as a nine."""
    for value in (0, None):
        config = {"Financing_Terms": {"reserves": {RECEIVABLES_GUARANTEE_KEY: value}}}
        assert len(_errors(config)) == 1


def test_absent_key_is_no_error() -> None:
    assert _errors({"Financing_Terms": {"reserves": {"dsra_months": 6}}}) == []
    assert _errors({}) == []
    assert _errors({"Financing_Terms": "not a mapping"}) == []


def test_committed_lender_case_passes_pre_flight() -> None:
    validate_config_for_v14(_lender(), str(LENDER), ["cashflow", "debt"])


def test_reintroducing_the_key_fails_full_pre_flight() -> None:
    """Negative control through the real gate, not only the helper."""
    from analytics.schema_guard import ConfigValidationError

    config = _lender()
    config["Financing_Terms"]["reserves"][RECEIVABLES_GUARANTEE_KEY] = 9
    with pytest.raises(ConfigValidationError, match="receivables_guarantee_months"):
        validate_config_for_v14(config, str(LENDER), ["cashflow", "debt"])


@pytest.mark.parametrize(
    "path",
    sorted(
        list((REPO_ROOT / "scenarios").glob("*.yaml"))
        + list((REPO_ROOT / "feasibility_reproduce" / "cache").glob("*.yaml"))
    ),
    ids=lambda p: p.name,
)
def test_no_committed_scenario_declares_the_dead_key(path: Path) -> None:
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if not isinstance(document, dict):
            continue
        assert _errors(document) == [], path.name


def test_funding_states_zero_dsra_at_close_and_fee_only_guarantee() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    result = run_v14_pipeline(config=str(LENDER), validation_mode="strict")
    funding = result["debt_result"]["funding"]
    assert funding["fund_at_close"] is False
    assert funding["initial_dsra_usd"] == 0.0
    assert funding["dsra_target_months"] == 6.0
    assert funding["dsra_at_close_basis"] == "none_built_from_operating_cash"
    assert funding["payment_support"] == {
        "use_revenue_guarantee": False,
        "treatment": "fee_in_cost_of_debt_only",
        "payment_support_cash_flow_modelled": False,
    }


def test_funding_basis_follows_fund_at_close() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    config = _lender()
    config["Financing_Terms"].setdefault("dsra", {})["fund_at_close"] = True
    config["Financing_Terms"]["use_revenue_guarantee"] = True
    funding = run_v14_pipeline(config=config, validation_mode="strict")["debt_result"][
        "funding"
    ]
    assert funding["initial_dsra_usd"] > 0.0
    assert funding["dsra_at_close_basis"] == "funded_at_close"
    # Turning the guarantee on charges its fee; it still creates no cash flow.
    assert funding["payment_support"]["use_revenue_guarantee"] is True
    assert funding["payment_support"]["payment_support_cash_flow_modelled"] is False


def test_report_states_zero_dsra_and_no_payment_support() -> None:
    from app.api.responses import CaseResult
    from app.reports.renderer import render_report_html
    from app.reports.report_model import build_report_context

    case = CaseResult(
        status="success",
        scenario_variant="lendercase",
        kpis={"project_irr": 0.01, "equity_irr": 0.01, "min_dscr": 1.3},
        run_manifest=None,
    )
    debt = {
        "debt_total": 60_000_000.0,
        "funding": {
            "fund_at_close": False,
            "dsra_target_months": 6.0,
            "initial_dsra_usd": 0.0,
            "sources_and_uses": {
                "uses": {"capex_usd": 150_000_000.0, "idc_usd": 5_000_000.0},
                "sources": {
                    "senior_debt_usd": 65_000_000.0,
                    "equity_usd": 90_000_000.0,
                },
                "uses_total_usd": 155_000_000.0,
                "sources_total_usd": 155_000_000.0,
                "balanced": True,
            },
        },
    }
    html = render_report_html(
        build_report_context(
            case,
            generated_at="2026-10-27T00:00:00+00:00",
            scenario_config={"project": {"capacity_mw": 150.0}},
            debt_result=debt,
        )
    )
    assert "No debt service reserve is funded at financial close." in html
    assert "6.0-month reserve target is built from operating cash" in html
    assert "No payment-support cash flow is modelled." in html
