"""Project sizing O&M must follow the scenario's price basis, not hybrid rates."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from finance.cashflow_v14_production import opex_for_year
from solar_resource import pv_bess_sizing as sz

ROOT = Path(__file__).resolve().parents[2]


def scenario() -> dict[str, Any]:
    """Load the committed scenario without altering its source or assumptions."""
    return yaml.safe_load(
        (ROOT / "scenarios/blue_whale_solar_bess_lot5b_2026.yaml").read_text()
    )


def test_scenario_reference_and_scaled_points() -> None:
    """Scale the independently recorded DC-basis cost to two nominal sizes."""
    basis = sz.project_opex_basis(scenario(), 1.1, 150000)
    total, unit, components = basis.at_size(5.70304, 20)
    assert total == pytest.approx(246630.40)
    assert unit == pytest.approx(96630.40)
    assert components[1]["units"] == pytest.approx(22000)
    total2, unit2, components2 = basis.at_size(6, 10)
    assert total2 == pytest.approx(150000 + 60000 + 19800)
    assert unit2 == pytest.approx(79800)
    assert components2[1]["units"] == pytest.approx(11000)
    assert basis.pre_cod_years == 3


def test_first_year_matches_finance_engine() -> None:
    """Compare pre-COD escalation with the canonical cashflow implementation."""
    basis = sz.project_opex_basis(scenario(), 1.1, 150000)
    total, unit, _ = basis.at_size(5.70304, 20)
    params = {
        "opex_usd_per_year": total,
        "opex_usd_share": 0.0,
        "opex_lkr_base_fx": 333.79,
        "opex_lkr_escalation_pct": 0.05,
        "opex_usd_escalation_pct": 0.025,
        "opex_pre_cod_years": 3,
    }
    engine, _ = opex_for_year(params, 0, 333.79)
    assert engine == pytest.approx(total * 1.05**3)
    flows = sz.unit_pretax_cashflows_usd(
        [0],
        capex_usd=0,
        opex_usd_year1=unit * 1.05**basis.pre_cod_years,
        opex_escalation_pct=5,
        lkr_per_usd=333.79,
        construction_years=0,
    )
    assert flows[-1] == pytest.approx(-unit / total * engine)


@pytest.mark.parametrize(
    "change",
    ["duplicate", "missing", "total", "ratio", "overhead", "share", "nonfinite"],
)
def test_reject_inconsistent_sources(change: str) -> None:
    """Refuse inconsistent, duplicated or invalid O&M source data."""
    raw = deepcopy(scenario())
    parts = raw["opex"]["currency_split"]["components"]
    ratio, overhead = 1.1, 150000
    if change == "duplicate":
        parts.append(deepcopy(parts[0]))
    if change == "missing":
        parts.pop()
    if change == "total":
        raw["opex"]["usd_per_year"] += 1
    if change == "ratio":
        ratio = 1.2
    if change == "overhead":
        overhead += 1
    if change == "share":
        parts[0]["usd_share"] = 0.1
    if change == "nonfinite":
        parts[0]["usd_per_unit_year"] = float("nan")
    with pytest.raises(ValueError):
        sz.project_opex_basis(raw, ratio, overhead)


@pytest.mark.parametrize("field", ["opex", "currency_split", "components"])
def test_missing_source_names_its_contract(field: str) -> None:
    """Missing source blocks produce actionable value errors at the boundary."""
    raw = scenario()
    if field == "opex":
        del raw["opex"]
    elif field == "currency_split":
        del raw["opex"][field]
    else:
        del raw["opex"]["currency_split"][field]
    with pytest.raises(ValueError, match="opex|components"):
        sz.project_opex_basis(raw, 1.1, 150000)


@pytest.mark.parametrize("name", [["solar_om"], {"name": "solar_om"}, None, 17, ""])
def test_malformed_component_name_is_an_actionable_source_error(name: Any) -> None:
    """Validate YAML name scalars before using them as set or lookup keys."""
    raw = scenario()
    raw["opex"]["currency_split"]["components"][0]["name"] = name
    with pytest.raises(ValueError, match=r"components\[0\]\.name"):
        sz.project_opex_basis(raw, 1.1, 150000)


@pytest.mark.parametrize(
    "field,value",
    [
        ("usd_per_unit_year", None),
        ("usd_share", {}),
        ("units", [22000]),
        ("usd_per_unit_year", "bad"),
        ("units", 10**400),
    ],
)
def test_malformed_component_numbers_name_the_source(field: str, value: Any) -> None:
    """Refuse malformed numeric cells through the O&M source error contract."""
    raw = scenario()
    raw["opex"]["currency_split"]["components"][0][field] = value
    with pytest.raises(ValueError, match="O&M"):
        sz.project_opex_basis(raw, 1.1, 150000)
