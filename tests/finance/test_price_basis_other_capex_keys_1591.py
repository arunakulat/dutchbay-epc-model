"""Capex amounts beside ``capex.usd_total`` take the price-year factor (#1591 D-1/A-1).

``capex.price_basis`` (#1569) escalated only ``capex.usd_total``. The engine also reads
capex amounts under other keys, some of them in place of ``usd_total``, so a scenario
that stated one of them skipped the price date silently: the #1591 domain lane measured
Blue Whale wind with ``finance.capex_usd`` at project NPV 2,004,538 against the dated
1,398,803. The owner ruled on 2026-11-14 to apply the factor to those amounts
automatically and to say so clearly. These tests pin both halves.

``TEST-01`` oracles that did not originate in this change: the capex resolvers
themselves (``finance.debt_v14._extract_capex_usd`` and
``analytics.core.metrics._derive_capex_usd``), which must read ``factor x`` what they
read before, and the committed Blue Whale wind scenario, whose dated KPIs a scenario
that states its capex under another key must now reproduce.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.core.metrics import _derive_capex_usd
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from finance.capex_price_basis import (
    APPLIED_KEY,
    AUTO_KEY,
    apply_capex_price_basis,
    automatic_escalation,
    capex_escalation_factor,
)
from finance.debt_v14 import _extract_capex_usd

WIND = Path(__file__).resolve().parents[2] / "scenarios/blue_whale_wind_lot5b_2026.yaml"
STATED = 1_000_000.0
LOGGER = "finance.capex_price_basis"


def _cfg() -> Dict[str, Any]:
    """A dated capex with a one-period build to a 2028 COD: factor 1.05."""
    return {
        "capex": {
            "usd_total": STATED,
            "price_basis": {"price_year": 2026, "escalation_pct": 5.0},
        },
        "Financing_Terms": {"construction_periods": 1},
        "project": {"cod_year": 2028},
    }


def _factor(cfg: Dict[str, Any]) -> float:
    resolved = capex_escalation_factor(cfg)
    assert resolved is not None
    return float(resolved["factor"])


def _set(cfg: Dict[str, Any], path: str, value: Any) -> None:
    *sections, key = path.split(".")
    node = cfg
    for section in sections:
        node = node.setdefault(section, {})
    node[key] = value


def _get(cfg: Dict[str, Any], path: str) -> Any:
    node: Any = cfg
    for part in path.split("."):
        node = node[part]
    return node


# Every capex amount key the engine reads besides the canonical capex.usd_total.
OTHER_KEYS = [
    "finance.capex_usd",
    "finance.capex_total_usd",
    "capex.epc_usd",
    "capex.capex_total_usd",
    "capex.total_capex_usd",
    "capex.total_capex",
    "capex.lkr_total",
    "capex.USD_TOTAL",
    "costs.capex_total_usd",
    "costs.capex_usd",
    "costs.total_capex_usd",
    "costs.total_capex",
    "tax.depreciable_capex_lkr",
    "tax.dep_base_lkr",
    "Finance.CAPEX_USD",
    # The equity distribution's flat lookup reads the project section too (#1704 review).
    "project.capex_usd",
    "project.capex_total_usd",
    "Project.total_capex_usd",
]
TOP_LEVEL_KEYS = ["capex_usd_total", "capex_total_usd", "total_capex_usd"]


@pytest.mark.parametrize("path", OTHER_KEYS + TOP_LEVEL_KEYS)
def test_each_other_capex_amount_takes_the_factor_and_is_disclosed(
    path: str, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = _cfg()
    _set(cfg, path, 400_000)
    before = copy.deepcopy(cfg)
    factor = _factor(cfg)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        out = apply_capex_price_basis(cfg)
    assert cfg == before  # the caller's config is not changed
    assert _get(out, path) == pytest.approx(400_000 * factor)
    assert out["capex"]["usd_total"] == pytest.approx(STATED * factor)
    applied = out["capex"][APPLIED_KEY]
    assert applied[AUTO_KEY] == {path: 400_000.0}
    assert applied["usd_total_at_price_year"] == STATED
    warnings = [r for r in caplog.records if r.name == LOGGER]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert path in warnings[0].getMessage()
    assert "AUTOMATICALLY" in warnings[0].getMessage()


@pytest.mark.parametrize(
    "path", ["finance.capex_usd", "tax.dep_base_lkr", "Project.capex_usd"]
)
@pytest.mark.parametrize("stated", ["400000", " 4e5 ", "400000.0"])
def test_a_numeric_string_amount_takes_the_factor(path: str, stated: str) -> None:
    """The capex readers parse a numeric string, so it is an amount (#1704 review)."""
    cfg = _cfg()
    _set(cfg, path, stated)
    factor = _factor(cfg)
    out = apply_capex_price_basis(cfg)
    assert _get(out, path) == pytest.approx(400_000 * factor)
    assert out["capex"][APPLIED_KEY][AUTO_KEY] == {path: 400_000.0}


def test_project_capex_alias_reaches_the_equity_capex_reader() -> None:
    """Oracle: the equity distribution's own capex lookup reads factor x the alias."""
    from finance.equity_distribution_v14_hydra import _extract_capex_usd as equity_capex

    cfg = _cfg()
    cfg["capex"].pop("usd_total")
    _set(cfg, "Project.capex_usd", 2_500_000)
    plain = copy.deepcopy(cfg)
    plain["capex"].pop("price_basis")
    out = apply_capex_price_basis(cfg)
    assert equity_capex(out) == pytest.approx(_factor(cfg) * equity_capex(plain))


def test_breakdown_line_items_take_the_factor_with_and_without_qra() -> None:
    cfg = _cfg()
    cfg["capex"]["derive_from_breakdown"] = True
    cfg["capex"]["breakdown"] = {
        "turbine_usd": 700_000,
        "bop_usd": 300_000.0,
        "note": "text is not an amount",
        "included": True,
    }
    factor = _factor(cfg)
    out = apply_capex_price_basis(cfg)
    items = out["capex"]["breakdown"]
    assert items["turbine_usd"] == pytest.approx(700_000 * factor)
    assert items["bop_usd"] == pytest.approx(300_000 * factor)
    assert items["note"] == "text is not an amount" and items["included"] is True
    assert out["capex"][APPLIED_KEY][AUTO_KEY] == {
        "capex.breakdown.turbine_usd": 700_000.0,
        "capex.breakdown.bop_usd": 300_000.0,
    }
    # The 0.5% breakdown cross-check holds, because usd_total moved with it.
    assert _extract_capex_usd(out) == pytest.approx(STATED * factor)
    qra = copy.deepcopy(cfg)
    qra["capex"]["contingency"] = {"method": "qra", "base_cost_uncertainty_pct": 10.0}
    plain = copy.deepcopy(qra)
    plain["capex"].pop("price_basis")
    assert _extract_capex_usd(apply_capex_price_basis(qra)) == pytest.approx(
        factor * _extract_capex_usd(plain)
    )


@pytest.mark.parametrize(
    "path",
    ["finance.capex_usd", "capex.total_capex", "costs.capex_usd", "capex_total_usd"],
)
def test_the_capex_resolvers_read_the_dated_amount(path: str) -> None:
    """Debt sizing and the NPV base read factor x their undated amount (D-1/A-1)."""
    cfg = _cfg()
    cfg["capex"].pop("usd_total")
    _set(cfg, path, 2_500_000)
    plain = copy.deepcopy(cfg)
    plain["capex"].pop("price_basis")
    factor = _factor(cfg)
    out = apply_capex_price_basis(cfg)
    assert _extract_capex_usd(out) == pytest.approx(factor * _extract_capex_usd(plain))
    assert _derive_capex_usd(out) == pytest.approx(factor * _derive_capex_usd(plain))
    assert "usd_total" not in out["capex"]
    assert "usd_total_at_price_year" not in out["capex"][APPLIED_KEY]


def test_without_other_amounts_nothing_new_is_written_or_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _cfg()
    cfg["capex"]["capex_per_kw_usd"] = 105.0  # a rate, not an amount
    cfg["finance"] = {"capex_usd": "n/a"}  # not a number the resolvers would use
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        out = apply_capex_price_basis(cfg)
    assert AUTO_KEY not in out["capex"][APPLIED_KEY]
    assert out["capex"]["capex_per_kw_usd"] == 105.0
    assert out["finance"] == {"capex_usd": "n/a"}
    assert not [r for r in caplog.records if r.name == LOGGER]


def test_applying_twice_escalates_every_amount_once() -> None:
    cfg = _cfg()
    cfg["finance"] = {"capex_usd": 400_000}
    once = apply_capex_price_basis(cfg)
    assert apply_capex_price_basis(once) == once


def test_a_block_with_no_capex_amount_is_refused() -> None:
    cfg = _cfg()
    cfg["capex"].pop("usd_total")
    with pytest.raises(ValueError, match="found no capex amount to escalate"):
        apply_capex_price_basis(cfg)


def _wind() -> Dict[str, Any]:
    data = yaml.safe_load(WIND.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _kpis(result: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("project_npv", "project_irr", "equity_npv", "equity_irr", "min_dscr")
    return {key: result["kpis"].get(key) for key in keys}


def test_wind_with_capex_under_other_keys_matches_the_dated_case() -> None:
    """The #1591 probe: another capex key now gives the dated wind KPIs, disclosed."""
    wind = _wind()
    stated = float(wind["capex"]["usd_total"])
    fx = float(wind["fx"]["start_lkr_per_usd"])
    dated = run_v14_pipeline(copy.deepcopy(wind))
    assert "capex_price_basis" not in dated
    variants = {
        "finance.capex_usd": stated,
        "tax.depreciable_capex_lkr": stated * fx,
    }
    for path, value in variants.items():
        cfg = copy.deepcopy(wind)
        _set(cfg, path, value)
        result = run_v14_pipeline(cfg)
        assert _kpis(result) == pytest.approx(_kpis(dated), rel=1e-12), path
        disclosure = result["capex_price_basis"]
        assert disclosure["automatically_applied"] is True
        assert disclosure["keys_at_price_year"] == {path: value}
        assert disclosure["factor"] == pytest.approx(1.05)
        assert path in disclosure["warning"]
        assert disclosure["warning"] in result["metrics"]["validation_warnings"]


def test_the_warning_says_what_was_escalated_and_how() -> None:
    """The #1704 review wording: beside or instead of usd_total, and the LKR caveat."""
    cfg = _cfg()
    cfg["finance"] = {"capex_usd": 400_000}
    cfg["tax"] = {"dep_base_lkr": 120_000_000}
    out = apply_capex_price_basis(cfg)
    disclosure = automatic_escalation(out)
    assert disclosure is not None
    assert disclosure["warning"] == (
        "capex.price_basis: the price-year factor 1.050000 (from 2026) was applied "
        "AUTOMATICALLY to finance.capex_usd, tax.dep_base_lkr: capex amounts stated "
        "beside or instead of capex.usd_total (a capex.breakdown is escalated to stay "
        "consistent with it). Each is taken as stated at the price year; LKR amounts "
        "keep the FX they were stated at; the stated amounts are kept in "
        "capex.price_basis_applied.automatically_escalated."
    )
