"""The balloon limit and the DSRA months have no code default (#1429, D08 and D09).

The debt engine used to fill an absent ``constraints.max_balloon_pct`` with 10% and absent
DSRA target months with 6, both Dutch Bay figures. Both are project terms a lender sets, so
each now comes only from the scenario YAML: strict pre-flight refuses a scenario that omits
one, naming the path, and so does the engine where it reads it. The owner's #920 ruling
keeps 6 months as a labelled assumption until a term sheet sets it; the figure is now the
scenario's, still labelled ``assumption_no_term_sheet``.

The DSRA months are read from the section the debt layer reads its terms from
(``Financing_Terms``, else ``financing``, else ``debt``, else the top level), as the
sizing terms are. Every committed engine scenario declares both terms, so no figure moves.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from analytics.pipeline_v14_enhanced import _build_debt_covenant_snapshot
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.debt_v14 import (
    plan_debt,
    resolve_dsra_target_months,
    resolve_max_balloon_pct,
)
from tests.finance.test_debt_fallbacks_required_1429 import (
    LENDER,
    SCENARIOS,
    _engine_scenarios,
)

_BAD = ["ten", float("nan"), float("inf"), True, None]


def _lender() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(str(LENDER))))


def _preflight(config: Dict[str, Any]) -> None:
    validate_config_for_v14(config, "case", ["cashflow", "debt"])


def _synthetic(section: Any = "Financing_Terms", **extra: Any) -> Dict[str, Any]:
    """A minimal engine config declaring both terms, with its terms in ``section``."""
    terms: Dict[str, Any] = {
        "construction_periods": 1,
        "construction_schedule": [100.0],
        "debt_drawdown_pct": [1.0],
        "debt_ratio": 0.70,
        "tenor_years": 5,
        "interest_only_years": 0,
        "amortization_style": "sculpted",
        "target_dscr": 1.30,
        "mix": {"usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08},
        "dsra_months": 6,
        **extra,
    }
    config: Dict[str, Any] = {
        "capex": {"usd_total": 100_000_000.0},
        "constraints": {"max_balloon_pct": 0.10},
    }
    if section is None:
        config.update(terms)
    else:
        config[section] = terms
    return config


def _rows(count: int = 5) -> List[Dict[str, Any]]:
    return [
        {"year": i + 1, "cfads_usd": 12_000_000.0, "fx_rate": 300.0}
        for i in range(count)
    ]


@pytest.mark.parametrize(
    "path", _engine_scenarios(), ids=lambda p: str(p.relative_to(SCENARIOS))
)
def test_every_engine_scenario_declares_both_terms(path: Any) -> None:
    """No committed engine scenario relied on either fallback, so none is refused."""
    config = dict(load_scenario_config(str(path)))
    assert 0.0 < resolve_max_balloon_pct(config) <= 1.0
    months, source = resolve_dsra_target_months(config)
    assert months > 0.0
    assert source.endswith("dsra_months") or source.endswith("target_months")


def test_preflight_accepts_the_lender_case() -> None:
    _preflight(_lender())  # control for every refusal below


def test_preflight_refuses_a_missing_balloon_limit_naming_its_path() -> None:
    config = _lender()
    del config["constraints"]["max_balloon_pct"]
    with pytest.raises(ConfigValidationError) as excinfo:
        _preflight(config)
    assert "constraints.max_balloon_pct is required" in str(excinfo.value)
    assert "no code default (#1429)" in str(excinfo.value)


def test_preflight_refuses_missing_dsra_months_naming_the_authored_path() -> None:
    config = _lender()
    del config["Financing_Terms"]["reserves"]["dsra_months"]
    with pytest.raises(ConfigValidationError) as excinfo:
        _preflight(config)
    assert "Financing_Terms.reserves.dsra_months is required" in str(excinfo.value)


def test_preflight_names_both_terms_when_both_are_missing() -> None:
    config = _lender()
    del config["constraints"]
    del config["Financing_Terms"]["reserves"]
    with pytest.raises(ConfigValidationError) as excinfo:
        _preflight(config)
    message = str(excinfo.value)
    assert "constraints.max_balloon_pct is required" in message
    assert "Financing_Terms.reserves.dsra_months is required" in message


@pytest.mark.parametrize("bad", _BAD, ids=str)
def test_a_declared_balloon_limit_that_is_not_a_number_is_refused(bad: Any) -> None:
    config = _lender()
    config["constraints"]["max_balloon_pct"] = bad
    with pytest.raises(ConfigValidationError, match=r"constraints\.max_balloon_pct"):
        _preflight(config)


@pytest.mark.parametrize("bad", _BAD, ids=str)
def test_declared_dsra_months_that_are_not_a_number_are_refused(bad: Any) -> None:
    config = _lender()
    config["Financing_Terms"]["reserves"]["dsra_months"] = bad
    with pytest.raises(
        ConfigValidationError, match=r"Financing_Terms\.reserves\.dsra_months"
    ):
        _preflight(config)


def test_preflight_is_not_asked_when_debt_is_not_validated() -> None:
    config = _lender()
    del config["constraints"]["max_balloon_pct"]
    del config["Financing_Terms"]["reserves"]
    validate_config_for_v14(config, "lender", ["cashflow"])


@pytest.mark.parametrize(
    ("section", "path"),
    [
        ("Financing_Terms", "Financing_Terms.reserves.dsra_months"),
        ("financing", "financing.dsra_months"),
        ("debt", "debt.dsra_months"),
        (None, "dsra_months"),
    ],
)
def test_dsra_months_are_required_in_the_section_the_debt_layer_reads(
    section: Any, path: str
) -> None:
    config = _synthetic(section)
    assert resolve_dsra_target_months(config) == (
        6.0,
        "dsra_months" if section is None else f"{section}.dsra_months",
    )
    terms = config if section is None else config[section]
    del terms["dsra_months"]
    with pytest.raises(ValueError, match=rf"^{path.replace('.', '[.]')} is required"):
        resolve_dsra_target_months(config)


def test_engine_refuses_a_missing_balloon_limit_at_the_point_of_use() -> None:
    config = _synthetic()
    del config["constraints"]
    with pytest.raises(ValueError, match=r"constraints\.max_balloon_pct is required"):
        plan_debt(annual_rows=_rows(), config=config)


@pytest.mark.parametrize("section", ["Financing_Terms", "debt"])
def test_engine_refuses_missing_dsra_months_at_the_point_of_use(section: str) -> None:
    config = _synthetic(section)
    del config[section]["dsra_months"]
    with pytest.raises(ValueError, match=rf"{section}\.\S*dsra_months is required"):
        plan_debt(annual_rows=_rows(), config=config)


@pytest.mark.parametrize("section", ["Financing_Terms", "debt"])
def test_declared_values_are_used_unchanged(section: str) -> None:
    config = _synthetic(section, dsra_months=9)
    config["constraints"]["max_balloon_pct"] = 0.25
    debt = plan_debt(annual_rows=_rows(), config=config)
    assert debt["max_balloon_pct"] == pytest.approx(0.25)
    funding = debt["funding"]
    assert funding["dsra_target_months"] == pytest.approx(9.0)
    assert funding["dsra_target_source"] == f"{section}.dsra_months"
    assert funding["dsra_target_basis"] == "assumption_no_term_sheet"


def test_covenant_note_prints_the_scenarios_own_limit() -> None:
    """The breach note prints the limit the engine published, not a 10% stand-in."""
    config = _synthetic()
    debt_result = dict(plan_debt(annual_rows=_rows(), config=config))
    # A published breach against a 25% limit (the synthetic case itself has no balloon).
    debt_result.update(
        balloon_remaining=30_000_000.0,
        balloon_pct=0.30,
        balloon_covenant_breach=True,
        max_balloon_pct=0.25,
    )
    snapshot = _build_debt_covenant_snapshot(config, debt_result)
    assert "BREACHES max_balloon_pct 25%" in (snapshot.notes or "")
