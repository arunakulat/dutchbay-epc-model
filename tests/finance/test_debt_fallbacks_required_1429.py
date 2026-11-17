"""The debt engine's sizing terms have no code default (#1429).

The engine used to fill an absent ``debt_ratio``, ``target_dscr`` or
``dscr_p99_downside_factor`` with Dutch Bay figures (0.70, 1.30, 0.80). The second step
removes three more: the tenor (15 years), the dual-DSCR capacity discount rate
``interest_rate_nominal`` (8%) and the construction-period count (two). Each now comes
only from the scenario YAML: pre-flight refuses a scenario that omits one, naming the
path, and so does the engine at the point of use. No committed engine scenario relied on
the fallbacks, so no figure moves.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.debt.balloon import _resize_for_amortization
from finance.debt.constants import _BALLOON_TOL
from finance.debt.layer import apply_debt_layer
from finance.debt.sizing import _maybe_autosolve_dscr, resolve_debt_sizing_terms

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
LENDER = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"

#: Committed files under scenarios/ that the canonical pipeline already refused before
#: #1429 (bad-input fixtures, EPC-only or sensitivity-suite files, and files that do not
#: load). They are not engine scenarios, so they are outside the census.
_NOT_ENGINE_SCENARIOS = {
    "bad_missing_tax.yaml",
    "contracts_edgecase_base_v14.yaml",
    "dscr_sensitivity_example.yaml",
    "dutchbay_mc_enhanced_2025Q4.yaml",
    "dutchbay_sprint17_enhanced.yaml",
    "example_fx_structured_blocks.yaml",
    "kolonnawa_epc_100mw.yaml",
    "sensitivity_parameters_examples.yaml",
}
#: Partial configs merged onto a base, and scratch files.
_PARTIAL_DIRS = {"overrides", "what_if", "_scrtch"}


def _engine_scenarios() -> List[Path]:
    paths = []
    for path in sorted(SCENARIOS.rglob("*.y*ml")):
        if _PARTIAL_DIRS.intersection(path.relative_to(SCENARIOS).parts):
            continue
        if path.name in _NOT_ENGINE_SCENARIOS:
            continue
        paths.append(path)
    return paths


def _lender() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(str(LENDER))))


def test_census_finds_engine_scenarios() -> None:
    assert len(_engine_scenarios()) >= 30


@pytest.mark.parametrize(
    "path", _engine_scenarios(), ids=lambda p: str(p.relative_to(SCENARIOS))
)
def test_every_engine_scenario_declares_its_debt_sizing_terms(path: Path) -> None:
    """No committed engine scenario relies on a removed fallback, so none is refused."""
    config = dict(load_scenario_config(str(path)))
    terms = resolve_debt_sizing_terms(config)
    assert 0.0 <= terms["debt_ratio"] <= 1.0
    assert terms["target_dscr"] > 0.0
    assert terms["tenor_years"] >= 1.0
    assert terms["construction_periods"] >= 0.0


@pytest.mark.parametrize(
    ("key", "path"),
    [
        ("debt_ratio", "Financing_Terms.debt_ratio"),
        ("target_dscr", "Financing_Terms.target_dscr"),
        ("tenor_years", "Financing_Terms.tenor_years"),
        ("interest_rate_nominal", "Financing_Terms.interest_rate_nominal"),
    ],
)
def test_preflight_refuses_a_missing_term_naming_its_path(key: str, path: str) -> None:
    config = _lender()
    validate_config_for_v14(config, "lender", ["cashflow", "debt"])  # control
    del config["Financing_Terms"][key]
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(config, "lender", ["cashflow", "debt"])
    assert f"{path} is required" in str(excinfo.value)
    assert "no code default (#1429)" in str(excinfo.value)


def test_preflight_requires_the_flat_downside_factor_only_where_it_is_read() -> None:
    config = _lender()
    fin = config["Financing_Terms"]
    assert str(fin.get("debt_sizing")).lower() == "dual_dscr"
    fin.pop("dscr_p99_downside_factor", None)

    # Without bind_downside the autosolve always reads the flat factor.
    fin["bind_downside"] = False
    with pytest.raises(ValueError, match=r"dscr_p99_downside_factor is required"):
        resolve_debt_sizing_terms(config)

    # With bind_downside, a P50/P90 AEP pair stands in for it.
    fin["bind_downside"] = True
    fin["downside_aep_source"] = "p90"
    config["expected_results"] = {"net_aep_p50_gwh": 100.0, "net_aep_p90_gwh": 90.0}
    assert "dscr_p99_downside_factor" not in resolve_debt_sizing_terms(config)

    # Without the pair, the flat factor is required again.
    del config["expected_results"]
    with pytest.raises(ValueError, match=r"dscr_p99_downside_factor"):
        resolve_debt_sizing_terms(config)


def test_preflight_is_not_asked_when_debt_is_not_validated() -> None:
    config = _lender()
    del config["Financing_Terms"]["debt_ratio"]
    validate_config_for_v14(config, "lender", ["cashflow"])


@pytest.mark.parametrize(
    ("section", "terms", "message"),
    [
        ("Financing_Terms", {"target_dscr": 1.3}, r"Financing_Terms\.debt_ratio"),
        ("financing", {"debt_ratio": 0.6}, r"financing\.target_dscr"),
        ("debt", {"target_dscr": 1.3}, r"debt\.debt_ratio"),
        ("debt", {"debt_ratio": 0.6}, r"debt\.target_dscr"),
        (None, {"debt_ratio": 0.6}, r"^target_dscr is required"),
    ],
)
def test_engine_refuses_at_the_point_of_use(
    section: Any, terms: Dict[str, Any], message: str
) -> None:
    base: Dict[str, Any] = {
        "tenor_years": 5,
        "construction_periods": 1,
        "rates": {"usd_nominal": 0.08},
        "mix": {"usd_commercial_min": 1.0},
        **terms,
    }
    params: Dict[str, Any] = {"capex": {"usd_total": 100.0}}
    if section is None:
        params.update(base)
    else:
        params[section] = base
    with pytest.raises(ValueError, match=message):
        apply_debt_layer(params=params, annual_rows=[])


@pytest.mark.parametrize("bad", ["seventy", float("nan"), float("inf"), True], ids=str)
def test_a_declared_non_number_is_refused_not_replaced(bad: Any) -> None:
    config = _lender()
    config["Financing_Terms"]["debt_ratio"] = bad
    with pytest.raises(ValueError, match=r"Financing_Terms\.debt_ratio is required"):
        resolve_debt_sizing_terms(config)


def test_declared_values_are_used_unchanged() -> None:
    params = {
        "capex": {"usd_total": 100.0},
        "Financing_Terms": {
            "debt_ratio": 0.55,
            "target_dscr": 1.45,
            "tenor_years": 5,
            "construction_periods": 1,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
    }
    terms = resolve_debt_sizing_terms(params)
    assert terms == {
        "debt_ratio": 0.55,
        "target_dscr": 1.45,
        "tenor_years": 5.0,
        "construction_periods": 1.0,
    }
    core = apply_debt_layer(params=params, annual_rows=[])
    assert core["debt_total"] == pytest.approx(55.0)


def test_balloon_bisection_reads_a_flat_configs_own_gearing() -> None:
    """The bisection's upper bound is the config's own gearing, not 0.70.

    Before #1429 a config with no Financing_Terms section bisected between 0 and the
    0.70 fallback, whatever its top-level gearing, so a balloon-free gearing above 0.70
    could not be found. Here it is about 0.79.
    """
    rows = [{"year": y, "cfads_usd": 20.0} for y in range(1, 9)]
    config = {
        "capex": {"usd_total": 100.0},
        "debt_ratio": 0.90,
        "target_dscr": 1.30,
        "tenor_years": 8,
        "construction_periods": 1,
        "amortization_style": "sculpted",
        "mix": {"usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08},
    }
    core = apply_debt_layer(params=config, annual_rows=rows)
    assert core["balloon_remaining"] > 0.0
    out_cfg, out_core = _resize_for_amortization(config, rows, core)
    assert 0.70 < out_cfg["debt_ratio"] < 0.90
    assert out_core["balloon_remaining"] <= _BALLOON_TOL


# --- #1429, second step: tenor, capacity rate and construction periods -----------


def test_preflight_refuses_an_undeclared_build_time() -> None:
    """With neither the financing count nor ``timeline`` declared, pre-flight refuses."""
    config = _lender()
    del config["Financing_Terms"]["construction_periods"]
    validate_config_for_v14(config, "lender", ["cashflow", "debt"])  # timeline alone
    del config["timeline"]["construction_years"]
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(config, "lender", ["cashflow", "debt"])
    message = str(excinfo.value)
    assert "Financing_Terms.construction_periods (or timeline.construction_years)" in (
        message
    )
    assert "no code default (#1429)" in message


def test_capacity_rate_is_required_only_under_dscr_sizing() -> None:
    """The capacity discount rate is read only by the DSCR autosolve."""
    config = _lender()
    del config["Financing_Terms"]["interest_rate_nominal"]
    config["Financing_Terms"]["debt_sizing"] = "fixed"
    terms = resolve_debt_sizing_terms(config)
    assert "interest_rate_nominal" not in terms


@pytest.mark.parametrize(
    ("key", "message"),
    [
        ("debt_ratio", r"Financing_Terms\.debt_ratio is required"),
        ("target_dscr", r"Financing_Terms\.target_dscr is required"),
        ("dscr_p99_downside_factor", r"dscr_p99_downside_factor is required"),
        ("tenor_years", r"Financing_Terms\.tenor_years is required"),
        ("interest_rate_nominal", r"Financing_Terms\.interest_rate_nominal"),
    ],
)
def test_autosolve_refuses_at_the_point_of_use(key: str, message: str) -> None:
    """With pre-flight bypassed, the DSCR autosolve still refuses each absent term.

    This pins the engine's own refusal: a caller that skips ``schema_guard`` cannot
    reach the removed fallbacks either.
    """
    config = _lender()
    fin = config["Financing_Terms"]
    fin["bind_downside"] = False
    rows = [{"year": y, "cfads_usd": 30e6} for y in range(1, 21)]
    _maybe_autosolve_dscr(copy.deepcopy(config), rows)  # control: runs as declared
    fin.pop(key)
    with pytest.raises(ValueError, match=message):
        _maybe_autosolve_dscr(config, rows)


@pytest.mark.parametrize(
    ("section", "tenor_key"),
    [
        ("Financing_Terms", "tenor_years"),
        ("financing", "tenor_years"),
        ("debt", "tenor_years"),
        (None, "tenor_years"),
    ],
)
def test_engine_refuses_an_undeclared_tenor(section: Any, tenor_key: str) -> None:
    base: Dict[str, Any] = {
        "debt_ratio": 0.6,
        "target_dscr": 1.3,
        "construction_periods": 1,
        "rates": {"usd_nominal": 0.08},
        "mix": {"usd_commercial_min": 1.0},
    }
    params: Dict[str, Any] = {"capex": {"usd_total": 100.0}}
    prefix = "" if section is None else f"{section}."
    if section is None:
        params.update(base)
    else:
        params[section] = base
    with pytest.raises(ValueError, match=rf"^{prefix}{tenor_key} is required"):
        apply_debt_layer(params=params, annual_rows=[])
    with pytest.raises(ValueError, match=rf"{prefix}tenor_years is required"):
        resolve_debt_sizing_terms(params)


@pytest.mark.parametrize("section", ["Financing_Terms", "debt"])
def test_term_years_is_honoured_as_the_tenor(section: str) -> None:
    """``term_years`` is the tenor alias the strict schema accepts; the engine reads it."""
    params: Dict[str, Any] = {
        "capex": {"usd_total": 100.0},
        section: {
            "debt_ratio": 0.6,
            "target_dscr": 1.3,
            "term_years": 7,
            "construction_periods": 1,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
    }
    assert resolve_debt_sizing_terms(params)["tenor_years"] == 7.0
    core = apply_debt_layer(params=params, annual_rows=[])
    assert core["tenor_years"] == 7


@pytest.mark.parametrize("bad", ["fifteen", True, float("nan")], ids=str)
def test_a_declared_tenor_that_is_not_a_number_is_refused(bad: Any) -> None:
    """Before #1429's second step ``True`` became one year and text became 15."""
    config = _lender()
    config["Financing_Terms"]["tenor_years"] = bad
    with pytest.raises(ValueError, match=r"Financing_Terms\.tenor_years is required"):
        resolve_debt_sizing_terms(config)


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [("debt_pct", 65, 0.65), ("leverage_pct", 0.55, 0.55), ("debt_ratio", 0.7, 0.7)],
)
def test_resolver_scales_a_percentage_gearing_alias(
    key: str, value: float, expected: float
) -> None:
    """Pre-flight resolves an alias to the same fraction the extractor gives the engine."""
    config = _lender()
    fin = config["Financing_Terms"]
    fin["debt_sizing"] = "fixed"
    del fin["debt_ratio"]
    fin[key] = value
    assert resolve_debt_sizing_terms(config)["debt_ratio"] == pytest.approx(expected)


def test_balloon_bisection_reads_a_financing_terms_gearing_alias() -> None:
    """A gearing declared only as ``debt_pct`` bounds the bisection at that gearing.

    Before this step the bisection read ``Financing_Terms.debt_ratio`` alone, so a
    scenario that pre-flight and the debt layer accepted through the alias was refused
    here (#1733 review low).
    """
    rows = [{"year": y, "cfads_usd": 20.0} for y in range(1, 9)]
    config = {
        "capex": {"usd_total": 100.0},
        "Financing_Terms": {
            "debt_pct": 90,
            "target_dscr": 1.30,
            "tenor_years": 8,
            "construction_periods": 1,
            "amortization_style": "sculpted",
            "mix": {"usd_commercial_min": 1.0},
            "rates": {"usd_nominal": 0.08},
        },
    }
    core = apply_debt_layer(params=config, annual_rows=rows)
    assert core["balloon_remaining"] > 0.0
    out_cfg, out_core = _resize_for_amortization(config, rows, core)
    assert 0.0 < out_cfg["Financing_Terms"]["debt_ratio"] < 0.90
    assert out_core["balloon_remaining"] <= _BALLOON_TOL


def test_capacity_detail_reads_term_years_as_the_tenor() -> None:
    """The dual-DSCR capacity detail spans the tenor the debt layer uses.

    With only ``Financing_Terms.term_years`` declared, the detail must equal the one for
    the same figure declared as ``tenor_years``, and differ from a 15-year tenor (the
    old fallback), so the autosolve cannot read a different tenor from the layer.
    """
    rows = [{"year": y, "cfads_usd": 30e6} for y in range(1, 21)]

    def detail(**tenor: int) -> Dict[str, Any]:
        config = _lender()
        fin = config["Financing_Terms"]
        fin["bind_downside"] = False
        fin.pop("tenor_years")
        fin.update(tenor)
        _, out = _maybe_autosolve_dscr(config, rows)
        assert out is not None
        return out

    by_term = detail(term_years=12)
    assert by_term == detail(tenor_years=12)
    assert by_term != detail(tenor_years=15)
