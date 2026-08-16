"""Cross-technology headline-KPI comparison report emitter (#745 slice-1) — tests.

The emitter (``app.reports.tech_comparison_emit``) is the opt-in, batch-path caller that runs each
compared config through the CANONICAL pipeline and renders the lender report section. These tests
pin:
  - the PURE projection maps fixture KPI dicts into rows correctly (a report_model-level unit);
  - the emitter runs 2 canonical configs and the wind column KPIs match ``run_v14_pipeline`` on the
    lendercase EXACTLY (the lender-integrity reconciliation basis, per #745);
  - fail-loud (CESSPIT) when the scenario list is absent / empty / malformed, or a listed path is
    missing;
  - default-off byte-identity: a context WITHOUT ``tech_comparison`` renders identically to one
    built with the section omitted;
  - the latency guard: ``app/api/main.py`` (the synchronous HTTP route) is NOT modified by this
    slice — the multi-run comparison must never be reachable from the sync route (#645).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    TechComparisonBlock,
    _build_tech_comparison,
    build_report_context,
)
from app.reports.tech_comparison_emit import (
    build_tech_comparison_for_scenarios,
    emit_tech_comparison_report_from_pipeline,
    resolve_tech_comparison_scenarios,
)
from tests._canon import LENDER_PROJECT_IRR as _WIND_PROJECT_IRR

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
HYBRID_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"

#: The wind lendercase committed headline project IRR (tests/_canon.py, #955) — the
#: column must reconcile to this exactly.


# --------------------------------------------------------------------------- #
# (a) Pure projection
# --------------------------------------------------------------------------- #
def test_projection_maps_kpi_dicts_into_rows() -> None:
    """``_build_tech_comparison`` reshapes (label, kpis) pairs into one row per case (pure)."""
    cases = [
        (
            "Wind",
            {
                "project_irr": 0.0146,
                "equity_irr": -0.0584,
                "min_dscr": 1.2857,
                "project_npv": -79273039.21,
                "total_cfads_usd": 191111047.68,
                # gearing intentionally absent -> em-dash / None.
            },
        ),
        (
            "Hybrid",
            {
                "project_irr": 0.0186,
                "equity_irr": -0.0285,
                "min_dscr": 1.30,
                "project_npv": -92672410.10,
                "total_cfads_usd": 235664760.14,
                "gearing": 0.4275,
            },
        ),
    ]
    block = _build_tech_comparison(cases)
    assert isinstance(block, TechComparisonBlock)
    assert [r.label for r in block.rows] == ["Wind", "Hybrid"]
    wind, hybrid = block.rows
    assert wind.project_irr == pytest.approx(0.0146)
    assert wind.total_cfads_usd == pytest.approx(191111047.68)
    # A KPI absent from the run projects to None (em-dash), never fabricated.
    assert wind.gearing is None
    assert hybrid.gearing == pytest.approx(0.4275)


def test_projection_empty_cases_is_none() -> None:
    """No cases -> None (section omitted). The emitter enforces the config-required list fail-loud."""
    assert _build_tech_comparison([]) is None


def test_projection_ignores_non_finite_and_bool() -> None:
    """A non-finite or bool KPI value projects to None rather than a garbage/coerced number."""
    block = _build_tech_comparison(
        [("X", {"project_irr": float("nan"), "min_dscr": True, "equity_irr": 0.02})]
    )
    assert block is not None
    (row,) = block.rows
    assert row.project_irr is None  # NaN -> None
    assert row.min_dscr is None  # bool -> None (never coerced to 1.0)
    assert row.equity_irr == pytest.approx(0.02)


# --------------------------------------------------------------------------- #
# (b) Emitter: canonical basis reconciliation
# --------------------------------------------------------------------------- #
def test_build_for_scenarios_reconciles_wind_column_to_canonical() -> None:
    """The wind column's project IRR equals ``run_v14_pipeline`` on the lendercase EXACTLY (#745)."""
    block = build_tech_comparison_for_scenarios(
        [("Wind", str(WIND_SCENARIO)), ("Hybrid", str(HYBRID_SCENARIO))]
    )
    assert [r.label for r in block.rows] == ["Wind", "Hybrid"]
    wind, hybrid = block.rows
    # The independent canonical run of the same config.
    wind_run = run_v14_pipeline(config=str(WIND_SCENARIO), validation_mode="strict")
    assert wind.project_irr == wind_run["kpis"]["project_irr"]
    assert wind.project_irr == _WIND_PROJECT_IRR
    # Gearing is injected from the dual-DSCR solved gearing (the report's OWN gearing
    # source), so the column reconciles to the report instead of rendering blank.
    assert wind.gearing == pytest.approx(
        wind_run["debt_result"]["dual_dscr"]["solved_gearing"]
    )
    assert wind.gearing == pytest.approx(0.355)
    # The hybrid column is a distinct, non-trivial economics (a real second column).
    assert hybrid.project_irr is not None
    assert hybrid.project_irr != wind.project_irr
    assert hybrid.gearing is not None and hybrid.gearing != wind.gearing


def test_emit_renders_comparison_section_through_canonical_runs(tmp_path) -> None:
    """The full caller: a finance run + 2 canonical runs → a rendered report carrying the section."""
    result = run_v14_pipeline(config=str(WIND_SCENARIO), validation_mode="strict")
    assert isinstance(result, dict) and result.get("kpis")

    out_html = tmp_path / "tech_comparison_report.html"
    written = emit_tech_comparison_report_from_pipeline(
        result,
        WIND_SCENARIO,
        out_html,
        scenarios=[
            {"label": "Wind", "config": str(WIND_SCENARIO)},
            {"label": "Hybrid", "config": str(HYBRID_SCENARIO)},
        ],
        generated_at="2026-07-05T00:00:00+00:00",
    )
    assert written == out_html
    html = out_html.read_text(encoding="utf-8")
    assert "Cross-Technology Comparison" in html
    # Both column labels render; the wind column carries the reconciled headline IRR.
    assert "Wind" in html and "Hybrid" in html
    # The report's own Project IRR (-0.12%) appears — proving reconciliation.
    assert "-0.12%" in html
    # No server filesystem path is leaked into the lender document.
    assert str(tmp_path) not in html


# --------------------------------------------------------------------------- #
# (c) Fail-loud (CESSPIT)
# --------------------------------------------------------------------------- #
def test_resolve_rejects_absent_list() -> None:
    with pytest.raises(ValueError, match="tech_comparison.scenarios"):
        resolve_tech_comparison_scenarios(None)


def test_resolve_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        resolve_tech_comparison_scenarios([])


def test_resolve_rejects_entry_missing_config() -> None:
    with pytest.raises(ValueError, match="config"):
        resolve_tech_comparison_scenarios([{"label": "Wind"}])


def test_resolve_rejects_entry_missing_label() -> None:
    with pytest.raises(ValueError, match="label"):
        resolve_tech_comparison_scenarios([{"config": str(WIND_SCENARIO)}])


def test_resolve_rejects_missing_scenario_path() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        resolve_tech_comparison_scenarios(
            [{"label": "Ghost", "config": "scenarios/does_not_exist.yaml"}]
        )


def test_emit_fails_loud_on_absent_scenarios(tmp_path) -> None:
    """The emitter itself fails loud when the opted-in caller supplied no scenarios list."""
    result = run_v14_pipeline(config=str(WIND_SCENARIO), validation_mode="strict")
    with pytest.raises(ValueError):
        emit_tech_comparison_report_from_pipeline(
            result, WIND_SCENARIO, tmp_path / "x.html", scenarios=[]
        )


# --------------------------------------------------------------------------- #
# (d) Default-off byte-identity
# --------------------------------------------------------------------------- #
def _minimal_case() -> CaseResult:
    kpis: Dict[str, float] = {
        "project_irr": 0.0146,
        "equity_irr": -0.0584,
        "min_dscr": 1.2857,
        "discount_rate_used": 0.10,
    }
    return CaseResult(
        status="success", scenario_variant="wind", kpis=kpis, run_manifest=None
    )


def test_default_off_renders_identically_to_omitted() -> None:
    """A context WITHOUT tech_comparison renders byte-identically to one that omits the block."""
    generated = "2026-07-05T00:00:00+00:00"
    ctx_default = build_report_context(_minimal_case(), generated_at=generated)
    ctx_explicit_none = build_report_context(
        _minimal_case(), generated_at=generated, tech_comparison=None
    )
    assert ctx_default.tech_comparison is None
    assert render_report_html(ctx_default) == render_report_html(ctx_explicit_none)
    # The section marker is absent when the block is omitted.
    assert "Cross-Technology Comparison" not in render_report_html(ctx_default)


# --------------------------------------------------------------------------- #
# (e) Latency guard — the sync HTTP route is untouched
# --------------------------------------------------------------------------- #
def test_sync_api_route_is_not_modified_by_this_slice() -> None:
    """Latency guard (#645): the multi-run comparison must never be reachable from the sync route.

    Each column is a full-pipeline run; wiring it into ``app/api/main.py`` would reintroduce the
    latency the #645 ledger forbids. The Optional-default-None field on ReportContext keeps the sync
    route fast, so main.py must carry no reference to the comparison.
    """
    main_src = (REPO_ROOT / "app" / "api" / "main.py").read_text(encoding="utf-8")
    assert "tech_comparison" not in main_src
    assert "tech_comparison_emit" not in main_src
