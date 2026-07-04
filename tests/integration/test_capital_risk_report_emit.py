"""End-to-end: the #779 opt-in caller runs the CANONICAL MC and renders the capital-risk section.

#776 wired build_report_context to render a CapitalRiskBlock render-when-present, but nothing
supplied one in production, so the section never appeared for a lender. #779 adds the "separate
call" (app.reports.capital_risk_emit) that runs the canonical MC engine (LHS + Iman-Conover) with
monte_carlo.allow_toy_fallback forced false over a bounded n and renders a lender report carrying
the section.

These tests drive the REAL lender scenario through the canonical MC (the gate #776 could not have:
its render test fed a synthetic report). They assert the section renders with the actual MC
provenance (rank correlation — proving the canonical, correlated engine ran, not a toy), leaks no
server path, and that a scenario without sampled drivers fails loud (CESSPIT).

GWTF:
    - CESSPIT: the missing-parameters guard asserts a raise.
    - CCCDIR: consumes the canonical engine + the build_report_context gateway.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from app.reports import capital_risk_emit
from app.reports.capital_risk_emit import (
    LENDER_GRADE_MIN_TRIALS,
    build_capital_risk_report_for_scenario,
    emit_capital_risk_report_from_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

# Bounded trial count for a fast integration run: clears the engine's VaR/CVaR crash-floor (20)
# while keeping the per-trial full-evaluation cost low. Mirrors
# tests/integration/test_mc_canonical_scenario.py, which pins that this scenario runs 24 canonical
# trials with zero toy fallback. This is a deliberately SUB-lender-grade WIRING smoke — it is NOT a
# statistically adequate sample, so the tests below must explicitly lower ``min_trials`` past the
# LENDER_GRADE_MIN_TRIALS (1000) production floor (which a separate test pins is enforced).
_N_TRIALS = 24
_SEED = 42


def test_build_report_for_scenario_runs_the_canonical_mc(tmp_path) -> None:
    """The report is built from the real canonical MC (correlated LHS), not a toy fallback."""
    pytest.importorskip("matplotlib")
    report = build_capital_risk_report_for_scenario(
        LENDER_SCENARIO, tmp_path, n_trials=_N_TRIALS, min_trials=_N_TRIALS, seed=_SEED
    )
    assert report.n_trials == _N_TRIALS
    assert report.scenario == LENDER_SCENARIO.stem
    # The method is derived from the canonical result's metadata: the lender scenario enables the
    # Iman-Conover correlation block, so a faithful provenance string names it. A toy/fallback run
    # (or a non-correlated engine) could not produce this — it is the proof the real MC ran.
    assert report.method == "lhs sampling, rank correlation"
    # The NPV-distribution PNG was written under the output dir.
    assert Path(report.npv_distribution_png).exists()


def test_emit_renders_capital_risk_section_through_real_mc(tmp_path) -> None:
    """The full caller: finance run + canonical MC → a rendered report carrying the section."""
    pytest.importorskip("matplotlib")
    result = run_v14_pipeline(config=str(LENDER_SCENARIO), validation_mode="strict")
    assert isinstance(result, dict) and result.get("kpis")

    out_html = tmp_path / "capital_risk_report.html"
    written = emit_capital_risk_report_from_pipeline(
        result,
        LENDER_SCENARIO,
        out_html,
        n_trials=_N_TRIALS,
        min_trials=_N_TRIALS,  # sub-lender-grade wiring smoke (see module note)
        seed=_SEED,
        generated_at="2026-07-04T00:00:00+00:00",
    )
    assert written == out_html and out_html.exists()

    html = out_html.read_text(encoding="utf-8")
    assert "Capital Risk — Monte-Carlo Distribution" in html
    assert f"over {_N_TRIALS} trials" in html
    assert "Covenant-breach probability" in html
    assert "Value at Risk" in html
    # The methodology string is the ACTUAL MC provenance (correlated canonical engine), not a
    # hardcoded claim — the strongest signal the lender-grade MC path really ran.
    assert "lhs sampling, rank correlation" in html
    # The NPV chart is embedded as a self-contained data URI — no absolute server path leaks.
    assert 'src="data:image/png;base64,' in html
    assert str(tmp_path) not in html


def test_scenario_without_mc_parameters_fails_loud(monkeypatch, tmp_path) -> None:
    """CESSPIT: opting in on a scenario with no monte_carlo.parameters raises, not renders empty."""
    stub: Dict[str, Any] = {"monte_carlo": {"enabled": True}}  # no parameters list
    monkeypatch.setattr(capital_risk_emit, "load_scenario_config", lambda _p: stub)
    with pytest.raises(ValueError, match="monte_carlo.parameters"):
        # min_trials lowered so the floor guard does not mask the parameters guard under test.
        build_capital_risk_report_for_scenario(
            "no_mc.yaml", tmp_path, n_trials=_N_TRIALS, min_trials=_N_TRIALS
        )


def test_below_lender_grade_floor_fails_loud(tmp_path) -> None:
    """CESSPIT: at the DEFAULT floor, a thin sample refuses to build a lender-grade report.

    Guards the sample-adequacy floor (LENDER_GRADE_MIN_TRIALS = 1000): with the default min_trials,
    a small n_trials must raise BEFORE running the (heavy) MC — so no lender ever sees a VaR/CVaR
    number computed off a statistically inadequate tail. Fast: it raises before any evaluation.
    """
    assert LENDER_GRADE_MIN_TRIALS >= 1000
    with pytest.raises(ValueError, match=r"lender-grade VaR/CVaR tail"):
        build_capital_risk_report_for_scenario(
            LENDER_SCENARIO, tmp_path, n_trials=LENDER_GRADE_MIN_TRIALS - 1
        )


def test_invalid_npv_metric_fails_fast_before_mc(tmp_path) -> None:
    """CESSPIT pre-flight: a mistyped npv_metric raises BEFORE the bounded MC is wasted.

    The downstream renderer already guards the NPV_METRICS set, but only after the full run; this
    hoists the check so an operator misconfiguration fails immediately (fast, no evaluation).
    """
    with pytest.raises(ValueError, match=r"npv_metric must be one of"):
        build_capital_risk_report_for_scenario(
            LENDER_SCENARIO,
            tmp_path,
            n_trials=_N_TRIALS,
            min_trials=_N_TRIALS,
            npv_metric="ebitda_npv",  # not in NPV_METRICS
        )
