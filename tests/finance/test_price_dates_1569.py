"""Capex and opex price dates (#1569): closed forms, guards and the committed scenarios.

``capex.price_basis`` escalates ``capex.usd_total`` from its price year to the construction
draws; ``opex.price_year`` escalates every opex line from its price year, so operating year 1
(``project.cod_year``) carries ``cod_year - price_year`` years before its own. A scenario that
declares neither is unchanged.

``TEST-01`` oracles that did not originate in this change:

* the closed forms, written out here: one draw ``C * (1 + e) ** (close - price)``; phased
  draws ``C * sum_i w_i (1 + e) ** (close + i - price)``; opex
  ``O * (1 + e) ** (t + cod - price)``;
* the committed scenarios' own YAML: their price dates, COD and O&M index start;
* responsiveness guards: the escalation rate and the price year move the engine's capex,
  opex and project NPV.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from finance.capex_price_basis import (
    APPLIED_KEY,
    apply_capex_price_basis,
    capex_escalation_factor,
)
from finance.cashflow_v14 import build_annual_rows
from finance.cashflow_v14_params import _resolve_opex_pre_cod_years

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
WIND = SCENARIOS / "blue_whale_wind_lot5b_2026.yaml"
SOLAR_BESS = SCENARIOS / "blue_whale_solar_bess_lot5b_2026.yaml"
HYBRID = SCENARIOS / "blue_whale_hybrid_lot5b_2026.yaml"

CAPEX = 1_000_000.0


def _capex_cfg(
    *,
    price_year: Any = 2026,
    escalation_pct: Any = 5.0,
    cod_year: Any = 2028,
    periods: int | None = 1,
    schedule: list[float] | None = None,
    **block_extra: Any,
) -> Dict[str, Any]:
    terms: Dict[str, Any] = {}
    if periods is not None:
        terms["construction_periods"] = periods
    if schedule is not None:
        terms["construction_schedule"] = schedule
    cfg: Dict[str, Any] = {
        "capex": {
            "usd_total": CAPEX,
            "price_basis": {
                "price_year": price_year,
                "escalation_pct": escalation_pct,
                **block_extra,
            },
        },
        "Financing_Terms": terms,
    }
    if cod_year is not None:
        cfg["project"] = {"cod_year": cod_year}
    return cfg


def _factor(cfg: Dict[str, Any]) -> float:
    resolved = capex_escalation_factor(cfg)
    assert resolved is not None
    return float(resolved["factor"])


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


# --- Capex: closed forms ---------------------------------------------------------


def test_one_period_build_escalates_to_the_year_before_cod() -> None:
    """2026 price, 2028 COD, one period: the draw is in 2027, one year at 5%."""
    out = apply_capex_price_basis(_capex_cfg())

    assert out["capex"]["usd_total"] == pytest.approx(CAPEX * 1.05, rel=1e-15)
    applied = out["capex"][APPLIED_KEY]
    assert applied["usd_total_at_price_year"] == CAPEX
    assert applied["close_year"] == 2027
    assert applied["factor"] == pytest.approx(1.05, rel=1e-15)
    assert "price_basis" not in out["capex"]


def test_phased_draws_escalate_each_share_to_its_own_year() -> None:
    """Two periods on the [40, 60] placeholder: 40% in 2026, 60% in 2027."""
    cfg = _capex_cfg(price_year=2025, periods=2)
    expected = 0.4 * 1.05 ** (2026 - 2025) + 0.6 * 1.05 ** (2027 - 2025)

    assert _factor(cfg) == pytest.approx(expected, rel=1e-15)


def test_an_explicit_phasing_is_normalised() -> None:
    """A schedule in any unit is read as shares: [1, 3] is 25% / 75%."""
    cfg = _capex_cfg(periods=2, schedule=[1.0, 3.0], cod_year=2029)
    expected = 0.25 * 1.05 ** (2027 - 2026) + 0.75 * 1.05 ** (2028 - 2026)

    assert _factor(cfg) == pytest.approx(expected, rel=1e-15)


def test_a_zero_period_build_escalates_to_cod() -> None:
    cfg = _capex_cfg(periods=0)

    assert _factor(cfg) == pytest.approx(1.05**2, rel=1e-15)


def test_price_at_close_and_zero_rate_leave_capex_unchanged() -> None:
    assert _factor(_capex_cfg(price_year=2027)) == 1.0
    assert _factor(_capex_cfg(escalation_pct=0)) == 1.0


def test_applying_twice_escalates_once() -> None:
    once = apply_capex_price_basis(_capex_cfg())
    twice = apply_capex_price_basis(once)

    assert twice == once


def test_a_config_without_the_block_is_returned_unchanged() -> None:
    cfg = _capex_cfg()
    del cfg["capex"]["price_basis"]
    before = copy.deepcopy(cfg)

    assert apply_capex_price_basis(cfg) == before
    assert capex_escalation_factor(cfg) is None
    assert capex_escalation_factor({"capex": None}) is None


@pytest.mark.parametrize("path", sorted(SCENARIOS.glob("*.yaml")), ids=lambda p: p.name)
def test_undeclared_committed_scenarios_are_untouched(path: Path) -> None:
    """Every scenario without the block passes through with no key changed."""
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        pytest.skip("not parseable YAML")
    if not isinstance(cfg, dict):
        pytest.skip("not a single-document mapping")
    capex = cfg.get("capex")
    if isinstance(capex, dict) and "price_basis" in capex:
        assert path in (WIND, SOLAR_BESS)
        return
    assert apply_capex_price_basis(cfg) == cfg


# --- Capex: refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"price_year": 2026.0}, "whole calendar year"),
        ({"price_year": True}, "whole calendar year"),
        ({"price_year": None}, "whole calendar year"),
        ({"escalation_pct": "5"}, "must be a number"),
        ({"escalation_pct": True}, "must be a number"),
        ({"escalation_pct": 100.0}, "out of range"),
        ({"escalation_pct": -100.0}, "out of range"),
        ({"price_year": 2028}, "after financial close"),
        ({"cod_year": None}, "needs project.cod_year"),
        ({"rate": 5.0}, "allowed"),
    ],
)
def test_malformed_blocks_are_refused(change: Dict[str, Any], match: str) -> None:
    kwargs: Dict[str, Any] = {"price_year": 2026, "escalation_pct": 5.0}
    kwargs.update(change)
    with pytest.raises(ValueError, match=match):
        capex_escalation_factor(_capex_cfg(**kwargs))


def test_a_price_year_that_contradicts_the_cost_basis_year_is_refused() -> None:
    cfg = _capex_cfg()
    cfg["capex"]["cost_basis_year"] = 2025
    with pytest.raises(ValueError, match="one price date"):
        capex_escalation_factor(cfg)
    cfg["capex"]["cost_basis_year"] = 2026
    assert capex_escalation_factor(cfg) is not None


def test_a_phasing_of_the_wrong_length_is_refused() -> None:
    with pytest.raises(ValueError, match="one capex phasing entry per construction"):
        capex_escalation_factor(_capex_cfg(periods=2, schedule=[100.0]))
    with pytest.raises(ValueError, match="non-negative with a positive sum"):
        capex_escalation_factor(_capex_cfg(periods=2, schedule=[0.0, 0.0]))


def test_the_block_needs_a_numeric_usd_total() -> None:
    cfg = _capex_cfg()
    cfg["capex"]["usd_total"] = "1e6"
    with pytest.raises(ValueError, match="escalates capex.usd_total"):
        apply_capex_price_basis(cfg)
    with pytest.raises(ValueError, match="must be a mapping"):
        capex_escalation_factor({"capex": {"price_basis": [2026]}})


# --- Opex: closed forms and refusals ----------------------------------------------


@pytest.mark.parametrize(
    ("opex", "project", "expected"),
    [
        ({"price_year": 2026}, {"cod_year": 2028}, 2),
        ({"price_year": 2028}, {"cod_year": 2028}, 0),
        ({}, {"cod_year": 2028}, 0),
        ({}, {}, 0),
    ],
)
def test_opex_steps_before_cod(
    opex: Dict[str, Any], project: Dict[str, Any], expected: int
) -> None:
    assert _resolve_opex_pre_cod_years({"opex": opex, "project": project}) == expected


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({"opex": {"price_year": 2029}, "project": {"cod_year": 2028}}, "after"),
        ({"opex": {"price_year": 2026}, "project": {}}, "needs project.cod_year"),
        ({"opex": {"price_year": "2026"}, "project": {"cod_year": 2028}}, "whole"),
    ],
)
def test_opex_price_dates_that_cannot_be_used_are_refused(
    raw: Dict[str, Any], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        _resolve_opex_pre_cod_years(raw)


def test_single_currency_opex_escalates_from_its_price_year() -> None:
    """On the wind scenario without its split: O * 1.05 ** (t + 2028 - 2026), bit-exact."""
    cfg = _yaml(WIND)
    del cfg["opex"]["currency_split"]
    total = float(cfg["opex"]["usd_per_year"])
    rows = build_annual_rows(cfg)
    for t, row in enumerate(rows):
        assert row["opex_usd"] == total * 1.05 ** (t + 2028 - 2026)

    cfg["opex"]["price_year"] = 2028
    at_cod = build_annual_rows(cfg)
    assert at_cod[0]["opex_usd"] == total
    assert rows[0]["opex_usd"] > at_cod[0]["opex_usd"]


# --- The committed Blue Whale scenarios -------------------------------------------


@pytest.mark.parametrize("path", [WIND, SOLAR_BESS], ids=lambda p: p.stem)
def test_blue_whale_dates_agree_with_each_other(path: Path) -> None:
    """One 2026 price date for capex and opex; the O&M index starts there too."""
    cfg = _yaml(path)
    cod = cfg["project"]["cod_year"]
    price = cfg["capex"]["price_basis"]["price_year"]

    assert price == cfg["capex"]["cost_basis_year"] == cfg["opex"]["price_year"]
    assert cfg["capex"]["price_basis"]["escalation_pct"] == (
        cfg["opex"]["currency_split"]["lkr_escalation_pct"]
    )
    assert cfg["tariff"]["om_indexation"]["pre_operation_years"] == cod - price
    assert _resolve_opex_pre_cod_years(cfg) == cod - price


def test_superseded_hybrid_declares_no_price_date() -> None:
    cfg = _yaml(HYBRID)

    assert "price_basis" not in cfg["capex"]
    assert "price_year" not in cfg["opex"]
    assert cfg["tariff"]["om_indexation"]["pre_operation_years"] == 0


@pytest.mark.parametrize(
    ("path", "years"),
    [(WIND, 2027 - 2026), (SOLAR_BESS, 2028 - 2026)],
    ids=["wind", "solar_bess"],
)
def test_engine_spends_the_escalated_capex(path: Path, years: int) -> None:
    """The engine's capex use is the stated total escalated to the year before COD."""
    stated = _yaml(path)["capex"]["usd_total"]
    full = evaluate_with_overrides(str(path), overrides={}, return_full_result=True)
    assert isinstance(full, dict)
    debt = full["debt_result"]
    assert isinstance(debt, dict)
    uses = debt["funding"]["sources_and_uses"]["uses"]

    assert uses["capex_usd"] == pytest.approx(stated * 1.05**years, abs=0.01)


def test_wind_npv_responds_to_the_price_dates() -> None:
    """Responsiveness: a later price date or a lower rate raises the project NPV."""
    base = evaluate_with_overrides(str(WIND), overrides={})
    no_escalation = evaluate_with_overrides(
        str(WIND), overrides={"capex.price_basis.escalation_pct": 0.0}
    )
    opex_at_cod = evaluate_with_overrides(
        str(WIND), overrides={"opex.price_year": 2028}
    )

    assert no_escalation["project_npv"] > base["project_npv"]
    assert opex_at_cod["project_npv"] > base["project_npv"]
