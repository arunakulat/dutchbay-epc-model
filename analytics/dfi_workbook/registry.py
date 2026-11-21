"""Cell coordinate models and collision-checked formula registry for DFI workbooks."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

_FORBIDDEN_SHEET_CHARS: frozenset[str] = frozenset(r"\/?*[:]")
_EXCEL_MAX_SHEET_LEN = 31
_EXCEL_MAX_COL_INDEX = 16_384  # Excel column XFD
_EXCEL_MAX_ROW = 1_048_576
_COL_RE = re.compile(r"^[A-Za-z]{1,3}$")
_UNQUOTED_SHEET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_A1_COLLISION_RE = re.compile(r"^[A-Za-z]{1,3}[1-9][0-9]*$")
_R1C1_COLLISION_RE = re.compile(r"^R[0-9]*C[0-9]*$", re.IGNORECASE)
_RESERVED_UNQUOTED_SHEETS = frozenset({"true", "false", "r", "c"})


def _reject_control_chars(value: str, label: str) -> str:
    """Reject ASCII control characters (``\\x00``–``\\x1f``) in text fields."""
    bad_ctrls = sorted({repr(ch) for ch in value if ord(ch) < 0x20})
    if bad_ctrls:
        raise ValueError(
            f"{label} {value!r} contains forbidden ASCII control character(s): "
            f"{bad_ctrls}."
        )
    return value


def column_letters_to_index(column: str) -> int:
    """Convert an Excel column label (``A``..``XFD``) to a 1-based column index.

    Args:
        column: Excel column letters (case-insensitive, 1 to 3 ASCII letters).

    Returns:
        1-based column index in ``1..16384``.

    Raises:
        ValueError: If ``column`` is not a valid Excel column in ``A..XFD``.
    """
    if not isinstance(column, str) or not _COL_RE.fullmatch(column):
        raise ValueError(
            f"Invalid Excel column {column!r}: expected 1..3 ASCII letters in A..XFD."
        )
    normalized = column.upper()
    index = 0
    for ch in normalized:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    if index < 1 or index > _EXCEL_MAX_COL_INDEX:
        raise ValueError(
            f"Excel column {column!r} (index {index}) exceeds maximum column XFD "
            f"({_EXCEL_MAX_COL_INDEX})."
        )
    return index


def validate_sheet_name(sheet: str) -> str:
    """Validate an Excel worksheet name against OOXML/Excel constraints.

    Args:
        sheet: Candidate worksheet name.

    Returns:
        The validated worksheet name unchanged.

    Raises:
        ValueError: If ``sheet`` is not a string, is empty/blank, has leading or
            trailing whitespace, contains ASCII control characters
            (``\\x00``–``\\x1f``), exceeds 31 characters, starts or ends with
            ``'``, or contains any of ``\\ / ? * [ ] :``.
    """
    if not isinstance(sheet, str):
        raise ValueError(f"Sheet name must be a string, got {type(sheet).__name__}.")
    if not sheet or not sheet.strip():
        raise ValueError("Sheet name must be non-empty.")
    _reject_control_chars(sheet, "Sheet name")
    if sheet != sheet.strip():
        raise ValueError(
            f"Sheet name {sheet!r} must not have leading or trailing whitespace."
        )
    if len(sheet) > _EXCEL_MAX_SHEET_LEN:
        raise ValueError(
            f"Sheet name {sheet!r} is {len(sheet)} characters; Excel allows at "
            f"most {_EXCEL_MAX_SHEET_LEN}."
        )
    bad = sorted(ch for ch in sheet if ch in _FORBIDDEN_SHEET_CHARS)
    if bad:
        raise ValueError(
            f"Sheet name {sheet!r} contains forbidden Excel character(s): {bad}."
        )
    if sheet.startswith("'") or sheet.endswith("'"):
        raise ValueError(
            f"Sheet name {sheet!r} must not start or end with a single quote."
        )
    return sheet


def quote_sheet_name(sheet: str) -> str:
    """Format a validated worksheet name for safe use in Excel formulas.

    Simple identifier sheet names (such as ``Inputs`` or ``Module_Ledger``) are
    returned unquoted unless they collide with cell references (including A1,
    R1C1, and bare ``R``/``C``) or boolean literals; all other valid names are
    wrapped in single quotes with internal apostrophes doubled.

    Args:
        sheet: Worksheet name to format.

    Returns:
        Formula-safe worksheet prefix (without trailing ``!``).
    """
    validated = validate_sheet_name(sheet)
    needs_quotes = (
        not _UNQUOTED_SHEET_RE.fullmatch(validated)
        or _A1_COLLISION_RE.fullmatch(validated) is not None
        or _R1C1_COLLISION_RE.fullmatch(validated) is not None
        or validated.lower() in _RESERVED_UNQUOTED_SHEETS
    )
    if not needs_quotes:
        return validated
    escaped = validated.replace("'", "''")
    return f"'{escaped}'"


class CellRef(BaseModel):
    """Immutable reference to a single worksheet cell with unit and provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sheet: str
    column: str
    row: int
    unit: str = ""
    number_format: str = "General"
    provenance: str = ""

    @field_validator("sheet", mode="before")
    @classmethod
    def _validate_sheet(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(
                f"Sheet name must be a string, got {type(value).__name__}."
            )
        return validate_sheet_name(value)

    @field_validator("column", mode="before")
    @classmethod
    def _validate_column(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(
                f"Invalid Excel column {value!r}: expected 1..3 ASCII letters in A..XFD."
            )
        column_letters_to_index(value)
        return value.upper()

    @field_validator("row", mode="before")
    @classmethod
    def _validate_row(cls, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"Excel row must be an integer >= 1, got {value!r} "
                f"({type(value).__name__})."
            )
        if value < 1 or value > _EXCEL_MAX_ROW:
            raise ValueError(
                f"Excel row {value} is out of bounds; expected 1..{_EXCEL_MAX_ROW}."
            )
        return value

    @field_validator("unit", "provenance", mode="before")
    @classmethod
    def _validate_str_field(cls, value: object, info: ValidationInfo) -> str:
        field_name = str(info.field_name)
        if not isinstance(value, str):
            raise ValueError(
                f"Expected string metadata field {field_name}, got "
                f"{type(value).__name__}."
            )
        return _reject_control_chars(value, field_name)

    @field_validator("number_format", mode="before")
    @classmethod
    def _validate_number_format(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("number_format must be a non-empty string.")
        return _reject_control_chars(value, "number_format")

    @property
    def coord(self) -> str:
        """Return relative A1 coordinate (e.g., ``C5``)."""
        return f"{self.column}{self.row}"

    @property
    def abs_coord(self) -> str:
        """Return absolute A1 coordinate (e.g., ``$C$5``)."""
        return f"${self.column}${self.row}"

    def formula_ref(self, absolute: bool = True) -> str:
        """Return a formula-safe cross-sheet cell reference.

        Args:
            absolute: When ``True`` (default), emit ``$C$5`` coordinates; when
                ``False``, emit relative ``C5`` coordinates.

        Returns:
            Formula reference string such as ``Inputs!$C$5`` or
            ``'Cash Flow'!$C$5``.
        """
        coord_str = self.abs_coord if absolute else self.coord
        return f"{quote_sheet_name(self.sheet)}!{coord_str}"


class CellRegistry:
    """Collision-checked registry mapping logical input keys to ``CellRef``s."""

    def __init__(self) -> None:
        """Initialize an empty cell coordinate registry."""
        self._by_key: dict[str, CellRef] = {}
        self._by_coord: dict[tuple[str, str, int], str] = {}

    def register(
        self,
        key: str,
        *,
        sheet: str,
        column: str,
        row: int,
        unit: str = "",
        number_format: str = "General",
        provenance: str = "",
    ) -> CellRef:
        """Bind a unique logical ``key`` to an immutable worksheet coordinate.

        Args:
            key: Unique logical identifier for the cell.
            sheet: Target worksheet name (validated against Excel rules).
            column: Target column letters (``A``..``XFD``).
            row: Target 1-based row number.
            unit: Display/engineering unit for the cell.
            number_format: Excel number format string.
            provenance: Source/provenance note for the registered cell.

        Returns:
            The registered immutable :class:`CellRef`.

        Raises:
            ValueError: If ``key`` is empty, has leading/trailing whitespace,
                contains ASCII control characters, is already registered, or
                collides with an existing ``(sheet, column, row)`` coordinate.
        """
        if not isinstance(key, str) or not key.strip():
            raise ValueError("CellRegistry key must be a non-empty string.")
        _reject_control_chars(key, "CellRegistry key")
        if key != key.strip():
            raise ValueError(
                f"CellRegistry key {key!r} must not have leading or trailing whitespace."
            )
        cell_ref = CellRef(
            sheet=sheet,
            column=column,
            row=row,
            unit=unit,
            number_format=number_format,
            provenance=provenance,
        )
        if key in self._by_key:
            existing = self._by_key[key]
            raise ValueError(
                f"Duplicate CellRegistry key {key!r}; already bound to "
                f"{existing.formula_ref()}."
            )
        coord_key = (cell_ref.sheet.casefold(), cell_ref.column, cell_ref.row)
        if coord_key in self._by_coord:
            occupant = self._by_coord[coord_key]
            raise ValueError(
                f"Cell coordinate collision at ({cell_ref.sheet!r}, "
                f"{cell_ref.column!r}, {cell_ref.row}): already bound to key "
                f"{occupant!r}; cannot bind {key!r}."
            )
        self._by_key[key] = cell_ref
        self._by_coord[coord_key] = key
        return cell_ref

    def get(self, key: str) -> CellRef:
        """Look up the :class:`CellRef` registered for ``key``.

        Args:
            key: Logical cell key to look up.

        Returns:
            The bound :class:`CellRef`.

        Raises:
            KeyError: If ``key`` is not registered.
        """
        if key not in self._by_key:
            sample = ", ".join(repr(k) for k in list(self._by_key)[:8])
            suffix = "..." if len(self._by_key) > 8 else ""
            available = f"[{sample}{suffix}]" if self._by_key else "[]"
            raise KeyError(
                f"Unknown CellRegistry key {key!r}; registered keys "
                f"({len(self._by_key)}): {available}"
            )
        return self._by_key[key]

    def ref(self, key: str, *, absolute: bool = True) -> str:
        """Return the Excel formula reference string for a registered ``key``.

        Args:
            key: Registered logical cell key.
            absolute: When ``True`` (default), emit ``$C$5`` coordinates; when
                ``False``, emit relative ``C5`` coordinates.

        Returns:
            Formula-safe cross-sheet reference string.
        """
        return self.get(key).formula_ref(absolute=absolute)

    def range_ref(
        self,
        sheet: str,
        start_col: str,
        start_row: int,
        end_col: str,
        end_row: int,
        *,
        absolute: bool = True,
    ) -> str:
        """Return a validated formula-safe cross-sheet cell range reference.

        Args:
            sheet: Worksheet name.
            start_col: Top-left column letters (``A``..``XFD``).
            start_row: Top-left 1-based row index.
            end_col: Bottom-right column letters (``A``..``XFD``).
            end_row: Bottom-right 1-based row index.
            absolute: When ``True`` (default), emit ``$C$2:$C$10`` coordinates;
                when ``False``, emit relative ``C2:C10`` coordinates.

        Returns:
            Formula-safe cross-sheet range string.

        Raises:
            ValueError: If endpoints fail validation or ``start > end``.
        """
        start = CellRef(sheet=sheet, column=start_col, row=start_row)
        end = CellRef(sheet=sheet, column=end_col, row=end_row)
        start_col_idx = column_letters_to_index(start.column)
        end_col_idx = column_letters_to_index(end.column)
        if start_col_idx > end_col_idx or start.row > end.row:
            raise ValueError(
                f"Inverted Excel range {start.coord}:{end.coord} on sheet "
                f"{start.sheet!r}: start must precede or equal end."
            )
        start_part = start.abs_coord if absolute else start.coord
        end_part = end.abs_coord if absolute else end.coord
        return f"{quote_sheet_name(start.sheet)}!{start_part}:{end_part}"

    def keys(self) -> tuple[str, ...]:
        """Return registered keys in insertion order as an immutable tuple."""
        return tuple(self._by_key.keys())

    def __contains__(self, key: object) -> bool:
        """Return ``True`` when ``key`` is registered."""
        return key in self._by_key

    def __len__(self) -> int:
        """Return the number of registered cell bindings."""
        return len(self._by_key)


__all__ = [
    "CellRef",
    "CellRegistry",
    "column_letters_to_index",
    "quote_sheet_name",
    "validate_sheet_name",
]
