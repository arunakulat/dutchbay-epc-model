"""#1403: the three non-canonical what-if cases and the location-agnostic loader.

The committed case files are checked for the disclosure #1403 requires (source,
limitations and per-parameter provenance, never canonical). The derivation rules
are checked on a synthetic base that names no real site, so the loader is shown
to work for any project. A few end-to-end runs on the committed cases check the
direction of each effect and that the base scenario is left untouched.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import warnings
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

import analytics.what_if_cases as what_if
from analytics.what_if_cases import (
    WhatIfCaseError,
    build_case_config,
    load_what_if_case,
    parse_what_if_case,
    run_what_if_case,
)
from tests._canon import LENDER_PROJECT_IRR, LENDER_PROJECT_NPV

REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "scenarios" / "what_if"
CASE_FILES = sorted(CASE_DIR.glob("*.yaml"))


def _case_raw(name: str) -> Dict[str, Any]:
    doc = yaml.safe_load((CASE_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    return copy.deepcopy(doc["what_if_case"])


def _synthetic_base() -> Dict[str, Any]:
    """A minimal base config for a made-up site, priced in a different currency."""
    return {
        "project": {"name": "Synthetic Site", "cod_year": 2031},
        "timeline": {"construction_years": 3, "lifetime_years": 28},
        "tariff": {"eur_per_kwh": 0.071, "tariff_type": "fixed"},
        "capex": {"usd_total": 50_000_000.0, "breakdown": {"plant_usd": 50_000_000.0}},
        "Financing_Terms": {
            "construction_periods": 3,
            "construction_schedule": [20.0, 50.0, 30.0],
            "debt_drawdown_pct": [0.2, 0.5, 0.3],
        },
    }


def _synthetic_case(kind: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"synthetic_{kind}",
        "kind": kind,
        "label": "synthetic",
        "canonical": False,
        "base_scenario": "unused.yaml",
        "parameters": parameters,
        "source": "test",
        "limitations": ["test only"],
        "report_kpis": ["project_irr"],
    }


# ------------------------------------------------------------- committed case files


def test_the_three_committed_cases_exist_and_cover_every_kind() -> None:
    kinds = {load_what_if_case(p, repo_root=REPO_ROOT).kind for p in CASE_FILES}
    assert kinds == set(what_if.SUPPORTED_KINDS)
    assert len(CASE_FILES) == 3


@pytest.mark.parametrize("path", CASE_FILES, ids=lambda p: p.stem)
def test_committed_case_discloses_source_limitations_and_provenance(path: Path) -> None:
    case = load_what_if_case(path, repo_root=REPO_ROOT)
    disclosure = case.disclosure()
    assert disclosure["canonical"] is False
    assert disclosure["source"]
    assert disclosure["limitations"]
    assert case.base_scenario.is_file(), case.base_scenario
    for name, param in disclosure["parameters"].items():
        assert param["provenance"], name


def test_the_tariff_case_is_labelled_a_reference_not_an_entitlement() -> None:
    case = load_what_if_case(CASE_DIR / "tariff_reference.yaml", repo_root=REPO_ROOT)
    assert "not an entitlement" in case.label
    assert case.parameters["tariff_per_kwh"].value == 25.73


def test_the_connection_case_defaults_to_zero_and_is_labelled_illustrative() -> None:
    case = load_what_if_case(
        CASE_DIR / "developer_funded_connection.yaml", repo_root=REPO_ROOT
    )
    assert "illustrative" in case.label.lower()
    assert case.parameters["connection_capex_usd"].value == 0
    assert case.parameters["reimbursement_usd_per_year"].value == 0


def test_the_delay_case_runs_the_owner_presets_6_12_and_24() -> None:
    case = load_what_if_case(
        CASE_DIR / "grid_connection_delay.yaml", repo_root=REPO_ROOT
    )
    assert case.parameters["delay_months"].presets == (6, 12, 24)


# -------------------------------------------------------- validation and refusals


def test_a_case_that_claims_to_be_canonical_is_refused() -> None:
    raw = _case_raw("tariff_reference")
    raw["canonical"] = True
    with pytest.raises(WhatIfCaseError, match="never canonical"):
        parse_what_if_case(raw, repo_root=REPO_ROOT)


def test_unknown_keys_and_missing_provenance_are_refused() -> None:
    raw = _case_raw("tariff_reference")
    raw["extra"] = 1
    with pytest.raises(WhatIfCaseError, match="unknown keys"):
        parse_what_if_case(raw, repo_root=REPO_ROOT)

    raw = _case_raw("tariff_reference")
    del raw["parameters"]["tariff_per_kwh"]["provenance"]
    with pytest.raises(WhatIfCaseError, match="provenance"):
        parse_what_if_case(raw, repo_root=REPO_ROOT)

    raw = _case_raw("tariff_reference")
    del raw["source"]
    with pytest.raises(WhatIfCaseError, match="missing required keys"):
        parse_what_if_case(raw, repo_root=REPO_ROOT)


def test_a_parameter_set_that_does_not_match_the_kind_is_refused() -> None:
    raw = _case_raw("tariff_reference")
    raw["parameters"]["delay_months"] = {"value": 12, "provenance": "x"}
    with pytest.raises(WhatIfCaseError, match="must be exactly"):
        parse_what_if_case(raw, repo_root=REPO_ROOT)


@pytest.mark.parametrize("months", [0, -12, 12.5, True, "12"])
def test_a_delay_that_is_not_a_positive_whole_number_of_months_is_refused(
    months: Any,
) -> None:
    raw = _synthetic_case(
        "grid_connection_delay", {"delay_months": {"value": months, "provenance": "x"}}
    )
    with pytest.raises(WhatIfCaseError, match="delay_months"):
        parse_what_if_case(raw)


def test_a_delay_on_top_of_one_the_base_already_carries_is_refused() -> None:
    raw = _synthetic_case(
        "grid_connection_delay", {"delay_months": {"value": 6, "provenance": "x"}}
    )
    case = parse_what_if_case(raw)
    base = _synthetic_base()
    base["project"]["first_year_grid_unavailable_months"] = 3
    with pytest.raises(WhatIfCaseError, match="already sets"):
        build_case_config(case, base, case.variants()[0])


def test_a_non_zero_reimbursement_is_refused() -> None:
    raw = _synthetic_case(
        "developer_funded_connection",
        {
            "connection_capex_usd": {"value": 1_000_000, "provenance": "x"},
            "reimbursement_usd_per_year": {"value": 50_000, "provenance": "x"},
        },
    )
    with pytest.raises(WhatIfCaseError, match="reimbursement_usd_per_year must be 0"):
        parse_what_if_case(raw)


def test_a_negative_connection_amount_is_refused() -> None:
    raw = _synthetic_case(
        "developer_funded_connection",
        {
            "connection_capex_usd": {"value": -1, "provenance": "x"},
            "reimbursement_usd_per_year": {"value": 0, "provenance": "x"},
        },
    )
    with pytest.raises(WhatIfCaseError, match="must not be negative"):
        parse_what_if_case(raw)


def test_a_tariff_field_the_base_does_not_carry_is_refused() -> None:
    raw = _synthetic_case(
        "tariff_reference",
        {
            "tariff_per_kwh": {"value": 0.09, "provenance": "x"},
            "currency": {"value": "USD", "provenance": "x"},
        },
    )
    case = parse_what_if_case(raw)
    with pytest.raises(WhatIfCaseError, match=r"no tariff\.usd_per_kwh"):
        build_case_config(case, _synthetic_base(), case.variants()[0])


def test_only_one_parameter_may_carry_presets() -> None:
    raw = _synthetic_case(
        "tariff_reference",
        {
            "tariff_per_kwh": {"presets": [0.08, 0.09], "provenance": "x"},
            "currency": {"presets": ["EUR", "EUR"], "provenance": "x"},
        },
    )
    with pytest.raises(WhatIfCaseError, match="at most one parameter"):
        parse_what_if_case(raw)


# ---------------------------------------------- derivation on a synthetic base site


def test_delay_appends_idle_periods_and_moves_the_calendar_on_any_site() -> None:
    raw = _synthetic_case(
        "grid_connection_delay",
        {"delay_months": {"presets": [12, 24], "provenance": "x"}},
    )
    case = parse_what_if_case(raw)
    base = _synthetic_base()
    pristine = copy.deepcopy(base)
    configs = [build_case_config(case, base, v)[0] for v in case.variants()]
    assert base == pristine, "the base config must never be modified"

    one, two = (c["Financing_Terms"] for c in configs)
    assert one["construction_periods"] == 4
    assert one["construction_schedule"] == [20.0, 50.0, 30.0, 0.0]
    assert one["debt_drawdown_pct"] == [0.2, 0.5, 0.3, 0.0]
    assert two["construction_periods"] == 5
    assert two["construction_schedule"] == [20.0, 50.0, 30.0, 0.0, 0.0]
    assert [c["project"]["cod_year"] for c in configs] == [2032, 2033]
    assert configs[1]["timeline"] == {"construction_years": 5, "lifetime_years": 30}
    assert configs[0]["meta"]["what_if_case"]["canonical"] is False
    for config in configs:
        assert "first_year_grid_unavailable_months" not in config["project"]


def test_months_under_a_year_use_the_partial_year_lever_on_any_site() -> None:
    raw = _synthetic_case(
        "grid_connection_delay",
        {"delay_months": {"presets": [6, 18], "provenance": "x"}},
    )
    case = parse_what_if_case(raw)
    base = _synthetic_base()
    six, eighteen = (build_case_config(case, base, v) for v in case.variants())

    config, changes = six
    assert config["Financing_Terms"] == base["Financing_Terms"]
    assert config["project"]["cod_year"] == 2031
    assert config["project"]["first_year_grid_unavailable_months"] == 6.0
    assert changes == [
        {
            "path": "project.first_year_grid_unavailable_months",
            "base": None,
            "case": 6.0,
        }
    ]

    config, _ = eighteen
    assert config["Financing_Terms"]["construction_periods"] == 4
    assert config["project"]["cod_year"] == 2032
    assert config["project"]["first_year_grid_unavailable_months"] == 6.0


def test_connection_adds_its_own_capex_line_on_any_site() -> None:
    raw = _synthetic_case(
        "developer_funded_connection",
        {
            "connection_capex_usd": {"value": 4_000_000, "provenance": "x"},
            "reimbursement_usd_per_year": {"value": 0, "provenance": "x"},
        },
    )
    case = parse_what_if_case(raw)
    config, changes = build_case_config(case, _synthetic_base(), case.variants()[0])
    assert config["capex"]["usd_total"] == 54_000_000.0
    assert config["capex"]["breakdown"]["developer_funded_connection_usd"] == 4_000_000
    assert sum(config["capex"]["breakdown"].values()) == config["capex"]["usd_total"]
    assert changes[0] == {
        "path": "capex.usd_total",
        "base": 50_000_000.0,
        "case": 54_000_000.0,
    }


def test_tariff_writes_the_field_named_by_the_case_currency() -> None:
    raw = _synthetic_case(
        "tariff_reference",
        {
            "tariff_per_kwh": {"value": 0.083, "provenance": "x"},
            "currency": {"value": "EUR", "provenance": "x"},
        },
    )
    case = parse_what_if_case(raw)
    config, changes = build_case_config(case, _synthetic_base(), case.variants()[0])
    assert config["tariff"]["eur_per_kwh"] == 0.083
    assert changes == [{"path": "tariff.eur_per_kwh", "base": 0.071, "case": 0.083}]


def test_the_loader_carries_no_site_specific_value() -> None:
    """Every site figure lives in the case YAML; the module names none (#1403)."""
    source = inspect.getsource(what_if)
    for token in ("dutch", "kalpitiya", "puttalam", "norochcholai", "wariyapola"):
        assert token not in source.lower(), token
    for literal in ("25.73", "20.3", "lkr_per_kwh"):
        assert literal not in source, literal


# ----------------------------------------------------------- end-to-end, real engine


def _run(name: str) -> Dict[str, Any]:
    case = load_what_if_case(CASE_DIR / f"{name}.yaml", repo_root=REPO_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_what_if_case(case)


def _report(variant: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {row["kpi"]: row for row in variant["report"]}


def test_running_a_case_leaves_the_base_scenario_file_untouched() -> None:
    case = load_what_if_case(CASE_DIR / "tariff_reference.yaml", repo_root=REPO_ROOT)
    before = hashlib.sha256(case.base_scenario.read_bytes()).hexdigest()
    result = _run("tariff_reference")
    assert hashlib.sha256(case.base_scenario.read_bytes()).hexdigest() == before
    base = result["base"]["kpis"]
    assert base["project_irr"] == pytest.approx(LENDER_PROJECT_IRR, rel=1e-12)
    assert base["project_npv"] == pytest.approx(LENDER_PROJECT_NPV, rel=1e-12)
    assert result["case"]["canonical"] is False


def test_grid_delay_raises_idc_and_cuts_value_more_the_longer_it_runs() -> None:
    result = _run("grid_connection_delay")
    six, twelve, twenty_four = (_report(v) for v in result["variants"])
    # Six months keeps COD and the construction window, so it moves no
    # Financing_Terms input; it only cuts operating-year-1 export.
    six_paths = [c["path"] for c in result["variants"][0]["changes"]]
    assert six_paths == ["project.first_year_grid_unavailable_months"]
    for key in ("project_npv", "project_irr"):
        assert six[key]["delta"] < 0
        assert twelve[key]["case"] < six[key]["case"]
        assert twenty_four[key]["case"] < twelve[key]["case"]
    assert twelve["total_idc_usd"]["delta"] > 0
    assert twenty_four["total_idc_usd"]["case"] > twelve["total_idc_usd"]["case"]
    # Liquidity: every delay leaves less debt capacity, so equity funds more.
    base_equity = result["base"]["sources_and_uses"]["sources"]["equity_usd"]
    for variant in result["variants"]:
        assert variant["sources_and_uses"]["sources"]["equity_usd"] > base_equity
    for variant in result["variants"]:
        assert variant["sources_and_uses"]["balanced"] is True


def test_zero_connection_amount_reproduces_the_base_exactly() -> None:
    result = _run("developer_funded_connection")
    (variant,) = result["variants"]
    assert variant["kpis"] == result["base"]["kpis"]


def test_a_connection_amount_is_financed_as_capex() -> None:
    raw = _case_raw("developer_funded_connection")
    raw["parameters"]["connection_capex_usd"]["value"] = 10_000_000
    case = parse_what_if_case(raw, repo_root=REPO_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run_what_if_case(case)
    (variant,) = result["variants"]
    uses_base = result["base"]["sources_and_uses"]["uses"]["capex_usd"]
    uses_case = variant["sources_and_uses"]["uses"]["capex_usd"]
    assert uses_case - uses_base >= 10_000_000
    assert _report(variant)["project_npv"]["delta"] < 0


def test_the_tariff_reference_raises_revenue_and_value() -> None:
    result = _run("tariff_reference")
    (variant,) = result["variants"]
    report = _report(variant)
    assert report["total_cfads_usd"]["delta"] > 0
    assert report["project_irr"]["delta"] > 0
    assert report["project_npv"]["delta"] > 0
    assert variant["changes"] == [
        {"path": "tariff.lkr_per_kwh", "base": 20.3, "case": 25.73}
    ]
