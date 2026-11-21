"""Report sections for the site analyses (#1824)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

import app.reports.site_analysis_sections as sas
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

ROOT = Path(__file__).resolve().parents[2]
WIND = Path("scenarios/blue_whale_wind_lot5b_2026.yaml")
BASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")
HYBRID = Path("scenarios/blue_whale_hybrid_lot5b_2026.yaml")
GENERATED_AT = "2026-06-22T12:00:00+00:00"


def _scenario(rel: Path) -> Dict[str, Any]:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def _statuses(block: sas.SiteAnalysesBlock) -> Dict[str, str]:
    return {s.key: s.status for s in block.sections}


def _by_key(block: sas.SiteAnalysesBlock, key: str) -> sas.SiteAnalysisSection:
    return next(s for s in block.sections if s.key == key)


def test_a_scenario_without_site_analysis_blocks_gets_no_sections() -> None:
    assert sas.build_site_analyses_block(_scenario(HYBRID), HYBRID) is None


def test_every_section_is_listed_with_its_status() -> None:
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    assert block is not None
    assert [s.key for s in block.sections] == list(sas.SECTION_KEYS)
    assert _statuses(block) == {
        "wind_resource_transfer": "completed",
        "storage_options": "completed",
        "solar_storage_sizing": "not_applicable",
        "financing_screening": "not_applicable",
        "equipment_cost_parity": "completed",
    }
    assert [s.key for s in block.not_applicable] == [
        "solar_storage_sizing",
        "financing_screening",
    ]
    for s in block.not_applicable:
        assert s.reason and s.labels == [] and s.figures == []


def test_screening_labels_are_carried() -> None:
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    assert block is not None
    transfer = _by_key(block, "wind_resource_transfer")
    options = _by_key(block, "storage_options")
    assert any(label.startswith("No lender P90.") for label in transfer.labels)
    assert any(label.startswith("No lender P90.") for label in options.labels)
    assert any(label.startswith("Tariff working assumption.") for label in options.labels)
    assert any(
        label.startswith("Contiguous-location limit.") and "10 MW" in label
        for label in options.labels
    )
    # The P90 the transfer summary carries is never shown as a figure.
    assert not any("P90" in name for name, _ in transfer.figures)
    # Each section keeps its analysis's own hold text.
    assert options.hold and options.hold.startswith("SCREENING ONLY")
    assert transfer.hold and transfer.hold.startswith("HOLD: not lender-grade")


def test_the_committed_summary_is_shown_with_its_provenance() -> None:
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    assert block is not None
    options = _by_key(block, "storage_options")
    assert options.source == (
        "docs/site_analyses/blue_whale_wind_lot5b_2026/storage_options.json"
    )
    assert options.provenance and options.provenance.startswith("committed summary;")
    parity = _by_key(block, "equipment_cost_parity")
    assert parity.provenance and parity.provenance.startswith("run live in this report;")
    names = [name for name, _ in options.figures]
    assert "Wind only: project IRR" in names
    (table,) = options.tables
    assert table.rows and all(len(r) == len(table.columns) for r in table.rows)


def test_a_stale_summary_shows_its_figures_under_the_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = sas.load_summary

    def changed(path: Path) -> Any:
        data = real(path)
        assert data is not None
        data = copy.deepcopy(data)
        rel = sorted(data["provenance"]["code"]["files"])[0]
        data["provenance"]["code"]["files"][rel] = "0" * 64
        return data

    monkeypatch.setattr(sas, "load_summary", changed)
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    assert block is not None
    options = _by_key(block, "storage_options")
    assert options.status == "stale"
    assert options.stale_reasons == [
        "code file changed since the summary: analytics/wind/wind_bess_options.py"
    ]
    assert options.figures and options.labels
    html = render_report_html(
        build_report_context(
            CaseResult(status="success", scenario_variant="x", kpis={}),
            generated_at=GENERATED_AT,
            site_analyses=block,
        )
    )
    assert "Stale summary." in html
    assert "analytics/wind/wind_bess_options.py" in html


def test_a_missing_summary_is_not_run_with_the_command_to_write_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sas, "summary_path", lambda path, block, root: tmp_path / f"{block}.json"
    )
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    assert block is not None
    options = _by_key(block, "storage_options")
    assert options.status == "not_run"
    assert options.reason and (
        "scripts/run_site_analysis_v14.py analysis=storage_options "
        f"scenario={WIND.as_posix()} write=true"
    ) in options.reason
    assert options.labels == [] and options.figures == []


def test_a_failed_analysis_is_listed_and_the_others_still_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(sas, "run_site_analysis", boom)
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    assert block is not None
    parity = _by_key(block, "equipment_cost_parity")
    assert parity.status == "failed"
    assert parity.reason == "RuntimeError: boom"
    assert _by_key(block, "storage_options").status == "completed"
    assert _by_key(block, "wind_resource_transfer").status == "completed"
    html = render_report_html(
        build_report_context(
            CaseResult(status="success", scenario_variant="x", kpis={}),
            generated_at=GENERATED_AT,
            site_analyses=block,
        )
    )
    assert "<strong>Failed:</strong> RuntimeError: boom" in html


def test_a_transfer_summary_without_a_yield_fails_its_section() -> None:
    with pytest.raises(ValueError, match="yield.net_aep_gwh"):
        sas._figures_wind_resource_transfer({"hold": "x"})


def test_live_analyses_run_on_the_effective_scenario() -> None:
    scenario = _scenario(BASE)
    block = sas.build_site_analyses_block(scenario, BASE)
    assert block is not None
    assert _by_key(block, "financing_screening").status == "completed"
    changed = copy.deepcopy(scenario)
    changed["capex"]["usd_total"] = float(changed["capex"]["usd_total"]) * 1.5
    moved = sas.build_site_analyses_block(changed, BASE)
    assert moved is not None
    assert (
        _by_key(block, "financing_screening").tables
        != _by_key(moved, "financing_screening").tables
    )


def test_the_sections_render_in_the_report() -> None:
    block = sas.build_site_analyses_block(_scenario(WIND), WIND)
    html = render_report_html(
        build_report_context(
            CaseResult(status="success", scenario_variant="x", kpis={}),
            generated_at=GENERATED_AT,
            site_analyses=block,
        )
    )
    assert "Site Analyses (Screening)" in html
    for title in (
        "Wind resource transfer (met-mast screening)",
        "Wind battery options",
        "Equipment cost parity",
        "Not applicable to this scenario",
    ):
        assert title in html
    assert "Contiguous-location limit." in html
    assert "Tariff working assumption." in html


def test_a_report_without_sections_omits_them() -> None:
    ctx = build_report_context(
        CaseResult(status="success", scenario_variant="x", kpis={}),
        generated_at=GENERATED_AT,
    )
    assert ctx.site_analyses is None
    assert "site-analyses" not in render_report_html(ctx)


def test_the_sections_config_is_checked(tmp_path: Path) -> None:
    raw = yaml.safe_load((ROOT / sas.SECTIONS_CONFIG).read_text(encoding="utf-8"))
    assert sas.load_sections_config(ROOT)["schema_version"] == sas.SECTIONS_SCHEMA

    def write(data: Any) -> Path:
        (tmp_path / "conf").mkdir(exist_ok=True)
        (tmp_path / sas.SECTIONS_CONFIG).write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )
        return tmp_path

    bad = copy.deepcopy(raw)
    bad["schema_version"] = "other"
    with pytest.raises(ValueError, match="must declare"):
        sas.load_sections_config(write(bad))
    bad = copy.deepcopy(raw)
    del bad["sections"]["storage_options"]
    with pytest.raises(ValueError, match="must hold exactly"):
        sas.load_sections_config(write(bad))
    bad = copy.deepcopy(raw)
    bad["sections"]["storage_options"]["labels"] = [1]
    with pytest.raises(ValueError, match="labels must be text"):
        sas.load_sections_config(write(bad))


def test_section_text_is_escaped() -> None:
    section = sas.SiteAnalysisSection(
        key="storage_options",
        title="Wind battery options",
        status="completed",
        hold="<script>x</script>",
    )
    html = render_report_html(
        build_report_context(
            CaseResult(status="success", scenario_variant="x", kpis={}),
            generated_at=GENERATED_AT,
            site_analyses=sas.SiteAnalysesBlock(intro="i", sections=[section]),
        )
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
