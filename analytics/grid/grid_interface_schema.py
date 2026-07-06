"""Grid interconnection study config schema (#872).

Defines and registers the required-field specs for the top-level ``grid`` block — the
strict, config-first (CESSPIT) contract for the design-stage grid-strength screen
(:mod:`analytics.grid.short_circuit`). The block is DEFAULT-OFF: ``grid.study_enabled``
gates the whole feature and is a strict required boolean whenever a ``grid`` block is
present (no silent default — a missing/typo'd value fails loud).

Enforcement is OPT-IN / validate-when-present: :func:`analytics.schema_guard.validate_config_for_v14`
adds the ``"grid"`` module only when a scenario actually declares a top-level ``grid``
block, so every non-grid scenario is byte-identical (KPI-neutral).

Fields (under the top-level ``grid`` key):
    - ``study_enabled``            master gate (bool; strict, no default)
    - ``poc_voltage_kv``           point-of-connection nominal voltage (kV; > 0)
    - ``source_fault_level_mva``   upstream busbar short-circuit level (MVA; > 0)
    - ``source_rx``                source Thevenin R/X ratio (>= 0)
    - ``connection_r_ohm``         connection resistance, ohms @ POC kV (>= 0)
    - ``connection_x_ohm``         connection reactance, ohms @ POC kV (>= 0)
    - ``plant_rating_mva``         aggregate plant rating, the SCR denominator (MVA; > 0)

Registered with :mod:`analytics.config_schema`; enforced via
:func:`analytics.schema_guard.validate_config_for_v14` with module ``"grid"``.
"""

from __future__ import annotations

from typing import Any

from analytics.config_schema import RequiredFieldSpec, register_required_fields

#: Logical module name used with ``validate_config_for_v14(..., ["grid"])``.
GRID_INTERFACE_MODULE = "grid"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_number(value: Any) -> bool:
    return _is_number(value) and float(value) > 0.0


def _is_nonneg_number(value: Any) -> bool:
    return _is_number(value) and float(value) >= 0.0


def _is_bool(value: Any) -> bool:
    """Strict boolean — the master gate must be a real bool, not a truthy string/int."""
    return isinstance(value, bool)


_GRID_SPECS = [
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="study_enabled",
        paths=[("grid", "study_enabled")],
        description="Master gate for the grid interconnection study (bool; default-off).",
        validator=_is_bool,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="poc_voltage_kv",
        paths=[("grid", "poc_voltage_kv")],
        description="Point-of-connection nominal voltage (kV; > 0).",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="source_fault_level_mva",
        paths=[("grid", "source_fault_level_mva")],
        description="Upstream (source) busbar short-circuit level (MVA; > 0).",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="source_rx",
        paths=[("grid", "source_rx")],
        description="Source Thevenin R/X ratio (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="connection_r_ohm",
        paths=[("grid", "connection_r_ohm")],
        description="Connection resistance, ohms referred to POC voltage (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="connection_x_ohm",
        paths=[("grid", "connection_x_ohm")],
        description="Connection reactance, ohms referred to POC voltage (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="plant_rating_mva",
        paths=[("grid", "plant_rating_mva")],
        description="Aggregate plant rating (MVA; > 0) — the SCR denominator.",
        validator=_is_positive_number,
    ),
]

# Registered at import (idempotent via Python's import cache). schema_guard maps the
# "grid" module name to this module so validation triggers registration.
register_required_fields(GRID_INTERFACE_MODULE, _GRID_SPECS)


__all__ = ["GRID_INTERFACE_MODULE"]
