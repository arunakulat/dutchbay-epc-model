from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Union


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float, with default fallback.

    Parameters
    ----------
    value : Any
        Value to convert to float.
    default : Optional[float]
        Default value if conversion fails.

    Returns
    -------
    Optional[float]
        Converted float or default.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert a value to int, with default fallback.

    Parameters
    ----------
    value : Any
        Value to convert to int.
    default : Optional[int]
        Default value if conversion fails.

    Returns
    -------
    Optional[int]
        Converted int or default.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_int_or_none(value: Any) -> Optional[int]:
    """Return int(value) or None if conversion fails.

    Parameters
    ----------
    value : Any
        Value to convert to int.

    Returns
    -------
    Optional[int]
        Converted int or None.
    """
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def get_nested(
    d: Dict[str, Any],
    keys: Union[str, Sequence[str]],
    default: Any = None,
) -> Any:
    """Safely navigate nested dictionaries by sequence of keys.

    Supports both single string keys (for top-level access) and sequences
    of keys (for nested access).

    Parameters
    ----------
    d : Dict[str, Any]
        Root dictionary to navigate.
    keys : Union[str, Sequence[str]]
        Either a single string key or sequence of keys representing a path.
    default : Any
        Default value if path not found.

    Returns
    -------
    Any
        Value at path or default if path missing.

    Examples
    --------
    >>> config = {'tax': {'rate': 0.3}}
    >>> get_nested(config, ['tax', 'rate'])
    0.3
    >>> get_nested(config, 'tax')
    {'rate': 0.3}
    """
    current: Any = d
    # Convert single string to list for uniform iteration
    if isinstance(keys, str):
        keys_list: Sequence[str] = [keys]
    else:
        keys_list = keys

    for key in keys_list:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def as_float_or_none(value: Any) -> Optional[float]:
    """Return float(value) or None if conversion fails.

    Parameters
    ----------
    value : Any
        Value to convert to float.

    Returns
    -------
    Optional[float]
        Converted float or None.
    """
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_to_decimal(raw: Optional[float]) -> Optional[float]:
    """Interpret a numeric as a percentage if > 1.0, otherwise as a decimal.

    Heuristic: values > 1.0 are treated as percentages (divided by 100),
    otherwise treated as decimals (returned as-is).

    Parameters
    ----------
    raw : Optional[float]
        Numeric value to interpret.

    Returns
    -------
    Optional[float]
        Decimal representation or None.

    Examples
    --------
    >>> pct_to_decimal(24)
    0.24
    >>> pct_to_decimal(0.24)
    0.24
    >>> pct_to_decimal(None)
    None
    """
    if raw is None:
        return None
    if raw > 1.0:
        return raw / 100.0
    return raw


def resolve_first(
    cfg: Dict[str, Any],
    *candidates: Union[str, Sequence[str]],
) -> Any:
    """Resolve the first non-None value using a list of candidate paths/keys.

    Mirrors the flexible path resolution used in cashflow_v14_params,
    allowing schema migration and backward compatibility by checking
    multiple possible locations for a single logical field.

    Parameters
    ----------
    cfg : Dict[str, Any]
        Configuration dictionary to search.
    *candidates : Union[str, Sequence[str]]
        Variable-length candidate paths. Each can be:
        - A string (top-level key)
        - A tuple/list of strings (nested path)

    Returns
    -------
    Any
        First non-None value found, or None if all candidates fail.

    Examples
    --------
    >>> config = {'project': {'capacity_mw': 150}}
    >>> # Check either top-level or nested path
    >>> resolve_first(
    ...     config,
    ...     'capacity_mw',
    ...     ('project', 'capacity_mw'),
    ... )
    150
    """
    for cand in candidates:
        # Type narrowing via isinstance check - mypy correctly infers types
        if isinstance(cand, str):
            # cand is narrowed to str in this branch
            val: Any = cfg.get(cand)
        else:
            # cand is narrowed to Sequence[str] in this branch
            val = get_nested(cfg, cand, None)

        if val is not None:
            return val
    return None


# =============================================================================
# Internal aliases with underscore prefix (for backward compatibility)
# =============================================================================
# These maintain compatibility with existing imports in cashflow_v14_params
# and cashflow_v14_fx which use underscore-prefixed names.

_as_float_or_none = as_float_or_none
"""Alias: as_float_or_none (internal use via underscore prefix)."""

_pct_to_decimal = pct_to_decimal
"""Alias: pct_to_decimal (internal use via underscore prefix)."""

_resolve_first = resolve_first
"""Alias: resolve_first (internal use via underscore prefix)."""


__all__ = [
    "as_float",
    "as_int",
    "as_int_or_none",
    "get_nested",
    "as_float_or_none",
    "pct_to_decimal",
    "resolve_first",
    # Internal aliases
    "_as_float_or_none",
    "_pct_to_decimal",
    "_resolve_first",
]
