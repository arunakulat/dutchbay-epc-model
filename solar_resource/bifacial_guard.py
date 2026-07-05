"""SOLAR-9 bifacial-in-chain discipline guard (config-correctness; byte-identical).

Promotes the SOLAR-9 doc note in :mod:`solar_resource.pv_producer` from a comment to an
ENFORCED validation. The rule (from the deep-research audit #485 disposition, re-verified):

    The financed / producer solar chain is MONOFACIAL by design. The committed hybrid lender
    pack finances the frozen monofacial pvlib yield (CF 0.1685). A bifacial rear-side uplift
    (typ. +5-10%) is NOT validated for the committed pack and must never silently inflate the
    billed capacity factor.

The ONLY place bifacial is legitimately applied is the standalone *illustrative*
``scripts/generate_solar_assessment_report.py``, which discloses ``cf_mono`` vs ``cf_bifacial``
side by side and is explicit that its headline carries the (un-validated) uplift. That report
sets ``project.capacity_factor`` directly and calls ``run_v14_pipeline`` — it deliberately does
NOT route through the frozen-export / cashflow-adapter finance bridge — so this guard, which
fires only on that bridge, never touches the report's legitimate disclosure.

Where the guard fires
---------------------
:func:`assert_monofacial_financed_cf` is called by
:func:`solar_resource.cashflow_adapter.solar_export_to_scenario_patch` — the OVERWRITE bridge
that makes a modelled solar CF the *billed* quantity. It inspects both the frozen export dict
and the target scenario's ``resource.solar`` block for a bifacial-uplift marker
(``bifacial_gain`` / ``bifacial_gain_pct`` / ``bifacial`` truthy), and RAISES
:class:`BifacialInFinancedChainError` if one is present. A neutral gain (1.0 / 0.0 / absent) is
a no-op, so EVERY committed scenario (none of which declares bifacial) is byte-identical.

Why a guard, not a silent strip: silently dropping a caller's bifacial gain would hide intent;
per CESSPIT the financed chain fails LOUD with an actionable message that points the caller at
the illustrative report for a disclosed side-by-side instead.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

__all__ = [
    "BIFACIAL_MARKER_KEYS",
    "BifacialInFinancedChainError",
    "detect_bifacial_uplift",
    "assert_monofacial_financed_cf",
]

#: Keys that, when present and non-neutral, mark a bifacial rear-side uplift. ``bifacial_gain``
#: is a multiplier (1.07 = +7%); ``bifacial_gain_pct`` is the same as a percent (7.0); a truthy
#: ``bifacial`` flag also trips the guard (an explicit intent to finance bifacial).
BIFACIAL_MARKER_KEYS: tuple[str, ...] = (
    "bifacial_gain",
    "bifacial_gain_pct",
    "bifacial",
)


class BifacialInFinancedChainError(ValueError):
    """Raised when a bifacial uplift is routed into the FINANCED solar CF chain (SOLAR-9).

    Carries the offending key and value so the finance bridge fails loud with an actionable
    message rather than silently booking an un-validated rear-side gain.
    """

    def __init__(self, key: str, value: Any, *, where: str) -> None:
        self.key = key
        self.value = value
        self.where = where
        super().__init__(
            f"Bifacial uplift {key!r}={value!r} found in {where}, but the FINANCED solar CF "
            "chain is monofacial by design (SOLAR-9): the committed lender pack finances the "
            "frozen monofacial pvlib yield. Remove the bifacial marker from the financed "
            "path. For a disclosed monofacial-vs-bifacial side-by-side, use the illustrative "
            "scripts/generate_solar_assessment_report.py (which does not bill off the uplift)."
        )


def _is_neutral(key: str, value: Any) -> bool:
    """A bifacial marker is neutral (no uplift) when it is a unit multiplier / zero / falsey.

    ``bifacial_gain`` neutral at 1.0; ``bifacial_gain_pct`` neutral at 0.0; ``bifacial`` neutral
    when falsey. A non-numeric value for a numeric key is treated as non-neutral (fail loud).
    """
    if key == "bifacial":
        return not bool(value)
    if value is None:
        return True
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    if key == "bifacial_gain":
        return num == 1.0
    if key == "bifacial_gain_pct":
        return num == 0.0
    return False  # pragma: no cover - unreachable for known keys


def detect_bifacial_uplift(
    source: Optional[Mapping[str, Any]],
) -> Optional[tuple[str, Any]]:
    """Return the first ``(key, value)`` bifacial-uplift marker in ``source``, else None.

    A neutral marker (gain 1.0, gain_pct 0.0, falsey ``bifacial``) is ignored. ``source=None``
    or a non-mapping returns None (nothing to guard).
    """
    if not isinstance(source, Mapping):
        return None
    for key in BIFACIAL_MARKER_KEYS:
        if key in source:
            value = source[key]
            if not _is_neutral(key, value):
                return key, value
    return None


def assert_monofacial_financed_cf(
    export: Optional[Mapping[str, Any]] = None,
    scenario_solar_block: Optional[Mapping[str, Any]] = None,
) -> None:
    """Refuse a bifacial uplift in the FINANCED solar CF chain (SOLAR-9; CESSPIT fail-loud).

    Inspects the frozen export dict and the scenario's ``resource.solar`` block for a
    non-neutral bifacial marker and raises if one is present. A no-op when neither carries a
    bifacial gain — so every committed scenario (none declares bifacial) passes unchanged.

    Args:
        export: The frozen solar export dict handed to the finance bridge, or None.
        scenario_solar_block: The scenario's ``resource.solar`` mapping, or None.

    Raises:
        BifacialInFinancedChainError: a non-neutral bifacial marker is present in either input.
    """
    hit = detect_bifacial_uplift(export)
    if hit is not None:
        raise BifacialInFinancedChainError(
            hit[0], hit[1], where="the frozen solar export"
        )
    hit = detect_bifacial_uplift(scenario_solar_block)
    if hit is not None:
        raise BifacialInFinancedChainError(
            hit[0], hit[1], where="the scenario resource.solar block"
        )
