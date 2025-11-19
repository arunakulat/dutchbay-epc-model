"""Consolidated utility functions for the finance module."""

from typing import Any, Iterable, Mapping, Optional


def get_nested(
    d: Mapping[str, Any],
    path: Iterable[str],
    default: Any = None,
) -> Any:
    """Safely get a nested value from a mapping using a sequence of keys.

    Parameters
    ----------
    d : Mapping[str, Any]
        The mapping to traverse.
    path : Iterable[str]
        Sequence of keys to follow, e.g. ["finance", "debt", "margin"].
    default : Any, optional
        Value to return if any key is missing or the structure is not a mapping.

    Returns
    -------
    Any
        The resolved value, or `default` if any lookup fails.
    """
    result: Any = d
    for key in path:
        if not isinstance(result, Mapping):
            return default
        if key not in result:
            return default
        result = result[key]
    return result


def as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float, returning a default on failure."""
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def as_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert a value to int, returning a default on failure."""
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default
