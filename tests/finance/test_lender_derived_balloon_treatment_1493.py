"""Scenarios that claim the lender case's debt stack resolve the balloon the same way (#1493).

#1492 (#1396 part B) moved the lender case to ``balloon_treatment: refinance``. Four
scenarios describe themselves as sharing the lender case's debt stack, but kept
``cash_sweep``, so a capex or technology comparison against the canon mixed a
balloon-treatment difference into what it presented as a capex or technology difference.
They now follow the lender case on its assumed refinance terms. These tests keep the
treatment and the terms in step with the lender case, and check that the two capex
variants (which carry a balloon) actually refinance it on those YAML terms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.pipeline_v14_enhanced import run_v14_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
LENDER = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"

#: Scenarios whose header says they share the lender case's debt stack (#1493).
CAPEX_VARIANTS = (
    "dutchbay_capex_eia_prudent_2025Q4.yaml",
    "dutchbay_capex_sinohydro_lean_2025Q4.yaml",
)
HYBRIDS = (
    "dutchbay_hybrid_bess_2025Q4.yaml",
    "dutchbay_hybrid_windsolar_2025Q4.yaml",
)
REFINANCE_TERMS = (
    "max_refinance_pct",
    "refinance_rate_premium",
    "refinance_tenor_years",
)


def _load(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.mark.parametrize("name", CAPEX_VARIANTS + HYBRIDS)
def test_balloon_treatment_and_terms_match_the_lender_case(name: str) -> None:
    lender = _load(LENDER)
    scenario = _load(SCENARIOS / name)

    assert lender["Financing_Terms"]["balloon_treatment"] == "refinance"
    assert scenario["Financing_Terms"]["balloon_treatment"] == "refinance", name
    for key in REFINANCE_TERMS:
        assert (
            scenario["constraints"]["refinancing"][key]
            == lender["constraints"]["refinancing"][key]
        ), f"{name}: constraints.refinancing.{key}"
    assert (
        scenario["constraints"]["min_dscr_covenant"]
        == lender["constraints"]["min_dscr_covenant"]
    ), name


@pytest.mark.parametrize("name", CAPEX_VARIANTS)
def test_capex_variant_refinances_its_balloon_on_the_yaml_terms(name: str) -> None:
    result = run_v14_pipeline(str(SCENARIOS / name))
    debt = result["debt_result"]
    refinance = debt["refinance"]

    assert debt["balloon_remaining"] > 0.0
    assert refinance["principal_usd"] == pytest.approx(debt["balloon_remaining"])
    assert refinance["terms_basis"] == "assumption_no_term_sheet"
    assert refinance["terms_source"] == {
        "tenor_years": "constraints.refinancing.refinance_tenor_years",
        "rate_premium": "constraints.refinancing.refinance_rate_premium",
    }
    assert refinance["tenor_years"] == 3
    assert refinance["rate_premium"] == pytest.approx(0.02)
    # The coverage test of the refinanced tranche uses the scenario's 1.30 covenant (#1668).
    assert refinance["coverage_floor"] == pytest.approx(1.30)


@pytest.mark.parametrize("name", HYBRIDS)
def test_hybrid_has_no_balloon_so_refinance_is_inert(name: str) -> None:
    result = run_v14_pipeline(str(SCENARIOS / name))
    debt = result["debt_result"]

    assert debt["balloon_pct"] == 0.0
    assert debt["refinance"] is None
