"""The capex price date reaches the per-technology capex and is disclosed in batch results.

By the ruling of 2026-11-15, a declared ``capex.price_basis`` escalates each
``generation.technologies.<name>.capex_usd`` by the factor the financed total takes
(#1591 A-4(2), carried under #1578). Before it, the per-technology capex stayed at the
price year while the financed total was escalated, so on the committed dated solar + BESS
scenario the batch LCOS view priced the battery in 2026 dollars, and the per-technology
work-breakdown allocated price-year amounts against an escalated total. The CASPER
gateway's work-breakdown also read the raw scenario, so it reported the price-year figure
as the financed capex. #1578 next-20 item 5 asks for the price-basis disclosure in the
batch results too.

``TEST-01`` oracles that did not originate in this change: :func:`compute_lcos_suite` on
a hand-escalated copy of the scenario (the LCOS view must equal it), the scenario's own
stated amounts times :func:`capex_escalation_factor`, and :func:`automatic_escalation`
for the disclosure the pipeline result already carries.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_casper_tail_risk
from analytics.scenario_analytics import ScenarioAnalytics
from analytics.storage_headline import apply_headline_storage_option
from finance.bess_lcos import compute_lcos_suite
from finance.capex_price_basis import (
    APPLIED_KEY,
    AUTO_KEY,
    TECH_KEY,
    UnappliedCapexPriceBasisError,
    apply_capex_price_basis,
    automatic_escalation,
    capex_escalation_factor,
)

ROOT = Path(__file__).resolve().parents[2]
SOLAR_BESS = ROOT / "scenarios/blue_whale_solar_bess_lot5b_2026.yaml"
WIND = ROOT / "scenarios/blue_whale_wind_lot5b_2026.yaml"
LOGGER = "finance.capex_price_basis"


def _load(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _factor(cfg: Dict[str, Any]) -> float:
    resolved = capex_escalation_factor(cfg)
    assert resolved is not None
    return float(resolved["factor"])


def _cfg() -> Dict[str, Any]:
    """A dated capex with a one-period build to a 2028 COD: factor 1.05."""
    return {
        "capex": {
            "usd_total": 1_000_000.0,
            "price_basis": {"price_year": 2026, "escalation_pct": 5.0},
        },
        "Financing_Terms": {"construction_periods": 1},
        "project": {"cod_year": 2028},
        "generation": {
            "technologies": {
                "wind": {"type": "wind", "capex_usd": 600_000},
                "solar": {"type": "solar", "capex_usd": "250000"},
                "bess_1": {
                    "type": "bess",
                    "capex_usd": 150_000.0,
                    "revenue": {
                        "augmentation_schedule": [{"year": 10, "capex_usd": 40_000.0}]
                    },
                },
                "notes": "not a technology block",
            }
        },
    }


def test_each_technology_capex_takes_the_factor_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _cfg()
    before = copy.deepcopy(cfg)
    factor = _factor(cfg)
    assert factor == pytest.approx(1.05)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        out = apply_capex_price_basis(cfg)
    assert cfg == before  # the caller's config is not changed
    techs = out["generation"]["technologies"]
    assert techs["wind"]["capex_usd"] == pytest.approx(600_000 * factor)
    assert techs["solar"]["capex_usd"] == pytest.approx(250_000 * factor)
    assert techs["bess_1"]["capex_usd"] == pytest.approx(150_000 * factor)
    # A mid-life top-up is spent in its own operating year, not at the draws.
    assert techs["bess_1"]["revenue"]["augmentation_schedule"] == [
        {"year": 10, "capex_usd": 40_000.0}
    ]
    assert techs["notes"] == "not a technology block"
    applied = out["capex"][APPLIED_KEY]
    assert applied[TECH_KEY] == {
        "generation.technologies.wind.capex_usd": 600_000.0,
        "generation.technologies.solar.capex_usd": 250_000.0,
        "generation.technologies.bess_1.capex_usd": 150_000.0,
    }
    # A component of the declared total, escalated by the block itself: recorded, but
    # not an automatic escalation of another capex key, so no warning or disclosure.
    assert AUTO_KEY not in applied
    assert automatic_escalation(out) is None
    assert not [r for r in caplog.records if r.name == LOGGER]


def test_technology_capex_is_escalated_once() -> None:
    once = apply_capex_price_basis(_cfg())
    assert apply_capex_price_basis(once) == once


def test_an_undated_config_keeps_its_technology_capex() -> None:
    cfg = _cfg()
    cfg["capex"].pop("price_basis")
    out = apply_capex_price_basis(cfg)
    assert out["generation"] == cfg["generation"]


def test_technology_capex_alone_is_not_a_financed_amount() -> None:
    cfg = _cfg()
    cfg["capex"].pop("usd_total")
    with pytest.raises(ValueError, match="found no capex amount to escalate"):
        apply_capex_price_basis(cfg)


def test_a_non_numeric_technology_capex_is_left_as_stated() -> None:
    cfg = _cfg()
    cfg["generation"]["technologies"]["wind"]["capex_usd"] = "tbd"
    out = apply_capex_price_basis(cfg)
    assert out["generation"]["technologies"]["wind"]["capex_usd"] == "tbd"
    assert (
        "generation.technologies.wind.capex_usd"
        not in out["capex"][APPLIED_KEY][TECH_KEY]
    )


def _batch(path: Path) -> Any:
    return ScenarioAnalytics(scenarios_dir=path.parent)._run_single(path)


def test_dated_solar_bess_lcos_prices_the_battery_at_the_draws() -> None:
    """The ruling's KPI move: the batch LCOS view reads the escalated BESS capex."""
    raw = _load(SOLAR_BESS)
    factor = _factor(raw)
    assert factor == pytest.approx(1.1025)  # 2026 prices, close 2028, 5%/yr
    result = _batch(SOLAR_BESS)
    assert result.fail_reason is None
    (view,) = result.lcos
    project_years = len(result.annual_rows)

    # Oracle: the LCOS engine itself on a copy whose BESS capex is escalated by hand.
    by_hand = copy.deepcopy(raw)
    stated = float(by_hand["generation"]["technologies"]["bess_1"]["capex_usd"])
    by_hand["generation"]["technologies"]["bess_1"]["capex_usd"] = stated * factor
    # #1899: the LCOS resolver refuses an unapplied price date, so the hand-escalated
    # copy escalates the project total too and drops the declaration.
    by_hand["capex"]["usd_total"] = float(by_hand["capex"]["usd_total"]) * factor
    del by_hand["capex"]["price_basis"]
    (expected,) = compute_lcos_suite(
        by_hand, wacc=result.discount_rate, project_years=project_years
    )
    assert view["pv_capex_usd"] == pytest.approx(stated * factor, rel=1e-12)
    assert view["lcos_usd_per_mwh"] == pytest.approx(
        expected.lcos_usd_per_mwh, rel=1e-12
    )
    # The stated price-year figures, without the declaration (the pre-#1578 reading).
    stated_only = copy.deepcopy(raw)
    del stated_only["capex"]["price_basis"]
    (at_price_year,) = compute_lcos_suite(
        stated_only, wacc=result.discount_rate, project_years=project_years
    )
    # #1899: the raw scenario, with its price date unapplied, is refused.
    with pytest.raises(UnappliedCapexPriceBasisError):
        compute_lcos_suite(raw, wacc=result.discount_rate, project_years=project_years)
    assert view["lcos_usd_per_mwh"] > at_price_year.lcos_usd_per_mwh
    # A committed scenario states its capex only through usd_total and the technology
    # blocks, so nothing is escalated automatically and nothing is disclosed.
    assert result.capex_price_basis is None


def test_batch_results_carry_the_automatic_escalation_disclosure(
    tmp_path: Path,
) -> None:
    """#1578 next-20 item 5: the batch result discloses what the pipeline discloses."""
    wind = _load(WIND)
    wind.setdefault("finance", {})["capex_usd"] = float(wind["capex"]["usd_total"])
    path = tmp_path / "wind_finance_capex.yaml"
    path.write_text(yaml.safe_dump(wind, sort_keys=False), encoding="utf-8")

    result = _batch(path)
    assert result.fail_reason is None
    expected = automatic_escalation(apply_capex_price_basis(wind))
    assert expected is not None
    assert result.capex_price_basis == expected
    assert result.capex_price_basis["keys_at_price_year"] == {
        "finance.capex_usd": float(wind["capex"]["usd_total"])
    }

    _, _, summary = ScenarioAnalytics(scenarios_dir=tmp_path).run()
    assert summary.batch_summary["capex_price_basis"] == [
        {"scenario": "wind_finance_capex", "disclosure": expected}
    ]


def test_a_batch_without_automatic_escalation_lists_no_disclosure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wind.yaml"
    path.write_text(WIND.read_text(encoding="utf-8"), encoding="utf-8")
    _, _, summary = ScenarioAnalytics(scenarios_dir=tmp_path).run()
    assert summary.n_success == 1
    assert summary.batch_summary["capex_price_basis"] == []


@pytest.mark.parametrize("path", [SOLAR_BESS, WIND], ids=["solar_bess", "wind"])
def test_gateway_work_breakdown_reconciles_to_the_dated_total(path: Path) -> None:
    """The CASPER gateway's WBS reads the configuration the engine financed."""
    raw = _load(path)
    factor = _factor(raw)
    wbs = evaluate_with_casper_tail_risk(config_path=str(path)).multi_tech_wbs
    assert wbs is not None
    # #1823: the financed total includes a declared headline battery's capex.
    assert wbs.financed_capex_usd == pytest.approx(
        float(apply_headline_storage_option(raw)["capex"]["usd_total"]) * factor,
        rel=1e-12,
    )
    stated = {
        name: float(block["capex_usd"])
        for name, block in raw["generation"]["technologies"].items()
    }
    for name, amount in stated.items():
        assert wbs.technologies[name].capex_usd == pytest.approx(
            amount * factor, rel=1e-12
        )
    # The unallocated residual (grid, civils, development) is escalated with them.
    assert wbs.capex_residual_usd == pytest.approx(
        (float(raw["capex"]["usd_total"]) - sum(stated.values())) * factor, rel=1e-9
    )
