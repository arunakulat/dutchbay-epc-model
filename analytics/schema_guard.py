"""
Schema guard for v14 configs.

This module sits on top of analytics.config_schema and:
  * lazily imports domain modules (cashflow, debt, irr, etc.) so that
    their schema registration side-effects run; and
  * validates a raw config dict against all registered field specs.

Usage::

    from analytics.schema_guard import validate_config_for_v14

    validate_config_for_v14(
        raw_config=config,
        config_path="scenarios/example_a.yaml",
        modules=["cashflow", "debt"],
    )
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from analytics.config_schema import get_required_fields


PathSpec = Tuple[str, ...]


class ConfigValidationError(RuntimeError):
    """Raised when a YAML / JSON config is missing required fields."""


# ---------------------------------------------------------------------------
# Lazy import map – logical module name -> import path
# ---------------------------------------------------------------------------

_MODULE_IMPORTS: Dict[str, str] = {
    # Core v14 CF stack
    "cashflow": "dutchbay_v14chat.finance.cashflow",
    "debt": "dutchbay_v14chat.finance.debt",
    "irr": "dutchbay_v14chat.finance.irr",
    # Future extensions can be added here, e.g.:
    # "monte_carlo": "dutchbay_v14chat.finance.monte_carlo",
    # "sensitivity": "dutchbay_v14chat.finance.sensitivity",
}


def _ensure_module_registered(name: str) -> None:
    """
    Ensure the given logical module has been imported so that its schema
    registration side-effects (register_required_fields) have run.

    If the name is not known in _MODULE_IMPORTS we treat it as a no-op,
    to keep the guard forwards-compatible as new modules are added.
    """
    module_path = _MODULE_IMPORTS.get(name)
    if not module_path:
        return
    importlib.import_module(module_path)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _get_nested(container: Mapping[str, Any], path: PathSpec) -> Any:
    """
    Walk a nested mapping by path segments.

    Returns the nested value at the end of the path, or None if any segment
    is missing or not a mapping.
    """
    current: Any = container
    for seg in path:
        if not isinstance(current, Mapping) or seg not in current:
            return None
        current = current[seg]
    return current


def _first_resolved_value(raw_config: Mapping[str, Any], paths: Sequence[PathSpec]) -> Any:
    """
    Try each candidate path in order and return the first resolved value.

    Each path is a tuple like ("tax", "corporate_tax_rate_pct").
    """
    for path in paths:
        if not path:
            continue
        parent_path = path[:-1]
        field = path[-1]
        parent = _get_nested(raw_config, parent_path)
        if parent is not None and isinstance(parent, Mapping) and field in parent:
            return parent[field]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_config_for_v14(
    raw_config: Dict[str, Any],
    config_path: str,
    modules: Sequence[str],
) -> None:
    """
    Validate a raw YAML/JSON config against all registered field specs
    for the given logical modules.

    Steps:
      1) Lazily import each module so its schema registration runs.
      2) Collect all RequiredFieldSpec instances for those modules.
      3) Check each spec's validator against the resolved value.
      4) Raise ConfigValidationError with a detailed message if any fail.

    Args:
        raw_config: The configuration dict loaded from YAML/JSON.
        config_path: A human-friendly identifier used in error messages
                     (usually the file path).
        modules: Sequence of logical module names, e.g. ["cashflow", "debt"].

    Raises:
        ConfigValidationError: if any required field is missing or invalid.
    """
    # 1) Ensure all relevant modules are imported so their registration runs
    for m in modules:
        _ensure_module_registered(m)

    # 2) Collect all specs from the registry
    specs: List[Any] = []
    for m in modules:
        specs.extend(get_required_fields(m))

    if not specs:
        # If nothing is registered, we deliberately treat this as a no-op.
        # It lets us bring the guard in gradually without breaking callers.
        return

    missing: List[str] = []

    for spec in specs:
        # Expected RequiredFieldSpec attributes:
        #   - name: logical field name (e.g. "corporate_tax_rate")
        #   - paths: sequence of candidate PathSpec tuples
        #   - required: whether the field must be present
        #   - validator: callable(value) -> bool (optional)
        #   - severity: "error" / "warning" / etc. (we hard-fail only errors)
        logical_name: str = str(getattr(spec, "name", "<unknown>"))
        paths: Sequence[PathSpec] = getattr(spec, "paths", ()) or ()
        required: bool = bool(getattr(spec, "required", True))
        validator = getattr(spec, "validator", None)
        severity: str = str(getattr(spec, "severity", "error")).lower()

        if severity != "error":
            # For now we only enforce error-severity fields at this layer.
            continue

        val = _first_resolved_value(raw_config, paths)
        ok = True

        # Required check
        if required and val is None:
            ok = False

        # Validator / predicate check
        if ok and validator is not None:
            try:
                if not validator(val):
                    ok = False
            except Exception:
                ok = False

        if not ok:
            path_labels = [".".join(p) for p in paths] or ["<no paths registered>"]
            missing.append(f"{logical_name} (paths: {', '.join(path_labels)})")

    if missing:
        details = "; ".join(sorted(missing))
        raise ConfigValidationError(
            f"Config '{config_path}' is missing or has invalid required fields: {details}"
        )


__all__ = [
    "ConfigValidationError",
    "validate_config_for_v14",
]
