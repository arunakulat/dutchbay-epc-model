"""The DSRA target is published as an assumption, with the key it came from (#920).

Owner ruling on #920 (2026-11-15): keep the reserve at 6 months of debt service as a
labelled assumption until a term sheet sets it. ``debt_result["funding"]`` now carries
``dsra_target_basis`` (``assumption_no_term_sheet``) and ``dsra_target_source``, the YAML
path the months were read from, or ``code_default`` when no key is authored. The months
and every figure are unchanged.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

LENDER = str(
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def _funding(
    dsra: Optional[Dict[str, Any]] = None,
    reserves: Any = "keep",
    **fin: Any,
) -> Dict[str, Any]:
    cfg = dict(load_scenario_config(LENDER))
    terms = {**cfg["Financing_Terms"], **fin}
    if reserves != "keep":
        terms["reserves"] = reserves
    if dsra is not None:
        terms["dsra"] = dsra
    cfg["Financing_Terms"] = terms
    result = run_v14_pipeline(config=copy.deepcopy(cfg))
    return dict(result["debt_result"]["funding"])


def test_lender_case_labels_its_six_months_as_an_assumption() -> None:
    funding = _funding()
    assert funding["dsra_target_months"] == pytest.approx(6.0)
    assert funding["dsra_target_basis"] == "assumption_no_term_sheet"
    assert funding["dsra_target_source"] == "Financing_Terms.reserves.dsra_months"


@pytest.mark.parametrize(
    ("kwargs", "source", "months"),
    [
        (
            {"dsra": {"target_months": 3}, "dsra_months": 9},
            "Financing_Terms.dsra.target_months",
            3.0,
        ),
        ({"dsra_months": 9}, "Financing_Terms.dsra_months", 9.0),
        ({"reserves": {}}, "code_default", 6.0),
    ],
    ids=["dsra-block", "legacy-key", "code-default"],
)
def test_source_follows_the_resolver_precedence(
    kwargs: Dict[str, Any], source: str, months: float
) -> None:
    funding = _funding(**kwargs)
    assert funding["dsra_target_source"] == source
    assert funding["dsra_target_months"] == pytest.approx(months)
    assert funding["dsra_target_basis"] == "assumption_no_term_sheet"
