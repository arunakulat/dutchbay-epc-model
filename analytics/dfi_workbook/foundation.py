"""Macro-free, formula-driven DFI workbook foundation (Control, Inputs, Ledger)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Self, Sequence, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
)

from analytics.dfi_workbook.registry import CellRegistry, _reject_control_chars
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

# Pure-string F-5 non-reliance notice (identical wording to
# analytics.executive_workbook.EXECUTIVE_WORKBOOK_F5_CAVEAT, defined locally so
# analytics.dfi_workbook stays free of pandas/numpy at import time).
DFI_WORKBOOK_F5_CAVEAT: str = (
    "HOLD (F-5, #1110, v15.6.1): Non-reliance notice. These are model outputs for "
    "screening and discussion only. They support no covenant, lender or IC "
    "representation, and no quarterly CFADS or intra-year DSCR figure may be used "
    "for covenant purposes."
)

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
    "Option B Formula Boundary: values on 'Inputs' are literal, engine-supplied "
    "scalar parameters registered by coordinate in CellRegistry; they are not "
    "formulas. The only live Excel formulas in this workbook are the "
    "'Module_Ledger' status rollups (COUNTIF/SUM). Complex upstream physics, "
    "Monte Carlo simulations and debt-sculpting schedules are engine-computed "
    "and are not part of this foundation workbook; no simplified spreadsheet "
    "approximation of them is offered."
)

_FORMULA_TRIGGER_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@")
_LEDGER_STATUS_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")

# An allowlist for the entire format. Only an unquoted, unescaped semicolon
# separates sections. Literal tokens consume their delimiters as a unit.
_FORMAT_LITERAL = r'(?: "[^"\\]*" | \\[ ;:,.%$€£¥()+-] | [ $€£¥()+-] )'
_NUMERIC_FORMAT_SECTION = rf"""
    (?: \[(?:Black|Blue|Cyan|Green|Magenta|Red|White|Yellow)\] )?
    (?: \[(?:<=|>=|<>|=|<|>)[+-]?[0-9]+(?:\.[0-9]+)?\] )?
    {_FORMAT_LITERAL}*+
    (?: General
        | [0#?]++(?:,[0#?]++)*+(?:\.[0#?]++)?,*+(?:E[+-]0++)?(?:[ ]*%)?
    )
    {_FORMAT_LITERAL}*+
"""
_SUPPORTED_NUMERIC_FORMAT_RE = re.compile(
    rf"""
    {_NUMERIC_FORMAT_SECTION}
    (?: ; {_NUMERIC_FORMAT_SECTION}
        (?: ; {_NUMERIC_FORMAT_SECTION}
            (?: ; {_FORMAT_LITERAL}*+ @ {_FORMAT_LITERAL}*+ )?
        )?
    )?
    """,
    re.VERBOSE | re.IGNORECASE | re.ASCII,
)

# A quoted literal may hold only a unit token (optionally with one space on
# either side) or one character that could also be written escaped. Free
# wording beside a value would bypass the literal-text and reliance controls
# (#1828).
_QUOTED_UNIT_TOKENS: frozenset[str] = frozenset(
    {"%", "x", "MW", "MWh", "kWh", "GWh", "USD", "LKR", "days", "years", "yrs"}
)
_QUOTED_SINGLE_CHARACTERS: frozenset[str] = frozenset(" ;:,.%$€£¥()+-")
_FORMAT_TOKEN_RE = re.compile(r'"[^"]*"|\\.|.', re.DOTALL)
_TEXT_OR_BOOL_FORMATS: frozenset[str] = frozenset({"General", "@"})


def _quoted_literal_allowed(content: str) -> bool:
    if content in _QUOTED_SINGLE_CHARACTERS:
        return True
    core = content[1:] if content.startswith(" ") else content
    core = core[:-1] if core.endswith(" ") else core
    return core in _QUOTED_UNIT_TOKENS


def _numeric_format_display_problem(number_format: str) -> Optional[str]:
    """Return why a grammar-valid numeric format would misstate a value.

    The grammar fixes the shape of a format; this check fixes what it shows.
    Conditional sections are refused because spreadsheet readers disagree on
    whether such a section prints the minus sign (#1828). With an explicit
    negative section, the minus sign must be written into that section, either
    as ``-`` or as parentheses, and no other section may print one.
    """
    # Each section is a list of (character, written_as_literal) pairs.
    sections: list[list[tuple[str, bool]]] = [[]]
    for token in _FORMAT_TOKEN_RE.findall(number_format):
        if token == ";":
            sections.append([])
        elif token.startswith('"'):
            content = token[1:-1]
            if not _quoted_literal_allowed(content):
                return (
                    f"quoted literal {token} is not an allowed unit token; allowed "
                    f"are {', '.join(sorted(_QUOTED_UNIT_TOKENS))} or one "
                    "punctuation character."
                )
            sections[-1].extend((char, True) for char in content)
        elif token.startswith("\\"):
            sections[-1].append((token[1:], True))
        else:
            sections[-1].append((token, False))
    if "[<" in number_format or "[>" in number_format or "[=" in number_format:
        return "conditional sections are not supported."
    numeric_sections = sections[:3]
    for index, section in enumerate(numeric_sections):
        # The sign of a scientific exponent (E-00, E+00) is not a value sign.
        text = "".join(
            char
            for position, (char, literal) in enumerate(section)
            if not (
                not literal
                and char in "+-"
                and position > 0
                and section[position - 1] in (("E", False), ("e", False))
            )
        )
        signs = "-" in text or ("(" in text and ")" in text)
        if index == 1:
            if not signs:
                return (
                    "the negative section must show the sign as '-' or as "
                    "parentheses."
                )
        elif "-" in text or "(" in text or ")" in text:
            return (
                f"section {index + 1} prints a minus sign or parentheses, so a "
                "non-negative value would read as negative."
            )
    return None


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


# Conservative cell-text capacity, measured in UTF-16 code units.
_MAX_CELL_TEXT_UNITS = 32767
# Conservative numeric input domain from Microsoft's Excel specifications:
# https://support.microsoft.com/en-us/excel/excel-specifications-and-limits
# Reject rather than round source values that exceed 15 significant digits.
_MAX_EXACT_INPUT_INTEGER = 999_999_999_999_999
_MIN_INPUT_FLOAT_MAGNITUDE = 2.2251e-308
_MAX_INPUT_FLOAT_MAGNITUDE = 9.99999999999999e307
_NUMERIC_SOURCE_RECOVERY = (
    "Preserve the original source externally and supply a supported textual reference "
    "as the workbook input value, for example 'Archive record NUM-04'."
)


def _validate_xml_characters(value: str, field_name: str) -> None:
    """Refuse Unicode characters that cannot appear in an XML 1.0 document."""
    if any(
        0xD800 <= ord(char) <= 0xDFFF or ord(char) in (0xFFFE, 0xFFFF) for char in value
    ):
        raise ValueError(f"{field_name} must contain valid Unicode XML 1.0 text.")


def _validate_literal_text(
    value: object,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> str:
    """Validate text against control characters and leading formula triggers."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value).__name__}.")
    _reject_control_chars(value, field_name)
    _validate_xml_characters(value, field_name)
    try:
        units = len(value.encode("utf-16-le")) // 2
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must contain valid Unicode text.") from exc
    if units > _MAX_CELL_TEXT_UNITS:
        raise ValueError(
            f"{field_name} exceeds the 32767 UTF-16-unit workbook cell-text limit; "
            "shorten or externally reference the source rather than truncate it."
        )
    stripped = value.strip()
    if not allow_empty and not stripped:
        raise ValueError(f"{field_name} must be a non-empty string.")
    if stripped.startswith(_FORMULA_TRIGGER_PREFIXES):
        raise ValueError(
            f"{field_name} {value!r} starts with forbidden formula-injection "
            f"character {stripped[0]!r}; active formula prefixes are disallowed."
        )
    return value


def _validate_iso8601_timestamp(value: object, field_name: str) -> str:
    """Validate that ``value`` is a timezone-aware ISO-8601 datetime or ISO date."""
    text = _validate_literal_text(value, field_name, allow_empty=False)
    if text != text.strip():
        raise ValueError(
            f"{field_name} {text!r} must not have leading or trailing whitespace."
        )
    if _ISO_DATE_RE.fullmatch(text):
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} {text!r} is not a valid ISO-8601 date: {exc}."
            ) from exc
        return text
    if not _ISO_DATETIME_PREFIX_RE.match(text):
        raise ValueError(
            f"{field_name} {text!r} must be a valid timezone-aware ISO-8601 "
            "datetime (e.g. '2026-11-19T12:00:00Z') or ISO date ('YYYY-MM-DD')."
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} {text!r} is not a valid ISO-8601 datetime: {exc}."
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"{field_name} {text!r} must include an explicit UTC or timezone offset "
            "(e.g. 'Z' or '+00:00')."
        )
    return text


def _require_openpyxl() -> Any:
    """Import openpyxl lazily with an actionable CASPER error if missing."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - optional-guard safety
        raise ImportError(
            "openpyxl is required to validate numeric input formats and build DFI "
            "workbooks. Install runtime dependencies (e.g. `pip install openpyxl>=3.1`)."
        ) from exc
    return openpyxl


class WorkbookInputItem(BaseModel):
    """Scalar source that can be represented without implicit rounding.

    Integers are limited to +/-999999999999999. Nonzero floats must be within
    Excel's documented input range and round-trip through 15 significant decimal
    digits to the same Python float. Numeric formats allow one to three sections
    using General or digit placeholders, grouping, decimals, scaling commas,
    percentages and signed scientific exponents. Each numeric section may have
    one of the eight standard named colors. Affixes may use spaces, signs,
    parentheses, currency symbols ($, €, £, ¥), backslash-escaped punctuation
    from the allowlist, or quoted literals holding a unit token or one such
    punctuation character. An optional fourth section after three numeric
    sections accepts a single @ with literal affixes. Formats that openpyxl
    would reopen as a date, time, or duration are also refused.

    A format must not change what a reader sees (#1828). Text and boolean
    values accept only General or @. Conditional sections are refused. An
    explicit negative section must print the sign as ``-`` or parentheses, and
    the positive and zero sections must print neither. Preserve unsupported
    sources externally and supply a supported textual reference as the input
    value. Text must satisfy the literal-text contract, including its
    formula-prefix restriction.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    key: str
    section: str
    label: str
    value: Union[float, int, str, bool]
    unit: str
    number_format: str = "General"
    provenance: str

    @field_validator("key", mode="before")
    @classmethod
    def _validate_key(cls, value: object) -> str:
        text = _validate_literal_text(value, "key", allow_empty=False)
        if text != text.strip():
            raise ValueError(
                f"WorkbookInputItem.key {text!r} must not have leading or "
                "trailing whitespace."
            )
        return text

    @field_validator("section", "label", "provenance", mode="before")
    @classmethod
    def _validate_required_texts(cls, value: object, info: ValidationInfo) -> str:
        return _validate_literal_text(value, str(info.field_name), allow_empty=False)

    @field_validator("number_format", mode="before")
    @classmethod
    def _validate_number_format(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("number_format must be a non-empty string.")
        _reject_control_chars(value, "number_format")
        _validate_xml_characters(value, "number_format")
        if value.strip().startswith("="):
            raise ValueError(f"number_format {value!r} must not start with '='.")
        return value

    @field_validator("unit", mode="before")
    @classmethod
    def _validate_unit(cls, value: object) -> str:
        return _validate_literal_text(value, "unit", allow_empty=True)

    @field_validator("value", mode="before")
    @classmethod
    def _validate_scalar_value(cls, value: object) -> Union[float, int, str, bool]:
        if type(value) not in (bool, int, float, str):
            raise ValueError(
                "WorkbookInputItem.value must be strict Python bool, int, float, "
                f"or str; got {type(value).__name__}."
            )
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(
                    f"WorkbookInputItem.value must be finite, got {value!r}."
                )
            if value != 0.0 and not (
                _MIN_INPUT_FLOAT_MAGNITUDE <= abs(value) <= _MAX_INPUT_FLOAT_MAGNITUDE
            ):
                raise ValueError(
                    "WorkbookInputItem.value exceeds the supported Excel numeric "
                    "input range (nonzero magnitude 2.2251e-308 through "
                    f"9.99999999999999e307). {_NUMERIC_SOURCE_RECOVERY}"
                )
            if float(format(value, ".15g")) != value:
                raise ValueError(
                    "WorkbookInputItem.value exceeds supported Excel numeric "
                    f"precision (15 significant digits). {_NUMERIC_SOURCE_RECOVERY}"
                )
            return value
        if isinstance(value, str):
            return _validate_literal_text(value, "value", allow_empty=False)
        if isinstance(value, (bool, int)):
            if not isinstance(value, bool) and abs(value) > _MAX_EXACT_INPUT_INTEGER:
                raise ValueError(
                    "WorkbookInputItem.value exceeds the supported Excel numeric "
                    f"integer range (+/-999999999999999). {_NUMERIC_SOURCE_RECOVERY}"
                )
            return value
        raise ValueError(  # pragma: no cover - unreachable after type check
            "WorkbookInputItem.value must be strict Python bool, int, float, "
            f"or str; got {type(value).__name__}."
        )

    @model_validator(mode="after")
    def _validate_scalar_format(self) -> Self:
        if isinstance(self.value, (str, bool)):
            if self.number_format in _TEXT_OR_BOOL_FORMATS:
                return self
            raise ValueError(
                f"WorkbookInputItem {self.key!r} has number_format "
                f"{self.number_format!r} for a {type(self.value).__name__} value. "
                "Text and boolean inputs accept only 'General' or '@', so the "
                "displayed text always equals the stored value (#1828)."
            )
        if self.number_format == "General":
            return self
        if _SUPPORTED_NUMERIC_FORMAT_RE.fullmatch(self.number_format):
            problem = _numeric_format_display_problem(self.number_format)
            if problem is not None:
                raise ValueError(
                    f"WorkbookInputItem {self.key!r} has number_format "
                    f"{self.number_format!r} that would misstate the value: "
                    f"{problem}"
                )
            # The reader may misinterpret even a supported literal (e.g. a
            # quoted semicolon after date letters). Check the emitted spelling.
            formats = _require_openpyxl().styles.numbers
            if not (
                formats.is_date_format(self.number_format)
                or formats.is_timedelta_format(self.number_format)
            ):
                return self
        raise ValueError(
            f"WorkbookInputItem {self.key!r} has an unsupported or temporal "
            f"number_format {self.number_format!r} for a numeric scalar. Use "
            "'General' or a supported non-temporal numeric format."
        )


class ModuleLedgerEntry(BaseModel):
    """Typed contract for one module execution/representation ledger entry."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

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
        "excel_representation",
        mode="before",
    )
    @classmethod
    def _validate_required_texts(cls, value: object, info: ValidationInfo) -> str:
        return _validate_literal_text(value, str(info.field_name), allow_empty=False)

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(f"status must be a string, got {type(value).__name__}.")
        _validate_literal_text(value, "status", allow_empty=False)
        normalized = value.strip()
        if not normalized:
            raise ValueError("status must be a non-empty string.")
        if not _LEDGER_STATUS_RE.fullmatch(normalized):
            raise ValueError(
                f"Invalid ModuleLedgerEntry.status {value!r}: expected lowercase "
                "identifier matching ^[a-z][a-z0-9_]*$ (no uppercase, wildcards, "
                "operators, or spaces) so Excel COUNTIF stays exact."
            )
        if normalized == "total":
            raise ValueError(
                "ModuleLedgerEntry.status 'total' is reserved for the "
                "Module_Ledger rollup Total row."
            )
        return normalized

    @field_validator("reason", "provenance_ref", mode="before")
    @classmethod
    def _validate_optional_texts(cls, value: object, info: ValidationInfo) -> str:
        return _validate_literal_text(value, str(info.field_name), allow_empty=True)


class DfiWorkbookMetadata(BaseModel):
    """Strict provenance and governance metadata for ``Control_Provenance``."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    project_name: str
    scenario_name: str
    run_mode: Optional[str] = None
    config_sha256: str
    engine_version: str
    generated_at: str
    non_reliance_notice: str = DFI_WORKBOOK_F5_CAVEAT
    formula_boundary_note: str = DEFAULT_FORMULA_BOUNDARY_NOTE
    # Free scenario wording lives in its own field and row, never in the F-5
    # notice cell, so no appended text can qualify or withdraw the hold.
    scenario_note: Optional[str] = None

    @field_validator(
        "project_name",
        "scenario_name",
        "engine_version",
        "formula_boundary_note",
        mode="before",
    )
    @classmethod
    def _validate_required_texts(cls, value: object, info: ValidationInfo) -> str:
        return _validate_literal_text(value, str(info.field_name), allow_empty=False)

    @field_validator("config_sha256", mode="before")
    @classmethod
    def _validate_config_sha256(cls, value: object) -> str:
        text = _validate_literal_text(value, "config_sha256", allow_empty=False)
        if not _SHA256_HEX_RE.fullmatch(text):
            raise ValueError(
                f"config_sha256 {text!r} must be a 64-character lowercase hex "
                "SHA-256 digest matching ^[0-9a-f]{64}$."
            )
        return text

    @field_validator("generated_at", mode="before")
    @classmethod
    def _validate_generated_at(cls, value: object) -> str:
        return _validate_iso8601_timestamp(value, "generated_at")

    @field_validator("non_reliance_notice", mode="before")
    @classmethod
    def _validate_non_reliance_notice(cls, value: object) -> str:
        text = _validate_literal_text(value, "non_reliance_notice", allow_empty=False)
        if text != DFI_WORKBOOK_F5_CAVEAT:
            raise ValueError(
                "DfiWorkbookMetadata.non_reliance_notice must equal the canonical "
                "F-5 hold (DFI_WORKBOOK_F5_CAVEAT) exactly; the non-reliance notice "
                "cannot be suppressed, replaced, prefixed or extended. Put any "
                "scenario wording in scenario_note."
            )
        return text

    @field_validator("scenario_note", mode="before")
    @classmethod
    def _validate_scenario_note(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        return _validate_literal_text(value, "scenario_note", allow_empty=False)

    @field_validator("run_mode", mode="before")
    @classmethod
    def _validate_run_mode(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        return _validate_literal_text(value, "run_mode", allow_empty=False)


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
    if metadata.non_reliance_notice != DFI_WORKBOOK_F5_CAVEAT:
        raise ValueError(
            "DfiWorkbookMetadata.non_reliance_notice must equal "
            "DFI_WORKBOOK_F5_CAVEAT exactly; cannot emit workbook without the "
            "unaltered F-5 hold."
        )
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
        (
            "scenario_note",
            metadata.scenario_note if metadata.scenario_note is not None else "",
        ),
    )
    for row_idx, (field_name, field_value) in enumerate(rows, start=4):
        key_cell = ws.cell(row=row_idx, column=1, value=field_name)
        val_cell = ws.cell(row=row_idx, column=2, value=field_value)
        val_cell.data_type = "s"
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
            if isinstance(val, str):
                # Literal source text must not inherit Excel error-token inference.
                cell.data_type = "s"
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
            if isinstance(val, str):
                # Literal source text must not inherit Excel error-token inference.
                cell.data_type = "s"
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


def build_dfi_workbook_foundation(
    output_path: PathLike,
    *,
    metadata: DfiWorkbookMetadata | Mapping[str, object],
    inputs: Sequence[WorkbookInputItem | Mapping[str, object]],
    ledger_entries: Sequence[ModuleLedgerEntry | Mapping[str, object]],
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
        metadata: A :class:`DfiWorkbookMetadata` record or equivalent mapping.
        inputs: Non-empty sequence of :class:`WorkbookInputItem` records or mappings.
        ledger_entries: Sequence of :class:`ModuleLedgerEntry` records or mappings.

    Returns:
        Tuple of ``(resolved_output_path, populated_cell_registry)``.

    Raises:
        ValueError: If any record fails validation, ``inputs`` is empty,
            duplicate keys occur, or the output path does not use ``.xlsx``.
    """
    # Revalidate typed records as well as mappings before touching the destination.
    validated_metadata = DfiWorkbookMetadata.model_validate(metadata)
    validated_inputs = [WorkbookInputItem.model_validate(item) for item in inputs]
    if not validated_inputs:
        raise ValueError(
            "inputs must contain at least one WorkbookInputItem; cannot build "
            "an Inputs sheet without registered scalar parameters."
        )
    validated_ledger = [
        ModuleLedgerEntry.model_validate(entry) for entry in ledger_entries
    ]

    out_path = Path(output_path).expanduser().resolve()
    if out_path.suffix.lower() != ".xlsx":
        raise ValueError(
            f"Workbook output path {out_path.name!r} has extension "
            f"{out_path.suffix!r}; DFI workbooks must be macro-free .xlsx artifacts."
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
    "DFI_WORKBOOK_F5_CAVEAT",
    "DfiWorkbookMetadata",
    "INPUTS_SHEET_NAME",
    "LEDGER_SHEET_NAME",
    "ModuleLedgerEntry",
    "WorkbookInputItem",
    "build_dfi_workbook_foundation",
]
