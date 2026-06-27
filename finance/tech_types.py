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


def _norm(type_value: Any) -> str:
    """Normalise a declared ``type`` to a lower-case string ("" when absent)."""
    return str(type_value).strip().lower() if type_value is not None else ""


def is_generation_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a recognised generation technology type."""
    return _norm(type_value) in GENERATION_TYPES


def is_storage_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a recognised storage technology type (e.g. bess)."""
    return _norm(type_value) in STORAGE_TYPES


def is_known_type(type_value: Any) -> bool:
    """True iff ``type_value`` is a recognised generation OR storage type."""
    return is_generation_type(type_value) or is_storage_type(type_value)


__all__ = [
    "GENERATION_TYPES",
    "STORAGE_TYPES",
    "is_generation_type",
    "is_storage_type",
    "is_known_type",
]
