"""The lender report prints each tariff's legal status beside the revenue it sets (#1837)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.tariff_legal_status import STATUS_LABELS, resolve_scenario_status
from app.reports import lender_report_emit as lre
from app.reports.dbpl import DbplDependencyError
from app.reports.lender_report_emit import (
    SECTION_SITE_ANALYSES,
    SECTION_TARIFF_STATUS,
    emit_lender_report_from_pipeline,
)
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    compute_report_sensitivity,
)
from app.reports.site_analysis_model import (
    STATUS_COMPLETED,
    SiteAnalysesBlock,
    SiteAnalysisSection,
    SiteAnalysisTable,
)
from app.reports.tariff_status_section import (
    REVENUE_BASIS_FIGURE,
    STORAGE_OPTIONS_KEY,
    label_site_analyses,
)

ROOT = Path(__file__).resolve().parents[2]
WIND = ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
GENERATED_AT = "2026-11-22T00:00:00+00:00"
ANALOGY = STATUS_LABELS["analogy_unpublished"]


def _empty_bundle(
    scenario: Mapping[str, Any], *, profile: Any
) -> ReportSensitivityBundle:
    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )


def _not_called(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("the capital-risk Monte Carlo must not run here")


@pytest.fixture(autouse=True)
def _html_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_print(*_args: Any, **_kwargs: Any) -> Any:
        raise DbplDependencyError("PDF print not exercised by this test")

    monkeypatch.setattr(lre, "_render_pdf", _no_print)


@pytest.fixture(scope="module")
def wind_result() -> Mapping[str, Any]:
    return run_v14_pipeline(config=dict(load_scenario_config(str(WIND))))


def _emit(result: Mapping[str, Any], scenario: Path, out: Path) -> Any:
    return emit_lender_report_from_pipeline(
        result,
        scenario,
        out / "lender_report.html",
        capital_risk_not_run="not run: switched off for this test",
        generated_at=GENERATED_AT,
        require_pdf=False,
        sensitivity_computer=_empty_bundle,
        capital_risk_builder=_not_called,
    )


def _storage_section(html: str) -> str:
    start = html.index("Wind battery options")
    end = html.index("Equipment cost parity", start)
    return html[start:end]


def test_the_wind_report_prints_the_status_beside_revenue(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    out = _emit(wind_result, WIND, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert "Tariff Basis and Legal Status" in html
    assert "until the next tariff revision" in html
    income = html[html.index("<h3>Income statement</h3>") :]
    assert income.index("Revenue rests on 25.73 LKR/kWh: Published") < income.index(
        "<table>"
    )
    assert SECTION_TARIFF_STATUS not in [s.section for s in out.sections_not_run]


def test_no_figure_on_the_analogy_rate_reaches_the_report_without_its_label(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    """Every storage-options figure rests on the analogy rate: each must carry the label."""
    out = _emit(wind_result, WIND, tmp_path)
    section = _storage_section(out.html_path.read_text(encoding="utf-8"))
    basis_row = re.search(
        rf"<td>{re.escape(REVENUE_BASIS_FIGURE)}</td><td>([^<]*)</td>", section
    )
    assert basis_row is not None
    assert f"[{ANALOGY}]" in basis_row.group(1)
    captions = re.findall(r"<caption>([^<]*)</caption>", section)
    assert captions
    assert all(f"[{ANALOGY}]" in c for c in captions)
    assert f"Tariff legal status. {ANALOGY.upper()}" in section


def test_hybrid_and_lender_case_print_their_recorded_statuses(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    hybrid = ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"
    out_hybrid = _emit(wind_result, hybrid, tmp_path / "hybrid")
    html_hybrid = out_hybrid.html_path.read_text(encoding="utf-8")
    assert "Revenue rests on 24.97 LKR/kWh: Analogy, unpublished" in html_hybrid
    assert "pucsl_fit_2026_wind_solar_blended_hybrid" in html_hybrid

    lender = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
    out_lender = _emit(wind_result, lender, tmp_path / "lender")
    html_lender = out_lender.html_path.read_text(encoding="utf-8")
    assert "Revenue rests on 20.30 LKR/kWh: Unconfirmed" in html_lender
    assert "ceb_sppa_unexecuted_wind_assumption" in html_lender


def test_an_unlisted_scenario_says_its_status_is_not_recorded(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    base = ROOT / "scenarios" / "dutchbay_basecase_2025Q4.yaml"
    out = _emit(wind_result, base, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert STATUS_LABELS["not_recorded"] in html


def test_a_broken_registry_leaves_out_the_figures_it_would_label(
    wind_result: Mapping[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("conf/tariff_legal_status.yaml is invalid")

    monkeypatch.setattr(lre, "build_tariff_status", boom)
    out = _emit(wind_result, WIND, tmp_path)
    listed = {s.section: s.reason for s in out.sections_not_run}
    assert SECTION_TARIFF_STATUS in listed
    assert SECTION_SITE_ANALYSES in listed
    html = out.html_path.read_text(encoding="utf-8")
    assert "Tariff Basis and Legal Status" not in html
    assert "Wind battery options" not in html


def test_labelling_touches_only_storage_options_and_labels_an_unrecorded_basis() -> (
    None
):
    scenario = dict(load_scenario_config(str(WIND)))
    status = resolve_scenario_status(scenario, WIND.stem)
    other = SiteAnalysisSection(
        key="equipment_cost_parity",
        title="Equipment cost parity",
        status=STATUS_COMPLETED,
        figures=[(REVENUE_BASIS_FIGURE, "whole_wind_peak_rate")],
    )
    unknown_basis = SiteAnalysisSection(
        key=STORAGE_OPTIONS_KEY,
        title="Wind battery options",
        status=STATUS_COMPLETED,
        figures=[(REVENUE_BASIS_FIGURE, "not_a_recorded_basis")],
        tables=[SiteAnalysisTable(caption="c", columns=["a"], rows=[["1"]])],
    )
    block = SiteAnalysesBlock(intro="i", sections=[other, unknown_basis])
    labelled = label_site_analyses(block, status)
    assert labelled is not None
    assert labelled.sections[0] == other
    unrecorded = STATUS_LABELS["not_recorded"]
    assert dict(labelled.sections[1].figures)[REVENUE_BASIS_FIGURE] == (
        f"not_a_recorded_basis [{unrecorded}]"
    )
    assert labelled.sections[1].tables[0].caption == f"c [{unrecorded}]"


def test_the_section_prints_conditions_open_questions_and_window_flags_once(
    wind_result: Mapping[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = lre.build_tariff_status

    def signed_early(scenario: Mapping[str, Any], name: str, *a: Any, **k: Any) -> Any:
        ppa = {**(scenario.get("ppa") or {}), "signing_date": "2026-05-01"}
        return real({**scenario, "ppa": ppa}, name, *a, **k)

    monkeypatch.setattr(lre, "build_tariff_status", signed_early)
    out = _emit(wind_result, WIND, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    start = html.index("<h2>Tariff Basis and Legal Status</h2>")
    section = html[start : html.index("</section>", start)]
    assert "<strong>Outside the effective window.</strong>" in section
    assert (
        "pucsl_fit_2026_wind: the assumed SPPA signing date 2026-05-01 is before the "
        "rate takes effect (2026-08-25)." in section
    )
    assert "SPPA signing 2026-05-01" in section
    assert (
        "<strong>Condition (pucsl_fit_2026_wind):</strong> Applies only to an SPPA "
        "signed on or after 25 August 2026 (Decision Annex 3 s.7(d))" in section
    )
    assert section.count("<strong>Open question (pucsl_fit_2026_wind):</strong>") == 1
    # Three storage bases share one rate: its notes print once, not once per basis.
    analogy = "wind_bess_on_solar_bess_formula"
    assert section.count(f"<strong>Condition ({analogy}):</strong>") == 1
    assert section.count(f"<strong>Open question ({analogy}):</strong>") == 1


def test_the_section_has_no_window_flag_block_when_the_dates_are_inside(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    out = _emit(wind_result, WIND, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert "Outside the effective window." not in html
