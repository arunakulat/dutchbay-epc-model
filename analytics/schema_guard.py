from __future__ import annotations

import importlib
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from analytics.config_schema import get_required_fields

logger = logging.getLogger(__name__)

"""
Schema guard for v14 configs.

Validates YAML/JSON scenario configs against the v14 finance engine schema
before running cashflow or debt calculations.
"""

# Type aliases
PathSpec = tuple[str, ...]

# Constants
FX_START_KEY = "start_lkr_per_usd"
FX_DEPR_KEY = "annual_depr"
FX_REQUIRED_KEYS: tuple[str, ...] = (FX_START_KEY, FX_DEPR_KEY)
SEVERITY_ERROR = "error"


class ConfigValidationError(ValueError):
    """
    Raised when config is missing required fields or fails validation.

    Example
    -------
    >>> try:
    ...     validate_config_for_v14(cfg, "config.yaml", ["cashflow"])
    ... except ConfigValidationError as exc:
    ...     print(f"ERROR: {exc}")
    ...     raise SystemExit(1)
    """


# Logical module -> import path
# A logical module's specs may be split across SEVERAL Python modules; every one
# must be imported so registration is deterministic regardless of import order.
# In particular the EPC capex specs (epc_usd_total, ...) live in
# finance.epc_helper_v14, NOT finance.cashflow_v14 — omitting it silently skipped
# epc_usd_total validation whenever epc_helper_v14 happened not to be imported
# yet (which, since the pipeline's lazy import in #298, is the common case on a
# fresh process). Map each logical module to ALL of its registering modules.
_MODULE_IMPORTS: dict[str, tuple[str, ...]] = {
    "cashflow": ("finance.cashflow_v14", "finance.epc_helper_v14"),
    "debt": ("finance.debt_v14",),
    "irr": ("finance.irr",),
    "wind": ("analytics.wind.wind_interface_schema",),
    "era5": ("analytics.wind.era5_interface_schema",),
}


def _ensure_module_registered(name: str) -> None:
    """
    Import logical module to trigger schema registration side effects.

    The finance/analytics modules are expected to register their
    required-field specifications with analytics.config_schema on import.
    """
    for module_path in _MODULE_IMPORTS.get(name, ()):
        importlib.import_module(module_path)


def _get_nested(container: Mapping[str, Any], path: PathSpec) -> Any:
    """
    Walk a nested mapping by `path` and return the value or None.

    Parameters
    ----------
    container
        Root mapping (typically the raw config).
    path
        Tuple of keys, e.g. ("project", "capacity_mw").
    """
    current: Any = container
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current


def _first_resolved_value(
    raw_config: Mapping[str, Any],
    paths: Sequence[PathSpec],
) -> Any:
    """
    Try each candidate path in order and return the first resolved value.

    This lets a single logical field be mapped to multiple possible
    locations (for backward-compatibility or aliasing) without
    hard-coding the path.
    """
    for path in paths:
        if not path:
            continue
        parent_path = path[:-1]
        field = path[-1]
        parent = _get_nested(raw_config, parent_path)
        if isinstance(parent, Mapping) and field in parent:
            return parent[field]
    return None


def _validate_fx_section(
    raw_config: Mapping[str, Any],
    errors: list[str],
) -> None:
    """
    Validate the FX section structure.

    v14 requires an `fx` mapping with `start_lkr_per_usd` and
    `annual_depr`. Scalar `fx` configs are explicitly rejected.
    """
    fx_cfg = raw_config.get("fx")

    if fx_cfg is None:
        errors.append(
            "Missing `fx` section. Expected mapping with keys: "
            f"`{FX_START_KEY}`, `{FX_DEPR_KEY}`."
        )
        return

    if isinstance(fx_cfg, (int, float, str)):
        errors.append(
            "Invalid FX config: scalar `fx` is no longer supported in v14. "
            f"Use a mapping with `{FX_START_KEY}` and `{FX_DEPR_KEY}`."
        )
        return

    if not isinstance(fx_cfg, Mapping):
        errors.append(
            f"Invalid FX config type: {type(fx_cfg)!r} " "(expected mapping/dict)."
        )
        return

    missing = [key for key in FX_REQUIRED_KEYS if key not in fx_cfg]
    if missing:
        missing_keys = ", ".join(missing)
        errors.append(
            f"FX config missing required key(s): {missing_keys}. "
            f"Expected `{FX_START_KEY}` and `{FX_DEPR_KEY}`."
        )


def _validate_technology_types(
    raw_config: Mapping[str, Any], errors: list[str]
) -> None:
    """Validate any declared ``generation.technologies.<name>.type`` against the enum.

    ARCH-6 (#488): the schema guard is the pre-flight gatekeeper (CESSPIT), but it did not
    check the technology ``type`` — a typo (``wnid``) or an unsupported class (``battery``)
    slipped through here and only surfaced (if at all) downstream. This fails fast at
    pre-flight against the single source of truth (:mod:`finance.tech_types`).

    A ``type`` is validated only when declared: blocks without an explicit ``type`` are the
    backward-compatible key-sniff path (a ``capacity_factor`` -> generation), so this does
    not force a ``type`` on legacy scenarios. This complements the downstream #474 ARCH-1
    gate (which only fires for an explicitly-typed, billed, unmodelled generation tech).
    """
    generation = (
        raw_config.get("generation") if isinstance(raw_config, Mapping) else None
    )
    techs = generation.get("technologies") if isinstance(generation, Mapping) else None
    if not isinstance(techs, Mapping):
        return

    from finance.tech_types import GENERATION_TYPES, STORAGE_TYPES, is_known_type

    valid = ", ".join(sorted(GENERATION_TYPES | STORAGE_TYPES))
    for name, block in techs.items():
        if not isinstance(block, Mapping):
            continue
        declared = block.get("type")
        if declared is None:
            continue  # untyped -> backward-compatible key-sniff path, not gated here
        if not is_known_type(declared):
            errors.append(
                f"generation.technologies['{name}'].type={declared!r} is not a "
                f"recognised technology type (valid: {valid})"
            )


def validate_config_for_v14(
    raw_config: Mapping[str, Any],
    config_path: str | None,
    modules: Sequence[str] | None,
) -> None:
    """
    Validate raw config against registered field specs for v14.

    Parameters
    ----------
    raw_config
        Configuration dictionary produced by scenario_loader.
    config_path
        Human-friendly identifier for errors (filename or label).
    modules
        Logical module names to validate against
        (e.g. ["cashflow"], ["cashflow", "debt"]).

    Raises
    ------
    ConfigValidationError
        If required fields are missing or invalid.
    """
    errors: list[str] = []

    # 1. Validate FX section (always required for v14)
    _validate_fx_section(raw_config, errors)

    # 1b. Validate any declared technology `type` against the enum (ARCH-6, #488).
    _validate_technology_types(raw_config, errors)

    # 2. Ensure modules are imported so they can register field specs
    module_list = list(modules) if modules is not None else []

    # Auto-enforce the wind / era5 interface schemas whenever the scenario actually
    # declares a resource.wind / resource.era5 block. These lender-grade interface guards
    # were registered but DORMANT: every live caller passes ['cashflow','debt'], so a
    # scenario could carry a malformed wind/era5 block that never got validated. Adding the
    # module only when the block is present keeps non-wind scenarios untouched (and all
    # shipped wind scenarios already satisfy the schema, so this is byte-identical today).
    resource = raw_config.get("resource") if isinstance(raw_config, Mapping) else None
    if isinstance(resource, Mapping):
        for _block in ("wind", "era5"):
            if isinstance(resource.get(_block), Mapping) and _block not in module_list:
                module_list.append(_block)
    for name in module_list:
        _ensure_module_registered(name)

    # 3. Collect and validate registered specs for requested modules
    specs: list[Any] = []
    for name in module_list:
        specs.extend(get_required_fields(name))

    for spec in specs:
        logical_name: str = str(getattr(spec, "name", "<unknown>"))
        paths: Sequence[PathSpec] = getattr(spec, "paths", ()) or ()
        required: bool = bool(getattr(spec, "required", True))
        validator = getattr(spec, "validator", None)
        severity: str = str(getattr(spec, "severity", SEVERITY_ERROR)).lower()

        # Only hard-enforce error-level fields here.
        if severity != SEVERITY_ERROR:
            continue

        value = _first_resolved_value(raw_config, paths)
        ok = True

        if required and value is None:
            ok = False

        if ok and validator is not None:
            try:
                if not validator(value):
                    ok = False
            except Exception as e:
                logger.debug(
                    "Validator for '%s' raised %s: %s",
                    logical_name,
                    type(e).__name__,
                    e,
                )
                ok = False

        if not ok:
            path_labels = [".".join(p) for p in paths] or ["<no paths>"]
            errors.append(f"{logical_name} (paths: {', '.join(path_labels)})")

    # 4. Raise aggregate error if any checks failed
    if errors:
        header = (
            f"Config '{config_path}' is missing or has invalid " "required fields: "
            if config_path
            else "Config is missing or has invalid required fields: "
        )
        details = "; ".join(sorted(errors))
        raise ConfigValidationError(header + details)


__all__: list[str] = [
    "ConfigValidationError",
    "validate_config_for_v14",
]
# EOF
