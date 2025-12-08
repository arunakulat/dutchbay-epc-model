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


def get_nested(d: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    """Safely navigate nested dictionaries by sequence of keys."""
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def _as_float_or_none(value: Any) -> Optional[float]:
    """Return float(value) or None."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_to_decimal(raw: Optional[float]) -> Optional[float]:
    """
    Interpret a numeric as a percentage if > 1.0, otherwise as a decimal.

    Examples
    --------
    24   -> 0.24
    0.24 -> 0.24
    """
    if raw is None:
        return None
    if raw > 1.0:
        return raw / 100.0
    return raw


def _resolve_first(cfg: Dict[str, Any], *candidates: Union[str, Sequence[str]]) -> Any:
    """
    Resolve the first non-None value using a list of candidate paths/keys.

    Each candidate can be:
      - A string (top-level key)
      - A (k1, k2, ...) sequence representing a nested path
    """
    for cand in candidates:
        if isinstance(cand, (list, tuple)):
            val = get_nested(cfg, list(cand), None)
        else:
            val = cfg.get(cand)
        if val is not None:
            return val
    return None


__all__ = [
    "as_float",
    "as_int",
    "as_int_or_none",
    "get_nested",
    "_as_float_or_none",
    "_pct_to_decimal",
    "_resolve_first",
]
