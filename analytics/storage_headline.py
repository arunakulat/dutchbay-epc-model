"""Carry a scenario's held battery option into its headline KPIs (#1823).

A scenario's ``storage_options`` block (``analytics.site_analysis_blocks``) screens a list of
battery options against the scenario's wind-only case. By default the headline KPIs stay
wind-only, and the battery exists only as a delta in the options summary. A scenario that
declares ``storage_options.headline_option: <option id>`` asks for that option to be part of
the project itself: its debt sizing, KPIs and reports then include the battery.

Only a ``held`` option can be carried this way. A held battery is never cycled for revenue
(capex and O&M only), so it needs no hourly dispatch. A ``cycled`` option's energy depends on
the hourly profile the options analysis builds, and is refused here with that reason.

Nothing is copied: the size comes from the named option, and the price (the mode of
``technology.battery.usd_per_kwh``), the O&M basis, the DC-per-nominal ratio and the
round-trip efficiency come from the same block the options summary reads. The scenario is
built by the same :func:`analytics.wind.wind_bess_options.scenario_with_battery` the options
analysis uses, so the headline KPIs equal that analysis's figures for the option.

Tariff basis (WORKING ASSUMPTION): the held battery earns no storage tariff. The regulator's
BESS tariff names solar PV only, so no storage payment is assumed for a wind project.

The combined capacity (the wind turbine plus the battery's power) must fit the block's
``grid_limits.export_limit_mw``, the limit the options summary tests as "reading A". A
held option that does not fit is refused.

The step runs once per evaluation: it replaces ``headline_option`` with
``headline_option_applied`` (a record of what was added), so a configuration that already
carries the battery is returned unchanged. A configuration that declares no headline option
is returned unchanged too, so every other scenario evaluates exactly as before.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

#: The block the headline option lives in, and its two keys.
BLOCK = "storage_options"
HEADLINE_KEY = "headline_option"
APPLIED_KEY = "headline_option_applied"

#: The tariff basis the held battery is evaluated on, recorded with the applied option.
TARIFF_BASIS = "WORKING ASSUMPTION: no storage tariff; the regulator's BESS tariff names solar PV only"


def declares_headline_option(config: Mapping[str, Any]) -> bool:
    """Return True when the configuration asks for a battery in its headline KPIs."""
    block = config.get(BLOCK) if isinstance(config, Mapping) else None
    return isinstance(block, Mapping) and HEADLINE_KEY in block


def strip_headline_option(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``config`` without its headline battery request.

    The wind battery options analysis compares every option with the wind-only case, so it
    evaluates the scenario through this function. A configuration that has already carried
    the battery into its figures cannot be made wind-only again here, and is refused.

    Raises:
        ValueError: The configuration already carries the battery.
    """
    out = dict(config)
    block = out.get(BLOCK)
    if not isinstance(block, Mapping):
        return out
    if APPLIED_KEY in block:
        raise ValueError(
            f"{BLOCK}.{APPLIED_KEY}: this configuration already carries the battery; "
            "evaluate the scenario as declared for its wind-only case"
        )
    if HEADLINE_KEY in block:
        out[BLOCK] = {k: v for k, v in block.items() if k != HEADLINE_KEY}
    return out


def apply_headline_storage_option(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``config`` with its declared headline battery added.

    Without ``storage_options.headline_option`` (or once it has been applied) the result is
    a plain copy with no key changed.

    Raises:
        ValueError: The block is malformed; the named option is not ``held``; the scenario
            has no ``generation.technologies.wind``; or the combined capacity exceeds the
            block's export limit.
    """
    if not declares_headline_option(config):
        return dict(config)
    # Imported here: the options analysis is only needed by a scenario that asks for it.
    from analytics.site_analysis_blocks import resolve_site_analysis_block
    from analytics.wind.wind_bess_options import PeakRate, scenario_with_battery

    block = resolve_site_analysis_block(config, BLOCK)
    assert block is not None  # declares_headline_option checked the block is present
    name = str(block[HEADLINE_KEY])
    option = next(o for o in block["sizes"]["options"] if str(o["id"]) == name)
    if option["operation"] != "held":
        raise ValueError(
            f"{BLOCK}.{HEADLINE_KEY}: option {name!r} is {option['operation']!r}; only a "
            "held option can be carried into the headline KPIs (a cycled option's energy "
            "comes from the options analysis's hourly dispatch)"
        )
    technologies = (config.get("generation") or {}).get("technologies") or {}
    wind = technologies.get("wind")
    if not isinstance(wind, Mapping) or "capacity_mw" not in wind:
        raise ValueError(
            f"{BLOCK}.{HEADLINE_KEY}: the scenario has no generation.technologies.wind "
            "with a capacity_mw to carry the battery beside"
        )
    power_mw = float(option["power_mw"])
    energy_mwh = float(option["energy_mwh"])
    limit_mw = float(block["grid_limits"]["export_limit_mw"])
    combined_mw = float(wind["capacity_mw"]) + power_mw
    if combined_mw > limit_mw:
        raise ValueError(
            f"{BLOCK}.{HEADLINE_KEY}: the turbine plus option {name!r} is "
            f"{combined_mw:g} MW, above grid_limits.export_limit_mw {limit_mw:g} MW"
        )
    capex_in = config.get("capex")
    if isinstance(capex_in, Mapping) and any(
        isinstance(k, str) and k.lower() in {"input", "native_input_applied"}
        for k in capex_in
    ):
        raise ValueError(
            f"{BLOCK}.{HEADLINE_KEY}: a native-currency capex.input cannot carry a headline "
            "battery yet; declare capex.usd_total, or drop the headline option"
        )
    total = capex_in.get("usd_total") if isinstance(capex_in, Mapping) else None
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        raise ValueError(
            f"{BLOCK}.{HEADLINE_KEY}: the battery's capex is added to capex.usd_total, "
            "which this scenario does not declare as a number"
        )
    battery = block["technology"]["battery"]
    usd_per_kwh = float(battery["usd_per_kwh"]["mode"])
    om_rate = float(battery["om_usd_per_dc_kwh_year"])
    dc_per_nominal = float(battery["dc_per_nominal"])
    no_premium = PeakRate(0.0, 0.0)
    out = scenario_with_battery(
        config,
        power_mw=power_mw,
        energy_mwh=energy_mwh,
        operation="held",
        usd_per_kwh=usd_per_kwh,
        om_usd_per_dc_kwh_year=om_rate,
        dc_per_nominal=dc_per_nominal,
        round_trip_efficiency=float(battery["round_trip_efficiency"]),
        delivered_mwh=0.0,
        charged_mwh=0.0,
        peak_rate=no_premium,
        wind_rate=no_premium,
        contract_years=int(block["tariff"]["contract_years"]),
    )
    # scenario_with_battery restates the per-kW figures; a scenario that does not declare
    # them (a native-currency capex.input, for example) keeps them undeclared.
    for section, key in (("capex", "capex_per_kw_usd"), ("opex", "opex_per_kw_yr_usd")):
        declared = config.get(section)
        if not (isinstance(declared, Mapping) and key in declared):
            out[section].pop(key, None)
    applied_block = {k: copy.deepcopy(v) for k, v in block.items() if k != HEADLINE_KEY}
    applied_block[APPLIED_KEY] = {
        "id": name,
        "operation": "held",
        "power_mw": power_mw,
        "energy_mwh": energy_mwh,
        "capex_usd": energy_mwh * 1000.0 * usd_per_kwh,
        "om_usd_per_year": energy_mwh * 1000.0 * dc_per_nominal * om_rate,
        "combined_capacity_mw": combined_mw,
        "export_limit_mw": limit_mw,
        "tariff_basis": TARIFF_BASIS,
    }
    out[BLOCK] = applied_block
    return out


__all__ = [
    "APPLIED_KEY",
    "BLOCK",
    "HEADLINE_KEY",
    "TARIFF_BASIS",
    "apply_headline_storage_option",
    "declares_headline_option",
    "strip_headline_option",
]
