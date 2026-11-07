"""Opex currency split (``opex.currency_split``): closed forms, guards and the committed data.

The owner's rule (2026-11-02): capex is fixed in LKR at project start, debt is LKR, and a
share of opex is USD. The engine reads the split from the scenario YAML, so nothing here is
specific to one site: the fixtures are the committed Blue Whale wind scenario with its
inputs moved by the test.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from finance.cashflow_v14 import (
    _prepare_cashflow_context,
    build_annual_rows,
    build_annual_rows_efficient,
)
from finance.cashflow_v14_params import (
    _build_cashflow_params,
    _resolve_opex_currency_split,
    opex_component_amounts_usd,
)
from finance.cashflow_v14_production import opex_for_year

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
SOLAR_BESS = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"


def _cfg() -> Dict[str, Any]:
    data = yaml.safe_load(WIND.read_text())
    assert isinstance(data, dict)
    return data


def _split(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = cfg["opex"]["currency_split"]
    assert isinstance(out, dict)
    return out


def _unsplit(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    del out["opex"]["currency_split"]
    return out


def _opex_lkr(rows: List[Dict[str, float]]) -> List[float]:
    return [r["opex_lkr"] for r in rows]


# ---------------------------------------------------------------------------
# No split: the original path, byte-identical
# ---------------------------------------------------------------------------
def test_without_a_split_the_opex_line_is_the_original_expression() -> None:
    cfg = _unsplit(_cfg())
    cfg["fx"]["annual_depr"] = 0.05
    rows = build_annual_rows(cfg)
    total = float(cfg["opex"]["usd_per_year"])
    esc = 0.05  # opex.escalation_pct 5.0, the single-currency reading
    for t, row in enumerate(rows):
        usd = total * (1.0 + esc) ** t
        assert row["opex_usd"] == usd  # bit-exact
        assert row["opex_lkr"] == usd * (1.0 + 0.0) * row["fx_rate"]


def test_a_null_split_is_the_same_as_no_split() -> None:
    cfg = _unsplit(_cfg())
    null = copy.deepcopy(cfg)
    null["opex"]["currency_split"] = None
    assert build_annual_rows(cfg) == build_annual_rows(null)


# ---------------------------------------------------------------------------
# The split: closed forms
# ---------------------------------------------------------------------------
def test_split_opex_matches_its_closed_form_on_the_own_fx_path() -> None:
    cfg = _cfg()
    rows = build_annual_rows(cfg)
    total = float(cfg["opex"]["usd_per_year"])
    s = 0.7 * 350_000.0 / 500_000.0
    spot = float(cfg["fx"]["start_lkr_per_usd"])
    construction = 2  # Financing_Terms declares no construction period: the default 2
    for t, row in enumerate(rows):
        usd_fx = spot * 1.0589 ** (construction + t)
        expected = total * s * 1.025**t * usd_fx + total * (1.0 - s) * spot * 1.05**t
        assert row["opex_lkr"] == pytest.approx(expected, rel=1e-12)
        # The model curve stays flat (constant-LKR reporting), so the USD view is LKR / spot.
        assert row["fx_rate"] == spot
        assert row["opex_usd"] == pytest.approx(row["opex_lkr"] / spot, rel=1e-12)


def test_both_row_builders_agree_on_the_split() -> None:
    cfg = _cfg()
    a = build_annual_rows(cfg)
    b = build_annual_rows_efficient(cfg)
    assert _opex_lkr(a) == _opex_lkr(b)
    assert [r["opex_usd"] for r in a] == [r["opex_usd"] for r in b]
    assert [r["ebitda_lkr"] for r in a] == [r["ebitda_lkr"] for r in b]


def test_all_usd_split_on_the_model_curve_reproduces_the_single_currency_path() -> None:
    cfg = _unsplit(_cfg())
    cfg["fx"]["annual_depr"] = 0.0589
    cfg["opex"]["escalation_pct"] = 2.5
    split = copy.deepcopy(cfg)
    split["opex"]["currency_split"] = {
        "usd_share": 1.0,
        "usd_escalation_pct": 2.5,
        "lkr_escalation_pct": 2.5,
    }
    ref, got = build_annual_rows(cfg), build_annual_rows(split)
    for r, g in zip(ref, got, strict=True):
        assert g["opex_lkr"] == pytest.approx(r["opex_lkr"], rel=1e-12)
        assert g["opex_usd"] == pytest.approx(r["opex_usd"], rel=1e-12)


def test_the_lkr_share_ignores_fx_and_the_usd_share_follows_it() -> None:
    cfg = _unsplit(_cfg())
    cfg["opex"]["currency_split"] = {
        "usd_share": 0.0,
        "usd_escalation_pct": 2.5,
        "lkr_escalation_pct": 5.0,
    }
    flat = build_annual_rows(cfg)
    deprec = copy.deepcopy(cfg)
    deprec["fx"]["annual_depr"] = 0.10
    moved = build_annual_rows(deprec)
    # All LKR: an FX path changes nothing in LKR (the financial-close anchor is the spot).
    assert _opex_lkr(moved) == pytest.approx(_opex_lkr(flat), rel=1e-12)
    cfg["opex"]["currency_split"]["usd_share"] = 1.0
    deprec["opex"]["currency_split"]["usd_share"] = 1.0
    usd_flat, usd_moved = build_annual_rows(cfg), build_annual_rows(deprec)
    assert all(
        m > f for m, f in zip(_opex_lkr(usd_moved), _opex_lkr(usd_flat), strict=True)
    )


def test_a_shock_to_the_total_scales_every_component_pro_rata() -> None:
    cfg = _cfg()
    doubled = copy.deepcopy(cfg)
    doubled["opex"]["usd_per_year"] = 2 * cfg["opex"]["usd_per_year"]
    for a, b in zip(
        _opex_lkr(build_annual_rows(cfg)),
        _opex_lkr(build_annual_rows(doubled)),
        strict=True,
    ):
        assert b == pytest.approx(2.0 * a, rel=1e-12)


def test_components_weight_the_usd_share_by_amount() -> None:
    cfg = _cfg()
    assert _resolve_opex_currency_split(cfg) is not None
    split = _resolve_opex_currency_split(cfg)
    assert split is not None and split.usd_share == pytest.approx(0.49)
    per_unit = _unsplit(cfg)
    per_unit["opex"]["currency_split"] = {
        "usd_escalation_pct": 2.5,
        "lkr_escalation_pct": 5.0,
        "components": [
            {"name": "a", "usd_per_unit_year": 2.0, "units": 300.0, "usd_share": 1.0},
            {"name": "b", "usd_per_year": 400.0, "usd_share": 0.25},
        ],
    }
    got = _resolve_opex_currency_split(per_unit)
    assert got is not None and got.usd_share == pytest.approx((600 + 100) / 1000)
    assert opex_component_amounts_usd(per_unit) == {"a": 600.0, "b": 400.0}


def test_usd_depreciation_lowers_the_wind_project_npv() -> None:
    base = evaluate_with_overrides(str(WIND), overrides={})
    harder = evaluate_with_overrides(
        str(WIND), overrides={"opex.currency_split.usd_lkr_depreciation_pct": 8.0}
    )
    unsplit = evaluate_with_overrides(
        str(WIND), overrides={"opex.currency_split": None}
    )
    assert harder["project_npv"] < base["project_npv"] < unsplit["project_npv"]


def test_the_helper_refuses_a_split_without_its_fx_anchor() -> None:
    params = dict(vars(_build_cashflow_params(_cfg())))
    with pytest.raises(ValueError, match="financial-close FX anchor"):
        opex_for_year(params, 0, 333.79)


# ---------------------------------------------------------------------------
# Guards (fail loud)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda s: s.update(usd_share=0.5), "exactly one of usd_share or components"),
        (lambda s: s.pop("components"), "exactly one of usd_share or components"),
        (lambda s: s.update(colour="red"), "unknown key"),
        (lambda s: s.pop("usd_escalation_pct"), "usd_escalation_pct is required"),
        (lambda s: s.update(lkr_escalation_pct=4.0), "disagree"),
        (lambda s: s.update(usd_escalation_pct=250.0), r"percent per year"),
        (lambda s: s.update(usd_escalation_pct="high"), "must be a number"),
        (lambda s: s.update(components=[]), "must not be empty"),
        (lambda s: s["components"][0].update(usd_share=1.5), r"in \[0, 1\]"),
        (lambda s: s["components"][0].update(units=3.0), "not both"),
        (lambda s: s["components"][1].update(name="wind_om"), "duplicated"),
        (lambda s: s["components"][0].update(usd_per_year=-1.0), ">= 0"),
        (lambda s: s["components"][0].pop("usd_share"), "usd_share is required"),
    ],
)
def test_malformed_splits_are_refused(mutate: Any, match: str) -> None:
    cfg = _cfg()
    mutate(_split(cfg))
    with pytest.raises(ValueError, match=match):
        build_annual_rows(cfg)


def test_an_own_fx_path_needs_a_scalar_start_spot() -> None:
    cfg = _cfg()
    cfg["fx"] = {"curve_lkr_per_usd": [333.79] * 20}
    with pytest.raises(ValueError, match="needs a scalar"):
        _prepare_cashflow_context(cfg, None, None, None)


# ---------------------------------------------------------------------------
# The committed data
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", sorted((REPO_ROOT / "scenarios").glob("*.yaml")))
def test_committed_components_add_up_to_the_committed_total(path: Path) -> None:
    for raw in yaml.safe_load_all(path.read_text()):
        if not isinstance(raw, dict) or not isinstance(raw.get("opex"), dict):
            continue
        amounts = opex_component_amounts_usd(raw)
        if amounts:
            assert sum(amounts.values()) == pytest.approx(
                float(raw["opex"]["usd_per_year"]), abs=0.5
            ), path.name


def test_the_committed_blue_whale_splits_follow_the_owners_decision() -> None:
    wind = opex_component_amounts_usd(_cfg())
    assert wind == {"wind_om": 350_000.0, "insurance_land_spv": 150_000.0}
    wind_split = {c["name"]: c["usd_share"] for c in _split(_cfg())["components"]}
    assert wind_split == {"wind_om": 0.70, "insurance_land_spv": 0.0}
    sb = yaml.safe_load(SOLAR_BESS.read_text())
    comps = {c["name"]: c for c in sb["opex"]["currency_split"]["components"]}
    assert comps["bess_ltsa"]["usd_per_unit_year"] == 1.80
    assert comps["bess_ltsa"]["usd_share"] == 1.0
    energy_kwh = sb["generation"]["technologies"]["bess_1"]["energy_mwh"] * 1000.0
    assert comps["bess_ltsa"]["units"] == pytest.approx(energy_kwh * 44.2 / 40.0)
    assert comps["solar_om"]["usd_share"] == 0.0
    assert comps["insurance_land_spv"]["usd_share"] == 0.0
