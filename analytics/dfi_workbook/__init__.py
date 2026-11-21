"""Formula-driven, macro-free DFI workbook foundation package."""

from __future__ import annotations

from analytics.dfi_workbook.foundation import (
    DFI_WORKBOOK_F5_CAVEAT,
    DfiWorkbookMetadata,
    ModuleLedgerEntry,
    WorkbookInputItem,
    build_dfi_workbook_foundation,
)
from analytics.dfi_workbook.registry import CellRef, CellRegistry

__all__ = [
    "CellRef",
    "CellRegistry",
    "DFI_WORKBOOK_F5_CAVEAT",
    "DfiWorkbookMetadata",
    "ModuleLedgerEntry",
    "WorkbookInputItem",
    "build_dfi_workbook_foundation",
]
