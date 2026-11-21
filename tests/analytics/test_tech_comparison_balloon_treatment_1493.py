"""The comparison section states each case's balloon treatment (#1493, third clause).

#1735 moved the capex variants and the hybrids onto the lender case's ``refinance``
treatment. The cross-technology comparison block can still list cases that resolve a balloon
differently (a cash-sweep base case beside the refinancing lender case, say), and then their
equity figures mix the treatment difference into what the table presents as a technology or
capex difference. Each column now states the treatment and the balloon its run published, and
the section carries a caveat when the cases that carry a balloon resolve it differently. The
values are read from each run's published ``debt_result``; no figure is recomputed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    TechComparisonBlock,
    _build_tech_comparison,
    build_report_context,
)
from app.reports.tech_comparison_emit import build_tech_comparison_for_scenarios

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
LENDER = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"
HYBRID = SCENARIOS / "dutchbay_hybrid_windsolar_2025Q4.yaml"
CAPEX_EIA = SCENARIOS / "dutchbay_capex_eia_prudent_2025Q4.yaml"
BASECASE = SCENARIOS / "dutchbay_basecase_2025Q4.yaml"

_CAVEAT = "Balloon treatments differ."


def _kpis(treatment: Optional[str], balloon: Optional[float]) -> Dict[str, Any]:
    return {
        "project_irr": 0.02,
        "equity_irr": -0.05,
        "balloon_treatment": treatment,
        "balloon_at_maturity_usd": balloon,
    }


def _render(block: TechComparisonBlock) -> str:
    case = CaseResult(
        status="success",
        scenario_variant="wind",
        kpis={"project_irr": 0.02, "equity_irr": -0.05, "discount_rate_used": 0.10},
        run_manifest=None,
    )
    context = build_report_context(
        case, generated_at="2026-11-21T00:00:00+00:00", tech_comparison=block
    )
    return render_report_html(context)


def _block(*cases: tuple[str, Dict[str, Any]]) -> TechComparisonBlock:
    block = _build_tech_comparison(list(cases))
    assert block is not None
    return block


def test_each_row_carries_its_published_treatment_and_balloon() -> None:
    block = _block(
        ("Wind", _kpis("refinance", 26_560_551.7)),
        ("Hybrid", _kpis("refinance", 0.0)),
    )
    wind, hybrid = block.rows
    assert (wind.balloon_treatment, wind.balloon_at_maturity_usd) == (
        "refinance",
        pytest.approx(26_560_551.7),
    )
    assert wind.carries_balloon is True
    assert hybrid.carries_balloon is False


def test_the_report_restates_the_engines_balloon_threshold() -> None:
    """The report layer restates the engine's repaid threshold; the two cannot move alone."""
    from app.reports.report_model import _TECH_COMPARISON_BALLOON_TOL_USD
    from finance.debt_v14 import _BALLOON_TOL

    assert _TECH_COMPARISON_BALLOON_TOL_USD == _BALLOON_TOL


def test_the_balloon_threshold_is_the_engines() -> None:
    """At or below the engine's repaid threshold no balloon is carried; above it one is."""
    from finance.debt_v14 import _BALLOON_TOL

    at, above = _block(
        ("At", _kpis("refinance", _BALLOON_TOL)),
        ("Above", _kpis("refinance", _BALLOON_TOL + 0.01)),
    ).rows
    assert at.carries_balloon is False
    assert above.carries_balloon is True


def test_rows_without_the_keys_carry_none() -> None:
    (row,) = _block(("Legacy", {"project_irr": 0.02})).rows
    assert row.balloon_treatment is None
    assert row.balloon_at_maturity_usd is None
    assert row.carries_balloon is False


@pytest.mark.parametrize("bad", [True, "", 7])
def test_a_treatment_that_is_not_a_name_is_dropped(bad: Any) -> None:
    (row,) = _block(("Odd", _kpis(bad, 1e6))).rows
    assert row.balloon_treatment is None


@pytest.mark.parametrize(
    ("cases", "differ"),
    [
        # Two balloons, two treatments: the equity comparison mixes them.
        ((("refinance", 1e6), ("cash_sweep", 1e6)), True),
        # Same treatment on both.
        ((("refinance", 1e6), ("refinance", 2e6)), False),
        # A case left with no balloon still counts: the treatment can change the debt
        # itself (an amortize case is resized to leave none), so equity still differs.
        ((("refinance", 1e6), ("amortize", 0.0)), True),
        ((("refinance", 1e6), ("cash_sweep", None)), True),
        ((("refinance", 0.0), ("refinance", 0.0)), False),
        # An unpublished treatment is not counted as a third one.
        ((("refinance", 1e6), (None, 1e6)), False),
    ],
)
def test_treatments_differ_when_any_two_cases_publish_different_ones(
    cases: Any, differ: bool
) -> None:
    block = _block(*[(f"c{i}", _kpis(t, b)) for i, (t, b) in enumerate(cases)])
    assert block.balloon_treatments_differ is differ


def test_the_section_states_each_treatment_and_the_caveat_when_they_differ() -> None:
    html = _render(
        _block(
            ("Lender case", _kpis("refinance", 26_560_551.7)),
            ("Base case", _kpis("cash_sweep", 98_085_363.1)),
            ("Hybrid", _kpis("refinance", 0.0)),
            ("Legacy", {"project_irr": 0.02}),
        )
    )
    assert "Balloon treatment" in html
    assert "Balloon at maturity" in html
    assert ">refinance<" in html
    assert ">cash sweep<" in html
    assert ">refinance (no balloon arises)<" in html
    assert _CAVEAT in html
    # The difference reaches more than the equity rows (#1855 domain review).
    caveat = " ".join(html[html.index(_CAVEAT) :].split("</p>")[0].split())
    assert "equity figures most of all" in caveat
    assert "project IRR, project NPV and CFADS" in caveat


def test_the_caveat_fires_for_a_case_its_treatment_left_with_no_balloon() -> None:
    """An amortize case leaves no balloon, but its treatment still moved its equity."""
    html = _render(
        _block(
            ("Lender case", _kpis("refinance", 26_560_551.7)),
            ("Amortising variant", _kpis("amortize", 0.0)),
        )
    )
    assert ">amortize (no balloon arises)<" in html
    assert _CAVEAT in html


def test_no_caveat_when_every_balloon_is_resolved_the_same_way() -> None:
    html = _render(
        _block(
            ("Lender case", _kpis("refinance", 26_560_551.7)),
            ("Capex variant", _kpis("refinance", 8_546_570.8)),
        )
    )
    assert ">refinance<" in html
    assert _CAVEAT not in html


def test_build_reads_each_runs_published_treatment_and_balloon() -> None:
    """The canonical runs' own published values, for the cases #1493 names."""
    pairs = [
        ("Lender case", str(LENDER)),
        ("Hybrid", str(HYBRID)),
        ("Capex EIA-prudent", str(CAPEX_EIA)),
        ("Base case", str(BASECASE)),
    ]
    block = build_tech_comparison_for_scenarios(pairs)
    for (label, path), row in zip(pairs, block.rows, strict=True):
        debt = run_v14_pipeline(config=path, validation_mode="strict")["debt_result"]
        assert row.label == label
        assert row.balloon_treatment == debt["balloon_treatment"]
        assert row.balloon_at_maturity_usd == pytest.approx(debt["balloon_remaining"])
    by_label = {row.label: row for row in block.rows}
    # The lender-derived cases follow the lender case (#1735); the hybrid amortises fully.
    assert by_label["Lender case"].balloon_treatment == "refinance"
    assert by_label["Capex EIA-prudent"].balloon_treatment == "refinance"
    assert by_label["Hybrid"].carries_balloon is False
    # The base case still sweeps, so beside the lender case the caveat applies.
    assert by_label["Base case"].balloon_treatment == "cash_sweep"
    assert block.balloon_treatments_differ is True
    lender_and_variant = build_tech_comparison_for_scenarios(pairs[:3])
    assert lender_and_variant.balloon_treatments_differ is False
