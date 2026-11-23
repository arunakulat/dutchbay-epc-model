"""Cross-surface consumer matrix, units, section disposition, and reliance tests (#1815 Slice 2b).

Binds a single real pipeline run across:
* ``api_pipeline`` (``api.pipeline_api.run_pipeline``);
* ``api_surface`` (``app.api.surface.CaseSurface``);
* ``report_html`` / ``dbpl_html`` (``app.reports.renderer`` + ``lender_report_emit.to_dbpl_print_html``);
* ``executive_workbook`` (``analytics.executive_workbook``); and
* ``dfi_workbook`` (``analytics.dfi_workbook.foundation``).

Exercises both positive parity (run identity, explicit unit contracts, section dispositions,
and F-5 / synthetic-grid / allocated-vs-covenant reliance labels) and hostile mismatch controls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import openpyxl
import pytest

import api.pipeline_api as papi
from analytics.contracts_v14 import (
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
)
from analytics.dfi_workbook.foundation import (
    CONTROL_SHEET_NAME,
    DFI_WORKBOOK_F5_CAVEAT,
    DfiWorkbookMetadata,
    WorkbookInputItem,
    build_dfi_workbook_foundation,
)
from analytics.executive_workbook import (
    EXECUTIVE_WORKBOOK_F5_CAVEAT,
    emit_executive_workbook_from_pipeline,
    read_workbook_run_manifest,
    read_workbook_unit_formats,
)
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_identity import (
    F5_NON_RELIANCE_NOTICE,
    RUN_IDENTITY_FIELDS,
    UNIT_EXCEL_NUMBER_FORMATS,
    check_no_hold_withdrawal,
    metric_unit,
    require_consistent_section_dispositions,
    require_reliance_labels,
    require_unit_contracts_aligned,
    validate_display_matches_unit,
    verify_consumer_matrix,
)
from analytics.scenario_loader import load_scenario_config
from app.api.responses import CaseResult
from app.api.surface import CaseSurface
from app.reports.grid_screening_emit import MANDATORY_SCREENING_CAVEAT
from app.reports.lender_report_emit import dbpl_furniture_for, to_dbpl_print_html
from app.reports.module_ledger import (
    ModuleExecutionRecord,
    ModuleExecutionStatus,
    build_module_execution_ledger,
    load_module_role_registry,
)
from app.reports.renderer import render_report_html
from app.reports.report_model import SectionNotRun, build_report_context

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = "scenarios/dutchbay_lendercase_2025Q4.yaml"
HYBRID_SCENARIO = "scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml"

_FORMAT_TO_UNIT = {fmt: unit for unit, fmt in UNIT_EXCEL_NUMBER_FORMATS.items()}


@pytest.fixture(scope="module")
def lender_run() -> Dict[str, Any]:
    return run_v14_pipeline(str(REPO_ROOT / LENDER_SCENARIO))


@pytest.fixture(scope="module")
def lender_surfaces(
    lender_run: Dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> Dict[str, Any]:
    patch = pytest.MonkeyPatch()
    patch.setattr(papi, "run_v14_pipeline", lambda **_kwargs: lender_run)
    try:
        api_pipeline = papi.run_pipeline(
            papi.RunPipelineRequest(config_path=LENDER_SCENARIO)
        )
    finally:
        patch.undo()

    report_ctx = build_report_context(
        CaseResult.from_pipeline_result(dict(lender_run), scenario_variant="lender"),
        generated_at=lender_run["run_manifest"]["generated_at"],
        debt_result=lender_run.get("debt_result"),
        annual_rows=lender_run.get("annual_rows"),
        run_result=dict(lender_run),
    ).model_copy(
        update={
            "f5_notice": F5_NON_RELIANCE_NOTICE,
            "sections_not_run": [
                SectionNotRun(
                    section="Capital risk: Monte Carlo distribution",
                    reason="not run on synchronous matrix profile",
                )
            ],
        }
    )
    api_surface = CaseSurface.from_report_context(report_ctx)
    report_html = render_report_html(report_ctx)
    dbpl_html = to_dbpl_print_html(report_html, dbpl_furniture_for(report_ctx))

    wb_dir = tmp_path_factory.mktemp("matrix_wb")
    exec_wb_path = emit_executive_workbook_from_pipeline(
        lender_run, wb_dir / "executive.xlsx"
    )

    registry = load_module_role_registry()
    finance_spec = registry.get("analytics.pipeline_v14_enhanced")
    ledger = build_module_execution_ledger(
        profile="consumer_matrix_lender",
        records=(
            ModuleExecutionRecord(
                module_path=finance_spec.module_path,
                pipeline_stage=finance_spec.pipeline_stage,
                role_description=finance_spec.role_description,
                status=ModuleExecutionStatus.EXECUTED,
                excel_representation=finance_spec.excel_representation,
                key_outputs=("kpis", "annual_rows", "debt_result"),
                provenance_refs=(lender_run["run_manifest"]["config_sha256"],),
            ),
        ),
        registry=registry,
    )
    dfi_wb_path = wb_dir / "dfi_foundation.xlsx"
    build_dfi_workbook_foundation(
        dfi_wb_path,
        metadata=DfiWorkbookMetadata(
            project_name="DutchBay",
            scenario_name="dutchbay_lendercase_2025Q4",
            run_mode="lender",
            config_sha256=lender_run["run_manifest"]["config_sha256"],
            engine_version=lender_run["run_manifest"]["engine_version"],
            generated_at=lender_run["run_manifest"]["generated_at"],
        ),
        inputs=(
            WorkbookInputItem(
                key="project_irr",
                section="Returns",
                label="Project IRR",
                value=float(format(float(lender_run["kpis"]["project_irr"]), ".15g")),
                unit="pct",
                number_format="0.00%",
                provenance=f"run_manifest:{lender_run['run_manifest']['config_sha256'][:12]}",
            ),
        ),
        execution_records=ledger,
    )

    return {
        "api_pipeline": api_pipeline,
        "api_surface": api_surface,
        "report_ctx": report_ctx,
        "report_html": report_html,
        "dbpl_html": dbpl_html,
        "exec_wb_path": exec_wb_path,
        "dfi_wb_path": dfi_wb_path,
    }


def _workbook_units_for_cards(
    exec_wb_path: Path, card_keys: list[str]
) -> Dict[str, str]:
    formats = read_workbook_unit_formats(exec_wb_path)
    summary_formats = formats["Summary"]
    out: Dict[str, str] = {}
    for key in card_keys:
        # Report KPI table uses `equity_moic` while workbook Summary stores `equity_moic`
        fmt = summary_formats.get(key)
        if fmt is not None and fmt in _FORMAT_TO_UNIT:
            out[key] = _FORMAT_TO_UNIT[fmt]
    return out


def test_full_consumer_matrix_binds_identity_units_dispositions_and_reliance(
    lender_run: Dict[str, Any], lender_surfaces: Dict[str, Any]
) -> None:
    surface: CaseSurface = lender_surfaces["api_surface"]
    report_ctx = lender_surfaces["report_ctx"]
    exec_wb_path: Path = lender_surfaces["exec_wb_path"]
    dfi_wb_path: Path = lender_surfaces["dfi_wb_path"]
    dbpl_html: str = lender_surfaces["dbpl_html"]
    report_html: str = lender_surfaces["report_html"]

    card_keys = [c.key for c in surface.kpi_cards]
    surface_units = {c.key: c.unit for c in surface.kpi_cards}
    report_units = {row.key: metric_unit(row.key) for row in report_ctx.kpi_rows}
    wb_units = _workbook_units_for_cards(exec_wb_path, card_keys)

    for card in surface.kpi_cards:
        validate_display_matches_unit(
            card.key, card.unit, card.value, card.display, surface="api_surface"
        )
    for row in report_ctx.kpi_rows:
        validate_display_matches_unit(
            row.key,
            metric_unit(row.key),
            row.value,
            row.display,
            surface="report_html",
        )

    wb = openpyxl.load_workbook(exec_wb_path, read_only=True, data_only=True)
    try:
        wb_notice = str(wb["Summary"]["A1"].value)
        ratios_rows = dict(wb["Ratios"].iter_rows(min_row=2, values_only=True))
    finally:
        wb.close()

    dfi_wb = openpyxl.load_workbook(dfi_wb_path, read_only=True, data_only=True)
    try:
        dfi_notice = str(dfi_wb[CONTROL_SHEET_NAME]["A1"].value)
        dfi_meta = {
            row[0]: row[1]
            for row in dfi_wb[CONTROL_SHEET_NAME].iter_rows(min_row=4, values_only=True)
            if row and row[0]
        }
    finally:
        dfi_wb.close()

    # DFI Control_Provenance carries the exact same config digest & engine version.
    assert dfi_meta["config_sha256"] == lender_run["run_manifest"]["config_sha256"]
    assert dfi_meta["engine_version"] == lender_run["run_manifest"]["engine_version"]
    assert dfi_notice == DFI_WORKBOOK_F5_CAVEAT == F5_NON_RELIANCE_NOTICE

    # DBPL HTML embeds the exact commit, config digest, F-5 caveat, and sections_not_run.
    assert lender_run["run_manifest"]["config_sha256"] in dbpl_html
    assert lender_run["run_manifest"]["git_sha"][:12] in dbpl_html
    assert F5_NON_RELIANCE_NOTICE in dbpl_html
    assert F5_NON_RELIANCE_NOTICE in report_html
    assert "Capital risk: Monte Carlo distribution" in dbpl_html

    # Ratios sheet explicitly keeps annual folded covenant min_dscr separate from sculpt min_dscr_period.
    assert "min_dscr" in ratios_rows
    assert "min_dscr_period" in ratios_rows

    result = verify_consumer_matrix(
        manifests={
            "api_pipeline": lender_surfaces["api_pipeline"].manifest.model_dump(),
            "api_surface": surface.run_manifest,
            "report_html": report_ctx.manifest,
            "executive_workbook": read_workbook_run_manifest(exec_wb_path),
        },
        units={
            "api_surface": surface_units,
            "report_html": report_units,
            "executive_workbook": wb_units,
        },
        dispositions={
            "api_surface": surface.section_dispositions,
            "report_html": {
                "kpis": "computed" if report_ctx.kpi_rows else "omitted",
                "tornado": "omitted",
                "global_sa_morris": "omitted",
                "global_sa_pawn": "omitted",
                "capital_risk": "not_run",
                "multi_tech": "omitted",
            },
        },
        reliance={
            "api_surface": {
                "reliance_label": surface.reliance_label,
                "notice": surface.reliance_notice,
                "allocated_covenant_distinct": True,
                "covenant_distinction_notice": surface.reliance_notice,
            },
            "dbpl_html": {
                "reliance_label": "lender_reliance_prohibited",
                "notice": report_ctx.f5_notice,
                "allocated_covenant_distinct": True,
                "covenant_distinction_notice": report_ctx.f5_notice,
            },
            "executive_workbook": {
                "reliance_label": "lender_reliance_prohibited",
                "notice": wb_notice,
                "allocated_covenant_distinct": True,
                "covenant_distinction_notice": wb_notice,
            },
            "dfi_workbook": {
                "reliance_label": "lender_reliance_prohibited",
                "notice": dfi_notice,
                "allocated_covenant_distinct": True,
                "covenant_distinction_notice": dfi_notice,
            },
        },
        require_f5=True,
        require_allocated_covenant_distinction=True,
    )
    assert result["run_identity"] == {
        key: lender_run["run_manifest"].get(key) for key in RUN_IDENTITY_FIELDS
    }
    assert result["shared_units"]["project_irr"] == "pct"
    assert result["shared_units"]["project_npv"] == "usd"
    assert result["shared_units"]["min_dscr"] == "multiple"
    assert result["shared_dispositions"]["capital_risk"] == "not_run"


def test_executive_workbook_applies_explicit_unit_number_formats(
    lender_surfaces: Dict[str, Any],
) -> None:
    formats = read_workbook_unit_formats(lender_surfaces["exec_wb_path"])
    assert formats["Summary"]["project_irr"] == "0.00%"
    assert formats["Summary"]["project_npv"] == '$#,##0;-$#,##0;"$0"'
    assert formats["Summary"]["min_dscr"] == '0.00"x"'
    assert formats["Ratios"]["min_dscr"] == '0.00"x"'
    assert formats["Ratios"]["min_dscr_period"] == '0.00"x"'
    assert formats["ScenarioSummary"]["project_irr"] == "0.00%"
    assert formats["ScenarioSummary"]["max_debt_usd"] == '$#,##0;-$#,##0;"$0"'


def test_hybrid_run_marks_multi_tech_section_as_allocated_not_computed(
    tmp_path: Path,
) -> None:
    hybrid_cfg = load_scenario_config(str(REPO_ROOT / HYBRID_SCENARIO))
    hybrid = run_v14_pipeline(str(REPO_ROOT / HYBRID_SCENARIO))
    report_ctx = build_report_context(
        CaseResult.from_pipeline_result(dict(hybrid), scenario_variant="hybrid"),
        generated_at=hybrid["run_manifest"]["generated_at"],
        scenario_config=hybrid_cfg,
        debt_result=hybrid.get("debt_result"),
        annual_rows=hybrid.get("annual_rows"),
        run_result=dict(hybrid),
    ).model_copy(update={"f5_notice": F5_NON_RELIANCE_NOTICE})
    surface = CaseSurface.from_report_context(report_ctx)
    assert report_ctx.multi_tech is not None
    assert surface.section_dispositions["multi_tech"] == "allocated"
    assert surface.section_dispositions["kpis"] == "computed"

    # Allocated CAPEX attribution on hybrid remains distinct from computed finance KPIs.
    wb_path = emit_executive_workbook_from_pipeline(hybrid, tmp_path / "hybrid.xlsx")
    shared = verify_consumer_matrix(
        manifests={
            "api_surface": surface.run_manifest,
            "report_html": report_ctx.manifest,
            "executive_workbook": read_workbook_run_manifest(wb_path),
        },
        units={
            "api_surface": {c.key: c.unit for c in surface.kpi_cards},
            "report_html": {
                row.key: metric_unit(row.key) for row in report_ctx.kpi_rows
            },
            "executive_workbook": _workbook_units_for_cards(
                wb_path, [c.key for c in surface.kpi_cards]
            ),
        },
        dispositions={
            "api_surface": surface.section_dispositions,
            "report_html": {
                "kpis": "computed",
                "tornado": "omitted",
                "global_sa_morris": "omitted",
                "global_sa_pawn": "omitted",
                "capital_risk": "omitted",
                "multi_tech": "allocated",
            },
        },
        reliance={
            "api_surface": {
                "reliance_label": surface.reliance_label,
                "notice": surface.reliance_notice,
                "allocated_covenant_distinct": True,
            },
            "report_html": {
                "reliance_label": "lender_reliance_prohibited",
                "notice": report_ctx.f5_notice,
                "allocated_covenant_distinct": True,
            },
        },
        require_f5=True,
        require_allocated_covenant_distinction=True,
    )
    assert shared["shared_dispositions"]["multi_tech"] == "allocated"


def test_synthetic_grid_screening_reliance_passes_only_with_non_bankable_disclosure() -> (
    None
):
    assert QSTS_SYNTHETIC_OUTPUT_CLASS == "synthetic_process_provenance"
    require_reliance_labels(
        {
            "grid_screening": {
                "reliance_label": "screening_only_synthetic_grid",
                "notice": EXECUTIVE_WORKBOOK_F5_CAVEAT,
                "synthetic_grid_screening_only": True,
                "synthetic_grid_notice": (
                    f"{MANDATORY_SCREENING_CAVEAT} {SYNTHETIC_PROCESS_PROVENANCE_WARNING}"
                ),
            }
        },
        require_f5=True,
        require_synthetic_grid_screening=True,
    )


# ---------------------------------------------------------------------------
# Hostile mismatch controls
# ---------------------------------------------------------------------------


def test_hostile_unit_contract_mismatch_fails_loudly() -> None:
    with pytest.raises(ValueError, match="unit contract mismatch.*project_irr"):
        require_unit_contracts_aligned(
            {
                "api_surface": {"project_irr": "pct", "project_npv": "usd"},
                "executive_workbook": {"project_irr": "usd", "project_npv": "usd"},
            }
        )


def test_hostile_display_unit_mismatch_fails_loudly() -> None:
    with pytest.raises(ValueError, match="must end with '%'"):
        validate_display_matches_unit("project_irr", "pct", 0.0146, "1.46x")
    with pytest.raises(ValueError, match="must end with 'x'"):
        validate_display_matches_unit("min_dscr", "multiple", 1.29, "129.00%")
    with pytest.raises(ValueError, match="accounting sign"):
        validate_display_matches_unit("project_npv", "usd", -100.0, "-100")


def test_hostile_section_disposition_mismatch_fails_loudly() -> None:
    with pytest.raises(ValueError, match="section disposition mismatch.*capital_risk"):
        require_consistent_section_dispositions(
            {
                "api_surface": {"kpis": "computed", "capital_risk": "computed"},
                "report_html": {"kpis": "computed", "capital_risk": "not_run"},
            }
        )
    with pytest.raises(ValueError, match="section disposition mismatch.*multi_tech"):
        require_consistent_section_dispositions(
            {
                "api_surface": {"multi_tech": "allocated"},
                "report_html": {"multi_tech": "computed"},
            }
        )
    with pytest.raises(ValueError, match="invalid disposition 'guessed'"):
        require_consistent_section_dispositions(
            {
                "api_surface": {"kpis": "guessed"},
                "report_html": {"kpis": "computed"},
            }
        )


def test_hostile_reliance_hold_stripping_and_withdrawal_fail_loudly() -> None:
    with pytest.raises(ValueError, match="lacks HOLD token"):
        require_reliance_labels(
            {
                "api_surface": {
                    "reliance_label": "lender_reliance_prohibited",
                    "notice": "Non-reliance notice for screening only.",
                }
            },
            require_f5=True,
        )
    with pytest.raises(ValueError, match="contradicting the active HOLD union"):
        check_no_hold_withdrawal(
            "HOLD lifted: approved for lender reliance.", "executive_workbook"
        )
    with pytest.raises(ValueError, match="not marked screening-only"):
        require_reliance_labels(
            {
                "grid_report": {
                    "reliance_label": "screening_only_synthetic_grid",
                    "notice": F5_NON_RELIANCE_NOTICE,
                    "synthetic_grid_screening_only": False,
                    "synthetic_grid_notice": MANDATORY_SCREENING_CAVEAT,
                }
            },
            require_synthetic_grid_screening=True,
        )
    with pytest.raises(
        ValueError, match="not distinguished from approved covenant metrics"
    ):
        require_reliance_labels(
            {
                "workbook": {
                    "reliance_label": "allocated_within_year_non_covenant",
                    "notice": F5_NON_RELIANCE_NOTICE,
                    "allocated_covenant_distinct": False,
                }
            },
            require_allocated_covenant_distinction=True,
        )
