"""An unresolved project IRR is reported as undefined, never as 0.0 (#1494, O-6).

Before #1494, ``calculate_scenario_kpis`` logged "Project IRR undefined" and then let the
stable-surface default write ``project_irr = irr = 0.0``. A 0.0 is finite and reads as a
genuine break-even, so every consumer downstream (tornado, report, API, solvers) saw a
number the solver never produced.

The independent oracle for "undefined" is ``finance.irr.approx_project_irr`` itself, which
already returns ``None`` for these cashflows and is pinned by ``tests/finance/
test_irr_coverage.py``. These tests check that the KPI surface reports what that function
says, rather than replacing it with 0.0. Genuine zero, defined and not-computed controls
pin the cases that must NOT change.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict

import pytest

from analytics.core.metrics import (
    PROJECT_IRR_COMPUTED,
    PROJECT_IRR_NOT_COMPUTED,
    PROJECT_IRR_UNDEFINED,
    calculate_scenario_kpis,
)
from finance.irr import approx_project_irr

#: All-negative CFADS: no rate makes the NPV zero.
_ALL_NEGATIVE = {"config": {"capex_total_usd": 1_000.0}, "cfads": [-50.0] * 10}
#: A positive root far above the solver's 500% cap (capex 1, CFADS 100 a year).
_ABOVE_SEARCH_BOUND = {"config": {"capex_total_usd": 1.0}, "cfads": [100.0] * 10}


def _kpis(case: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    return calculate_scenario_kpis(
        config=case["config"], cfads_series_usd=case["cfads"], **kwargs
    )


# ---------------------------------------------------------------------------
# KPI production
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "case", [_ALL_NEGATIVE, _ABOVE_SEARCH_BOUND], ids=["all_negative", "above_bound"]
)
def test_unresolved_project_irr_is_none_not_zero(case: Dict[str, Any]) -> None:
    # The oracle: the singleton solver finds no root for these cashflows.
    assert approx_project_irr(case["cfads"], case["config"]["capex_total_usd"]) is None

    result = _kpis(case)

    assert "project_irr" in result and result["project_irr"] is None
    assert "irr" in result and result["irr"] is None
    assert result["project_irr_status"] == PROJECT_IRR_UNDEFINED


def test_unresolved_project_irr_warns_that_it_is_reported_as_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="analytics.core.metrics"):
        _kpis(_ALL_NEGATIVE)
    assert any(
        "Project IRR undefined" in rec.getMessage() and "None" in rec.getMessage()
        for rec in caplog.records
    )


def test_genuine_zero_project_irr_stays_computed() -> None:
    capex, cfads = 100.0, [10.0] * 10  # lifetime CFADS == capex, so the IRR is ~0%
    result = calculate_scenario_kpis(
        config={"capex_total_usd": capex}, cfads_series_usd=cfads
    )
    assert result["project_irr_status"] == PROJECT_IRR_COMPUTED
    assert result["project_irr"] is not None
    assert result["project_irr"] == pytest.approx(0.0, abs=1e-6)
    assert result["irr"] == result["project_irr"]


def test_defined_project_irr_is_the_solver_value() -> None:
    capex, cfads = 1_000.0, [300.0] * 6
    result = calculate_scenario_kpis(
        config={"capex_total_usd": capex}, cfads_series_usd=cfads
    )
    expected = approx_project_irr(cfads, capex)
    assert expected is not None and expected > 0.0
    assert result["project_irr"] == expected
    assert result["irr"] == expected
    assert result["project_irr_status"] == PROJECT_IRR_COMPUTED


def test_not_computed_project_irr_keeps_the_zero_placeholder_and_says_so() -> None:
    # No capex: the solve is never attempted. The 0.0 API-stability default is unchanged
    # (pinned by test_core_metrics_coverage); the status now marks it as a placeholder.
    result = calculate_scenario_kpis(cfads_series_usd=[300.0] * 6)
    assert result["project_irr"] == 0.0
    assert result["irr"] == 0.0
    assert result["project_irr_status"] == PROJECT_IRR_NOT_COMPUTED


def test_valuation_supplied_irr_is_computed() -> None:
    result = _kpis(_ALL_NEGATIVE, valuation={"irr": 0.042})
    assert result["project_irr"] == 0.042
    assert result["project_irr_status"] == PROJECT_IRR_COMPUTED


def test_non_finite_valuation_irr_falls_back_to_the_solver() -> None:
    result = _kpis(_ALL_NEGATIVE, valuation={"irr": float("nan")})
    assert result["project_irr"] is None
    assert result["project_irr_status"] == PROJECT_IRR_UNDEFINED


def test_equity_irr_no_waterfall_sentinel_is_unchanged() -> None:
    # #1494 disposition: the not-run equity-waterfall 0.0 sentinel is out of scope and
    # stays as it is, even when the project IRR is undefined.
    result = _kpis(_ALL_NEGATIVE)
    assert result["equity_irr"] == 0.0


# ---------------------------------------------------------------------------
# Pipeline and contract
# ---------------------------------------------------------------------------
#: Opex above revenue on the generic unit-test scenario: every CFADS year is negative.
_UNDEFINED_OVERRIDES = {"opex.usd_per_year": 60_000_000}
_SCENARIO = "scenarios/good_unit_test.yaml"


@pytest.fixture(scope="module")
def undefined_full_result() -> Dict[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides

    return evaluate_with_overrides(
        _SCENARIO, overrides=_UNDEFINED_OVERRIDES, return_full_result=True
    )


def test_pipeline_carries_undefined_project_irr_to_kpis_and_contract(
    undefined_full_result: Dict[str, Any],
) -> None:
    kpis = undefined_full_result["kpis"]
    assert kpis["project_irr"] is None
    assert kpis["irr"] is None
    assert kpis["project_irr_status"] == PROJECT_IRR_UNDEFINED
    assert undefined_full_result["scenario_result"]["project_irr"] is None


def test_numeric_kpi_surface_omits_undefined_project_irr() -> None:
    # Unchanged normalizer behaviour (out of #1494's scope): an undefined KPI is dropped
    # from the numeric surface, so absent here means undefined, never 0.0.
    from analytics.evaluation_v14 import evaluate_with_overrides

    kpis = evaluate_with_overrides(_SCENARIO, overrides=_UNDEFINED_OVERRIDES)
    assert "project_irr" not in kpis
    assert "irr" not in kpis


def test_committed_scenario_project_irr_stays_defined() -> None:
    from analytics.evaluation_v14 import evaluate_with_overrides

    result = evaluate_with_overrides(_SCENARIO, return_full_result=True)
    kpis = result["kpis"]
    assert kpis["project_irr_status"] == PROJECT_IRR_COMPUTED
    assert isinstance(kpis["project_irr"], float) and math.isfinite(kpis["project_irr"])
    assert result["scenario_result"]["project_irr"] == kpis["project_irr"]


def test_irr_log_formatter_names_undefined() -> None:
    from analytics.pipeline_v14_enhanced import _format_irr_for_log

    assert _format_irr_for_log(None) == "undefined"
    assert _format_irr_for_log(0.1234) == "12.34%"


# ---------------------------------------------------------------------------
# API and report surfaces
# ---------------------------------------------------------------------------
def test_case_result_carries_undefined_project_irr_as_null(
    undefined_full_result: Dict[str, Any],
) -> None:
    from app.api.responses import CaseResult

    case = CaseResult.from_pipeline_result(
        undefined_full_result, scenario_variant="unit"
    )
    assert "project_irr" in case.kpis and case.kpis["project_irr"] is None


def test_run_pipeline_kpi_block_carries_status() -> None:
    from api.pipeline_api import _extract_kpis

    undefined = _extract_kpis(
        {"project_irr": None, "project_irr_status": PROJECT_IRR_UNDEFINED}
    )
    assert undefined.project_irr is None
    assert undefined.project_irr_status == PROJECT_IRR_UNDEFINED

    defined = _extract_kpis({"project_irr": 0.05, "project_irr_status": "computed"})
    assert defined.project_irr == 0.05
    assert defined.project_irr_status == PROJECT_IRR_COMPUTED

    legacy = _extract_kpis({"project_irr": 0.05})
    assert legacy.project_irr_status is None


def test_report_verdict_says_project_irr_is_undefined() -> None:
    from app.reports.report_model import _build_verdict, load_report_config

    kpis = {
        "project_irr": None,
        "discount_rate_used": 0.0854,
        "equity_npv": 1_000_000.0,
        "min_dscr": 1.45,
        "balloon_pct": 0.10,
    }
    verdict = _build_verdict(kpis, load_report_config().covenants)
    assert verdict.project_viable is False
    assert any("Project IRR is undefined" in note for note in verdict.notes)
    assert not any("Project IRR 0.00%" in note for note in verdict.notes)


def test_report_verdict_absent_project_irr_adds_no_undefined_note() -> None:
    from app.reports.report_model import _build_verdict, load_report_config

    verdict = _build_verdict(
        {"discount_rate_used": 0.0854, "min_dscr": 1.45},
        load_report_config().covenants,
    )
    assert not any("Project IRR" in note for note in verdict.notes)


# ---------------------------------------------------------------------------
# Consumers that used to receive 0.0
# ---------------------------------------------------------------------------
def test_wacc_band_reports_undefined_project_irr_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analytics.wacc_sensitivity as ws

    monkeypatch.setattr(
        ws,
        "evaluate_with_overrides",
        lambda *_a, **_k: {"discount_rate_used": 0.09, "project_npv": -1.0},
    )
    rows = ws.ke_band_npv("unused.yaml", [0.12])
    assert rows[0]["project_irr"] is None


def test_capex_monte_carlo_refuses_undefined_project_irr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analytics.cost.mc_capex as mc
    import analytics.pipeline_v14_enhanced as pipeline

    monkeypatch.setattr(
        pipeline,
        "run_v14_pipeline",
        lambda **_k: {"kpis": {"project_irr": None, "equity_irr": None}},
    )
    with pytest.raises(ValueError, match="project IRR is undefined"):
        mc.run_capex_mc(
            {"capex": {"usd_total": 1_000.0}}, n_samples=1, sigma_pct=10.0, seed=7
        )


# ---------------------------------------------------------------------------
# Real-engine reproduction: the web tornado over the assessed case's project IRR
# ---------------------------------------------------------------------------
def test_assessed_case_project_irr_tornado_discloses_undefined_points() -> None:
    """The 22.8% assessed lender case: the project IRR the solver cannot resolve.

    Its CFADS turn negative in the last operating years, so the project NPV changes sign
    twice and has two roots (about -31% and -10%). ``approx_project_irr`` needs a sign
    change between the ends of its range and so returns no rate. Before #1494 the KPI
    surface wrote 0.0 there, and ``default_analysis`` drew a tornado with a 0.00% base,
    13 of 14 driver cases at 0.0 and ``undefined_points == 0``. The inputs mirror
    ``tests/app/test_analysis_tornado_undefined_metric.py``.
    """
    from app.jobs.analysis_runner import _build_assessed_scenario, default_analysis
    from app.jobs.models import AnalysisJobRequest, WindJobRequest
    from app.models.inputs import WindFarmInputs

    wind = WindJobRequest(
        inputs=WindFarmInputs(
            site_name="Dutch Bay",
            capacity_mw=150.0,
            capacity_factor=0.339,
            project_life_years=20,
            ppa_price_lkr_per_kwh=26.0,
            ppa_term_years=20,
            capex_total_usd=195_000_000,
            opex_annual_usd=6_000_000,
            fx_start_lkr_per_usd=333.79,
        ),
        site_lat=8.33,
        site_lon=79.76,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        hub_height_m=119.0,
        resource_mode="weibull",
        weibull_a=8.199,
        weibull_k=2.665,
    )
    export = {
        "scenario": "P75",
        "annual_generation_mwh": 300_000.0,
        "capacity_factor_percent": 22.8,
        "revenue_annual_usd": 20_000_000.0,
        "revenue_cumulative_usd": 400_000_000.0,
        "project_capacity_mw": 150.0,
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10_000.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.3,
        "exchange_rate_lkr_usd": 300.0,
    }
    assessed = _build_assessed_scenario(wind, export)

    out = default_analysis(
        AnalysisJobRequest(analysis_type="tornado", metric="project_irr", wind=wind),
        assessed,
        lambda _step, _message: None,
    )
    result = out["engine_result"]
    meta = result["metadata"]
    bars = result["tornado_results"]
    cases = [
        case
        for bar in bars
        for shock in bar["shock_results"]
        for case in (shock["low_case"], shock["high_case"])
    ]
    assert len(bars) >= 7
    assert meta["undefined_base"] is True
    assert all(math.isnan(bar["base_metric"]) for bar in bars)
    assert meta["undefined_points"] > 0
    # No point is reported as a false break-even.
    assert not any(case == 0.0 for case in cases)


# ---------------------------------------------------------------------------
# finance.irr: a converged bracket on a large project is a root, not "undefined"
# ---------------------------------------------------------------------------
def test_large_project_single_root_resolves_and_matches_numpy_financial() -> None:
    """A USD 1bn single-root project the bisection pinned but called unconverged.

    ``approx_project_irr``'s ``tol`` is an absolute NPV tolerance (1e-6 USD). Here the NPV
    slope near the root is so steep that 50 halvings pin the rate to ~1e-15 while |NPV|
    stays above 1e-6 USD, so before #1494 it returned None, which the KPI surface then
    printed as 0.0. The independent oracle is ``numpy_financial.irr`` on the same
    time-aligned vector (capex at t=0, two zero build periods, then CFADS).
    """
    import numpy_financial as npf

    capex, cfads, construction_years = 1.0e9, [2.0e7] * 25, 2
    expected = float(npf.irr([-capex] + [0.0] * construction_years + cfads))

    got = approx_project_irr(cfads, capex, construction_years=construction_years)

    assert got is not None
    assert got == pytest.approx(expected, abs=1e-12)
    result = calculate_scenario_kpis(
        config={"capex_total_usd": capex, "construction_years": construction_years},
        cfads_series_usd=cfads,
    )
    assert result["project_irr_status"] == PROJECT_IRR_COMPUTED
    assert result["project_irr"] == got


def test_unconverged_bisection_is_still_undefined() -> None:
    # FIN-10 is unchanged: a bracket that is still wide when max_iter runs out is no root.
    assert approx_project_irr([300.0] * 6, 1_000.0, tol=1e-30, max_iter=1) is None
