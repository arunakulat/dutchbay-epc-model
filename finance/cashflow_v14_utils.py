from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Union


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float, with default fallback."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert a value to int, with default fallback."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    """Interpret a numeric as a percentage if > 1.0, otherwise as a decimal."""
    if raw is None:
        return None
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
]
