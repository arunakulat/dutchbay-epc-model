"""Single source of truth for technology TYPE discriminators (CCCDIR).

A technology's CLASS is either **generation** (earns revenue as capacity_factor x tariff)
or **storage** (earns an availability/energy charge, not generation revenue). When a
``generation.technologies.<name>`` block declares an explicit ``type``, that type is
AUTHORITATIVE for the class; otherwise the class is key-sniffed (a ``capacity_factor`` ->
generation; a ``power_mw``/``energy_mwh`` rating without a capacity factor -> storage) for
backward compatibility with scenarios authored before the enum existed.

To support a new generation technology (e.g. tidal, run-of-river), add its name to
``GENERATION_TYPES`` here — it then aggregates everywhere (cashflow, tornado, generation
view) automatically, with NO other code change. This retires the old hardcoded
``("wind", "solar")`` lists scattered across the analytics layer.

"hybrid" is DERIVED from the set of technology blocks present — it is never a stored type
(storing it would be a second source of truth, CCCDIR).
"""

from __future__ import annotations

from typing import Any

#: Generation technology types — priced as ``capacity_mw x capacity_factor x tariff``.
#: Extensible: append a new generation technology and it aggregates automatically.
GENERATION_TYPES: frozenset[str] = frozenset(
    {"wind", "solar", "tidal", "hydro", "run_of_river", "geothermal"}
)

#: Storage technology types — earn an availability/energy charge (finance.bess_revenue),
#: NOT generation revenue. Mirrors ``finance.bess_revenue.BESS_TYPE``.
STORAGE_TYPES: frozenset[str] = frozenset({"bess"})

#: Generation types backed by a VALIDATED resource->finance model (a real capacity-factor
#: source): ``wind`` (``wind_resource``: ERA5 Weibull / PyWake) and ``solar``
#: (``solar_resource``: pvlib). The remaining GENERATION_TYPES members
#: (tidal/hydro/geothermal/run_of_river) are ENUM-ONLY — recognised for classification and
#: aggregation, but backed by NO resource model, so a scenario that bills one would use an
#: UNVALIDATED flat ``capacity_factor x tariff``. They are gated at generation-spec
#: resolution (ARCH-1, #474): billing an explicitly-typed enum-only tech requires the
#: per-tech opt-in ``allow_unvalidated_flat_cf: true`` so a user can never SILENTLY get a
#: fake result. Supported-tech matrix: wind/solar = modelled generation; bess = storage
#: (capacity/energy charge); tidal/hydro/geothermal/run_of_river = experimental flat-CF
#: proxy (opt-in only).
MODELLED_GENERATION_TYPES: frozenset[str] = frozenset({"wind", "solar"})


def _norm(type_value: Any) -> str:
    """Normalise a declared ``type`` to a lower-case string ("" when absent)."""
    return str(type_value).strip().lower() if type_value is not None else ""


def is_generation_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a recognised generation technology type."""
    return _norm(type_value) in GENERATION_TYPES


def is_storage_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a recognised storage technology type (e.g. bess)."""
    return _norm(type_value) in STORAGE_TYPES


def is_modelled_generation_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a generation type backed by a validated resource model.

    Only ``wind`` and ``solar`` qualify. Enum-only generation types
    (tidal/hydro/geothermal/run_of_river) return ``False`` — they are recognised for
    classification (:func:`is_generation_type`) but have no resource model, so billing one
    yields an unvalidated flat capacity-factor proxy that is gated at generation-spec
    resolution (ARCH-1, #474).
    """
    return _norm(type_value) in MODELLED_GENERATION_TYPES


def is_known_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a recognised generation OR storage type."""
    return is_generation_type(type_value) or is_storage_type(type_value)


__all__ = [
    "GENERATION_TYPES",
    "STORAGE_TYPES",
    "MODELLED_GENERATION_TYPES",
    "is_generation_type",
    "is_storage_type",
    "is_modelled_generation_type",
    "is_known_type",
]
