"""Cross-validation config schema — the opt-in ``resource.crossval`` block.

Registers the required-field specs for the OPT-IN second-source cross-validation of the
ERA5 wind resource (:mod:`wind_resource.crossval`). Mirrors
:mod:`analytics.wind.era5_interface_schema` (same ``RequiredFieldSpec`` + auto-enforce
approach): when a scenario DECLARES ``resource.crossval``, the block is validated at
pre-flight (CESSPIT — no silent defaults on the source-type identity field); when it is
absent, nothing is enforced and committed scenarios are byte-identical (the disclosure
feature is strictly opt-in, default OFF).

Fields (under ``resource.crossval``):
    - ``enabled``       bool; feature is OFF unless explicitly true
    - ``source_type``   one of ``merra2`` / ``local`` / ``newa`` (validated when enabled)

``series_path`` (for ``source_type: local``) and ``drift_tolerance_pct`` are resolved and
range-checked by :func:`wind_resource.crossval.crossval_settings` at call time rather than
here, since their requirement is conditional on ``source_type`` — a dependency a flat
required-field spec cannot express (same pattern as ``reference.start_year`` in
:mod:`analytics.wind.era5_interface_schema`).

Registered with :mod:`analytics.config_schema`; enforced via
:func:`analytics.schema_guard.validate_config_for_v14` with module ``"crossval"``.
"""

from __future__ import annotations

from typing import Any

from analytics.config_schema import RequiredFieldSpec, register_required_fields
from wind_resource.crossval import CROSSVAL_SOURCES

#: Logical module name used with ``validate_config_for_v14(..., ["crossval"])``.
CROSSVAL_INTERFACE_MODULE = "crossval"


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_valid_source_type(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in CROSSVAL_SOURCES


_CROSSVAL_INTERFACE_SPECS = [
    RequiredFieldSpec(
        module=CROSSVAL_INTERFACE_MODULE,
        name="enabled",
        paths=[("resource", "crossval", "enabled")],
        description="Opt-in flag for the second-source cross-validation (bool).",
        validator=_is_bool,
    ),
    RequiredFieldSpec(
        module=CROSSVAL_INTERFACE_MODULE,
        name="source_type",
        paths=[("resource", "crossval", "source_type")],
        description="Second source: 'merra2' (SL fetch) / 'local' (file) / 'newa' (EU label).",
        validator=_is_valid_source_type,
    ),
]

# Registered at import (idempotent via Python's import cache). schema_guard maps
# the "crossval" module name to this module so validation triggers registration.
register_required_fields(CROSSVAL_INTERFACE_MODULE, _CROSSVAL_INTERFACE_SPECS)


__all__ = ["CROSSVAL_INTERFACE_MODULE"]
