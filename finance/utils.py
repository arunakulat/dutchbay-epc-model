"""Consolidated utility functions for the finance module."""
from typing import Any, Dict, Iterable, Optional

def get_nested(d: Dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    """Safely get nested dict value using dot-notation path."""
    result = d
    for key in path:
        if not isinstance(result, dict):
            return default
        result = result.get(key, default)
        if result is default:
            return default
    return result

def as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert value to float with fallback."""
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

def as_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert value to int with fallback."""
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default
