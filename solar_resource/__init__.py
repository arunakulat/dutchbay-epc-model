"""Solar-resource producer (optional ``[solar]`` extra).

Mirrors ``wind_resource`` for photovoltaics: a standalone, config-driven producer that
turns a PV-system spec + a site irradiance level into a bankable annual energy / capacity
factor, which can VALIDATE (never silently overwrite) the config-declared P50 a hybrid
``generation.technologies.solar`` block carries. The heavy physics dependency (``pvlib``)
is an OPTIONAL extra, imported lazily behind a ``_require_pvlib()`` guard (CASPER), exactly
like ``py-wake`` in ``wind_resource.bankable_aep`` and WeasyPrint in ``app.reports``.

Public surface:
    SolarResourceConfig   — typed, config-first PV-system + resource inputs.
    SolarAEPResult        — the produced annual energy / CF / yield.
    compute_solar_aep     — run the pvlib pipeline to produce the result.
    validate_declared_solar_cf — VALIDATE a declared P50 CF against the producer.
"""

from __future__ import annotations

from solar_resource.pv_producer import (
    SolarAEPResult,
    SolarCfValidation,
    SolarResourceConfig,
    compute_solar_aep,
    validate_declared_solar_cf,
)

__all__ = [
    "SolarResourceConfig",
    "SolarAEPResult",
    "SolarCfValidation",
    "compute_solar_aep",
    "validate_declared_solar_cf",
]
