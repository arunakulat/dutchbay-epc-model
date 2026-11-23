"""The lender report discloses the recomputed P90 cover of the committed debt (#1895).

Owner ruling on #1895 (option A): keep the P50 sizing and disclose the recomputed P90
cover. The debt table prints the recomputed P90 case's minimum and average DSCR and LLCR
beside the P90/P50 ratio method. When a scenario declares the opt-in cover term, the table
also says whether it bound and the sizing target it set. A scenario with no P50/P90 pair,
and a builder that fails, are listed under "Sections not run".
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Mapping

import pytest

from analytics.finance.p90_cover import P90_COVER_KEY, priced_config
from analytics.finance.p90_recomputed_downside import recomputed_p90_downside
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from app.reports import lender_report_emit as lre
from app.reports.dbpl import DbplDependencyError
from app.reports.lender_report_emit import emit_lender_report_from_pipeline
from app.reports.recomputed_p90_section import (
    SECTION_RECOMPUTED_P90,
    RecomputedP90Block,
    build_recomputed_p90_block,
)
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    compute_report_sensitivity,
)

ROOT = Path(__file__).resolve().parents[2]
LENDER = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
GENERATED_AT = "2026-11-22T00:00:00+00:00"
ROW = "Recomputed P90 minimum / average DSCR (committed debt)"
TERM_ROW = "P90 cover term (Financing_Terms.p90_cover_min_dscr)"


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
def lender() -> Dict[str, Any]:
    return dict(load_scenario_config(str(LENDER)))


@pytest.fixture(scope="module")
def lender_result(lender: Dict[str, Any]) -> Mapping[str, Any]:
    return run_v14_pipeline(config=copy.deepcopy(lender))


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


def test_the_block_is_the_recomputed_case_on_the_committed_debt(
    lender: Dict[str, Any], lender_result: Mapping[str, Any]
) -> None:
    block = build_recomputed_p90_block(lender, lender_result)
    assert isinstance(block, RecomputedP90Block)
    oracle = recomputed_p90_downside(copy.deepcopy(lender))
    assert block.min_dscr == pytest.approx(oracle["cases"]["recomputed"]["min_dscr"])
    assert block.llcr == pytest.approx(oracle["cases"]["recomputed"]["llcr"])
    assert block.ratio_method_min_dscr == pytest.approx(
        oracle["cases"]["ratio_method"]["min_dscr"]
    )
    # The lender case's committed debt is covered about 1.06x at P90 on main (15.33.0),
    # below the 1.30x P50 target.
    assert 1.0 < block.min_dscr < 1.30


def test_the_lender_report_prints_the_recomputed_cover(
    lender_result: Mapping[str, Any], tmp_path: Path
) -> None:
    block = build_recomputed_p90_block(
        dict(load_scenario_config(str(LENDER))), lender_result
    )
    assert isinstance(block, RecomputedP90Block)
    out = _emit(lender_result, LENDER, tmp_path)
    html = out.html_path.read_text(encoding="utf-8")
    assert ROW in html
    assert f"{block.min_dscr:.2f}x / {block.avg_dscr:.2f}x" in html
    assert "Not a lender P90 claim" in html
    assert TERM_ROW not in html  # the lender case declares no cover term
    assert SECTION_RECOMPUTED_P90 not in [s.section for s in out.sections_not_run]


def test_a_scenario_with_no_pair_lists_the_rows_as_not_run(
    lender_result: Mapping[str, Any], tmp_path: Path
) -> None:
    def unavailable(_scenario: Mapping[str, Any], _result: Mapping[str, Any]) -> str:
        return "not run: no expected_results net_aep_p50_gwh / net_aep_p90_gwh pair"

    out = _emit(lender_result, LENDER, tmp_path, recomputed_p90_builder=unavailable)
    listed = {s.section: s.reason for s in out.sections_not_run}
    assert listed[SECTION_RECOMPUTED_P90].startswith("not run: no expected_results")
    assert ROW not in out.html_path.read_text(encoding="utf-8")


def test_a_builder_that_fails_is_listed_and_does_not_sink_the_report(
    lender_result: Mapping[str, Any], tmp_path: Path
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("P90 case refused")

    out = _emit(lender_result, LENDER, tmp_path, recomputed_p90_builder=boom)
    listed = {s.section: s.reason for s in out.sections_not_run}
    assert listed[SECTION_RECOMPUTED_P90] == (
        "not run: could not be built (RuntimeError: P90 case refused)"
    )
    assert out.html_path.exists()


def test_an_unavailable_case_is_a_reason_not_a_block(lender: Dict[str, Any]) -> None:
    def unavailable(_config: Mapping[str, Any]) -> Dict[str, Any]:
        return {"status": "unavailable", "reason": "no debt service"}

    built = build_recomputed_p90_block(
        lender, {"debt_result": {}}, recompute=unavailable
    )
    assert built == "not run: no debt service"


def test_a_bound_cover_is_measured_on_the_debt_priced_at_the_raised_target(
    lender: Dict[str, Any],
) -> None:
    seen: List[Mapping[str, Any]] = []

    def record(config: Mapping[str, Any]) -> Dict[str, Any]:
        seen.append(copy.deepcopy(dict(config)))
        return {"status": "unavailable", "reason": "recorded"}

    declared = copy.deepcopy(lender)
    declared["Financing_Terms"][P90_COVER_KEY] = 1.1
    bound = {"binding": True, "target_dscr": 1.3431, "declared_target_dscr": 1.3}
    build_recomputed_p90_block(declared, {"debt_result": {"p90_cover": bound}}, record)
    met = {"binding": False, "target_dscr": 1.3, "declared_target_dscr": 1.3}
    build_recomputed_p90_block(declared, {"debt_result": {"p90_cover": met}}, record)
    assert seen[0]["Financing_Terms"]["target_dscr"] == 1.3431
    assert (
        seen[1]["Financing_Terms"]["target_dscr"]
        == lender["Financing_Terms"]["target_dscr"]
    )
    for config in seen:
        assert P90_COVER_KEY not in config["Financing_Terms"]
    assert priced_config(declared, None) == lender


def test_a_declared_cover_is_printed_with_whether_it_bound(
    lender: Dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declared = copy.deepcopy(lender)
    declared["Financing_Terms"][P90_COVER_KEY] = 1.1
    result = run_v14_pipeline(config=declared)
    cover = result["debt_result"]["p90_cover"]
    assert cover["binding"] is True

    def quick(_scenario: Mapping[str, Any], _result: Mapping[str, Any]) -> str:
        return "not run: skipped in this test"

    out = _emit(result, LENDER, tmp_path, recomputed_p90_builder=quick)
    html = out.html_path.read_text(encoding="utf-8")
    assert TERM_ROW in html
    assert (
        f"1.10x: binds; P50 sizing target raised from 1.30x to "
        f"{cover['target_dscr']:.2f}x" in html
    )
