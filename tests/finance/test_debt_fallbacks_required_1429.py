"""The debt engine's gearing, target DSCR and flat downside factor have no code default (#1429).

The engine used to fill an absent ``debt_ratio``, ``target_dscr`` or
``dscr_p99_downside_factor`` with Dutch Bay figures (0.70, 1.30, 0.80). Each now comes
only from the scenario YAML: pre-flight refuses a scenario that omits one, naming the
path, and so does the engine at the point of use. No committed scenario relied on the
fallbacks, so no figure moves.
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
from finance.debt.sizing import resolve_debt_sizing_terms

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


@pytest.mark.parametrize(
    ("key", "path"),
    [
        ("debt_ratio", "Financing_Terms.debt_ratio"),
        ("target_dscr", "Financing_Terms.target_dscr"),
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


@pytest.mark.parametrize("bad", ["seventy", float("nan"), float("inf")])
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
    assert terms == {"debt_ratio": 0.55, "target_dscr": 1.45}
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
