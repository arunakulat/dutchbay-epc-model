"""The command-line lender report: API section parity, sections not run, DBPL PDF (#1752)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping

import pytest
import yaml
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from analytics.executive_workbook import EXECUTIVE_WORKBOOK_F5_CAVEAT
from app.models.inputs import WindFarmInputs
from app.reports import lender_report_emit as lre
from app.reports.capital_risk_emit import build_capital_risk_report_for_scenario
from app.reports.dbpl import DbplDependencyError
from app.reports.lender_report_emit import (
    DOCUMENT_STATUS,
    SECTION_CAPITAL_RISK,
    SECTION_MORRIS,
    SECTION_PAWN,
    SECTION_TORNADO,
    DbplFurniture,
    dbpl_furniture_for,
    emit_lender_report_from_pipeline,
    to_dbpl_print_html,
)
from app.reports.renderer import render_report_html
from app.reports.report_model import technology_subtitle
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
)
from app.services.report_global_sa import GlobalSABlock, GlobalSADriver
from app.services.report_tornado import TornadoBlock, TornadoRow

GENERATED_AT = "2026-11-21T00:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
_H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)


def _inputs() -> WindFarmInputs:
    return WindFarmInputs(
        site_name="Report seam",
        capacity_mw=148.9,  # 14 x 10.638 MW, reconciles with the frozen AEP (tests/app/test_api.py)
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )


def _tornado() -> TornadoBlock:
    return TornadoBlock(
        metric="project_irr",
        rows=[
            TornadoRow(label=f"driver-{i}", impact_abs=0.01 * (i + 1)) for i in range(7)
        ],
    )


def _global_sa(method: str, n_runs: int) -> GlobalSABlock:
    return GlobalSABlock(
        method=method,
        metric="project_irr",
        n_runs=n_runs,
        drivers=[GlobalSADriver(name="capex", mu_star=0.02, median_ks=0.3)],
    )


def _bundle(
    scenario: Mapping[str, Any], *, empty: bool = False
) -> ReportSensitivityBundle:
    """A typed sensitivity bundle from injected computers (no live sweep)."""
    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None if empty else _tornado(),
        morris_computer=lambda _s, *, n_trajectories: (
            None if empty else _global_sa("morris", 28)
        ),
        pawn_computer=lambda _s, *, n, s: None if empty else _global_sa("pawn", 128),
    )


def _h2s(html: str) -> List[str]:
    return [re.sub(r"\s+", " ", h).strip() for h in _H2.findall(html)]


@pytest.fixture(scope="module")
def api_case() -> Any:
    """The API route's own finance seam on a wizard submission (one finance run)."""
    return run_report_case(_inputs(), generated_at=GENERATED_AT)


@pytest.fixture()
def scenario_file(api_case: Any, tmp_path: Path) -> Path:
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(dict(api_case.scenario_config)), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _html_only(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the slow PDF print except in the tests that are about it."""
    if "pdf" in request.node.name or "print_stack" in request.node.name:
        return

    def _no_print(*_args: Any, **_kwargs: Any) -> Any:
        raise DbplDependencyError("PDF print not exercised by this test")

    monkeypatch.setattr(lre, "_render_pdf", _no_print)


def _not_called(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("the capital-risk Monte Carlo must not run here")


# ── parity with POST /v1/cases/report.pdf ─────────────────────────────────────


def test_cli_report_has_the_api_report_sections(
    api_case: Any, scenario_file: Path, tmp_path: Path
) -> None:
    bundle = _bundle(api_case.scenario_config)
    api_html = render_report_html(build_report_context_from_case(api_case, bundle))

    out = emit_lender_report_from_pipeline(
        api_case.run_result,
        scenario_file,
        tmp_path / "out" / "lender_report.html",
        capital_risk_not_run="not run: switched off for this test",
        generated_at=GENERATED_AT,
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: bundle,
        capital_risk_builder=_not_called,
    )
    cli_html = out.html_path.read_text(encoding="utf-8")

    assert _h2s(cli_html) == _h2s(api_html)
    for section in ("Sensitivity Tornado", "Morris Screening", "PAWN"):
        assert any(section in h for h in _h2s(cli_html)), section
    assert [s.section for s in out.sections_not_run] == [SECTION_CAPITAL_RISK]


def test_the_cli_report_runs_the_production_profile(
    api_case: Any, scenario_file: Path, tmp_path: Path
) -> None:
    seen: Dict[str, Any] = {}

    def _record(
        scenario: Mapping[str, Any], *, profile: Any
    ) -> ReportSensitivityBundle:
        seen["profile"] = profile.name
        return _bundle(scenario)

    emit_lender_report_from_pipeline(
        api_case.run_result,
        scenario_file,
        tmp_path / "lender_report.html",
        capital_risk_not_run="not run: test",
        require_pdf=False,
        sensitivity_computer=_record,
    )
    assert seen["profile"] == "production_full"


def test_the_api_report_is_unchanged_without_a_not_run_list(api_case: Any) -> None:
    html = render_report_html(
        build_report_context_from_case(api_case, _bundle(api_case.scenario_config))
    )
    assert "Sections not run" not in html
    assert "sections-not-run" not in html


# ── sections not run ──────────────────────────────────────────────────────────


def test_every_section_left_out_is_listed_with_its_reason(
    api_case: Any, tmp_path: Path
) -> None:
    scenario = {
        k: v for k, v in dict(api_case.scenario_config).items() if k != "monte_carlo"
    }
    no_mc = tmp_path / "no_mc.yaml"
    no_mc.write_text(yaml.safe_dump(scenario), encoding="utf-8")
    out = emit_lender_report_from_pipeline(
        api_case.run_result,
        no_mc,
        tmp_path / "lender_report.html",
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario, empty=True),
        capital_risk_builder=_not_called,
    )
    listed = {s.section: s.reason for s in out.sections_not_run}
    assert list(listed) == [
        SECTION_TORNADO,
        SECTION_MORRIS,
        SECTION_PAWN,
        SECTION_CAPITAL_RISK,
    ]
    assert "outcome: degraded" in listed[SECTION_TORNADO]
    # The scenario declares no Monte Carlo block, so neither screening nor the
    # capital-risk Monte Carlo has anything to sample (and the builder is never called).
    assert "monte_carlo.parameters" in listed[SECTION_MORRIS]
    assert "monte_carlo.parameters" in listed[SECTION_CAPITAL_RISK]
    html = out.html_path.read_text(encoding="utf-8")
    block = html.split("<h3>Sections not run</h3>", 1)[1].split("</ul>", 1)[0]
    for section in listed:
        assert f"<strong>{section}</strong>" in block
    assert "Sensitivity Tornado" not in "".join(_h2s(html))
    record = json.loads(json.dumps(out.as_dict()))
    assert [r["section"] for r in record["sections_not_run"]] == list(listed)


def test_the_report_carries_the_f5_notice(
    api_case: Any, scenario_file: Path, tmp_path: Path
) -> None:
    out = emit_lender_report_from_pipeline(
        api_case.run_result,
        scenario_file,
        tmp_path / "lender_report.html",
        capital_risk_not_run="not run: test",
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
    )
    html = out.html_path.read_text(encoding="utf-8")
    assert "F-5 non-reliance notice:" in html
    assert "no quarterly CFADS or intra-year" in html


# ── the capital-risk section and the lender guards ────────────────────────────


@pytest.fixture(scope="module")
def lender_run() -> Dict[str, Any]:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    result: Dict[str, Any] = run_v14_pipeline(
        config=str(_LENDER_CFG), validation_mode="strict"
    )
    return result


def test_the_report_runs_the_guarded_monte_carlo_when_none_is_shared(
    lender_run: Dict[str, Any], tmp_path: Path
) -> None:
    calls: Dict[str, Any] = {}

    def _builder(path: Any, out_dir: Path, **kwargs: Any) -> Any:
        calls.update(kwargs)
        # A deliberately sub-lender-grade smoke: the CLI path never lowers the floor.
        return build_capital_risk_report_for_scenario(
            path,
            out_dir,
            n_trials=40,
            min_trials=20,
            seed=kwargs["seed"],
            npv_metric=kwargs["npv_metric"],
        )

    out = emit_lender_report_from_pipeline(
        lender_run,
        _LENDER_CFG,
        tmp_path / "lender_report.html",
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
        capital_risk_builder=_builder,
    )
    assert calls["n_trials"] == 2000  # the capital-risk emitter's lender default
    assert SECTION_CAPITAL_RISK not in {s.section for s in out.sections_not_run}
    html = out.html_path.read_text(encoding="utf-8")
    assert any("Capital Risk" in h for h in _h2s(html))
    assert (tmp_path / lre.LENDER_REPORT_FILES_DIR).is_dir()


def test_a_monte_carlo_that_fails_the_guards_is_listed_not_rendered(
    lender_run: Dict[str, Any], tmp_path: Path
) -> None:
    def _refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("capital-risk report needs >= 1000 trials")

    out = emit_lender_report_from_pipeline(
        lender_run,
        _LENDER_CFG,
        tmp_path / "lender_report.html",
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
        capital_risk_builder=_refuse,
    )
    reason = {s.section: s.reason for s in out.sections_not_run}[SECTION_CAPITAL_RISK]
    assert "could not run under the lender guards" in reason
    assert "1000 trials" in reason
    assert not any(
        "Capital Risk" in h for h in _h2s(out.html_path.read_text(encoding="utf-8"))
    )


def test_a_shared_capital_risk_report_is_used_as_is(
    lender_run: Dict[str, Any], tmp_path: Path
) -> None:
    shared = build_capital_risk_report_for_scenario(
        _LENDER_CFG, tmp_path / "cr", n_trials=40, min_trials=20
    )
    out = emit_lender_report_from_pipeline(
        lender_run,
        _LENDER_CFG,
        tmp_path / "lender_report.html",
        capital_risk=shared,
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
        capital_risk_builder=_not_called,
    )
    assert out.sections_not_run == ()
    html = out.html_path.read_text(encoding="utf-8")
    assert f"{shared.n_trials}" in html
    assert "Sections not run" not in html


# ── the DBPL print ────────────────────────────────────────────────────────────


def _furniture(**overrides: Any) -> DbplFurniture:
    fields: Dict[str, Any] = dict(
        document_id="DBAY-LR-TEST-20261121",
        version="v1",
        issue_date="2026-11-21",
        status="Draft",
        banner="A & B",
        title="Lender report",
        caveat=EXECUTIVE_WORKBOOK_F5_CAVEAT,
        control=(("Document ID", "DBAY-LR-TEST-20261121"),),
        revisions=({"rev": "P01", "date": "2026-11-21", "status": DOCUMENT_STATUS},),
    )
    fields.update(overrides)
    return DbplFurniture(**fields)


_SCREEN_HTML = (
    '<!DOCTYPE html><html lang="en"><head><title>t</title>'
    "<style>body { color: #1c2733; }</style></head><body>"
    '<h1>Title</h1><h2>Section</h2><h3>Sub</h3><table class="heatmap">'
    "<tr><td>x</td></tr></table><h2>Capital Risk</h2>"
    "<table><tr><td>y</td></tr></table></body></html>"
)


def test_dbpl_print_html_drops_the_screen_style_and_adds_house_classes() -> None:
    printed = to_dbpl_print_html(_SCREEN_HTML, _furniture())
    assert "#1c2733" not in printed
    assert ">Title</h1>" not in printed  # the base prints the title, once
    assert '<h1 class="dbpl-title">Lender report</h1>' in printed
    assert '<h2 class="dbpl-section">Section</h2>' in printed
    assert '<h3 class="dbpl-subsection">Sub</h3>' in printed
    assert '<table class="dbpl heatmap">' in printed
    assert '<table class="dbpl">' in printed
    assert '<div class="dbpl-banner">A &amp; B</div>' in printed
    # The running doc-line itself carries the document ID (DBPL-01 furniture), not only the
    # control table further down the page.
    assert (
        '<div class="dbpl-docline">DBAY-LR-TEST-20261121 | v1 | 2026-11-21 | Draft</div>'
        in printed
    )
    assert '<html lang="en">' in printed  # PDF/UA needs lang on <html>


def test_every_section_heading_carries_the_f5_caveat_band() -> None:
    printed = to_dbpl_print_html(_SCREEN_HTML, _furniture())
    body = printed.split('<h2 class="dbpl-section">Section</h2>', 1)[1]
    h2_count = len(re.findall(r"</h2>", body)) + 1
    bands = re.findall(r'</h2>\s*<div class="dbpl-caveat">', printed)
    assert len(bands) >= h2_count == 2
    assert (
        '<h2 class="dbpl-section">Capital Risk</h2>\n<div class="dbpl-caveat">'
        in printed
    )


def test_the_document_control_block_and_provenance_are_printed() -> None:
    printed = to_dbpl_print_html(
        _SCREEN_HTML, _furniture(provenance_lines=("DBPL print core 1", "pdf/ua-1"))
    )
    assert "Document control" in printed
    assert "Revision history" in printed
    assert DOCUMENT_STATUS in printed
    for role in ("Prepared", "Checked", "Reviewed", "Approved"):
        assert role in printed
    provenance = printed.split('<div class="dbpl-provenance">', 1)[1]
    assert "DBPL print core 1" in provenance and "pdf/ua-1" in provenance
    # The report body sits between the control block and the provenance.
    assert printed.index("Document control") < printed.index(">Section</h2>")
    assert printed.index(">Capital Risk</h2>") < printed.index(
        'class="dbpl-provenance"'
    )


def test_the_furniture_names_the_document_and_its_status(api_case: Any) -> None:
    context = build_report_context_from_case(
        api_case, _bundle(api_case.scenario_config)
    )
    furniture = dbpl_furniture_for(context)
    assert furniture.document_id.startswith("DBAY-LR-")
    assert furniture.caveat == EXECUTIVE_WORKBOOK_F5_CAVEAT
    labels = dict(furniture.control)
    assert labels["Document ID"] == furniture.document_id
    assert labels["Status / Reason for issue"] == DOCUMENT_STATUS
    assert [r["status"] for r in furniture.revisions] == [DOCUMENT_STATUS]
    assert furniture.document_id in furniture.table_source
    assert "run_full_pipeline_v14" in furniture.table_source


def test_every_table_carries_a_source_note_naming_its_section() -> None:
    printed = to_dbpl_print_html(
        _SCREEN_HTML, _furniture(table_source="DBAY-LR-TEST-20261121, model output")
    )
    body = printed.split('<h2 class="dbpl-section">Section</h2>', 1)[1]
    ends = [m.end() for m in re.finditer(r"</table>", body)]
    assert len(ends) == 2
    for end in ends:
        assert (
            body[end:]
            .lstrip()
            .startswith(
                '<div class="dbpl-tablenotes"><div class="dbpl-source">'
                '<span class="dbpl-label">Source:</span> DBAY-LR-TEST-20261121, model output'
            )
        )
    assert "model output; section: Sub.</div>" in body
    assert "model output; section: Capital Risk.</div>" in body


def test_numeric_cells_keep_their_right_alignment_in_print() -> None:
    html = _SCREEN_HTML.replace(
        "<td>y</td>", '<th class="num">h</th><td class="num warn">1.0</td>'
    )
    printed = to_dbpl_print_html(html, _furniture())
    assert '<th class="num dbpl-num">h</th>' in printed
    assert '<td class="num warn dbpl-num">1.0</td>' in printed
    assert "<td>x</td>" in printed  # a text cell is left alone


def test_dbpl_print_html_refuses_a_document_without_a_body() -> None:
    with pytest.raises(ValueError, match="no <body>"):
        to_dbpl_print_html("<html></html>", _furniture())


def test_the_pdf_is_printed_through_the_dbpl_core(
    api_case: Any, scenario_file: Path, tmp_path: Path
) -> None:
    out = emit_lender_report_from_pipeline(
        api_case.run_result,
        scenario_file,
        tmp_path / "lender_report.html",
        capital_risk_not_run="not run: test",
        require_pdf=True,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
    )
    assert out.pdf_path == tmp_path / "lender_report.pdf"
    assert out.pdf_path.read_bytes()[:5] == b"%PDF-"
    assert out.pdf_not_written is None
    assert any(line.startswith("DBPL print core") for line in out.pdf_provenance)
    assert any("pdf/ua-1" in line for line in out.pdf_provenance)

    # DBPL-01 furniture, read back from the printed PDF's text.
    from pdfminer.high_level import extract_text

    text = " ".join(extract_text(str(out.pdf_path)).split())
    assert "Document control" in text
    assert "Revision history" in text
    assert "DBAY-LR-" in text
    assert "Status / Reason for issue" in text
    assert "DBPL print core" in text
    assert "pdf/ua-1" in text
    caveat_head = " ".join(EXECUTIVE_WORKBOOK_F5_CAVEAT.split())[:60]
    html_h2 = len(_h2s(out.html_path.read_text(encoding="utf-8")))
    # Headline caveat plus one band under every section heading.
    assert text.count(caveat_head) >= html_h2 + 1
    # DBPL-01: a documentary source under every table (the revision history has its own).
    html_tables = out.html_path.read_text(encoding="utf-8").count("</table>")
    match = re.search(r"DBAY-LR-[A-Z0-9-]+", text)
    assert match is not None
    assert text.count(f"Source: {match.group(0)}, model output") >= html_tables


def _missing_stack(*_args: Any, **_kwargs: Any) -> Any:
    raise DbplDependencyError("not installed: weasyprint")


def test_a_missing_print_stack_fails_loud_when_required(
    api_case: Any, scenario_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lre, "_render_pdf", _missing_stack)
    with pytest.raises(DbplDependencyError):
        emit_lender_report_from_pipeline(
            api_case.run_result,
            scenario_file,
            tmp_path / "lender_report.html",
            capital_risk_not_run="not run: test",
            require_pdf=True,
            sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
        )
    assert (tmp_path / "lender_report.html").is_file()
    assert not (tmp_path / "lender_report.pdf").exists()


def test_a_missing_print_stack_is_recorded_when_not_required(
    api_case: Any, scenario_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lre, "_render_pdf", _missing_stack)
    out = emit_lender_report_from_pipeline(
        api_case.run_result,
        scenario_file,
        tmp_path / "lender_report.html",
        capital_risk_not_run="not run: test",
        require_pdf=False,
        sensitivity_computer=lambda scenario, *, profile: _bundle(scenario),
    )
    assert out.pdf_path is None
    assert out.pdf_not_written is not None
    assert "weasyprint" in out.pdf_not_written
    assert out.as_dict()["pdf_not_written"] == out.pdf_not_written


# ── the CLI wiring ────────────────────────────────────────────────────────────


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Run the CLI with the finance engine and both Monte Carlo emitters stubbed."""
    import app.reports.capital_risk_emit as cr

    calls: Dict[str, Any] = {}
    sentinel = object()

    def _engine(*, config: Any, validation_mode: Any, validation_modules: Any) -> Any:
        return {"status": "success", "kpis": {"project_irr": 0.1}}

    def _capital_risk(result: Any, *args: Any, **kwargs: Any) -> Path:
        kwargs["on_report"](sentinel)
        return Path(str(args[-1]))

    def _lender(result: Any, *args: Any, **kwargs: Any) -> Any:
        calls.update(kwargs)
        return lre.LenderReportOutput(
            html_path=Path(str(args[-1])),
            pdf_path=None,
            pdf_not_written="stub",
            sections_not_run=(),
        )

    monkeypatch.setattr(rfp, "run_v14_pipeline", _engine)
    monkeypatch.setattr(cr, "emit_capital_risk_report_from_pipeline", _capital_risk)
    monkeypatch.setattr(lre, "emit_lender_report_from_pipeline", _lender)
    path = tmp_path / "scenario.yaml"
    if scenario is None:
        scenario = {
            "scenario_name": "t",
            "monte_carlo": {"parameters": [{"name": "capex", "low": 0.9, "high": 1.1}]},
        }
    path.write_text(yaml.safe_dump(dict(scenario)), encoding="utf-8")
    base: Dict[str, Any] = {
        "config": str(path),
        "validation_mode": "off",
        "validation_modules": None,
        "export_dir": str(tmp_path / "run"),
        "write_artifacts": True,
        "wind_assessment_json": None,
        "wind_auto_orchestrate": False,
        "solar_assessment_json": None,
        "emit_executive_workbook": False,
    }
    base.update(overrides)
    rfp.cli.__wrapped__(OmegaConf.create(base))
    calls["sentinel"] = sentinel
    return calls


def test_cli_hands_the_capital_risk_report_to_the_lender_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _run_cli(tmp_path, monkeypatch)
    out = json.loads(capsys.readouterr().out)
    assert calls["capital_risk"] is calls["sentinel"]
    assert calls["capital_risk_not_run"] is None
    assert calls["require_pdf"] is False  # under emit_all a missing stack is recorded
    assert out["emitters"]["emit_lender_report"] == {
        "status": "run",
        "source": "emit_all",
        "pdf_not_written": "stub",  # a PDF left unwritten is noted on the emitter entry
    }
    assert out["lender_report"]["html_path"].endswith("lender_report.html")


def test_cli_reuses_the_capital_risk_not_run_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _run_cli(tmp_path, monkeypatch, scenario={"scenario_name": "t"})
    out = json.loads(capsys.readouterr().out)
    cr_entry = out["emitters"]["emit_capital_risk_report"]
    assert cr_entry["status"] == "not_run"
    assert calls["capital_risk"] is None
    # The lender report does not attempt the Monte Carlo the run declined: it lists why.
    assert calls["capital_risk_not_run"] == f"not run: {cr_entry['reason']}"


def test_cli_switched_on_by_name_requires_the_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _run_cli(tmp_path, monkeypatch, emit_all=False, emit_lender_report=True)
    capsys.readouterr()
    assert calls["require_pdf"] is True
    assert calls["capital_risk"] is None  # the capital-risk emitter did not run


# ── a technology-neutral subtitle (A-4) ───────────────────────────────────────


@pytest.mark.parametrize(
    "scenario, expected",
    [
        (None, "Wind"),
        ({"wind_resource": {"weibull_a": 8.0}}, "Wind"),
        # #1844 domain D2: no technologies block is the engine's wind path.
        ({}, "Wind"),
        ({"project": {"technology": "wind"}}, "Wind"),
        ({"project": {"technology": "solar"}}, "Solar"),
        (
            {"generation": {"technologies": {"solar": {"capacity_factor": 0.2}}}},
            "Solar",
        ),
        (
            {"generation": {"technologies": {"bess_unit": {"type": "bess"}}}},
            "Battery Storage",
        ),
        (
            {
                "generation": {
                    "technologies": {
                        "wind": {"type": "wind"},
                        "battery": {"type": "bess"},
                        "wind_b": {"type": "wind"},
                    }
                }
            },
            "Wind + Battery Storage",
        ),
        ({"generation": {"technologies": {"run_of_river": {}}}}, "Run Of River"),
    ],
)
def test_the_subtitle_follows_the_scenario_technology(
    scenario: Any, expected: str
) -> None:
    subtitle = "Utility-Scale {technology} — Project-Finance Summary"
    assert technology_subtitle(subtitle, scenario) == (
        f"Utility-Scale {expected} — Project-Finance Summary"
    )
    assert technology_subtitle("Fixed subtitle", scenario) == "Fixed subtitle"


def test_the_wind_reports_keep_their_subtitle(api_case: Any) -> None:
    html = render_report_html(
        build_report_context_from_case(api_case, _bundle(api_case.scenario_config))
    )
    assert "Utility-Scale Wind — Project-Finance Summary" in html
    assert "{technology}" not in html


@pytest.mark.parametrize(
    "scenario_file",
    ["dutchbay_basecase_2025Q4.yaml", "dutchbay_lendercase_2025Q4.yaml"],
)
def test_the_dutchbay_wind_cases_read_wind(scenario_file: str) -> None:
    """#1844 domain D2: a committed wind case without a technologies block reads "Wind"."""
    import yaml

    path = Path(__file__).resolve().parents[2] / "scenarios" / scenario_file
    scenario = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert technology_subtitle("{technology}", scenario) == "Wind"
