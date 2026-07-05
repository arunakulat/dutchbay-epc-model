"""Coastal / complex-terrain siting METADATA — diagnostics only (issue #742).

Surfaces an optional, self-declared site ``terrain_class`` (e.g. coastal, flat,
complex) into the AEP-summary provenance / diagnostics block. It is **pure
metadata**: it applies NO AEP correction and feeds no billed quantity. It is a
companion label for the existing single-cell-vs-neighbourhood diagnostic
:func:`wind_resource.era5_grid.spatial_representativeness` — a coastal / ridge
site is exactly where that spread-vs-deviation check matters, so declaring the
terrain class makes the diagnostic's relevance explicit in provenance.

DELIBERATELY OUT OF SCOPE (KPI-moving, user-gated — a SEPARATE change):
    a terrain AEP CORRECTION FACTOR that scales the energy yield. Terrain class
    here NEVER adjusts the AEP; it only records what the site is so a reviewer can
    judge whether a correction (built elsewhere, behind a KPI gate) is warranted.

GWTF: config-first, fully typed, fail-loud on an unknown class (CESSPIT — no
silent default), no ``argparse``/``input()``, pure/unit-testable.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

#: Recognised self-declared terrain classes (IEC-61400-1-flavoured, informal).
#: Purely descriptive labels — none of them carries an AEP multiplier here.
TERRAIN_CLASSES: tuple[str, ...] = (
    "flat",
    "coastal",
    "offshore",
    "hilly",
    "complex",
    "forested",
)

#: Provenance caveat stamped into every siting block (#742 honesty discipline).
SITING_METADATA_NOTE: str = (
    "Self-declared site terrain class (metadata only); applies NO AEP correction. "
    "A terrain AEP correction factor is a separate, KPI-gated change. Pairs with the "
    "single-cell representativeness diagnostic (era5_grid.spatial_representativeness)."
)


def resolve_siting_metadata(
    resource: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """Resolve the optional ``resource.siting`` metadata block (AEP-neutral).

    Reads ``resource.siting.terrain_class`` (optional). When absent, returns
    ``None`` (the field defaults to UNSET — the summary simply omits the block).
    When present, validates it against :data:`TERRAIN_CLASSES` and returns a small
    metadata dict for the provenance / diagnostics section. Never returns or
    implies an AEP multiplier.

    Args:
        resource: The scenario ``resource`` mapping.

    Returns:
        ``None`` if no ``terrain_class`` is declared, else a dict with
        ``terrain_class``, an optional ``terrain_notes`` passthrough,
        ``applies_aep_correction`` (always ``False``) and ``note``
        (:data:`SITING_METADATA_NOTE`).

    Raises:
        ValueError: If ``terrain_class`` is declared but not a recognised class
            (fail loud — CESSPIT; no silent acceptance of an unknown label).
    """
    siting = resource.get("siting", {}) or {}
    if not isinstance(siting, Mapping):
        raise ValueError(
            f"resource.siting must be a mapping when present, got {type(siting).__name__}."
        )
    terrain_class = siting.get("terrain_class")
    if terrain_class is None:
        return None

    terrain_class = str(terrain_class).strip().lower()
    if terrain_class not in TERRAIN_CLASSES:
        raise ValueError(
            f"resource.siting.terrain_class {terrain_class!r} is not recognised; "
            f"expected one of {TERRAIN_CLASSES}."
        )

    block: Dict[str, Any] = {
        "terrain_class": terrain_class,
        "applies_aep_correction": False,
        "note": SITING_METADATA_NOTE,
    }
    notes = siting.get("terrain_notes")
    if notes is not None:
        block["terrain_notes"] = str(notes)
    return block


__all__ = [
    "resolve_siting_metadata",
    "TERRAIN_CLASSES",
    "SITING_METADATA_NOTE",
]
