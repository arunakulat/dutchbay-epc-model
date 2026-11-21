"""The command-line lender report carries the site-analysis sections (#1824, after #1752)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from app.reports import lender_report_emit as lre
from app.reports.dbpl import DbplDependencyError
from app.reports.lender_report_emit import (
    SECTION_CAPITAL_RISK,
    SECTION_SITE_ANALYSES,
    emit_lender_report_from_pipeline,
)
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    compute_report_sensitivity,
)

ROOT = Path(__file__).resolve().parents[2]
WIND = Path("scenarios/blue_whale_wind_lot5b_2026.yaml")
HYBRID = Path("scenarios/blue_whale_hybrid_lot5b_2026.yaml")
GENERATED_AT = "2026-11-21T00:00:00+00:00"


def _empty_bundle(
    scenario: Mapping[str, Any], *, profile: Any
) -> ReportSensitivityBundle:
    """A sensitivity bundle with every method empty (no live sweep)."""
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
    """Skip the PDF print; these tests are about the HTML sections."""

    def _no_print(*_args: Any, **_kwargs: Any) -> Any:
        raise DbplDependencyError("PDF print not exercised by this test")

    monkeypatch.setattr(lre, "_render_pdf", _no_print)


@pytest.fixture(scope="module")
def wind_result() -> Mapping[str, Any]:
    return run_v14_pipeline(config=dict(load_scenario_config(str(ROOT / WIND))))


def _emit(result: Mapping[str, Any], scenario: Path, out: Path, **kwargs: Any) -> Any:
    return emit_lender_report_from_pipeline(
        result,
        scenario,
        out / "lender_report.html",
        capital_risk_not_run="not run: switched off for this test",
        generated_at=GENERATED_AT,
        require_pdf=False,
        sensitivity_computer=_empty_bundle,
        capital_risk_builder=_not_called,
        **kwargs,
    )


def test_the_lender_report_renders_the_scenarios_site_analyses(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    out = _emit(wind_result, ROOT / WIND, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert "Site Analyses (Screening)" in html
    for title in (
        "Wind resource transfer (met-mast screening)",
        "Wind battery options",
        "Equipment cost parity",
        "Not applicable to this scenario",
    ):
        assert title in html, title
    assert "Contiguous-location limit." in html
    assert SECTION_SITE_ANALYSES not in [s.section for s in out.sections_not_run]


def test_the_relative_scenario_path_finds_the_same_summaries(
    wind_result: Mapping[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    out = _emit(wind_result, WIND, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert "docs/site_analyses/blue_whale_wind_lot5b_2026/storage_options.json" in html


def test_a_builder_that_cannot_run_is_listed_with_the_sections_not_run(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("conf/site_analysis_sections.yaml is malformed")

    out = _emit(wind_result, ROOT / WIND, tmp_path, site_analyses_builder=boom)
    listed = {s.section: s.reason for s in out.sections_not_run}
    assert listed[SECTION_SITE_ANALYSES] == (
        "not run: the site-analysis sections could not be built "
        "(ValueError: conf/site_analysis_sections.yaml is malformed)"
    )
    assert SECTION_CAPITAL_RISK in listed
    html = out.html_path.read_text(encoding="utf-8")
    assert "Site Analyses (Screening)" not in html
    assert f"<strong>{SECTION_SITE_ANALYSES}</strong>" in html
    assert [r["section"] for r in out.as_dict()["sections_not_run"]] == list(listed)


def test_a_scenario_without_site_analyses_gets_no_block_and_no_entry(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    out = _emit(wind_result, ROOT / HYBRID, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert "site-analyses" not in html
    assert SECTION_SITE_ANALYSES not in [s.section for s in out.sections_not_run]


def test_the_builder_receives_the_effective_scenario(
    wind_result: Mapping[str, Any], tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    def record(scenario: Mapping[str, Any], scenario_path: Path) -> None:
        seen["scenario"] = dict(scenario)
        seen["path"] = scenario_path
        return None

    _emit(wind_result, ROOT / WIND, tmp_path, site_analyses_builder=record)
    assert seen["path"] == ROOT / WIND
    assert seen["scenario"] == dict(load_scenario_config(str(ROOT / WIND)))
