"""Itemised solar loss chain (config-first; IEC 61724-1 / PVsyst DC->AC categories).

Decomposes the producer's flat ``system_loss_pct`` derate into NAMED loss components, so a
lender energy-yield assessment can itemise soiling / wiring / mismatch / availability /
curtailment instead of a single opaque percentage. It reuses the generic,
taxonomy-parameterised retention engine from :mod:`analytics.wind.losses_model` — that
combiner is technology-neutral (it just classifies each ``*_pct`` key as a ``reduction`` or
an ``uptime`` and multiplies the retentions); only the *taxonomy* differs between wind and
solar. Reusing it (rather than forking ~30 lines of retention maths) keeps the two stacks
from drifting, exactly as the exceedance z-table is shared via ``analytics.core.exceedance``.

The solar taxonomy is config-first (``defaults.solar_resource.loss_taxonomy`` in
``config/defaults.yaml``); a loss-shaped key NOT in it RAISES rather than being silently
dropped (CESSPIT). The engine is imported lazily inside the functions (mirroring
``wind_resource.bankable_aep``'s lazy ``analytics.wind`` import) so importing this module
stays light and pvlib-free.

Scope (avoids double-counting): this itemises the flat ``system_loss_pct`` stack only. It
deliberately EXCLUDES what the pvlib chain already models (inverter efficiency/clipping,
cell-temperature) and recurring module degradation (the finance degradation schedule); the
one-time light-induced degradation ``lid_pct`` is the sole degradation-style term and is
appropriate here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

__all__ = [
    "DEFAULT_SOLAR_LOSS_TAXONOMY",
    "default_solar_loss_taxonomy",
    "compute_net_solar_loss_factor",
    "validate_solar_loss_keys",
]

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"

#: Built-in fallback solar loss taxonomy (IEC 61724-1 / PVsyst aligned), used only when
#: ``config/defaults.yaml`` does not define ``defaults.solar_resource.loss_taxonomy``.
#: ``reduction`` -> retention 1 - pct/100; ``uptime`` -> retention pct/100.
DEFAULT_SOLAR_LOSS_TAXONOMY: Dict[str, str] = {
    "soiling_pct": "reduction",
    "dc_wiring_loss_pct": "reduction",
    "ac_wiring_loss_pct": "reduction",
    "mismatch_loss_pct": "reduction",
    "connection_loss_pct": "reduction",
    "nameplate_loss_pct": "reduction",
    "lid_pct": "reduction",
    "transformer_loss_pct": "reduction",
    "transmission_loss_pct": "reduction",
    "curtailment_pct": "reduction",
    "other_pct": "reduction",
    "availability_pct": "uptime",
    "grid_availability_pct": "uptime",
}


@lru_cache(maxsize=1)
def default_solar_loss_taxonomy() -> Dict[str, str]:
    """The config-sourced solar loss taxonomy (``config/defaults.yaml``), else the built-in.

    Mirrors :func:`analytics.wind.losses_model.default_loss_taxonomy` — config-first
    (CESSPIT / CCCDIR). Each value is normalised to ``reduction`` or ``uptime``; anything
    else is a config error and raises. If the config has no taxonomy block, the built-in
    :data:`DEFAULT_SOLAR_LOSS_TAXONOMY` is used.
    """
    import yaml  # project core dep

    try:
        data = yaml.safe_load(_DEFAULTS_PATH.read_text())
        tax = data["defaults"]["solar_resource"]["loss_taxonomy"]
    except (KeyError, TypeError):
        return dict(DEFAULT_SOLAR_LOSS_TAXONOMY)

    if not isinstance(tax, Mapping) or not tax:
        return dict(DEFAULT_SOLAR_LOSS_TAXONOMY)
    out: Dict[str, str] = {}
    for key, kind in tax.items():
        norm = str(kind).strip().lower()
        if norm not in ("reduction", "uptime"):
            raise ValueError(
                f"solar loss_taxonomy[{key!r}] must be 'reduction' or 'uptime', got {kind!r}"
            )
        out[str(key)] = norm
    return out


def compute_net_solar_loss_factor(
    losses: Mapping[str, Any],
    taxonomy: Optional[Mapping[str, str]] = None,
    *,
    exclude: Iterable[str] = (),
) -> float:
    """Return the multiplicative gross->net retention for an itemised solar losses dict.

    Resolves each ``*_pct`` key via the solar taxonomy (config-first; defaults to
    :func:`default_solar_loss_taxonomy`) and multiplies the per-component retentions,
    delegating to the generic :func:`analytics.wind.losses_model.compute_net_factor`. A
    loss-shaped key absent from the taxonomy raises (no silent drop).

    Args:
        losses: A ``resource.solar.losses`` mapping of ``*_pct`` components.
        taxonomy: Optional explicit taxonomy override (defaults to the config solar one).
        exclude: Loss keys to omit (e.g. a term modelled elsewhere in the pvlib chain).

    Returns:
        A retention factor in (0, 1]: the product of per-component retentions.
    """
    from analytics.wind.losses_model import compute_net_factor  # generic engine (DRY)

    tax = taxonomy if taxonomy is not None else default_solar_loss_taxonomy()
    return compute_net_factor(losses, tax, exclude=exclude)


def validate_solar_loss_keys(
    losses: Mapping[str, Any],
    taxonomy: Optional[Mapping[str, str]] = None,
    *,
    exclude: Iterable[str] = (),
) -> None:
    """Raise ``ValueError`` if ``losses`` carries a loss-shaped key absent from the taxonomy.

    A cheap fail-loud guard for callers that want to validate an itemised solar loss block
    without computing the factor.
    """
    from analytics.wind.losses_model import validate_loss_keys

    tax = taxonomy if taxonomy is not None else default_solar_loss_taxonomy()
    validate_loss_keys(losses, tax, exclude=exclude)
