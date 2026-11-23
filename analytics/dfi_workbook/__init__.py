"""Formula-driven, macro-free DFI workbook foundation package."""

from __future__ import annotations

from analytics.dfi_workbook.foundation import (
    DFI_WORKBOOK_F5_CAVEAT,
    SCENARIO_NOTE_ROW_LABEL,
    DfiWorkbookMetadata,
    ModuleLedgerEntry,
    WorkbookInputItem,
    build_dfi_workbook_foundation,
    project_module_execution_ledger,
    project_module_execution_record,
    validate_ledger_against_execution_records,
)
from analytics.dfi_workbook.registry import CellRef, CellRegistry

__all__ = [
    "CellRef",
    "CellRegistry",
    "DFI_WORKBOOK_F5_CAVEAT",
    "DfiWorkbookMetadata",
    "ModuleLedgerEntry",
    "SCENARIO_NOTE_ROW_LABEL",
    "WorkbookInputItem",
    "build_dfi_workbook_foundation",
    "project_module_execution_ledger",
    "project_module_execution_record",
    "validate_ledger_against_execution_records",
]
