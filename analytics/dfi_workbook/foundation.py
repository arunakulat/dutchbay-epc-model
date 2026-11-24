"""Macro-free, formula-driven DFI workbook foundation (Control, Inputs, Ledger)."""

from __future__ import annotations

import math
import re
from collections import Counter
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
from app.reports.module_ledger import (
    _REASON_REQUIRED_STATUSES,
    ModuleExecutionLedger,
    ModuleExecutionRecord,
    ModuleExecutionStatus,
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

# Canonical status vocabulary derived directly from #1813's contract
# (app.reports.module_ledger.ModuleExecutionStatus); no second list here (#1827).
CANONICAL_LEDGER_STATUSES: tuple[str, ...] = tuple(
    status.value for status in ModuleExecutionStatus
)
_CANONICAL_LEDGER_STATUS_SET: frozenset[str] = frozenset(CANONICAL_LEDGER_STATUSES)
_REASON_REQUIRED_LEDGER_STATUSES: frozenset[str] = frozenset(
    status.value for status in _REASON_REQUIRED_STATUSES
)

SCENARIO_NOTE_ROW_LABEL: str = (
    "scenario_note (informational only; does not modify A1 F-5 hold)"
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

_HOLD_WITHDRAWAL_OR_RELIANCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "hold withdrawal claim",
        re.compile(
            r"\bhold\b[^.?!\n]{0,40}\b"
            r"(?:lifted|withdrawn|cleared|removed|waived|superseded|suspended|revoked|overridden)\b"
            r"|\b(?:lift|lifts|lifted|lifting|withdraw|withdraws|withdrew|withdrawn|withdrawing|"
            r"clear|clears|cleared|clearing|waive|waives|waived|waiving|"
            r"supersede|supersedes|superseded|superseding|"
            r"override|overrides|overrode|overridden|overriding|"
            r"revoke|revokes|revoked|revoking)\b[^.?!\n]{0,30}\bhold\b",
            re.IGNORECASE,
        ),
    ),
    (
        "non-reliance withdrawal claim",
        re.compile(
            r"\bnon[-\s_]+reliance[\s_-]+(?:lifted|withdrawn|cleared|waived|superseded|removed|revoked)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "approval or reliance qualification claim",
        re.compile(
            r"\bapproved[\s_-]+for\b"
            r"|\b(?:lender|dfi|investment|bank|credit|covenant)[\s_-]+grade\b"
            r"|\bbankab(?:le|ility)\b"
            r"|\b(?:lender|covenant|board|ic|credit|audit|external|official|formal)[\s_-]+reliance\b"
            r"|\breliance[\s_-]+(?:granted|approved|authorized|authorised|permitted|confirmed|restored)\b"
            r"|\b(?:fit|cleared|certified|qualified|usable|suitable|valid)[\s_-]+for[\s_-]+"
            r"(?:lender|covenant|board|ic|credit)\b"
            r"|\bfor[\s_-]+(?:lender|covenant|board|ic|credit)[\s_-]+"
            r"(?:use|purposes|reliance|reporting|submission)\b"
            r"|\b(?:f[\s_-]?5|covenant)[\s_-]+(?:cleared|waived|lifted|satisfied|approved|compliant)\b",
            re.IGNORECASE,
        ),
    ),
)


def _validate_non_contradictory_metadata_text(text: str, field_name: str) -> str:
    """Refuse hold-withdrawal or reliance-qualification wording in Control_Provenance."""
    for category, pattern in _HOLD_WITHDRAWAL_OR_RELIANCE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            raise ValueError(
                f"DfiWorkbookMetadata.{field_name} contains forbidden {category} "
                f"{match.group(0)!r}; free-text Control_Provenance metadata cannot "
                "withdraw, qualify, or contradict the A1 F-5 non-reliance hold."
            )
    return text


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

# A quoted literal may hold only a unit expression from the grammar below
# (optionally with one space on either side) or one character that could also
# be written escaped. Free wording beside a value would bypass the literal-text
# and reliance controls (#1828, #1906).
#
# Transactional ISO-4217 3-letter currency codes frozen from SIX ISO-4217
# Maintenance Agency List One on 2026-08-24 (same cutoff as
# analysis_tools.f5_02_lender_return, excluding non-transactional XTS/XXX).
_ISO_4217_CURRENCY_CODES: frozenset[str] = frozenset("""
    AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BHD BIF BMD BND BOB BOV
    BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP
    CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF
    GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR
    KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT
    MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN
    PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE
    SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX
    USD USN UYI UYU UYW UZS VED VES VND VUV WST XAD XAF XAG XAU XBA XBB XBC
    XBD XCD XCG XDR XOF XPD XPF XPT XSU XUA YER ZAR ZMW ZWG
    """.split())
_CURRENCY_SYMBOLS: frozenset[str] = frozenset({"$", "€", "£", "¥"})
_ENERGY_POWER_UNIT_RE = re.compile(
    r"^(?:(?:[kMGT])?(?:Wh|Wp|W|VA|VAr|var)|(?:[kM])?V|(?:[kMG])?Hz)$"
)
_TIME_UNIT_WORDS: frozenset[str] = frozenset(
    {
        "s",
        "sec",
        "secs",
        "second",
        "seconds",
        "min",
        "mins",
        "minute",
        "minutes",
        "h",
        "hr",
        "hrs",
        "hour",
        "hours",
        "d",
        "day",
        "days",
        "wk",
        "wks",
        "week",
        "weeks",
        "mo",
        "mos",
        "month",
        "months",
        "qtr",
        "qtrs",
        "quarter",
        "quarters",
        "yr",
        "yrs",
        "year",
        "years",
    }
)
_MAGNITUDE_SCALES: Mapping[str, int] = {
    "k": 1,
    "K": 1,
    "m": 2,
    "mn": 2,
    "M": 2,
    "MM": 2,
    "b": 3,
    "bn": 3,
    "B": 3,
    "t": 4,
    "tn": 4,
    "T": 4,
}
_RATIO_UNIT_WORDS: frozenset[str] = frozenset({"%", "x", "bps"})

_QUOTED_SINGLE_CHARACTERS: frozenset[str] = frozenset(" ;:,.%$€£¥()+-")
_FORMAT_TOKEN_RE = re.compile(r'"[^"]*"|\\.|.', re.DOTALL)
_LEADING_COLOR_TAG_RE = re.compile(r"^\[[A-Za-z]+\]")
_MANTISSA_RE = re.compile(r"([0#?]+(?:,[0#?]+)*)(?:\.([0#?]+))?(,*)")
_TEXT_FORMATS: frozenset[str] = frozenset({"General", "@"})


def _is_currency_atom(token: str) -> bool:
    return token in _ISO_4217_CURRENCY_CODES or token in _CURRENCY_SYMBOLS


def _is_energy_power_atom(token: str) -> bool:
    return bool(_ENERGY_POWER_UNIT_RE.fullmatch(token))


def _parse_currency_magnitude_or_atom(
    expr: str, *, allow_bare_magnitude: bool
) -> tuple[bool, Optional[int]]:
    """Parse a unit atom or ``<currency>[ ]<magnitude>`` expression."""
    if expr in _MAGNITUDE_SCALES:
        return (
            (True, _MAGNITUDE_SCALES[expr]) if allow_bare_magnitude else (False, None)
        )
    if (
        _is_currency_atom(expr)
        or _is_energy_power_atom(expr)
        or expr in _TIME_UNIT_WORDS
        or expr in _RATIO_UNIT_WORDS
    ):
        return True, None
    # Symbol + optional space + magnitude (e.g. "$m", "$ mn", "€bn").
    if expr and expr[0] in _CURRENCY_SYMBOLS:
        rest = expr[1:].lstrip(" ") if expr[1:].startswith(" ") else expr[1:]
        if rest in _MAGNITUDE_SCALES and len(expr) - len(rest) in (1, 2):
            return True, _MAGNITUDE_SCALES[rest]
    # ISO 4217 code + single space + magnitude (e.g. "USD m", "EUR mn").
    if " " in expr:
        head, _, tail = expr.partition(" ")
        if head in _ISO_4217_CURRENCY_CODES and tail in _MAGNITUDE_SCALES:
            return True, _MAGNITUDE_SCALES[tail]
    return False, None


def _parse_unit_token(core: str) -> tuple[bool, Optional[int]]:
    """Validate ``core`` against the DFI unit grammar and return magnitude scale."""
    if not core:
        return False, None
    if "/" in core:
        numerator, _, denominator = core.partition("/")
        if "/" in denominator or not numerator or not denominator:
            return False, None
        if not (
            _is_energy_power_atom(denominator)
            or denominator in _TIME_UNIT_WORDS
            or _is_currency_atom(denominator)
        ):
            return False, None
        return _parse_currency_magnitude_or_atom(numerator, allow_bare_magnitude=False)
    return _parse_currency_magnitude_or_atom(core, allow_bare_magnitude=True)


def _quoted_literal_info(content: str) -> tuple[bool, Optional[int]]:
    """Return ``(allowed, magnitude_scale)`` for the text inside quotes."""
    if content in _QUOTED_SINGLE_CHARACTERS:
        return True, None
    core = content[1:] if content.startswith(" ") else content
    core = core[:-1] if core.endswith(" ") else core
    return _parse_unit_token(core)


def _numeric_section_structure(
    section: list[tuple[str, bool]],
) -> tuple[bool, int, int]:
    """Return ``(has_zero_in_integer, percent_count, scaling_commas)``."""
    raw_unquoted = "".join(char for char, literal in section if not literal)
    body = _LEADING_COLOR_TAG_RE.sub("", raw_unquoted)
    if "general" in body.lower():
        return True, 0, 0
    match = _MANTISSA_RE.search(body)
    if match is None:  # pragma: no cover - guarded by _SUPPORTED_NUMERIC_FORMAT_RE
        return False, body.count("%"), 0
    integer_part = match.group(1)
    scaling_commas = len(match.group(3))
    return ("0" in integer_part), body.count("%"), scaling_commas


def _numeric_format_display_problem(number_format: str) -> Optional[str]:
    """Return why a grammar-valid numeric format would misstate a value.

    The grammar fixes the shape of a format; this check fixes what it shows.
    Conditional sections are refused because spreadsheet readers disagree on
    whether such a section prints the minus sign (#1828). With an explicit
    negative section, the minus sign must be written into that section, either
    as ``-`` or as parentheses, and no other section may print one. Numeric
    sections must also agree on ``%`` and trailing scaling commas, carry a ``0``
    in the integer part, and pair trailing scaling commas with a matching
    magnitude unit token (#1906).
    """
    # Each section is a list of (character, written_as_literal) pairs.
    sections: list[list[tuple[str, bool]]] = [[]]
    section_quoted_scales: list[list[int]] = [[]]
    for token in _FORMAT_TOKEN_RE.findall(number_format):
        if token == ";":
            sections.append([])
            section_quoted_scales.append([])
        elif token.startswith('"'):
            content = token[1:-1]
            allowed, scale = _quoted_literal_info(content)
            if not allowed:
                return (
                    f"quoted literal {token} is not an allowed unit token; allowed "
                    "are an ISO 4217 currency code, energy/power unit, time unit, "
                    "magnitude word (k/m/mn/bn/tn), ratio unit (%, x, bps), "
                    "per-unit form (X/Y), or one punctuation character."
                )
            if scale is not None:
                section_quoted_scales[-1].append(scale)
            sections[-1].extend((char, True) for char in content)
        elif token.startswith("\\"):
            sections[-1].append((token[1:], True))
        else:
            sections[-1].append((token, False))
    if "[<" in number_format or "[>" in number_format or "[=" in number_format:
        return "conditional sections are not supported."
    numeric_sections = sections[:3]
    scaling_signatures: list[tuple[int, int]] = []
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
        has_zero_in_int, percent_count, scaling_commas = _numeric_section_structure(
            section
        )
        if not has_zero_in_int:
            return (
                f"section {index + 1} has no '0' placeholder in its integer part, "
                "so zero or small values would be hidden."
            )
        if scaling_commas > 0:
            scales = section_quoted_scales[index]
            if not scales:
                return (
                    f"section {index + 1} uses {scaling_commas} trailing scaling "
                    "comma(s) without a magnitude unit token declaring the scale."
                )
            if len(set(scales)) != 1 or scales[0] != scaling_commas:
                return (
                    f"section {index + 1} has {scaling_commas} trailing scaling "
                    "comma(s), which does not match its magnitude unit token."
                )
        scaling_signatures.append((percent_count, scaling_commas))
    if len(set(scaling_signatures)) > 1:
        return (
            "numeric sections must not mix '%' or trailing scaling commas across "
            "sections."
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
    from the allowlist, or quoted literals holding a grammar-valid unit
    expression (ISO 4217 currency code, energy/power unit, time unit, magnitude
    word, ratio unit, or ``X/Y`` per-unit form) or one such punctuation
    character. An optional fourth section after three numeric sections accepts a
    single @ with literal affixes. Formats that openpyxl would reopen as a date,
    time, or duration are also refused.

    A format must not change what a reader sees (#1828, #1906). Text values
    accept only General or @, and boolean values accept only General (since @
    renders booleans as 1/0 in Calc). Conditional sections are refused. An
    explicit negative section must print the sign as ``-`` or parentheses, and
    the positive and zero sections must print neither. Numeric sections must
    share identical ``%`` and trailing scaling-comma scaling, carry a ``0`` in
    the integer part, and pair trailing scaling commas with a matching
    magnitude unit token. Preserve unsupported sources externally and supply a
    supported textual reference as the input value. Text must satisfy the
    literal-text contract, including its formula-prefix restriction.
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
        if isinstance(self.value, bool):
            if self.number_format == "General":
                return self
            raise ValueError(
                f"WorkbookInputItem {self.key!r} has number_format "
                f"{self.number_format!r} for a bool value. Boolean inputs accept "
                "only 'General' ('@' renders boolean values as '1'/'0' in Calc), "
                "so the displayed text always equals the stored boolean (#1906)."
            )
        if isinstance(self.value, str):
            if self.number_format in _TEXT_FORMATS:
                return self
            raise ValueError(
                f"WorkbookInputItem {self.key!r} has number_format "
                f"{self.number_format!r} for a str value. Text inputs accept "
                "only 'General' or '@', so the displayed text always equals the "
                "stored value (#1828)."
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
        if normalized not in _CANONICAL_LEDGER_STATUS_SET:
            allowed = ", ".join(CANONICAL_LEDGER_STATUSES)
            raise ValueError(
                f"Invalid ModuleLedgerEntry.status {value!r}: expected one of "
                f"#1813 ModuleExecutionStatus values ({allowed})."
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
    # Free scenario wording lives in its own explicitly labelled row and cannot
    # withdraw or qualify the F-5 non-reliance hold.
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
        field_name = str(info.field_name)
        text = _validate_literal_text(value, field_name, allow_empty=False)
        return _validate_non_contradictory_metadata_text(text, field_name)

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
        text = _validate_literal_text(value, "scenario_note", allow_empty=False)
        return _validate_non_contradictory_metadata_text(text, "scenario_note")

    @field_validator("run_mode", mode="before")
    @classmethod
    def _validate_run_mode(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        text = _validate_literal_text(value, "run_mode", allow_empty=False)
        return _validate_non_contradictory_metadata_text(text, "run_mode")


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
            SCENARIO_NOTE_ROW_LABEL,
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
        elif field_name == SCENARIO_NOTE_ROW_LABEL:
            ws.row_dimensions[row_idx].height = 30

    ws.freeze_panes = "A4"
    _apply_column_widths(ws, {"A": 34, "B": 96})


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

    rollup_statuses = CANONICAL_LEDGER_STATUSES

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


def project_module_execution_record(
    record: ModuleExecutionRecord | Mapping[str, object],
) -> ModuleLedgerEntry:
    """Project one #1813 ``ModuleExecutionRecord`` into a ``ModuleLedgerEntry``."""
    validated = ModuleExecutionRecord.model_validate(record)
    reason_text = (
        validated.reason
        if validated.reason is not None
        else (validated.caveat if validated.caveat is not None else "")
    )
    provenance_text = ", ".join(validated.provenance_refs)
    return ModuleLedgerEntry(
        module_path=validated.module_path,
        pipeline_stage=validated.pipeline_stage.value,
        role_description=validated.role_description,
        status=validated.status.value,
        excel_representation=validated.excel_representation.value,
        reason=reason_text,
        provenance_ref=provenance_text,
    )


def _normalize_execution_records(
    execution_records: (
        ModuleExecutionLedger | Sequence[ModuleExecutionRecord | Mapping[str, object]]
    ),
) -> tuple[ModuleExecutionRecord, ...]:
    """Validate an execution ledger or record sequence and enforce unique paths."""
    if isinstance(execution_records, ModuleExecutionLedger):
        return ModuleExecutionLedger.model_validate(execution_records).records
    if isinstance(execution_records, (str, bytes, Mapping, BaseModel)):
        raise ValueError(
            "execution_records must be a ModuleExecutionLedger or a sequence of "
            "ModuleExecutionRecord items."
        )
    records = tuple(
        ModuleExecutionRecord.model_validate(item) for item in execution_records
    )
    counts = Counter(record.module_path for record in records)
    duplicates = sorted(path for path, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(
            "Duplicate module_path entries in execution_records: "
            f"{', '.join(duplicates)}."
        )
    return records


def _validate_ledger_entries(
    ledger_entries: Sequence[ModuleLedgerEntry | Mapping[str, object]],
) -> tuple[ModuleLedgerEntry, ...]:
    """Validate ledger entries and refuse duplicate ``module_path`` rows."""
    if isinstance(ledger_entries, (str, bytes, Mapping, BaseModel)):
        raise ValueError(
            "ledger_entries must be a sequence of ModuleLedgerEntry items."
        )
    entries = tuple(ModuleLedgerEntry.model_validate(entry) for entry in ledger_entries)
    counts = Counter(entry.module_path for entry in entries)
    duplicates = sorted(path for path, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(
            f"Duplicate module_path entries in ledger_entries: {', '.join(duplicates)}."
        )
    return entries


def project_module_execution_ledger(
    execution_records: (
        ModuleExecutionLedger | Sequence[ModuleExecutionRecord | Mapping[str, object]]
    ),
) -> tuple[ModuleLedgerEntry, ...]:
    """Project all execution records in a run into ``ModuleLedgerEntry`` rows."""
    records = _normalize_execution_records(execution_records)
    return tuple(project_module_execution_record(record) for record in records)


def validate_ledger_against_execution_records(
    ledger_entries: Sequence[ModuleLedgerEntry | Mapping[str, object]],
    execution_records: (
        ModuleExecutionLedger | Sequence[ModuleExecutionRecord | Mapping[str, object]]
    ),
) -> tuple[ModuleLedgerEntry, ...]:
    """Validate ``Module_Ledger`` rows 1-to-1 against ``ModuleExecutionRecord`` inputs.

    Refuses duplicates, dropped execution records, orphan ledger entries, and any
    disagreement on ``pipeline_stage``, ``role_description``, ``status``, or
    ``excel_representation``.
    """
    validated_entries = _validate_ledger_entries(ledger_entries)
    validated_records = _normalize_execution_records(execution_records)

    records_by_path = {record.module_path: record for record in validated_records}
    entries_by_path = {entry.module_path: entry for entry in validated_entries}

    missing = [
        record.module_path
        for record in validated_records
        if record.module_path not in entries_by_path
    ]
    if missing:
        raise ValueError(
            "Execution record(s) missing from Module_Ledger: " f"{', '.join(missing)}."
        )

    orphans = [
        entry.module_path
        for entry in validated_entries
        if entry.module_path not in records_by_path
    ]
    if orphans:
        raise ValueError(
            "Orphan Module_Ledger entry/entries absent from execution_records: "
            f"{', '.join(orphans)}."
        )

    for entry in validated_entries:
        record = records_by_path[entry.module_path]
        mismatches: list[str] = []
        if entry.pipeline_stage != record.pipeline_stage.value:
            mismatches.append(
                f"pipeline_stage={entry.pipeline_stage!r} "
                f"(expected {record.pipeline_stage.value!r})"
            )
        if entry.role_description != record.role_description:
            mismatches.append(
                f"role_description={entry.role_description!r} "
                f"(expected {record.role_description!r})"
            )
        if entry.status != record.status.value:
            mismatches.append(
                f"status={entry.status!r} (expected {record.status.value!r})"
            )
        if entry.excel_representation != record.excel_representation.value:
            mismatches.append(
                f"excel_representation={entry.excel_representation!r} "
                f"(expected {record.excel_representation.value!r})"
            )
        if mismatches:
            raise ValueError(
                f"Module_Ledger entry for {entry.module_path!r} does not match "
                f"ModuleExecutionRecord: {'; '.join(mismatches)}."
            )

    return validated_entries


def build_dfi_workbook_foundation(
    output_path: PathLike,
    *,
    metadata: DfiWorkbookMetadata | Mapping[str, object],
    inputs: Sequence[WorkbookInputItem | Mapping[str, object]],
    ledger_entries: Optional[Sequence[ModuleLedgerEntry | Mapping[str, object]]] = None,
    execution_records: Optional[
        ModuleExecutionLedger | Sequence[ModuleExecutionRecord | Mapping[str, object]]
    ] = None,
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
        ledger_entries: Optional sequence of :class:`ModuleLedgerEntry` records or
            mappings. When omitted and ``execution_records`` is provided, rows are
            projected via :func:`project_module_execution_ledger`.
        execution_records: Optional :class:`ModuleExecutionLedger` or sequence of
            :class:`ModuleExecutionRecord` items. When provided alongside
            ``ledger_entries``, every row is strictly cross-checked against it
            before touching ``output_path``.

    Returns:
        Tuple of ``(resolved_output_path, populated_cell_registry)``.

    Raises:
        ValueError: If any record fails validation, ``inputs`` is empty,
            ``ledger_entries`` disagrees with ``execution_records``, duplicate keys
            occur, or the output path does not use ``.xlsx``.
    """
    # Revalidate typed records as well as mappings before touching the destination.
    validated_metadata = DfiWorkbookMetadata.model_validate(metadata)
    validated_inputs = [WorkbookInputItem.model_validate(item) for item in inputs]
    if not validated_inputs:
        raise ValueError(
            "inputs must contain at least one WorkbookInputItem; cannot build "
            "an Inputs sheet without registered scalar parameters."
        )
    if ledger_entries is None and execution_records is None:
        raise ValueError(
            "Must provide execution_records or ledger_entries to "
            "build_dfi_workbook_foundation."
        )
    if ledger_entries is None:
        assert execution_records is not None
        validated_ledger = list(project_module_execution_ledger(execution_records))
    elif execution_records is not None:
        validated_ledger = list(
            validate_ledger_against_execution_records(ledger_entries, execution_records)
        )
    else:
        validated_ledger = list(_validate_ledger_entries(ledger_entries))

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
    "SCENARIO_NOTE_ROW_LABEL",
    "WorkbookInputItem",
    "build_dfi_workbook_foundation",
    "project_module_execution_ledger",
    "project_module_execution_record",
    "validate_ledger_against_execution_records",
]
