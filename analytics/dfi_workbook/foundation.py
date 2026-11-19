"""Macro-free, formula-driven DFI workbook foundation (Control, Inputs, Ledger)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from analytics.dfi_workbook.registry import CellRegistry
from analytics.executive_workbook import EXECUTIVE_WORKBOOK_F5_CAVEAT
from analytics.reproducible_workbook import (
    PathLike,
    freeze_workbook_reproducible,
    normalize_xlsx_reproducible,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from openpyxl.worksheet.worksheet import Worksheet

CONTROL_SHEET_NAME = "Control_Provenance"
INPUTS_SHEET_NAME = "Inputs"
LEDGER_SHEET_NAME = "Module_Ledger"

CANONICAL_LEDGER_STATUSES: tuple[str, ...] = (
    "executed",
    "guard_passed",
    "guard_refused",
    "not_applicable",
    "skipped_missing_inputs",
    "skipped_optional_extra",
    "skipped_sync_profile",
    "failed",
)

DEFAULT_FORMULA_BOUNDARY_NOTE: str = (
    "Option B Formula Boundary: Scalar parameters on 'Inputs' and workbook-internal "
    "summaries (including 'Module_Ledger' status rollups) use live Excel formulas "
    "bound via CellRegistry; complex upstream physics, Monte Carlo simulations, and "
    "debt-sculpting schedules in downstream sheets are engine-computed tables with "
    "explicit provenance rather than simplified spreadsheet approximations."
)

_FORBIDDEN_OUTPUT_EXTENSIONS: frozenset[str] = frozenset({".xlsm", ".xlsb", ".xltm"})

_INPUT_HEADERS: tuple[str, ...] = (
    "Key",
    "Section",
    "Label",
    "Value",
    "Unit",
    "Provenance",
    "Excel_Ref",
)

_LEDGER_HEADERS: tuple[str, ...] = (
    "Module",
    "Stage",
    "Role",
    "Status",
    "Excel_Representation",
    "Reason",
    "Provenance_Ref",
)


def _require_non_empty_str(value: object, field_name: str) -> str:
    """Validate that ``value`` is a non-empty, non-blank string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _require_str(value: object, field_name: str) -> str:
    """Validate that ``value`` is a string (empty allowed)."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value).__name__}.")
    return value


def _require_openpyxl() -> Any:
    """Import openpyxl lazily with an actionable CASPER error if missing."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - optional-guard safety
        raise ImportError(
            "openpyxl is required to build DFI workbooks; install runtime "
            "dependencies (e.g. `pip install openpyxl>=3.1`)."
        ) from exc
    return openpyxl


class WorkbookInputItem(BaseModel):
    """Typed contract for one scalar input parameter written to ``Inputs``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    section: str
    label: str
    value: Union[float, int, str, bool]
    unit: str
    number_format: str = "General"
    provenance: str

    @field_validator(
        "key", "section", "label", "number_format", "provenance", mode="before"
    )
    @classmethod
    def _validate_required_texts(cls, value: object, info: ValidationInfo) -> str:
        return _require_non_empty_str(value, str(info.field_name))

    @field_validator("unit", mode="before")
    @classmethod
    def _validate_unit(cls, value: object) -> str:
        return _require_str(value, "unit")

    @field_validator("value", mode="before")
    @classmethod
    def _validate_scalar_value(cls, value: Any) -> Union[float, int, str, bool]:
        if hasattr(value, "item") and type(value).__module__.startswith("numpy"):
            value = value.item()
        if not isinstance(value, (bool, int, float, str)):
            raise ValueError(
                "WorkbookInputItem.value must be bool, int, float, or str; "
                f"got {type(value).__name__}."
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"WorkbookInputItem.value must be finite, got {value!r}.")
        return value


class ModuleLedgerEntry(BaseModel):
    """Typed contract for one module execution/representation ledger entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_path: str
    pipeline_stage: str
    role_description: str
    status: str
    excel_representation: str
    reason: str = ""
    provenance_ref: str = ""

    @field_validator(
        "module_path",
        "pipeline_stage",
        "role_description",
        "status",
        "excel_representation",
        mode="before",
    )
    @classmethod
    def _validate_required_texts(cls, value: object, info: ValidationInfo) -> str:
        return _require_non_empty_str(value, str(info.field_name))

    @field_validator("reason", "provenance_ref", mode="before")
    @classmethod
    def _validate_optional_texts(cls, value: object, info: ValidationInfo) -> str:
        return _require_str(value, str(info.field_name))


class DfiWorkbookMetadata(BaseModel):
    """Strict provenance and governance metadata for ``Control_Provenance``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_name: str
    scenario_name: str
    run_mode: Optional[str] = None
    config_sha256: str
    engine_version: str
    generated_at: str
    non_reliance_notice: str = EXECUTIVE_WORKBOOK_F5_CAVEAT
    formula_boundary_note: str = DEFAULT_FORMULA_BOUNDARY_NOTE

    @field_validator(
        "project_name",
        "scenario_name",
        "config_sha256",
        "engine_version",
        "generated_at",
        "non_reliance_notice",
        "formula_boundary_note",
        mode="before",
    )
    @classmethod
    def _validate_required_texts(cls, value: object, info: ValidationInfo) -> str:
        return _require_non_empty_str(value, str(info.field_name))

    @field_validator("run_mode", mode="before")
    @classmethod
    def _validate_run_mode(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty_str(value, "run_mode")


@dataclass(frozen=True)
class _WorkbookStyles:
    """Reusable openpyxl style objects for consistent DFI workbook formatting."""

    notice_font: Any
    notice_fill: Any
    notice_alignment: Any
    header_font: Any
    header_fill: Any
    header_alignment: Any
    body_font: Any
    body_alignment: Any
    value_alignment: Any
    total_font: Any
    total_fill: Any
    thin_border: Any
    total_border: Any


def _build_styles() -> _WorkbookStyles:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    thin = Side(border_style="thin", color="CBD5E1")
    double = Side(border_style="double", color="1B365D")
    top_thin = Side(border_style="thin", color="1B365D")

    return _WorkbookStyles(
        notice_font=Font(name="Calibri", size=10, bold=True, color="7F1D1D"),
        notice_fill=PatternFill(fill_type="solid", fgColor="FEF2F2"),
        notice_alignment=Alignment(
            horizontal="left", vertical="center", wrap_text=True
        ),
        header_font=Font(name="Calibri", size=10, bold=True, color="FFFFFF"),
        header_fill=PatternFill(fill_type="solid", fgColor="1B365D"),
        header_alignment=Alignment(
            horizontal="left", vertical="center", wrap_text=True
        ),
        body_font=Font(name="Calibri", size=10, color="0F172A"),
        body_alignment=Alignment(horizontal="left", vertical="top", wrap_text=True),
        value_alignment=Alignment(horizontal="right", vertical="top"),
        total_font=Font(name="Calibri", size=10, bold=True, color="0F172A"),
        total_fill=PatternFill(fill_type="solid", fgColor="F1F5F9"),
        thin_border=Border(left=thin, right=thin, top=thin, bottom=thin),
        total_border=Border(left=thin, right=thin, top=top_thin, bottom=double),
    )


def _apply_column_widths(
    ws: "Worksheet",
    widths: dict[str, int],
) -> None:
    """Assign deterministic explicit column widths."""
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def _populate_control_provenance_sheet(
    ws: "Worksheet",
    metadata: DfiWorkbookMetadata,
    styles: _WorkbookStyles,
) -> None:
    """Populate Sheet 1 (``Control_Provenance``) with notice and metadata."""
    ws.title = CONTROL_SHEET_NAME
    ws.views.sheetView[0].showGridLines = True

    ws["A1"] = metadata.non_reliance_notice
    ws.merge_cells("A1:B1")
    for col in ("A", "B"):
        cell = ws[f"{col}1"]
        cell.font = styles.notice_font
        cell.fill = styles.notice_fill
        cell.alignment = styles.notice_alignment
        cell.border = styles.thin_border
    ws.row_dimensions[1].height = 48

    ws["A3"] = "Field"
    ws["B3"] = "Value"
    for col in ("A", "B"):
        cell = ws[f"{col}3"]
        cell.font = styles.header_font
        cell.fill = styles.header_fill
        cell.alignment = styles.header_alignment
        cell.border = styles.thin_border
    ws.row_dimensions[3].height = 22

    rows: tuple[tuple[str, str], ...] = (
        ("project_name", metadata.project_name),
        ("scenario_name", metadata.scenario_name),
        ("run_mode", metadata.run_mode if metadata.run_mode is not None else ""),
        ("config_sha256", metadata.config_sha256),
        ("engine_version", metadata.engine_version),
        ("generated_at", metadata.generated_at),
        ("formula_boundary_note", metadata.formula_boundary_note),
    )
    for row_idx, (field_name, field_value) in enumerate(rows, start=4):
        key_cell = ws.cell(row=row_idx, column=1, value=field_name)
        val_cell = ws.cell(row=row_idx, column=2, value=field_value)
        key_cell.font = styles.body_font
        key_cell.alignment = styles.body_alignment
        key_cell.border = styles.thin_border
        val_cell.font = styles.body_font
        val_cell.alignment = styles.body_alignment
        val_cell.border = styles.thin_border
        if field_name == "formula_boundary_note":
            ws.row_dimensions[row_idx].height = 42

    ws.freeze_panes = "A4"
    _apply_column_widths(ws, {"A": 26, "B": 96})


def _populate_inputs_sheet(
    ws: "Worksheet",
    inputs: Sequence[WorkbookInputItem],
    registry: CellRegistry,
    styles: _WorkbookStyles,
) -> None:
    """Populate Sheet 2 (``Inputs``) and register every input in ``registry``."""
    ws.views.sheetView[0].showGridLines = True

    for col_idx, header in enumerate(_INPUT_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = styles.header_font
        cell.fill = styles.header_fill
        cell.alignment = styles.header_alignment
        cell.border = styles.thin_border
    ws.row_dimensions[1].height = 22

    max_lens = [len(h) for h in _INPUT_HEADERS]
    for row_idx, item in enumerate(inputs, start=2):
        cell_ref = registry.register(
            item.key,
            sheet=INPUTS_SHEET_NAME,
            column="D",
            row=row_idx,
            unit=item.unit,
            number_format=item.number_format,
            provenance=item.provenance,
        )
        excel_ref = cell_ref.formula_ref(absolute=True)
        row_values: tuple[Any, ...] = (
            item.key,
            item.section,
            item.label,
            item.value,
            item.unit,
            item.provenance,
            excel_ref,
        )
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = styles.body_font
            cell.border = styles.thin_border
            if col_idx == 4:
                cell.number_format = item.number_format
                cell.alignment = (
                    styles.body_alignment
                    if isinstance(val, (str, bool))
                    else styles.value_alignment
                )
            else:
                cell.alignment = styles.body_alignment
            max_lens[col_idx - 1] = max(max_lens[col_idx - 1], len(str(val)))

    ws.freeze_panes = "A2"
    col_letters = ("A", "B", "C", "D", "E", "F", "G")
    widths = {
        col: min(max(length + 4, 14), 56)
        for col, length in zip(col_letters, max_lens, strict=True)
    }
    _apply_column_widths(ws, widths)


def _populate_module_ledger_sheet(
    ws: "Worksheet",
    ledger_entries: Sequence[ModuleLedgerEntry],
    registry: CellRegistry,
    styles: _WorkbookStyles,
) -> None:
    """Populate Sheet 3 (``Module_Ledger``) and a live-formula Status Rollup."""
    ws.views.sheetView[0].showGridLines = True

    for col_idx, header in enumerate(_LEDGER_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = styles.header_font
        cell.fill = styles.header_fill
        cell.alignment = styles.header_alignment
        cell.border = styles.thin_border
    ws.row_dimensions[1].height = 22

    max_lens = [len(h) for h in _LEDGER_HEADERS]
    for row_idx, entry in enumerate(ledger_entries, start=2):
        row_values = (
            entry.module_path,
            entry.pipeline_stage,
            entry.role_description,
            entry.status,
            entry.excel_representation,
            entry.reason,
            entry.provenance_ref,
        )
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = styles.body_font
            cell.alignment = styles.body_alignment
            cell.border = styles.thin_border
            max_lens[col_idx - 1] = max(max_lens[col_idx - 1], len(val))

    # Build the Status Rollup table in columns I:J (separated by spacer H)
    # so Row 1 holds all headers cleanly and freeze_panes="A2" locks both tables.
    for col_idx, title in ((9, "Status"), (10, "Count")):
        cell = ws.cell(row=1, column=col_idx, value=title)
        cell.font = styles.header_font
        cell.fill = styles.header_fill
        cell.alignment = styles.header_alignment
        cell.border = styles.thin_border

    extra_statuses = sorted(
        {
            entry.status
            for entry in ledger_entries
            if entry.status not in CANONICAL_LEDGER_STATUSES
        }
    )
    rollup_statuses = list(CANONICAL_LEDGER_STATUSES) + extra_statuses

    status_end_row = max(2, 1 + len(ledger_entries))
    status_range = registry.range_ref(
        LEDGER_SHEET_NAME, "D", 2, "D", status_end_row, absolute=True
    )

    for row_idx, status_name in enumerate(rollup_statuses, start=2):
        label_cell = ws.cell(row=row_idx, column=9, value=status_name)
        count_cell = ws.cell(
            row=row_idx,
            column=10,
            value=f"=COUNTIF({status_range}, I{row_idx})",
        )
        label_cell.font = styles.body_font
        label_cell.alignment = styles.body_alignment
        label_cell.border = styles.thin_border
        count_cell.font = styles.body_font
        count_cell.alignment = styles.value_alignment
        count_cell.border = styles.thin_border
        count_cell.number_format = "#,##0"

    total_row = 2 + len(rollup_statuses)
    sum_range = registry.range_ref(
        LEDGER_SHEET_NAME, "J", 2, "J", total_row - 1, absolute=True
    )
    total_label_cell = ws.cell(row=total_row, column=9, value="Total")
    total_count_cell = ws.cell(row=total_row, column=10, value=f"=SUM({sum_range})")
    for cell, align in (
        (total_label_cell, styles.body_alignment),
        (total_count_cell, styles.value_alignment),
    ):
        cell.font = styles.total_font
        cell.fill = styles.total_fill
        cell.alignment = align
        cell.border = styles.total_border
    total_count_cell.number_format = "#,##0"

    ws.freeze_panes = "A2"
    ledger_cols = ("A", "B", "C", "D", "E", "F", "G")
    widths = {
        col: min(max(length + 4, 14), 52)
        for col, length in zip(ledger_cols, max_lens, strict=True)
    }
    widths["H"] = 4
    widths["I"] = max(26, max((len(s) for s in rollup_statuses), default=0) + 4)
    widths["J"] = 12
    _apply_column_widths(ws, widths)


def _coerce_input_item(item: object) -> WorkbookInputItem:
    if isinstance(item, WorkbookInputItem):
        return item
    return WorkbookInputItem.model_validate(item)


def _coerce_ledger_entry(entry: object) -> ModuleLedgerEntry:
    if isinstance(entry, ModuleLedgerEntry):
        return entry
    return ModuleLedgerEntry.model_validate(entry)


def build_dfi_workbook_foundation(
    output_path: PathLike,
    *,
    metadata: DfiWorkbookMetadata,
    inputs: Sequence[WorkbookInputItem],
    ledger_entries: Sequence[ModuleLedgerEntry],
) -> tuple[Path, CellRegistry]:
    """Build the macro-free, byte-reproducible DFI workbook foundation.

    Creates three worksheets in fixed order:

    1. ``Control_Provenance``: un-suppressible F-5 non-reliance notice in ``A1``
       followed by governance, config digest, and Option B formula-boundary rows.
    2. ``Inputs``: canonical scalar inputs registered into a :class:`CellRegistry`
       at column ``D`` with explicit units, number formats, provenance, and
       ``Excel_Ref`` coordinate strings.
    3. ``Module_Ledger``: structured module role/status ledger plus a live
       ``=COUNTIF(...)`` / ``=SUM(...)`` Status Rollup summary table.

    Args:
        output_path: Destination ``.xlsx`` path (parent directories created).
        metadata: Validated :class:`DfiWorkbookMetadata` record.
        inputs: Non-empty sequence of :class:`WorkbookInputItem` entries.
        ledger_entries: Sequence of :class:`ModuleLedgerEntry` records.

    Returns:
        Tuple of ``(resolved_output_path, populated_cell_registry)``.

    Raises:
        ValueError: If ``inputs`` is empty, duplicate keys occur, metadata
            validation fails, or a macro-enabled output extension is requested.
    """
    validated_metadata = (
        metadata
        if isinstance(metadata, DfiWorkbookMetadata)
        else DfiWorkbookMetadata.model_validate(metadata)
    )
    validated_inputs = [_coerce_input_item(item) for item in inputs]
    if not validated_inputs:
        raise ValueError(
            "inputs must contain at least one WorkbookInputItem; cannot build "
            "an Inputs sheet without registered scalar parameters."
        )
    validated_ledger = [_coerce_ledger_entry(entry) for entry in ledger_entries]

    out_path = Path(output_path).expanduser().resolve()
    if out_path.suffix.lower() in _FORBIDDEN_OUTPUT_EXTENSIONS:
        raise ValueError(
            f"Macro-enabled workbook extension {out_path.suffix!r} is forbidden; "
            "DFI workbooks must be macro-free .xlsx artifacts."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    openpyxl = _require_openpyxl()
    wb = openpyxl.Workbook()
    styles = _build_styles()
    registry = CellRegistry()

    control_ws = wb.active
    if control_ws is None:  # pragma: no cover - defensive mypy narrowing
        raise RuntimeError("openpyxl.Workbook() returned no active worksheet.")
    _populate_control_provenance_sheet(control_ws, validated_metadata, styles)

    inputs_ws = wb.create_sheet(title=INPUTS_SHEET_NAME)
    _populate_inputs_sheet(inputs_ws, validated_inputs, registry, styles)

    ledger_ws = wb.create_sheet(title=LEDGER_SHEET_NAME)
    _populate_module_ledger_sheet(ledger_ws, validated_ledger, registry, styles)

    freeze_workbook_reproducible(wb)
    wb.save(out_path)
    normalize_xlsx_reproducible(out_path)

    return out_path, registry


__all__ = [
    "CANONICAL_LEDGER_STATUSES",
    "CONTROL_SHEET_NAME",
    "DEFAULT_FORMULA_BOUNDARY_NOTE",
    "DfiWorkbookMetadata",
    "INPUTS_SHEET_NAME",
    "LEDGER_SHEET_NAME",
    "ModuleLedgerEntry",
    "WorkbookInputItem",
    "build_dfi_workbook_foundation",
]
