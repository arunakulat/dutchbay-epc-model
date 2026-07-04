from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Union


def as_float(
    value: Any, default: Optional[float] = None, *, key: Optional[str] = None
) -> Optional[float]:
    """Convert a value to float; ``None`` yields ``default``, malformed fails loud.

    A *present-but-non-coercible* value (e.g. ``"12,5"`` or a mapping) raises
    ``ValueError`` instead of silently returning ``default`` (#585 fail-loud):
    every caller sits on a precedence chain where a silent fallback can move a
    tax/capex base with no trace. Use :func:`as_float_or_none` where probe /
    fall-through semantics are intended (heuristic tree-walks, candidate scans).

    Args:
        value: Raw config value to coerce.
        default: Returned when ``value`` is ``None``.
        key: Optional config-key context (e.g. ``"tax.depreciable_capex_lkr"``)
            named in the error so the operator does not have to infer which
            candidate of a precedence chain held the malformed value (#683).
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        where = f" (config key {key!r})" if key else ""
        raise ValueError(
            f"as_float: cannot convert {value!r} to float{where}; supply a numeric "
            "value or omit the key (an absent/None value yields the default)"
        ) from exc


def as_int(
    value: Any, default: Optional[int] = None, *, key: Optional[str] = None
) -> Optional[int]:
    """Convert a value to int; ``None`` yields ``default``, malformed fails loud.

    Mirrors :func:`as_float`: a present-but-non-coercible value raises
    ``ValueError`` (#585 fail-loud), and ``key`` names the offending config key
    in the error when provided (#683). Use :func:`as_int_or_none` where probe /
    fall-through semantics are intended (e.g. the project-life tree-walk).
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        where = f" (config key {key!r})" if key else ""
        raise ValueError(
            f"as_int: cannot convert {value!r} to int{where}; supply an integer "
            "value or omit the key (an absent/None value yields the default)"
        ) from exc


def as_int_or_none(value: Any) -> Optional[int]:
    """Return int(value) or None if conversion fails."""
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_key_case_insensitive(d: Dict[str, Any], key: str) -> Any:
    """Resolve a mapping key exactly first, then case-insensitively."""
    if key in d:
        return d[key]
    key_lower = key.lower()
    for existing_key, value in d.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def get_nested(
    d: Dict[str, Any],
    keys: Union[str, Sequence[str]],
    default: Any = None,
) -> Any:
    """Safely navigate nested dictionaries by sequence of keys.

    Key resolution is exact first and case-insensitive second. This preserves
    canonical lower-case configs while accepting lightweight title-case test and
    hand-authored scenario dictionaries such as ``Project`` / ``Costs``.
    """
    current: Any = d
    keys_list: Sequence[str] = [keys] if isinstance(keys, str) else keys

    for key in keys_list:
        if not isinstance(current, dict):
            return default
        current = _resolve_key_case_insensitive(current, key)
        if current is None:
            return default
    return current


def as_float_or_none(value: Any) -> Optional[float]:
    """Return float(value) or None if conversion fails."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_to_decimal(raw: Optional[float]) -> Optional[float]:
    """Normalize a rate/factor to a decimal fraction, fail-loud on nonsense.

    A value in ``[0, 1]`` (and any negative, e.g. a deflationary escalation) is
    treated as an already-decimal fraction; a value in ``(1, 100]`` is treated as a
    percentage and divided by 100. A value ``> 100`` cannot be a valid rate or
    capacity factor under *either* reading, so it now raises instead of being
    silently reinterpreted as a fraction of a percent (audit D7, #573) — e.g. the
    old heuristic mapped ``150 -> 1.5`` and ``1.5 -> 0.015`` with no complaint.
    Every value on the committed/canonical path is <= 100, so this is byte-identical
    for real inputs and only converts a previously-silent mis-scaling into a loud error.
    """
    if raw is None:
        return None
    if raw > 100.0:
        raise ValueError(
            f"pct_to_decimal: {raw!r} is out of range — a rate or capacity factor "
            "must be a decimal fraction (<= 1) or a percentage (<= 100). Declare the "
            "value in decimal or percent form (a *_pct-suffixed key carries percent)."
        )
    if raw > 1.0:
        return raw / 100.0
    return raw


def resolve_first(
    cfg: Dict[str, Any],
    *candidates: Union[str, Sequence[str]],
) -> Any:
    """Resolve the first non-None value using candidate paths/keys."""
    for cand in candidates:
        if isinstance(cand, str):
            val: Any = _resolve_key_case_insensitive(cfg, cand)
        else:
            val = get_nested(cfg, cand, None)

        if val is not None:
            return val
    return None


# =============================================================================
# Revenue-basis resolution paths — the SINGLE source of truth for how the engine
# resolves the capacity and capacity-factor it bills revenue off. _build_cashflow_params
# (cashflow_v14_params) and the AEP reconciliation guard (analytics.aep_reconciliation)
# BOTH consume these so the guard reconciles exactly what the engine bills (and the two
# can never silently diverge). Order = precedence (first non-None wins). capacity_factor
# is normalized via pct_to_decimal (a value > 1.0 is a percent).
# =============================================================================

CAPACITY_MW_PATHS: tuple[Any, ...] = (
    ("project", "capacity_mw"),
    ("project", "capacity"),
    ("parameters", "capacity_mw"),
    "capacity_mw",
)

CAPACITY_FACTOR_PATHS: tuple[Any, ...] = (
    ("project", "capacity_factor_pct"),
    ("project", "capacity_factor"),
    ("production", "capacity_factor_net"),
    ("production", "capacity_factor"),
    ("parameters", "capacity_factor_pct"),
    ("parameters", "capacity_factor"),
    "capacity_factor_pct",
    "capacity_factor",
)


# =============================================================================
# Internal aliases with underscore prefix (for backward compatibility)
# =============================================================================

_as_float_or_none = as_float_or_none
_pct_to_decimal = pct_to_decimal
_resolve_first = resolve_first


__all__ = [
    "as_float",
    "as_int",
    "as_int_or_none",
    "get_nested",
    "as_float_or_none",
    "pct_to_decimal",
    "resolve_first",
    "_as_float_or_none",
    "_pct_to_decimal",
    "_resolve_first",
    "CAPACITY_MW_PATHS",
    "CAPACITY_FACTOR_PATHS",
]
