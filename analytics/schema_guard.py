"""
Schema guard for v14 configs.

This module is a thin safety layer that makes sure a YAML/JSON scenario
config is structurally compatible with the **v14 finance engine** before
you try to run any cashflow or debt calculations.

It does two main things:

  1. Lazily imports the v14 engine modules (cashflow, debt, irr, etc.)
     so that their `register_required_fields(...)` calls run and populate
     the central schema registry.

  2. Walks the raw config dict and checks that all required fields
     (for the selected logical modules) are present and valid. If not,
     it raises a `ConfigValidationError` with a human-readable list of
     what is missing or invalid.

Typical usage in code that is about to run the v14 pipeline::

    from analytics.schema_guard import validate_config_for_v14
    from analytics.scenario_loader import load_scenario_config

    raw = load_scenario_config("scenarios/example_a.yaml")
    validate_config_for_v14(
        raw_config=raw,
        config_path="scenarios/example_a.yaml",
        modules=["cashflow", "debt"],
    )
    # Only if the schema passes do we hand off to finance.cashflow_v14 /
    # finance.debt_v14 / finance.irr.

You should think of this as a **pre-flight checklist** for configs:
it fails early, with clear messages, before any heavy finance logic runs.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from analytics.config_schema import get_required_fields

# A PathSpec is a tuple of keys that describe how to walk a nested dict,
# e.g. ("tax", "corporate_tax_rate_pct") -> raw_config["tax"]["corporate_tax_rate_pct"]
PathSpec = Tuple[str, ...]


class ConfigValidationError(RuntimeError):
    """
    Raised when a YAML / JSON config is missing required fields or fails
    validation for the v14 finance engine.

    This is deliberately a RuntimeError subclass so callers can either:
      * let it bubble up and fail fast, or
      * catch it and present a user-friendly error message.

    Example (CLI style)::

        try:
                validate_config_for_v14(
                raw_config=cfg,
                config_path=config_path,
                modules=["cashflow", "debt"],
            )

        except ConfigValidationError as exc:
            print(f"ERROR: {exc}")
            raise SystemExit(1)
    """


# ---------------------------------------------------------------------------
# Lazy import map – logical module name -> import path
# ---------------------------------------------------------------------------

# IMPORTANT:
#   These logical names ("cashflow", "debt", "irr") are what callers pass
#   into `validate_config_for_v14(modules=[...])`.
#
#   The import paths now point to the **canonical v14 engine surface**
#   under `finance.*`. There are **no** dutchbay_v14chat imports here.
#
#   If you introduce a new engine module that registers required fields,
#   add it to this map so the guard can import it on demand.
_MODULE_IMPORTS: Dict[str, str] = {
    # Core v14 finance stack
    "cashflow": "finance.cashflow_v14",
    "debt": "finance.debt_v14",
    "irr": "finance.irr",
    # Future extensions can be added here, e.g.:
    # "monte_carlo": "analytics.monte_carlo_v14",
    # "sensitivity": "analytics.sensitivity_v14",
}


def _ensure_module_registered(name: str) -> None:
    """
    Ensure the given logical module has been imported so that its schema
    registration side-effects run.

    The actual schema definition lives in the engine modules (e.g.
    finance.cashflow_v14). Those modules call
    `register_required_fields("cashflow", [...])` at import time.

    This helper:
      * looks up the real import path in _MODULE_IMPORTS,
      * imports the module (if present),
      * and does nothing if the logical name is unknown.

    That "do nothing if unknown" behaviour keeps this guard forward-compatible:
    callers can start passing new logical module names before we wire them
    into this map, and it will be treated as a no-op until then.
    """
    module_path = _MODULE_IMPORTS.get(name)
    if not module_path:
        # Unknown logical name: treat as a no-op. This lets us add new
        # modules gradually without breaking existing callers.
        return
    importlib.import_module(module_path)


# ---------------------------------------------------------------------------
# Core helpers – nested lookup and value resolution
# ---------------------------------------------------------------------------


def _get_nested(container: Mapping[str, Any], path: PathSpec) -> Any:
    """
    Walk a nested mapping by path segments and return the value, or None.

    Args:
        container: The root config dict (typically the full raw_config).
        path: A tuple of keys like ("tax", "corporate_tax_rate_pct").

    Returns:
        The value at the nested path if all segments exist, otherwise None.

    This is intentionally forgiving: if any segment is missing or the
    structure changes (e.g. a non-mapping), it just returns None instead
    of raising KeyError. The validator layer decides whether that is a
    hard error based on the RequiredFieldSpec.
    """
    current: Any = container
    for seg in path:
        if not isinstance(current, Mapping) or seg not in current:
            return None
        current = current[seg]
    return current


def _first_resolved_value(
    raw_config: Mapping[str, Any], paths: Sequence[PathSpec]
) -> Any:
    """
    Try each candidate path in order and return the first resolved value.

    Many fields can live in more than one place depending on config
    evolution. A RequiredFieldSpec therefore typically provides a list
    of candidate paths. For example:

        paths = [
            ("tax", "corporate_tax_rate_pct"),
            ("taxes", "corp_tax_rate_pct"),  # legacy alias
        ]

    This helper attempts each path, in order, and returns the first
    non-None value. If none resolve, it returns None.
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
# Public API – v14 config validation entry point
# ---------------------------------------------------------------------------


def validate_config_for_v14(
    raw_config: Dict[str, Any],
    config_path: str,
    modules: Sequence[str],
) -> None:
    """
    Validate a raw YAML/JSON config against all registered field specs
    for the given logical modules.

    This is the main entry point used by the v14 pipeline before running
    any heavy finance computations. It is intentionally simple to use:

        validate_config_for_v14(
            raw_config=cfg,
            config_path="scenarios/full_model_variables_updated.yaml",
            modules=["cashflow", "debt", "irr"],
        )

    If **any** required field (for those modules) is missing or fails its
    predicate, this will raise `ConfigValidationError` with a descriptive
    list of logical field names and their candidate paths.

    Args:
        raw_config:
            The configuration dict loaded from YAML/JSON. This is the full
            scenario config, not a partial view.
        config_path:
            A human-friendly identifier used in error messages
            (usually the file path on disk).
        modules:
            Sequence of logical module names, e.g. ["cashflow", "debt"].
            These names are mapped via _MODULE_IMPORTS to real engine
            modules under `finance.*` or `analytics.*`.

    Raises:
        ConfigValidationError:
            If any required field for the selected modules is missing
            or fails its validator predicate.
    """
    # 1) Ensure all relevant modules are imported so their schema
    #    registration side-effects run before we read the registry.
    for m in modules:
        _ensure_module_registered(m)

    # 2) Collect all RequiredFieldSpec instances from the registry
    specs: List[Any] = []
    for m in modules:
        specs.extend(get_required_fields(m))

    if not specs:
        # If nothing is registered, we deliberately treat this as a no-op.
        # This lets us introduce the guard gradually without breaking
        # existing callers or partially migrated modules.
        return

    missing: List[str] = []

    for spec in specs:
        # Expected RequiredFieldSpec attributes:
        #   - name: logical field name (e.g. "corporate_tax_rate")
        #   - paths: sequence of candidate PathSpec tuples
        #   - required: whether the field must be present
        #   - validator: callable(value) -> bool (optional)
        #   - severity: "error" / "warning" / etc.
        logical_name: str = str(getattr(spec, "name", "<unknown>"))
        paths: Sequence[PathSpec] = getattr(spec, "paths", ()) or ()
        required: bool = bool(getattr(spec, "required", True))
        validator = getattr(spec, "validator", None)
        severity: str = str(getattr(spec, "severity", "error")).lower()

        # For now we only enforce error-severity fields at this layer.
        if severity != "error":
            continue

        val = _first_resolved_value(raw_config, paths)
        ok = True

        # Required presence check
        if required and val is None:
            ok = False

        # Validator / predicate check
        if ok and validator is not None:
            try:
                if not validator(val):
                    ok = False
            except Exception:
                # We treat validator exceptions as a hard failure – better
                # to fail fast and fix the validator than silently ignore.
                ok = False

        if not ok:
            path_labels = [".".join(p) for p in paths] or ["<no paths registered>"]
            missing.append(f"{logical_name} (paths: {', '.join(path_labels)})")

    if missing:
        details = "; ".join(sorted(missing))
        raise ConfigValidationError(
        f"Config '{config_path}' is missing or has invalid required "
        f"fields: {details}"
    )



__all__ = [
    "ConfigValidationError",
    "validate_config_for_v14",
]
