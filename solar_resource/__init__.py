"""Solar-resource producer (optional ``[solar]`` extra).

Mirrors ``wind_resource`` for photovoltaics: a standalone, config-driven producer that
turns a PV-system spec + a site irradiance level into a bankable annual energy / capacity
factor for a hybrid ``generation.technologies.solar`` block. The heavy physics dependency
(``pvlib``) is an OPTIONAL extra, imported lazily behind a ``_require_pvlib()`` guard
(CASPER), exactly like ``py-wake`` in ``wind_resource.bankable_aep`` and WeasyPrint in
``app.reports``.

Two complementary surfaces consume the modelled CF, chosen per use:

* VALIDATE (``validate_declared_solar_cf``) — cross-checks a config-declared P50 and flags
  drift; it never mutates the scenario (the photovoltaic analogue of the ERA5/ARCO wind
  VALIDATE guard).
* OVERWRITE (``cashflow_adapter.solar_export_to_scenario_patch``) — makes the modelled CF
  the financed driver, patching the per-tech block and re-blending the project headline
  (the photovoltaic analogue of ``wind_resource.cashflow_adapter``). It is pvlib-free: it
  consumes a frozen export (``build_solar_cashflow_export``), so the finance stack never
  imports ``pvlib``.

Public surface:
    SolarResourceConfig   — typed, config-first PV-system + resource inputs.
    SolarAEPResult        — the produced annual energy / CF / yield.
    compute_solar_aep     — run the pvlib pipeline to produce the result.
    validate_declared_solar_cf — VALIDATE a declared P50 CF against the producer.
    solar_export_to_scenario_patch — OVERWRITE the financed CF from a frozen export.
    build_solar_cashflow_export — freeze a SolarAEPResult into a finance export dict.
    SolarUncertaintyBudget / SolarExceedanceResult / exceedance_levels_solar — the
        pure (pvlib-free) P50/P75/P90 exceedance build-up (IEC 61724-1 / IEA-PVPS Task 13).
    compute_net_solar_loss_factor / default_solar_loss_taxonomy / validate_solar_loss_keys —
        the config-first itemised gross->net loss chain (replaces the flat system_loss_pct).
"""

from __future__ import annotations

from solar_resource.cashflow_adapter import (
    SolarCashflowExport,
    build_solar_cashflow_export,
    solar_export_to_scenario_patch,
)
from solar_resource.exceedance import (
    SolarExceedanceResult,
    SolarUncertaintyBudget,
    exceedance_levels_solar,
)
from solar_resource.loss_model import (
    compute_net_solar_loss_factor,
    default_solar_loss_taxonomy,
    validate_solar_loss_keys,
)
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
    "SolarCashflowExport",
    "build_solar_cashflow_export",
    "solar_export_to_scenario_patch",
    "SolarUncertaintyBudget",
    "SolarExceedanceResult",
    "exceedance_levels_solar",
    "compute_net_solar_loss_factor",
    "default_solar_loss_taxonomy",
    "validate_solar_loss_keys",
]
