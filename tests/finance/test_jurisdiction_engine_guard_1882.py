"""The Sri Lanka tax and levy code refuses a scenario declaring another jurisdiction (#1882).

Test J-01 of the 22 Nov 2026 platform evaluation: a project in an unknown jurisdiction must
never receive Sri Lanka tax, levy or tariff rules. The #1843 resolver already refuses an
unknown jurisdiction, but the engine does not call it yet (#1841). These tests pin the
engine-level guard that stands in until it does, and pin that Sri Lanka scenarios and
scenarios without the key are untouched.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.pipeline_v14_enhanced import PipelineValidationError
from finance.cashflow_v14_tax import TaxConfig, require_sri_lanka_jurisdiction
from finance.import_levies import resolve_indirect_taxes

REPO = Path(__file__).resolve().parents[2]
LENDER = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
BLUE_WHALE = REPO / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"

_LEVY_BLOCK = {
    "import_share_pct": 0.5,
    "cid_pct": 0.0,
    "pal_pct": 0.05,
    "sscl_import_pct": 0.025,
    "vat_capex_pct": 0.18,
}


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _with_jurisdiction(cfg: dict[str, Any], value: Any) -> dict[str, Any]:
    out = copy.deepcopy(cfg)
    out.setdefault("project", {})["jurisdiction"] = value
    return out


def _without_jurisdiction(cfg: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(cfg)
    out.get("project", {}).pop("jurisdiction", None)
    return out


@pytest.fixture(scope="module")
def lender() -> dict[str, Any]:
    return _load(LENDER)


# --- The guard on its own ------------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["Sri Lanka", "sri lanka", "  SRI LANKA ", "LK", "lka"]
)
def test_sri_lanka_spellings_are_accepted(value: str) -> None:
    require_sri_lanka_jurisdiction({"project": {"jurisdiction": value}}, "tax")


@pytest.mark.parametrize(
    "cfg",
    [
        {},
        {"project": {}},
        {"project": {"jurisdiction": None}},
        {"project": "not a mapping"},
    ],
)
def test_an_absent_jurisdiction_is_accepted_as_before(cfg: dict[str, Any]) -> None:
    require_sri_lanka_jurisdiction(cfg, "tax")


@pytest.mark.parametrize("value", ["Kenya", "XX", "India", "Sri Lankan Province", ""])
def test_another_jurisdiction_is_refused_and_names_the_pack_route(value: str) -> None:
    with pytest.raises(ValueError, match=r"#1841") as excinfo:
        require_sri_lanka_jurisdiction({"project": {"jurisdiction": value}}, "tax")
    assert repr(value) in str(excinfo.value)
    assert str(excinfo.value).startswith("tax: ")


@pytest.mark.parametrize("value", [1, ["Sri Lanka"], {"code": "LK"}, True])
def test_a_non_string_jurisdiction_is_refused(value: Any) -> None:
    with pytest.raises(ValueError, match="must be a string"):
        require_sri_lanka_jurisdiction({"project": {"jurisdiction": value}}, "tax")


def test_the_project_section_is_found_case_insensitively() -> None:
    with pytest.raises(ValueError, match="#1841"):
        require_sri_lanka_jurisdiction({"Project": {"Jurisdiction": "XX"}}, "tax")


# --- Direct tax ------------------------------------------------------------------------------


def test_direct_tax_refuses_another_jurisdiction(lender: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"^tax: .*'XX'.*#1841"):
        TaxConfig.from_yaml(_with_jurisdiction(lender, "XX"))


def test_direct_tax_is_unchanged_for_sri_lanka_and_an_absent_key(
    lender: dict[str, Any],
) -> None:
    as_committed = TaxConfig.from_yaml(lender)
    assert TaxConfig.from_yaml(_with_jurisdiction(lender, "LK")) == as_committed
    assert TaxConfig.from_yaml(_without_jurisdiction(lender)) == as_committed


# --- Indirect tax and import levies ----------------------------------------------------------


def test_levies_refuse_another_jurisdiction() -> None:
    cfg = {"project": {"jurisdiction": "Kenya"}, "taxes_indirect": dict(_LEVY_BLOCK)}
    with pytest.raises(ValueError, match=r"^taxes_indirect: .*'Kenya'.*#1841"):
        resolve_indirect_taxes(cfg)


def test_levies_are_unchanged_for_sri_lanka_and_an_absent_key() -> None:
    sri_lanka = resolve_indirect_taxes(
        {"project": {"jurisdiction": "Sri Lanka"}, "taxes_indirect": dict(_LEVY_BLOCK)}
    )
    absent = resolve_indirect_taxes({"taxes_indirect": dict(_LEVY_BLOCK)})
    assert sri_lanka is not None
    assert sri_lanka == absent


def test_no_levy_block_still_resolves_to_none_whatever_the_jurisdiction() -> None:
    # Nothing to leak when the block is absent; the direct-tax guard still refuses the run.
    assert resolve_indirect_taxes({"project": {"jurisdiction": "Kenya"}}) is None


# --- End to end: J-01 ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", [LENDER, BLUE_WHALE], ids=["lender_case", "blue_whale_wind"]
)
def test_a_committed_scenario_rebound_to_an_unknown_jurisdiction_is_refused(
    path: Path,
) -> None:
    # The pipeline wraps the guard's ValueError; the refusal and its reason must survive.
    with pytest.raises(PipelineValidationError, match=r"'XX'.*#1841"):
        evaluate_with_overrides(raw_config=_with_jurisdiction(_load(path), "XX"))


def test_the_lender_case_kpis_are_unchanged_without_the_key(
    lender: dict[str, Any],
) -> None:
    as_committed = evaluate_with_overrides(raw_config=lender)
    without_key = evaluate_with_overrides(raw_config=_without_jurisdiction(lender))
    assert without_key == as_committed
