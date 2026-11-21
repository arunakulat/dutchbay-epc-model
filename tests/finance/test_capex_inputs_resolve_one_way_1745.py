"""Capex inputs resolve one way, or are refused (#1745; #1578 next-20 item 3).

Two defects, one family: a project cost that the debt engine, NPV and the tax base
would read differently.

* #1745: the native-LKR guard looked only at a cost section's top-level keys, and
  only at underscore spellings. An LKR line item under ``capex.breakdown`` was
  summed as USD; ``lkr-per-year`` or ``lkrPerYear`` was dropped; a ``CAPEX`` list
  was skipped. Each is now refused in strict preflight and on the direct paths.
* #1578 next-20 item 3: the tax-base ladder read only ``capex.usd_total``, so a
  capex stated under an alias was financed but never depreciated. The ladder now
  reads the debt engine's resolver, and refuses a stated capex it cannot resolve.

The oracle for the tax base is the explicit ``tax.depreciable_capex_lkr`` input,
a supported path that predates this change: the alias run must equal it.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from analytics.storage_headline import strip_headline_option
from finance.cashflow_v14 import build_annual_rows
from finance.cashflow_v14_params import _build_cashflow_params
from finance.cost_input_currency import validate_cost_input_currencies
from finance.debt.capex import _extract_capex_base_usd

ROOT = Path(__file__).resolve().parents[2]
WIND = ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
SOLAR_BESS = ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
LENDER = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

_DIRECT: tuple[Callable[[dict[str, Any]], object], ...] = (
    validate_cost_input_currencies,
    _extract_capex_base_usd,
    _build_cashflow_params,
    build_annual_rows,
)


def _load(path: Path) -> dict[str, Any]:
    # Capex-input plumbing on the wind-only case; the headline battery is #1823's subject.
    return strip_headline_option(yaml.safe_load(path.read_text()))


@pytest.fixture(params=[WIND, SOLAR_BESS], ids=["wind", "solar_bess"])
def scenario(request: pytest.FixtureRequest) -> dict[str, Any]:
    """A committed scenario, copied so each test edits its own."""
    return _load(request.param)


def _refused_everywhere(cfg: dict[str, Any], pattern: str) -> None:
    """Strict preflight and every direct finance path refuse, naming the path."""
    with pytest.raises(ConfigValidationError, match=pattern):
        validate_config_for_v14(
            copy.deepcopy(cfg), config_path="capex-1745", modules=["cashflow", "debt"]
        )
    for path in _DIRECT:
        with pytest.raises(ValueError, match=pattern):
            path(copy.deepcopy(cfg))


# ---------------------------------------------------------------------------
# #1745 shape 1: an LKR line item inside capex.breakdown
# ---------------------------------------------------------------------------


def _breakdown_config(
    scenario: dict[str, Any], items: dict[str, Any], *, derive: bool = True
) -> dict[str, Any]:
    usd = float(scenario["capex"]["usd_total"])
    scenario["capex"] = {"derive_from_breakdown": derive, "breakdown": items}
    if not derive:
        scenario["capex"]["usd_total"] = usd
    return scenario


def test_usd_breakdown_still_sums(scenario: dict[str, Any]) -> None:
    """Positive control: an all-USD breakdown is accepted and is the capex."""
    usd = float(scenario["capex"]["usd_total"])
    cfg = _breakdown_config(
        scenario, {"plant_usd": usd * 0.75, "civil_works_usd": usd * 0.25}
    )
    cfg["capex"]["usd_total"] = usd  # strict preflight still requires the flat total
    validate_config_for_v14(cfg, config_path="capex-1745", modules=["cashflow"])
    assert math.isclose(_extract_capex_base_usd(cfg), usd, rel_tol=1e-12)


@pytest.mark.parametrize(
    "key", ["civil_lkr", "civil-works-lkr", "civilWorksLkr", "LKR civil works"]
)
@pytest.mark.parametrize("derive", [True, False])
def test_lkr_breakdown_item_is_refused(
    scenario: dict[str, Any], key: str, derive: bool
) -> None:
    """An LKR line item can never be summed as USD, derived or not."""
    usd = float(scenario["capex"]["usd_total"])
    cfg = _breakdown_config(
        scenario, {"plant_usd": usd * 0.9, key: usd * 0.1 * 300.0}, derive=derive
    )
    _refused_everywhere(cfg, rf"capex\.breakdown\.{key}:.*native-LKR")


def test_nested_or_case_variant_breakdown_is_inspected(
    scenario: dict[str, Any],
) -> None:
    """The walk follows a nested group and a case-variant breakdown key."""
    usd = float(scenario["capex"]["usd_total"])
    scenario["capex"] = {
        "derive_from_breakdown": True,
        "Breakdown": {"plant_usd": usd, "civil": {"earthworks_lkr": 1.0}},
    }
    with pytest.raises(ValueError, match=r"capex\.Breakdown\.civil\.earthworks_lkr"):
        validate_cost_input_currencies(scenario)


# ---------------------------------------------------------------------------
# #1745 shape 2: hyphen and camelCase spellings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key", ["lkr-per-year", "lkrPerYear", "LKRPerYear", "annualOpexLkr", "lkr per year"]
)
def test_opex_lkr_spellings_are_refused(scenario: dict[str, Any], key: str) -> None:
    """Every word-boundary spelling of an LKR opex key is refused."""
    scenario["opex"][key] = 1000.0
    _refused_everywhere(scenario, rf"opex\.{key}.*native-LKR opex")


@pytest.mark.parametrize("key", ["lkrTotal", "lkr-total", "totalLKR"])
def test_capex_lkr_spellings_are_refused(scenario: dict[str, Any], key: str) -> None:
    """Only the exact legacy ``capex.lkr_total`` spelling has its tax-only exception."""
    scenario["capex"][key] = 1000.0
    _refused_everywhere(scenario, rf"capex\.{key}.*native-LKR project costs")


@pytest.mark.parametrize("key", ["bulkrate_usd", "milkround_usd", "flkr_usd"])
def test_lkr_inside_a_word_is_not_a_currency(
    scenario: dict[str, Any], key: str
) -> None:
    """``lkr`` must be a whole word: the guard does not refuse unrelated keys."""
    scenario["opex"][key] = 1.0
    scenario["capex"][key] = 1.0
    validate_cost_input_currencies(scenario)


# ---------------------------------------------------------------------------
# #1745 shape 3: a cost section that is not a mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,value",
    [
        ("CAPEX", [{"lkr_total": 1.0}]),
        ("Capex", 12345.0),
        ("OPEX", ["usd_per_year", 1.0]),
        ("opex_", None),  # not a cost section; control for the name match
    ],
)
def test_non_mapping_cost_section_is_refused(
    scenario: dict[str, Any], name: str, value: object
) -> None:
    """A list or scalar cost section cannot hide behind the canonical block."""
    scenario[name] = value
    if name == "opex_":
        validate_cost_input_currencies(scenario)
        return
    _refused_everywhere(scenario, rf"{name} \(\w+\): a cost section must be a mapping")


def test_empty_cost_section_is_absent(scenario: dict[str, Any]) -> None:
    """A null case variant (an empty YAML block) is treated as absent."""
    scenario["CAPEX"] = None
    scenario["OPEX"] = None
    validate_cost_input_currencies(scenario)


# ---------------------------------------------------------------------------
# Supported LKR inputs keep working
# ---------------------------------------------------------------------------


def test_supported_lkr_inputs_still_pass(scenario: dict[str, Any]) -> None:
    """Tax-only LKR bases and the opex currency-split settings are untouched."""
    scenario["tax"]["depreciable_capex_lkr"] = 1.0e9
    scenario["tax"]["dep_base_lkr"] = 1.0e9
    scenario["opex"]["currency_split"] = {
        "usd_share": 0.5,
        "usd_lkr_depreciation_pct": 0.03,
    }
    validate_cost_input_currencies(scenario)
    validate_config_for_v14(scenario, config_path="capex-1745", modules=["cashflow"])


def test_native_flat_capex_input_still_passes() -> None:
    """The #1632 native flat capex input under capex.input is not an LKR key."""
    cfg = {
        "fx": {"start_lkr_per_usd": 317.25},
        "capex": {
            "input": {
                "currency": "LKR",
                "amount": 6345000.0,
                "price_date": "2026-02-01",
                "financial_close_date": "2027-01-10",
                "conversion": {
                    "rate_lkr_per_usd": 317.25,
                    "date": "2027-01-10",
                    "source": "test quotation",
                    "basis": "financial_close",
                },
            }
        },
    }
    assert _extract_capex_base_usd(cfg) == 20000


# ---------------------------------------------------------------------------
# #1578 next-20 item 3: the tax base reads the capex resolver
# ---------------------------------------------------------------------------


def _without_capex(cfg: dict[str, Any]) -> tuple[dict[str, Any], float]:
    usd = float(cfg["capex"].pop("usd_total"))
    return cfg, usd


def _depreciation(cfg: dict[str, Any]) -> list[float]:
    return [row["total_depreciation_lkr"] for row in build_annual_rows(cfg)]


_ALIASES: list[tuple[str, Callable[[dict[str, Any], float], None]]] = [
    ("capex.total_capex", lambda c, v: c["capex"].__setitem__("total_capex", v)),
    (
        "capex.capex_total_usd",
        lambda c, v: c["capex"].__setitem__("capex_total_usd", v),
    ),
    (
        "capex.total_capex_usd",
        lambda c, v: c["capex"].__setitem__("total_capex_usd", v),
    ),
    ("finance.capex_usd", lambda c, v: c.setdefault("finance", {}).update(capex_usd=v)),
    (
        "finance.capex_total_usd",
        lambda c, v: c.setdefault("finance", {}).update(capex_total_usd=v),
    ),
    ("costs.total_capex", lambda c, v: c.setdefault("costs", {}).update(total_capex=v)),
    ("capex_usd_total", lambda c, v: c.__setitem__("capex_usd_total", v)),
    ("CAPEX.USD_TOTAL", lambda c, v: c.__setitem__("CAPEX", {"USD_TOTAL": v})),
]


@pytest.mark.parametrize("alias,state", _ALIASES, ids=[a for a, _ in _ALIASES])
def test_alias_capex_is_depreciated_like_the_explicit_tax_base(
    scenario: dict[str, Any],
    alias: str,
    state: Callable[[dict[str, Any], float], None],
) -> None:
    """Every resolver alias gives the depreciation of the explicit tax base."""
    fx = float(scenario["fx"]["start_lkr_per_usd"])
    explicit, usd = _without_capex(copy.deepcopy(scenario))
    explicit["capex"]["usd_total"] = usd
    explicit.setdefault("tax", {})["depreciable_capex_lkr"] = usd * fx
    expected = _depreciation(explicit)
    assert sum(expected) > 0

    cfg, usd = _without_capex(scenario)
    if alias == "CAPEX.USD_TOTAL":
        cfg.pop("capex")
    state(cfg, usd)
    got = _depreciation(cfg)
    assert got == pytest.approx(expected, rel=1e-12, abs=1e-6)


def test_derived_breakdown_without_flat_total_is_depreciated(
    scenario: dict[str, Any],
) -> None:
    """A bottom-up capex with no usd_total is depreciated at its sum."""
    fx = float(scenario["fx"]["start_lkr_per_usd"])
    usd = float(scenario["capex"]["usd_total"])
    cfg = _breakdown_config(
        scenario, {"plant_usd": usd * 0.6, "civil_works_usd": usd * 0.4}
    )
    explicit = copy.deepcopy(cfg)
    explicit["tax"]["depreciable_capex_lkr"] = usd * fx
    assert _depreciation(cfg) == pytest.approx(_depreciation(explicit), rel=1e-12)


def test_alias_capex_gives_the_same_project_result() -> None:
    """End to end: an alias-only capex gives the usd_total KPIs (the #1578 repro).

    On main 78ab7992 the alias run gave project NPV -673,886 against 1,398,803.
    """
    base = _load(WIND)
    alias, usd = _without_capex(copy.deepcopy(base))
    alias.setdefault("finance", {})["capex_usd"] = usd
    want = evaluate_with_overrides(raw_config=base, overrides={})
    got = evaluate_with_overrides(raw_config=alias, overrides={})
    for key in ("project_npv", "project_irr", "equity_irr", "min_dscr"):
        assert got[key] == pytest.approx(want[key], rel=1e-12), key


def test_no_capex_stated_still_books_no_depreciation(scenario: dict[str, Any]) -> None:
    """With no project capex at all, the toy fallback is never depreciated."""
    scenario["capex"] = {}
    scenario["allow_toy_fallback"] = True
    assert _extract_capex_base_usd(copy.deepcopy(scenario)) == 100.0
    assert sum(_depreciation(scenario)) == 0.0


@pytest.mark.parametrize(
    "stated",
    [
        {"capex": {"epc_usd": 1.0e7}},
        {"finance": {"capex_usd": "ten million"}},
    ],
    ids=["unread_alias", "unparseable_alias"],
)
def test_stated_capex_that_does_not_resolve_is_refused(
    scenario: dict[str, Any], stated: dict[str, Any]
) -> None:
    """A capex that is stated but unreadable is refused, even with toy fallback on."""
    scenario["capex"] = {}
    scenario["allow_toy_fallback"] = True
    for section, block in stated.items():
        scenario.setdefault(section, {}).update(block)
    with pytest.raises(ValueError, match="tax depreciation base: a project capex"):
        build_annual_rows(scenario)


def test_lender_case_tax_base_unchanged() -> None:
    """The committed lender case depreciates exactly its usd_total, as before."""
    cfg = _load(LENDER)
    cfg.pop("taxes_indirect", None)
    fx = float(cfg["fx"]["start_lkr_per_usd"])
    explicit = copy.deepcopy(cfg)
    explicit["tax"]["depreciable_capex_lkr"] = float(cfg["capex"]["usd_total"]) * fx
    assert _depreciation(cfg) == pytest.approx(_depreciation(explicit), rel=1e-12)
