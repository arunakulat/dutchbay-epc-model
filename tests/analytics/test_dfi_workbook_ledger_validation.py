"""Unit and mutation tests for #1827 Module_Ledger vs ModuleExecutionRecord validation."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest
from pydantic import ValidationError

from analytics.dfi_workbook import (
    DfiWorkbookMetadata,
    ModuleLedgerEntry,
    WorkbookInputItem,
    build_dfi_workbook_foundation,
    project_module_execution_ledger,
    project_module_execution_record,
    validate_ledger_against_execution_records,
)
from analytics.dfi_workbook.foundation import CANONICAL_LEDGER_STATUSES
from app.reports.module_ledger import (
    ExcelRepresentationKind,
    ModuleExecutionLedger,
    ModuleExecutionRecord,
    ModuleExecutionStatus,
    PipelineStage,
    build_module_execution_ledger,
    load_module_role_registry,
)


def _metadata() -> DfiWorkbookMetadata:
    return DfiWorkbookMetadata(
        project_name="Sample Utility Wind Project",
        scenario_name="base_case",
        run_mode="full_deterministic",
        config_sha256="b" * 64,
        engine_version="15.33.0",
        generated_at="2026-11-23T10:00:00Z",
    )


def _inputs() -> tuple[WorkbookInputItem, ...]:
    return (
        WorkbookInputItem(
            key="project.capacity_mw",
            section="Technical",
            label="Installed Capacity",
            value=100.0,
            unit="MW",
            number_format="#,##0.0",
            provenance="scenario_yaml:project.capacity_mw",
        ),
    )


def _sample_execution_ledger() -> ModuleExecutionLedger:
    registry = load_module_role_registry()
    cashflow_spec = registry.get("finance.cashflow_v14")
    aep_spec = registry.get("analytics.aep_provenance")
    grid_spec = registry.get("analytics.grid.pandapower_screening")
    sc_spec = registry.get("analytics.grid.short_circuit")

    records = (
        ModuleExecutionRecord(
            module_path=cashflow_spec.module_path,
            pipeline_stage=cashflow_spec.pipeline_stage,
            role_description=cashflow_spec.role_description,
            status=ModuleExecutionStatus.EXECUTED,
            excel_representation=cashflow_spec.excel_representation,
            provenance_refs=("run_manifest:cashflow", "v14:annual"),
        ),
        ModuleExecutionRecord(
            module_path=aep_spec.module_path,
            pipeline_stage=aep_spec.pipeline_stage,
            role_description=aep_spec.role_description,
            status=ModuleExecutionStatus.GUARD_PASSED,
            excel_representation=aep_spec.excel_representation,
            caveat="AEP provenance verified",
            provenance_refs=("guard:aep",),
        ),
        ModuleExecutionRecord(
            module_path=grid_spec.module_path,
            pipeline_stage=grid_spec.pipeline_stage,
            role_description=grid_spec.role_description,
            status=ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
            excel_representation=grid_spec.excel_representation,
            missing_extra="grid",
            reason="Optional extra [grid] not installed.",
        ),
        ModuleExecutionRecord(
            module_path=sc_spec.module_path,
            pipeline_stage=sc_spec.pipeline_stage,
            role_description=sc_spec.role_description,
            status=ModuleExecutionStatus.DEGRADED,
            excel_representation=sc_spec.excel_representation,
            reason="Closed-form fallback executed because [grid] is absent.",
            provenance_refs=("fallback:thevenin",),
        ),
    )
    return build_module_execution_ledger("sync_lender", records, registry=registry)


def test_canonical_status_vocabulary_matches_1813_contract_exactly() -> None:
    expected = tuple(status.value for status in ModuleExecutionStatus)
    assert CANONICAL_LEDGER_STATUSES == expected
    assert "degraded" in CANONICAL_LEDGER_STATUSES


def test_project_module_execution_record_projects_fields_and_caveat_fallback() -> None:
    ledger = _sample_execution_ledger()
    projected = project_module_execution_ledger(ledger)
    assert len(projected) == len(ledger.records)

    cashflow_entry = project_module_execution_record(ledger.records[0].model_dump())
    assert cashflow_entry == projected[0]
    assert cashflow_entry.module_path == "finance.cashflow_v14"
    assert cashflow_entry.pipeline_stage == PipelineStage.CORE_FINANCE.value
    assert cashflow_entry.status == ModuleExecutionStatus.EXECUTED.value
    assert cashflow_entry.excel_representation == ExcelRepresentationKind.FORMULA.value
    assert cashflow_entry.reason == ""
    assert cashflow_entry.provenance_ref == "run_manifest:cashflow, v14:annual"

    # When reason is None and caveat is present, caveat surfaces in reason.
    assert projected[1].reason == "AEP provenance verified"
    assert projected[1].provenance_ref == "guard:aep"
    assert projected[2].reason == "Optional extra [grid] not installed."
    assert projected[3].status == ModuleExecutionStatus.DEGRADED.value


def test_build_dfi_workbook_from_execution_records_only(tmp_path: Path) -> None:
    exec_ledger = _sample_execution_ledger()
    dest = tmp_path / "from_exec_ledger.xlsx"
    out_path, _ = build_dfi_workbook_foundation(
        dest,
        metadata=_metadata(),
        inputs=_inputs(),
        execution_records=exec_ledger,
    )
    assert out_path.exists()

    wb = openpyxl.load_workbook(out_path, data_only=False)
    ws = wb["Module_Ledger"]
    projected = project_module_execution_ledger(exec_ledger)
    for row_idx, entry in enumerate(projected, start=2):
        assert ws.cell(row=row_idx, column=1).value == entry.module_path
        assert ws.cell(row=row_idx, column=2).value == entry.pipeline_stage
        assert ws.cell(row=row_idx, column=3).value == entry.role_description
        assert ws.cell(row=row_idx, column=4).value == entry.status
        assert ws.cell(row=row_idx, column=5).value == entry.excel_representation
        assert (ws.cell(row=row_idx, column=6).value or "") == entry.reason
        assert (ws.cell(row=row_idx, column=7).value or "") == entry.provenance_ref

    assert [
        ws.cell(row=r, column=9).value
        for r in range(2, 2 + len(CANONICAL_LEDGER_STATUSES))
    ] == list(CANONICAL_LEDGER_STATUSES)
    wb.close()


def test_build_dfi_workbook_accepts_matching_ledger_and_execution_records(
    tmp_path: Path,
) -> None:
    exec_ledger = _sample_execution_ledger()
    projected = project_module_execution_ledger(exec_ledger)
    dest = tmp_path / "matched.xlsx"
    out_path, _ = build_dfi_workbook_foundation(
        dest,
        metadata=_metadata(),
        inputs=_inputs(),
        ledger_entries=projected,
        execution_records=exec_ledger.records,
    )
    assert out_path.exists()


def test_mutation_drop_execution_record_refused_before_touching_dest(
    tmp_path: Path,
) -> None:
    exec_ledger = _sample_execution_ledger()
    projected = project_module_execution_ledger(exec_ledger)
    dropped = projected[:-1]

    dest = tmp_path / "new_dir" / "dropped.xlsx"
    with pytest.raises(ValueError, match="missing from Module_Ledger"):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            ledger_entries=dropped,
            execution_records=exec_ledger,
        )
    assert not dest.parent.exists()


def test_mutation_orphan_ledger_row_refused_before_touching_dest(
    tmp_path: Path,
) -> None:
    exec_ledger = _sample_execution_ledger()
    projected = project_module_execution_ledger(exec_ledger)
    orphan = ModuleLedgerEntry(
        module_path="analytics.unexecuted_orphan",
        pipeline_stage=PipelineStage.GOVERNANCE.value,
        role_description="Orphan row injected without execution record.",
        status=ModuleExecutionStatus.EXECUTED.value,
        excel_representation=ExcelRepresentationKind.GOVERNANCE_METADATA.value,
    )

    dest = tmp_path / "new_dir" / "orphan.xlsx"
    with pytest.raises(ValueError, match="Orphan Module_Ledger"):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            ledger_entries=projected + (orphan,),
            execution_records=exec_ledger,
        )
    assert not dest.parent.exists()


def test_mutation_renamed_status_refused_before_touching_dest(tmp_path: Path) -> None:
    exec_ledger = _sample_execution_ledger()
    projected = list(project_module_execution_ledger(exec_ledger))
    projected[0] = projected[0].model_copy(
        update={"status": ModuleExecutionStatus.FAILED.value}
    )

    dest = tmp_path / "new_dir" / "renamed_status.xlsx"
    with pytest.raises(ValueError, match="does not match ModuleExecutionRecord"):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            ledger_entries=projected,
            execution_records=exec_ledger,
        )
    assert not dest.parent.exists()

    with pytest.raises(ValidationError, match="ModuleExecutionStatus"):
        ModuleLedgerEntry.model_validate(
            projected[0].model_dump() | {"status": "renamed_custom_status"}
        )


@pytest.mark.parametrize(
    ("field", "mutated_value"),
    (
        ("pipeline_stage", PipelineStage.REPORTING_DELIVERY.value),
        ("role_description", "Tampered role description for module."),
        ("excel_representation", ExcelRepresentationKind.GOVERNANCE_METADATA.value),
    ),
)
def test_mutation_mismatched_stage_role_or_representation_refused(
    tmp_path: Path, field: str, mutated_value: str
) -> None:
    exec_ledger = _sample_execution_ledger()
    projected = list(project_module_execution_ledger(exec_ledger))
    projected[0] = projected[0].model_copy(update={field: mutated_value})

    dest = tmp_path / "new_dir" / f"mismatch_{field}.xlsx"
    with pytest.raises(ValueError, match=field):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            ledger_entries=projected,
            execution_records=exec_ledger,
        )
    assert not dest.parent.exists()


def test_duplicate_paths_in_ledger_or_execution_records_refused(
    tmp_path: Path,
) -> None:
    exec_ledger = _sample_execution_ledger()
    projected = project_module_execution_ledger(exec_ledger)

    dest = tmp_path / "new_dir" / "dup_ledger.xlsx"
    with pytest.raises(ValueError, match="Duplicate module_path"):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            ledger_entries=(projected[0], projected[0]),
            execution_records=(exec_ledger.records[0],),
        )
    assert not dest.parent.exists()

    with pytest.raises(ValueError, match="Duplicate module_path"):
        validate_ledger_against_execution_records(
            (projected[0],),
            (exec_ledger.records[0], exec_ledger.records[0]),
        )


def test_tampered_execution_ledger_model_copy_refused(tmp_path: Path) -> None:
    exec_ledger = _sample_execution_ledger()
    tampered = exec_ledger.model_copy(
        update={
            "summary_counts": {
                **dict(exec_ledger.summary_counts),
                ModuleExecutionStatus.EXECUTED.value: 99,
            }
        }
    )
    dest = tmp_path / "new_dir" / "tampered_ledger.xlsx"
    with pytest.raises(ValidationError, match="summary_counts do not match"):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            execution_records=tampered,
        )
    assert not dest.parent.exists()


def test_builder_refuses_missing_both_and_non_sequence_ledger_inputs(
    tmp_path: Path,
) -> None:
    exec_ledger = _sample_execution_ledger()
    dest = tmp_path / "new_dir" / "bad_args.xlsx"

    with pytest.raises(
        ValueError, match="Must provide execution_records or ledger_entries"
    ):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
        )
    assert not dest.parent.exists()

    with pytest.raises(ValueError, match="execution_records must be"):
        build_dfi_workbook_foundation(
            dest,
            metadata=_metadata(),
            inputs=_inputs(),
            execution_records=exec_ledger.records[0],  # type: ignore[arg-type]
        )
    assert not dest.parent.exists()
