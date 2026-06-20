"""ERA5 (ARCO single-point) request schema — the ``resource.era5`` block.

Defines and registers the required-field specs for the **co-located ARCO ERA5
retrieval config** that drives :class:`wind_resource.era5_retrieval.ERA5RequestConfig`
from the *same* scenario file as the finance model (CESSPIT single-source-of-truth):
the site centroid, the reference window, and the hub height used for shear
extrapolation all live next to ``resource.wind`` / ``turbine`` rather than in a
separate YAML that could silently drift.

Fields (under ``resource.era5``):
    - ``latitude`` / ``longitude``   site centroid (decimal degrees)
    - ``reference.mode``             ``fixed`` (reproducible, default for lender runs)
                                     or ``latest`` (rolling — exploratory only)
    - ``hub_height_m``               shear-extrapolation hub height; MUST equal
                                     ``turbine.hub_height_m`` (cross-asserted in the adapter)
    - ``strict_coverage``            fail (not warn) on a latency-truncated series

``reference.start_year`` / ``reference.end_year`` are required only when
``mode == fixed``; that conditional is enforced by the adapter
(:func:`wind_resource.arco_assessment.era5_config_from_scenario`), not here, since a
flat required-field spec cannot express the dependency.

Registered with :mod:`analytics.config_schema`; enforced via
:func:`analytics.schema_guard.validate_config_for_v14` with module ``"era5"``.
"""

from __future__ import annotations

from typing import Any

from analytics.config_schema import RequiredFieldSpec, register_required_fields

#: Logical module name used with ``validate_config_for_v14(..., ["era5"])``.
ERA5_INTERFACE_MODULE = "era5"

#: Supported reference-window modes (see the module docstring).
VALID_REFERENCE_MODES = frozenset({"fixed", "latest"})

# Plausible hub-height band (m); guards typos / unit errors.
_HUB_HEIGHT_MIN_M = 10.0
_HUB_HEIGHT_MAX_M = 300.0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_latitude(value: Any) -> bool:
    return _is_number(value) and -90.0 <= float(value) <= 90.0


def _is_longitude(value: Any) -> bool:
    return _is_number(value) and -180.0 <= float(value) <= 180.0


def _is_reference_mode(value: Any) -> bool:
    return isinstance(value, str) and value in VALID_REFERENCE_MODES


def _is_plausible_hub_height(value: Any) -> bool:
    return _is_number(value) and _HUB_HEIGHT_MIN_M <= float(value) <= _HUB_HEIGHT_MAX_M


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


_ERA5_INTERFACE_SPECS = [
    RequiredFieldSpec(
        module=ERA5_INTERFACE_MODULE,
        name="latitude",
        paths=[("resource", "era5", "latitude")],
        description="Site centroid latitude (decimal degrees, -90..90).",
        validator=_is_latitude,
    ),
    RequiredFieldSpec(
        module=ERA5_INTERFACE_MODULE,
        name="longitude",
        paths=[("resource", "era5", "longitude")],
        description="Site centroid longitude (decimal degrees, -180..180).",
        validator=_is_longitude,
    ),
    RequiredFieldSpec(
        module=ERA5_INTERFACE_MODULE,
        name="reference_mode",
        paths=[("resource", "era5", "reference", "mode")],
        description="Reference-window mode: 'fixed' (reproducible) or 'latest' (rolling).",
        validator=_is_reference_mode,
    ),
    RequiredFieldSpec(
        module=ERA5_INTERFACE_MODULE,
        name="hub_height_m",
        paths=[("resource", "era5", "hub_height_m")],
        description="Shear-extrapolation hub height (m); must equal turbine.hub_height_m.",
        validator=_is_plausible_hub_height,
    ),
    RequiredFieldSpec(
        module=ERA5_INTERFACE_MODULE,
        name="strict_coverage",
        paths=[("resource", "era5", "strict_coverage")],
        description="Fail (True) rather than warn on a latency-truncated ERA5 series.",
        validator=_is_bool,
    ),
]

# Registered at import (idempotent via Python's import cache). schema_guard maps
# the "era5" module name to this module so validation triggers registration.
register_required_fields(ERA5_INTERFACE_MODULE, _ERA5_INTERFACE_SPECS)


__all__ = ["ERA5_INTERFACE_MODULE", "VALID_REFERENCE_MODES"]
