"""GIS → EPC wind interface schema (#22).

Defines and registers the required-field specs for the **normalized
``resource.wind`` block** — the stable contract for passing wind/AEP from the
GIS resource assessment to the EPC finance model. Downstream cashflow/metrics
should depend on this normalized block, not on raw CSVs.

Fields (under ``resource.wind``):
    - ``ws150_mean_ms``   mean hub-height (150 m) wind speed (m/s)
    - ``ws150_std_ms``    standard deviation of hub-height wind speed (m/s)
    - ``capacity_factor`` net capacity factor (0–1)
    - ``aep_gwh``         net AEP (GWh)
    - ``source_id``       AEP source identifier (must be in the approved manifest)
    - ``source_type``     source category (OEM / ECMWF / NREL)

Registered with :mod:`analytics.config_schema`; enforced via
:func:`analytics.schema_guard.validate_config_for_v14` with module ``"wind"``.

Context:
    Sprint 10 - Issue #22 (Standardize GIS → EPC wind interface schema).
"""

from __future__ import annotations

from typing import Any

from analytics.config_schema import RequiredFieldSpec, register_required_fields
from analytics.loader.aep_loader import validate_source_manifest

#: Logical module name used with ``validate_config_for_v14(..., ["wind"])``.
WIND_INTERFACE_MODULE = "wind"

#: Approved source categories for the GIS → EPC handoff. REFERENCE covers
#: open reference machines (e.g. the IEA Reference 10 MW) used when no
#: OEM-certified curve is available.
VALID_SOURCE_TYPES = frozenset({"OEM", "ECMWF", "NREL", "REFERENCE"})

# Plausible upper bound for a hub-height mean wind speed (m/s); guards typos.
_MAX_PLAUSIBLE_WS_MS = 30.0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_plausible_ws(value: Any) -> bool:
    """Mean wind speed: a positive, physically plausible m/s value."""
    return _is_number(value) and 0.0 < float(value) < _MAX_PLAUSIBLE_WS_MS


def _is_nonneg_number(value: Any) -> bool:
    """Non-negative number (e.g. a standard deviation)."""
    return _is_number(value) and float(value) >= 0.0


def _is_positive_number(value: Any) -> bool:
    """Strictly positive number (e.g. AEP in GWh)."""
    return _is_number(value) and float(value) > 0.0


def _is_capacity_factor(value: Any) -> bool:
    """Net capacity factor in the open-closed interval (0, 1]."""
    return _is_number(value) and 0.0 < float(value) <= 1.0


def _is_approved_source(value: Any) -> bool:
    """Source id must be present in the approved AEP manifest (#18)."""
    return isinstance(value, str) and validate_source_manifest(value)


def _is_valid_source_type(value: Any) -> bool:
    return isinstance(value, str) and value in VALID_SOURCE_TYPES


_WIND_INTERFACE_SPECS = [
    RequiredFieldSpec(
        module=WIND_INTERFACE_MODULE,
        name="ws150_mean_ms",
        paths=[("resource", "wind", "ws150_mean_ms")],
        description="Mean hub-height (150 m) wind speed (m/s).",
        validator=_is_plausible_ws,
    ),
    RequiredFieldSpec(
        module=WIND_INTERFACE_MODULE,
        name="ws150_std_ms",
        paths=[("resource", "wind", "ws150_std_ms")],
        description="Standard deviation of hub-height wind speed (m/s).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=WIND_INTERFACE_MODULE,
        name="capacity_factor",
        paths=[("resource", "wind", "capacity_factor")],
        description="Net capacity factor (0–1).",
        validator=_is_capacity_factor,
    ),
    RequiredFieldSpec(
        module=WIND_INTERFACE_MODULE,
        name="aep_gwh",
        paths=[("resource", "wind", "aep_gwh")],
        description="Net annual energy production (GWh).",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=WIND_INTERFACE_MODULE,
        name="source_id",
        paths=[("resource", "wind", "source_id")],
        description="AEP source id (must be in the approved manifest).",
        validator=_is_approved_source,
    ),
    RequiredFieldSpec(
        module=WIND_INTERFACE_MODULE,
        name="source_type",
        paths=[("resource", "wind", "source_type")],
        description="Source category (OEM / ECMWF / NREL).",
        validator=_is_valid_source_type,
    ),
]

# Registered at import (idempotent via Python's import cache). schema_guard maps
# the "wind" module name to this module so validation triggers registration.
register_required_fields(WIND_INTERFACE_MODULE, _WIND_INTERFACE_SPECS)


__all__ = ["WIND_INTERFACE_MODULE", "VALID_SOURCE_TYPES"]
